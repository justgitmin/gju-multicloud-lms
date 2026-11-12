import copy,json,threading,time,unittest
from unittest.mock import Mock,patch
from cloudops.resource_ops import Resources,capabilities
from cloudops.providers import CloudError
import test_nhn_batch as fixture

class Cloud(fixture.FakeAPI):
 states={};calls=[];fail_storage=False
 def compute(self,tenant):
  client=Mock();client.http=Mock()
  client.inventory=lambda:[{'remote_id':'server-gju-nhn-s'+code+'-web','name':'gju-nhn-s'+code+'-web','state':status,'ip':'1.2.3.4'} for code,status in self.states.items()]
  def action(remote,action):
   self.calls.append((action,remote));code=remote.split('-s')[-1].split('-')[0]
   if action=='delete':self.states.pop(code,None)
   else:self.states[code]='SHUTOFF' if action=='stop' else 'ACTIVE'
  client.action=action;return client
 def container(self,*args,**kw):
  if self.fail_storage:raise CloudError('storage HTTP 403')
  return super().container(*args,**kw)
 def rds(self,product,path,body=None,method=None):
  if path.endswith(('/start','/stop')):
   self.calls.append((method,path));rid=path.split('/')[-2]
   for x in self.objects['/db-instances']:
    if x['dbInstanceId']==rid:x['dbInstanceStatus']='SHUTDOWN' if path.endswith('/stop') else 'AVAILABLE'
   return {'jobId':'action-job'}
  if path=='/db-instances' and body is None and method is None:
   return {'dbInstances':[{**x,'dbInstanceStatus':x.get('dbInstanceStatus','AVAILABLE'),'progressStatus':'NONE'} for x in self.objects.get(path,[])]}
  return super().rds(product,path,body,method)

class OperationTests(unittest.TestCase):
 setUp=fixture.BatchTests.setUp
 tearDown=fixture.BatchTests.tearDown
 post=fixture.BatchTests.post
 create=fixture.BatchTests.create
 def prepare(self):
  id=self.create(True);self.manager.apply(id);Cloud.states={'01':'ACTIVE','02':'ACTIVE'};Cloud.calls=[];Cloud.fail_storage=False
  self.control=Resources(self.db,self.vault,threading.Event());self.api=patch('cloudops.resource_ops.API',Cloud);self.api.start();self.addCleanup(self.api.stop)
  self.control.sync(id);return id
 def row(self,id,kind,student='s01'):return next(r for r in self.control.catalog(id) if r['kind']==kind and r['student']==student)
 def perform(self,id,row,action):return self.control.apply(id,[{'id':row['id'],'remote_id':row['remote_id']}],action,'job-test')
 def test_server_stop_start_and_individual_delete_preserve_other_students(self):
  id=self.prepare();row=self.row(id,'server');self.perform(id,row,'STOP');self.assertEqual(self.row(id,'server')['state'],'SHUTOFF')
  self.perform(id,row,'START');self.assertEqual(self.row(id,'server')['state'],'ACTIVE')
  with self.assertRaises(CloudError):self.perform(id,row,'DELETE')
  self.perform(id,row,'STOP');self.perform(id,row,'DELETE');self.assertEqual(self.row(id,'server')['presence'],0);self.assertEqual(Cloud.states['02'],'ACTIVE')
  self.assertTrue(self.db.one("SELECT id FROM resource_actions WHERE action='DELETE' AND status='REQUESTED'"))
  self.assertEqual(self.db.one("SELECT status FROM nhn_items WHERE student='s01'")['status'],'RESOURCE_DELETED')
 def test_database_stop_start_without_rotating_password(self):
  id=self.prepare();before=self.vault.open(self.db.one('SELECT state FROM nhn_batches')['state'],'nhn-state:'+id)['s01']['access'];row=self.row(id,'database')
  self.perform(id,row,'STOP');self.assertEqual(self.row(id,'database')['state'],'SHUTDOWN');self.perform(id,row,'START');self.assertEqual(self.row(id,'database')['state'],'AVAILABLE')
  after=self.vault.open(self.db.one('SELECT state FROM nhn_batches')['state'],'nhn-state:'+id)['s01']['access'];self.assertEqual(before,after)
 def test_storage_no_power_controls_and_nonempty_delete_blocked(self):
  id=self.prepare();row=self.row(id,'container');self.assertEqual(row['actions'],['DELETE'])
  for action in ['START','STOP']:
   with self.assertRaises(CloudError):self.perform(id,row,action)
  Cloud.containers[row['name']]['count']=1
  with self.assertRaises(CloudError):self.perform(id,row,'DELETE')
  Cloud.containers[row['name']]['count']=0;self.perform(id,row,'DELETE');self.assertEqual(self.row(id,'container')['presence'],0)
 def test_permission_error_is_unknown_not_absent_and_stale_identity_blocks(self):
  id=self.prepare();Cloud.fail_storage=True
  with self.assertRaises(CloudError):self.control.sync(id)
  self.assertEqual(self.row(id,'container')['presence'],-1);self.assertEqual(self.row(id,'container')['state'],'CHECK_FAILED')
  row=self.row(id,'server');row['remote_id']='different'
  with self.assertRaises(CloudError):self.perform(id,row,'STOP')
 def test_bulk_route_all_selection_validated_and_delete_reauth(self):
  id=self.prepare();a=self.row(id,'server');b=self.row(id,'database');data={'kind':'STOP','ack':'on','selected':['managed:'+a['id'],'managed:'+b['id']],'_return':'/#resources/NHN'}
  r=self.post('/operations/resources',data);self.assertEqual(r.status_code,303);self.assertEqual(r.headers['location'],'/#resources/NHN')
  self.assertTrue(self.app.state.worker.run_one());self.assertEqual(self.db.one("SELECT status FROM jobs WHERE kind='RESOURCE_ACTION'")['status'],'SUCCEEDED')
  self.assertEqual(self.row(id,'database')['state'],'SHUTDOWN')
  data.update(kind='DELETE',password='wrong',delete_confirm='삭제');self.assertEqual(self.post('/operations/resources',data).status_code,403)
  self.db.execute("UPDATE users SET role='OPERATOR'");data['password']='A-long-test-password!';self.assertEqual(self.post('/operations/resources',data).status_code,403)
 def test_metrics_and_error_return_to_previous_view_without_open_redirect(self):
  id=self.prepare();resource=self.db.one('SELECT id FROM resources');path='/resources/'+resource['id']+'/metrics'
  with patch('cloudops.providers.adapter',return_value=Mock(metrics=lambda remote:{'cpu':None,'memory':None,'disk':None})):
   r=self.post(path,{'_return':'/#resources/NHN'});self.assertIn('href="/#resources/NHN"',r.text)
  r=self.post('/operations/resources',{'_return':'/#resources/NHN'});self.assertEqual(r.status_code,400);self.assertIn('href="/#resources/NHN"',r.text)
  r=self.post('/operations/resources',{'_return':'https://evil.test'});self.assertNotIn('href="https://evil.test"',r.text)
 def test_tracked_network_delete_and_ambiguous_creation_are_separate(self):
  id=self.prepare();base=self.vault.open(self.db.one('SELECT state FROM nhn_batches')['state'],'nhn-state:'+id)
  boot={'students':{'s01':{'tenant':base['s01']['plan']['server']['tenant'],'server_id':base['s01']['summary']['server_id'],'summary':base['s01']['summary'],'journal':{'vpc':{'id':'vpc-one'}},'person':{}}}}
  self.db.execute('INSERT INTO nhn_bootstrap(batch_id,config,state,updated) VALUES(?,?,?,?)',(id,'{}',self.vault.seal(boot,'nhn-servers:'+id),time.time()))
  network={'id':'vpc-one','state':'available'};calls=[]
  class Infra:
   def __init__(self,*a):pass
   def close(self):pass
   def net(self,path,method=None):
    if method=='DELETE':calls.append(path);network.clear();return {}
    return {'vpcs':[network] if network else []}
  with patch('cloudops.nhn_servers.Infra',Infra):
   self.control.sync(id);row=self.row(id,'vpc');self.assertEqual(row['actions'],['DELETE']);self.perform(id,row,'DELETE');self.assertEqual(calls,['/vpcs/vpc-one']);self.assertEqual(self.row(id,'vpc')['presence'],0)
  item=base['s02'];item['journal']['database']={'intent':True};self.manager.save_item(id,'s02',item)
  row=self.row(id,'database','s02');self.assertTrue(row['creation_recorded']);self.assertEqual(self.control.lookup(Cloud({},'KR1'),row,base,{}),('CHECK_REQUIRED',-1,{'note':'생성 요청 기록은 있으나 결과 식별자가 없습니다. 중복 생성하지 않습니다.'}))
 def test_viewer_cannot_control_and_no_secrets_in_catalog(self):
  id=self.prepare();page=self.client.get('/').text;self.assertNotIn('SECRET-APPKEY',page);self.assertNotIn('SECRET-UAK',page)
  self.db.execute("UPDATE users SET role='VIEWER'");self.assertEqual(self.post('/operations/refresh',{'connection_id':'ALL'}).status_code,403);self.assertNotIn('id="selected-count"',self.client.get('/').text)


class AdapterDeleteTests(unittest.TestCase):
 def test_delete_maps_to_provider_delete_not_power_stop(self):
  from cloudops.providers import AWS,NHN,NCP
  aws=AWS.__new__(AWS);aws.identity=Mock();ec2=Mock();aws.client=Mock(return_value=ec2);aws.action('i-12345678','delete');ec2.terminate_instances.assert_called_once_with(InstanceIds=['i-12345678']);ec2.stop_instances.assert_not_called()
  nhn=NHN.__new__(NHN);nhn.request=Mock();remote='12345678-1234-1234-1234-123456789abc';nhn.action(remote,'delete');nhn.request.assert_called_once_with('/servers/'+remote,method='DELETE')
  ncp=NCP.__new__(NCP);ncp.request=Mock();ncp.action('12345','delete');ncp.request.assert_called_once_with('terminateServerInstances',{'serverInstanceNoList.1':'12345'})

if __name__=='__main__':unittest.main()

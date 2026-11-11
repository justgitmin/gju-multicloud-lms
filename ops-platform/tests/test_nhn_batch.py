import base64,json,secrets,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from fastapi.testclient import TestClient
from cloudops.app import create_app,COOKIE
from cloudops.security import password_hash,digest
from cloudops.nhn_batch import Batch,API,CloudError,choose_server

class FakeAPI:
 containers={};objects={};calls=[];fail_create=False
 def __init__(self,secret,region):self.secret=secret;self.region=region
 def close(self):pass
 def projects(self,org):return [{'projectId':f'project{n:02}','projectName':f'TBIT_Edu01_Pro{n:02}','orgId':org,'projectStatusCode':'STABLE'} for n in range(1,3)]
 def products(self):return {'instance':'compute','objectstorage':'storage','rdsformysql':'rds'}
 def product(self,pid,product):return {'productId':product,'projectId':pid,'appKey':'SECRET-APPKEY','externalId':'tenant-'+pid+'000000000000000','productStatusCode':'STABLE','statusCode':'STABLE'}
 def container(self,product,name,method='HEAD',marker=None):
  type(self).calls.append((method,name))
  if method=='HEAD':return type(self).containers.get(name)
  if method=='DELETE':type(self).containers.pop(name,None);return {}
  type(self).containers[name]={'marker':marker,'public':False,'count':0}
  if type(self).fail_create:raise TimeoutError('sensitive remote error')
  return {}
 def rds(self,product,path,body=None,method=None):
  type(self).calls.append((method or ('POST' if body else 'GET'),path,body))
  if method=='DELETE':
   root,rid=path.rsplit('/',1);type(self).objects[root]=[x for x in type(self).objects.get(root,[]) if x.get('id')!=rid];return {}
  keys={'/db-instances':('dbInstances','dbInstanceName','dbInstanceId'),'/parameter-groups':('parameterGroups','parameterGroupName','parameterGroupId'),'/db-security-groups':('dbSecurityGroups','dbSecurityGroupName','dbSecurityGroupId')}
  if path in keys:
   key,nk,ik=keys[path]
   if body:
    rid='generated'+str(len(type(self).calls));x={**body,ik:rid,'id':rid};type(self).objects.setdefault(path,[]).append(x)
    return {ik:rid} if ik!='dbInstanceId' else {'jobId':'job123'}
   return {key:type(self).objects.get(path,[])}
  if path=='/storage-types':return {'storageTypes':['General SSD']}
  if path=='/db-flavors':return {'dbFlavors':[{'dbFlavorId':'flavor1','dbFlavorName':'db.m2.c1m2','vcpus':1,'ram':2048}]}
  if path=='/db-versions':return {'dbVersions':[{'dbVersion':'MYSQL_V8045','dbVersionName':'MySQL 8.0.45'}]}
  if path=='/network/subnets':return {'subnets':[{'subnetId':'subnet1','availableIpCount':5}]}
  if path.endswith('/db-schemas'):
   if body:type(self).objects[path]=[{'dbSchemaName':'labdb','dbSchemaStatus':'STABLE'}];return {'jobId':'schemajob'}
   return {'dbSchemas':type(self).objects.get(path,[])}
  if path.endswith('/network-info'):return {'endPoints':[{'ipAddress':'10.30.1.50'}]}
  if path.startswith('/db-instances/'):return {'dbInstanceStatus':'AVAILABLE','progressStatus':'NONE'}
  raise AssertionError(path)
 def wait(self,*a):pass
 def core(self,*a,**kw):return {}

def server(api,product,name):return {'server_id':'server-'+name,'server_name':name,'ip':'1.2.3.4','private_ip':'10.30.1.32','subnet_id':'subnet1','az':'kr-pub-a','tenant':product['externalId']}

class BatchTests(unittest.TestCase):
 def setUp(self):
  FakeAPI.containers={};FakeAPI.objects={};FakeAPI.calls=[];FakeAPI.fail_create=False
  self.tmp=tempfile.TemporaryDirectory();self.app=create_app({'OPS_ORIGIN':'https://ops.test','OPS_MASTER_KEY':base64.b64encode(secrets.token_bytes(32)).decode(),'OPS_DATA_DIR':self.tmp.name},False);self.db=self.app.state.store;self.vault=self.app.state.vault;self.client=TestClient(self.app,base_url='https://ops.test')
  self.db.execute('INSERT INTO users(email,name,password,role) VALUES(?,?,?,?)',('admin@test.example','admin',password_hash('A-long-test-password!'),'ADMIN'))
  self.client.get('/login');r=self.client.post('/login',data={'email':'admin@test.example','password':'A-long-test-password!','csrf':self.client.cookies['cloudops_login_csrf']},headers={'Origin':'https://ops.test'},follow_redirects=False);self.assertEqual(r.status_code,303)
  self.csrf=self.db.one('SELECT csrf FROM sessions WHERE token=?',(digest(self.client.cookies[COOKIE]),))['csrf']
  self.post('/connections',{'name':'pilot','provider':'NHN','region':'KR1','account':'a'*32,'username':'operator@example.com','api_password':'SECRET-API','writable':'on'});self.c=self.db.one('SELECT * FROM connections');self.post('/events',{'name':'class','ends':'2026-11-20'});self.event=self.db.one('SELECT * FROM events')
  self.manager=Batch(self.db,self.vault,threading.Event());self.patch=patch('cloudops.nhn_batch.API',FakeAPI);self.patch.start();self.serverpatch=patch('cloudops.nhn_batch.choose_server',side_effect=server);self.servermock=self.serverpatch.start()
 def tearDown(self):self.serverpatch.stop();self.patch.stop();self.client.close();self.tmp.cleanup()
 def post(self,path,data=None):return self.client.post(path,data={'csrf':self.csrf,**(data or {})},headers={'Origin':'https://ops.test'},follow_redirects=False)
 def create(self,db=False):
  data={'connection_id':self.c['id'],'event_id':self.event['id'],'name':'class-batch','org':'org123456789','project_prefix':'TBIT_Edu01_Pro','server_prefix':'gju-nhn-s','lab_prefix':'gju-nhn','first':'1','last':'2','access_key':'SECRET-UAK','secret_key':'SECRET-KEY','db_flavor':'','db_version':''}
  if db:data['db']='on'
  r=self.post('/nhn/batches',data);self.assertEqual(r.status_code,303);self.b=self.db.one('SELECT * FROM nhn_batches');self.assertTrue(self.app.state.worker.run_one());return self.b['id']
 def action(self,kind):return self.post('/nhn/batches/'+self.b['id']+'/action',{'kind':kind,'confirm':'class-batch','password':'A-long-test-password!'})
 def test_plan_is_read_only_and_encrypted(self):
  id=self.create();self.assertTrue(all(x[0]=='HEAD' for x in FakeAPI.calls));self.assertEqual(self.db.one('SELECT COUNT(*) n FROM nhn_items')[ 'n'],2)
  page=self.client.get('/').text;self.assertIn('PLANNED',page)
  for secret in ['SECRET-UAK','SECRET-KEY','SECRET-APPKEY','SECRET-API']:self.assertNotIn(secret,page);self.assertNotIn(secret,Path(self.tmp.name,'ops.sqlite3').read_bytes().decode(errors='ignore'))
 def test_apply_twice_creates_once_and_registers_inventory(self):
  self.create();self.assertEqual(self.action('NHN_APPLY').status_code,303);self.app.state.worker.run_one();self.assertEqual(self.db.one('SELECT status FROM jobs ORDER BY created DESC')['status'],'SUCCEEDED')
  self.assertEqual(len([x for x in FakeAPI.calls if x[0]=='PUT']),2);self.assertEqual(self.db.one('SELECT COUNT(*) n FROM resources')['n'],2)
  self.action('NHN_APPLY');self.app.state.worker.run_one();self.assertEqual(len([x for x in FakeAPI.calls if x[0]=='PUT']),2)
 def test_lost_container_response_reconciles_without_duplicate(self):
  self.create();FakeAPI.fail_create=True;self.action('NHN_APPLY');self.app.state.worker.run_one();self.assertEqual(self.db.one('SELECT status FROM jobs ORDER BY created DESC')['status'],'FAILED');FakeAPI.fail_create=False
  self.action('NHN_APPLY');self.app.state.worker.run_one();self.assertEqual(self.db.one('SELECT status FROM jobs ORDER BY created DESC')['status'],'SUCCEEDED');self.assertEqual(len([x for x in FakeAPI.calls if x[0]=='PUT']),2)
 def test_ambiguous_absent_result_is_not_recreated(self):
  self.create();FakeAPI.fail_create=True;self.action('NHN_APPLY');self.app.state.worker.run_one();FakeAPI.containers={};FakeAPI.fail_create=False;self.action('NHN_APPLY');self.app.state.worker.run_one();self.assertEqual(len([x for x in FakeAPI.calls if x[0]=='PUT']),2);self.assertEqual(self.db.one('SELECT status FROM jobs ORDER BY created DESC')['status'],'FAILED')
 def test_drift_blocks_all_writes(self):
  self.create();self.servermock.side_effect=lambda a,p,n:{**server(a,p,n),'subnet_id':'different'};self.action('NHN_APPLY');self.app.state.worker.run_one();self.assertFalse(any(x[0]=='PUT' for x in FakeAPI.calls))
 def test_nonempty_or_foreign_container_preserved(self):
  self.create();self.action('NHN_APPLY');self.app.state.worker.run_one();FakeAPI.containers['gju-nhn-s01-files']['count']=1;self.action('NHN_CLEANUP');self.app.state.worker.run_one();self.assertIn('gju-nhn-s01-files',FakeAPI.containers);self.assertNotIn('gju-nhn-s02-files',FakeAPI.containers)
 def test_existing_private_container_reused_and_not_deleted(self):
  FakeAPI.containers['gju-nhn-s01-files']={'marker':'existing-owner','public':False,'count':2};self.create();self.action('NHN_APPLY');self.app.state.worker.run_one();self.assertEqual(len([x for x in FakeAPI.calls if x[0]=='PUT']),1)
  self.action('NHN_CLEANUP');self.app.state.worker.run_one();self.assertIn('gju-nhn-s01-files',FakeAPI.containers);self.assertEqual(FakeAPI.containers['gju-nhn-s01-files']['count'],2)
 def test_foreign_name_collision_blocks_plan(self):
  FakeAPI.containers['gju-nhn-s01-files']={'marker':'other','public':True,'count':0};self.create();self.assertEqual(self.action('NHN_APPLY').status_code,409);self.assertEqual(FakeAPI.containers['gju-nhn-s01-files']['marker'],'other')
 def test_reauth_readonly_and_queued_revocation(self):
  self.create();self.assertEqual(self.post('/nhn/batches/'+self.b['id']+'/action',{'kind':'NHN_APPLY','confirm':'class-batch','password':'wrong'}).status_code,403)
  self.action('NHN_APPLY');self.db.execute('UPDATE connections SET writable=0');self.app.state.worker.run_one();self.assertFalse(any(x[0]=='PUT' for x in FakeAPI.calls))
 def test_download_is_one_student_without_operator_keys(self):
  self.create(True);self.action('NHN_APPLY');self.app.state.worker.run_one();self.assertEqual(self.db.one('SELECT status FROM jobs ORDER BY created DESC')['status'],'SUCCEEDED')
  r=self.post('/nhn/batches/'+self.b['id']+'/student',{'student':'s01','password':'A-long-test-password!'});self.assertEqual(r.status_code,200);d=r.json();self.assertEqual(d['db_host'],'10.30.1.50');self.assertTrue(d['db_password']);self.assertNotIn('s02',r.text);self.assertNotIn('SECRET-',r.text)
  self.assertNotIn(d['db_password'],self.client.get('/').text);self.assertNotIn(d['db_password'],Path(self.tmp.name,'ops.sqlite3').read_bytes().decode(errors='ignore'))
 def test_rds_payload_private_and_password_saved_before_create(self):
  self.create(True);self.action('NHN_APPLY');self.app.state.worker.run_one();calls=[x for x in FakeAPI.calls if x[0]=='POST'];db=next(x[2] for x in calls if x[1]=='/db-instances');sg=next(x[2] for x in calls if x[1]=='/db-security-groups')
  self.assertFalse(db['network']['usePublicAccess']);self.assertFalse(db['useHighAvailability']);self.assertEqual(db['storage']['storageSize'],20);self.assertEqual(sg['rules'][0]['cidr'],'10.30.1.32/32')
  state=self.vault.open(self.db.one('SELECT state FROM nhn_batches')['state'],'nhn-state:'+self.b['id']);self.assertEqual(state['s01']['password'],db['dbPassword'])
 def test_plan_cannot_overwrite_created_journal_or_reapply_cleanup(self):
  self.create();self.action('NHN_APPLY');self.app.state.worker.run_one();self.assertEqual(self.action('NHN_PLAN').status_code,409);self.action('NHN_CLEANUP');self.app.state.worker.run_one();self.assertEqual(self.action('NHN_APPLY').status_code,409)
 def test_changed_master_credentials_block_batch(self):
  self.create();self.db.execute('UPDATE connections SET revision=revision+1');self.action('NHN_APPLY');self.app.state.worker.run_one();self.assertFalse(any(x[0]=='PUT' for x in FakeAPI.calls))
 def test_key_refresh_preserves_state_and_is_blocked_during_jobs(self):
  self.create();self.action('NHN_APPLY');self.app.state.worker.run_one();before=self.db.one('SELECT state FROM nhn_batches')['state'];self.db.execute('UPDATE connections SET revision=revision+1')
  r=self.post('/nhn/batches/'+self.b['id']+'/credentials',{'password':'A-long-test-password!','access_key':'NEW-KEY-UAK','secret_key':'NEW-KEY-SECRET'});self.assertEqual(r.status_code,303);b=self.db.one('SELECT * FROM nhn_batches');self.assertEqual(b['state'],before);self.assertEqual(json.loads(b['config'])['connection_revision'],2)
  self.action('NHN_APPLY');self.assertEqual(self.post('/nhn/batches/'+self.b['id']+'/credentials',{'password':'A-long-test-password!'}).status_code,409)
 def test_job_failure_hides_provider_exception(self):
  self.create();FakeAPI.fail_create=True;self.action('NHN_APPLY');self.app.state.worker.run_one();self.assertNotIn('sensitive remote error',self.client.get('/').text)
 def test_plan_expiry_requires_refresh(self):
  self.create();self.db.execute('UPDATE nhn_batches SET planned=?',(time.time()-3601,));self.assertEqual(self.action('NHN_APPLY').status_code,409)
 def test_operator_cannot_execute_or_download(self):
  self.create();self.db.execute("UPDATE users SET role='OPERATOR'");self.assertEqual(self.action('NHN_APPLY').status_code,403);self.assertEqual(self.post('/nhn/batches/'+self.b['id']+'/student',{}).status_code,403);self.assertNotIn('name="access_key"',self.client.get('/').text)

class TransportTests(unittest.TestCase):
 def test_storage_uses_separate_tenant_and_rejects_catalog_host(self):
  with patch('cloudops.nhn_batch.httpx.Client') as client:
   api=API({'username':'operator','api_password':'secret'},'KR1');response=Mock(is_success=True);response.json.return_value={'access':{'token':{'tenant':{'id':'b'*32},'id':'token'},'serviceCatalog':[{'type':'object-store','endpoints':[{'region':'KR1','publicURL':'https://attacker.example/v1/AUTH_'+'b'*32}]}]}};client.return_value.post.return_value=response
   with self.assertRaises(CloudError):api.storage_auth({'externalId':'b'*32})
   self.assertEqual(client.return_value.post.call_args.kwargs['json']['auth']['tenantId'],'b'*32)
 def test_rds_checks_business_status_without_logging_response(self):
  with patch('cloudops.nhn_batch.httpx.Client') as client:
   api=API({'access_key':'key','secret_key':'secret'},'KR1');r=Mock(is_success=True,content=b'x');r.json.return_value={'header':{'isSuccessful':False,'resultMessage':'sensitive-response'}};client.return_value.request.return_value=r
   with self.assertRaises(CloudError) as e:api.rds({'appKey':'app'},'/db-instances')
   self.assertNotIn('sensitive-response',str(e.exception));self.assertEqual(client.return_value.request.call_args.kwargs['headers']['X-TC-APP-KEY'],'app')
if __name__=='__main__':unittest.main()

import json,threading,time,unittest
from unittest.mock import Mock,patch
from botocore.exceptions import ClientError
from cloudops.aws_resources import AWSResources
from cloudops.providers import CloudError
import test_nhn_batch as fixture

class FakeAWS:
 state='available';count=0;tags=True;denied=False;deleted=False;calls=[]
 def __init__(self,c,secret):self.c=c
 def identity(self):pass
 def client(self,service):
  result=Mock()
  if service=='cloudformation':
   def paginator(name):
    pages=Mock()
    if name=='describe_stacks':pages.paginate.return_value=[{'Stacks':[{'StackName':'test-lab-s01','StackId':'stack-id','StackStatus':'CREATE_COMPLETE','Tags':[{'Key':'LabId','Value':'test-lab'},{'Key':'StudentId','Value':'s01'},{'Key':'ManagedBy','Value':'gju-lab-tool' if self.tags else 'OTHER'}]}]}]
    else:pages.paginate.return_value=[{'StackResourceSummaries':[{'LogicalResourceId':logical,'ResourceType':kind,'ResourceStatus':'CREATE_COMPLETE','PhysicalResourceId':remote} for logical,kind,remote in [('Web','AWS::EC2::Instance','i-12345678'),('Database','AWS::RDS::DBInstance','db-one'),('Bucket','AWS::S3::Bucket','bucket-one')]]}]
    return pages
   result.get_paginator=paginator
  elif service=='ec2':result.describe_instances.return_value={'Reservations':[{'Instances':[{'InstanceId':'i-12345678','State':{'Name':'running'},'PrivateIpAddress':'10.0.0.1'}]}]}
  elif service=='rds':
   def describe(**kw):
    if self.deleted:raise ClientError({'Error':{'Code':'DBInstanceNotFound'}},'DescribeDBInstances')
    if self.denied:raise ClientError({'Error':{'Code':'AccessDenied'}},'DescribeDBInstances')
    return {'DBInstances':[{'DBInstanceIdentifier':'db-one','DBInstanceStatus':self.state}]}
   def action(name,**kw):
    self.calls.append((name,kw))
    if name=='delete':type(self).deleted=True
    else:type(self).state='stopped' if name=='stop' else 'available'
   result.describe_db_instances=describe
   result.stop_db_instance=lambda **kw:action('stop',**kw);result.start_db_instance=lambda **kw:action('start',**kw);result.delete_db_instance=lambda **kw:action('delete',**kw)
  elif service=='s3':
   result.list_objects_v2.return_value={'Contents':[{'Key':'not-exported'}]} if self.count else {}
   result.list_object_versions.return_value={};result.delete_bucket=lambda **kw:self.calls.append(('delete-bucket',kw))
  return result

class AWSTests(unittest.TestCase):
 setUp=fixture.BatchTests.setUp
 tearDown=fixture.BatchTests.tearDown
 post=fixture.BatchTests.post
 def prepare(self):
  self.post('/connections',{'name':'AWS lab','provider':'AWS','region':'ap-northeast-2','account':'123456789012','writable':'on'});c=self.db.one("SELECT * FROM connections WHERE provider='AWS'")
  cfg={'lab_id':'test-lab','students':['s01'],'s3':True,'rds':True,'region':'ap-northeast-2'};id='aws-env'
  self.db.execute('INSERT INTO environments(id,connection_id,event_id,lab_id,config,created) VALUES(?,?,?,?,?,?)',(id,c['id'],self.event['id'],'test-lab',json.dumps(cfg),time.time()))
  FakeAWS.state='available';FakeAWS.count=0;FakeAWS.tags=True;FakeAWS.denied=False;FakeAWS.deleted=False;FakeAWS.calls=[]
  patcher=patch('cloudops.aws_resources.AWS',FakeAWS);patcher.start();self.addCleanup(patcher.stop)
  self.manager=AWSResources(self.db,self.vault,threading.Event());self.manager.sync(id);return id
 def test_aws_db_start_stop_delete_and_s3_no_power_controls(self):
  id=self.prepare();rows=self.manager.catalog(id);db=next(r for r in rows if r['kind']=='database');storage=next(r for r in rows if r['kind']=='container')
  selected=[{'id':db['id'],'remote_id':db['remote_id']}]
  self.manager.apply(id,selected,'STOP','job');self.assertEqual(next(r for r in self.manager.catalog(id) if r['kind']=='database')['state'],'SHUTDOWN')
  self.manager.apply(id,selected,'START','job');self.manager.apply(id,selected,'DELETE','job')
  self.assertEqual(next(r for r in self.manager.catalog(id) if r['kind']=='database')['presence'],0)
  self.assertEqual(FakeAWS.calls[-1],('delete',{'DBInstanceIdentifier':'db-one','SkipFinalSnapshot':True,'DeleteAutomatedBackups':True}))
  with self.assertRaises(CloudError):self.manager.apply(id,[{'id':storage['id'],'remote_id':storage['remote_id']}],'STOP','job')
  FakeAWS.count=1
  with self.assertRaises(CloudError):self.manager.apply(id,[{'id':storage['id'],'remote_id':storage['remote_id']}],'DELETE','job')
 def test_aws_wrong_stack_owner_and_permission_errors_are_not_missing(self):
  id=self.prepare();FakeAWS.denied=True
  with self.assertRaises(CloudError):self.manager.sync(id)
  self.assertEqual(next(r for r in self.manager.catalog(id) if r['kind']=='database')['presence'],-1)
  FakeAWS.tags=False
  with self.assertRaises(CloudError):self.manager.sync(id)
  self.assertTrue(all(r['presence']==-1 for r in self.manager.catalog(id)))
 def test_aws_rows_and_selection_route(self):
  id=self.prepare();self.assertIn('bucket-one',self.client.get('/').text);db=next(r for r in self.manager.catalog(id) if r['kind']=='database')
  r=self.post('/operations/resources',{'kind':'STOP','selected':'aws:'+db['id'],'ack':'on','_return':'/#resources/AWS'});self.assertEqual(r.status_code,303);self.assertTrue(self.app.state.worker.run_one())
  self.assertEqual(self.db.one("SELECT status FROM jobs WHERE kind='RESOURCE_ACTION'")['status'],'SUCCEEDED')

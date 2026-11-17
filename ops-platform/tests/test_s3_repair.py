import importlib.util
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import test_nhn_batch as fixture
from cloudops.providers import CloudError

class S3RepairIntegrationTests(unittest.TestCase):
 setUp=fixture.BatchTests.setUp
 tearDown=fixture.BatchTests.tearDown
 post=fixture.BatchTests.post
 def prepare_aws(self):
  self.post('/connections', {'name':'lab','provider':'AWS','region':'ap-northeast-2',
      'account':'498307943987','access_key':'LAB-ACCESS','secret_key':'LAB-SECRET','writable':'on'})
  c=self.db.one("SELECT * FROM connections WHERE provider='AWS'")
  root=Path(__file__).resolve().parents[2]/'infra/aws-lab'
  spec=importlib.util.spec_from_file_location('fixture_lab',root/'lab.py')
  lab=importlib.util.module_from_spec(spec);spec.loader.exec_module(lab)
  cfg=lab.load_config(root/'config.example.json');cfg.update(lab_id='test-lab',students=['s01'],access_mode='ssm')
  self.db.execute('INSERT INTO environments(id,connection_id,event_id,lab_id,config,created) VALUES(?,?,?,?,?,?)',
      ('aws-repair',c['id'],self.event['id'],'test-lab',json.dumps(cfg),1))
  return c,cfg,lab
 def test_route_requires_ack_password_and_exact_account(self):
  c,cfg,lab=self.prepare_aws()
  data={'kind':'AWS_S3_REPAIR','confirm':'test-lab','account':'498307943987','password':'A-long-test-password!'}
  self.assertEqual(self.post('/environments/aws-repair/action',data).status_code,400)
  data['ack']='on';data['account']='290780119395'
  self.assertEqual(self.post('/environments/aws-repair/action',data).status_code,400)
  data['account']='498307943987'
  self.assertEqual(self.post('/environments/aws-repair/action',data).status_code,303)
  self.assertEqual(self.db.one("SELECT kind FROM jobs")['kind'],'AWS_S3_REPAIR')
 def test_worker_uses_stored_connection_not_host_role(self):
  c,cfg,lab=self.prepare_aws();worker=self.app.state.worker
  calls=[]
  def command(args,**kw):
   calls.append((args,kw))
   if 'get-caller-identity' in args:
    result={'Account':'498307943987'}
   elif 'describe-stacks' in args:
    result={'Stacks':[{'StackName':'test-lab-s01','StackStatus':'CREATE_COMPLETE','Tags':[
        {'Key':'LabId','Value':'test-lab'},{'Key':'StudentId','Value':'s01'},{'Key':'ManagedBy','Value':'gju-lab-tool'}]}]}
   elif 'get-template' in args:
    result={'TemplateBody':lab.template(cfg,'s01')}
   else:raise AssertionError(args)
   return SimpleNamespace(returncode=0,stdout=json.dumps(result))
  secret={'access_key':'LAB-ACCESS','secret_key':'LAB-SECRET'}
  job={'id':'test-job','target':'aws-repair','kind':'AWS_S3_REPAIR','payload':'{}'}
  with patch('cloudops.jobs.providers.AWS') as adapter,patch('cloudops.jobs.subprocess.run',side_effect=command),patch.dict('os.environ',{'AWS_PROFILE':'wrong','AWS_ACCESS_KEY_ID':'HOST-KEY'}):
   worker.aws_lab(c,secret,job)
  self.assertTrue(calls)
  for args,kw in calls:
   self.assertEqual(kw['env']['AWS_ACCESS_KEY_ID'],'LAB-ACCESS')
   self.assertEqual(kw['env']['AWS_SECRET_ACCESS_KEY'],'LAB-SECRET')
   self.assertNotIn('AWS_PROFILE',kw['env'])
   self.assertNotIn('OPS_MASTER_KEY',kw['env'])
  with self.assertRaises(CloudError):
   worker.aws_lab(c,{},job)

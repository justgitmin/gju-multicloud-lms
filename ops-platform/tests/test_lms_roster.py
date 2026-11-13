import copy,json,time,unittest
from unittest.mock import patch
from cloudops.lms_roster import snapshot,proposals,approve,approved_people,require_generation,plan
from cloudops.providers import CloudError
from roster_fixture import snapshot_for,approved_config
import test_ops as fixture
CFG={'lab_id':'test-lab','students':['s01','s02','s03']}
class RosterTests(unittest.TestCase):
 def test_identity_preserves_codes_email_changes_and_excludes_removed_students(self):
  config=approved_config(CFG);data=snapshot_for(CFG);data['students']=data['students'][:2];data['students'][0]['email']='changed@example.com'
  config=approve(config,data,{'user-s01':'s01','user-s02':'s02'},{},{'test-lab-s03/outputs.json':'opaque'})
  self.assertEqual(approved_people(config)['s01']['email'],'changed@example.com');self.assertFalse(config['lms_bindings']['s03']['active'])
  self.assertIn('승인 명단에 없음',plan(config,{'test-lab-s03/outputs.json':'opaque'})[2]['status'])
  with self.assertRaises(CloudError):require_generation(config,['s03'])
  with self.assertRaises(CloudError):approve(config,data,{'user-s01':'s02'},{},{})
 def test_empty_approval_snapshot_disables_generation_without_deleting_resources(self):
  config=approved_config(CFG);data=snapshot_for(CFG);data['students']=[]
  result=approve(config,data,{},{},{'test-lab-s01/outputs.json':'opaque'})
  self.assertEqual(approved_people(result),{});self.assertEqual(result['students'],CFG['students'])
  self.assertTrue(plan(result,{'test-lab-s01/outputs.json':'opaque'})[0]['started'])
  with self.assertRaises(CloudError):require_generation(result,['s01'])
 def test_proposals_require_review_and_new_codes_do_not_reuse_legacy_slots(self):
  data=snapshot_for({'students':['s01','s02']});data['students'][0].update(email='new@example.com',name='Same Name')
  rows=proposals(CFG,data,{'s01':{'name':'Same Name','email':'old@example.com'}})
  self.assertEqual(rows[0]['code'],'s01');self.assertIn('이름만',rows[0]['reason']);self.assertFalse(rows[1]['include']);self.assertEqual(rows[1]['code'],'s02')
  with self.assertRaises(CloudError):require_generation(CFG,['s01'])
 def test_new_environment_uses_unused_plan_slots_and_reserves_existing_resources(self):
  data=snapshot_for(CFG);rows=proposals(CFG,data,{})
  self.assertEqual([r['code'] for r in rows],['s01','s02','s03'])
  self.assertTrue(all(not r['include'] for r in rows))
  rows=proposals(CFG,data,{}, {'test-lab-s02/credentials.json':'opaque'})
  self.assertNotIn('s02',[r['code'] for r in rows])
 def test_invalid_stale_duplicate_and_revision_mismatch_fail_closed(self):
  data=snapshot_for(CFG)
  for mutate in [lambda d:d.update(exportedAt='2000-01-01T00:00:00Z'),lambda d:d['students'].append(d['students'][0]),lambda d:d['students'][0].update(email='not-an-email')]:
   bad=copy.deepcopy(data);mutate(bad)
   with self.assertRaises(CloudError):snapshot(bad)
  config=approved_config(CFG)
  with self.assertRaises(CloudError):require_generation(config,['s01'],'old-revision')
  self.assertTrue(require_generation(config,['s01'],config['lms_roster']['revision']))
  bad=copy.deepcopy(config);bad['lms_roster']['exportedAt']='2000-01-01T00:00:00Z'
  with self.assertRaises(CloudError):approved_people(bad)
 def test_legacy_resources_cannot_be_given_to_unrelated_new_student(self):
  data=snapshot_for(CFG)
  with self.assertRaises(CloudError):approve(CFG,data,{'user-s01':'s01'},{'s01':{'name':'Another Student','email':'another@example.com'}},{'test-lab-s01/credentials.json':'opaque'})

class RouteTests(unittest.TestCase):
 setUp=fixture.PlatformTests.setUp
 tearDown=fixture.PlatformTests.tearDown
 post=fixture.PlatformTests.post
 connection=fixture.PlatformTests.connection
 assigned=fixture.PlatformTests.assigned
 login=fixture.PlatformTests.login
 def test_review_gates_generation_and_no_cloud_job_is_created_by_roster_review(self):
  c=self.connection();event=self.assigned(c);self.post('/environments',{'connection_id':c['id'],'event_id':event['id'],'lab_id':'test-lab','count':'3','volume':'20','instance':'t3.micro'})
  env=self.db.one('SELECT * FROM environments');cfg=json.loads(env['config']);path='/environments/'+env['id'];action={'kind':'PROVISION','confirm':'test-lab','account':c['account'],'students':['s01']}
  self.assertEqual(self.post(path+'/action',action).status_code,409)
  data=snapshot_for(cfg)
  self.assertEqual(self.post(path+'/approved-roster',{'password':'wrong','roster_json':json.dumps(data)}).status_code,403)
  self.assertEqual(self.post(path+'/approved-roster',{'password':'A-long-test-password!','roster_json':json.dumps(data)}).status_code,303)
  self.assertEqual(self.post(path+'/action',action).status_code,409)
  self.assertIn('대조 결과 · 아직 확정 전',self.client.get('/').text)
  self.assertEqual(self.post(path+'/approved-roster',{'password':'A-long-test-password!','action':'approve','ack':'on','include':['user-s01'],'code_user-s01':'s01'}).status_code,303)
  self.assertFalse(self.db.one('SELECT id FROM jobs'))
  self.assertIn('신규 생성 1명',self.client.get('/').text)
  self.assertEqual(self.post(path+'/action',{**action,'students':['s02']}).status_code,409)
  self.assertEqual(self.post(path+'/action',action).status_code,303)
  self.assertIn('roster_revision',json.loads(self.db.one('SELECT payload FROM jobs')['payload']))
  self.assertEqual(self.post(path+'/approved-roster',{'password':'A-long-test-password!','roster_json':json.dumps(data)}).status_code,409)
  changed=json.loads(self.db.one('SELECT config FROM environments')['config']);changed['lms_roster']['revision']='changed-after-queue';self.db.execute('UPDATE environments SET config=?',(json.dumps(changed),))
  with patch('cloudops.jobs.providers.AWS') as aws:
   self.app.state.worker.run_one();aws.assert_not_called()
  self.assertEqual(self.db.one('SELECT status FROM jobs')['status'],'FAILED')
  self.login('operator@test.example');self.assertEqual(self.post(path+'/approved-roster',{}).status_code,403)

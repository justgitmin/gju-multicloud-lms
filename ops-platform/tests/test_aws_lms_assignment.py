import base64,json,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
from cloudops.aws_student_bundles import lms_batch
from cloudops.providers import CloudError
from test_aws_student_bundles import CFG,files,RouteTests

class BatchTests(unittest.TestCase):
 def test_export_roundtrips_through_real_lms_validator_without_operator_keys(self):
  roster={'s01':{'email':'ONE@example.com'},'s02':{'email':'two@example.com'}}
  batch=lms_batch(CFG,'123456789012',{**files('s01'),**files('s02')},roster,'gju-multicloud-2026')
  self.assertEqual(batch['entries'][0]['email'],'one@example.com')
  self.assertNotIn('NEVER-EXPORT-OPERATOR',json.dumps(batch));self.assertNotIn('evil.invalid',json.dumps(batch))
  source="import {validateLabBatch} from './lib/lab-secrets.mjs';let text='';for await(const chunk of process.stdin)text+=chunk;const batch=validateLabBatch(JSON.parse(text));if(batch.entries.length!==2||batch.entries[0].studentCode!=='s01')process.exit(1);"
  result=subprocess.run(['node','--input-type=module','-e',source],input=json.dumps(batch),text=True,capture_output=True,cwd=Path(__file__).resolve().parents[2])
  self.assertEqual(result.returncode,0,result.stderr)
 def test_missing_duplicate_and_incomplete_are_blocked(self):
  good={'s01':{'email':'one@example.com'},'s02':{'email':'two@example.com'}}
  for roster,records,course in [({},files('s01'),'course'),({'s01':{'email':'one@example.com'},'s02':{'email':'ONE@example.com'}},{**files('s01'),**files('s02')},'course'),(good,files('s01'),'course'),(good,{**files('s01'),**files('s02')},'')]:
   with self.assertRaises(CloudError):lms_batch(CFG,'123456789012',records,roster,course)

class ExportRouteTests(unittest.TestCase):
 setUp=RouteTests.setUp
 tearDown=RouteTests.tearDown
 post=RouteTests.post
 connection=RouteTests.connection
 assigned=RouteTests.assigned
 login=RouteTests.login
 prepare=RouteTests.prepare
 def test_export_requires_admin_reauthentication_and_is_audited_no_cache(self):
  env,c=self.prepare();from roster_fixture import approved_config;config=approved_config(dict(CFG,students=['s01']));self.db.execute('UPDATE environments SET config=? WHERE id=?',(json.dumps(config),env['id']))
  path='/environments/'+env['id']+'/lms-assignment';data={'password':'A-long-test-password!','course_id':'gju-multicloud-2026'}
  self.assertEqual(self.post(path,{**data,'password':'wrong'}).status_code,403)
  with patch('cloudops.aws_student_bundles.people',return_value={'s01':{'email':'one@example.com'}}):
   response=self.post(path,data)
  self.assertEqual(response.status_code,200);self.assertEqual(response.json()['entries'][0]['studentCode'],'s01');self.assertEqual(response.headers['cache-control'],'no-store');self.assertIn('attachment;',response.headers['content-disposition'])
  self.assertEqual(self.db.one("SELECT COUNT(*) n FROM audits WHERE event='AWS_LMS_ASSIGNMENT_EXPORT'")['n'],1)
  actor=self.db.one("SELECT id FROM users WHERE role='ADMIN'")['id'];self.app.state.worker.enqueue(actor,c,'PROVISION',env['id'])
  self.assertEqual(self.post(path,data).status_code,409)
  self.login('operator@test.example');self.assertEqual(self.post(path,data).status_code,403)

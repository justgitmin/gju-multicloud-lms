import base64,io,json,time,unittest,zipfile
from pathlib import Path
from unittest.mock import Mock,patch
from cloudops.aws_student_bundles import kit,archive
from cloudops.providers import CloudError
import test_ops as fixture

CFG={'lab_id':'gju-mc-2026-aws','students':['s01','s02'],'region':'ap-northeast-2','access_mode':'ssm','s3':True,'rds':True}
def files(code):
 stem=CFG['lab_id']+'-'+code
 credentials={'account_id':'123456789012','username':stem,'initial_password':'INITIAL-PASSWORD-'+code,'db_password':'DATABASE-PASSWORD-'+code,'operator_key':'NEVER-EXPORT-OPERATOR'}
 outputs={'Username':stem,'InstanceId':'i-12345678','SessionDocument':CFG['lab_id']+'-shell','LoginUrl':'https://evil.invalid','SessionConsoleUrl':'https://evil.invalid','BucketName':'gju-test-bucket-'+code,'DbEndpoint':'db-'+code+'.example.ap-northeast-2.rds.amazonaws.com','PublicIp':'1.2.3.4'}
 return {stem+'/'+name:base64.b64encode(json.dumps(value).encode()).decode() for name,value in [('credentials.json',credentials),('outputs.json',outputs)]}

class KitTests(unittest.TestCase):
 def test_personal_zip_has_guide_assets_and_no_other_or_operator_credentials(self):
  content,access=kit(CFG,'123456789012',{**files('s01'),**files('s02')},'s01',{'name':'Student One'});z=zipfile.ZipFile(io.BytesIO(content));text='\n'.join(z.read(n).decode('utf-8-sig') for n in z.namelist())
  self.assertIn('INITIAL-PASSWORD-s01',text);self.assertIn('DATABASE-PASSWORD-s01',text);self.assertNotIn('PASSWORD-s02',text);self.assertNotIn('NEVER-EXPORT-OPERATOR',text);self.assertNotIn('evil.invalid',text)
  self.assertTrue({'demo-app/index.html','demo-app/assets/style.css','demo-app/assets/app.js','접속안내.txt','access.json','웹앱_설치명령.txt'}<=set(z.namelist()));self.assertFalse(any(n.endswith('.pem') for n in z.namelist()))
  self.assertEqual(access['session_document'],CFG['lab_id']+'-shell');self.assertEqual(access['db_user'],'labadmin');self.assertIn('sudo apt-get install -y nginx curl',z.read('웹앱_설치명령.txt').decode('utf-8-sig'))
 def test_archive_excludes_incomplete_students_and_keeps_separate_zips(self):
  content,manifest=archive(CFG,'123456789012',files('s01'),{'s01':{'name':'Student One'},'s02':{'name':'Student Two'}});z=zipfile.ZipFile(io.BytesIO(content));self.assertIn('s01_Student_One.zip',z.namelist());self.assertFalse(manifest[1]['included'])
 def test_wrong_account_student_document_or_unknown_code_blocks(self):
  with self.assertRaises(CloudError):kit(CFG,'999999999999',files('s01'),'s01')
  with self.assertRaises(CloudError):kit(CFG,'123456789012',files('s01'),'s03')
  bad=files('s01');key=CFG['lab_id']+'-s01/outputs.json';data=json.loads(base64.b64decode(bad[key]));data['SessionDocument']='other-shell';bad[key]=base64.b64encode(json.dumps(data).encode()).decode()
  with self.assertRaises(CloudError):kit(CFG,'123456789012',bad,'s01')

class RouteTests(unittest.TestCase):
 setUp=fixture.PlatformTests.setUp
 tearDown=fixture.PlatformTests.tearDown
 post=fixture.PlatformTests.post
 connection=fixture.PlatformTests.connection
 assigned=fixture.PlatformTests.assigned
 login=fixture.PlatformTests.login
 def prepare(self):
  c=self.connection();event=self.assigned(c);self.post('/environments',{'connection_id':c['id'],'event_id':event['id'],'lab_id':CFG['lab_id'],'count':'14','volume':'20','instance':'t3.micro','s3':'on','rds':'on'});env=self.db.one('SELECT * FROM environments');from roster_fixture import approved_config;self.db.execute('UPDATE environments SET config=? WHERE id=?',(json.dumps(approved_config(json.loads(env['config']))),env['id']));env=self.db.one('SELECT * FROM environments');self.db.execute('UPDATE environments SET state=?',(self.vault.seal(files('s01'),'state:'+env['id']),));return env,c
 def test_archive_and_single_require_admin_reauth_and_no_cache(self):
  env,_=self.prepare();path='/environments/'+env['id']+'/students/archive'
  self.assertEqual(self.post(path,{'password':'wrong'}).status_code,403)
  r=self.post(path,{'password':'A-long-test-password!'});self.assertEqual(r.status_code,200);self.assertEqual(r.headers['cache-control'],'no-store');self.assertTrue(zipfile.is_zipfile(io.BytesIO(r.content)))
  r=self.post('/environments/'+env['id']+'/student',{'student':'s01','password':'A-long-test-password!'});self.assertEqual(r.status_code,200);self.assertIn('demo-app/index.html',zipfile.ZipFile(io.BytesIO(r.content)).namelist())
  self.login('operator@test.example');self.assertEqual(self.post(path,{'password':'A-long-test-password!'}).status_code,403)
 def test_new_student_subset_can_follow_pilot_but_existing_credentials_cannot_be_overwritten(self):
  env,c=self.prepare();path='/environments/'+env['id']+'/action';data={'kind':'PROVISION','confirm':env['lab_id'],'account':c['account']}
  self.assertEqual(self.post(path,{**data,'students':'s01'}).status_code,409);self.assertEqual(self.post(path,{**data,'students':'s99'}).status_code,400)
  r=self.post(path,{**data,'students':['s02','s03']});self.assertEqual(r.status_code,303);self.assertEqual(json.loads(self.db.one('SELECT payload FROM jobs')['payload']),{'students':['s02','s03'],'roster_revision':json.loads(env['config'])['lms_roster']['revision']})
 def test_readonly_check_uses_remaining_students_without_writable_or_creation(self):
  env,c=self.prepare();self.db.execute('UPDATE connections SET writable=0')
  r=self.post('/environments/'+env['id']+'/action',{'kind':'AWS_CHECK'});self.assertEqual(r.status_code,303)
  fake=Path(self.tmp.name)/'check_lab.py';fake.write_text("import json\ndef save_private(path,value):raise AssertionError('no secret creation')\ndef load_config(path,deployment=False):return json.loads(path.read_text())\ndef preflight(config):\n assert len(config['students'])==13 and 's01' not in config['students']\n aws(config,'ec2','describe-instance-types')\ndef deploy(*a):raise AssertionError('no creation')\ndef destroy(*a):raise AssertionError('no deletion')\n")
  self.app.state.worker.runner=fake
  with patch('cloudops.jobs.providers.AWS'),patch('cloudops.jobs.subprocess.run',return_value=Mock(returncode=0,stdout='{}')):self.assertTrue(self.app.state.worker.run_one())
  self.assertEqual(self.db.one('SELECT status FROM jobs')['status'],'SUCCEEDED')
 def test_worker_uses_selected_students_and_preserves_pilot_state(self):
  env,c=self.prepare();fake=Path(self.tmp.name)/'selected_lab.py';fake.write_text("import json\ndef save_private(path,value):\n path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))\ndef load_config(path,deployment=False):return json.loads(path.read_text())\ndef deploy(config,state):\n assert config['students']==['s02']\n save_private(state/(config['lab_id']+'-s02')/'credentials.json',{'new':'student-two'})\n aws(config,'cloudformation','create-stack')\ndef destroy(config):pass\n")
  worker=self.app.state.worker;worker.runner=fake
  with patch('cloudops.jobs.providers.AWS'),patch('cloudops.jobs.subprocess.run',return_value=Mock(returncode=0,stdout='{}')):worker.aws_lab(c,{}, {'id':'selected','target':env['id'],'kind':'PROVISION','payload':json.dumps({'students':['s02'],'roster_revision':json.loads(env['config'])['lms_roster']['revision']})})
  saved=self.vault.open(self.db.one('SELECT state FROM environments')['state'],'state:'+env['id']);self.assertEqual(saved[env['lab_id']+'-s01/credentials.json'],files('s01')[env['lab_id']+'-s01/credentials.json']);self.assertIn(env['lab_id']+'-s02/credentials.json',saved)

if __name__=='__main__':unittest.main()

import base64,json,secrets,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from fastapi.testclient import TestClient
from cloudops.app import create_app,COOKIE
from cloudops.security import password_hash,Vault
from cloudops.providers import NCP,CloudError
ORIGIN='https://ops.test'
class PlatformTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.app=create_app({'OPS_ORIGIN':ORIGIN,'OPS_MASTER_KEY':base64.b64encode(secrets.token_bytes(32)).decode(),'OPS_DATA_DIR':self.tmp.name},False);self.db=self.app.state.store;self.vault=self.app.state.vault
  for email,role in [('admin@test.example','ADMIN'),('operator@test.example','OPERATOR'),('viewer@test.example','VIEWER')]:self.db.execute('INSERT INTO users(email,name,password,role) VALUES(?,?,?,?)',(email,role,password_hash('A-long-test-password!'),role))
  self.client=TestClient(self.app,base_url=ORIGIN);self.login()
 def tearDown(self):self.client.close();self.tmp.cleanup()
 def login(self,email='admin@test.example'):
  self.client.get('/login');token=self.client.cookies['cloudops_login_csrf'];r=self.client.post('/login',data={'csrf':token,'email':email,'password':'A-long-test-password!'},headers={'Origin':ORIGIN},follow_redirects=False);self.assertEqual(r.status_code,303)
  self.csrf=self.db.one('SELECT csrf FROM sessions WHERE token=?',(__import__('hashlib').sha256(self.client.cookies[COOKIE].encode()).hexdigest(),))['csrf']
 def post(self,path,data=None):return self.client.post(path,data={'csrf':self.csrf,**(data or {})},headers={'Origin':ORIGIN},follow_redirects=False)
 def connection(self):
  r=self.post('/connections',{'name':'training','provider':'AWS','region':'ap-northeast-2','account':'123456789012','access_key':'test-access','secret_key':'sensitive-example','writable':'on'});self.assertEqual(r.status_code,303);return self.db.one('SELECT * FROM connections')
 def assigned(self,c):
  self.post('/events',{'name':'교육','ends':'2026-11-20'});event=self.db.one('SELECT * FROM events')
  self.db.execute('INSERT INTO resources(id,connection_id,remote_id,name,state,ip,flavor,event_id,seen) VALUES(?,?,?,?,?,?,?,?,?)',('r1',c['id'],'i-1234567890abcdef0','student','running','1.2.3.4','t3.micro',event['id'],time.time()));return event
 def test_connection_save_and_sync_return_to_matching_card(self):
  r=self.post('/connections',{'name':'NHN pilot','provider':'NHN','region':'KR1','account':'a'*32,'username':'operator@example.com','api_password':'test-api-password'})
  self.assertEqual(r.status_code,303);c=self.db.one('SELECT * FROM connections');saved=f'/?saved={c["id"]}#connection-{c["id"]}'
  self.assertEqual(r.headers['location'],saved);self.assertIsNone(self.db.one('SELECT * FROM jobs'))
  page=self.client.get(saved).text;self.assertIn(f'id="connection-{c["id"]}"',page);self.assertIn('연결 설정을 저장했습니다.',page);self.assertIn(f'action="/connections/{c["id"]}/sync"',page)
  self.assertNotIn('연결 설정을 저장했습니다.',self.client.get('/').text)
  r=self.post('/connections/'+c['id']+'/security',{'admin_password':'A-long-test-password!'})
  self.assertEqual(r.headers['location'],saved)
  r=self.post('/connections/'+c['id']+'/sync');self.assertEqual(r.status_code,303);self.assertEqual(r.headers['location'],f'/#connection-{c["id"]}');self.assertEqual(self.db.one('SELECT kind FROM jobs')['kind'],'SYNC')
 def test_encrypted_credentials_and_no_ui_disclosure(self):
  c=self.connection();self.assertNotIn('sensitive-example',Path(self.tmp.name,'ops.sqlite3').read_bytes().decode(errors='ignore'));self.assertEqual(self.vault.open(c['secret'],'connection:'+c['id'])['secret_key'],'sensitive-example');self.assertNotIn('sensitive-example',self.client.get('/').text)
  with self.assertRaises(Exception):self.vault.open(c['secret'],'connection:other')
 def test_csrf_origin_and_body_size(self):
  self.assertEqual(self.client.post('/events',data={'name':'x'},headers={'Origin':ORIGIN}).status_code,403)
  self.assertEqual(self.client.post('/events',data={'csrf':self.csrf},headers={'Origin':'https://evil.example'}).status_code,403)
  self.assertEqual(self.client.post('/events',content=b'x'*100001,headers={'Origin':ORIGIN}).status_code,413)
 def test_roles_server_side(self):
  c=self.connection();self.assigned(c);self.login('viewer@test.example');self.assertEqual(self.post('/connections',{}).status_code,403);self.assertEqual(self.post('/resources/r1/action',{'kind':'STOP','confirm':'i-1234567890abcdef0'}).status_code,403);self.assertEqual(self.client.get('/api/overview').status_code,200)
  self.login('operator@test.example');self.assertEqual(self.post('/users',{}).status_code,403);self.assertEqual(self.post('/environments',{}).status_code,403);self.assertEqual(self.post('/resources/r1/action',{'kind':'STOP','confirm':'i-1234567890abcdef0'}).status_code,303)
 def test_job_uniqueness_and_revoked_actor(self):
  c=self.connection();self.assigned(c);self.login('operator@test.example');self.assertEqual(self.post('/resources/r1/action',{'kind':'STOP','confirm':'i-1234567890abcdef0'}).status_code,303);self.assertEqual(self.post('/connections/'+c['id']+'/sync').status_code,409)
  self.db.execute("UPDATE users SET active=0 WHERE role='OPERATOR'")
  with patch('cloudops.jobs.providers.adapter') as adapter:self.app.state.worker.run_one();adapter.assert_not_called()
  self.assertEqual(self.db.one('SELECT status FROM jobs')['status'],'FAILED')
 def test_stale_credentials_revision_blocks_queued_job(self):
  c=self.connection();self.post('/connections/'+c['id']+'/sync');self.db.execute('UPDATE connections SET revision=revision+1')
  with patch('cloudops.jobs.providers.adapter') as adapter:self.app.state.worker.run_one();adapter.assert_not_called()
  self.assertEqual(self.db.one('SELECT status FROM jobs')['status'],'FAILED')
 def test_inventory_failure_keeps_last_known_resources(self):
  c=self.connection();self.assigned(c);self.post('/connections/'+c['id']+'/sync')
  with patch('cloudops.jobs.providers.adapter') as adapter:adapter.return_value.inventory.side_effect=RuntimeError('secret provider response');self.app.state.worker.run_one()
  self.assertEqual(self.db.one('SELECT missing FROM resources')['missing'],0);self.assertNotIn('secret provider response',self.db.one('SELECT message FROM jobs')['message']);self.assertTrue(self.db.one('SELECT error FROM connections')['error'])
 def test_inventory_commits_only_after_success(self):
  c=self.connection();self.assigned(c);self.post('/connections/'+c['id']+'/sync')
  with patch('cloudops.jobs.providers.adapter') as adapter:adapter.return_value.inventory.return_value=[];self.app.state.worker.run_one()
  self.assertEqual(self.db.one('SELECT missing FROM resources')['missing'],1)
 def test_actual_action_scoped_to_assigned_resource(self):
  c=self.connection();self.assigned(c);self.assertEqual(self.post('/resources/r1/action',{'kind':'STOP','confirm':'wrong'}).status_code,400);self.post('/resources/r1/action',{'kind':'STOP','confirm':'i-1234567890abcdef0'})
  with patch('cloudops.jobs.providers.adapter') as adapter:self.app.state.worker.run_one();adapter.return_value.action.assert_called_once_with('i-1234567890abcdef0','stop')
  self.assertEqual(self.db.one('SELECT status FROM jobs')['status'],'SUCCEEDED')
 def test_key_rotation_hides_secret_and_revokes_job_revision(self):
  c=self.connection();self.post('/connections/'+c['id']+'/sync');r=self.post('/connections/'+c['id']+'/security',{'admin_password':'A-long-test-password!','access_key':'new-access','secret_key':'new-secret'})
  self.assertEqual(r.status_code,303);updated=self.db.one('SELECT * FROM connections');self.assertEqual(updated['revision'],2);self.assertEqual(updated['writable'],0);self.assertNotIn('new-secret',self.client.get('/').text)
 def test_logout_revokes_server_session(self):
  old=self.client.cookies[COOKIE];self.assertEqual(self.post('/logout').status_code,303);self.client.cookies.set(COOKIE,old);self.assertEqual(self.client.get('/api/overview').status_code,401)
 def test_self_disable_rejected_and_password_change_revokes_all(self):
  actor=self.db.one("SELECT * FROM users WHERE role='ADMIN'");self.assertEqual(self.post('/users/'+str(actor['id'])+'/disable').status_code,400);self.assertEqual(self.post('/password',{'current':'A-long-test-password!','password':'New-long-test-password!'}).status_code,303);self.assertEqual(self.db.one('SELECT COUNT(*) n FROM sessions WHERE user_id=?',(actor['id'],))['n'],0)
 def test_no_public_registration_and_no_fake_counts(self):
  self.assertEqual(self.client.get('/register').status_code,404);page=self.client.get('/');self.assertIn('아직 연결된 실제 클라우드나 예시 자원은 없습니다',page.text);self.assertEqual(page.headers['cache-control'],'no-store');self.assertIn("frame-ancestors 'none'",page.headers['content-security-policy'])
 def test_environment_requires_explicit_account_and_confirmation(self):
  c=self.connection();e=self.assigned(c);r=self.post('/environments',{'connection_id':c['id'],'event_id':e['id'],'lab_id':'test-training','count':'1','volume':'20','instance':'t3.micro'})
  self.assertEqual(r.status_code,303);env=self.db.one('SELECT * FROM environments');self.assertEqual(self.post('/environments/'+env['id']+'/action',{'kind':'PROVISION','confirm':env['lab_id'],'account':'999999999999'}).status_code,400);self.assertIsNone(self.db.one('SELECT * FROM jobs'))
 def test_ncp_signature_covers_encoded_query(self):
  import hmac,hashlib
  
  with patch('cloudops.providers.httpx.Client'):c=NCP({'region':'KR'},{'access_key':'access','secret_key':'secret'})
  c.http=Mock();c.http.get.return_value.is_success=True;c.http.get.return_value.json.return_value={'getServerInstanceListResponse':{'returnCode':0,'serverInstanceList':[]}}
  with patch('cloudops.providers.time.time',return_value=123):c.inventory()
  args,kw=c.http.get.call_args;uri=args[0].removeprefix('https://ncloud.apigw.ntruss.com');expected=base64.b64encode(hmac.new(b'secret',f'GET {uri}\n123000\naccess'.encode(),hashlib.sha256).digest()).decode();self.assertEqual(kw['headers']['x-ncp-apigw-signature-v2'],expected)
 def test_aws_secret_checkpoint_is_durable_before_mutation(self):
  c=self.connection();event=self.assigned(c);self.post('/environments',{'connection_id':c['id'],'event_id':event['id'],'lab_id':'durable-lab','count':'1','volume':'20','instance':'t3.micro'});env=self.db.one('SELECT * FROM environments')
  from roster_fixture import approved_config
  self.db.execute('UPDATE environments SET config=? WHERE id=?',(json.dumps(approved_config(json.loads(env['config']))),env['id']));env=self.db.one('SELECT * FROM environments')
  fake=Path(self.tmp.name)/'fake_lab.py';fake.write_text("import json\ndef save_private(path,value):\n path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))\ndef load_config(path,deployment=False):return json.loads(path.read_text())\ndef deploy(config,state):\n save_private(state/'student'/'credentials.json',{'password':'only-in-encrypted-vault'});aws(config,'cloudformation','create-stack')\ndef destroy(config):pass\n")
  worker=self.app.state.worker;worker.runner=fake
  def run(*args,**kwargs):
   stored=self.db.one('SELECT state FROM environments WHERE id=?',(env['id'],))['state'];files=self.vault.open(stored,'state:'+env['id']);self.assertIn('student/credentials.json',files);self.assertNotIn('OPS_MASTER_KEY',kwargs['env']);return Mock(returncode=0,stdout='{}')
  with patch('cloudops.jobs.providers.AWS') as aws,patch('cloudops.jobs.subprocess.run',side_effect=run):worker.aws_lab(c,{'access_key':'test','secret_key':'test'},{'id':'job-test','target':env['id'],'kind':'PROVISION','payload':json.dumps({'roster_revision':json.loads(env['config'])['lms_roster']['revision']})})
  self.assertNotIn('only-in-encrypted-vault',Path(self.tmp.name,'ops.sqlite3').read_bytes().decode(errors='ignore'))
 def test_restart_marks_running_job_interrupted(self):
  c=self.connection();self.post('/connections/'+c['id']+'/sync');self.db.execute("UPDATE jobs SET status='RUNNING'");worker=self.app.state.worker;worker.stop.set();worker.loop();self.assertEqual(self.db.one('SELECT status FROM jobs')['status'],'INTERRUPTED')
 def test_nhn_rejects_untrusted_catalog_endpoint(self):
  from cloudops.providers import NHN
  with patch('cloudops.providers.httpx.Client'):c=NHN({'account':'tenant','region':'KR1'},{'username':'iam','api_password':'test'})
  response=Mock(is_success=True);response.json.return_value={'access':{'token':{'id':'never-show','tenant':{'id':'tenant'}},'serviceCatalog':[{'type':'compute','endpoints':[{'region':'KR1','publicURL':'http://127.0.0.1/private'}]}]}};c.http=Mock();c.http.post.return_value=response
  with self.assertRaises(CloudError):c.auth()
 def test_https_required_and_master_key_size(self):
  with self.assertRaises(ValueError):create_app({'OPS_ORIGIN':'http://ops.test'})
  with self.assertRaises(ValueError):Vault(base64.b64encode(b'short').decode())
if __name__=='__main__':unittest.main()

import copy,io,json,threading,time,unittest,zipfile
from unittest.mock import patch
from cloudops.nhn_iam import IAM,Client,make_plan,login_url
from cloudops.nhn_iam_roles import ROLE_NAMES
from cloudops.providers import CloudError
from cloudops.student_bundles import build
import test_nhn_batch as fixture

class Fake:
 def __init__(self,*args):
  self.calls=[];self.roles={'project01':[],'project02':[]};self.status='member';self.extra=False
 def close(self):pass
 def projects(self,org):
  n=1 if org=='orgOne' else 2
  return [{'projectId':f'project{n:02}','projectName':f'Class{n:02}','orgId':org,'projectStatusCode':'STABLE'}]
 def core(self,path,body=None,method=None):
  path=path.split('?')[0];parts=path.split('/');self.calls.append((method,path,copy.deepcopy(body)))
  if '/iam/organizations/' in path:
   return {'orgMember':{'id':parts[-1],'organizationId':parts[-3],'userCode':'educity'+parts[-1][-2:],'status':self.status,'passwordChangedAt':'UNCHANGED'}}
  pid=parts[4] if '/iam/projects/' in path else parts[3];n=pid[-2:]
  if path.endswith('/roles'):
   return {'roles':[{'roleId':'role'+str(i),'roleName':name,'categoryTypeCode':'ROLE','roleCategory':'PROJECT_SERVICE_ROLE'} for i,name in enumerate(ROLE_NAMES)],'totalCount':4}
  if path.endswith('/members/search'):
   return {'projectMembers':[{'uuid':'protected','memberTypeCode':'TOAST_CLOUD','emailAddress':'operator@example.com'}],'paging':{'totalCount':1}}
  if path.endswith('/members/protected'):
   return {'projectMember':{'uuid':'protected','roles':[{'roleId':'admin','roleName':'ADMIN','categoryKey':'ProjectRole'}]}}
  if path.endswith('/members'):
   records=[{'uuid':'uuid'+n,'id':'educity'+n}]
   if self.extra and pid=='project03':records.append({'uuid':'uuid01','id':'educity01'})
   return {'projectMembers':records,'totalCount':len(records)}
  if '/members/uuid' in path:
   if method=='PUT':self.roles[pid]=copy.deepcopy(body['assignRoles']);return {}
   return {'projectMember':{'uuid':'uuid'+n,'id':'educity'+n,'relatedRoles':copy.deepcopy(self.roles[pid])}}
  raise AssertionError(path)

CFG={'org':'orgOne','project_prefix':'Class','first':1,'last':2,'project_scopes':[{'org':'orgTwo','prefix':'Class','first':2,'last':2}]}
SETTINGS={'prefix':'educity','operator':'operator@example.com','urls':{}}
class PlanTests(unittest.TestCase):
 def test_two_orgs_and_query_never_mutates(self):
  raw=Fake();plan=make_plan(Client(raw),CFG,SETTINGS,threading.Event())
  self.assertEqual([(r['org'],r['username']) for r in plan['rows']],[('orgOne','educity01'),('orgTwo','educity02')])
  self.assertEqual([r['status'] for r in plan['rows']],['PLANNED','PLANNED']);self.assertFalse(any(c[0]=='PUT' for c in raw.calls))
 def test_active_correct_roles_skip_and_other_roles_block(self):
  raw=Fake();raw.roles['project01']=[{'roleId':'role'+str(i)} for i in range(4)];raw.roles['project02']=[{'roleId':'admin'}]
  plan=make_plan(Client(raw),CFG,SETTINGS,threading.Event());self.assertEqual([r['status'] for r in plan['rows']],['UNCHANGED','BLOCKED'])
 def test_suspended_and_cross_project_block(self):
  raw=Fake();raw.status='disabled';self.assertTrue(all(r['status']=='BLOCKED' for r in make_plan(Client(raw),CFG,SETTINGS,threading.Event())['rows']))
  raw.extra=True;original=raw.projects
  raw.projects=lambda org: original(org)+([{'projectId':'project03','projectName':'Other','orgId':org,'projectStatusCode':'STABLE'}] if org=='orgOne' else [])
  with self.assertRaises(CloudError):make_plan(Client(raw),CFG,SETTINGS,threading.Event())
 def test_login_url_rejects_credential_or_external_hosts(self):
  for url in ['http://foo.nhncloud.com','https://nhncloud.com.evil.test','https://user@foo.nhncloud.com','https://foo.nhncloud.com:444']:
   with self.assertRaises(CloudError):login_url(url)
  self.assertEqual(login_url('https://foo.nhncloud.com/login'),'https://foo.nhncloud.com/login')

class ApplyTests(unittest.TestCase):
 setUp=fixture.BatchTests.setUp
 tearDown=fixture.BatchTests.tearDown
 post=fixture.BatchTests.post
 create=fixture.BatchTests.create
 def prepare(self):
  id=self.create();b=self.db.one('SELECT * FROM nhn_batches');cfg=json.loads(b['config']);cfg.update(CFG);self.db.execute('UPDATE nhn_batches SET config=? WHERE id=?',(json.dumps(cfg),id))
  self.db.execute('INSERT INTO nhn_iam(batch_id,config,updated) VALUES(?,?,?)',(id,json.dumps(SETTINGS),time.time()))
  return id,IAM(self.db,self.vault,threading.Event())
 def test_apply_verifies_preserves_credentials_and_replans_as_no_change(self):
  id,manager=self.prepare();raw=Fake();before=self.db.one('SELECT state,secret FROM nhn_batches')
  with patch('cloudops.nhn_iam.API',return_value=raw):
   manager.plan(id);self.assertEqual(self.client.get('/').status_code,200);manager.apply(id)
   puts=[c for c in raw.calls if c[0]=='PUT'];self.assertEqual(len(puts),2);self.assertTrue(all(set(c[2])=={'assignRoles'} for c in puts))
   self.assertEqual(self.db.one('SELECT status FROM nhn_iam')['status'],'VERIFIED')
   manager.plan(id);manager.apply(id);self.assertEqual(len([c for c in raw.calls if c[0]=='PUT']),2)
  self.assertEqual(self.db.one('SELECT state,secret FROM nhn_batches'),before)
  self.assertTrue(self.db.one("SELECT id FROM nhn_iam_history WHERE status='RUNNING'"))
  self.assertFalse(any('password' in c[1] for c in raw.calls))
 def test_drift_is_detected_before_write(self):
  id,manager=self.prepare();raw=Fake()
  with patch('cloudops.nhn_iam.API',return_value=raw):
   manager.plan(id);raw.status='disabled'
   with self.assertRaises(CloudError):manager.apply(id)
  self.assertFalse(any(c[0]=='PUT' for c in raw.calls))
 def test_readonly_plan_job_works_without_writable_and_rejects_missing_csrf(self):
  id,_=self.prepare();self.db.execute('UPDATE connections SET writable=0');raw=Fake();path='/nhn/batches/'+id+'/iam'
  self.assertEqual(self.client.post(path,data={'kind':'NHN_IAM_PLAN'},headers={'Origin':'https://ops.test'}).status_code,403)
  r=self.post(path,{'kind':'NHN_IAM_PLAN','prefix':'educity','operator':'operator@example.com'});self.assertEqual(r.status_code,303)
  with patch('cloudops.nhn_iam.API',return_value=raw):self.assertTrue(self.app.state.worker.run_one())
  self.assertEqual(self.db.one("SELECT status FROM jobs WHERE kind='NHN_IAM_PLAN'")['status'],'SUCCEEDED')
  self.assertIn('educity01',self.client.get('/').text);self.assertFalse(any(c[0]=='PUT' for c in raw.calls))
 def test_route_requires_admin_password_csrf_and_writable(self):
  id,_=self.prepare();path='/nhn/batches/'+id+'/iam'
  self.assertEqual(self.post(path,{'kind':'NHN_IAM_APPLY','confirm':'class-batch','password':'wrong'}).status_code,403)
  self.db.execute("UPDATE users SET role='OPERATOR'")
  self.assertEqual(self.post(path,{'kind':'NHN_IAM_PLAN'}).status_code,403)

class ZipTests(unittest.TestCase):
 def test_iam_addition_keeps_existing_credentials_and_excludes_extra_fields(self):
  servers={'s01':{'ready':True,'summary':{'project':'Class01','ip':'133.186.251.193'},'key_material':{'private':'SAME-PEM'}}}
  iam={'s01':{'username':'educity01','project':'Class01','login_url':'https://foo.nhncloud.com','password':'NEVER-EXPORT'}}
  payload,_=build(servers,{}, {},iam);outer=zipfile.ZipFile(io.BytesIO(payload));inner=zipfile.ZipFile(io.BytesIO(outer.read('s01_s01.zip')))
  access=json.loads(inner.read('access.json'));self.assertEqual(access['public_ip'],'133.186.251.193');self.assertEqual(access['iam']['username'],'educity01');self.assertEqual(inner.read('s01-key.pem'),b'SAME-PEM');self.assertNotIn('NEVER-EXPORT',inner.read('access.json').decode())

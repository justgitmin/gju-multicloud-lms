import io,json,unittest,zipfile
from cloudops.student_bundles import build
import test_nhn_batch as fixture
class BundleTests(unittest.TestCase):
 def test_nested_zips_contain_only_their_students_secrets(self):
  servers={c:{'ready':True,'person':{'name':c,'email':c+'@example.com'},'summary':{'project':c,'server_name':c+'-web','ip':'10.0.0.1, 133.186.146.222'},'key_material':{'private':'PRIVATE-'+c}} for c in ['s01','s02']}
  batch={c:{'summary':{'container':c+'-files'},'access':{'db_host':'10.0.0.5','db_port':3306,'db_user':'labuser','db_name':'labdb','db_password':'PASSWORD-'+c},'operator_api_key':'NEVER-EXPORT'} for c in servers}
  data,manifest=build(servers,batch,{'s01':'READY','s02':'READY'});outer=zipfile.ZipFile(io.BytesIO(data));self.assertEqual(len(manifest),2)
  for c in servers:
   inner=zipfile.ZipFile(io.BytesIO(outer.read(c+'_'+c+'.zip')));alltext='\n'.join(inner.read(n).decode('utf-8-sig') for n in inner.namelist());self.assertIn('PRIVATE-'+c,alltext);self.assertIn('PASSWORD-'+c,alltext);self.assertNotIn('NEVER-EXPORT',alltext)
   other='s02' if c=='s01' else 's01';self.assertNotIn('PRIVATE-'+other,alltext);self.assertNotIn('PASSWORD-'+other,alltext)
   access=json.loads(inner.read('access.json'));self.assertEqual(access['public_ip'],'133.186.146.222');self.assertTrue(access['database_ready'])
 def test_partial_database_and_missing_pem_are_explicit(self):
  servers={'s01':{'ready':True,'summary':{'ip':'133.186.251.193'}}};batch={'s01':{'access':{'db_password':'INCOMPLETE-SECRET'}}}
  data,manifest=build(servers,batch,{'s01':'RUNNING'});outer=zipfile.ZipFile(io.BytesIO(data));inner=zipfile.ZipFile(io.BytesIO(outer.read('s01_s01.zip')))
  self.assertFalse(manifest[0]['pem_included']);self.assertFalse(manifest[0]['database_ready']);self.assertFalse(any(n.endswith('.pem') for n in inner.namelist()));self.assertNotIn('INCOMPLETE-SECRET',inner.read('access.json').decode());self.assertIn('기존에 개별 전달받은 PEM',inner.read('접속안내.txt').decode('utf-8-sig'))
 def test_unready_servers_skipped_and_codes_validated(self):
  data,manifest=build({'s01':{}},{},{})
  self.assertFalse(manifest[0]['included'])
  with self.assertRaises(ValueError):build({'../s01':{}},{},{})
class ArchiveAuthTests(unittest.TestCase):
 setUp=fixture.BatchTests.setUp
 tearDown=fixture.BatchTests.tearDown
 post=fixture.BatchTests.post
 create=fixture.BatchTests.create
 def test_admin_reauthentication_and_no_cache(self):
  id=self.create(True);self.manager.apply(id)
  path='/nhn/batches/'+id+'/students/archive'
  self.assertEqual(self.post(path,{'password':'wrong'}).status_code,403)
  r=self.post(path,{'password':'A-long-test-password!'});self.assertEqual(r.status_code,200);self.assertEqual(r.headers['cache-control'],'no-store');self.assertTrue(zipfile.is_zipfile(io.BytesIO(r.content)))
  self.db.execute("UPDATE users SET role='OPERATOR'");self.assertEqual(self.post(path,{'password':'A-long-test-password!'}).status_code,403)
if __name__=='__main__':unittest.main()

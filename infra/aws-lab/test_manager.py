import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parent))
import manager

class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.m=manager.Manager(self.temp.name)
        self.c=json.loads((Path(__file__).with_name('config.example.json')).read_text())
    def tearDown(self):self.temp.cleanup()
    def test_saves_reusable_configs_without_aws_credentials(self):
        self.c['AWS_SECRET_ACCESS_KEY']='never-retain';self.m.save(self.c)
        saved=self.m.read(self.c['lab_id'])
        self.assertNotIn('AWS_SECRET_ACCESS_KEY',saved)
        self.assertEqual(saved['access_mode'],'ssm')
    def test_path_traversal_rejected(self):
        for value in ['../outside','/tmp/test','foo/bar','A','']:
            with self.assertRaises(ValueError):self.m.path(value)
    def test_invalid_form_does_not_replace_saved_config(self):
        self.m.save(self.c);self.c['volume_gb']=999
        with self.assertRaises(ValueError):self.m.save(self.c)
        self.assertEqual(self.m.read(self.c['lab_id'])['volume_gb'],20)
    def test_unsupported_action_is_rejected(self):
        with self.assertRaises(ValueError):self.m.start('shell','x',[], '', '', '')
    def test_wrong_confirmation_never_invokes_aws(self):
        self.m.save(self.c)
        with patch.object(self.m,'identity') as mocked:
            with self.assertRaises(ValueError):self.m.start('destroy',self.c['lab_id'],['s01'],'','123456789012','wrong-name')
            mocked.assert_not_called()
    def test_unknown_student_rejected(self):
        self.m.save(self.c)
        with self.assertRaises(ValueError):self.m.start('apply',self.c['lab_id'],['s99'],'','123456789012',self.c['lab_id'])
    def test_account_mismatch_never_starts_job(self):
        self.m.save(self.c)
        with patch.object(self.m,'identity',return_value={'account':'111111111111'}),patch.object(manager.subprocess,'Popen') as mocked:
            with self.assertRaises(ValueError):self.m.start('apply',self.c['lab_id'],['s01'],'','222222222222',self.c['lab_id'])
            mocked.assert_not_called()
    def test_existing_credentials_not_overwritten(self):
        self.m.save(self.c);(self.m.state/(self.c['lab_id']+'-s01')).mkdir()
        with patch.object(self.m,'identity',return_value={'account':'111111111111'}),patch.object(manager.subprocess,'Popen') as mocked:
            with self.assertRaises(ValueError):self.m.start('apply',self.c['lab_id'],['s01'],'','111111111111',self.c['lab_id'])
            mocked.assert_not_called()
    def test_gui_rejects_ssh_mode(self):
        self.c['access_mode']='ssh'
        with self.assertRaises(ValueError):self.m.save(self.c)
    def test_http_requires_csrf_and_local_host(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),manager.make_handler(self.m));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urlopen(base) as r:
                self.assertEqual(r.status,200);self.assertEqual(r.headers['Cache-Control'],'no-store')
                self.assertIn(self.m.token,r.read().decode())
            request=Request(base+'/api/init',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
            with self.assertRaises(HTTPError) as e:urlopen(request)
            self.assertEqual(e.exception.code,403)
            request.add_header('X-Lab-Token',self.m.token)
            with urlopen(request) as r:self.assertIn('configs',json.loads(r.read()))
            request.add_header('Origin','https://foreign.example')
            with self.assertRaises(HTTPError) as e:urlopen(request)
            self.assertEqual(e.exception.code,403)
            request=Request(base,headers={'Host':'attacker.example'})
            with self.assertRaises(HTTPError) as e:urlopen(request)
            self.assertEqual(e.exception.code,403)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()

class LmsSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.m=manager.Manager(self.temp.name)
        self.c=json.loads((Path(__file__).with_name('config.example.json')).read_text());self.c['students']=['s01'];self.c['student_emails']={'s01':'student@example.invalid'};self.m.save(self.c)
        self.folder=self.m.state/(self.c['lab_id']+'-s01');self.folder.mkdir()
        (self.folder/'credentials.json').write_text(json.dumps({'account_id':'123456789012','username':self.c['lab_id']+'-s01','initial_password':'fake-initial-password','db_password':'fake-db-password','AWS_SECRET_ACCESS_KEY':'must-not-send'}))
        (self.folder/'outputs.json').write_text(json.dumps({'Username':self.c['lab_id']+'-s01','InstanceId':'i-0123456789abcdef0','SessionDocument':self.c['lab_id']+'-shell'}))
    def tearDown(self):self.temp.cleanup()
    def test_batch_maps_explicit_email_without_aws_admin_key(self):
        b=self.m.batch(self.c['lab_id'],['s01'],'course-test');e=b['entries'][0]
        self.assertEqual(e['email'],'student@example.invalid');self.assertNotIn('AWS_SECRET_ACCESS_KEY',e)
        self.assertEqual(e['studentCode'],'s01')
    def test_http_url_is_rejected_before_network(self):
        with patch.object(manager,'build_opener') as mocked:
            with self.assertRaises(ValueError):self.m.sync(self.c['lab_id'],['s01'],'course-test','http://lms.example.com','a'*64)
            mocked.assert_not_called()
    def test_sync_uses_post_tls_and_no_redirect_handler(self):
        from unittest.mock import MagicMock
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{"count":1,"students":[]}'
        opener=MagicMock();opener.open.return_value=response
        with patch.object(manager,'build_opener',return_value=opener) as mocked:
            result=self.m.sync(self.c['lab_id'],['s01'],'course-test','https://lms.example.com','a'*64)
            req=opener.open.call_args.args[0]
            self.assertEqual(req.full_url,'https://lms.example.com/api/admin/lab-import');self.assertEqual(req.method,'POST')
            self.assertEqual(req.headers['Authorization'],'Bearer '+'a'*64)
            self.assertIsNone(mocked.call_args.args[0].redirect_request(None,None,None,None,None,None))
            self.assertEqual(result['count'],1)
    def test_missing_mapping_refuses_export(self):
        self.c['student_emails']={};self.m.save(self.c)
        with self.assertRaises(ValueError):self.m.batch(self.c['lab_id'],['s01'],'course-test')

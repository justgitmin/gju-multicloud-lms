import datetime,importlib.util,os,sqlite3,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
# UI logic tests do not need database credentials or a PostgreSQL server.
try:import psycopg
except ImportError:
 sys.modules['psycopg']=types.ModuleType('psycopg');sys.modules['psycopg.rows']=types.SimpleNamespace(dict_row=None)
spec=importlib.util.spec_from_file_location('attendance_service',Path(__file__).with_name('service.py'));service=importlib.util.module_from_spec(spec);spec.loader.exec_module(service)
from fastapi.testclient import TestClient
class AttendanceTests(unittest.TestCase):
 def test_kst_day_boundary(self):
  start,end=service.dates('2026-11-11');self.assertEqual(start.isoformat(),'2026-11-11T00:00:00+09:00');self.assertEqual((end-start).total_seconds(),86400)
 def test_requires_admin(self):
  c=TestClient(service.app);r=c.get('/attendance',follow_redirects=False);self.assertEqual(r.status_code,303);self.assertEqual(r.headers['location'],'/login')
 def test_csv_separates_manual_and_actual_and_escapes_formula(self):
  moment=datetime.datetime(2026,11,11,8,30,tzinfo=datetime.timezone.utc)
  rows=[{'name':'=formula','email':'student@example.com','studentNumber':'1','kind':'MANUAL_ATTENDANCE','eventAt':moment,'recordedAt':moment+datetime.timedelta(hours=1),'registeredBy':'operator','note':'실제 로그인 아님'}]
  with patch.object(service,'actor',return_value={'role':'ADMIN'}),patch.object(service,'report',return_value=rows):
   r=TestClient(service.app).get('/attendance.csv?date=2026-11-11');self.assertEqual(r.status_code,200);self.assertIn("'=formula",r.text);self.assertIn('운영자 수동 출석',r.text);self.assertIn('17:30:00 KST',r.text);self.assertIn('18:30:00 KST',r.text);self.assertEqual(r.headers['cache-control'],'no-store')
 def test_html_escapes_student_name(self):
  now=datetime.datetime.now(datetime.timezone.utc);rows=[{'name':'<script>bad</script>','email':'x@example.com','studentNumber':None,'kind':'LOGIN','eventAt':now,'recordedAt':now,'registeredBy':None,'note':''}]
  with patch.object(service,'actor',return_value={'role':'ADMIN'}),patch.object(service,'report',return_value=rows):
   r=TestClient(service.app).get('/attendance');self.assertNotIn('<script>bad',r.text);self.assertIn('&lt;script&gt;',r.text)

@unittest.skipUnless(os.environ.get('ATTENDANCE_TEST_DATABASE_URL'),'isolated PostgreSQL test database required')
class DatabaseTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import psycopg
  cls.db=psycopg.connect(os.environ['ATTENDANCE_TEST_DATABASE_URL'],autocommit=True)
  cls.db.execute('''CREATE TABLE "User"(id text PRIMARY KEY,name text,role text);CREATE TABLE "Session"(id text PRIMARY KEY,"userId" text);CREATE TABLE "Enrollment"(id text PRIMARY KEY,"userId" text);CREATE TABLE "Playback"(id text PRIMARY KEY,"enrollmentId" text,"lastAt" timestamptz);''')
  cls.db.execute(Path(__file__).with_name('install.sql').read_text())
 @classmethod
 def tearDownClass(cls):cls.db.close()
 def test_real_login_and_learning_events(self):
  self.db.execute('''INSERT INTO "User" VALUES('s1','Student','STUDENT'),('a1','Admin','ADMIN');INSERT INTO "Session" VALUES('ses1','s1'),('admin1','a1');INSERT INTO "Enrollment" VALUES('e1','s1');INSERT INTO "Playback" VALUES('p1','e1',now());UPDATE "Playback" SET "lastAt"=now() WHERE id='p1';''')
  actual=self.db.execute('SELECT kind,count(*) FROM "LmsAccessEvidence" GROUP BY kind ORDER BY kind').fetchall();self.assertEqual(actual,[('LEARNING_ACTIVITY',1),('LOGIN',1)])
  self.assertTrue(self.db.execute('SELECT bool_and("eventAt">now()-interval \'1 minute\') FROM "LmsAccessEvidence"').fetchone()[0])
if __name__=='__main__':unittest.main()

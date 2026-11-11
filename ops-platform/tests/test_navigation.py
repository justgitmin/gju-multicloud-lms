import unittest,json,time
from html.parser import HTMLParser
import test_nhn_batch as fixture
class Structure(HTMLParser):
 def __init__(self):super().__init__();self.stack=[];self.elements=[]
 def handle_starttag(self,tag,attrs):
  data=dict(attrs);self.elements.append((tag,data,list(self.stack)))
  if tag not in ['input','meta','link','br','hr','img','source','wbr']:self.stack.append((tag,data))
 def handle_endtag(self,tag):
  for n in range(len(self.stack)-1,-1,-1):
   if self.stack[n][0]==tag:self.stack=self.stack[:n];break
class NavigationTests(unittest.TestCase):
 setUp=fixture.BatchTests.setUp
 tearDown=fixture.BatchTests.tearDown
 post=fixture.BatchTests.post
 create=fixture.BatchTests.create
 def test_views_and_vendor_panels_are_separate_and_old_targets_survive(self):
  page=self.client.get('/').text;s=Structure();s.feed(page)
  views=[d['data-view'] for _,d,_ in s.elements if 'data-view' in d]
  self.assertEqual(set(views),{'overview','resources','events','connections','prepare','jobs','users','audit','security'})
  self.assertEqual(len(views),9)
  for _,d,parents in s.elements:
   if 'data-view' in d:self.assertFalse(any('data-view' in p for _,p in parents))
   if d.get('id') in ['provision','nhn-batches']:
    self.assertEqual(next(p['data-vendor-panel'] for _,p in reversed(parents) if 'data-vendor-panel' in p),'AWS' if d['id']=='provision' else 'NHN')
  self.assertEqual({d['data-vendor-panel'] for _,d,_ in s.elements if 'data-vendor-panel' in d},{'AWS','NHN','NCP'})
  self.assertIn('교육 환경 일괄 생성·삭제는 아직 지원하지 않습니다.',page)
  self.assertIn('href="/attendance"',page)
 def test_viewer_has_no_provision_or_admin_panels(self):
  self.db.execute("UPDATE users SET role='VIEWER'");page=self.client.get('/').text;s=Structure();s.feed(page)
  self.assertFalse({'prepare','users','audit'}&{d.get('data-view') for _,d,_ in s.elements})
  self.assertNotIn('data-vendor-panel',page);self.assertNotIn('action="/environments"',page)
 def test_connection_redirect_target_is_still_inside_connection_view(self):
  s=Structure();s.feed(self.client.get('/').text)
  target=next((d,parents) for _,d,parents in s.elements if d.get('id')=='connection-'+self.c['id'])
  self.assertEqual(next(p['data-view'] for _,p in reversed(target[1]) if 'data-view' in p),'connections')
  self.assertEqual(target[0]['data-cloud-card'],'NHN')
 def test_mutations_return_to_their_own_section(self):
  r=self.post('/events',{'name':'Another class','ends':'2026-12-01'});self.assertEqual(r.headers['location'],'/#events')
  r=self.post('/users',{'name':'Observer','email':'observer@example.com','password':'A-long-test-password!','role':'VIEWER'});self.assertEqual(r.headers['location'],'/#users')
 def test_saved_roster_names_survive_storage_plan_summary_replacement(self):
  id=self.create(True)
  self.db.execute('INSERT INTO nhn_bootstrap(batch_id,config,updated) VALUES(?,?,?)',(id,json.dumps({'roster':{'s01':{'name':'Student One','email':'one@example.com'},'s02':{'name':'Student Two','email':'two@example.com'}}}),time.time()))
  self.manager.apply(id)
  page=self.client.get('/').text
  self.assertIn('s01 Student One',page);self.assertIn('s02 Student Two',page)
if __name__=='__main__':unittest.main()

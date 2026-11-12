import json,unittest
from unittest.mock import patch,Mock
import test_nhn_batch as fixture

class ConnectionSyncTests(unittest.TestCase):
 setUp=fixture.BatchTests.setUp
 tearDown=fixture.BatchTests.tearDown
 post=fixture.BatchTests.post
 def test_sync_preserves_vendor_and_duplicate_requests_do_not_queue(self):
  path='/connections/'+self.c['id']+'/sync'
  response=self.post(path,{'_return':'/#connections/AWS'})
  self.assertEqual(response.headers['location'],'/#connections/AWS')
  self.post(path,{'_return':'/#connections/AWS'})
  self.assertEqual(self.db.one('SELECT COUNT(*) n FROM jobs')['n'],1)
 def test_snapshot_tracks_status_without_credentials(self):
  self.post('/connections/'+self.c['id']+'/sync')
  snapshot=self.client.get('/api/overview').json()['connections'][0]
  self.assertEqual(set(snapshot),{'id','last_sync','error','sync_job'})
  self.assertEqual(snapshot['sync_job']['status'],'QUEUED')
  page=self.client.get('/').text
  self.assertIn('동기화 대기 중',page)
  self.assertIn('data-connection-sync-button disabled',page)
  with patch('cloudops.providers.adapter') as adapter:
   adapter.return_value.inventory.return_value=[]
   self.app.state.worker.run_one()
  snapshot=self.client.get('/api/overview').json()['connections'][0]
  self.assertEqual(snapshot['sync_job']['status'],'SUCCEEDED')
  self.assertTrue(snapshot['last_sync'])
  self.assertIsNone(snapshot['error'])
  self.assertNotIn('SECRET-API',json.dumps(snapshot))
 def test_manual_work_precedes_automatic_work(self):
  worker=self.app.state.worker
  auto=worker.enqueue(1,self.c,'SYNC',self.c['id'],{'automatic':True})
  self.post('/connections',{'name':'aws','provider':'AWS','region':'ap-northeast-2','account':'123456789012','access_key':'test','secret_key':'test'})
  second=self.db.one("SELECT * FROM connections WHERE provider='AWS'")
  manual=worker.enqueue(1,second,'SYNC',second['id'])
  with patch.object(worker,'sync') as sync:
   worker.run_one()
   self.assertEqual(sync.call_args.args[0]['id'],second['id'])
  self.assertEqual(self.db.one('SELECT status FROM jobs WHERE id=?',(auto,))['status'],'QUEUED')
  self.assertEqual(self.db.one('SELECT status FROM jobs WHERE id=?',(manual,))['status'],'SUCCEEDED')

 def test_slow_refresh_does_not_immediately_schedule_another_cycle(self):
  worker=self.app.state.worker
  self.db.execute('UPDATE connections SET last_sync=1')
  clock=[1000.0];calls=[0]
  def run_one():
   calls[0]+=1
   if calls[0]==2:clock[0]+=130;return True
   return False
  worker.stop=Mock();worker.stop.is_set.side_effect=[False,False,False,True]
  with patch.object(worker,'run_one',side_effect=run_one),patch.object(worker,'enqueue') as enqueue,patch('cloudops.jobs.time.time',side_effect=lambda:clock[0]):
   worker.loop()
  self.assertEqual(enqueue.call_count,1)
  self.assertTrue(enqueue.call_args.args[-1]['automatic'])

if __name__=='__main__':unittest.main()

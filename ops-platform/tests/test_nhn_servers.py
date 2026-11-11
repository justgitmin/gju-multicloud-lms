import json,secrets,unittest
from unittest.mock import patch
from urllib.parse import urlparse,parse_qs
from cryptography.hazmat.primitives import serialization
import test_nhn_batch as fixture
from cloudops.nhn_servers import Servers,generate_key
from cloudops.nhn_batch import CloudError

class ServerAPI(fixture.FakeAPI):
 added=[]
 def projects(self,org):return super().projects(org)+type(self).added
 def core(self,path,enable=False,body=None):
  if body:
   p={'projectId':'newproject'+str(len(type(self).added)),'projectName':body['projectName'],'description':body['description'],'orgId':'org123456789','projectStatusCode':'STABLE'};type(self).added.append(p);return {'project':p}
  if '/products/' in path and not enable:return {'product':self.product(path.split('/')[3],path.rsplit('/',1)[1])}
  return super().core(path,enable=enable)

class Infra:
 clouds={};fail_server=False;hook=None
 def __init__(self,api,product):
  self.api=api;self.product=product;self.cloud=type(self).clouds.setdefault(product['projectId'],{});self.compute=self;self.http=self
 def close(self):pass
 def inventory(self):return [{'remote_id':x['id'],'name':x['name'],'state':x.get('status','ACTIVE'),'ip':'1.2.3.4'} for x in self.cloud.get('servers',[])]
 def request(self,path,body=None):
  if path=='/os-keypairs':
   if body:self.cloud.setdefault('keys',[]).append(body['keypair']);return body
   return {'keypairs':[{'keypair':x} for x in self.cloud.get('keys',[])]}
  if path=='/servers' and body:
   if type(self).hook:type(self).hook()
   x={**body['server'],'id':'server'+secrets.token_hex(5),'status':'ACTIVE'};self.cloud.setdefault('servers',[]).append(x)
   if type(self).fail_server:type(self).fail_server=False;raise TimeoutError('ambiguous creation')
   return {'server':x}
  if path.startswith('/servers/'):return {'server':next(x for x in self.cloud['servers'] if x['id']==path.rsplit('/',1)[1])}
  raise AssertionError(path)
 def wait_server(self,id,stop):return self.request('/servers/'+id)['server']
 def net(self,path,body=None,method=None):
  root=urlparse(path).path;query=parse_qs(urlparse(path).query)
  if root=='/vpcs' and query.get('router:external')==['true']:return {'vpcs':[{'id':'external'}]}
  kinds={'/vpcs':'vpc','/vpcsubnets':'vpcsubnet','/internetgateways':'internetgateway','/security-groups':'security_group','/security-group-rules':'security_group_rule','/floatingips':'floatingip'}
  if root=='/security-group-ports':return {'security_group_ports':[{'id':'port1','device_id':self.cloud['servers'][0]['id']}]}
  if '/attach_gateway' in root:self.cloud['gateway']=body['gateway_id'];return {}
  if root.startswith('/vpcsubnets/'):
   x=self.cloud['/vpcsubnets'][0];return {'vpcsubnet':{**x,'routingtable':{'id':'rt1','gateway_id':self.cloud.get('gateway')}}}
  if root.startswith('/security-groups/'):return {'security_group':{**self.cloud['/security-groups'][0],'security_group_rules':self.cloud.get('/security-group-rules',[])}}
  kind=kinds[root]
  if body:
   x={**body[kind],'id':kind+secrets.token_hex(5)}
   if root=='/security-groups':x['security_group_rules']=[]
   if root=='/floatingips':x['floating_ip_address']='1.2.3.4'
   self.cloud.setdefault(root,[]).append(x);return {kind:x}
  values=self.cloud.get(root,[])
  if query.get('name'):values=[x for x in values if x.get('name')==query['name'][0]]
  return {root.strip('/').replace('-','_'):values}

class ServerTests(unittest.TestCase):
 setUp=fixture.BatchTests.setUp
 tearDown=fixture.BatchTests.tearDown
 post=fixture.BatchTests.post
 create=fixture.BatchTests.create
 action=fixture.BatchTests.action
 def prepare(self,count=2,existing=False):
  Infra.clouds={};Infra.fail_server=False;Infra.hook=None;ServerAPI.added=[];self.create()
  if existing:Infra.clouds['project01']={'servers':[{'id':'existing01','name':'gju-nhn-s01-web','status':'ACTIVE','metadata':{'original':'keep'}}]}
  roster='\n'.join(f's{n:02},Student {n},student{n}@example.com' for n in range(1,count+1))
  r=self.post('/nhn/batches/'+self.b['id']+'/servers/plan',{'last':str(count),'roster':roster});self.assertEqual(r.status_code,303)
  self.api_patch=patch('cloudops.nhn_servers.API',ServerAPI);self.api_patch.start();self.addCleanup(self.api_patch.stop)
  self.infra_patch=patch('cloudops.nhn_servers.Infra',Infra);self.infra_patch.start();self.addCleanup(self.infra_patch.stop)
  template={'source_server':'source','image':'image1','flavor':'flavor1','flavor_name':'m2.c1m2','size':20,'volume_type':'HDD','az':'kr-pub-a','rules':[{'direction':'ingress','ethertype':'IPv4','protocol':'tcp','port_range_min':22,'port_range_max':22,'remote_ip_prefix':'61.84.192.32/32'},{'direction':'ingress','ethertype':'IPv4','protocol':'tcp','port_range_min':80,'port_range_max':80,'remote_ip_prefix':'0.0.0.0/0'}]}
  self.tmpl=patch('cloudops.nhn_servers.Servers.template',side_effect=lambda api,b,cfg:(template,api.projects(cfg['org']),api.products()));self.tmpl.start();self.addCleanup(self.tmpl.stop)
  self.app.state.worker.run_one();self.servers=Servers(self.db,self.vault,self.app.state.worker.stop)
 def test_server_plan_creates_no_cloud_resources(self):
  self.prepare();self.assertFalse(Infra.clouds);self.assertEqual(self.db.one('SELECT status FROM nhn_bootstrap')['status'],'PLANNED');self.assertEqual(self.db.one('SELECT COUNT(*) n FROM nhn_items')['n'],2)
 def test_create_and_retry_do_not_duplicate_servers(self):
  self.prepare();self.servers.apply(self.b['id']);self.assertEqual(sum(len(x.get('servers',[])) for x in Infra.clouds.values()),2);self.servers.apply(self.b['id']);self.assertEqual(sum(len(x.get('servers',[])) for x in Infra.clouds.values()),2);self.assertEqual(self.db.one('SELECT COUNT(*) n FROM resources')['n'],2)
 def test_key_and_write_intent_durable_before_server_request(self):
  self.prepare()
  def check():
   raw=self.db.one('SELECT state FROM nhn_bootstrap')['state'];state=self.vault.open(raw,'nhn-servers:'+self.b['id']);active=[x for x in state['students'].values() if x.get('key_material') and x['journal'].get('server',{}).get('intent')];self.assertTrue(active);self.assertTrue(active[0]['key_material']['private'].startswith('-----BEGIN RSA PRIVATE KEY-----'))
  Infra.hook=check;self.servers.apply(self.b['id'])
 def test_lost_server_response_reconciles_existing_metadata(self):
  self.prepare();Infra.fail_server=True
  with self.assertRaises(CloudError):self.servers.apply(self.b['id'])
  self.servers.apply(self.b['id']);self.assertEqual(sum(len(x.get('servers',[])) for x in Infra.clouds.values()),2)
 def test_missing_project_is_created_once(self):
  self.prepare(3);self.servers.apply(self.b['id']);self.assertEqual(len(ServerAPI.added),1);self.assertEqual(ServerAPI.added[0]['projectName'],'TBIT_Edu01_Pro03');self.servers.apply(self.b['id']);self.assertEqual(len(ServerAPI.added),1)
 def test_existing_pilot_preserved_without_rekey(self):
  self.prepare(existing=True);self.servers.apply(self.b['id']);self.assertEqual(Infra.clouds['project01']['servers'][0]['id'],'existing01');self.assertNotIn('keys',Infra.clouds['project01']);self.assertEqual(len(Infra.clouds['project01']['servers']),1)
 def test_bootstrap_auth_and_duplicate_roster(self):
  self.prepare();self.assertEqual(self.post('/nhn/batches/'+self.b['id']+'/servers/apply',{'confirm':'class-batch','password':'wrong'}).status_code,403)
  r=self.post('/nhn/batches/'+self.b['id']+'/servers/plan',{'last':'2','roster':'s01,One,one@example.com\ns01,Two,two@example.com'});self.assertEqual(r.status_code,400)
 def test_student_download_contains_only_own_key(self):
  self.prepare();self.servers.apply(self.b['id']);r=self.post('/nhn/batches/'+self.b['id']+'/servers/student',{'student':'s01','password':'A-long-test-password!'});self.assertEqual(r.status_code,200)
  import zipfile,io
  z=zipfile.ZipFile(io.BytesIO(r.content));self.assertTrue(all(x.startswith('s01/') for x in z.namelist()));self.assertEqual(len([x for x in z.namelist() if x.endswith('.pem')]),1);self.assertNotIn(b'SECRET-UAK',r.content)
 def test_key_material_is_parseable_and_private(self):
  data=generate_key();key=serialization.load_pem_private_key(data['private'].encode(),password=None);self.assertEqual(key.key_size,2048);self.assertTrue(data['public'].startswith('ssh-rsa '))
if __name__=='__main__':unittest.main()

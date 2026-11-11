"""Create only missing NHN training servers, with encrypted write-ahead state.
Existing servers, LMS containers, IAM identities and existing network policies are untouched.
"""
import base64,ipaddress,json,secrets,time
from urllib.parse import urlencode
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from .nhn_batch import API,Batch,CloudError,ident,rows,safe_error

class Infra:
 def __init__(self,api,product):self.api=api;self.product=product;self.compute=api.compute(product['externalId']);self.compute.auth()
 def close(self):self.compute.http.close()
 def net(self,path,body=None,method=None):
  url=f'https://{self.api.region.lower()}-api-network-infrastructure.nhncloudservice.com/v2.0'+path
  r=self.api.http.request(method or ('POST' if body is not None else 'GET'),url,headers={'X-Auth-Token':self.compute.token},json=body)
  if not r.is_success:raise CloudError('NHN 네트워크 '+path.split('?')[0]+' HTTP '+str(r.status_code))
  return r.json() if r.content else {}
 def volume(self,id):
  r=self.api.http.get(f'https://{self.api.region.lower()}-api-block-storage-infrastructure.nhncloudservice.com/v2/{ident(self.product["externalId"])}/volumes/{ident(id)}',headers={'X-Auth-Token':self.compute.token})
  if not r.is_success:raise CloudError('템플릿 루트 디스크 조회 실패 HTTP '+str(r.status_code))
  return r.json()['volume']
 def wait_server(self,id,stop):
  for _ in range(180):
   s=self.compute.request('/servers/'+ident(id))['server']
   if s['status']=='ACTIVE':return s
   if s['status'] not in ['BUILD']:raise CloudError('서버 생성 상태 확인 필요: '+s['status'])
   if stop.wait(5):raise CloudError('서버 종료로 대기 중단')
  raise CloudError('서버 생성 대기 시간 초과')

def generate_key():
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
 return {'private':key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.TraditionalOpenSSL,serialization.NoEncryption()).decode(),'public':key.public_key().public_bytes(serialization.Encoding.OpenSSH,serialization.PublicFormat.OpenSSH).decode()}

class Servers:
 def __init__(self,store,vault,stop):self.store=store;self.vault=vault;self.stop=stop;self.batch=Batch(store,vault,stop)
 def save(self,id,state,status='PLANNED'):
  self.store.execute('UPDATE nhn_bootstrap SET state=?,status=?,updated=? WHERE batch_id=?',(self.vault.seal(state,'nhn-servers:'+id),status,time.time(),id))
 def load(self,id):
  b,cfg,secret=self.batch.load(id);boot=self.store.one('SELECT * FROM nhn_bootstrap WHERE batch_id=?',(id,))
  if not boot:raise CloudError('서버 준비 계획이 없습니다.')
  return b,cfg,secret,boot,json.loads(boot['config'])
 def template(self,api,b,cfg):
  c=self.store.one('SELECT * FROM connections WHERE id=?',(b['connection_id'],));products=api.products();projects=api.projects(cfg['org']);anchor=[p for p in projects if p['projectName']==cfg['project_prefix']+'01']
  if len(anchor)!=1:raise CloudError('템플릿 Pro01 프로젝트를 찾을 수 없습니다.')
  product=api.product(anchor[0]['projectId'],products['instance'])
  if product['externalId']!=c['account']:raise CloudError('템플릿 연결은 Pro01이어야 합니다.')
  infra=Infra(api,product)
  try:
   items=infra.compute.inventory();matches=[x for x in items if x['name']==cfg['server_prefix']+'01-web']
   if len(matches)!=1:raise CloudError('Pro01 템플릿 서버를 하나로 확인할 수 없습니다.')
   s=infra.compute.request('/servers/'+ident(matches[0]['remote_id']))['server'];volumes=s.get('os-extended-volumes:volumes_attached',[])
   if s['status']!='ACTIVE' or len(volumes)!=1:raise CloudError('템플릿은 실행 중인 단일 루트 디스크 서버여야 합니다.')
   v=infra.volume(volumes[0]['id']);image=s.get('image',{}).get('id') or v.get('volume_image_metadata',{}).get('image_id')
   if not image or v['size']!=20:raise CloudError('20GB 이미지 기반 템플릿 확인 실패')
   groups=rows(infra.net('/security-groups'),'security_groups');names={g['name'] for g in s.get('security_groups',[])};selected=[g for g in groups if g['name'] in names]
   if not selected:raise CloudError('템플릿 보안 그룹 조회 실패')
   rules=[]
   for g in selected:
    for r in g['security_group_rules']:
     if r.get('remote_group_id'):raise CloudError('원격 그룹을 참조하는 템플릿 규칙은 자동 복제하지 않습니다.')
     rule={k:r[k] for k in ['direction','ethertype','protocol','port_range_min','port_range_max','remote_ip_prefix'] if r.get(k) is not None}
     if rule['direction']=='ingress' and not (rule.get('protocol')=='tcp' and rule.get('port_range_min')==rule.get('port_range_max') and rule.get('port_range_min') in [22,80]):raise CloudError('템플릿 수신 규칙은 TCP 22/80만 허용합니다.')
     if rule['direction']=='ingress' and rule.get('port_range_min')==22 and ipaddress.ip_network(rule.get('remote_ip_prefix','0.0.0.0/0')).prefixlen!=32:raise CloudError('템플릿 SSH는 단일 IP/32 허용 상태여야 합니다.')
     if rule not in rules:rules.append(rule)
   if not any(r.get('port_range_min')==22 and r.get('direction')=='ingress' for r in rules):raise CloudError('템플릿에 운영자 SSH /32 규칙이 필요합니다.')
   external=rows(infra.net('/vpcs?router:external=true'),'vpcs')
   public=[x for x in external if x.get('name')=='Public Network']
   if len(external)!=1 and len(public)!=1:raise CloudError('템플릿 리전의 Public Network 식별 실패')
   external_id=(public or external)[0]['id']
   flavor=infra.compute.request('/flavors/'+ident(s['flavor']['id']))['flavor']
   return {'source_server':s['id'],'image':image,'flavor':s['flavor']['id'],'flavor_name':flavor['name'],'volume_type':v['volume_type'],'size':20,'az':s['OS-EXT-AZ:availability_zone'],'rules':rules,'external_id':external_id},projects,products
  finally:infra.close()
 def plan(self,id):
  b,cfg,secret,boot,opts=self.load(id)
  if boot['state']:
   old=self.vault.open(boot['state'],'nhn-servers:'+id)
   if any(x.get('journal') for x in old.get('students',{}).values()):raise CloudError('생성 이력이 있어 서버 계획을 덮어쓸 수 없습니다. 재시도를 사용하세요.')
  api=API(secret,cfg['region'])
  try:
   template,projects,products=self.template(api,b,cfg);state={'template':template,'products':products,'students':{},'planned':time.time()}
   for n in range(cfg['first'],cfg['last']+1):
    code=f's{n:02}';name=cfg['project_prefix']+f'{n:02}';matches=[p for p in projects if p['projectName']==name]
    if len(matches)>1 or (matches and matches[0].get('projectStatusCode')!='STABLE'):raise CloudError('대상 프로젝트 상태·중복 확인 필요: '+name)
    project=matches[0] if matches else None;server=None
    if project:
     raw=api.core(f'/v1/projects/{ident(project["projectId"])}/products/{products["instance"]}').get('product',{})
     if raw.get('statusCode')=='STABLE':
      infra=Infra(api,raw)
      try:
       found=[s for s in infra.compute.inventory() if s['name']==cfg['server_prefix']+f'{n:02}-web']
       if len(found)>1:raise CloudError('동일 이름 서버 중복')
       server=found[0] if found else None
      finally:infra.close()
    summary={'project':name,'server_name':cfg['server_prefix']+f'{n:02}-web','container':cfg['lab_prefix']+'-'+code+'-files','db_name':cfg['lab_prefix']+'-'+code+'-db','db':cfg['db'],'owner':opts['roster'].get(code,{}).get('name',code),'ip':server['ip'] if server else '', 'server_action':'기존 서버 유지' if server else '서버·개별 키·VPC·IP 생성','flavor':template['flavor_name']}
    state['students'][code]={'project':project,'existing_server':server,'summary':summary,'journal':{},'person':opts['roster'].get(code,{})}
    self.batch.report(id,code,summary,'SERVER_PLANNED',summary['server_action']+' · '+template['flavor_name']+' · 20GB')
   self.save(id,state)
  finally:api.close()
 def apply(self,id):
  b,cfg,secret,boot,opts=self.load(id)
  if not boot['state']:raise CloudError('서버 계획을 먼저 조회하세요.')
  state=self.vault.open(boot['state'],'nhn-servers:'+id)
  if boot['status']=='CLEANED':raise CloudError('정리된 서버 계획입니다.')
  if time.time()-state['planned']>3600 and not any(x['journal'] for x in state['students'].values()):raise CloudError('서버 계획이 1시간 지났습니다. 다시 조회하세요.')
  api=API(secret,cfg['region']);failures=0
  try:
   for code,item in state['students'].items():
    if item.get('ready'):continue
    try:
     self.student(api,b,cfg,state,code,item);self.register(b,cfg,secret,code,item);item['ready']=True;self.save(id,state,'RUNNING');self.batch.report(id,code,item['summary'],'SERVER_READY','서버·개별 키·IP 준비 완료 · SSH 허용 IP는 템플릿과 동일')
    except Exception as error:failures+=1;self.save(id,state,'RUNNING');self.batch.report(id,code,item['summary'],'SERVER_FAILED',safe_error(error))
   self.save(id,state,'FAILED' if failures else 'READY')
  finally:api.close()
  if failures:raise CloudError(f'{failures}명 서버 준비 확인 필요. 성공한 학생은 재시도에서 건너뜁니다.')
 def register(self,b,cfg,secret,code,item):
  s=item['summary'];now=time.time()
  with self.store.connect() as db:
   matches=db.execute("SELECT id FROM connections WHERE provider='NHN' AND account=? AND region=?",(item['tenant'],cfg['region'])).fetchall()
   if len(matches)>1:raise CloudError('학생 테넌트 연결이 중복됩니다.')
   if matches:cid=matches[0]['id']
   else:
    cid=secrets.token_hex(16);db.execute("INSERT INTO connections(id,name,provider,region,account,secret,writable,last_sync) VALUES(?,?,'NHN',?,?,?,0,?)",(cid,s['project'],cfg['region'],item['tenant'],self.vault.seal({k:secret[k] for k in ['username','api_password']},'connection:'+cid),now))
   old=db.execute('SELECT event_id FROM resources WHERE connection_id=? AND remote_id=?',(cid,item['server_id'])).fetchone()
   if old and old['event_id'] and old['event_id']!=b['event_id']:raise CloudError('다른 교육에 배정된 서버는 자동 재배정하지 않습니다.')
   db.execute('INSERT INTO resources(id,connection_id,remote_id,name,state,ip,flavor,event_id,owner,seen) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(connection_id,remote_id) DO UPDATE SET event_id=excluded.event_id,owner=excluded.owner',(secrets.token_hex(16),cid,item['server_id'],s['server_name'],'ACTIVE',s['ip'],s.get('flavor',''),b['event_id'],code+' · '+item['person'].get('name',''),now))
 def student(self,api,b,cfg,state,code,item):
  j=item['journal'];summary=item['summary'];t=state['template'];marker='tbit-ops-servers:'+b['id']+':'+code;save=lambda:self.save(b['id'],state,'RUNNING')
  def once(key,lookup,create,valid=lambda x:True):
   found=lookup()
   if len(found)>1:raise CloudError('동일 이름 자원 중복: '+key)
   if found:
    if key not in j or not valid(found[0]):raise CloudError('기존 자원 소유권 확인 필요: '+key)
    j[key]['id']=found[0]['id'];save();return found[0]
   if key in j:raise CloudError('이전 생성 결과가 불명확합니다: '+key)
   j[key]={'intent':True};save();x=create();j[key]['id']=x['id'];save();return x
  project=item['project']
  if not project:
   project=once('project',lambda:[{**p,'id':p['projectId']} for p in api.projects(cfg['org']) if p['projectName']==summary['project']],lambda:(lambda p:{**p,'id':p['projectId']})(api.core(f'/v1/organizations/{ident(cfg["org"])}/projects',body={'projectName':summary['project'],'description':marker})['project']),lambda p:p.get('description')==marker)
   if not project.get('id'):project['id']=project['projectId'];j['project']['id']=project['id'];save()
   item['project']=project;save()
  pid=ident(project['projectId'])
  for service in ['instance','objectstorage']+(['rdsformysql'] if cfg['db'] else []):
   api.core(f'/v1/projects/{pid}/products/{state["products"][service]}/enable',enable=True)
  product=api.product(pid,state['products']['instance']);item['tenant']=product['externalId'];save();infra=Infra(api,product)
  try:
   # A previously existing server is never rebuilt or re-keyed.
   existing=[x for x in infra.compute.inventory() if x['name']==summary['server_name']]
   if item['existing_server']:
    if len(existing)!=1 or existing[0]['remote_id']!=item['existing_server']['remote_id'] or existing[0]['state']!='ACTIVE':raise CloudError('기존 서버 상태 변경: 자동 변경하지 않습니다.')
    summary['ip']=existing[0]['ip'];item['server_id']=existing[0]['remote_id'];return
   suffix=b['id'][:6];stem=cfg['lab_prefix']+'-'+code+'-'+suffix
   vpc=once('vpc',lambda:rows(infra.net('/vpcs?'+urlencode({'name':stem+'-vpc'})),'vpcs'),lambda:infra.net('/vpcs',{'vpc':{'name':stem+'-vpc','cidrv4':f'10.{40+int(code[1:])}.0.0/16'}})['vpc'])
   subnet=once('subnet',lambda:rows(infra.net('/vpcsubnets?'+urlencode({'name':stem+'-web'})),'vpcsubnets'),lambda:infra.net('/vpcsubnets',{'vpcsubnet':{'name':stem+'-web','vpc_id':vpc['id'],'cidr':f'10.{40+int(code[1:])}.1.0/24'}})['vpcsubnet'],lambda x:x['vpc_id']==vpc['id'])
   external=rows(infra.net('/vpcs?router:external=true'),'vpcs')
   if t.get('external_id'):external=[x for x in external if x['id']==t['external_id']]
   if len(external)!=1:raise CloudError('Public Network를 하나로 확정할 수 없습니다.')
   igw=once('igw',lambda:rows(infra.net('/internetgateways?'+urlencode({'name':stem+'-igw'})),'internetgateways'),lambda:infra.net('/internetgateways',{'internetgateway':{'name':stem+'-igw','external_network_id':external[0]['id']}})['internetgateway'])
   detail=infra.net('/vpcsubnets/'+ident(subnet['id']))['vpcsubnet'];rt=detail['routingtable']
   if rt.get('gateway_id') and rt['gateway_id']!=igw['id']:raise CloudError('라우팅 테이블에 다른 게이트웨이가 연결되었습니다.')
   if rt.get('gateway_id')!=igw['id']:infra.net('/routingtables/'+ident(rt['id'])+'/attach_gateway',{'gateway_id':igw['id']},'PUT')
   sg=once('security',lambda:rows(infra.net('/security-groups?'+urlencode({'name':stem+'-sg'})),'security_groups'),lambda:infra.net('/security-groups',{'security_group':{'name':stem+'-sg','description':marker}})['security_group'],lambda x:x.get('description')==marker)
   actual=infra.net('/security-groups/'+ident(sg['id']))['security_group']['security_group_rules']
   for index,rule in enumerate(t['rules']):
    def same(r):
     normalized=dict(r)
     if not normalized.get('remote_ip_prefix'):normalized['remote_ip_prefix']='::/0' if normalized.get('ethertype')=='IPv6' else '0.0.0.0/0'
     expected=dict(rule)
     if not expected.get('remote_ip_prefix'):expected['remote_ip_prefix']='::/0' if expected.get('ethertype')=='IPv6' else '0.0.0.0/0'
     return all(normalized.get(k)==v for k,v in expected.items())
    if any(same(r) for r in actual):continue
    key='rule'+str(index)
    if key in j:raise CloudError('보안 규칙 생성 결과 확인 필요')
    j[key]={'intent':True};save();created=infra.net('/security-group-rules',{'security_group_rule':{**rule,'security_group_id':sg['id'],'description':marker}})['security_group_rule'];j[key]['id']=created['id'];save()
   if 'key_material' not in item:item['key_material']=generate_key();save()
   keyname=stem+'-key';keys=rows(infra.compute.request('/os-keypairs'),'keypairs');matching=[k['keypair'] for k in keys if k['keypair']['name']==keyname]
   if matching:
    if matching[0]['public_key'].split()[:2]!=item['key_material']['public'].split()[:2]:raise CloudError('키페어 공개키가 다릅니다.')
   else:
    if 'key' in j:raise CloudError('키페어 등록 응답 확인 필요')
    j['key']={'intent':True};save();infra.compute.request('/os-keypairs',{'keypair':{'name':keyname,'public_key':item['key_material']['public']}});j['key']['registered']=True;save()
   def server_lookup():
    return [{**infra.compute.request('/servers/'+ident(x['remote_id']))['server']} for x in infra.compute.inventory() if x['name']==summary['server_name']]
   server=once('server',server_lookup,lambda:infra.compute.request('/servers',{'server':{'name':summary['server_name'],'imageRef':t['image'],'flavorRef':t['flavor'],'key_name':keyname,'availability_zone':t['az'],'metadata':{'tbit_ops':marker},'networks':[{'subnet':subnet['id']}],'block_device_mapping_v2':[{'source_type':'image','uuid':t['image'],'boot_index':0,'volume_size':20,'volume_type':t['volume_type'],'destination_type':'volume','delete_on_termination':True}],'security_groups':[{'name':sg['name']}],'min_count':1,'max_count':1}})['server'],lambda x:x.get('metadata',{}).get('tbit_ops')==marker)
   infra.wait_server(server['id'],self.stop)
   ports=rows(infra.net('/security-group-ports?'+urlencode({'security_group_id':sg['id']})),'security_group_ports');ports=[p for p in ports if p['device_id']==server['id']]
   if len(ports)!=1:raise CloudError('서버 네트워크 포트를 하나로 확인할 수 없습니다.')
   fip=once('floating',lambda:[x for x in rows(infra.net('/floatingips'),'floatingips') if x.get('label')==stem],lambda:infra.net('/floatingips',{'floatingip':{'floating_network_id':external[0]['id'],'port_id':ports[0]['id'],'label':stem}})['floatingip'],lambda x:x.get('port_id')==ports[0]['id'])
   item['key_name']=keyname;summary['ip']=fip['floating_ip_address'];item['server_id']=server['id'];save()
  finally:infra.close()

"""NHN project-scoped training preparation. Cloud secrets never enter public plans.

API references and operating/recovery rules: docs/nhn-batch.md.
"""
import base64,ipaddress,json,re,secrets,time
from urllib.parse import urlparse
import httpx
from .providers import CloudError,NHN

AUTH='https://oauth.api.nhncloudservice.com'
CORE='https://core.api.nhncloudservice.com'

def ident(value):
 if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',value):raise CloudError('NHN 식별자 형식 오류')
 return value

def project_target(cfg,n):
 for scope in cfg.get('project_scopes',[]):
  if scope['first']<=n<=scope['last']:return scope['org'],scope['prefix']+f'{n:02}'
 return cfg['org'],cfg['project_prefix']+f'{n:02}'

def scoped_projects(api,cfg):
 orgs={cfg['org']}|{x['org'] for x in cfg.get('project_scopes',[])}
 return {org:api.projects(org) for org in orgs}

def rows(data,key):
 value=data.get(key)
 if not isinstance(value,list):raise CloudError('NHN 목록 응답 형식 오류: '+key)
 return value

def safe_error(error):
 return str(error) if isinstance(error,CloudError) else '연결·권한·API 응답 확인 필요 (원문과 비밀정보는 기록하지 않음)'

class API:
 def __init__(self,credentials,region):
  self.secret=credentials;self.region=region;self.http=httpx.Client(timeout=30,follow_redirects=False);self.token=None
 def close(self):
  if self.token:
   try:self.http.post(AUTH+'/oauth2/token/revoke',headers={'Authorization':self.basic()},data={'token':self.token})
   except Exception:pass
  self.http.close()
 def basic(self):return 'Basic '+base64.b64encode((self.secret['access_key']+':'+self.secret['secret_key']).encode()).decode()
 def response(self,r,label):
  if not r.is_success:raise CloudError(label+' HTTP '+str(r.status_code)+' · 운영자 키·서비스 활성화·권한 확인')
  data=r.json() if r.content else {}
  if data.get('header',{}).get('isSuccessful') is not True:
   code=data.get('header',{}).get('resultCode');hint=f' · resultCode={code}' if type(code) is int else ''
   raise CloudError(label+' 응답 실패'+hint+' · 서비스 활성화·권한 확인')
  return data
 def core(self,path,enable=False,body=None):
  if not self.token:
   r=self.http.post(AUTH+'/oauth2/token/create',headers={'Authorization':self.basic()},data={'grant_type':'client_credentials'})
   if not r.is_success:raise CloudError('운영자 User Access Key 인증 실패 HTTP '+str(r.status_code))
   data=r.json()
   if data.get('token_type','').lower()!='bearer' or not data.get('access_token'):raise CloudError('운영자 Bearer 토큰 응답 오류')
   self.token=data['access_token']
  r=self.http.request('POST' if enable or body is not None else 'GET',CORE+path,headers={'x-nhn-authorization':'Bearer '+self.token},**({'json':body} if body is not None else {}))
  if enable and r.is_success and r.json().get('header',{}).get('resultCode')==13002:return {'already_enabled':True}
  label='서비스 활성화' if enable else ('서비스 카탈로그 조회' if path.startswith('/v1/product-uis/') else '조직 프로젝트 목록 조회' if '/organizations/' in path else '프로젝트 서비스 정보 조회')
  return self.response(r,label)
 def projects(self,org):
  result=[];seen=set()
  for page in range(1,101):
   data=self.core(f'/v1/organizations/{ident(org)}/projects?limit=20&page={page}')
   for p in rows(data,'projectList'):
    if p.get('projectId') in seen or p.get('orgId')!=org:raise CloudError('프로젝트 중복 또는 조직 불일치')
    seen.add(p['projectId']);result.append(p)
   total=data.get('totalCount',data.get('paging',{}).get('totalCount'))
   if type(total)!=int or total<0:raise CloudError('프로젝트 페이지 응답 오류')
   if len(result)==total:return result
   if not data['projectList'] or len(result)>total:break
  raise CloudError('프로젝트 페이지 조회가 완료되지 않음')
 def products(self):
  found={}
  def walk(items):
   for item in items:
    if item is None:continue
    if not isinstance(item,dict):raise CloudError('서비스 카탈로그 항목 형식 오류')
    name=re.sub(r'\s+','',item.get('productUiName','')).lower()
    if name in ['instance','objectstorage','rdsformysql'] and item.get('productId'):found.setdefault(name,set()).add(ident(item['productId']))
    walk(item.get('children') or [])
  walk(rows(self.core('/v1/product-uis/hierarchy?productUiType=PROJECT'),'productUiList'))
  if any(len(found.get(k,set()))!=1 for k in ['instance','objectstorage','rdsformysql']):raise CloudError('서비스 카탈로그 식별 실패: 자동으로 서비스 ID를 추측하지 않습니다.')
  return {k:next(iter(v)) for k,v in found.items()}
 def product(self,project,product):
  p=self.core(f'/v1/projects/{ident(project)}/products/{ident(product)}').get('product',{})
  if p.get('projectId')!=project or p.get('productId')!=product or p.get('statusCode')!='STABLE' or p.get('productStatusCode')!='STABLE' or not p.get('appKey'):raise CloudError('프로젝트 서비스가 활성화되지 않았거나 조회 권한이 없습니다.')
  return p
 def compute(self,tenant):return NHN({'account':tenant,'region':self.region},self.secret)
 def storage_auth(self,product):
  tenant=product.get('externalId','')
  if not re.fullmatch('[a-zA-Z0-9-]{16,64}',tenant):raise CloudError('Object Storage 전용 Tenant ID를 조회하지 못했습니다.')
  r=self.http.post('https://api-identity-infrastructure.nhncloudservice.com/v2.0/tokens',json={'auth':{'tenantId':tenant,'passwordCredentials':{'username':self.secret['username'],'password':self.secret['api_password']}}})
  if not r.is_success:raise CloudError('Object Storage 인증 실패 HTTP '+str(r.status_code))
  access=r.json()['access']
  if access['token']['tenant']['id']!=tenant:raise CloudError('Object Storage 테넌트 불일치')
  expected=f'https://{self.region.lower()}-api-object-storage.nhncloudservice.com/v1/AUTH_{tenant}'
  matches=[e['publicURL'].rstrip('/') for s in access['serviceCatalog'] if s['type']=='object-store' for e in s['endpoints'] if e.get('region')==self.region]
  if expected not in matches:raise CloudError('Object Storage 리전·엔드포인트 검증 실패')
  return expected,access['token']['id']
 def container(self,product,name,method='HEAD',marker=None):
  endpoint,token=self.storage_auth(product);headers={'X-Auth-Token':token}
  if method=='PUT':headers.update({'X-Storage-Policy':'Standard','X-Container-Meta-Tbit-Ops':marker,'X-Container-Read':'','X-Container-Write':''})
  r=self.http.request(method,endpoint+'/'+ident(name),headers=headers)
  if method=='HEAD' and r.status_code==404:return None
  if not r.is_success:raise CloudError('컨테이너 '+method+' 실패 HTTP '+str(r.status_code))
  if method=='PUT' and r.status_code!=201:raise CloudError('동일 이름 컨테이너 발견: 소유권 확인 후 다시 조회하세요.')
  return {'marker':r.headers.get('X-Container-Meta-Tbit-Ops',''),'public':bool(r.headers.get('X-Container-Read','') or r.headers.get('X-Container-Write','')),'count':int(r.headers.get('X-Container-Object-Count',0))}
 def rds(self,product,path,body=None,method=None):
  host={'KR1':'kr1','KR2':'kr2','JP1':'jp1'}.get(self.region)
  if not host:raise CloudError('RDS 지원 리전은 KR1/KR2/JP1입니다.')
  headers={'X-TC-APP-KEY':product['appKey'],'X-TC-AUTHENTICATION-ID':self.secret['access_key'],'X-TC-AUTHENTICATION-SECRET':self.secret['secret_key']}
  r=self.http.request(method or ('POST' if body is not None else 'GET'),f'https://{host}-rds-mysql.api.nhncloudservice.com/v3.0'+path,headers=headers,json=body)
  if method=='DELETE' and r.is_success and not r.content:return {}
  return self.response(r,'RDS '+path.split('/')[1])
 def wait(self,product,job,stop):
  jid=ident(job['jobId']);deadline=time.monotonic()+2400
  while time.monotonic()<deadline:
   data=self.rds(product,'/jobs/'+jid);status=data.get('jobStatus')
   if status=='COMPLETED':return
   if status in ['FAILED','ERROR','CANCELED','INTERRUPTED','FAIL_TO_READY','FAIL_TO_REGISTER','COMPLETED_WITH_ERROR','CANNOT_PROGRESS','DELETED']:raise CloudError('NHN 비동기 작업 실패: '+str(status))
   if stop.wait(5):raise CloudError('서버 종료로 대기 중단: 상태 확인 후 재시도')
  raise CloudError('NHN 비동기 작업 대기 시간 초과: 상태 확인 후 재시도')

def choose_server(api,product,name):
 tenant=product.get('externalId','')
 if not re.fullmatch('[a-zA-Z0-9-]{16,64}',tenant):raise CloudError('인프라 Tenant ID 조회 실패')
 client=api.compute(tenant)
 try:
  servers=client.inventory();matches=[s for s in servers if s['name']==name]
  if len(matches)!=1:raise CloudError('기존 학생 서버가 없거나 이름이 중복됨: '+name)
  server=client.request('/servers/'+ident(matches[0]['remote_id']))['server']
  if server.get('status')!='ACTIVE':raise CloudError('학생 서버가 ACTIVE가 아닙니다.')
  ips=[a['addr'] for group in server.get('addresses',{}).values() for a in group if ipaddress.ip_address(a['addr']).version==4 and any(ipaddress.ip_address(a['addr']) in ipaddress.ip_network(cidr) for cidr in ['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'])]
  ips=list(dict.fromkeys(ips))
  if len(ips)!=1:raise CloudError('서버 상세에서 사설 IPv4를 하나로 확정할 수 없습니다.')
  return {'server_id':server['id'],'server_name':server['name'],'ip':matches[0]['ip'],'private_ip':ips[0],'subnet_id':'','az':server['OS-EXT-AZ:availability_zone'],'tenant':tenant}
 finally:client.http.close()

def resolve_subnet(api,product,server):
 subnets=rows(api.rds(product,'/network/subnets'),'subnets')
 matches=[x for x in subnets if ipaddress.ip_address(server['private_ip']) in ipaddress.ip_network(x['subnetCidr'])]
 if len(matches)!=1:raise CloudError('학생 서버 IP와 일치하는 RDS 서브넷을 하나로 확정하지 못했습니다.')
 return matches[0]

class Batch:
 def __init__(self,store,vault,stop):self.store=store;self.vault=vault;self.stop=stop
 def load(self,id):
  b=self.store.one('SELECT * FROM nhn_batches WHERE id=?',(id,))
  if not b:raise CloudError('NHN 일괄 계획을 찾을 수 없습니다.')
  cfg=json.loads(b['config']);c=self.store.one('SELECT revision FROM connections WHERE id=?',(b['connection_id'],))
  if not c or c['revision']!=cfg['connection_revision']:raise CloudError('연결 인증정보가 변경되었습니다. 이 계획의 인증정보를 갱신하세요.')
  return b,cfg,self.vault.open(b['secret'],'nhn-batch:'+id)
 def save(self,id,state):self.store.execute('UPDATE nhn_batches SET state=? WHERE id=?',(self.vault.seal(state,'nhn-state:'+id),id))
 def report(self,id,student,summary,status,message):
  self.store.execute('INSERT INTO nhn_items(batch_id,student,summary,status,message,updated) VALUES(?,?,?,?,?,?) ON CONFLICT(batch_id,student) DO UPDATE SET summary=excluded.summary,status=excluded.status,message=excluded.message,updated=excluded.updated',(id,student,json.dumps(summary),status,message,time.time()))
 def enable(self,id):
  b,cfg,secret=self.load(id)
  if b['state'] and any(x.get('journal') for x in self.vault.open(b['state'],'nhn-state:'+id).values()):raise CloudError('자원 생성 후에는 활성화 대신 실패 항목 재시도를 사용하세요.')
  api=API(secret,cfg['region']);failures=0
  try:
   projects=scoped_projects(api,cfg);products=api.products()
   for n in range(cfg['first'],cfg['last']+1):
    org,project_name=project_target(cfg,n);student=f's{n:02}';summary={'project':project_name,'server_name':cfg['server_prefix']+f'{n:02}-web','container':cfg['lab_prefix']+'-'+student+'-files','db_name':cfg['lab_prefix']+'-'+student+'-db','db':cfg['db']}
    try:
     matches=[p for p in projects[org] if p['projectName']==summary['project'] and p.get('projectStatusCode')=='STABLE']
     if len(matches)!=1:raise CloudError('대상 프로젝트가 없거나 정상 상태가 아닙니다.')
     pid=ident(matches[0]['projectId'])
     for key in ['objectstorage']+(['rdsformysql'] if cfg['db'] else []):
      api.core(f'/v1/projects/{pid}/products/{products[key]}/enable',enable=True)
      api.product(pid,products[key])
     self.report(id,student,summary,'SERVICES_ENABLED','서비스 활성화 확인 완료 · 계획 다시 조회를 누르세요.')
    except Exception as error:failures+=1;self.report(id,student,summary,'BLOCKED',safe_error(error))
  finally:api.close()
  self.store.execute('UPDATE nhn_batches SET planned=NULL WHERE id=?',(id,))
  if failures:raise CloudError(f'{failures}개 프로젝트 서비스 활성화 확인 필요')
 def plan(self,id):
  b,cfg,secret=self.load(id);api=API(secret,cfg['region']);state={};failures=0
  try:
   projects=scoped_projects(api,cfg);products=api.products()
   for n in range(cfg['first'],cfg['last']+1):
    org,project_name=project_target(cfg,n);student=f's{n:02}';summary={'project':project_name,'server_name':cfg['server_prefix']+f'{n:02}-web','container':cfg['lab_prefix']+'-'+student+'-files','db_name':cfg['lab_prefix']+'-'+student+'-db','db':cfg['db']}
    try:
     selected=[p for p in projects[org] if p['projectName']==summary['project'] and p.get('projectStatusCode')=='STABLE']
     if len(selected)!=1:raise CloudError('정상 상태의 대상 프로젝트가 없거나 중복됩니다.')
     pid=ident(selected[0]['projectId']);compute=api.product(pid,products['instance']);storage=api.product(pid,products['objectstorage']);server=choose_server(api,compute,summary['server_name']);marker='tbit-ops:'+id+':'+pid
     container=api.container(storage,summary['container'])
     if container and container['public']:raise CloudError('같은 이름의 기존 컨테이너가 공개 상태입니다. 자동으로 정책을 변경하지 않습니다.')
     private={'existing_container':container,'project_id':pid,'compute':compute,'storage':storage,'server':server,'marker':marker}
     summary.update({'container_action':'기존 비공개 재사용' if container else '신규 생성','project_id':pid,**{k:v for k,v in server.items() if k!='tenant'}})
     if cfg['db']:
      rds=api.product(pid,products['rdsformysql']);existing=rows(api.rds(rds,'/db-instances'),'dbInstances')
      if any(x['dbInstanceName']==summary['db_name'] for x in existing):raise CloudError('같은 이름의 DB가 있습니다. 기존 DB는 변경하지 않습니다.')
      subnet=resolve_subnet(api,rds,server)
      if subnet.get('availableIpCount',0)<=0:raise CloudError('학생 서버 서브넷에 RDS 생성 가능한 IP가 없습니다.')
      server['subnet_id']=subnet['subnetId'];summary['subnet_id']=subnet['subnetId']
      if 'General SSD' not in rows(api.rds(rds,'/storage-types'),'storageTypes'):raise CloudError('리전에서 General SSD 스토리지를 지원하지 않습니다.')
      flavors=rows(api.rds(rds,'/db-flavors'),'dbFlavors')
      chosen_flavor=cfg['db_flavor']
      if not chosen_flavor:
       candidates=[x for x in flavors if type(x.get('ram')) in (int,float) and type(x.get('vcpus')) in (int,float) and x['ram']>0 and x['vcpus']>0]
       if not candidates:raise CloudError('사용 가능한 RDS 사양을 찾을 수 없습니다.')
       chosen_flavor=min(candidates,key=lambda x:(x['vcpus'],x['ram'],x['dbFlavorName']))['dbFlavorName']
      matches=[x for x in flavors if x['dbFlavorName']==chosen_flavor]
      if len(matches)!=1:raise CloudError('선택한 RDS 사양을 리전에서 찾을 수 없습니다: '+cfg['db_flavor'])
      versions=rows(api.rds(rds,'/db-versions'),'dbVersions')
      chosen_version=cfg['db_version']
      if not chosen_version:
       candidates=[x for x in versions if re.fullmatch('MYSQL_V[0-9]+',x.get('dbVersion','')) and re.search(r'8\.0\.',x.get('dbVersionName',''))]
       if not candidates:raise CloudError('MySQL 8.0 버전을 자동 선택하지 못했습니다. 버전 코드를 지정하세요.')
       chosen_version=max(candidates,key=lambda x:tuple(map(int,re.findall('[0-9]+',x['dbVersionName']))))['dbVersion']
      if not any(x['dbVersion']==chosen_version for x in versions):raise CloudError('선택한 DB 버전이 API 목록에 없습니다.')
      private.update({'rds':rds,'flavor_id':matches[0]['dbFlavorId']});summary.update({'db_flavor':chosen_flavor,'db_version':chosen_version,'db_gb':20})
     state[student]={'plan':private,'summary':summary,'journal':{},'password':secrets.token_urlsafe(24)}
     self.report(id,student,summary,'PLANNED','기존 서버 재사용 · 비공개 컨테이너'+(' · 사설 RDS 1대/20GB' if cfg['db'] else ''))
    except Exception as error:failures+=1;self.report(id,student,summary,'BLOCKED',safe_error(error))
   self.save(id,state);self.store.execute('UPDATE nhn_batches SET planned=? WHERE id=?',(time.time(),id))
  finally:api.close()
  if failures:raise CloudError(f'{failures}개 프로젝트 준비 조건 미충족. 생성된 클라우드 자원 없음. 차단 사유 확인 후 새 계획을 만드세요.')
 def ensure_rds(self,api,cfg,item,save):
  p=item['plan'];s=item['summary'];j=item['journal'];product=p['rds'];marker=p['marker']
  # Every mutation has a durable intent. Ambiguous POST results are never retried blindly.
  def ensure(kind,path,listkey,namekey,idkey,body):
   if j.get(kind,{}).get('job'):api.wait(product,{'jobId':j[kind]['job']},self.stop)
   matches=[x for x in rows(api.rds(product,path),listkey) if x.get(namekey)==body[namekey]]
   if len(matches)>1:raise CloudError('동일 이름 RDS 자원이 중복되어 중단했습니다.')
   if matches:
    x=matches[0]
    if x.get('description')!=marker or kind not in j:raise CloudError('기존 RDS 자원의 소유권을 확인할 수 없습니다.')
    j[kind]['id']=x[idkey];save();return x[idkey]
   if kind in j:raise CloudError('이전 생성 요청의 결과가 불명확합니다. 클라우드 확인이 필요합니다: '+kind)
   j[kind]={'intent':True};save();response=api.rds(product,path,body)
   if idkey in response:j[kind]['id']=response[idkey];save();return response[idkey]
   if 'jobId' in response:j[kind]['job']=response['jobId'];save();api.wait(product,response,self.stop)
   matches=[x for x in rows(api.rds(product,path),listkey) if x.get(namekey)==body[namekey] and x.get('description')==marker]
   if len(matches)!=1:raise CloudError('생성 결과 식별 실패: 재생성하지 않고 중단합니다.')
   j[kind]['id']=matches[0][idkey];save();return j[kind]['id']
  pg=ensure('parameter','/parameter-groups','parameterGroups','parameterGroupName','parameterGroupId',{'parameterGroupName':s['db_name']+'-params','dbVersion':s['db_version'],'description':marker})
  sg=ensure('security','/db-security-groups','dbSecurityGroups','dbSecurityGroupName','dbSecurityGroupId',{'dbSecurityGroupName':s['db_name']+'-sg','description':marker,'rules':[{'direction':'INGRESS','etherType':'IPV4','port':{'portType':'PORT','minPort':3306,'maxPort':3306},'cidr':p['server']['private_ip']+'/32','description':marker}]})
  db=ensure('database','/db-instances','dbInstances','dbInstanceName','dbInstanceId',{'dbInstanceName':s['db_name'],'description':marker,'dbFlavorId':p['flavor_id'],'dbVersion':s['db_version'],'dbPort':3306,'dbUserName':'labuser','dbPassword':item['password'],'parameterGroupId':pg,'dbSecurityGroupIds':[sg],'useHighAvailability':False,'useDeletionProtection':False,'authenticationPlugin':'CACHING_SHA2','network':{'subnetId':p['server']['subnet_id'],'usePublicAccess':False,'availabilityZone':p['server']['az']},'storage':{'storageType':'General SSD','storageSize':20},'backup':{'backupPeriod':0,'backupSchedules':[{'backupWndBgnTime':'00:00:00','backupWndDuration':'HALF_AN_HOUR'}]}})
  if j['database'].get('job'):api.wait(product,{'jobId':j['database']['job']},self.stop)
  detail=api.rds(product,'/db-instances/'+ident(db))
  if detail.get('dbInstanceStatus')!='AVAILABLE' or detail.get('progressStatus') not in ['NONE',None]:raise CloudError('RDS가 아직 사용 가능 상태가 아닙니다. 완료 후 실패 항목 재시도하세요.')
  if j.get('schema',{}).get('job'):api.wait(product,{'jobId':j['schema']['job']},self.stop)
  schemas=rows(api.rds(product,'/db-instances/'+db+'/db-schemas'),'dbSchemas')
  if not any(x['dbSchemaName']=='labdb' and x['dbSchemaStatus']=='STABLE' for x in schemas):
   if 'schema' in j:raise CloudError('스키마 생성 상태 확인 필요. 중복 생성하지 않습니다.')
   j['schema']={'intent':True};save();r=api.rds(product,'/db-instances/'+db+'/db-schemas',{'dbSchemaName':'labdb'});j['schema']['job']=r['jobId'];save();api.wait(product,r,self.stop)
  network=api.rds(product,'/db-instances/'+db+'/network-info');endpoints=rows(network,'endPoints');private=[x['ipAddress'] for x in endpoints if x.get('ipAddress') and ipaddress.ip_address(x['ipAddress']).is_private]
  if not private:raise CloudError('RDS 사설 접속 주소 확인 실패')
  item['access']={'db_host':private[0],'db_port':3306,'db_user':'labuser','db_name':'labdb','db_password':item['password']};save()
 def apply(self,id):
  b,cfg,secret=self.load(id)
  if not b['planned']:raise CloudError('먼저 계획을 조회하세요.')
  state=self.vault.open(b['state'],'nhn-state:'+id);api=API(secret,cfg['region']);failures=0
  try:
   for student,item in state.items():
    old=self.store.one('SELECT status FROM nhn_items WHERE batch_id=? AND student=?',(id,student))
    if old['status']=='READY':continue
    if old['status'] in ['CLEANED','CLEANING','CLEANUP_FAILED'] or any(v.get('delete_intent') or v.get('deleted') for v in item['journal'].values()):raise CloudError('정리를 시작한 계획은 재생성할 수 없습니다. 새 계획을 사용하세요.')
    p=item['plan'];s=item['summary'];j=item['journal'];save=lambda:self.save(id,state)
    self.report(id,student,s,'RUNNING','프로젝트 자원 준비 중')
    try:
     # Re-read immutable project identity and current server placement before any write.
     current=api.product(p['project_id'],p['compute']['productId']);server=choose_server(api,current,s['server_name'])
     if cfg['db']:server['subnet_id']=resolve_subnet(api,p['rds'],server)['subnetId']
     if any(server[k]!=p['server'][k] for k in ['server_id','private_ip','subnet_id','az','tenant']):raise CloudError('계획 후 서버·네트워크가 변경되었습니다. 새 계획이 필요합니다.')
     container=api.container(p['storage'],s['container'])
     if container and p.get('existing_container') is not None:
      if container['public'] or container['marker']!=p['existing_container']['marker']:raise CloudError('계획 후 기존 컨테이너 접근 정책·소유 정보가 변경되었습니다.')
      j['container']={'reused':True};save()
     elif container:
      if container['marker']!=p['marker'] or container['public'] or 'container' not in j:raise CloudError('컨테이너 소유권·비공개 상태 확인 실패')
     else:
      if p.get('existing_container') is not None:raise CloudError('재사용 예정 컨테이너가 사라졌습니다. 새 계획이 필요합니다.')
      if 'container' in j:raise CloudError('이전 컨테이너 요청 결과 불명확: 클라우드 확인 필요')
      j['container']={'intent':True};save();api.container(p['storage'],s['container'],'PUT',p['marker']);j['container']['created']=True;save()
      check=api.container(p['storage'],s['container'])
      if not check or check['public'] or check['marker']!=p['marker']:raise CloudError('컨테이너 생성 후 비공개·소유권 검증 실패')
     if cfg['db']:self.ensure_rds(api,cfg,item,save)
     # Register discovered servers in the existing inventory without replacing other assignments.
     tenant=p['server']['tenant'];now=time.time()
     with self.store.connect() as db:
      connections=db.execute("SELECT * FROM connections WHERE provider='NHN' AND account=? AND region=?",(tenant,cfg['region'])).fetchall()
      if len(connections)>1:raise CloudError('동일 테넌트 연결이 중복되어 서버 배정을 중단했습니다.')
      if connections:cid=connections[0]['id']
      else:
       cid=secrets.token_hex(16);encrypted=self.vault.seal({k:secret[k] for k in ['username','api_password']},'connection:'+cid)
       db.execute("INSERT INTO connections(id,name,provider,region,account,secret,writable,last_sync) VALUES(?,?,'NHN',?,?,?,0,?)",(cid,s['project'],cfg['region'],tenant,encrypted,now))
      existing=db.execute('SELECT event_id FROM resources WHERE connection_id=? AND remote_id=?',(cid,server['server_id'])).fetchone()
      if existing and existing['event_id'] and existing['event_id']!=b['event_id']:raise CloudError('서버가 다른 교육에 배정되어 있습니다. 배정 변경을 확인하세요.')
      db.execute('INSERT INTO resources(id,connection_id,remote_id,name,state,ip,flavor,event_id,owner,seen) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(connection_id,remote_id) DO UPDATE SET event_id=excluded.event_id,owner=excluded.owner',(secrets.token_hex(16),cid,server['server_id'],server['server_name'],'ACTIVE',server['ip'],'',b['event_id'],student,now))
     self.report(id,student,s,'READY','준비 완료 · 학생 서버에서 파일·DB 실습으로 최종 확인하세요.')
    except Exception as error:failures+=1;self.report(id,student,s,'FAILED',safe_error(error))
  finally:api.close()
  if failures:raise CloudError(f'{failures}개 프로젝트 실패/확인 필요. 완료 항목은 유지되며 재시도에서 건너뜁니다.')
 def cleanup(self,id):
  b,cfg,secret=self.load(id)
  if not b['state']:raise CloudError('정리할 생성 기록이 없습니다.')
  state=self.vault.open(b['state'],'nhn-state:'+id);api=API(secret,cfg['region']);failures=0
  try:
   for student,item in state.items():
    s=item['summary'];p=item['plan'];j=item['journal'];save=lambda:self.save(id,state)
    if not j:continue
    try:
     self.report(id,student,s,'CLEANING','생성 기록과 소유권을 대조하며 정리 중')
     if 'container' in j and not j['container'].get('reused'):
      preflight=api.container(p['storage'],s['container'])
      if preflight and (preflight['count'] or preflight['marker']!=p['marker']):raise CloudError('컨테이너 파일 또는 소유권 확인 필요: 정리 전 백업·확인하세요.')
     if cfg['db']:
      for kind,path,listkey,namekey,idkey,name in [('database','/db-instances','dbInstances','dbInstanceName','dbInstanceId',s['db_name']),('security','/db-security-groups','dbSecurityGroups','dbSecurityGroupName','dbSecurityGroupId',s['db_name']+'-sg'),('parameter','/parameter-groups','parameterGroups','parameterGroupName','parameterGroupId',s['db_name']+'-params')]:
       if kind not in j:continue
       product=p['rds']
       if j[kind].get('delete_job'):api.wait(product,{'jobId':j[kind]['delete_job']},self.stop)
       matches=[x for x in rows(api.rds(product,path),listkey) if x.get(namekey)==name]
       if len(matches)>1:raise CloudError('정리 대상 이름 중복')
       if matches:
        x=matches[0]
        if x.get('description')!=p['marker'] or (j[kind].get('id') and j[kind]['id']!=x[idkey]):raise CloudError('정리 대상 소유권 불일치: 기존 자원은 삭제하지 않습니다.')
        j[kind]['delete_intent']=True;save();response=api.rds(product,path+'/'+ident(x[idkey]),method='DELETE')
        if response.get('jobId'):j[kind]['delete_job']=response['jobId'];save();api.wait(product,response,self.stop)
       j[kind]['deleted']=True;save()
     if 'container' in j and not j['container'].get('reused'):
      container=api.container(p['storage'],s['container'])
      if container:
       if container['marker']!=p['marker']:raise CloudError('컨테이너 소유권 불일치')
       if container['count']:raise CloudError('컨테이너에 학생 파일이 있습니다. 파일을 백업·정리한 후 다시 요청하세요.')
       api.container(p['storage'],s['container'],'DELETE')
      j['container']['deleted']=True;save()
     self.report(id,student,s,'CLEANED','생성한 자원 정리 완료 · 기존 서버·네트워크 유지')
    except Exception as error:failures+=1;self.report(id,student,s,'CLEANUP_FAILED',safe_error(error))
  finally:api.close()
  if failures:raise CloudError(f'{failures}개 프로젝트 정리 확인 필요. 기존 서버는 변경하지 않았습니다.')

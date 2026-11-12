"""Official API adapters. No raw cloud response or credential is returned to the UI."""
import base64,datetime,hashlib,hmac,re,time
from urllib.parse import urlencode,urlparse
import boto3,httpx
from botocore.config import Config

class CloudError(Exception):pass

def resource(remote,name,state,ip='',flavor=''):
 return dict(remote_id=str(remote),name=str(name)[:160],state=str(state)[:40],ip=str(ip)[:240],flavor=str(flavor)[:100])

class AWS:
 def __init__(self,c,secret):
  self.c=c;self.secret=secret
  self.session=boto3.Session(region_name=c['region'],**{k:v for k,v in {'aws_access_key_id':secret.get('access_key'),'aws_secret_access_key':secret.get('secret_key'),'aws_session_token':secret.get('session_token')}.items() if v})
 def client(self,name):return self.session.client(name,config=Config(connect_timeout=5,read_timeout=30,retries={'max_attempts':2}))
 def identity(self):
  actual=self.client('sts').get_caller_identity()['Account']
  if actual!=self.c['account']:raise CloudError('AWS 계정 ID 불일치: 연결 설정을 확인하세요.')
 def inventory(self):
  self.identity();rows=[]
  for page in self.client('ec2').get_paginator('describe_instances').paginate():
   for reservation in page['Reservations']:
    for i in reservation['Instances']:
     name=next((t['Value'] for t in i.get('Tags',[]) if t['Key']=='Name'),i['InstanceId'])
     rows.append(resource(i['InstanceId'],name,i['State']['Name'],i.get('PublicIpAddress') or i.get('PrivateIpAddress',''),i['InstanceType']))
  return rows
 def action(self,remote,action):
  if not re.fullmatch(r'i-[0-9a-f]{8,17}',remote):raise CloudError('잘못된 EC2 ID')
  if action not in ['start','stop','delete']:raise CloudError('지원하지 않는 서버 작업')
  self.identity();getattr(self.client('ec2'),('terminate' if action=='delete' else action)+'_instances')(InstanceIds=[remote])
 def metrics(self,remote):
  self.identity();now=datetime.datetime.now(datetime.timezone.utc)
  stats=self.client('cloudwatch').get_metric_statistics(Namespace='AWS/EC2',MetricName='CPUUtilization',Dimensions=[{'Name':'InstanceId','Value':remote}],StartTime=now-datetime.timedelta(minutes=30),EndTime=now,Period=300,Statistics=['Average'])
  points=sorted(stats.get('Datapoints',[]),key=lambda p:p['Timestamp'])
  return {'cpu':round(points[-1]['Average'],1) if points else None,'at':points[-1]['Timestamp'].isoformat() if points else None,'memory':None,'disk':None}

class NHN:
 def __init__(self,c,secret):self.c=c;self.secret=secret;self.http=httpx.Client(timeout=30,follow_redirects=False);self.token=None
 def auth(self):
  r=self.http.post('https://api-identity-infrastructure.nhncloudservice.com/v2.0/tokens',json={'auth':{'tenantId':self.c['account'],'passwordCredentials':{'username':self.secret['username'],'password':self.secret['api_password']}}})
  if not r.is_success:raise CloudError(f'NHN 인증 실패 HTTP {r.status_code}: API 비밀번호·테넌트·권한 확인')
  data=r.json()['access']
  if data['token']['tenant']['id']!=self.c['account']:raise CloudError('NHN 테넌트 불일치')
  self.token=data['token']['id'];found=None
  for service in data['serviceCatalog']:
   if service['type']=='compute':
    found=next((e['publicURL'] for e in service['endpoints'] if e.get('region')==self.c['region']),None)
  if not found:raise CloudError('선택 리전 compute 엔드포인트 없음')
  u=urlparse(found)
  if u.scheme!='https' or not u.hostname or not (u.hostname.endswith('.nhncloudservice.com') or u.hostname.endswith('.cloud.toast.com')) or u.port not in (None,443) or u.username or u.password or u.query or u.fragment:raise CloudError('NHN 엔드포인트 검증 실패')
  self.endpoint=found.rstrip('/')
 def request(self,path,body=None,method=None):
  if not self.token:self.auth()
  r=self.http.request(method or ('POST' if body is not None else 'GET'),self.endpoint+path,headers={'X-Auth-Token':self.token},json=body)
  if not r.is_success:raise CloudError(f'NHN 요청 실패 HTTP {r.status_code}')
  return r.json() if r.content else {}
 def inventory(self):
  result=[];marker=None
  for _ in range(100):
   page=self.request('/servers/detail?'+urlencode({'limit':1000,**({'marker':marker} if marker else {})})).get('servers',[])
   for i in page:
    addresses=[a['addr'] for v in i.get('addresses',{}).values() for a in v]
    result.append(resource(i['id'],i['name'],i['status'],', '.join(addresses),i.get('flavor',{}).get('id','')))
   if len(page)<1000:return result
   marker=page[-1]['id']
  raise CloudError('NHN 조회 상한 초과: 연결 범위를 나누세요.')
 def action(self,remote,action):
  if not re.fullmatch(r'[0-9a-f-]{36}',remote):raise CloudError('잘못된 NHN 서버 ID')
  if action not in ['start','stop','delete']:raise CloudError('지원하지 않는 서버 작업')
  if action=='delete':self.request('/servers/'+remote,method='DELETE')
  else:self.request('/servers/'+remote+'/action',{'os-'+action:None})
 def metrics(self,remote):return {'cpu':None,'memory':None,'disk':None,'note':'기본 연결은 서버 상태·IP 조회입니다. 지표 수집은 추가 연동이 필요합니다.'}

class NCP:
 def __init__(self,c,secret):self.c=c;self.secret=secret;self.http=httpx.Client(timeout=30,follow_redirects=False)
 def request(self,action,params=None):
  query=urlencode(sorted({'regionCode':self.c['region'],'responseFormatType':'json',**(params or {})}.items()))
  uri='/vserver/v2/'+action+'?'+query;timestamp=str(int(time.time()*1000));key=self.secret['access_key'];msg=f'GET {uri}\n{timestamp}\n{key}'
  signature=base64.b64encode(hmac.new(self.secret['secret_key'].encode(),msg.encode(),hashlib.sha256).digest()).decode()
  r=self.http.get('https://ncloud.apigw.ntruss.com'+uri,headers={'x-ncp-apigw-timestamp':timestamp,'x-ncp-iam-access-key':key,'x-ncp-apigw-signature-v2':signature})
  if not r.is_success:raise CloudError(f'NAVER 요청 실패 HTTP {r.status_code}')
  data=r.json();body=data.get(action+'Response',{})
  if str(body.get('returnCode'))!='0':raise CloudError('NAVER API 오류: 키·VPC 환경·권한을 확인하세요.')
  return body
 def inventory(self):
  result=[]
  for page in range(1,101):
   data=self.request('getServerInstanceList',{'pageNo':page,'pageSize':100});items=data.get('serverInstanceList',[])
   for i in items:result.append(resource(i['serverInstanceNo'],i['serverName'],i.get('serverInstanceStatusName') or i['serverInstanceStatus']['code'],i.get('publicIp') or i.get('privateIp',''),i.get('serverSpecCode','')))
   if len(items)<100:return result
  raise CloudError('NAVER 조회 상한 초과')
 def action(self,remote,action):
  if not re.fullmatch(r'[0-9]+',remote):raise CloudError('잘못된 NAVER 서버 ID')
  if action not in ['start','stop','delete']:raise CloudError('지원하지 않는 서버 작업')
  self.request(('terminate' if action=='delete' else action)+'ServerInstances',{'serverInstanceNoList.1':remote})
 def metrics(self,remote):return {'cpu':None,'memory':None,'disk':None,'note':'Cloud Insight 지표는 별도 연동 전까지 미수집으로 표시합니다.'}

def adapter(c,secret):return {'AWS':AWS,'NHN':NHN,'NCP':NCP}[c['provider']](c,secret)

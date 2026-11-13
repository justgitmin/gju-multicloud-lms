"""Lifecycle control of resources bound to this platform's CloudFormation stacks."""
import json,time
from .providers import AWS,CloudError
from botocore.exceptions import ClientError
from .resource_ops import Resources,key,capabilities
from .nhn_batch import safe_error

TYPES={'server':('Web','AWS::EC2::Instance'),'database':('Database','AWS::RDS::DBInstance'),'container':('Bucket','AWS::S3::Bucket')}
class AWSResources(Resources):
 def load_env(self,id):
  env=self.store.one('SELECT * FROM environments WHERE id=?',(id,))
  if not env:raise CloudError('AWS 교육 환경이 없습니다.')
  c=self.store.one('SELECT * FROM connections WHERE id=?',(env['connection_id'],))
  if not c or c['provider']!='AWS':raise CloudError('AWS 연결 불일치')
  return env,c,json.loads(env['config'])
 def catalog(self,id):
  env,c,cfg=self.load_env(id);cached={r['id']:r for r in self.store.all('SELECT * FROM aws_resource_observations WHERE environment_id=?',(id,))};result=[]
  for code in cfg['students']:
   for kind in TYPES:
    if kind=='database' and not cfg['rds'] or kind=='container' and not cfg['s3']:continue
    rid=key(id,code,kind);saved=cached.get(rid,{})
    row={'id':rid,'environment_id':id,'batch_id':id,'connection_id':c['id'],'event_id':env['event_id'],'student':code,'owner':'','project':cfg['lab_id']+'-'+code,'provider':'AWS','kind':kind,'label':{'server':'서버','database':'DB','container':'Object Storage'}[kind],'name':saved.get('remote_id') or cfg['lab_id']+'-'+code+' · '+kind,'remote_id':saved.get('remote_id',''),'state':saved.get('state','UNCHECKED'),'presence':saved.get('presence',-1),'updated':saved.get('updated'),'owned':True,**json.loads(saved.get('detail','{}'))}
    person=cfg.get('lms_bindings',{}).get(code,{})
    if person:row['owner_display']=code+' · '+person.get('name','')+(' · 승인 명단에 없음' if not person.get('active') else '')
    row['actions']=capabilities(row);result.append(row)
  return result
 def observe(self,row,state,presence,detail=None):
  self.store.execute('INSERT INTO aws_resource_observations(id,environment_id,student,kind,remote_id,state,presence,detail,updated) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET remote_id=excluded.remote_id,state=excluded.state,presence=excluded.presence,detail=excluded.detail,updated=excluded.updated',(row['id'],row['environment_id'],row['student'],row['kind'],row['remote_id'],state,presence,json.dumps(detail or {}),time.time()))
 def physical(self,aws,cfg):
  result={};cf=aws.client('cloudformation')
  for page in cf.get_paginator('describe_stacks').paginate():
   for stack in page['Stacks']:
    code=next((code for code in cfg['students'] if stack['StackName']==cfg['lab_id']+'-'+code),None)
    if code is None:continue
    tags={t['Key']:t['Value'] for t in stack.get('Tags',[])}
    if tags.get('LabId')!=cfg['lab_id'] or tags.get('StudentId')!=code or tags.get('ManagedBy')!='gju-lab-tool':raise CloudError('CloudFormation 교육 소유권 불일치')
    if stack['StackStatus']=='DELETE_COMPLETE':continue
    for resources in cf.get_paginator('list_stack_resources').paginate(StackName=stack['StackId']):
     for resource in resources['StackResourceSummaries']:
      for kind,(logical,expected) in TYPES.items():
       if resource['LogicalResourceId']==logical and resource['ResourceType']==expected and resource['ResourceStatus']!='DELETE_COMPLETE':
        result[(code,kind)]=resource.get('PhysicalResourceId','')
  return result
 def lookup_aws(self,aws,row,physical):
  try:return self._lookup_aws(aws,row,physical)
  except ClientError as error:
   code=str(error.response.get('Error',{}).get('Code',''))
   if code in ['DBInstanceNotFound','DBInstanceNotFoundFault','NoSuchBucket','404','InvalidInstanceID.NotFound']:return 'NOT_FOUND',0,{}
   raise CloudError('AWS 자원 조회 권한·연결 확인 필요') from None
 def _lookup_aws(self,aws,row,physical):
  remote=physical.get((row['student'],row['kind']))
  if not remote:return 'NOT_FOUND',0,{}
  if row['remote_id'] and remote!=row['remote_id']:raise CloudError('AWS 자원 식별자가 변경되었습니다. 다시 조회하세요.')
  row['remote_id']=remote;kind=row['kind']
  if kind=='server':
   items=[x for reservation in aws.client('ec2').describe_instances(InstanceIds=[remote])['Reservations'] for x in reservation['Instances']]
   if len(items)!=1 or items[0]['InstanceId']!=remote:raise CloudError('EC2 식별 불일치')
   x=items[0];state=x['State']['Name'];return state,0 if state=='terminated' else 1,{'ip':x.get('PublicIpAddress') or x.get('PrivateIpAddress',''),'note':'중지는 데이터 유지, 삭제 시 루트 디스크도 삭제될 수 있습니다.'}
  if kind=='database':
   x=aws.client('rds').describe_db_instances(DBInstanceIdentifier=remote)['DBInstances'][0]
   if x['DBInstanceIdentifier']!=remote:raise CloudError('RDS 식별 불일치')
   return {'available':'AVAILABLE','stopped':'SHUTDOWN'}.get(x['DBInstanceStatus'],x['DBInstanceStatus']),1,{'note':'정지 중에도 스토리지 비용이 발생할 수 있습니다. 영구 삭제는 최종 스냅샷 없이 진행됩니다.'}
  args={'Bucket':remote,'ExpectedBucketOwner':aws.c['account']};s3=aws.client('s3');s3.head_bucket(**args)
  objects=s3.list_objects_v2(**args,MaxKeys=1);versions=s3.list_object_versions(**args,MaxKeys=1)
  count=int(bool(objects.get('Contents') or versions.get('Versions') or versions.get('DeleteMarkers')))
  return 'AVAILABLE',1,{'count':count,'owned':True,'note':'시작·중지 기능 없음 · 객체·과거 버전·삭제 마커가 있으면 삭제 차단'}
 def sync(self,id):
  env,c,cfg=self.load_env(id);aws=AWS(c,self.vault.open(c['secret'],'connection:'+c['id']));aws.identity();failed=0
  try:physical=self.physical(aws,cfg)
  except Exception:
   for row in self.catalog(id):self.observe(row,'CHECK_FAILED',-1,{'note':'AWS 스택 조회·소유권 확인 실패'})
   raise CloudError('AWS 스택 조회·소유권 확인 실패')
  for row in self.catalog(id):
   if self.stop.is_set():raise CloudError('AWS 자원 조회 중단')
   # Refresh may learn a replacement ID; a write must match the reviewed ID.
   row['remote_id']=''
   try:state,present,detail=self.lookup_aws(aws,row,physical);self.observe(row,state,present,detail)
   except Exception as error:failed+=1;self.observe(row,'CHECK_FAILED',-1,{'note':safe_error(error)})
  if failed:raise CloudError(f'{failed}개 AWS 자원 조회 실패')
 def apply(self,id,selected,action,job):
  env,c,cfg=self.load_env(id);aws=AWS(c,self.vault.open(c['secret'],'connection:'+c['id']));aws.identity();catalog={r['id']:r for r in self.catalog(id)};targets=[];failed=0
  physical=self.physical(aws,cfg)
  for saved in selected:
   row=catalog.get(saved['id'])
   if not row or row['remote_id']!=saved['remote_id']:raise CloudError('AWS 대상 식별자가 변경되었습니다.')
   state,present,detail=self.lookup_aws(aws,row,physical);row.update(detail,state=state,presence=present)
   if action not in capabilities(row):raise CloudError('AWS 자원의 현재 상태에서 지원하지 않는 작업')
   targets.append(row)
  for row in targets:
   if self.stop.is_set():raise CloudError('AWS 선택 작업 중단')
   try:
    state,present,detail=self.lookup_aws(aws,row,self.physical(aws,cfg));row.update(detail,state=state,presence=present)
    if action not in capabilities(row):raise CloudError('AWS 적용 직전 상태 변경')
    self.receipt(job,row,action,'REQUESTED')
    if row['kind']=='server':aws.action(row['remote_id'],action.lower())
    elif row['kind']=='container':aws.client('s3').delete_bucket(Bucket=row['remote_id'],ExpectedBucketOwner=c['account'])
    elif action=='DELETE':aws.client('rds').delete_db_instance(DBInstanceIdentifier=row['remote_id'],SkipFinalSnapshot=True,DeleteAutomatedBackups=True)
    else:getattr(aws.client('rds'),action.lower()+'_db_instance')(DBInstanceIdentifier=row['remote_id'])
    self.observe(row,action+'_REQUESTED',-1,{'note':'요청 접수 · 실제 상태 재확인 필요'});self.receipt(job,row,action,'ACCEPTED')
   except Exception as error:failed+=1;self.observe(row,'CHECK_REQUIRED',-1,{'note':safe_error(error)});self.receipt(job,row,action,'CHECK_REQUIRED',safe_error(error))
  try:self.sync(id)
  except CloudError:failed+=1
  if failed:raise CloudError(f'{failed}개 AWS 작업·확인 실패')

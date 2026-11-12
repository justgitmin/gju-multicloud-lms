"""Inventory and explicit lifecycle operations for tracked education resources.

Only exact saved identifiers are targeted. An error is never evidence of absence.
No cloud mutation is run by a dashboard read or inventory refresh.
"""
import hashlib,json,time
from . import providers
from .nhn_batch import API,Batch,ident,rows,safe_error

KINDS={'server':'서버','database':'DB','container':'Object Storage','security':'DB 보안 그룹','parameter':'DB 파라미터 그룹','vpc':'VPC','subnet':'서브넷','igw':'인터넷 게이트웨이','web_security':'서버 보안 그룹','floating':'플로팅 IP'}
RDS={'database':('/db-instances','dbInstances','dbInstanceId','dbInstanceName'),'security':('/db-security-groups','dbSecurityGroups','dbSecurityGroupId','dbSecurityGroupName'),'parameter':('/parameter-groups','parameterGroups','parameterGroupId','parameterGroupName')}
NET={'vpc':('/vpcs','vpcs'),'subnet':('/vpcsubnets','vpcsubnets'),'igw':('/internetgateways','internetgateways'),'web_security':('/security-groups','security_groups'),'floating':('/floatingips','floatingips')}

def key(batch,student,kind):return hashlib.sha256((batch+':'+student+':'+kind).encode()).hexdigest()[:32]

def capabilities(row):
 if row['presence']!=1:return []
 if row['kind']=='server':
  if row['state'] in ['ACTIVE','running','RUN','running (normal)']:return ['STOP']
  if row['state'] in ['SHUTOFF','stopped','STOP','NSTOP','stopped (normal)']:return ['START','DELETE']
  return []
 if row['kind']=='database':
  if row['state']=='AVAILABLE':return ['STOP','DELETE']
  if row['state']=='SHUTDOWN':return ['START','DELETE']
  return []
 if row['kind']=='container':return ['DELETE'] if row.get('owned') and row.get('count')==0 else []
 if row['kind'] in ['security','parameter',*NET] and row.get('owned'):return ['DELETE']
 return []

class Resources(Batch):
 def snapshots(self,id):
  b=self.store.one('SELECT * FROM nhn_batches WHERE id=?',(id,))
  if not b:raise providers.CloudError('교육 환경이 없습니다.')
  boot=self.store.one('SELECT state,config FROM nhn_bootstrap WHERE batch_id=?',(id,))
  state=self.vault.open(b['state'],'nhn-state:'+id) if b['state'] else {}
  servers=self.vault.open(boot['state'],'nhn-servers:'+id) if boot and boot['state'] else {}
  return b,state,servers
 def catalog(self,id):
  b,state,servers=self.snapshots(id);result=[]
  roster=json.loads((self.store.one('SELECT config FROM nhn_bootstrap WHERE batch_id=?',(id,)) or {'config':'{}'})['config']).get('roster',{})
  cache={r['id']:r for r in self.store.all('SELECT * FROM resource_observations WHERE batch_id=?',(id,))}
  for code in sorted(set(state)|set(servers.get('students',{}))):
   item=state.get(code,{});boot=servers.get('students',{}).get(code,{})
   summary=item.get('summary',{}) or boot.get('summary',{});person=boot.get('person',{}) or roster.get(code,{});plan=item.get('plan',{});journal=item.get('journal',{});bj=boot.get('journal',{})
   def add(kind,remote,name,owned=False):
    rid=key(id,code,kind);observed=cache.get(rid);valid=observed and observed['remote_id']==remote
    detail=json.loads(observed['detail']) if valid else {}
    r={'id':rid,'batch_id':id,'connection_id':b['connection_id'],'event_id':b['event_id'],'student':code,'owner':person.get('name',summary.get('owner','')),'project':summary.get('project',''),'kind':kind,'label':KINDS[kind],'remote_id':remote,'name':name,'creation_recorded':bool((bj if kind in ['server',*NET] else journal).get('security' if kind=='web_security' else kind)),'owned':owned,'state':observed['state'] if valid else 'UNCHECKED','presence':observed['presence'] if valid else -1,'updated':observed['updated'] if valid else None,**detail}
    r['actions']=capabilities(r);result.append(r)
   server=plan.get('server',{});sid=boot.get('server_id') or server.get('server_id') or bj.get('server',{}).get('id','')
   add('server',sid,summary.get('server_name',code+'-web'),True)
   add('container',summary.get('container',''),summary.get('container',''),bool(journal.get('container',{}).get('created') or (journal.get('container',{}).get('intent') and not journal.get('container',{}).get('reused'))))
   if summary.get('db'):
    for kind in RDS:
     name=summary.get('db_name','')+{'database':'','security':'-sg','parameter':'-params'}[kind]
     add(kind,journal.get(kind,{}).get('id',''),name,kind in journal)
   for kind in NET:
    record=bj.get('security' if kind=='web_security' else kind,{})
    if record.get('id'):add(kind,record['id'],KINDS[kind]+' · '+code,True)
  return result
 def observe(self,row,state,presence,detail=None):
  self.store.execute('INSERT INTO resource_observations(id,batch_id,student,kind,remote_id,state,presence,detail,updated) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET remote_id=excluded.remote_id,state=excluded.state,presence=excluded.presence,detail=excluded.detail,updated=excluded.updated',(row['id'],row['batch_id'],row['student'],row['kind'],row['remote_id'],state,presence,json.dumps(detail or {}),time.time()))
 def lookup(self,api,row,state,servers):
  code=row['student'];kind=row['kind'];item=state.get(code,{});plan=item.get('plan',{});boot=servers.get('students',{}).get(code,{})
  if not row['remote_id']:return ('CHECK_REQUIRED',-1,{'note':'생성 요청 기록은 있으나 결과 식별자가 없습니다. 중복 생성하지 않습니다.'}) if row.get('creation_recorded') else ('NOT_CREATED',0,{})
  if kind=='container':
   if not plan.get('storage'):return 'UNCHECKED',-1,{'note':'저장소 생성 계획 조회가 필요합니다.'}
   found=api.container(plan['storage'],row['remote_id'])
   if found is None:return 'NOT_FOUND',0,{}
   owned=found['marker']==plan['marker'] and row['owned']
   return 'AVAILABLE',1,{'count':found['count'],'owned':owned,'note':'시작·중지 기능 없음'+(' · 파일 '+str(found['count'])+'개' if found['count'] else ' · 빈 컨테이너')}
  if kind in RDS:
   if not plan.get('rds'):return 'UNCHECKED',-1,{'note':'DB 서비스 정보 확인 필요'}
   path,listkey,idkey,namekey=RDS[kind];matches=[x for x in rows(api.rds(plan['rds'],path),listkey) if x.get(idkey)==row['remote_id']]
   if not matches:return 'NOT_FOUND',0,{}
   if len(matches)!=1 or matches[0].get(namekey)!=row['name'] or matches[0].get('description')!=plan['marker']:raise providers.CloudError('자원 ID·이름·소유권 불일치')
   found=matches[0];status=found.get('dbInstanceStatus','AVAILABLE')
   if kind=='database' and found.get('progressStatus') not in [None,'NONE']:status=found['progressStatus']
   return status,0 if status=='DELETED' else 1,{'owned':True,'note':'사설 DB' if kind=='database' else 'DB 연결 중이면 삭제가 거절될 수 있습니다.'}
  tenant=boot.get('tenant') or plan.get('server',{}).get('tenant')
  if not tenant:return 'UNCHECKED',-1,{'note':'인프라 Tenant 확인 필요'}
  if kind=='server':
   client=api.compute(tenant)
   try:matches=[x for x in client.inventory() if x['remote_id']==row['remote_id']]
   finally:client.http.close()
   if not matches:return 'NOT_FOUND',0,{}
   if len(matches)!=1 or matches[0]['name']!=row['name']:raise providers.CloudError('서버 ID·이름 불일치')
   return matches[0]['state'],1,{'ip':matches[0]['ip'],'note':'삭제 시 연결된 루트 디스크가 함께 삭제될 수 있습니다.'}
  from .nhn_servers import Infra
  infra=Infra(api,{'externalId':tenant})
  try:
   path,listkey=NET[kind];matches=[x for x in rows(infra.net(path),listkey) if x.get('id')==row['remote_id']]
   if not matches:return 'NOT_FOUND',0,{}
   return matches[0].get('status',matches[0].get('state','AVAILABLE')),1,{'owned':row['owned'],'note':'연결된 자원이 있으면 삭제가 거절될 수 있습니다. 연결은 자동 해제하지 않습니다.'}
  finally:infra.close()
 def sync(self,id):
  b,cfg,secret=self.load(id);_,state,servers=self.snapshots(id);api=API(secret,cfg['region']);failed=0
  try:
   for row in self.catalog(id):
    if self.stop.is_set():raise providers.CloudError('자원 확인 중단')
    try:status,present,detail=self.lookup(api,row,state,servers);self.observe(row,status,present,detail)
    except Exception as error:failed+=1;self.observe(row,'CHECK_FAILED',-1,{'note':safe_error(error)})
  finally:api.close()
  if failed:raise providers.CloudError(f'{failed}개 자원 조회 실패 · 미생성으로 처리하지 않았습니다.')
 def receipt(self,job,row,action,status,message=''):
  self.store.execute('INSERT INTO resource_actions(job_id,resource_id,action,status,message,created) VALUES(?,?,?,?,?,?)',(job,row['id'],action,status,message,time.time()))
 def tombstone(self,id,row):
  b,state,servers=self.snapshots(id);code=row['student'];kind=row['kind']
  if code in state:
   item=state[code];item.setdefault('journal',{}).setdefault(kind,{})['delete_intent']=True;self.save_item(id,code,item)
  if kind in ['server',*NET] and code in servers.get('students',{}):
   servers['students'][code]['lifecycle_deleted']=True;servers['students'][code]['ready']=False
   self.store.execute('UPDATE nhn_bootstrap SET state=? WHERE batch_id=?',(self.vault.seal(servers,'nhn-servers:'+id),id))
  self.store.execute("UPDATE nhn_items SET status='RESOURCE_DELETED',message='개별 삭제 작업 요청 · 자원 관리에서 실제 상태 확인',updated=? WHERE batch_id=? AND student=?",(time.time(),id,code))
 def apply(self,id,selected,action,job):
  b,cfg,secret=self.load(id);_,state,servers=self.snapshots(id);catalog={r['id']:r for r in self.catalog(id)};api=API(secret,cfg['region']);targets=[];failures=0;waiting=[]
  try:
   # Validate the complete selection before issuing the first mutation.
   for saved in selected:
    row=catalog.get(saved['id'])
    if not row or row['remote_id']!=saved['remote_id']:raise providers.CloudError('선택한 자원 식별자가 변경되었습니다.')
    status,present,detail=self.lookup(api,row,state,servers);row.update(detail,state=status,presence=present)
    if action not in capabilities(row):raise providers.CloudError('현재 상태에서 지원하지 않는 작업: '+row['name'])
    targets.append(row)
   if action=='DELETE':targets.sort(key=lambda r:{'database':0,'container':1,'server':2,'floating':3,'security':4,'parameter':4,'web_security':4,'subnet':5,'igw':6,'vpc':7}.get(r['kind'],9))
   for row in targets:
    if self.stop.is_set():raise providers.CloudError('작업 중단 · 실제 상태 확인 후 재요청하세요.')
    try:
     # Read again immediately before each write, not just before the batch.
     status,present,detail=self.lookup(api,row,state,servers);row.update(detail,state=status,presence=present)
     if action not in capabilities(row):raise providers.CloudError('적용 직전 자원 상태가 변경되었습니다.')
     if action=='DELETE':self.tombstone(id,row)
     self.receipt(job,row,action,'REQUESTED')
     if row['kind']=='server':
      boot=servers.get('students',{}).get(row['student'],{});tenant=boot.get('tenant') or state[row['student']]['plan']['server']['tenant'];client=api.compute(tenant)
      try:client.action(row['remote_id'],action.lower())
      finally:client.http.close()
     elif row['kind']=='container':api.container(state[row['student']]['plan']['storage'],row['remote_id'],'DELETE')
     elif row['kind'] in NET:
      from .nhn_servers import Infra
      boot=servers['students'][row['student']];infra=Infra(api,{'externalId':boot['tenant']})
      try:infra.net(NET[row['kind']][0]+'/'+ident(row['remote_id']),method='DELETE')
      finally:infra.close()
     else:
      product=state[row['student']]['plan']['rds'];path=RDS[row['kind']][0]+'/'+ident(row['remote_id'])
      response=api.rds(product,path if action=='DELETE' else path+'/'+action.lower(),method='DELETE' if action=='DELETE' else 'POST')
      if response.get('jobId'):
       self.receipt(job,row,action,'ACCEPTED','비동기 ID '+ident(response['jobId']))
       if action=='DELETE':api.wait(product,response,self.stop)
       else:waiting.append((row,product,response))
     self.observe(row,'DELETE_REQUESTED' if action=='DELETE' else action+'_REQUESTED',-1,{'note':'요청 접수 · 실제 상태 재확인 필요'});self.receipt(job,row,action,'ACCEPTED')
    except Exception as error:
     failures+=1;self.observe(row,'CHECK_REQUIRED',-1,{'note':safe_error(error)});self.receipt(job,row,action,'CHECK_REQUIRED',safe_error(error))
   for row,product,response in waiting:
    try:api.wait(product,response,self.stop)
    except Exception as error:failures+=1;self.receipt(job,row,action,'CHECK_REQUIRED',safe_error(error))
  finally:api.close()
  try:self.sync(id)
  except providers.CloudError:failures+=1
  if failures:raise providers.CloudError(f'{failures}개 작업·확인 실패 · 자원별 작업 결과를 확인하세요.')

def server_bulk(store,vault,connection,selected,action,job,stop):
 client=providers.adapter(connection,vault.open(connection['secret'],'connection:'+connection['id']));targets=[];failed=0
 def fresh(saved):
  local=store.one('SELECT * FROM resources WHERE id=?',(saved['id'],))
  if not local or local['connection_id']!=connection['id'] or not local['event_id'] or local['missing'] or local['remote_id']!=saved['remote_id']:raise providers.CloudError('서버 배정·식별자가 변경되었습니다.')
  matches=[x for x in client.inventory() if x['remote_id']==saved['remote_id']]
  if len(matches)!=1 or matches[0]['name']!=local['name']:raise providers.CloudError('서버 실제 상태·이름 확인 실패')
  row={'presence':1,'kind':'server','state':matches[0]['state']}
  if action not in capabilities(row):raise providers.CloudError('서버 상태에서 지원하지 않는 작업입니다. 삭제는 먼저 중지하세요.')
  return local
 try:
  for saved in selected:targets.append(fresh(saved))
  for row in targets:
   if stop.is_set():raise providers.CloudError('선택 작업 중단')
   try:
    fresh(row)
    store.execute('INSERT INTO resource_actions(job_id,resource_id,action,status,message,created) VALUES(?,?,?,?,?,?)',(job,row['id'],action,'REQUESTED','',time.time()))
    client.action(row['remote_id'],action.lower())
    store.execute('INSERT INTO resource_actions(job_id,resource_id,action,status,message,created) VALUES(?,?,?,?,?,?)',(job,row['id'],action,'ACCEPTED','실제 상태는 동기화로 확인',time.time()))
   except Exception as error:
    failed+=1;store.execute('INSERT INTO resource_actions(job_id,resource_id,action,status,message,created) VALUES(?,?,?,?,?,?)',(job,row['id'],action,'CHECK_REQUIRED',safe_error(error),time.time()))
 finally:
  if hasattr(client,'http'):client.http.close()
 if failed:raise providers.CloudError(f'{failed}개 서버 요청 실패 · 자원별 작업 결과를 확인하세요.')

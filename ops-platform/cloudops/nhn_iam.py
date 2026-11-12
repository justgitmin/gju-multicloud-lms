"""Existing education IAM accounts only. Never reset passwords or send mail."""
import json,re,time
from urllib.parse import urlencode,urlparse
from .nhn_batch import API,Batch,ident,project_target,scoped_projects
from .nhn_iam_roles import paged,member,operator,desired_roles,assignments,student_assignments
from .providers import CloudError

def login_url(value):
 value=value.strip()
 if not value:return ''
 u=urlparse(value)
 if u.scheme!='https' or not u.hostname or not u.hostname.endswith('.nhncloud.com') or u.username or u.password or u.port not in (None,443) or u.fragment:raise CloudError('조직 IAM 로그인 URL을 NHN 콘솔에서 복사하세요 (HTTPS nhncloud.com).')
 return value

class Client:
 def __init__(self,api):self.api=api
 def call(self,method,path,body=None,query=None):
  return self.api.core(path+('?' + urlencode(query,doseq=True) if query else ''),body=body,method=method)

def org_member(api,org,uuid,username):
 value=api.call('GET',f'/v1/iam/organizations/{ident(org)}/members/{ident(uuid)}').get('orgMember')
 if not isinstance(value,dict) or value.get('id')!=uuid or value.get('organizationId')!=org or value.get('userCode')!=username:raise CloudError('조직 IAM 계정 식별 불일치')
 return value

def make_plan(api,cfg,settings,stop):
 projects=scoped_projects(api.api,cfg);memberships={};result=[]
 targets={}
 for n in range(cfg['first'],cfg['last']+1):
  org,name=project_target(cfg,n);username=settings['prefix']+f'{n:02}'
  found=[p for p in projects[org] if p.get('projectName')==name and p.get('projectStatusCode')=='STABLE']
  if len(found)!=1:raise CloudError('학생 프로젝트가 없거나 정상 상태가 아닙니다: '+name)
  targets[(org,username)]=found[0]
 for org,items in projects.items():
  for project in items:
   if stop.is_set():raise CloudError('IAM 조회 중단')
   pid=ident(project['projectId']);records=paged(api,f'/v1/iam/projects/{pid}/members','projectMembers');memberships[pid]=records
   for record in records:
    target=targets.get((org,record.get('id')))
    if target and target['projectId']!=pid:raise CloudError('학생 IAM이 다른 프로젝트에도 배정되어 있습니다. 자동 변경을 중단합니다.')
 for n in range(cfg['first'],cfg['last']+1):
  code=f's{n:02}';org,name=project_target(cfg,n);username=settings['prefix']+f'{n:02}';pid=ident(targets[(org,username)]['projectId'])
  row={'student':code,'username':username,'org':org,'project':name,'project_id':pid,'login_url':settings['urls'].get(org,''),'status':'BLOCKED'}
  records=[m for m in memberships[pid] if m.get('id')==username]
  if len(records)!=1:
   row['message']='기존 프로젝트 IAM 배정이 없습니다. 조직·계정 배정을 확인하세요.';result.append(row);continue
  uuid=ident(records[0]['uuid']);detail=member(api,pid,uuid)
  if detail.get('id')!=username:raise CloudError('프로젝트 IAM 식별 불일치')
  account=org_member(api,org,uuid,username);protected=operator(api,pid,settings['operator'])
  if protected['uuid']==uuid:raise CloudError('운영자 계정은 변경할 수 없습니다.')
  before=student_assignments(detail,name);catalog=paged(api,f'/v1/projects/{pid}/roles','roles',{'categoryTypeCodes':['ROLE']});after=assignments(desired_roles(catalog))
  row.update({'uuid':uuid,'before':before,'after':after,'operator':protected,'account_status':account.get('status'),'password_changed_at':account.get('passwordChangedAt')})
  if account.get('status')!='member':row['message']='이용 정지 또는 알 수 없는 계정 상태입니다. NHN 조직에서 허용한 뒤 다시 조회하세요.'
  elif any(r not in after for r in before):row['message']='추가 역할·조건이 있어 자동 덮어쓰기를 차단했습니다.'
  else:row.update({'status':'UNCHANGED' if before==after else 'PLANNED','message':'정상 · 변경 없음' if before==after else '누락된 실습 역할만 추가'})
  result.append(row)
 return {'config':cfg,'settings':settings,'rows':result}

class IAM(Batch):
 def record(self,id,plan,status):
  encrypted=self.vault.seal(plan,'nhn-iam:'+id);now=time.time()
  with self.store.connect() as db:
   db.execute('UPDATE nhn_iam SET state=?,status=?,updated=? WHERE batch_id=?',(encrypted,status,now,id))
   db.execute('INSERT INTO nhn_iam_history(batch_id,state,status,created) VALUES(?,?,?,?)',(id,encrypted,status,now))
 def plan(self,id):
  b,cfg,secret=self.load(id);saved=self.store.one('SELECT * FROM nhn_iam WHERE batch_id=?',(id,))
  if not saved:raise CloudError('IAM 설정을 먼저 저장하세요.')
  raw=API(secret,cfg['region'])
  try:plan=make_plan(Client(raw),cfg,json.loads(saved['config']),self.stop)
  finally:raw.close()
  self.record(id,plan,'BLOCKED' if any(r['status']=='BLOCKED' for r in plan['rows']) else 'PLANNED')
 def apply(self,id):
  b,cfg,secret=self.load(id);saved=self.store.one('SELECT * FROM nhn_iam WHERE batch_id=?',(id,))
  if not saved or saved['status']!='PLANNED' or time.time()-saved['updated']>3600:raise CloudError('1시간 이내 차단 없는 IAM 계획 조회가 필요합니다.')
  plan=self.vault.open(saved['state'],'nhn-iam:'+id);raw=API(secret,cfg['region']);api=Client(raw)
  try:
   fresh=make_plan(api,cfg,json.loads(saved['config']),self.stop)
   if fresh!=plan:raise CloudError('IAM 상태 또는 설정이 변경되었습니다. 다시 조회하세요.')
   self.record(id,plan,'RUNNING')
   for row in plan['rows']:
    if self.stop.is_set():raise CloudError('IAM 적용 중단 · 다시 조회 후 재시도하세요.')
    pid=row['project_id'];uuid=row['uuid'];current=member(api,pid,uuid);account=org_member(api,row['org'],uuid,row['username'])
    if current.get('id')!=row['username'] or student_assignments(current,pid)!=row['before'] or account.get('status')!='member' or account.get('passwordChangedAt')!=row['password_changed_at'] or operator(api,pid,plan['settings']['operator'])!=row['operator']:raise CloudError('적용 직전 IAM 변경 감지 · 다시 조회하세요.')
    if row['before']!=row['after']:
     row['status']='WRITE_REQUESTED';self.record(id,plan,'RUNNING')
     api.call('PUT',f'/v1/iam/projects/{pid}/members/{uuid}',{'assignRoles':row['after']})
    checked=member(api,pid,uuid);account=org_member(api,row['org'],uuid,row['username'])
    if checked.get('id')!=row['username'] or student_assignments(checked,pid)!=row['after'] or account.get('status')!='member' or account.get('passwordChangedAt')!=row['password_changed_at'] or operator(api,pid,plan['settings']['operator'])!=row['operator']:raise CloudError('IAM 적용 후 검증 실패 · 실제 상태를 확인하세요.')
    row.update({'status':'VERIFIED','message':'실습 역할 확인 완료 · 기존 비밀번호 유지'});self.record(id,plan,'RUNNING')
   self.record(id,plan,'VERIFIED')
  except Exception:
   self.record(id,plan,'CHECK_REQUIRED');raise
  finally:raw.close()

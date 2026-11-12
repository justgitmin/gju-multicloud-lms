import base64,importlib.util,json,os,secrets,subprocess,tempfile,threading,time
from pathlib import Path
from . import providers

class Worker:
 def __init__(self,store,vault,runner=None):self.store=store;self.vault=vault;self.runner=runner or Path(__file__).resolve().parents[2]/'infra/aws-lab/lab.py';self.stop=threading.Event()
 def enqueue(self,actor,c,kind,target,payload=None):
  id=secrets.token_hex(16);now=time.time()
  with self.store.connect() as db:
   db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',(id,actor,c['id'],c['revision'],kind,target,json.dumps(payload or {}),'QUEUED',now,now,'실행 대기'))
   db.execute('INSERT INTO audits(actor,event,target,result,created) VALUES(?,?,?,?,?)',(str(actor),'JOB_'+kind,target,'QUEUED',now))
  return id
 def sync(self,c,secret):
  items=providers.adapter(c,secret).inventory();now=time.time()
  with self.store.connect() as db:
   db.execute('UPDATE resources SET missing=1 WHERE connection_id=?',(c['id'],))
   for i in items:
    db.execute('''INSERT INTO resources(id,connection_id,remote_id,name,state,ip,flavor,seen) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(connection_id,remote_id) DO UPDATE SET name=excluded.name,state=excluded.state,ip=excluded.ip,flavor=excluded.flavor,seen=excluded.seen,missing=0''',(secrets.token_hex(16),c['id'],i['remote_id'],i['name'],i['state'],i['ip'],i['flavor'],now))
   db.execute('UPDATE connections SET last_sync=?,error=NULL WHERE id=?',(now,c['id']))
 def aws_lab(self,c,secret,job):
  env=self.store.one('SELECT * FROM environments WHERE id=?',(job['target'],))
  if not env or env['connection_id']!=c['id'] or c['provider']!='AWS':raise providers.CloudError('환경 연결 불일치')
  config=json.loads(env['config']);selected=json.loads(job.get('payload','{}')).get('students')
  if selected is not None:
   if not isinstance(selected,list) or not selected or len(selected)!=len(set(selected)) or any(code not in config['students'] for code in selected):raise providers.CloudError('AWS 선택 학생이 계획과 일치하지 않습니다.')
   config['students']=selected
  action={'PROVISION':'apply','DESTROY':'destroy','AWS_CHECK':'check'}[job['kind']]
  aws=providers.AWS(c,secret);aws.identity()
  with tempfile.TemporaryDirectory(prefix='ops-lab-') as folder:
   root=Path(folder);state=root/'state';state.mkdir(mode=0o700);cfg=root/'config.json';cfg.write_text(json.dumps(config));cfg.chmod(0o600)
   if env['state']:
    for name,value in self.vault.open(env['state'],'state:'+env['id']).items():
     path=state/name
     if not path.resolve().is_relative_to(state.resolve()):raise providers.CloudError('상태 경로 오류')
     path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);path.write_bytes(base64.b64decode(value));path.chmod(0o600)
   process_env={k:v for k,v in os.environ.items() if not k.startswith('AWS_') and k not in ['OPS_MASTER_KEY','OPS_ADMIN_PASSWORD']}
   process_env.update({'PATH':os.environ.get('PATH',''),'HOME':folder,'AWS_DEFAULT_REGION':c['region'],'AWS_REGION':c['region'],'AWS_PAGER':''})
   for src,dst in [('access_key','AWS_ACCESS_KEY_ID'),('secret_key','AWS_SECRET_ACCESS_KEY'),('session_token','AWS_SESSION_TOKEN')]:
    if secret.get(src):process_env[dst]=secret[src]
   def checkpoint():
    files={str(p.relative_to(state)):base64.b64encode(p.read_bytes()).decode() for p in state.rglob('*') if p.is_file() and not p.is_symlink()}
    self.store.execute('UPDATE environments SET state=? WHERE id=?',(self.vault.seal(files,'state:'+env['id']),env['id']))
   spec=importlib.util.spec_from_file_location('isolated_lab_'+job['id'],self.runner);lab=importlib.util.module_from_spec(spec);spec.loader.exec_module(lab)
   original_save=lab.save_private;deadline=time.monotonic()+7200
   def durable_save(path,value):original_save(path,value);checkpoint()
   def cli(config,*args):
    # Commit encrypted state BEFORE cloud requests, including credentials creation.
    checkpoint();self.store.execute('UPDATE jobs SET message=?,updated=? WHERE id=?',('AWS '+str(args[0])+' '+str(args[1])+' 진행 중',time.time(),job['id']));remaining=deadline-time.monotonic()
    if remaining<=0:raise providers.CloudError('작업 시간 제한 초과: 클라우드 상태를 확인하세요.')
    result=subprocess.run(['aws','--region',config['region'],'--output','json','--no-cli-pager',*args],env=process_env,capture_output=True,text=True,timeout=remaining)
    if result.returncode:raise providers.CloudError('AWS 명령 실패: 계정·권한·CloudFormation 이벤트를 확인하세요. 원문 응답은 저장하지 않습니다.')
    return json.loads(result.stdout) if result.stdout.strip() else {}
   lab.save_private=durable_save;lab.aws=cli
   try:
    validated=lab.load_config(cfg,deployment=action=='apply')
    if action=='apply':lab.deploy(validated,state)
    elif action=='check':
     validated['students']=[code for code in validated['students'] if not (state/(validated['lab_id']+'-'+code)).exists()]
     lab.preflight(validated)
    else:lab.destroy(validated)
   except Exception as error:
    capacity_type=getattr(lab,'CapacityError',None)
    if isinstance(capacity_type,type) and isinstance(error,capacity_type):raise providers.CloudError(str(error)) from None
    raise
   finally:checkpoint()

 def run_one(self):
  with self.store.connect() as db:
   db.execute('BEGIN IMMEDIATE');pending=db.execute("SELECT * FROM jobs WHERE status='QUEUED' ORDER BY created").fetchall();job=next((row for row in pending if not json.loads(row['payload']).get('automatic')),pending[0] if pending else None)
   if not job:return False
   job=dict(job);db.execute("UPDATE jobs SET status='RUNNING',updated=?,message='클라우드 요청 실행 중' WHERE id=?",(time.time(),job['id']))
  try:
   user=self.store.one('SELECT * FROM users WHERE id=?',(job['actor'],));c=self.store.one('SELECT * FROM connections WHERE id=?',(job['connection_id'],))
   required=['ADMIN','OPERATOR'] if job['kind'] in ['SYNC','START','STOP','RESOURCE_REFRESH','RESOURCE_ACTION'] else ['ADMIN']
   if job['kind']=='RESOURCE_ACTION' and json.loads(job['payload']).get('action')=='DELETE':required=['ADMIN']
   if not user or not user['active'] or user['role'] not in required or not c or c['revision']!=job['revision']:raise providers.CloudError('권한 또는 연결 설정 변경으로 작업을 중단했습니다.')
   if job['kind'] not in ['SYNC','NHN_PLAN','NHN_SERVER_PLAN','NHN_IAM_PLAN','RESOURCE_REFRESH','AWS_CHECK'] and not c['writable']:raise providers.CloudError('연결의 변경 권한이 비활성화되어 있습니다.')
   secret=self.vault.open(c['secret'],'connection:'+c['id'])
   if job['kind']=='SYNC':self.sync(c,secret);message='동기화 완료'
   elif job['kind'] in ['START','STOP']:
    r=self.store.one('SELECT * FROM resources WHERE id=?',(job['target'],))
    if not r or r['connection_id']!=c['id'] or r['missing'] or not r['event_id']:raise providers.CloudError('교육에 배정된 현재 자원만 제어할 수 있습니다.')
    providers.adapter(c,secret).action(r['remote_id'],job['kind'].lower());message='요청 접수 완료 · 실제 상태는 다음 동기화에서 확인'
   elif job['kind']=='RESOURCE_REFRESH':
    from .resource_ops import Resources
    manager=Resources(self.store,self.vault,self.stop);failed=0
    for bid in json.loads(job['payload']).get('batches',[]):
     batch=self.store.one('SELECT connection_id FROM nhn_batches WHERE id=?',(bid,))
     if not batch or batch['connection_id']!=c['id']:raise providers.CloudError('자원 조회 연결 불일치')
     try:manager.sync(bid)
     except providers.CloudError:failed+=1
    from .aws_resources import AWSResources
    for eid in json.loads(job['payload']).get('environments',[]):
     env=self.store.one('SELECT connection_id FROM environments WHERE id=?',(eid,))
     if not env or env['connection_id']!=c['id']:raise providers.CloudError('AWS 조회 연결 불일치')
     try:AWSResources(self.store,self.vault,self.stop).sync(eid)
     except providers.CloudError:failed+=1
    if not json.loads(job['payload']).get('batches'):self.sync(c,secret)
    if failed:raise providers.CloudError(f'{failed}개 환경에서 일부 자원 조회 실패 · 자원별 결과 확인')
    self.store.execute('UPDATE connections SET last_sync=?,error=NULL WHERE id=?',(time.time(),c['id']))
    message='자원 생성 여부·실제 상태 확인 완료'
   elif job['kind']=='RESOURCE_ACTION':
    from .resource_ops import Resources,server_bulk
    payload=json.loads(job['payload']);action=payload['action'];failed=0
    if action not in ['START','STOP','DELETE']:raise providers.CloudError('지원하지 않는 작업')
    for bid,selected in payload.get('managed',{}).items():
     batch=self.store.one('SELECT connection_id FROM nhn_batches WHERE id=?',(bid,))
     if not batch or batch['connection_id']!=c['id']:raise providers.CloudError('제어 대상 연결 불일치')
     try:Resources(self.store,self.vault,self.stop).apply(bid,selected,action,job['id'])
     except providers.CloudError:failed+=1
    from .aws_resources import AWSResources
    for eid,selected in payload.get('aws',{}).items():
     env=self.store.one('SELECT connection_id FROM environments WHERE id=?',(eid,))
     if not env or env['connection_id']!=c['id']:raise providers.CloudError('AWS 제어 연결 불일치')
     try:AWSResources(self.store,self.vault,self.stop).apply(eid,selected,action,job['id'])
     except providers.CloudError:failed+=1
    if payload.get('servers'):
     server_bulk(self.store,self.vault,c,payload['servers'],action,job['id'],self.stop)
     self.sync(c,secret)
    if failed:raise providers.CloudError(f'{failed}개 환경 작업·확인 실패 · 자원별 결과 확인')
    message='선택 자원 요청 처리 완료 · 실제 상태와 자원별 결과 확인'
   elif job['kind'] in ['NHN_IAM_PLAN','NHN_IAM_APPLY']:
    from .nhn_iam import IAM
    batch=self.store.one('SELECT connection_id FROM nhn_batches WHERE id=?',(job['target'],))
    if not batch or batch['connection_id']!=c['id'] or c['provider']!='NHN':raise providers.CloudError('IAM 연결 불일치')
    manager=IAM(self.store,self.vault,self.stop)
    if job['kind']=='NHN_IAM_PLAN':manager.plan(job['target']);message='IAM 계정 상태·실습 역할 조회 완료 · 실제 변경 없음'
    else:manager.apply(job['target']);message='IAM 실습 역할 검증 완료 · 비밀번호·기존 접속 정보 유지'
   elif job['kind'] in ['NHN_PLAN','NHN_ENABLE','NHN_APPLY','NHN_CLEANUP','NHN_SERVER_PLAN','NHN_SERVERS','NHN_IPS']:
    from .nhn_batch import Batch
    batch=self.store.one('SELECT connection_id FROM nhn_batches WHERE id=?',(job['target'],))
    if not batch or batch['connection_id']!=c['id'] or c['provider']!='NHN':raise providers.CloudError('NHN 일괄 작업 연결 불일치')
    manager=Batch(self.store,self.vault,self.stop)
    if job['kind'] in ['NHN_SERVER_PLAN','NHN_SERVERS','NHN_IPS']:
     from .nhn_servers import Servers
     servers=Servers(self.store,self.vault,self.stop)
     if job['kind']=='NHN_SERVER_PLAN':servers.plan(job['target']);message='서버 준비 계획 조회 완료 · 실제 생성 없음'
     elif job['kind']=='NHN_IPS':servers.repair_ips(job['target']);message='기존 학생 서버 플로팅 IP 일괄 할당·연결 확인 완료'
     else:
      if json.loads(job['payload']).get('prepare_iam'):
       from .nhn_iam import IAM
       iam=IAM(self.store,self.vault,self.stop);iam.plan(job['target']);iam.apply(job['target'])
      servers.apply(job['target'])
      current=self.store.one('SELECT state FROM nhn_batches WHERE id=?',(job['target'],))['state']
      if not current or not any(x.get('journal') for x in self.vault.open(current,'nhn-state:'+job['target']).values()):manager.plan(job['target'])
      manager.apply(job['target']);message='학생별 서버·컨테이너·선택 DB 준비 완료'
    elif job['kind']=='NHN_PLAN':manager.plan(job['target']);message='NHN 생성 계획 조회 완료 · 클라우드 자원 변경 없음'
    elif job['kind']=='NHN_ENABLE':manager.enable(job['target']);message='NHN 서비스 일괄 활성화 완료 · 계획 다시 조회를 누르세요.'
    elif job['kind']=='NHN_APPLY':manager.apply(job['target']);message='NHN 프로젝트 일괄 준비 완료'
    else:manager.cleanup(job['target']);message='NHN 소유 자원 정리 완료 · 기존 서버는 유지'
   elif job['kind'] in ['PROVISION','DESTROY','AWS_CHECK']:
    self.aws_lab(c,secret,job);message='AWS 사전 점검 통과 · VPC·EC2 vCPU·RDS 한도·MySQL 사양 확인 (생성 없음)' if job['kind']=='AWS_CHECK' else 'AWS 템플릿 작업 완료 · 동기화로 확인하세요.'
   else:raise providers.CloudError('지원하지 않는 작업')
   status='SUCCEEDED'
  except Exception as error:
   message=str(error) if isinstance(error,providers.CloudError) else '요청 실패: 인증정보·권한·연결 설정을 확인하세요. 비밀정보 보호를 위해 원문 오류는 저장하지 않습니다.'
   status='FAILED'
   if job['kind'] in ['SYNC','RESOURCE_REFRESH']:self.store.execute('UPDATE connections SET error=? WHERE id=?',(message,job['connection_id']))
  self.store.execute('UPDATE jobs SET status=?,updated=?,message=? WHERE id=?',(status,time.time(),message,job['id']));self.store.audit(job['actor'],'JOB_'+job['kind'],job['target'],status)
  return True
 def loop(self):
  self.store.execute("UPDATE jobs SET status='INTERRUPTED',message='서버 재시작으로 중단됨. 클라우드 상태 확인 후 수동 재요청하세요.',updated=? WHERE status='RUNNING'",(time.time(),))
  self.store.execute("UPDATE nhn_iam SET status='CHECK_REQUIRED' WHERE status='RUNNING'")
  last=0
  while not self.stop.is_set():
   if self.run_one():
    # Wait a full quiet interval after completed work; slow refreshes must not
    # immediately occupy every connection again and starve operator actions.
    last=time.time();continue
   if time.time()-last>=120:
    last=time.time();admin=self.store.one("SELECT id FROM users WHERE active=1 AND role='ADMIN' ORDER BY id LIMIT 1")
    if admin:
     for c in self.store.all('SELECT * FROM connections'):
      # New or failing credentials require an explicit operator check, not a retry loop.
      if not c['last_sync'] or c['error']:continue
      # Parent batch observations already cover these NHN child connections.
      if self.store.one("SELECT 1 FROM resource_observations o JOIN nhn_batches b ON b.id=o.batch_id JOIN resources r ON r.remote_id=o.remote_id WHERE r.connection_id=? AND o.kind='server' AND o.presence=1 AND o.updated>? AND b.connection_id!=? LIMIT 1",(c['id'],time.time()-300,c['id'])):continue
      if not self.store.one("SELECT id FROM jobs WHERE connection_id=? AND status IN ('QUEUED','RUNNING')",(c['id'],)):
       try:
        batches=self.store.all('SELECT id FROM nhn_batches WHERE connection_id=?',(c['id'],));envs=self.store.all('SELECT id FROM environments WHERE connection_id=?',(c['id'],))
        self.enqueue(admin['id'],c,'RESOURCE_REFRESH' if batches or envs else 'SYNC',c['id'],{'automatic':True,'batches':[b['id'] for b in batches],'environments':[e['id'] for e in envs]})
       except Exception:pass
   self.stop.wait(2)

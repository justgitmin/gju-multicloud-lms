import base64,contextlib,csv,datetime,io,json,os,re,secrets,sqlite3,threading,time,zipfile
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import RedirectResponse,JSONResponse,Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .store import Store
from .security import Vault,password_hash,verify_password,digest
from .jobs import Worker
from . import providers
COOKIE='cloudops_session'

def create_app(settings=None,start_worker=True):
 cfg=dict(os.environ if settings is None else settings);origin=cfg.get('OPS_ORIGIN','').rstrip('/');u=urlparse(origin);dev=cfg.get('OPS_DEV')=='1'
 if not u.hostname or u.path or u.query or u.fragment or u.username or (u.scheme!='https' and not(dev and u.scheme=='http' and u.hostname in ['127.0.0.1','localhost'])):raise ValueError('OPS_ORIGIN requires an HTTPS origin; local HTTP only with OPS_DEV=1')
 store=Store(Path(cfg.get('OPS_DATA_DIR','/data'))/'ops.sqlite3');vault=Vault(cfg.get('OPS_MASTER_KEY',''));worker=Worker(store,vault)
 @contextlib.asynccontextmanager
 async def lifespan(app):
  thread=None
  if start_worker:
   if not store.one('SELECT id FROM users WHERE active=1 AND role="ADMIN"'):raise RuntimeError('먼저 python -m cloudops.bootstrap으로 관리자를 만드세요.')
   thread=threading.Thread(target=worker.loop,daemon=True);thread.start()
  yield
  worker.stop.set()
 app=FastAPI(title='TBIT Cloud Ops',docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan);app.state.store=store;app.state.vault=vault;app.state.worker=worker
 dummy_hash=password_hash('dummy-not-a-user-'+secrets.token_hex(16))
 root=Path(__file__).parent;app.mount('/static',StaticFiles(directory=root/'static'),name='static');templates=Jinja2Templates(directory=root/'templates');templates.env.filters['kst']=lambda value:datetime.datetime.fromtimestamp(value,datetime.timezone(datetime.timedelta(hours=9))).strftime('%m/%d %H:%M:%S')
 def user(request,roles=None):
  token=request.cookies.get(COOKIE,'');row=store.one('SELECT u.*,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1',(digest(token),time.time())) if re.fullmatch('[0-9a-f]{64}',token) else None
  if not row:raise HTTPException(401,'로그인이 필요합니다.')
  if roles and row['role'] not in roles:store.audit(row['email'],'ACCESS_DENIED',request.url.path,'DENIED');raise HTTPException(403,'이 작업의 권한이 없습니다.')
  return row
 async def form(request,roles=None,anonymous=False):
  actor=None if anonymous else user(request,roles);data=await request.form(max_fields=40,max_files=0,max_part_size=100000)
  expected=request.cookies.get('cloudops_login_csrf','') if anonymous else actor['csrf']
  if not expected or not secrets.compare_digest(str(data.get('csrf','')),expected):raise HTTPException(403,'화면을 새로고침하고 다시 시도하세요.')
  return actor,data
 def csrf(actor):return actor['csrf'] if actor else secrets.token_hex(32)
 def redirect(target='/'):return RedirectResponse(target,303)
 def connection(id):
  c=store.one('SELECT * FROM connections WHERE id=?',(id,))
  if not c:raise HTTPException(404,'연결을 찾을 수 없습니다.')
  return c
 def queue(actor,c,kind,target):
  try:return worker.enqueue(actor['id'],c,kind,target)
  except sqlite3.IntegrityError:raise HTTPException(409,'이 연결에 실행 중인 작업이 있습니다. 완료 후 다시 요청하세요.')
 @app.middleware('http')
 async def protect(request,call_next):
  if request.url.path!='/health' and request.headers.get('host')!=u.netloc:return Response('잘못된 호스트',400)
  if request.method not in ['GET','HEAD','OPTIONS']:
   if request.headers.get('origin')!=origin:return Response('외부 출처 요청 차단',403)
   chunks=[];total=0
   async for chunk in request.stream():
    total+=len(chunk)
    if total>100000:return Response('요청이 너무 큽니다.',413)
    chunks.append(chunk)
   request._body=b''.join(chunks)
  response=await call_next(request);response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"})
  return response
 @app.exception_handler(HTTPException)
 async def error_page(request,error):
  if error.status_code==401 and not request.url.path.startswith('/api/'):return RedirectResponse('/login',303)
  return templates.TemplateResponse(request=request,name='error.html',context={'message':error.detail,'code':error.status_code},status_code=error.status_code)
 @app.get('/health')
 def health():return {'status':'ok'}
 @app.get('/login')
 def login_page(request:Request):
  token=csrf(None);response=templates.TemplateResponse(request=request,name='login.html',context={'csrf':token,'error':request.query_params.get('error')});response.set_cookie('cloudops_login_csrf',token,httponly=True,secure=not dev,samesite='strict',max_age=1800);return response
 @app.post('/login')
 async def login(request:Request):
  _,data=await form(request,anonymous=True);email=str(data.get('email','')).strip().lower();password=str(data.get('password',''))
  if not store.rate('login-global',300) or not store.rate('login:'+digest(email),10):raise HTTPException(429,'로그인 시도가 많습니다. 15분 후 다시 시도하세요.')
  actor=store.one('SELECT * FROM users WHERE email=? AND active=1',(email,));encoded=actor['password'] if actor else dummy_hash
  if not verify_password(password,encoded) or not actor:
   store.audit('anonymous','LOGIN',digest(email),'DENIED');return RedirectResponse('/login?error=1',303)
  token=secrets.token_hex(32);store.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),actor['id'],secrets.token_hex(32),time.time()+8*3600));store.execute('DELETE FROM sessions WHERE expires<?',(time.time(),));store.audit(email,'LOGIN')
  response=redirect();response.set_cookie(COOKIE,token,httponly=True,secure=not dev,samesite='strict',max_age=8*3600);response.delete_cookie('cloudops_login_csrf');return response
 @app.post('/logout')
 async def logout(request:Request):
  actor,_=await form(request);store.execute('DELETE FROM sessions WHERE token=?',(digest(request.cookies[COOKIE]),));store.audit(actor['email'],'LOGOUT');response=RedirectResponse('/login',303);response.delete_cookie(COOKIE);return response
 @app.get('/')
 def dashboard(request:Request):
  actor=user(request);connections=store.all('SELECT id,name,provider,region,account,writable,last_sync,error FROM connections ORDER BY name');resources=store.all('SELECT r.*,c.provider,c.name connection_name,e.name event_name FROM resources r JOIN connections c ON c.id=r.connection_id LEFT JOIN events e ON e.id=r.event_id ORDER BY r.missing,r.name')
  context={'user':actor,'csrf':csrf(actor),'connections':connections,'resources':resources,'nhn_batches':[{**b,'options':json.loads(b['config']),'bootstrap':store.one('SELECT status FROM nhn_bootstrap WHERE batch_id=?',(b['id'],)),'items':[{**i,'details':json.loads(i['summary'])} for i in store.all('SELECT student,summary,status,message FROM nhn_items WHERE batch_id=? ORDER BY student',(b['id'],))]} for b in store.all('SELECT id,name,config,planned FROM nhn_batches ORDER BY created DESC')] if actor['role']=='ADMIN' else [],'events':store.all('SELECT * FROM events ORDER BY created DESC'),'environments':store.all('SELECT e.id,e.lab_id,e.connection_id,e.config,c.name connection_name FROM environments e JOIN connections c ON c.id=e.connection_id ORDER BY e.created DESC'),'jobs':store.all('SELECT j.id,j.kind,j.target,j.status,j.message,j.updated,u.email FROM jobs j JOIN users u ON u.id=j.actor ORDER BY created DESC LIMIT 50'),'audits':store.all('SELECT * FROM audits ORDER BY id DESC LIMIT 50') if actor['role']=='ADMIN' else [],'users':store.all('SELECT id,email,name,role,active FROM users ORDER BY id') if actor['role']=='ADMIN' else []}
  return templates.TemplateResponse(request=request,name='dashboard.html',context=context)
 @app.get('/api/overview')
 def overview(request:Request):
  user(request);return {'resources':store.all('SELECT id,state,ip,seen,missing FROM resources'),'jobs':store.all('SELECT id,status,message FROM jobs ORDER BY created DESC LIMIT 50')}
 @app.post('/connections')
 async def add_connection(request:Request):
  actor,d=await form(request,['ADMIN']);provider=str(d.get('provider'));name=str(d.get('name','')).strip();region=str(d.get('region','')).strip();account=str(d.get('account','')).strip();id=secrets.token_hex(16)
  if not 1<=len(name)<=100:raise HTTPException(400,'연결 이름은 1~100자입니다.')
  if provider=='AWS':
   if not re.fullmatch('[0-9]{12}',account) or not re.fullmatch('[a-z]{2}-[a-z]+-[0-9]',region):raise HTTPException(400,'AWS 계정 ID·리전 형식 확인')
   secret={k:str(d.get(k,'')) for k in ['access_key','secret_key','session_token']}
   if bool(secret['access_key'])!=bool(secret['secret_key']):raise HTTPException(400,'AWS Access Key와 Secret Key를 함께 입력하세요.')
   if secret['session_token'] and not secret['access_key']:raise HTTPException(400,'Session Token은 키와 함께 입력하세요.')
  elif provider=='NHN':
   if not re.fullmatch('[a-zA-Z0-9-]{16,64}',account) or region not in ['KR1','KR2','JP1','US1']:raise HTTPException(400,'NHN Tenant ID·리전 확인')
   secret={k:str(d.get(k,'')) for k in ['username','api_password']}
   if not all(secret.values()):raise HTTPException(400,'NHN IAM ID와 API 비밀번호를 입력하세요.')
  elif provider=='NCP':
   if region not in ['KR','SGN','JPN'] or not 1<=len(account)<=100:raise HTTPException(400,'NAVER 계정 별칭·리전 확인')
   secret={k:str(d.get(k,'')) for k in ['access_key','secret_key']}
   if not all(secret.values()):raise HTTPException(400,'NAVER API 키를 입력하세요.')
  else:raise HTTPException(400,'지원하지 않는 클라우드')
  if any(len(v)>4096 for v in secret.values()):raise HTTPException(400,'인증정보 입력이 너무 깁니다.')
  store.execute('INSERT INTO connections(id,name,provider,region,account,secret,writable) VALUES(?,?,?,?,?,?,?)',(id,name,provider,region,account,vault.seal(secret,'connection:'+id),int(d.get('writable')=='on')));store.audit(actor['email'],'CONNECTION_CREATE',id);return redirect(f'/?saved={id}#connection-{id}')
 @app.post('/connections/{id}/security')
 async def connection_security(request:Request,id:str):
  actor,d=await form(request,['ADMIN']);c=connection(id)
  if not verify_password(str(d.get('admin_password','')),actor['password']):raise HTTPException(403,'관리자 비밀번호 확인')
  fields=['username','api_password'] if c['provider']=='NHN' else ['access_key','secret_key']+(['session_token'] if c['provider']=='AWS' else [])
  entered={key:str(d.get(key,'')) for key in fields}
  if any(len(v)>4096 for v in entered.values()):raise HTTPException(400,'입력값이 너무 깁니다.')
  if any(entered.values()):
   if not all(entered[k] for k in fields[:2]):raise HTTPException(400,'인증정보의 필수 항목을 모두 입력하세요.')
   encrypted=vault.seal(entered,'connection:'+id)
  else:encrypted=c['secret']
  if store.one("SELECT id FROM jobs WHERE connection_id=? AND status='RUNNING'",(id,)):raise HTTPException(409,'실행 중인 작업이 끝난 뒤 변경하세요.')
  store.execute('UPDATE connections SET secret=?,writable=?,revision=revision+1 WHERE id=?',(encrypted,int(d.get('writable')=='on'),id));store.audit(actor['email'],'CONNECTION_SECURITY_UPDATE',id);return redirect(f'/?saved={id}#connection-{id}')
 @app.post('/connections/{id}/sync')
 async def sync(request:Request,id:str):
  actor,_=await form(request,['ADMIN','OPERATOR']);queue(actor,connection(id),'SYNC',id);return redirect(f'/#connection-{id}')
 @app.post('/events')
 async def add_event(request:Request):
  actor,d=await form(request,['ADMIN','OPERATOR']);name=str(d.get('name','')).strip();ends=str(d.get('ends',''))
  if not 1<=len(name)<=100:raise HTTPException(400,'교육 이름 확인')
  try:datetime.date.fromisoformat(ends)
  except ValueError:raise HTTPException(400,'종료일 확인')
  id=secrets.token_hex(16);store.execute('INSERT INTO events VALUES(?,?,?,?)',(id,name,ends,time.time()));store.audit(actor['email'],'EVENT_CREATE',id);return redirect('/#events')
 @app.post('/resources/{id}/assign')
 async def assign(request:Request,id:str):
  actor,d=await form(request,['ADMIN','OPERATOR']);event=str(d.get('event_id',''));owner=str(d.get('owner','')).strip()
  if len(owner)>100 or not store.one('SELECT id FROM events WHERE id=?',(event,)) or not store.one('SELECT id FROM resources WHERE id=?',(id,)):raise HTTPException(400,'교육·자원·담당자 확인')
  store.execute('UPDATE resources SET event_id=?,owner=? WHERE id=?',(event,owner,id));store.audit(actor['email'],'RESOURCE_ASSIGN',id);return redirect('/#resources')
 @app.post('/resources/{id}/action')
 async def resource_action(request:Request,id:str):
  actor,d=await form(request,['ADMIN','OPERATOR']);r=store.one('SELECT * FROM resources WHERE id=?',(id,));kind=str(d.get('kind',''))
  if not r or not r['event_id'] or r['missing'] or kind not in ['START','STOP']:raise HTTPException(400,'교육에 배정된 자원과 작업을 확인하세요.')
  c=connection(r['connection_id'])
  if not c['writable'] or d.get('confirm')!=r['remote_id']:raise HTTPException(400,'변경 허용 설정과 정확한 서버 ID 확인 문구가 필요합니다.')
  queue(actor,c,kind,id);return redirect('/#jobs')
 @app.post('/resources/{id}/metrics')
 async def metrics(request:Request,id:str):
  actor,_=await form(request);r=store.one('SELECT * FROM resources WHERE id=?',(id,))
  if not r:raise HTTPException(404,'자원 없음')
  c=connection(r['connection_id'])
  try:result=providers.adapter(c,vault.open(c['secret'],'connection:'+c['id'])).metrics(r['remote_id'])
  except Exception:raise HTTPException(502,'지표를 가져오지 못했습니다. 연결·권한·수집 설정을 확인하세요.')
  store.audit(actor['email'],'METRICS_READ',id);return templates.TemplateResponse(request=request,name='metrics.html',context={'resource':r,'metrics':result})
 @app.post('/environments')
 async def environment(request:Request):
  actor,d=await form(request,['ADMIN']);c=connection(str(d.get('connection_id','')));lab=str(d.get('lab_id',''));event=str(d.get('event_id',''))
  if c['provider']!='AWS' or c['region']!='ap-northeast-2' or not re.fullmatch('[a-z][a-z0-9-]{2,24}',lab) or not store.one('SELECT id FROM events WHERE id=?',(event,)):raise HTTPException(400,'AWS 서울 연결·교육·환경 이름을 확인하세요.')
  try:count=int(str(d.get('count','1')));volume=int(str(d.get('volume','20')))
  except ValueError:raise HTTPException(400,'학생 수·디스크 숫자 확인')
  instance=str(d.get('instance','t3.micro'))
  if not 1<=count<=30 or not 8<=volume<=30 or instance not in ['t3.micro','t3.small']:raise HTTPException(400,'학생 1~30명, 디스크 8~30GB, 허용 사양을 선택하세요.')
  config={'lab_id':lab,'region':'ap-northeast-2','students':[f's{i:02}' for i in range(1,count+1)],'instance_type':instance,'volume_gb':volume,'s3':d.get('s3')=='on','rds':d.get('rds')=='on','db_class':'db.t4g.micro','ami_parameter':'/aws/service/canonical/ubuntu/server/noble/stable/current/amd64/hvm/ebs-gp3/ami-id','access_mode':'ssm'}
  id=secrets.token_hex(16)
  try:store.execute('INSERT INTO environments(id,connection_id,event_id,lab_id,config,created) VALUES(?,?,?,?,?,?)',(id,c['id'],event,lab,json.dumps(config),time.time()))
  except sqlite3.IntegrityError:raise HTTPException(409,'이미 사용 중인 환경 이름입니다.')
  store.audit(actor['email'],'ENVIRONMENT_PLAN',id);return redirect('/#provision')
 @app.post('/environments/{id}/action')
 async def environment_action(request:Request,id:str):
  actor,d=await form(request,['ADMIN']);e=store.one('SELECT * FROM environments WHERE id=?',(id,));kind=str(d.get('kind',''))
  if not e or kind not in ['PROVISION','DESTROY']:raise HTTPException(400,'환경·작업 확인')
  c=connection(e['connection_id'])
  if not c['writable'] or d.get('confirm')!=e['lab_id'] or d.get('account')!=c['account']:raise HTTPException(400,'환경 이름·AWS 계정 ID 확인 문구와 변경 허용 설정이 필요합니다.')
  if kind=='PROVISION' and e['state']:raise HTTPException(409,'생성 기록이 있는 환경입니다. 현재 상태를 확인하고 추가 학생은 새 환경 이름으로 준비하세요.')
  queue(actor,c,kind,id);return redirect('/#jobs')
 @app.post('/environments/{id}/student')
 async def student_download(request:Request,id:str):
  actor,d=await form(request,['ADMIN']);e=store.one('SELECT * FROM environments WHERE id=?',(id,));student=str(d.get('student',''))
  if not verify_password(str(d.get('password','')),actor['password']) or not e or not e['state'] or not re.fullmatch('s[0-9]{2}',student):raise HTTPException(403,'비밀번호·환경·학생을 확인하세요.')
  prefix=e['lab_id']+'-'+student+'/'
  files=vault.open(e['state'],'state:'+id);selected={k:v for k,v in files.items() if k.startswith(prefix) and k.endswith(('/credentials.json','/outputs.json'))}
  if not selected:raise HTTPException(404,'해당 학생의 접속 자료가 없습니다.')
  buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,'w') as z:
   for path,value in selected.items():z.writestr(path,base64.b64decode(value))
  store.audit(actor['email'],'STUDENT_SECRET_DOWNLOAD',id+':'+student)
  return Response(buffer.getvalue(),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="{student}-private-access.zip"'})
 @app.post('/nhn/batches')
 async def nhn_batch_create(request:Request):
  actor,d=await form(request,['ADMIN']);c=connection(str(d.get('connection_id','')));event=str(d.get('event_id',''));name=str(d.get('name','')).strip()
  if c['provider']!='NHN' or c['region'] not in ['KR1','KR2','JP1'] or not store.one('SELECT id FROM events WHERE id=?',(event,)):raise HTTPException(400,'NHN 연결·교육을 선택하세요.')
  if not 1<=len(name)<=80:raise HTTPException(400,'일괄 작업 이름은 1~80자입니다.')
  try:first=int(str(d.get('first','1')));last=int(str(d.get('last','10')))
  except ValueError:raise HTTPException(400,'학생 번호는 숫자로 입력하세요.')
  if not 1<=first<=last<=30:raise HTTPException(400,'학생 번호 범위는 1~30입니다.')
  config={k:str(d.get(k,'')).strip() for k in ['org','project_prefix','server_prefix','lab_prefix','db_flavor','db_version']}
  if not re.fullmatch('[A-Za-z0-9_-]{8,32}',config['org']) or any(not re.fullmatch('[A-Za-z][A-Za-z0-9_-]{1,40}',config[k]) for k in ['project_prefix','server_prefix']) or not re.fullmatch('[a-z][a-z0-9-]{2,24}',config['lab_prefix']):raise HTTPException(400,'조직 ID·프로젝트/서버 접두사·자원 이름 확인')
  config.update({'first':first,'last':last,'db':d.get('db')=='on','region':c['region'],'connection_revision':c['revision']})
  if config['db'] and ((config['db_flavor'] and not re.fullmatch('[a-zA-Z0-9.]{1,40}',config['db_flavor'])) or (config['db_version'] and not re.fullmatch('MYSQL_V[0-9]{3,8}',config['db_version']))):raise HTTPException(400,'RDS 사양과 API 버전 코드를 입력하세요.')
  secret=vault.open(c['secret'],'connection:'+c['id']);secret.update({k:str(d.get(k,'')) for k in ['access_key','secret_key']})
  if any(not 8<=len(secret[k])<=256 or not re.fullmatch('[!-~]+',secret[k]) for k in ['access_key','secret_key']):raise HTTPException(400,'운영자 User Access Key와 Secret 원문을 입력하세요. 공백은 허용하지 않습니다.')
  id=secrets.token_hex(16)
  try:
   with store.connect() as db:
    db.execute('INSERT INTO nhn_batches(id,connection_id,event_id,name,config,secret,created) VALUES(?,?,?,?,?,?,?)',(id,c['id'],event,name,json.dumps(config),vault.seal(secret,'nhn-batch:'+id),time.time()))
    db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',(secrets.token_hex(16),actor['id'],c['id'],c['revision'],'NHN_PLAN',id,'{}','QUEUED',time.time(),time.time(),'일괄 계획 조회 대기'))
  except sqlite3.IntegrityError:raise HTTPException(409,'같은 이름의 계획 또는 실행 중인 연결 작업이 있습니다.')
  store.audit(actor['email'],'NHN_BATCH_PLAN',id);return redirect('/#nhn-batch-'+id)
 @app.post('/nhn/batches/{id}/action')
 async def nhn_batch_action(request:Request,id:str):
  actor,d=await form(request,['ADMIN']);b=store.one('SELECT * FROM nhn_batches WHERE id=?',(id,));kind=str(d.get('kind',''))
  if not b or kind not in ['NHN_PLAN','NHN_ENABLE','NHN_APPLY','NHN_CLEANUP']:raise HTTPException(400,'NHN 일괄 작업 확인')
  c=connection(b['connection_id'])
  if kind!='NHN_PLAN':
   if not c['writable'] or d.get('confirm')!=b['name']:raise HTTPException(400,'변경 허용과 일괄 작업 이름 확인이 필요합니다.')
   if not verify_password(str(d.get('password','')),actor['password']):raise HTTPException(403,'Cloud Ops 관리자 비밀번호를 확인하세요.')
  items=store.all('SELECT status FROM nhn_items WHERE batch_id=?',(id,))
  if kind=='NHN_APPLY' and (not items or any(x['status'] in ['BLOCKED','SERVICES_ENABLED','CLEANED','CLEANING','CLEANUP_FAILED'] for x in items) or not b['planned']):raise HTTPException(409,'차단 항목 없는 생성 계획이 먼저 필요합니다.')
  if kind=='NHN_APPLY' and all(x['status']=='PLANNED' for x in items) and time.time()-b['planned']>3600:raise HTTPException(409,'생성 계획이 1시간 지났습니다. 다시 조회하세요.')
  if kind=='NHN_PLAN' and b['state']:
   state=vault.open(b['state'],'nhn-state:'+id)
   if any(x.get('journal') for x in state.values()):raise HTTPException(409,'생성 기록이 있어 계획을 덮어쓸 수 없습니다. 실패 항목 재시도를 사용하세요.')
  queue(actor,c,kind,id);return redirect('/#nhn-batch-'+id)
 @app.post('/nhn/batches/{id}/servers/plan')
 async def nhn_servers_plan(request:Request,id:str):
  actor,d=await form(request,['ADMIN']);b=store.one('SELECT * FROM nhn_batches WHERE id=?',(id,))
  if not b:raise HTTPException(404,'NHN 계획을 찾을 수 없습니다.')
  c=connection(b['connection_id']);config=json.loads(b['config'])
  try:last=int(str(d.get('last','14')))
  except ValueError:raise HTTPException(400,'학생 수는 숫자입니다.')
  if not 1<=last<=30:raise HTTPException(400,'학생 수는 1~30명입니다.')
  second_org=str(d.get('second_org','')).strip();second_prefix=str(d.get('second_prefix','')).strip()
  if second_org or second_prefix:
   if not re.fullmatch('[A-Za-z0-9_-]{1,80}',second_org) or not re.fullmatch('[A-Za-z0-9_-]{1,64}',second_prefix) or last<=10:raise HTTPException(400,'두 번째 조직 ID·프로젝트 접두사·학생 수를 확인하세요.')
   config['project_scopes']=[{'first':1,'last':10,'org':config['org'],'prefix':config['project_prefix']},{'first':11,'last':last,'org':second_org,'prefix':second_prefix}]
  else:
   config.pop('project_scopes',None)
   if last>10:raise HTTPException(400,'11명 이상이면 두 번째 조직과 프로젝트 접두사가 필요합니다.')
  config['public_lab_ports']=d.get('public_lab_ports')=='on'
  roster={}
  for row in csv.reader(io.StringIO(str(d.get('roster','')))):
   if not row or not any(x.strip() for x in row):continue
   if len(row)!=3:raise HTTPException(400,'명단은 학생코드,이름,이메일 형식입니다.')
   code,name,email=[x.strip() for x in row]
   if not re.fullmatch('s[0-9]{2}',code) or not 1<=int(code[1:])<=last or code in roster or not 1<=len(name)<=50 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254:raise HTTPException(400,'명단 코드·이름·이메일·중복을 확인하세요.')
   roster[code]={'name':name,'email':email}
  if len(roster)!=last:raise HTTPException(400,'학생 수와 명단 행 수가 같아야 합니다.')
  with store.connect() as db:
   db.execute('BEGIN IMMEDIATE')
   if db.execute("SELECT id FROM jobs WHERE connection_id=? AND status IN ('QUEUED','RUNNING')",(c['id'],)).fetchone():raise HTTPException(409,'실행 중 작업이 끝난 뒤 계획을 만드세요.')
   boot=db.execute('SELECT state FROM nhn_bootstrap WHERE batch_id=?',(id,)).fetchone()
   if boot and boot['state'] and any(x.get('journal') for x in vault.open(boot['state'],'nhn-servers:'+id).get('students',{}).values()):raise HTTPException(409,'서버 생성 기록이 있습니다. 기존 계획을 재시도하세요.')
   if b['state'] and any(x.get('journal') for x in vault.open(b['state'],'nhn-state:'+id).values()):raise HTTPException(409,'저장소/DB 생성 이력이 있습니다. 새 일괄 계획을 사용하세요.')
   config.update({'first':1,'last':last});db.execute("UPDATE nhn_batches SET config=?,state='',planned=NULL WHERE id=?",(json.dumps(config),id));db.execute('DELETE FROM nhn_items WHERE batch_id=?',(id,))
   db.execute("INSERT INTO nhn_bootstrap(batch_id,config,updated) VALUES(?,?,?) ON CONFLICT(batch_id) DO UPDATE SET config=excluded.config,state='',status='QUEUED',updated=excluded.updated",(id,json.dumps({'roster':roster},ensure_ascii=False),time.time()))
   db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',(secrets.token_hex(16),actor['id'],c['id'],c['revision'],'NHN_SERVER_PLAN',id,'{}','QUEUED',time.time(),time.time(),'서버 준비 계획 조회 대기'))
  store.audit(actor['email'],'NHN_SERVER_PLAN',id);return redirect('/#nhn-batch-'+id)
 @app.post('/nhn/batches/{id}/servers/apply')
 async def nhn_servers_apply(request:Request,id:str):
  actor,d=await form(request,['ADMIN']);b=store.one('SELECT * FROM nhn_batches WHERE id=?',(id,));boot=store.one('SELECT * FROM nhn_bootstrap WHERE batch_id=?',(id,))
  if not b or not boot or not boot['state'] or d.get('confirm')!=b['name'] or not verify_password(str(d.get('password','')),actor['password']):raise HTTPException(403,'계획·작업 이름·Cloud Ops 관리자 비밀번호를 확인하세요.')
  c=connection(b['connection_id'])
  if not c['writable']:raise HTTPException(400,'변경 작업 허용이 필요합니다.')
  kind='NHN_IPS' if d.get('kind')=='NHN_IPS' else 'NHN_SERVERS'
  queue(actor,c,kind,id);return redirect('/#nhn-batch-'+id)
 @app.post('/nhn/batches/{id}/servers/student')
 async def nhn_server_student(request:Request,id:str):
  actor,d=await form(request,['ADMIN']);boot=store.one('SELECT * FROM nhn_bootstrap WHERE batch_id=?',(id,));code=str(d.get('student',''))
  if not boot or not boot['state'] or not verify_password(str(d.get('password','')),actor['password']):raise HTTPException(403,'계획·Cloud Ops 관리자 비밀번호 확인')
  state=vault.open(boot['state'],'nhn-servers:'+id);item=state.get('students',{}).get(code)
  if not item or not item.get('ready'):raise HTTPException(409,'서버 준비 완료한 학생만 내려받을 수 있습니다.')
  access={**item['person'],'student':code,'project':item['summary']['project'],'server':item['summary']['server_name'],'public_ip':item['summary']['ip'],'ssh_user':'ubuntu','key_file':item.get('key_name','기존 개인 키')+'.pem','ssh_allowed_cidrs':[r.get('remote_ip_prefix') for r in state['template']['rules'] if r.get('direction')=='ingress' and (r.get('port_range_min')==22 or not r.get('protocol'))],'note':'SSH 허용 IP에 학생 PC의 공인 IP가 포함돼야 합니다. NHN IAM 로그인과 이 PEM 키는 별개입니다.'}
  buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,'w') as z:
   z.writestr(code+'/access.json',json.dumps(access,ensure_ascii=False,indent=2))
   if item.get('key_material'):z.writestr(code+'/'+item['key_name']+'.pem',item['key_material']['private'])
  store.audit(actor['email'],'NHN_SERVER_STUDENT_DOWNLOAD',id+':'+code)
  return Response(buffer.getvalue(),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="{code}-nhn-server-access.zip"'})
 @app.post('/nhn/batches/{id}/credentials')
 async def nhn_batch_credentials(request:Request,id:str):
  actor,d=await form(request,['ADMIN']);b=store.one('SELECT * FROM nhn_batches WHERE id=?',(id,))
  if not b or not verify_password(str(d.get('password','')),actor['password']):raise HTTPException(403,'Cloud Ops 관리자 비밀번호·계획을 확인하세요.')
  c=connection(b['connection_id'])
  key=str(d.get('access_key',''));secret_key=str(d.get('secret_key',''))
  if bool(key)!=bool(secret_key) or any(not 8<=len(x)<=256 or not re.fullmatch('[!-~]+',x) for x in [key,secret_key] if x):raise HTTPException(400,'운영자 키 두 항목을 함께 입력하세요.')
  with store.connect() as db:
   db.execute('BEGIN IMMEDIATE')
   if db.execute("SELECT id FROM jobs WHERE connection_id=? AND status IN ('QUEUED','RUNNING')",(c['id'],)).fetchone():raise HTTPException(409,'연결 작업 완료 후 인증정보를 갱신하세요.')
   secret=vault.open(b['secret'],'nhn-batch:'+id);secret.update({k:v for k,v in vault.open(c['secret'],'connection:'+c['id']).items() if k in ['username','api_password']})
   if key:secret.update({'access_key':key,'secret_key':secret_key})
   config=json.loads(b['config']);config['connection_revision']=c['revision']
   db.execute('UPDATE nhn_batches SET secret=?,config=? WHERE id=?',(vault.seal(secret,'nhn-batch:'+id),json.dumps(config),id))
  store.audit(actor['email'],'NHN_BATCH_CREDENTIAL_UPDATE',id);return redirect('/#nhn-batch-'+id)
 @app.post('/nhn/batches/{id}/student')
 async def nhn_student_download(request:Request,id:str):
  actor,d=await form(request,['ADMIN']);b=store.one('SELECT * FROM nhn_batches WHERE id=?',(id,));student=str(d.get('student',''))
  if not b or not b['state'] or not verify_password(str(d.get('password','')),actor['password']):raise HTTPException(403,'Cloud Ops 관리자 비밀번호·계획을 확인하세요.')
  item=vault.open(b['state'],'nhn-state:'+id).get(student);row=store.one('SELECT status FROM nhn_items WHERE batch_id=? AND student=?',(id,student))
  if not item or not row or row['status']!='READY':raise HTTPException(409,'준비 완료한 학생만 안내를 내려받을 수 있습니다.')
  summary=item['summary'];access={'project':summary['project'],'server':summary['server_name'],'server_ip':summary['ip'],'ssh_user':'ubuntu','container':summary['container'],**item.get('access',{}),'note':'IAM 로그인·해당 서버 PEM 키는 기존 개별 안내를 사용하세요. 비밀번호와 키를 과제로 제출하지 마세요.'}
  store.audit(actor['email'],'NHN_STUDENT_DOWNLOAD',id+':'+student)
  return Response(json.dumps(access,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="{student}-nhn-private-access.json"'})
 @app.post('/users')
 async def create_user(request:Request):
  actor,d=await form(request,['ADMIN']);email=str(d.get('email','')).strip().lower();name=str(d.get('name','')).strip();role=str(d.get('role',''))
  if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254 or not 1<=len(name)<=60 or role not in ['ADMIN','OPERATOR','VIEWER']:raise HTTPException(400,'사용자 입력 확인')
  try:encoded=password_hash(str(d.get('password','')));store.execute('INSERT INTO users(email,name,password,role) VALUES(?,?,?,?)',(email,name,encoded,role))
  except ValueError:raise HTTPException(400,'비밀번호는 12~128자입니다.')
  except sqlite3.IntegrityError:raise HTTPException(409,'이미 등록된 이메일입니다.')
  store.audit(actor['email'],'USER_CREATE',email);return redirect('/#users')
 @app.post('/users/{id}/disable')
 async def disable_user(request:Request,id:int):
  actor,_=await form(request,['ADMIN'])
  if id==actor['id']:raise HTTPException(400,'본인 계정은 중지할 수 없습니다.')
  with store.connect() as db:db.execute('UPDATE users SET active=0 WHERE id=?',(id,));db.execute('DELETE FROM sessions WHERE user_id=?',(id,))
  store.audit(actor['email'],'USER_DISABLE',id);return redirect('/#users')
 @app.post('/password')
 async def change_password(request:Request):
  actor,d=await form(request)
  if not verify_password(str(d.get('current','')),actor['password']):raise HTTPException(403,'현재 비밀번호 확인')
  try:encoded=password_hash(str(d.get('password','')))
  except ValueError:raise HTTPException(400,'비밀번호는 12~128자입니다.')
  with store.connect() as db:db.execute('UPDATE users SET password=? WHERE id=?',(encoded,actor['id']));db.execute('DELETE FROM sessions WHERE user_id=?',(actor['id'],))
  store.audit(actor['email'],'PASSWORD_CHANGE');response=RedirectResponse('/login',303);response.delete_cookie(COOKIE);return response
 return app

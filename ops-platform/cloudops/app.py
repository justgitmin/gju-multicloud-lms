import base64,contextlib,datetime,io,json,os,re,secrets,sqlite3,threading,time,zipfile
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
 def redirect():return RedirectResponse('/',303)
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
  actor=store.one('SELECT * FROM users WHERE email=? AND active=1',(email,));encoded=actor['password'] if actor else password_hash('not-a-valid-login-'+secrets.token_hex(16))
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
  context={'user':actor,'csrf':csrf(actor),'connections':connections,'resources':resources,'events':store.all('SELECT * FROM events ORDER BY created DESC'),'environments':store.all('SELECT e.id,e.lab_id,e.connection_id,e.config,c.name connection_name FROM environments e JOIN connections c ON c.id=e.connection_id ORDER BY e.created DESC'),'jobs':store.all('SELECT j.id,j.kind,j.target,j.status,j.message,j.updated,u.email FROM jobs j JOIN users u ON u.id=j.actor ORDER BY created DESC LIMIT 50'),'audits':store.all('SELECT * FROM audits ORDER BY id DESC LIMIT 50') if actor['role']=='ADMIN' else [],'users':store.all('SELECT id,email,name,role,active FROM users ORDER BY id') if actor['role']=='ADMIN' else []}
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
  store.execute('INSERT INTO connections(id,name,provider,region,account,secret,writable) VALUES(?,?,?,?,?,?,?)',(id,name,provider,region,account,vault.seal(secret,'connection:'+id),int(d.get('writable')=='on')));store.audit(actor['email'],'CONNECTION_CREATE',id);return redirect()
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
  store.execute('UPDATE connections SET secret=?,writable=?,revision=revision+1 WHERE id=?',(encrypted,int(d.get('writable')=='on'),id));store.audit(actor['email'],'CONNECTION_SECURITY_UPDATE',id);return redirect()
 @app.post('/connections/{id}/sync')
 async def sync(request:Request,id:str):
  actor,_=await form(request,['ADMIN','OPERATOR']);queue(actor,connection(id),'SYNC',id);return redirect()
 @app.post('/events')
 async def add_event(request:Request):
  actor,d=await form(request,['ADMIN','OPERATOR']);name=str(d.get('name','')).strip();ends=str(d.get('ends',''))
  if not 1<=len(name)<=100:raise HTTPException(400,'교육 이름 확인')
  try:datetime.date.fromisoformat(ends)
  except ValueError:raise HTTPException(400,'종료일 확인')
  id=secrets.token_hex(16);store.execute('INSERT INTO events VALUES(?,?,?,?)',(id,name,ends,time.time()));store.audit(actor['email'],'EVENT_CREATE',id);return redirect()
 @app.post('/resources/{id}/assign')
 async def assign(request:Request,id:str):
  actor,d=await form(request,['ADMIN','OPERATOR']);event=str(d.get('event_id',''));owner=str(d.get('owner','')).strip()
  if len(owner)>100 or not store.one('SELECT id FROM events WHERE id=?',(event,)) or not store.one('SELECT id FROM resources WHERE id=?',(id,)):raise HTTPException(400,'교육·자원·담당자 확인')
  store.execute('UPDATE resources SET event_id=?,owner=? WHERE id=?',(event,owner,id));store.audit(actor['email'],'RESOURCE_ASSIGN',id);return redirect()
 @app.post('/resources/{id}/action')
 async def resource_action(request:Request,id:str):
  actor,d=await form(request,['ADMIN','OPERATOR']);r=store.one('SELECT * FROM resources WHERE id=?',(id,));kind=str(d.get('kind',''))
  if not r or not r['event_id'] or r['missing'] or kind not in ['START','STOP']:raise HTTPException(400,'교육에 배정된 자원과 작업을 확인하세요.')
  c=connection(r['connection_id'])
  if not c['writable'] or d.get('confirm')!=r['remote_id']:raise HTTPException(400,'변경 허용 설정과 정확한 서버 ID 확인 문구가 필요합니다.')
  queue(actor,c,kind,id);return redirect()
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
  store.audit(actor['email'],'ENVIRONMENT_PLAN',id);return redirect()
 @app.post('/environments/{id}/action')
 async def environment_action(request:Request,id:str):
  actor,d=await form(request,['ADMIN']);e=store.one('SELECT * FROM environments WHERE id=?',(id,));kind=str(d.get('kind',''))
  if not e or kind not in ['PROVISION','DESTROY']:raise HTTPException(400,'환경·작업 확인')
  c=connection(e['connection_id'])
  if not c['writable'] or d.get('confirm')!=e['lab_id'] or d.get('account')!=c['account']:raise HTTPException(400,'환경 이름·AWS 계정 ID 확인 문구와 변경 허용 설정이 필요합니다.')
  if kind=='PROVISION' and e['state']:raise HTTPException(409,'생성 기록이 있는 환경입니다. 현재 상태를 확인하고 추가 학생은 새 환경 이름으로 준비하세요.')
  queue(actor,c,kind,id);return redirect()
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
 @app.post('/users')
 async def create_user(request:Request):
  actor,d=await form(request,['ADMIN']);email=str(d.get('email','')).strip().lower();name=str(d.get('name','')).strip();role=str(d.get('role',''))
  if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254 or not 1<=len(name)<=60 or role not in ['ADMIN','OPERATOR','VIEWER']:raise HTTPException(400,'사용자 입력 확인')
  try:encoded=password_hash(str(d.get('password','')));store.execute('INSERT INTO users(email,name,password,role) VALUES(?,?,?,?)',(email,name,encoded,role))
  except ValueError:raise HTTPException(400,'비밀번호는 12~128자입니다.')
  except sqlite3.IntegrityError:raise HTTPException(409,'이미 등록된 이메일입니다.')
  store.audit(actor['email'],'USER_CREATE',email);return redirect()
 @app.post('/users/{id}/disable')
 async def disable_user(request:Request,id:int):
  actor,_=await form(request,['ADMIN'])
  if id==actor['id']:raise HTTPException(400,'본인 계정은 중지할 수 없습니다.')
  with store.connect() as db:db.execute('UPDATE users SET active=0 WHERE id=?',(id,));db.execute('DELETE FROM sessions WHERE user_id=?',(id,))
  store.audit(actor['email'],'USER_DISABLE',id);return redirect()
 @app.post('/password')
 async def change_password(request:Request):
  actor,d=await form(request)
  if not verify_password(str(d.get('current','')),actor['password']):raise HTTPException(403,'현재 비밀번호 확인')
  try:encoded=password_hash(str(d.get('password','')))
  except ValueError:raise HTTPException(400,'비밀번호는 12~128자입니다.')
  with store.connect() as db:db.execute('UPDATE users SET password=? WHERE id=?',(encoded,actor['id']));db.execute('DELETE FROM sessions WHERE user_id=?',(actor['id'],))
  store.audit(actor['email'],'PASSWORD_CHANGE');response=RedirectResponse('/login',303);response.delete_cookie(COOKIE);return response
 return app

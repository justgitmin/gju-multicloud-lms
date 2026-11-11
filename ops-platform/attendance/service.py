"""Read-only attendance evidence UI. Actual login capture lives in PostgreSQL triggers.
No LMS web or Ops worker restart is required. No cookies or passwords enter reports.
"""
import csv,datetime,hashlib,html,io,os,re,sqlite3,time
from contextlib import closing
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import HTMLResponse,RedirectResponse,Response
import psycopg
from psycopg.rows import dict_row
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
KST=datetime.timezone(datetime.timedelta(hours=9))
LABELS={'LOGIN':'실제 로그인','LEARNING_ACTIVITY':'실제 학습 요청','MANUAL_ATTENDANCE':'운영자 수동 출석'}
def actor(request):
 token=request.cookies.get('cloudops_session','')
 if not re.fullmatch('[a-f0-9]{64}',token):raise HTTPException(401)
 with closing(sqlite3.connect('file:/ops-data/ops.sqlite3?mode=ro',uri=True)) as db:
  db.row_factory=sqlite3.Row
  row=db.execute('SELECT u.id,u.email,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
 if not row:raise HTTPException(401)
 if row['role']!='ADMIN':raise HTTPException(403)
 return row
@app.exception_handler(HTTPException)
async def denied(request,error):
 if error.status_code==401:return RedirectResponse('/login',303)
 return Response('관리자 권한이 필요합니다.',status_code=error.status_code)
@app.middleware('http')
async def headers(request,call_next):
 response=await call_next(request)
 response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'",'Referrer-Policy':'same-origin'})
 return response

def dates(day):
 try:date=datetime.date.fromisoformat(day)
 except ValueError:raise HTTPException(400,'날짜 형식 오류')
 start=datetime.datetime.combine(date,datetime.time(),KST)
 return start,start+datetime.timedelta(days=1)

def report(day):
 start,end=dates(day)
 with psycopg.connect(os.environ['ATTENDANCE_DATABASE_URL'],connect_timeout=5,options='-c default_transaction_read_only=on -c statement_timeout=5000',row_factory=dict_row) as db:
  rows=db.execute('''SELECT u.name,u.email,u."studentNumber",e.kind,e."eventAt",e."recordedAt",e."registeredBy",e.note
   FROM "LmsAccessEvidence" e JOIN "User" u ON u.id=e."userId"
   WHERE e."eventAt">=%s AND e."eventAt"<%s ORDER BY u.name,e."eventAt",e.id''',(start,end)).fetchall()
 return rows

def fmt(value):return value.astimezone(KST).strftime('%Y-%m-%d %H:%M:%S KST') if value else ''
def export_rows(rows):return [[r['name'],r['email'],r['studentNumber'] or '',LABELS[r['kind']],fmt(r['eventAt']),fmt(r['recordedAt']),r['registeredBy'] or '',r['note']] for r in rows]
HEAD=['이름','이메일','학번','기록 구분','출석 인정/실제 발생 시각','기록 저장 시각','수동 등록자','근거·비고']
def cell(v):return html.escape(str(v))
def csv_cell(v):
 text=str(v)
 return "'"+text if text.startswith(('=','+','-','@','\t','\r')) else text
@app.get('/health')
def health():return {'status':'ok'}
@app.get('/attendance.csv')
def download(request:Request,date:str=''):
 admin=actor(request);day=date or datetime.datetime.now(KST).date().isoformat();rows=export_rows(report(day));out=io.StringIO();writer=csv.writer(out);writer.writerow(HEAD);writer.writerows([[csv_cell(v) for v in r] for r in rows])
 return Response('\ufeff'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="gju-attendance-{day}.csv"'})
@app.get('/attendance',response_class=HTMLResponse)
@app.get('/attendance/',response_class=HTMLResponse)
def page(request:Request,date:str=''):
 actor(request);day=date or datetime.datetime.now(KST).date().isoformat();rows=report(day);table=''.join('<tr>'+''.join('<td>'+cell(v)+'</td>' for v in r)+'</tr>' for r in export_rows(rows))
 return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>광주대 출석 증빙</title><style>body{font:18px/1.6 system-ui;margin:32px;color:#153d35;background:#f4f7f3}h1{font-size:30px}a,button{color:#175f46}table{border-collapse:collapse;background:white;width:100%}th,td{border:1px solid #ccd9d1;padding:12px;text-align:left;font-size:16px}th{background:#e5eee6}aside{background:white;padding:20px;border-radius:10px;margin:20px 0}.scroll{overflow:auto}input,button{font:inherit;padding:8px}</style><a href="/">← Ops로 돌아가기</a><h1>학생 접속·출석 증빙</h1><aside>실제 로그인은 기록 기능 적용 이후 인증 세션이 생성된 시각입니다. 기존 학생의 17:30 출석은 운영자 요청으로 수동 등록하며 실제 로그인 시각으로 표시하지 않습니다. 학습 요청은 서버에 도달한 시각이며 출석·시청 완료 판정은 학교 기준에 따릅니다. 과거 로그는 소급 생성하지 않습니다.</aside><form method="get"><label>조회 날짜 <input type="date" name="date" value="'+cell(day)+'"></label> <button>조회·새로고침</button> <a href="/attendance.csv?date='+cell(day)+'">CSV 내려받기</a></form><p>기록 학생 '+str(len({r['email'] for r in rows}))+'명 · '+str(len(rows))+'건 · 한국시간(KST)</p><div class="scroll"><table><thead><tr>'+''.join('<th>'+cell(x)+'</th>' for x in HEAD)+'</tr></thead><tbody>'+table+'</tbody></table></div></html>'

"""Reviewed LMS approval snapshots. No cloud writes or credential changes."""
import datetime,hashlib,json,re,time
from .providers import CloudError
MAX_AGE=24*3600

def snapshot(raw):
 try:data=json.loads(raw) if isinstance(raw,str) else raw
 except (ValueError,TypeError):raise CloudError('승인 명단 JSON 형식을 확인하세요.') from None
 if not isinstance(data,dict) or data.get('version')!=1 or data.get('kind')!='approved-enrollments':raise CloudError('LMS의 승인 학생 명단 파일을 사용하세요. 배정 JSON·학생 ZIP과 다릅니다.')
 try:stamp=datetime.datetime.fromisoformat(data['exportedAt'].replace('Z','+00:00')).timestamp()
 except (KeyError,ValueError,TypeError,AttributeError):raise CloudError('명단 발급 시각을 확인하세요.') from None
 if not -300<=time.time()-stamp<=MAX_AGE:raise CloudError('24시간 이내에 LMS에서 다시 받은 승인 명단을 사용하세요.')
 course=data.get('courseId');students=data.get('students')
 if not isinstance(course,str) or not 1<=len(course)<=100 or not isinstance(students,list) or not 0<=len(students)<=30:raise CloudError('과정 ID·승인 학생 수(0~30명)를 확인하세요.')
 ids=set();enrollments=set();emails=set();clean=[]
 for person in students:
  if not isinstance(person,dict):raise CloudError('승인 학생 형식을 확인하세요.')
  p={key:str(person.get(key) or '').strip() for key in ['userId','enrollmentId','name','email','studentNumber','assignedLabId','assignedCode']};p['email']=p['email'].lower()
  if any(not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',p[key]) for key in ['userId','enrollmentId']) or not 1<=len(p['name'])<=50 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',p['email']) or len(p['email'])>254 or len(p['studentNumber'])>100:raise CloudError('학생 ID·수강 ID·이름·이메일 형식을 확인하세요.')
  if p['userId'] in ids or p['enrollmentId'] in enrollments or p['email'] in emails:raise CloudError('학생 ID·수강 ID·이메일이 중복된 명단입니다.')
  ids.add(p['userId']);enrollments.add(p['enrollmentId']);emails.add(p['email']);clean.append(p)
 return {'version':1,'kind':'approved-enrollments','courseId':course,'courseTitle':str(data.get('courseTitle',''))[:200],'exportedAt':data['exportedAt'],'students':clean}

def revision(data):return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

def proposals(config,data,legacy,files=None):
 bindings=config.get('lms_bindings',{});reserved=set(bindings)|{code for code in config['students'] if code in legacy or any(path.startswith(config['lab_id']+'-'+code+'/') for path in (files or {}))};used=set();rows=[]
 for p in data['students']:
  code=next((c for c,b in bindings.items() if b['userId']==p['userId']),None);reason='학생 ID 일치' if code else ''
  if not code and p.get('assignedLabId')==config['lab_id'] and p.get('assignedCode') in config['students']:code=p['assignedCode'];reason='LMS 기존 배정'
  if not code:
   for key,label in [('email','기존 이메일 일치'),('name','이름만 일치 · 본인 확인 필요')]:
    matches=[c for c,b in legacy.items() if c in config['students'] and str(b.get(key,'')).strip().lower()==p[key].lower()]
    if len(matches)==1 and (key!='name' or sum(other['name']==p['name'] for other in data['students'])==1):code=matches[0];reason=label;break
  linked=bool(code)
  if not code:code=next((f's{n:02}' for n in range(1,31) if f's{n:02}' not in reserved|used),'');reason='신규 학생 · 생성 대상 여부 확인'
  if code:used.add(code)
  rows.append({**p,'code':code or '', 'reason':reason,'include':linked})
 return rows

def approve(config,data,mappings,legacy,files):
 data=snapshot(data)
 if config.get('lms_roster') and config['lms_roster']['courseId']!=data['courseId']:raise CloudError('기존 LMS 과정과 다릅니다. 다른 과정은 별도 환경을 사용하세요.')
 source={p['userId']:p for p in data['students']};bindings=dict(config.get('lms_bindings',{}));selected={};codes=set()
 if any(uid not in source for uid in mappings):raise CloudError('명단에 없는 학생은 선택할 수 없습니다.')
 for uid,code in mappings.items():
  if not re.fullmatch(r's(?:0[1-9]|[12][0-9]|30)',code) or code in codes:raise CloudError('학생 코드는 s01~s30 사이에서 중복 없이 선택하세요.')
  codes.add(code);p=source[uid]
  old=next((c for c,b in bindings.items() if b['userId']==uid),None)
  if old and old!=code:raise CloudError('기존 LMS 학생 ID의 코드는 변경할 수 없습니다.')
  if code in bindings and bindings[code]['userId']!=uid:raise CloudError('다른 학생에게 연결됐던 코드는 재사용하지 않습니다.')
  started=any(path.startswith(config['lab_id']+'-'+code+'/') for path in files)
  known=legacy.get(code,{})
  identity_match=known.get('email','').lower()==p['email'] or known.get('name')==p['name'] or (p['assignedLabId']==config['lab_id'] and p['assignedCode']==code)
  if (started or code in legacy) and code not in bindings and not identity_match:raise CloudError(code+': 기존 자원 소유 학생과 일치하지 않습니다. 재배정하지 않았습니다.')
  selected[code]=p
 for code,b in bindings.items():bindings[code]={**b,'active':False}
 for code,p in selected.items():bindings[code]={**p,'active':True}
 result=dict(config);result['students']=list(dict.fromkeys(config['students']+sorted(selected)));result['lms_bindings']=bindings;result['lms_roster']={**data,'revision':revision(data),'reviewedAt':time.time()};result.pop('lms_draft',None)
 return result

def approved_people(config):
 if 'lms_roster' not in config:return None
 snapshot(config['lms_roster'])
 return {c:b for c,b in config.get('lms_bindings',{}).items() if b.get('active')}

def require_generation(config,selected,expected=None):
 people=approved_people(config)
 if people is None:raise CloudError('먼저 LMS 승인 학생 명단을 가져와 학생 코드 대조를 확정하세요.')
 if expected is not None and config['lms_roster']['revision']!=expected:raise CloudError('생성 대기 중 승인 명단이 바뀌었습니다. 계획을 다시 확인하세요.')
 if not selected or any(code not in people for code in selected):raise CloudError('승인 명단에서 확정한 학생만 생성할 수 있습니다.')
 return config['lms_roster']['revision']

def plan(config,files):
 bindings=config.get('lms_bindings',{});rows=[]
 for code in config['students']:
  prefix=config['lab_id']+'-'+code+'/'
  started=any(p.startswith(prefix) for p in files);ready=prefix+'outputs.json' in files;person=bindings.get(code,{})
  rows.append({'code':code,'name':person.get('name',''),'email':person.get('email',''),'approved':person.get('active',False),'started':started,'ready':ready,'status':(('기존 자원 · 승인 명단에 없음 (삭제하지 않음)' if config.get('lms_roster') else '기존 자원 · LMS 명단 미연결') if started and not person.get('active') else '기존 자원 재사용' if ready else '생성 기록 있음 · 상태 확인 필요' if started else '신규 생성 대상' if person.get('active') else '미배정 · 생성 제외')})
 return rows

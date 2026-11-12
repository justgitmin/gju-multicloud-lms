"""Build independent student archives in memory; never export operator credentials."""
import io,ipaddress,json,re,zipfile
DB_FIELDS=('db_host','db_port','db_user','db_name','db_password')
def public_ip(value):
 values=[]
 for value in str(value).split(','):
  try:ip=ipaddress.ip_address(value.strip())
  except ValueError:continue
  if ip.is_global:values.append(str(ip))
 return values[0] if len(set(values))==1 else ''
def build(servers,batch,statuses,iam=None):
 output=io.BytesIO();manifest=[]
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as outer:
  for code in sorted(set(servers)|set(batch)):
   if not re.fullmatch(r's(?:0[1-9]|[12][0-9]|30)',code):raise ValueError('Invalid student code')
   server=servers.get(code,{});item=batch.get(code,{});summary=server.get('summary') or item.get('summary',{});person=server.get('person',{})
   if not server.get('ready') and statuses.get(code)!='READY':
    manifest.append({'student':code,'included':False,'reason':'서버 준비 미완료'});continue
   ready=statuses.get(code)=='READY';credentials={k:item.get('access',{}).get(k) for k in DB_FIELDS if k in item.get('access',{})} if ready else {}
   database_ready=ready and all(credentials.get(k) for k in DB_FIELDS)
   key=server.get('key_material',{}).get('private');keyfile=code+'-key.pem' if key else None
   access={'student':code,'name':person.get('name',code),'email':person.get('email',''),'project':summary.get('project',''),'server':summary.get('server_name',''),'public_ip':public_ip(summary.get('ip','')),'ssh_user':'ubuntu','ssh_port':22,'key_file':keyfile,'storage_ready':ready,'container':item.get('summary',summary).get('container',''),'database_ready':database_ready,**(credentials if database_ready else {})}
   own_iam=(iam or {}).get(code,{})
   if own_iam and own_iam.get('project')==access['project']:access['iam']={k:own_iam.get(k,'') for k in ['username','login_url','project','project_id']}
   lines=[access['name']+' 학생 NHN 실습 접속 안내','학생 코드: '+code,'프로젝트: '+access['project'],'','[서버 SSH]','공인 IP: '+(access['public_ip'] or '운영자 확인 필요'),'사용자: ubuntu / 포트: 22','개인 키: '+(keyfile or 'Ops에 보관된 키 없음. 기존에 개별 전달받은 PEM을 사용하세요.'),'','MobaXterm → Session → SSH → Remote host에 공인 IP 입력','Specify username: ubuntu → Advanced SSH settings → Use private key에서 PEM 선택','접속 확인: whoami 및 hostname 실행','','[Object Storage]']
   lines+=['컨테이너: '+access['container'],'본인 NHN IAM으로 해당 프로젝트의 Object Storage에 접속하세요.','비공개 컨테이너입니다.'] if ready else ['아직 준비 완료되지 않았습니다. 이후 갱신된 안내를 받으세요.']
   if access.get('iam'):
    lines+=['IAM ID: '+access['iam']['username'],'로그인 주소: '+(access['iam']['login_url'] or '기존에 전달받은 조직 IAM 주소 사용'),'IAM 비밀번호: 기존에 전달받은 비밀번호 유지']
   lines+=['','[MySQL DB]']
   if database_ready:
    lines+=['DB 주소: '+str(credentials['db_host']),'포트: '+str(credentials['db_port']),'사용자: '+str(credentials['db_user']),'DB 이름: '+str(credentials['db_name']),'비밀번호: '+str(credentials['db_password']),'집 PC에서 직접 접속하지 말고, 본인 실습 서버에 SSH 접속한 뒤 사용하세요.','접속 명령: mysql -h '+str(credentials['db_host'])+' -P '+str(credentials['db_port'])+' -u '+str(credentials['db_user'])+' -p '+str(credentials['db_name'])]
   else:lines+=['아직 준비 완료되지 않았습니다. DB 비밀번호는 포함하지 않았습니다.']
   lines+=['','개인 키·비밀번호는 본인만 보관하세요. 공개 채널·과제·GitHub에 올리지 마세요.']
   student=io.BytesIO()
   with zipfile.ZipFile(student,'w',zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('접속안내.txt','\ufeff'+'\n'.join(lines));archive.writestr('access.json',json.dumps(access,ensure_ascii=False,indent=2))
    if key:archive.writestr(keyfile,key)
   name=re.sub(r'[^\w가-힣-]','_',access['name'])[:50]
   filename=code+'_'+name+'.zip';outer.writestr(filename,student.getvalue());manifest.append({'student':code,'name':access['name'],'file':filename,'included':True,'pem_included':bool(key),'storage_ready':ready,'database_ready':database_ready})
  outer.writestr('운영자_전달목록.json',json.dumps(manifest,ensure_ascii=False,indent=2))
  outer.writestr('운영자_읽어주세요.txt','\ufeff이 전체 ZIP은 운영자용입니다. 내부의 학생별 ZIP만 해당 학생에게 개별 전달하세요.\n미완료 저장소·DB 정보와 Ops에 없는 기존 PEM은 포함되지 않습니다.\n')
 return output.getvalue(),manifest

"""Student-only AWS kits. Allowlist outputs; never export operator or CFN inputs."""
import base64,io,json,re,zipfile
from pathlib import Path
from .providers import CloudError

EXAMPLE_FILES=('index.html','assets/style.css','assets/app.js','README.md')
EXAMPLES=Path(__file__).resolve().parents[1]/'examples/demo-app'
if not EXAMPLES.is_dir():EXAMPLES=Path(__file__).resolve().parents[2]/'examples/demo-app'
GUIDE='https://lms.gju-boot.tbitcloud.com/guide/aws'

def people(store,event):
 result={};conflicts=set()
 for row in store.all('SELECT n.config FROM nhn_bootstrap n JOIN nhn_batches b ON b.id=n.batch_id WHERE b.event_id=?',(event,)):
  for code,person in json.loads(row['config']).get('roster',{}).items():
   if code in result and result[code]!=person:conflicts.add(code)
   else:result[code]=person
 return {code:person for code,person in result.items() if code not in conflicts}

def kit(config,account,files,student,person=None,examples=EXAMPLES):
 if student not in config['students'] or not re.fullmatch('s[0-9]{2}',student):raise CloudError('교육에 등록된 학생 코드를 선택하세요.')
 if config.get('access_mode','ssm')!='ssm':raise CloudError('이 접속 자료는 Session Manager 교육 환경용입니다.')
 stem=config['lab_id']+'-'+student
 def read(name):
  value=files.get(stem+'/'+name)
  if not value:raise CloudError('아직 생성 완료 출력이 없습니다.')
  try:return json.loads(base64.b64decode(value,validate=True))
  except (ValueError,TypeError):raise CloudError('학생 배포 자료 형식 확인 필요') from None
 credentials=read('credentials.json');outputs=read('outputs.json')
 if credentials.get('account_id')!=account or credentials.get('username')!=stem or outputs.get('Username')!=stem or outputs.get('SessionDocument')!=config['lab_id']+'-shell' or not re.fullmatch('i-[0-9a-f]{8,17}',outputs.get('InstanceId','')):raise CloudError('학생·AWS 계정·서버·세션 문서 자료가 일치하지 않습니다.')
 password=credentials.get('initial_password')
 if not isinstance(password,str) or len(password)<12:raise CloudError('학생 초기 비밀번호 확인 필요')
 region=config['region'];instance=outputs['InstanceId'];document=outputs['SessionDocument'];person=person or {}
 access={'student':student,'name':person.get('name',student),'lab_id':config['lab_id'],'region':region,'account_id':account,'username':stem,'initial_password':password,'login_url':f'https://{account}.signin.aws.amazon.com/console/','instance_id':instance,'session_document':document,'session_url':f'https://{region}.console.aws.amazon.com/systems-manager/session-manager/start-session?region={region}&target={instance}&documentName={document}','public_ip':outputs.get('PublicIp',''),'ssh_required':False,'guide_url':GUIDE}
 if config.get('s3'):
  bucket=outputs.get('BucketName','')
  if not re.fullmatch('[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',bucket):raise CloudError('학생 S3 출력이 아직 준비되지 않았습니다.')
  access.update(bucket=bucket,s3_url=f'https://s3.console.aws.amazon.com/s3/buckets/{bucket}?region={region}&prefix=practice/&showversions=false')
 if config.get('rds'):
  host=outputs.get('DbEndpoint','');dbpassword=credentials.get('db_password')
  if not re.fullmatch('[a-zA-Z0-9.-]+\\.rds\\.amazonaws\\.com',host) or not isinstance(dbpassword,str) or len(dbpassword)<12:raise CloudError('학생 DB 출력이 아직 준비되지 않았습니다.')
  access.update(db_host=host,db_port=3306,db_user='labadmin',db_name='labdb',db_password=dbpassword)
 commands='''sudo apt-get update
sudo apt-get install -y nginx curl
sudo systemctl enable --now nginx
mkdir -p ~/demo-app/assets
curl -fL https://raw.githubusercontent.com/justgitmin/gju-multicloud-lms/main/examples/demo-app/index.html -o ~/demo-app/index.html
curl -fL https://raw.githubusercontent.com/justgitmin/gju-multicloud-lms/main/examples/demo-app/assets/style.css -o ~/demo-app/assets/style.css
curl -fL https://raw.githubusercontent.com/justgitmin/gju-multicloud-lms/main/examples/demo-app/assets/app.js -o ~/demo-app/assets/app.js
sudo nginx -t
sudo cp -a /var/www/html "/var/www/html.before-lab-$(date +%Y%m%d%H%M%S)"
sudo cp -r ~/demo-app/. /var/www/html/
curl -I http://127.0.0.1/
'''
 lines=[access['name']+' 학생 AWS 실습 안내','학생 코드: '+student,'가이드: '+GUIDE,'','1. AWS 로그인','콘솔: '+access['login_url'],'IAM 사용자: '+stem,'초기 비밀번호: '+password,'첫 로그인 후 본인이 비밀번호를 변경하세요. LMS·NHN 비밀번호와 다릅니다.','리전: 서울 ('+region+')','','2. 브라우저 서버 접속','접속 주소: '+access['session_url'],'서버 ID: '+instance,'세션 문서: '+document,'Session Manager → 본인 서버 → Next → 지정 세션 문서 선택 → Review and launch → 세션 시작','확인 명령: whoami / hostname / cat /etc/os-release','ubuntu 사용자와 Ubuntu 24.04를 확인합니다. PEM·집 IP 등록은 필요하지 않습니다.','','3. 예제 앱 설치','본인 학생 서버 터미널에서 아래 명령을 순서대로 실행합니다. PC·LMS 서버·CloudShell에서 실행하지 않습니다.','예제 파일은 명령으로 자동 다운로드됩니다. ZIP의 demo-app 폴더는 같은 예제의 참고용 사본입니다.','서버 접속 안내를 읽는 것만으로 Nginx가 설치되지는 않습니다.','정적 앱 버튼은 실제 DB 연결 검증이 아닙니다.','','브라우저 확인 주소: http://'+(access['public_ip'] or 'EC2에서 현재 공인 IP 확인'),'중지 후 시작하면 공인 IP가 바뀔 수 있으므로 EC2에서 다시 확인하세요.']
 if access.get('bucket'):lines+=['','4. S3 파일 실습','버킷: '+access['bucket'],'직접 주소: '+access['s3_url'],'practice/ 경로에 test.txt를 업로드하고 내려받아 내용을 비교합니다. 전체 버킷 목록이 안 보일 수 있습니다.','버킷·객체는 비공개입니다. 공개 설정을 변경하지 않습니다.']
 if access.get('db_host'):lines+=['','5. 본인 서버에서 DB 연결','DB 주소: '+access['db_host'],'DB 사용자: labadmin / 포트: 3306 / DB 이름: labdb','DB 비밀번호: '+access['db_password'],'sudo apt-get install -y mysql-client','mysql -h '+access['db_host']+' -u labadmin -p labdb','비밀번호는 -p 뒤에 쓰지 말고 프롬프트에서 입력합니다.','접속 후 SELECT 1; SELECT DATABASE(); 를 확인하고 가이드의 시험 테이블 실습을 진행하세요.','집 PC에서 직접 DB에 접속하지 않습니다.']
 lines+=['','6. 제출·종료','LMS의 AWS 실습 제출란에 작업 내용과 확인 결과를 작성합니다. 증빙 주소는 선택이며 비밀정보를 제외하세요.','시험 파일 정리는 운영 안내를 따르세요. AWS 세션 종료와 서버 중지·최종 자원 삭제는 서로 다릅니다.','공용 네트워크와 다른 학생 자원을 수정하지 않습니다. 인프라 최종 삭제는 운영자가 담당합니다.','이 ZIP에는 개인 비밀번호가 들어 있습니다. 본인만 보관하고 공개 채널·GitHub·증빙 자료에 올리지 마세요.']
 output=io.BytesIO()
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('접속안내.txt','\ufeff'+'\n'.join(lines));z.writestr('access.json',json.dumps(access,ensure_ascii=False,indent=2));z.writestr('웹앱_설치명령.txt','\ufeff'+commands)
  for filename in EXAMPLE_FILES:
   path=Path(examples)/filename
   if not path.is_file():raise CloudError('배포 이미지에 공통 예제 파일이 없습니다. Ops를 최신 버전으로 빌드하세요.')
   z.writestr('demo-app/'+filename,path.read_bytes())
 return output.getvalue(),access

def archive(config,account,files,roster):
 output=io.BytesIO();manifest=[]
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as outer:
  for code in config['students']:
   try:data,access=kit(config,account,files,code,roster.get(code,{}))
   except CloudError as error:manifest.append({'student':code,'included':False,'reason':str(error)});continue
   name=re.sub(r'[^\w가-힣-]','_',access['name'])[:50];filename=code+'_'+name+'.zip';outer.writestr(filename,data);manifest.append({'student':code,'name':access['name'],'included':True,'file':filename})
  outer.writestr('운영자_전달목록.json',json.dumps(manifest,ensure_ascii=False,indent=2));outer.writestr('운영자_읽어주세요.txt','\ufeff전체 ZIP은 운영자만 보관하세요. 내부 학생별 ZIP만 해당 학생에게 개별 전달합니다.\n출력 미완료·식별 불일치 자료는 제외하며 운영자 AWS 키는 포함하지 않습니다.\n')
 return output.getvalue(),manifest

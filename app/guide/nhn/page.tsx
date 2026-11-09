import Link from 'next/link';
import {requireUser} from '../../../lib/auth';
import {PortalHeader,PortalFooter} from '../../components/PortalChrome';
import {nhnMissions} from '../../../lib/nhn-missions';
import MobaSteps from '../MobaSteps';
import s from '../aws/guide.module.css';
export default async function NhnGuide(){await requireUser();return <><PortalHeader active="classroom"/><main id="portal-content" className="portal-main"><section className="classhero"><div className="eyebrow">NHN CLOUD PRACTICAL GUIDE</div><h1>NHN 영상부터 보고, MobaXterm으로 실습하기</h1><p>NHN 영상 → NHN 실습 → AWS 영상 → AWS 실습 순서로 진행합니다.</p><Link href="/classroom" className="smallbutton">내 강의실로 돌아가기</Link></section><aside><b>Bastion 웹 터미널은 생성하지 않습니다.</b><p>운영자가 준비한 본인 서버에 SSH로 접속합니다. 영상의 인프라 생성 설명은 개념으로 보고 실제 작업은 이 가이드를 따르세요. 영상 원본에 AWS를 먼저 언급하는 부분이 있어도 NHN부터 아래 예제 앱으로 진행할 수 있습니다.</p></aside><section className="card"><h2>영상별 실습 미션</h2><ol>{nhnMissions.map(m=><li key={m.id}><Link href={`/learn/${m.id}`}>{m.id.toUpperCase()} · {m.title}</Link> — <a href={`#step${m.step}`}>실습 단계</a><p>{m.task}</p><p>{m.skip} <b>성공 기준:</b> {m.success}</p></li>)}</ol><p>NHN 8강을 각각 95% 이상 시청하면 NHN 퀴즈가 열립니다. 바로 쉬운 퀴즈로 복습하고 실습하세요.</p></section><div className={s.grid}><nav className={s.index} aria-label="NHN 실습 단계">{['계정과 준비','MobaXterm 접속','네트워크 확인','예제 웹 앱 배포','파일 업로드','DB 연결','상태와 로그','제출과 종료'].map((t,i)=><a key={t} href={`#step${i+1}`}>{i+1}. {t}</a>)}</nav><div className={s.steps}>
<section id="step1"><h2>1. 본인 프로젝트와 접속 안내 확인</h2><p>운영자가 안전하게 전달한 개인 안내에서 IAM 콘솔 주소·IAM ID·초기 비밀번호·프로젝트·서버 공인 IP·개인 키 파일을 확인합니다. LMS 로그인과 NHN 로그인은 별개입니다. 예를 들어 TBIT_Edu01_Pro01은 educity01에 대응합니다. 다른 학생 프로젝트를 선택하지 마세요.</p><p>안내받은 IAM 콘솔에 로그인하고 본인 프로젝트와 한국(판교) 리전을 확인하세요. 최초 비밀번호 변경 안내가 나오면 변경합니다. 운영자가 서버·네트워크·저장소·DB를 준비하므로 학생은 중복 생성하지 않습니다. 아직 제공되지 않은 항목은 운영자에게 요청하세요.</p></section>
<section id="step2"><h2>2. MobaXterm으로 SSH 접속</h2><MobaSteps provider="NHN"/><p>이번에 검증한 서버는 Ubuntu 22.04.5 LTS입니다. 배정 서버가 24.04라면 안내된 버전을 기준으로 확인하세요. MobaXterm을 닫아도 서버가 삭제되거나 중지되지는 않습니다.</p></section>
<section id="step3"><h2>3. 인터넷 경로 확인</h2><p>콘솔에서 본인 VPC·웹 서브넷·라우팅 테이블을 확인합니다. 웹 서브넷에 인터넷 게이트웨이 경로(0.0.0.0/0)가 연결되고 서버에 플로팅 IP가 있어야 외부에서 접근할 수 있습니다. SSH는 운영자가 승인한 학생 PC 공인 IP의 22번, 웹은 허용된 80번을 사용합니다.</p><p>사용자 → 플로팅 IP → 웹 서버 → 사설 DB 흐름을 한 줄로 적으세요. 권한이 없어 설정을 볼 수 없다면 제공된 구조도를 참고합니다. 학생이 보안 그룹·라우팅을 변경하지 않습니다.</p></section>
<section id="step4"><h2>4. 같은 예제 웹 앱 배포</h2><p>다음 명령은 MobaXterm으로 접속한 <b>본인 NHN 학생 서버</b>에서 실행합니다. index.html과 assets 파일을 모두 설치하세요.</p><pre>{`sudo apt-get update
sudo apt-get install -y nginx curl
sudo systemctl enable --now nginx
mkdir -p ~/demo-app/assets
curl -fL https://raw.githubusercontent.com/justgitmin/gju-multicloud-lms/main/examples/demo-app/index.html -o ~/demo-app/index.html
curl -fL https://raw.githubusercontent.com/justgitmin/gju-multicloud-lms/main/examples/demo-app/assets/style.css -o ~/demo-app/assets/style.css
curl -fL https://raw.githubusercontent.com/justgitmin/gju-multicloud-lms/main/examples/demo-app/assets/app.js -o ~/demo-app/assets/app.js
sudo nginx -t
sudo cp -a /var/www/html "/var/www/html.before-lab-$(date +%Y%m%d%H%M%S)"
sudo cp -r ~/demo-app/. /var/www/html/
curl -I http://127.0.0.1/`}</pre><p>각 명령이 성공했는지 확인하세요. <code>nano ~/demo-app/index.html</code>로 제목을 수정하고 다시 복사해도 됩니다. PC 브라우저에서 <code>http://본인공인IP</code>를 엽니다. 제목·스타일·버튼이 동작하면 성공입니다. 버튼 문구는 정적 JavaScript 확인이며 실제 DB 연결 증거는 아닙니다.</p></section>
<section id="step5"><h2>5. Object Storage 파일 실습</h2><ol><li>개인정보 없는 test.txt를 PC에서 만듭니다.</li><li>본인 프로젝트의 Object Storage에서 배정받은 컨테이너를 엽니다.</li><li>practice/ 경로에 업로드하고 내려받아 내용을 비교합니다.</li></ol><p>컨테이너 이름·객체 경로·크기·결과를 기록합니다. 컨테이너가 없거나 접근이 거부되면 운영자에게 요청하세요. 컨테이너 생성이나 공개 전환은 하지 않습니다. API 키·개인 키를 업로드하지 마세요.</p></section>
<section id="step6"><h2>6. 학생 서버에서 DB 연결</h2><p>DB 주소·DB 사용자명·DB 이름·비밀번호가 배정된 경우에 진행하세요. 미배정이면 운영자에게 요청하고 직접 RDS를 만들지 않습니다. 아래 입력에는 본인 안내의 값을 사용합니다.</p><pre>{`sudo apt-get install -y mysql-client
read -r -p 'DB host: ' LAB_DB_HOST
read -r -p 'DB user: ' LAB_DB_USER
read -r -p 'DB name: ' LAB_DB_NAME
mysql -h "$LAB_DB_HOST" -u "$LAB_DB_USER" -p "$LAB_DB_NAME"`}</pre><p>비밀번호는 이어지는 프롬프트에만 입력합니다. 접속 후 아래 쿼리로 확인하세요.</p><pre>{`SELECT 1;
SELECT DATABASE();
exit;`}</pre><p>1과 배정된 DB 이름이 나오면 성공입니다. 연결 시간 초과와 인증 오류를 구분해 기록하고 운영자에게 알려주세요. DB 연결을 위해 인터넷 전체에 DB 포트를 열지 않습니다.</p></section>
<section id="step7"><h2>7. 서비스 상태와 로그 확인</h2><pre>{`systemctl is-active nginx
sudo journalctl -u nginx --no-pager -n 20
free -h
df -h`}</pre><p>서비스 상태·로그·메모리·디스크를 확인합니다. 웹이 안 열리면 서버 내부 curl → Nginx 상태 → 공인 IP·80번 접근 순으로 확인하세요. 본인 자원만 점검하고 로그를 임의로 삭제하지 않습니다.</p></section>
<section id="step8"><h2>8. 제출하고 AWS 학습으로 이동</h2><p>과정의 NHN 실습 제출란에 접속 결과·웹 확인·네트워크 흐름·파일 업로드·DB 연결·문제 해결 과정을 정리하세요. 미배정으로 수행하지 못한 항목은 이유를 적고 운영자 안내에 따라 보완합니다. 비밀번호·키는 제출하지 않습니다. 기존 제출 안내의 AWS 비교표는 AWS 학습 후 보완하세요.</p><p>본인 시험 파일 정리는 운영 안내를 따르고 터미널에 exit를 입력해 접속을 종료합니다. 최종 서버·DB·플로팅 IP·디스크·네트워크 삭제는 운영자가 담당합니다. SSH 종료만으로 과금이 끝나지 않습니다.</p><p><Link className="button" href="/course/gju-multicloud-2026#nhn-lab">NHN 실습 제출·퀴즈 →</Link></p><Link href="/learn/aws-01">다음: AWS 영상 학습 →</Link></section>
</div></div></main><PortalFooter/></>}

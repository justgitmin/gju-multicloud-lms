import Link from 'next/link';
import {requireUser} from '../../../lib/auth';
import {PortalHeader,PortalFooter} from '../../components/PortalChrome';
import s from './guide.module.css';
export default async function AwsGuide(){await requireUser();return <><PortalHeader active="classroom"/><main id="portal-content" className="portal-main"><section className="classhero"><div className="eyebrow">AWS PRACTICAL GUIDE</div><h1>집에서 시작하는 AWS 실습</h1><p>제공된 계정으로 로그인하고, 브라우저 터미널에서 본인 서버를 사용하세요.</p><Link className="smallbutton" href="/classroom">내 강의실로 돌아가기</Link></section><aside><b>영상의 SSH 접속 부분은 아래 방법으로 진행하세요.</b><br/>새 환경은 MobaXterm·집 IP 등록·개인 키 없이 Session Manager로 접속합니다. 이후 웹 배포·S3·DB 미션은 동일합니다. 기존 영상 자체를 다시 편집한 것은 아니므로 접속 단계에서는 이 안내를 우선하세요.</aside><div className={s.grid}><nav className={s.index} aria-label="실습 단계">{['로그인과 준비','브라우저 서버 접속','네트워크 확인','웹 앱 배포','S3 파일 실습','DB 연결','권한과 제출','실습 종료'].map((title,i)=><a href={'#step'+(i+1)} key={title}>{String(i+1).padStart(2,'0')}　{title}</a>)}</nav><div className={s.steps}>
<section id="step1"><span>01 · AWS 영상 01</span><h2>개인 접속 안내로 로그인</h2><p>운영자가 개별 전달한 안내에서 콘솔 주소·사용자명·초기 비밀번호를 확인하세요. 최초 로그인 후 비밀번호를 바꾸고 리전을 <b>서울(ap-northeast-2)</b>로 선택합니다. LMS 로그인과 AWS 로그인은 별개입니다.</p><p>본인 서버 ID, 세션 문서 이름, S3 직접 주소, DB 주소와 비밀번호를 확인하세요. 미배정 상태라면 운영자에게 요청하고 개인 결제 계정으로 대신 만들지 마세요.</p></section>
<section id="step2"><span>02 · AWS 영상 03 접속 방법 보완</span><h2>Session Manager에서 본인 서버 접속</h2><ol><li>개별 안내의 <b>브라우저 접속</b> 링크를 엽니다.</li><li>대상이 본인 <b>서버 ID</b>인지 확인합니다.</li><li>세션 문서 선택에서 안내받은 <b>교육 환경 이름-shell</b> 문서를 선택합니다. 링크가 문서를 자동 선택하지 않으면 직접 선택하세요.</li><li><b>세션 시작</b>을 누릅니다. 메뉴로 찾는 경우 AWS 검색 → Systems Manager → Session Manager → 세션 시작입니다.</li></ol><pre>{`whoami
hostname
cat /etc/os-release`}</pre><p><b>성공 기준:</b> ubuntu 사용자와 Ubuntu 24.04가 표시됩니다. 연결 실패 시 서울 리전·본인 서버 ID·지정 세션 문서를 확인합니다. 서버가 중지됐다면 본인 서버를 시작하고 에이전트 연결을 기다리세요. 새 환경 첫 생성 후에도 연결 준비 시간이 필요합니다.</p><p>EC2의 기본 연결 문서나 SSH 탭으로 들어가면 권한 오류가 날 수 있습니다. 이 실습은 지정한 교육용 세션 문서를 사용합니다.</p></section>
<section id="step3"><span>03 · AWS 영상 02</span><h2>네트워크 구조 확인</h2><p>VPC 콘솔에서 교육용 VPC, 웹 서브넷, 사설 DB 서브넷과 라우팅을 확인하세요. VPC는 학생이 공유하지만 서버·접근 권한은 개인별입니다. 네트워크나 보안 그룹을 새로 만들거나 변경하지 않습니다.</p><p>사용자 → 공인 웹 서버 → 사설 DB 흐름을 그리세요. 웹에는 인터넷 경로가 있고, DB는 본인 서버에서만 접근 가능한 이유를 적습니다.</p></section>
<section id="step4"><span>04 · AWS 영상 04</span><h2>예제 웹 앱 전체 배포</h2><p>다음 명령은 <b>본인 학생 서버의 브라우저 터미널</b>에서 실행합니다. LMS 서버나 관리자 CloudShell에 설치하는 명령이 아닙니다.</p><pre>{`sudo apt-get update
sudo apt-get install -y nginx curl
sudo systemctl enable --now nginx
mkdir -p ~/demo-app/assets
curl -fL https://raw.githubusercontent.com/justgitmin/gju-multicloud-lms/main/examples/demo-app/index.html -o ~/demo-app/index.html
curl -fL https://raw.githubusercontent.com/justgitmin/gju-multicloud-lms/main/examples/demo-app/assets/style.css -o ~/demo-app/assets/style.css
curl -fL https://raw.githubusercontent.com/justgitmin/gju-multicloud-lms/main/examples/demo-app/assets/app.js -o ~/demo-app/assets/app.js`}</pre><p>각 curl 명령이 성공했는지 확인한 뒤 진행하세요. 제목을 바꾸려면 <code>nano ~/demo-app/index.html</code>로 수정합니다. 기존 document root가 실습 Nginx 기본 경로인지 확인하고 파일을 백업한 뒤 배치합니다.</p><pre>{`sudo nginx -t
sudo cp -a /var/www/html /var/www/html.before-lab
sudo cp -r ~/demo-app/. /var/www/html/
curl -I http://127.0.0.1/
curl http://127.0.0.1/`}</pre><p>EC2 콘솔에서 본인 서버의 현재 공인 IPv4를 확인하고 PC 브라우저에서 <code>http://본인공인IP</code>로 접속합니다. <b>성공 기준:</b> 제목·스타일·버튼이 동작합니다. 이 예제 앱의 성공 문구는 정적 JavaScript 동작 확인이며 실제 AWS API·DB 연결 검증은 아닙니다.</p></section>
<section id="step5"><span>05 · AWS 영상 05</span><h2>본인 S3 경로에 파일 업로드</h2><ol><li>PC에 개인정보 없는 <code>test.txt</code>를 만듭니다.</li><li>본인의 학생 IAM 사용자로 로그인한 상태에서 개별 안내의 <b>S3 직접 링크</b>를 엽니다. 전체 버킷 목록은 권한이 없어 안 보일 수 있습니다.</li><li><code>practice/</code> 경로에서 파일을 업로드합니다. 버킷 루트에 올리면 거부됩니다.</li><li>파일을 다운로드하고 내용이 일치하는지 확인합니다.</li></ol><p>정확한 객체 키·크기·확인 결과를 기록하세요. 버킷은 비공개이므로 익명 URL이 열리지 않는 것이 정상입니다. 공개 전환하거나 서명 URL을 제출하지 마세요. S3를 제공하지 않은 교육은 운영자 안내를 따릅니다.</p></section>
<section id="step6"><span>06 · AWS 영상 06</span><h2>웹 서버에서 본인 DB 연결</h2><p>학생 서버 브라우저 터미널에서 설치한 뒤 <code>본인DB주소</code>를 개별 제공 주소로 바꿉니다.</p><pre>{`sudo apt-get install -y mysql-client
mysql -h 본인DB주소 -u labadmin -p labdb`}</pre><p>비밀번호는 프롬프트에만 입력하며 화면에 표시되지 않습니다. 접속 후:</p><pre>{`SELECT 1;
SELECT DATABASE();
exit;`}</pre><p><b>성공 기준:</b> 1과 labdb가 반환됩니다. PC에서 직접 DB 연결은 허용하지 않습니다. 연결 시간 초과와 비밀번호 오류를 구분해서 기록하세요. DB가 제공되지 않은 교육에서는 임의로 생성하지 말고 운영자에게 문의합니다.</p></section>
<section id="step7"><span>07 · AWS 영상 07–08</span><h2>권한과 결과를 설명해서 제출</h2><p>IAM 정책을 바꾸는 실습은 하지 않습니다. “누가 · 어떤 작업을 · 어느 자원에 · 왜 수행해야 하는지” 한 줄로 권한 요청문을 작성하세요. 다른 학생 자원과 설정은 변경할 수 없습니다.</p><p>과정의 실습 제출란에 웹 내부/외부 확인, 네트워크 흐름, S3 파일, DB 쿼리, 오류 해결, 남은 자원을 정리합니다. 수행하지 못한 항목은 이유를 적으세요. 비밀번호·토큰·개인정보는 제출하지 않습니다.</p></section>
<section id="step8"><span>08 · 실습을 마칠 때</span><h2>정리하고 학습 기록 남기기</h2><p>본인이 올린 시험 파일은 운영 안내에 따라 삭제하고, AWS 콘솔에서 세션을 종료합니다. 이후 재사용 여부를 확인해 본인 서버를 중지할 수 있습니다. 중지해도 DB·디스크 등 비용이 모두 끝나는 것은 아닙니다. 최종 인프라 삭제는 운영자가 수행합니다.</p><p>계정 비밀번호는 본인만 보관하세요. 다음 접속에도 집 IP 승인 없이 동일한 Session Manager 방식으로 접속합니다. 서버 중지·시작 후 웹 공인 IP는 바뀔 수 있으니 다시 확인하세요.</p><Link className="button" href="/classroom">내 강의실로 이동 →</Link></section>
</div></div></main><PortalFooter/></>}

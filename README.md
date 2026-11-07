# gju-multicloud-lms
광주대학교 AWS·NHN Cloud 멀티클라우드 온라인 학습 플랫폼.

## 구현 현황
- 회원가입·로그인·로그아웃, 수강신청과 관리자 승인/반려.
- 서버 세션·비밀번호 해시·시도 제한·상태 변경의 출처 검증.
- 승인 및 이전 강의 이수에 따른 영상 접근, 서버 경과시간 기반 진도 검증, 이어보기.
- 최초 1배속·미시청 구간 이동 제한, 이수 후 탐색·배속 허용, 한국어 자막.
- 실습 설명/증빙 URL 제출·피드백·통과/보완 요청, 서버 퀴즈 채점·재응시.
- 현재 콘텐츠 버전의 온라인 이수 기준과 관리자 CSV 보고서.
- 비공개 로컬 MP4 또는 S3 인증 스트리밍. 현재 S3 모드의 영상 트래픽은 앱 서버를 통과합니다.
- AWS 8편 + NHN 8편의 자체 개념·실습 안내 영상·자막·대본. 실제 콘솔 녹화가 아니며 최종 청취·실제 계정 실습 검수가 필요합니다.

## 개발
Node.js 24와 PostgreSQL 16 기준입니다.
```bash
npm ci
npm run db:generate
npm run db:migrate
npm run dev
```
.env.example을 참고해 실제 환경변수는 서버에만 설정합니다. 키·학생 정보·영상 원본·백업은 Git에 포함하지 않습니다.

## 초기 데이터
- ADMIN_EMAIL/ADMIN_PASSWORD를 프로세스 환경에 설정한 뒤 `npm run db:setup`. 기존 계정의 권한·비밀번호는 바꾸지 않습니다.
- `npm run db:seed-lessons`, `npm run db:seed-assessments`로 기본 과정 콘텐츠 레코드를 준비합니다.
- S3에 전체 영상·자막을 수동 업로드한 뒤 `npm run media:register-course`. 파일 존재·영상 크기 확인이 모두 성공한 후 DB에 등록합니다. 원격 전체 파일 해시까지 검증하는 명령은 아닙니다.
- 호스트의 AWS CLI 프로필은 Docker에 자동 전달되지 않습니다. 컨테이너의 제한된 자격 증명 설정이 필요합니다.

## 검증
```bash
npm test
npm run build
npm run typecheck
```
`npm run test:integration`은 **빈 전용 테스트 DB** 및 `LMS_INTEGRATION_TEST=true`에서만 실행합니다. 운영 DB를 대상으로 실행하지 않습니다. GitHub CI는 PostgreSQL 16 서비스를 별도로 생성합니다.

## 문서와 자료
- [영상 전체 목록·실제 길이](docs/CONTENT_INDEX.md)
- [학생 실습 안내](docs/STUDENT_LAB_GUIDE.md)
- [Lightsail 배포·S3 연결](docs/DEPLOYMENT.md)
- [공통 정적 웹 앱](examples/demo-app)
- [구현·검증 기록](docs/IMPLEMENTATION.md)
- [영상 제작 방식](docs/VIDEO_PRODUCTION.md)

수동 업로드용 ZIP은 압축을 푼 후 **S3 버킷 최상위에서 courses 폴더**를 올립니다. 버킷 비공개 설정은 유지합니다. 01/02 파일이 같은 경로에 이미 있다면 중복 업로드 여부를 확인하고 자막을 추가합니다.

## 이수 기준과 한계
모든 현재 버전 영상 95% 이상, 필수 실습 전체 통과, 현재 버전 평가별 70점 이상이면 온라인 기준 충족입니다. 학교의 대면 출석·최종 프로젝트를 포함한 공식 수료 확정과는 구분합니다.
실습은 텍스트·증빙 URL 방식이며 파일 직접 첨부, 이메일 인증/비밀번호 재설정, 공식 수료증은 미구현입니다. 공개 저장소의 평가 문항은 학습 확인용이며 비공개 시험 보안을 제공하지 않습니다.
갑작스러운 종료 시 마지막 저장 이후 몇 초가 유실될 수 있습니다. 브라우저에서 실제 집중과 모든 부정행위를 증명하지는 않습니다. 현재 동일 학생·동일 강의의 중복 재생 세션을 교체하며 계정 전체의 서로 다른 강의 동시 재생 제한은 별도 범위입니다.
실제 Lightsail 배포·S3 권한·클라우드 원격 재생·운영 DB 복구와 최종 청취는 별도 검증이 필요합니다. 개인정보 안내 확정 전 ENABLE_REGISTRATION=false를 유지합니다.

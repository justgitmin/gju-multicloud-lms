# gju-multicloud-lms
광주대학교 AWS·NHN Cloud 멀티클라우드 온라인 학습 플랫폼.

## 현재 상태
기본 Next.js 앱, 과정 안내, AWS·NHN 커리큘럼, Prisma 데이터 모델, Docker Compose 골격과 DB 백업 스크립트가 준비되어 있습니다.
회원가입·로그인·로그아웃·수강신청·관리자 승인/반려를 구현했습니다. 가입은 기본적으로 비활성화됩니다. 영상 플레이어·서버 진도 검증·이어보기·순차 강의 개방을 구현했습니다. **실제 영상 제작, 퀴즈 및 PostgreSQL 통합시험과 운영 검증은 아직 완료되지 않았습니다.**

## 로컬 실행
Node.js 24 사용.
```bash
npm ci
npm run dev
```

## 검증
```bash
npm run db:generate
npm test
npm run typecheck
npm run build
```

## 서버 준비
`.env.example`을 `.env`로 복사하고 고유한 DB 비밀번호와 DATABASE_URL을 설정합니다. DB 비밀번호의 URL 예약문자는 URL 인코딩해야 합니다. DB 포트는 외부 공개하지 않습니다.
현재 Docker Compose는 기본 구조 검증용입니다. HTTPS·인증·마이그레이션·복구 검증 후 운영 배포 절차를 제공합니다.

## 문서
- [구현 계획](docs/IMPLEMENTATION.md)
- [자체 영상 제작](docs/VIDEO_PRODUCTION.md)

실제 환경변수·학생 정보·영상 원본·백업 파일은 커밋하지 않습니다.


## 계정·신청 기능 검증 준비
1. PostgreSQL 연결 및 `npm run db:migrate` 실행.
2. 프로세스 환경에 `ADMIN_EMAIL`, `ADMIN_PASSWORD`를 설정한 뒤 `npm run db:setup` 실행. 비밀번호는 12~128자이며 기존 계정의 권한/비밀번호는 자동 변경하지 않습니다.
3. 실제 운영 전 개인정보 안내의 처리자·문의처·보유기간과 HTTPS를 확정합니다.
4. 테스트 환경에서 `ENABLE_REGISTRATION=true` 설정 후 가입 → 수강신청 → 관리자 승인 → 학생 상태 변경을 확인합니다.
5. 학생의 `/admin` 접근 거부, 비로그인 `/classroom` 접근 차단, 반려 학생 콘텐츠 접근 차단을 검증합니다.

Docker에서 DB 도구는 `docker compose --profile tools run --rm tools`로 마이그레이션을 실행할 수 있습니다. 관리자 초기화는 같은 명령 뒤 `npm run db:setup`을 붙이며 관리자 환경변수를 전달해야 합니다. 최초 배포는 후속 운영 검증 후 진행합니다.

세션은 HttpOnly·SameSite=Lax 쿠키, 운영 모드에서 Secure를 사용합니다. 상태 변경은 Next.js Server Actions를 사용하며 프레임워크의 동일 출처 검증을 유지합니다. 로그인 시도는 DB 기반 15분 제한을 사용합니다. 공유 전역 제한은 대규모 운영 전에 재조정해야 합니다. 이메일 소유 확인 및 비밀번호 재설정은 후속 구현 항목입니다.


## 영상 학습 준비
- `npm run db:migrate` 후 `npm run db:seed-lessons`로 16개 강의 레코드를 등록합니다. 기존 영상 정보는 덮어쓰지 않습니다.
- 실제 제작·검수한 MP4는 `npm run media:register -- aws-01 /absolute/path/video.mp4`로 등록합니다. ffprobe가 필요합니다. 실제 길이가 DB에 반영됩니다.
- 현재 단계는 비공개 로컬 디렉터리의 인증된 MP4 Range 전송입니다. S3·CloudFront 연동 및 자막은 후속 단계입니다. 영상 원본은 Git에 올리지 않습니다.
- Docker web은 `./media`를 읽기 전용으로 마운트합니다. 파일은 컨테이너 node 사용자(uid 1000)가 읽을 수 있어야 합니다.
- 같은 학생이 같은 영상을 새 창에서 시작하면 이전 재생 세션의 저장이 중지됩니다. 다른 영상의 동시 재생을 계정 전체에서 막는 기능은 후속 항목입니다.
- 첫 학습은 1배속, 이미 본 구간 탐색 허용, 고유 연속 시청구간 95% 이상이면 영상 이수입니다. 이수 후 탐색·배속을 허용합니다.
- 탭 숨김 시 일시정지, 약 5초마다 저장, 일시정지·종료 시 추가 저장을 시도합니다. 갑작스러운 종료 시 마지막 저장 이후 몇 초는 유실될 수 있습니다.
- 서버는 승인·이전 강의 이수·영상 버전·경과시간·세션 revision을 검증합니다. 브라우저에서 실제 집중이나 모든 부정행위를 증명하는 기능은 아닙니다.

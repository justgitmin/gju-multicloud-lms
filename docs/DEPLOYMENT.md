# Lightsail 배포 준비와 실행 순서

아직 실제 서버 배포나 S3 업로드 검증은 수행하지 않았습니다. 아래 절차는 새 LMS 서버용입니다.

## 선행 조건
- Ubuntu 24.04, Docker Engine 및 Compose 플러그인, Git 설치.
- 도메인의 A 레코드가 Lightsail 고정 IP를 가리키고 80/443 포트 허용.
- .env에 고유 DB 비밀번호, DATABASE_URL, 실제 도메인 SITE_ADDRESS 및 외부 HTTPS 주소 APP_ORIGIN 입력.
- 개인정보처리자·문의처·보유기간 등 학교 정책 확정 전 ENABLE_REGISTRATION=false 유지.
- 비공개 S3 버킷에 영상과 자막을 지정 경로로 업로드.

## 파일 업로드
AWS/NHN ZIP을 각각 풀면 courses/ 폴더가 나옵니다. **버킷 최상위**에서 courses 폴더를 업로드합니다. courses 안에서 다시 courses 폴더를 올리면 경로가 중복됩니다.
원본 경로 예: courses/2026-multicloud/aws/03/v1/aws-03.mp4
자막 경로 예: courses/2026-multicloud/aws/03/v1/captions-ko.vtt
자막 교정본은 01/02를 포함한 전체 16개 MP4와 VTT를 같은 키에 덮어씁니다. MP4의 Content-Type은 video/mp4, VTT는 text/vtt로 설정합니다. 버전 관리가 켜져 있으면 이전 버전도 남아 저장 요금이 발생할 수 있습니다.

## 인증과 S3 제공
운영 서버의 .env에만 제한된 S3 읽기용 자격 증명을 설정합니다. IAM 사용자 키 또는 허용된 임시 자격 증명을 사용할 수 있습니다. 키를 Git/채팅/브라우저에 넣지 않습니다.
MEDIA_BACKEND=s3, MEDIA_S3_BUCKET=gju-multicloud-lms-media-2026, AWS_REGION=ap-northeast-2를 설정합니다.
현재 S3 모드는 서버가 수강 권한을 확인한 후 S3 파일을 스트리밍합니다. 버킷 공개·CORS·CloudFront가 없어도 이 방식으로 연결할 수 있습니다. 영상 트래픽은 앱 서버를 통과하므로 동시 수강 확대 시 CDN 전송을 별도로 검토합니다.
호스트의 aws configure 프로필은 Docker에 자동 전달되지 않습니다. 컨테이너 환경의 자격 증명이 필요합니다. 웹 서버에는 GetObject만, 설치 도구에는 확인에 필요한 권한만 부여합니다.

## 실행
1. 명시적인 검증 커밋을 checkout합니다.
2. `.env.example`을 `.env`로 복사하고 값을 설정한 뒤 chmod 600 .env를 적용합니다.
3. `bash scripts/deploy.sh` 실행. DB 마이그레이션을 수행하고 웹·HTTPS 프록시를 시작합니다.
4. 관리자 계정 생성: ADMIN_EMAIL/ADMIN_PASSWORD를 안전하게 설정한 프로세스 환경에서 `docker compose --profile tools run --rm tools npm run db:setup` 실행. 기존 계정이 있으면 거부합니다.
5. `docker compose --profile tools run --rm tools npm run db:seed-lessons`
6. `docker compose --profile tools run --rm tools npm run db:seed-assessments`
7. `docker compose --profile tools run --rm tools npm run media:register-course` 실행. 16개 MP4와 자막의 크기·전체 SHA-256·Content-Type을 확인한 뒤에만 DB에 일괄 등록합니다. 약 160 MiB를 순차 다운로드해 검사하며 영상은 디스크에 저장하지 않습니다. 한 파일이라도 다르면 DB를 변경하지 않습니다. 동일 해시의 재등록은 영상 버전을 올리지 않습니다.
8. 관리자·학생 테스트 계정으로 신청/승인/재생/탐색 제한/실습/퀴즈/CSV를 검증합니다.
9. 개인정보 안내 확정과 테스트 완료 후 ENABLE_REGISTRATION=true로 바꾸고 web 컨테이너를 재생성합니다.

## 영상 교체 후 확인과 등록

이미 초기 과정이 등록된 서버에서, 최신 수정 커밋을 checkout한 다음 실행합니다.

```bash
bash scripts/deploy.sh
docker compose --profile tools run --rm tools npm run media:verify-course
# 위 검사 성공 후에만 실행. 기존 학생 정보가 있으면 먼저 백업합니다.
bash scripts/backup.sh
docker compose --profile tools run --rm tools npm run media:register-course
```

검사는 `MEDIA_VERIFICATION_OK`로 끝나며 DB를 변경하지 않습니다. 등록 명령도 다시 검증한 후 DB에 적용합니다. `Content-Type mismatch`는 S3 객체 속성의 메타데이터에서 유형을 수정하고 다시 검사합니다. 내용/크기 불일치는 최신 ZIP의 MP4와 VTT를 같은 경로에 재업로드합니다.

영상 해시가 바뀌면 콘텐츠 버전이 올라가므로 기존 버전 진도가 새 버전의 이수로 자동 인정되지 않습니다. 학생이 이미 학습 중이라면 영상 교체 전 운영 시점을 조정합니다.

## 백업·복구
`scripts/backup.sh`는 로컬 DB 덤프를 만듭니다. 외부 보관 위치와 주기, 보유기간은 운영 환경에서 설정해야 합니다. 덤프에는 학생 정보가 포함됩니다.
복구는 운영 DB에 바로 덮어쓰지 말고 새 별도 테스트 DB에 먼저 복원해 계정·진도·제출·평가를 확인합니다. DB 마이그레이션을 포함하는 롤백은 단순 git checkout으로 보장되지 않습니다.

## 한계
- Docker 이미지 실제 빌드·HTTPS 발급·S3 권한·원격 재생·서버 백업 복원은 사용자 서버에서 최종 검증해야 합니다.
- 직접 파일 첨부 업로드, 이메일 인증/비밀번호 재설정, 수료증 발행, 대면 출석·최종 프로젝트 통합은 별도 범위입니다.

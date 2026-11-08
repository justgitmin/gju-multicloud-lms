# HTTPS 전환 및 학생 AWS 실습 환경 연결

기능은 구현되어 있으며 실제 운영 서버의 DNS·인증서 발급·DB 마이그레이션·학생 배정은 운영자가 아래 순서로 적용합니다. 이 문서는 실제 적용 완료 기록이 아닙니다.

## 운영 주소

기존 부트캠프 주소: `gju-boot.tbitcloud.com`.
별도 LMS 주소: **`lms.gju-boot.tbitcloud.com`**.
대상은 기존 LMS 서버이며, 최근 확인한 IPv4는 **15.165.254.45**입니다. Lightsail 콘솔에서 해당 서버의 현재 주소/고정 IP 연결을 확인한 뒤 DNS를 설정하세요. 학생 실습 EC2 IP와 혼동하지 마세요.

DNS에서 A 레코드 1개를 추가합니다:

| 항목 | 값 |
|---|---|
| 호스트 / 이름 | lms.gju-boot (tbitcloud.com 영역일 때) |
| 형식 | A |
| 대상 | 기존 LMS 서버의 현재 고정 IPv4 |
| TTL | 300초 예시 |

위임된 DNS 영역이 `gju-boot.tbitcloud.com`이면 이름은 `lms`입니다. 기존 `gju-boot` 레코드를 바꾸는 작업이 아닙니다. 잘못된 AAAA 레코드는 만들지 마세요. Cloudflare 등 프록시를 쓰면 초기 인증서 검증을 위한 연결 경로를 별도로 확인해야 합니다.

Lightsail 네트워킹 방화벽에서 HTTP TCP80/HTTPS TCP443을 인터넷에 허용합니다. SSH는 기존 운영 접속 규칙을 유지합니다. DB/3000 포트는 공개하지 않습니다. Caddy가 DNS의 대상 서버에 도달해야 인증서를 발급할 수 있습니다. 도메인에 CAA 제한이 있다면 인증서 발급기관 허용 여부도 확인하세요.

## 1. 운영 서버에서 설정 준비

**기존 LMS 서버의 SSH 창**에서 진행합니다. 학생 서버/PC/CloudShell이 아닙니다.

```bash
cd ~/gju-multicloud-lms
git pull --ff-only origin main
python3 scripts/configure-https.py --domain lms.gju-boot.tbitcloud.com --public-ip 15.165.254.45
```

이 단계는 DNS/설정 계획만 검사하며 파일을 바꾸지 않습니다. 실제 IP가 다르면 `--public-ip`도 바꾸세요. DNS가 안 맞으면 중단하며 DNS부터 수정해야 합니다. 연결이 확인되면:

```bash
python3 scripts/configure-https.py --domain lms.gju-boot.tbitcloud.com --public-ip 15.165.254.45 --apply
```

설정 도구는 `.env`의 다른 비밀번호/키를 유지하면서 APP_ORIGIN/SITE_ADDRESS를 갱신합니다. LAB_CREDENTIALS_KEY가 없으면 AES-256-GCM용 32바이트 키를 생성하며 **이미 있는 키는 바꾸지 않습니다**. `Caddyfile`의 IP 테스트용 :80 설정은 도메인용 자동 HTTPS 설정으로 되돌립니다.

`backups/https-.../`에 적용 전/후 .env와 이전 Caddyfile을 보관합니다. 비밀정보가 들어 있으므로 운영자만 보관합니다. 키와 DB 백업은 함께 복구할 수 있어야 합니다. 암호화 키를 잃으면 저장된 AWS 비밀번호를 복호화할 수 없습니다.

## 2. 백업·빌드·마이그레이션·재배포

아래 명령은 **하나씩 성공을 확인하며** 실행합니다. 실패한 다음 단계로 넘어가지 마세요.

```bash
bash scripts/backup.sh
docker compose -f compose.yaml -f compose.prod.yaml config --quiet
docker compose -f compose.yaml -f compose.prod.yaml build web tools
docker compose -f compose.yaml -f compose.prod.yaml --profile tools run --rm tools npm run db:migrate
docker compose -f compose.yaml -f compose.prod.yaml up -d --no-deps --force-recreate web caddy
```

이번 변경은 새 DB 테이블을 추가하므로 웹만 재빌드하는 것으로 끝내지 않습니다. 기존 학습 기록/계정 테이블을 삭제하지 않는 추가 마이그레이션입니다. 자동 deploy.sh는 추적 파일 변경(Caddyfile)을 감지해 중단할 수 있어 명시적 Compose 명령을 사용합니다.

```bash
curl -I https://lms.gju-boot.tbitcloud.com
curl -I http://lms.gju-boot.tbitcloud.com
docker compose -f compose.yaml -f compose.prod.yaml logs --tail=60 caddy
```

HTTPS 인증서 검증을 끄는 `curl -k`로 성공 판정을 하지 않습니다. 정상 인증서의 HTTPS 200/정상 이동, HTTP→HTTPS 이동을 확인합니다. 브라우저에서 HTTPS 주소로 새로 로그인하세요. IP 주소로 받은 기존 쿠키와는 별개입니다.

학생 접속 정보 API는 구성된 HTTPS origin, Caddy의 HTTPS 전달 정보, 올바른 암호화 키가 있어야 동작합니다. HTTP에서는 배정 전송/비밀정보 확인을 허용하지 않습니다.

## 3. 학생 준비

1. 학생 LMS 계정이 있어야 합니다. 회원가입이 꺼져 있으면 운영 절차에 따라 계정을 준비합니다.
2. 해당 학생이 과정에 수강신청하고 운영자가 승인합니다.
3. HTTPS 사이트 관리자 메뉴 **실습 환경 배정**에서 실제 학생 이메일·이름·학번·과정 ID를 확인합니다.

AWS IAM 사용자와 LMS 학생 계정은 서로 다른 계정입니다. 같은 이메일로 자동 추측하거나 이름 순서로 매칭하지 않습니다. 운영자가 학생별 이메일을 명시합니다. 이미 다른 학생에게 배정된 AWS 사용자/기존 학생의 다른 배정은 자동 교체하지 않습니다. 과정을 변경하거나 재배정할 때 기존 배정부터 확인하세요.

테스트 계정에 실제 학생을 임의 배정하지 마세요. 먼저 운영 절차로 등록된 시험 학생 1명의 수강을 승인하고 파일럿으로 확인합니다. AWS 관리자 계정을 학생에게 배정하지 않습니다.

## 4. PC GUI에서 배정 전송

PC PowerShell에서 관리 도구 실행을 종료한 뒤 소스를 갱신합니다:

```powershell
cd "$env:USERPROFILE\gju-lab-manager"
git pull --ff-only origin main
python infra/aws-lab/manager.py
```

사용자 홈의 기존 `.gju-lab-manager/` 운영 자료는 유지됩니다.

1. 기존 생성 환경(예: gju-ssm-pilot)을 불러옵니다.
2. 학생 목록의 **LMS 이메일** 칸에 관리자 화면에서 확인한 실제 이메일을 입력하고 **설정 저장**.
3. 전송할 학생만 선택합니다. AWS 환경은 이미 생성되어 있어야 하며 다시 생성하지 않습니다.
4. HTTPS LMS 관리자 → 실습 환경 배정 → 현재 LMS 관리자 비밀번호 재확인 → **일회용 전송 토큰 발급**.
5. PC GUI의 LMS 주소에 `https://lms.gju-boot.tbitcloud.com`, 과정 ID와 전송 토큰을 입력합니다.
6. **선택 학생을 LMS에 연결** → 대상/이메일 확인 후 전송.
7. LMS 배정 현황에서 연결 결과를 확인합니다. 한 번의 배치에서 오류가 나면 전체 배정을 롤백합니다. 전송 실패 시 성공 여부를 배정 화면에서 확인한 뒤 재시도하세요.

토큰은 15분 유효, 성공 전송 1회 사용이며 해시만 DB에 저장합니다. 실패한 트랜잭션은 소비하지 않지만 처리 후 응답이 유실됐다면 배정이 이미 완료됐을 수 있습니다. 토큰은 GUI 메모리에서만 사용하고 파일에 보관하지 않습니다. AWS 관리자 자격 증명은 전송하지 않습니다.

대체 방법: GUI의 **배정 JSON 내려받기** → LMS 관리자에서 파일 가져오기. 파일에는 초기/DB 비밀번호가 있으므로 공개 업로드/단체방/채팅/Git에 올리지 마세요. 이메일 연결 목록을 확인하고 관리자 비밀번호를 재확인한 후 가져옵니다.

## 5. 학생 화면

학생 로그인 → 내 강의실 → 승인된 과정의 **내 AWS 실습 환경**:
- AWS 콘솔 주소·IAM 사용자명·서버 ID·세션 문서.
- 브라우저 터미널·본인 S3 링크·DB 주소.
- **LMS 비밀번호 재확인 후** 최초 AWS 비밀번호·본인 DB 비밀번호 확인 또는 안내 파일 다운로드.

초기 AWS 비밀번호는 처음 로그인한 뒤 변경해야 합니다. 변경된 AWS 비밀번호는 홈페이지와 자동 동기화되지 않습니다. 비밀값은 페이지 HTML에 미리 넣지 않고 재인증 API로 받아 90초 뒤 화면에서 숨깁니다. 다운로드 파일은 학생이 별도로 안전하게 보관해야 합니다.

학생 조회는 로그인한 본인의 **승인된 수강신청**으로 한정합니다. 요청의 배정 ID나 이메일로 다른 학생 데이터를 고르지 않습니다. 수강 반려/과정 비공개/열람 중지 상태에서는 반환하지 않습니다. 관리자 페이지에도 AWS 비밀번호 전체 목록을 표시하지 않습니다.

## 6. 열람 중지·정리

- LMS **열람 중지**: 이후 웹 조회/다운로드 차단. 이미 받은 AWS 비밀번호·진행 중 AWS 세션을 무효화하는 기능이 아님.
- LMS **배정 삭제**: 열람 중지 후 저장된 배정/암호문 삭제. 새 환경 재배정 가능.
- 운영자 GUI **AWS 학생 삭제**: 실제 IAM·인프라 정리. **LMS 배정은 자동 중지하지 않으므로 먼저 열람 중지/배정 삭제**하세요. 생성 완료 데이터를 임의로 AWS 상태와 자동 동기화하지 않습니다.
- 배정·확인·다운로드·열람 중지 기록은 관리자 화면에서 확인. 로그에는 비밀번호/토큰 원문을 기록하지 않습니다.

## 검증 범위

Node 단위/경계 검사: 암호문 난수화·다른 학생 AAD로 복호화 거부·암호문 변조 거부·이메일 중복/식별자 검사·HTTPS/Origin 제한·재인증·소유자 필터·재배정 거부.
Python 검사: 환경 설정·권한 템플릿·GUI HTTP 보호·이메일 배정·HTTPS 전송·리디렉션 거부·HTTPS 설정 파일 변경 검사.
PostgreSQL 통합 검사: `npm run test:lab-integration` (전용 테스트 DB, LMS_INTEGRATION_TEST=true). 실제 DB에서 단일 사용 토큰·원자적 롤백·소유자별 데이터·반려/회수 상태를 검증하도록 CI에 추가했습니다. 이 개발 환경에는 PostgreSQL이 없어 해당 통합 검사는 로컬 미실행이며 CI 결과를 확인해야 합니다.

운영 DNS/인증서/실학생 배정의 실제 완료 판정은 위 운영 적용 후 수행합니다.

## DNS 담당자 작업 전: HTTP 상태에서 미리 준비하기

DNS를 다음 날 설정하는 경우 기존 HTTP 접속을 유지한 채 암호화 키와 새 DB 테이블을 준비할 수 있습니다. 이 단계는 인증서 발급이나 Caddy 설정 변경을 하지 않습니다.

기존 LMS 서버 SSH에서 명령을 하나씩 성공 확인하며 실행:

```bash
cd ~/gju-multicloud-lms
git pull --ff-only origin main
python3 scripts/prepare-lab-access.py --apply
bash scripts/backup.sh
docker compose -f compose.yaml -f compose.prod.yaml build web tools
docker compose -f compose.yaml -f compose.prod.yaml --profile tools run --rm tools npm run db:migrate
docker compose -f compose.yaml -f compose.prod.yaml up -d --no-deps web
```

현재 IP의 HTTP 사이트에서 관리자 메뉴 **실습 환경 배정**이 표시되고 준비 안내가 나오는지 확인하세요. 비밀번호 전송/토큰/학생 비밀번호 조회는 HTTPS 적용 전까지 차단된 상태입니다. Caddy를 재생성하거나 도메인용으로 바꾸지 마세요.

PC GUI는 소스를 갱신한 뒤 기존 환경을 불러와 실제 LMS 학생 이메일만 입력하고 설정을 저장할 수 있습니다. AWS 자원을 다시 생성하거나 HTTP 주소로 비밀번호를 전송하지 않습니다. 학생이 아직 가입하지 않았다면 임의의 이메일로 연결하지 말고 배정 목록만 준비하세요.

DNS 작업 후 기존 HTTPS 설정 절차를 진행하면 이미 준비한 암호화 키를 유지합니다.

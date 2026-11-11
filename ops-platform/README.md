# TBIT Cloud Ops — 별도 인프라 관리 웹 서비스

학생 LMS와 별도 컨테이너·DB·로그인·암호화 키를 사용하는 운영자 전용 서비스입니다. LMS 소스·스키마·Compose 구성은 변경하지 않습니다. 기존 AWS 로컬 관리자도 그대로 사용할 수 있습니다. 초기 운영은 단일 서버·단일 worker 구성입니다.

## 현재 제공 범위

| 기능 | AWS | NHN Cloud | NAVER Cloud |
|---|---|---|---|
| 기존 서버 조회·실행 상태·IP | EC2, 연결 리전 | 프로젝트 Instance, 연결 리전 | VPC Server, 연결 리전 |
| 교육·학생·팀에 자원 배정 | 지원 | 지원 | 지원 |
| 배정 서버 시작·중지 | 지원 | 지원 | 지원 |
| 교육 템플릿 생성·삭제 | 기존 서울 SSM 템플릿 | 미지원 | 미지원 |
| 기본 지표 | CloudWatch CPU | 서버 상태만 | 서버 상태만 |
| 메모리·디스크·비용 집계 | 미수집 | 미수집 | 미수집 |

기존 AWS 템플릿의 EC2·S3·RDS·공유 네트워크·학생 IAM 사용자 구성을 재사용합니다. 학생 수 1~30명, t3.micro/t3.small, Ubuntu 24.04, SSM 접속입니다. NHN·NAVER 생성·삭제, GPU/NKS/NCP Classic/공공/금융 리전, 자동 종료·자동 비용 예측, LMS 학생 배정 자동 전송은 이번 버전에 포함하지 않습니다. 지원하지 않는 기능을 완료한 것처럼 표시하지 않습니다.

실제 CSP 인증정보가 없는 상태에서는 실제 서버나 임의 예시를 표시하지 않습니다. 단위·HTTP·API 모의 응답·컨테이너 빌드 검사와 실제 CSP 운영 검증은 구분합니다. 연결 후에는 조회 전용으로 확인하고 파일럿 1명부터 생성·삭제를 검증하세요.

## 권한과 보관

- ADMIN: 클라우드 키 등록·교체, 변경 권한 설정, 계정 추가·중지, AWS 생성·삭제, 학생 개별 접속 자료 열람.
- OPERATOR: 현황·지표 조회, 교육 등록·자원 배정, 변경 허용 연결에서 배정 서버 시작·중지.
- VIEWER: 현황·기본 지표·작업 이력 조회.
- 현재 역할은 플랫폼 전체에 적용합니다. 교육별 세분화 권한은 지원하지 않습니다. 조회자는 연결한 계정의 자원 이름·주소를 볼 수 있습니다.
- 세션은 8시간, HttpOnly/Secure/SameSite 쿠키와 서버 DB 세션을 사용합니다. 공개 회원가입은 없습니다. 모든 변경 요청은 CSRF·Origin·권한 검사를 합니다. 로그인 실패 제한과 감사 기록을 제공합니다.
- 클라우드 키와 AWS 학생 접속 자료는 AES-256-GCM으로 암호화해 DB에 보관합니다. 암호문은 연결·교육 환경 ID에 결합됩니다. API 원문 오류·키·비밀번호를 작업 로그로 저장하지 않습니다.
- 관리자 비밀번호는 scrypt 해시만 저장합니다. 최초 관리자는 서버 터미널에서 생성합니다. 일반 계정은 관리자가 웹에서 추가하고 본인 비밀번호를 바꿀 수 있습니다. MFA·외부 SSO·계정 분실 초기화 UI는 아직 없습니다. 운영 네트워크/VPN 등의 추가 접근 제한은 기존 조직 정책을 따르세요.
- `.env`의 OPS_MASTER_KEY는 서버 전용이며 키를 잃으면 인증정보를 복호화할 수 없습니다. DB 백업과 암호화 키 백업은 별도로 보호하세요. 마스터 키 자동 순환은 지원하지 않습니다.
- SQLite WAL과 단일 worker를 사용합니다. 컨테이너 수나 uvicorn worker를 임의로 늘리지 마세요. 여러 사용자는 같은 서버에서 사용할 수 있지만 같은 연결의 클라우드 작업은 동시에 하나만 실행합니다.
- 작업 상태: QUEUED/RUNNING/SUCCEEDED/FAILED/INTERRUPTED. 서버 재시작 시 실행 중 작업은 중단 표시만 하며 자동으로 생성·삭제를 재시도하지 않습니다. 클라우드에서 작업이 계속될 수 있으니 상태 확인 후 수동 처리합니다.
- AWS 자격 정보 파일은 임시 메모리 파일시스템에만 풀며 클라우드 호출 전에 암호화 상태를 DB에 커밋합니다. 컨테이너 재시작 이후에도 생성한 학생 비밀번호 자료가 남습니다. 작업 원문 stdout/stderr는 웹에 저장하지 않습니다.

## 1. 배포 준비

Docker Compose v2가 있는 Linux 서버가 필요합니다. 같은 Lightsail에 별도 서비스로 올리거나 별도 서버에 올릴 수 있습니다. 초기에는 기존 서버의 CPU/메모리 여유를 먼저 확인하세요.

운영 URL은 예를 들어 `https://ops.tbitcloud.com`처럼 LMS와 다른 주소를 사용합니다. 실제 사용할 도메인의 A 레코드를 배포 서버 공인 IP로 연결하고 기존 HTTPS 프록시에서 이 서비스로 연결합니다. 예시 주소가 실제로 등록되었다는 뜻은 아닙니다.

**아래 명령은 LMS 서버 터미널에서 실행합니다. 학생 서버·Windows 관리자 도구에서 실행하는 명령이 아닙니다.**

```bash
cd ~/gju-multicloud-lms
git pull --ff-only origin main
cd ops-platform
python3 setup.py
# 사용할 HTTPS 주소를 입력합니다. .env 생성 시 키는 출력되지 않습니다.
docker compose build ops
docker compose run --rm --no-deps ops python -m cloudops.bootstrap
# 관리자 이메일과 새 비밀번호를 직접 입력합니다.
docker compose up -d ops
docker compose ps
docker compose logs --tail=30 ops
```

기존 LMS의 web/db 컨테이너를 빌드하거나 재시작하지 않습니다. `.env`는 기존 LMS 루트 `.env`와 별도입니다. 키가 이미 있으면 setup.py는 덮어쓰지 않습니다. Linux에서 `.env`는 0600 권한으로 생성됩니다.

## 2. 기존 LMS Caddy를 공유하는 경우

현재 프록시의 호스트 설정을 보존하고 **새 호스트 블록만 추가**합니다. 기존 LMS 호스트 블록을 교체하지 마세요.

`ops-platform/Caddyfile.example`의 예시를 실제 도메인으로 바꾸어 기존 Caddyfile 마지막에 추가합니다.

```caddyfile
ops.tbitcloud.com {
    encode zstd gzip
    reverse_proxy tbit-cloud-ops-ops-1:8780
}
```

루트 경로에서 아래 명령으로 실행 중인 Caddy를 운영 네트워크에 연결합니다. 기존 LMS 컨테이너를 재생성하지 않습니다. 먼저 ops 컨테이너가 실행되어 `tbit_ops_edge` 네트워크가 만들어져 있어야 합니다. 이미 네트워크에 연결한 경우 network connect는 생략하세요.

```bash
cd ~/gju-multicloud-lms
docker compose -f compose.yaml -f compose.prod.yaml -f ops-platform/lms-proxy.override.yaml config --quiet
ops_caddy_id="$(docker compose -f compose.yaml -f compose.prod.yaml ps -q caddy)"
test -n "$ops_caddy_id"
docker network connect tbit_ops_edge "$ops_caddy_id"
docker compose -f compose.yaml -f compose.prod.yaml -f ops-platform/lms-proxy.override.yaml exec caddy caddy validate --config /etc/caddy/Caddyfile
docker compose -f compose.yaml -f compose.prod.yaml -f ops-platform/lms-proxy.override.yaml exec caddy caddy reload --config /etc/caddy/Caddyfile
```

위 절차는 기존 프록시에 네트워크를 추가하고 설정만 reload합니다. 이후 계획된 Caddy 재생성 시에는 override 파일을 함께 사용해야 네트워크 연결이 유지됩니다. LMS web/db는 그대로 유지합니다. 다른 프록시라면 해당 프록시를 `tbit_ops_edge` 네트워크에 연결하고 Host/Origin을 원래 HTTPS 주소대로 전달하세요. 기존 80/443 포트를 차지하는 새 프록시를 추가 실행하지 않습니다. ops의 8780 포트는 호스트 loopback에만 바인딩되어 인터넷에 직접 열리지 않습니다.

## 3. 연결 등록

### AWS

실제 12자리 계정 ID와 리전, API 자격 정보를 입력합니다. EC2에 배포했다면 해당 서버의 IAM Role을 사용할 수도 있습니다. 일반 Lightsail에는 동일한 EC2 Role 방식이 자동 제공되는 것으로 가정하지 않습니다. 임시 키를 쓰면 Session Token도 입력하고 만료 후 웹에서 교체합니다. 읽기·모니터링 최소 권한 예: `ec2:DescribeInstances`, `cloudwatch:GetMetricStatistics`, STS 자기 계정 확인. 시작·중지는 별도 `ec2:StartInstances`/`ec2:StopInstances`가 필요합니다.

교육 생성·삭제는 기존 `infra/aws-lab` 도구에 필요한 CloudFormation·IAM·EC2·S3·RDS·SSM·Service Quotas 권한을 추가로 필요로 합니다. 연결을 추가했다고 AWS 권한이 자동 부여되지는 않습니다. 앱은 실제 AWS 계정을 STS로 비교하고 기존 템플릿은 LabId/StudentId/ManagedBy 소유권을 확인합니다.

### NHN Cloud

프로젝트의 **Tenant ID**, IAM ID, **API 비밀번호**, 리전(KR1: 판교/KR2: 평촌)을 입력합니다. 로그인 비밀번호나 예전에 역할 변경에 사용한 User Access Key Secret을 API 비밀번호 칸에 넣지 마세요. IaaS 토큰의 서비스 카탈로그에서 선택 리전의 compute 엔드포인트를 확인합니다. 여러 학생 프로젝트는 연결을 각각 등록합니다.

### NAVER Cloud

상용 VPC 환경의 Access Key/Secret Key와 리전 KR/SGN/JPN을 입력합니다. 계정 항목은 운영자가 알아볼 별칭이며 AWS STS와 같은 계정 ID 대조를 제공하지 않습니다. 등록된 키가 조회하는 실제 서버 목록을 먼저 확인하세요. Classic·공공·금융 API는 다른 엔드포인트이므로 지원하지 않습니다.

처음에는 모든 연결을 **조회 전용**으로 등록하고 동기화합니다. 생성·시작·중지·삭제가 필요한 연결에서만 관리자가 변경 허용을 켭니다. 키 교체·변경 권한 갱신은 관리자 비밀번호 재확인이 필요하며, 대기 작업은 이전 연결 버전이면 실행되지 않습니다.

## 4. 운영 흐름

1. 관리자 로그인 → 클라우드 연결 등록 → 지금 동기화.
2. 교육·해커톤 이름과 종료일 등록 → 기존 서버를 교육/학생/팀에 배정.
3. 허용된 연결에서 대상 서버 ID를 다시 입력해 시작·중지 요청.
4. AWS 새 교육은 환경 계획을 저장한 뒤 내용·학생 수·옵션을 확인합니다. 환경 이름과 계정 ID를 입력하여 생성합니다. 계획 저장은 실제 자원을 생성하지 않습니다.
5. 학생 접속 자료는 관리자 비밀번호 재확인 후 **한 학생씩** 다운로드합니다. 기존 학생 LMS의 자동 배정 API 연결은 후속 작업이며 현재 자동 전송하지 않습니다.
6. 작업 결과는 서버에 보관되어 운영자 PC를 꺼도 계속 실행합니다. 모니터링은 2분마다 연결 범위의 서버 상태를 읽고, 화면은 15초마다 상태를 확인합니다.
7. 종료일 경과는 화면에 표시할 뿐 자원을 자동 삭제하지 않습니다. AWS 삭제 시 선택한 환경의 학생 S3·DB 데이터가 사라지고 마지막 공유 네트워크가 삭제됩니다. 시작·중지와 과금 종료는 같지 않습니다. NHN·NAVER 삭제는 각 콘솔에서 별도 수행합니다.

현재 자원 목록은 서버 중심이며 S3·DB·IP·볼륨 전체 인벤토리를 제공하지 않습니다. 연결 오류가 생기면 이전 서버 목록을 유지하고 오류·마지막 확인 시각을 표시합니다. 미수집 값을 0으로 표시하지 않습니다.

## 5. 백업·업데이트

```bash
cd ~/gju-multicloud-lms/ops-platform
docker compose exec ops python /app/backup.py
# 백업은 ops_data 볼륨 /data/backups 아래에 생성됩니다.
# 복사할 때는 운영자 전용 보관처를 사용하고 .env 암호화 키는 별도 보관하세요.
```

업데이트는 루트에서 git pull 후 ops-platform으로 돌아와 `docker compose build ops`와 `docker compose up -d ops`만 실행합니다. 이때 실행 중 생성·삭제 작업이 없는지 먼저 확인하세요.

## 검증

```bash
python -m pip install -r ops-platform/requirements.txt
PYTHONPATH=ops-platform python -m unittest discover -s ops-platform/tests -v
```

- 공식 API 참고: [AWS 템플릿](../infra/aws-lab/README.md), [NHN Instance](https://docs.nhncloud.com/ko/Compute/Instance/ko/public-api/), [NHN IaaS 인증](https://docs.nhncloud.com/ko/nhncloud/ko/public-api/iaas-token/), [NAVER VPC 서버](https://api.ncloud-docs.com/docs/compute-vserver-getserverinstancelist), [NAVER 서명](https://api.ncloud-docs.com/docs/common-ncpapi).

실패한 다중 학생 생성·삭제의 자동 복구는 제공하지 않습니다. 생성 기록을 덮어쓰거나 같은 환경을 무작정 재생성하지 말고 CloudFormation 상태를 먼저 확인하세요. 현재 웹 화면은 일부 학생만 재시도하는 기능을 제공하지 않습니다.

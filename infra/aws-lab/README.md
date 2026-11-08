# 클라우드 실습 환경 관리자 v3

**운영자 PC에서 실행하는 GUI + AWS Session Manager 학생 접속**입니다. 공개 LMS에 AWS 관리자 키를 넣지 않습니다. 기본 접속 방식은 집 IP 등록·승인·SSH 키 없이 사용하는 브라우저 터미널입니다.

## 가능한 일

- 교육별 환경 설정 저장/불러오기. 새 이름으로 저장해 다른 교육에 재사용.
- 학생 1~30명, Ubuntu 서버(t3.micro / t3.small), 디스크 8~30GB, 개인 S3·RDS 선택.
- 선택 학생만 생성 / 상태 확인 / 삭제. 공용 VPC 자동 생성·재사용·마지막 학생 삭제 후 정리.
- AWS CLI 프로필과 실제 AWS 계정 확인, 계정 ID 검증 후 생성·삭제.
- 학생 한 명씩 개인 접속 안내 파일 내려받기. 초기 콘솔 비밀번호/DB 비밀번호 포함이므로 개별 전달.
- 진행 중 작업 로그. 동시에 두 개의 작업을 실행하지 않음.

**현재 지원 범위는 AWS 서울 리전, Ubuntu 24.04, EC2·S3·RDS 제공 자원 사용형 교육**입니다. 임의 CSP/OS/서비스를 만드는 범용 플랫폼은 아닙니다. 설정 저장은 실행 중인 AWS 자원을 변경하는 기능이 아니며 스택 업데이트/자동 복구는 지원하지 않습니다. 기존 SSH 환경을 자동 변환하지 않습니다. 새 교육 이름으로 생성하세요.

## 1. Windows PC에서 시작

Python 3.12 이상, Git, 최신 AWS CLI v2가 필요합니다. 추가 Python 패키지는 필요하지 않습니다. AWS CLI의 `aws login`은 2.32.0 이상에서 콘솔 로그인 기반 임시 인증을 지원합니다. 기존 IAM 사용자의 AdministratorAccess에 조직 제한이 없는지 확인하세요.

**아래는 PC의 PowerShell에서 실행합니다. CloudShell/학생 서버에서 GUI를 실행하지 않습니다.**

```powershell
git clone https://github.com/justgitmin/gju-multicloud-lms.git gju-lab-ops
cd gju-lab-ops
aws --version
aws login --profile gju-operator
```

브라우저에서 기존 운영자 IAM 사용자로 로그인합니다. 로그인 코드·토큰·AWS 키를 이 도구나 채팅에 붙여넣지 마세요. 기존 CLI 프로필을 이미 사용하는 경우 그 프로필을 그대로 쓸 수 있습니다. `aws login`을 지원하지 않는 CLI는 공식 배포판으로 업데이트하세요.

```powershell
python infra/aws-lab/manager.py
```

브라우저가 `http://127.0.0.1:8765`에서 열립니다. 또는 `infra/aws-lab/start-manager.bat`을 더블클릭해 실행합니다. 포트가 사용 중이면 `python infra/aws-lab/manager.py --port 8766`.

PC의 Python 명령이 `python`이 아니라 `py`라면 `py infra/aws-lab/manager.py`를 사용하세요. 실행 창을 닫으면 화면/API에 접속할 수 없습니다. 작업 중에는 창을 닫지 마세요.

## 2. GUI 사용 순서

1. **환경 설정:** 교육 고유 이름, 학생 수, 서버·디스크·S3·RDS를 선택.
2. **설정 저장·생성 목록 확인:** 이 단계는 AWS 자원을 생성하지 않음.
3. **AWS 연결:** 프로필 `gju-operator` 입력 → 계정 확인. 표시된 실제 계정 ID/사용자가 맞는지 확인.
4. 먼저 학생 **s01 한 명만** 선택하고 확인란에 환경 이름 입력 → 선택 학생 생성.
5. 상태 확인으로 CloudFormation 출력과 상태 확인. 생성 직후 SSM Agent 준비까지 시간이 걸릴 수 있음.
6. s01만 선택 → 접속 안내 내려받기. 본인 학생에게만 전달.
7. 실제 브라우저 접속·웹 배포·S3·DB와 상대 접근 거부 확인 후 나머지 학생만 생성.
8. 종료 시 필요한 제출물을 보관 → 선택 학생 삭제. 마지막 학생 삭제 시 공용 네트워크도 삭제.

**생성은 과금 자원을 만들고 삭제는 선택 학생 DB/S3 데이터를 최종 스냅샷 없이 삭제합니다.** 학생이 수강할 기간 동안 켜 둘 DB·디스크·공인 IPv4 비용도 고려하세요. 학생 수에 맞는 EC2 vCPU/RDS 한도도 별도 확인합니다. VPC/IGW는 생성 전 자동 여유 한도를 검사합니다. 기본 구성은 NAT Gateway를 만들지 않습니다.

설정/운영 자료는 기본적으로 PC 사용자 홈의 `.gju-lab-manager/`에 저장합니다:
- `configs/`: 교육별 설정. AWS 관리자 키는 저장하지 않음.
- `state/`: 학생별 초기 비밀번호·DB 비밀번호·출력 정보.
- 새 학습 환경은 SSH 개인 키를 만들지 않음.

AWS CLI가 임시 인증을 관리합니다. GUI는 CLI 프로필을 선택해 명령을 실행할 뿐 관리자 자격 증명을 직접 보관하지 않습니다. Windows 파일 접근 권한은 사용자 홈 ACL을 따르므로 개인 PC와 운영자 전용 보관처를 사용하세요. POSIX에서는 상태 폴더 0700/비밀 파일 0600을 사용합니다. 초기 비밀번호는 학생이 변경하면 더 이상 사용할 수 없습니다. 삭제 후 로컬 파일/백업은 자동 폐기하지 않습니다.

### 재사용과 실패 처리

- 기존 설정을 불러온 뒤 **환경 이름을 바꾸고 저장**하면 새 교육 설정으로 복사됩니다.
- 새 학생만 생성할 때 기존 학생 선택은 해제합니다. 기존 개인 자료를 덮어쓰지 않습니다.
- 이미 배포된 사양은 GUI의 값만 바꿔 저장해도 변경되지 않습니다. 변경된 구성은 새 환경에 적용하세요.
- 실패 시 작업 로그와 CloudFormation 이벤트를 확인하세요. 생성이 일부 완료됐을 수 있습니다. 무작정 같은 이름으로 재생성하거나 로컬 비밀번호 폴더를 지우지 마세요.
- 상태 확인에 없는 스택이 포함돼 있으면 오류가 날 수 있으므로 실제 존재하는 학생만 선택하세요.
- 도구를 다시 열어도 저장된 설정/비밀 파일은 유지됩니다. 지난 작업 로그는 메모리 기반으로, 종료 후 유지하지 않습니다.

## 3. 학생 접속 방식과 격리

- AWS 콘솔에 **개별 IAM 사용자**로 로그인 → 서울 → Session Manager → 세션 시작.
- 본인 서버 ID와 **`환경이름-shell` 세션 문서** 선택. 접속 안내의 직접 링크가 문서를 자동 선택하지 않으면 수동 선택.
- EC2의 기본 연결 버튼/문서로 접속하면 문서 권한 오류가 날 수 있습니다. 이 도구는 교육별 전용 세션 문서를 사용합니다.
- 문서에서 OS 사용자를 ubuntu로 지정합니다. 기본 계정 전역 `SSM-SessionManagerRunShell` 문서는 변경하지 않습니다.
- 학생은 본인 서버에만 StartSession 가능. 본인이 시작한 세션만 재개/종료할 수 있습니다. 다른 학생 세션 목록 일부는 콘솔 조회에 보일 수 있으나 연결/종료 권한은 주지 않습니다.
- SSH 22 인바운드·키페어는 만들지 않음. 웹 실습 80은 공개이며 다른 학생도 웹 페이지는 열 수 있음.
- 공용 VPC/서브넷, 학생별 서버·보안 그룹·S3·DB. 본인 DB는 본인 서버 보안 그룹에서만 3306 허용.
- 학생에게 IAM/네트워크/보안 그룹 변경·역할 전달·새 서비스/자원 생성 권한을 주지 않음.
- 서버 역할에는 SSM 연결 상태/채널에 필요한 작업만 부여. 학생이 sudo로 서버 역할 자격 증명을 얻을 수 있으므로 계정의 Parameter Store 읽기나 S3 권한은 역할에 부여하지 않음.
- 웹 서버는 공인 주소와 아웃바운드 HTTPS로 SSM에 연결. 인터넷 경로가 끊기거나 Agent가 중지되면 접속되지 않음.
- Ubuntu 공식 AMI의 SSM Agent를 UserData에서 시작. 실제 AWS에선 Agent 온라인 상태까지 확인해야 함.
- 기존 버전의 학생별 집 IP SSH 모드는 CLI에서 `access_mode: ssh`와 `ssh_cidrs`로 유지하지만 GUI는 SSM만 지원.

현재 정책에 강제 MFA·조직 정책·리소스 정책이 있으면 추가 조정이 필요할 수 있습니다. 세션에서 웹 서버 설정을 망가뜨리거나 에이전트를 종료하면 해당 학생 서버에 접속 장애가 생길 수 있습니다. 공유 네트워크까지 변경하는 IAM 권한은 없습니다.

## 4. 영상과 교안

기존 영상 자체를 다시 제작한 것은 아닙니다. LMS의 `/guide/aws`에 접속 보완 안내와 단계별 교안을 추가했고 AWS 영상 페이지와 실습 제출 화면에 연결했습니다.

| 영상 | 새 환경의 학생 작업 |
|---|---|
| AWS 01 | 개별 콘솔 계정·서울 리전·제공 자원 확인 |
| AWS 02 | 공용 VPC·웹/DB 서브넷·라우팅 조회 및 흐름 그리기 |
| AWS 03 | MobaXterm 대신 지정 문서로 Session Manager 접속 |
| AWS 04 | 브라우저 터미널에서 예제 파일 전체 내려받기·Nginx 배포 |
| AWS 05 | 본인 S3 직접 링크 → practice/ 파일 업로드·확인·삭제 |
| AWS 06 | 본인 서버에서 개인 RDS 주소로 최소 쿼리 |
| AWS 07 | 권한 요청문 작성 (IAM 변경 불허) |
| AWS 08 | 증빙·정리 목록 제출, 본인 파일 정리, 최종 삭제는 운영자 |

S3/RDS를 끈 교육은 해당 실제 업로드/DB 연결 미션을 수행할 수 없습니다. 전체 영상 실습은 둘 다 켜세요. NHN Cloud의 계정·프로젝트는 이 AWS 도구에서 생성하지 않습니다.

## 5. CLI 사용도 가능

CloudShell에서는 GUI 대신 기존 CLI를 계속 쓸 수 있습니다. 새 설정에는 집 IP가 필요하지 않습니다.

```bash
cp infra/aws-lab/config.example.json infra/aws-lab/config.local.json
# 처음에는 students를 ["s01"]로 수정하고 고유 lab_id 사용
python3 infra/aws-lab/lab.py plan --config infra/aws-lab/config.local.json
python3 infra/aws-lab/lab.py apply --config infra/aws-lab/config.local.json --confirm-account 실제12자리계정ID
python3 infra/aws-lab/lab.py status --config infra/aws-lab/config.local.json
python3 infra/aws-lab/lab.py destroy --config infra/aws-lab/config.local.json --confirm-account 실제12자리계정ID
```

GUI 자료는 PC의 전용 경로, CLI 기본 자료는 실행 폴더의 `.lab-state/`에 저장합니다. CloudShell에서 만든 자료를 GUI가 자동 가져오지는 않습니다. 기존 시험 자원은 이미 삭제한 상태이므로 새 환경 이름으로 시작하면 됩니다. 원격 AWS 자원은 도구를 닫거나 로그아웃해도 자동 삭제되지 않습니다.

삭제 시 학생 IAM 권한 차단 → 전용 비버전 S3 비우기 → 학생 스택 삭제 → 남은 같은 LabId 스택이 없을 때 공용 네트워크 삭제. 외부 추가 자원·버전 관리/Object Lock·보호 설정은 삭제를 막을 수 있습니다. 수동 스냅샷·백업·도구 외 자원은 별도 점검하세요.

## 검증

```bash
python3 -m unittest discover -s infra/aws-lab -p 'test_*.py' -v
```

- 기존 SSH 버전은 사용자와 실제 AWS 생성·접속·권한 시뮬레이션·개별/전체 삭제 검증 완료.
- 새 SSM 버전은 Python 테스트/템플릿 검사 및 GUI 모의 화면 검사 완료. **실제 AWS 신규 배포·SSM 접속은 미검증**. 1명 파일럿이 필요.
- GUI HTTP 요청의 로컬 호스트·토큰·출처 검증, 확인문구/계정 불일치 시 변경 방지, 경로 탈출 방지, 기존 비밀 파일 덮어쓰기 방지 등을 검사.
- CloudFormation은 W1011(비밀값 동적 참조 권장)을 NoEcho + 운영자 전용 파일 전달 설계로 제외하고 검사.

공식 참고:
- https://docs.aws.amazon.com/systems-manager/latest/userguide/getting-started-restrict-access-quickstart.html
- https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-schema.html
- https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html

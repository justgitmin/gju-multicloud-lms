# AWS 온라인 영상 실습 환경 — 운영자용

현재 AWS 01–08 영상의 `content/aws-*/lesson.json` 직접 미션과 `docs/STUDENT_LAB_GUIDE.md`에 맞춘 **제공 자원 사용형** 구성입니다. 학생이 VPC/EC2/RDS/IAM을 임의 생성하는 실습이 아닙니다. 실제 AWS 배포와 학생 간 접근 차단 시험은 아직 수행하지 않았습니다. 먼저 2명으로 파일럿 검증한 뒤 15명으로 확대하세요.

## 구성과 범위

- 서울 리전 한 곳, 학생별 CloudFormation 스택·IAM 사용자·VPC·Ubuntu 24.04 서버·SSH 키.
- 공인 IPv4 웹 서버 1대, 공개 HTTP 80, SSH 22는 운영자가 지정한 교육장 공인 IPv4 CIDR에서만 허용. 자동 Nginx 설치는 하지 않으므로 영상대로 학생이 설치합니다.
- 선택: 학생별 비공개 S3 버킷(`practice/` 경로에만 객체 쓰기/읽기/삭제), 학생별 RDS MySQL 1대.
- DB는 학생별 별도 VPC의 사설 서브넷에 배치하며 해당 학생 웹 서버 보안 그룹만 3306 접근을 허용합니다. DB 사용자 `labadmin`은 **본인 전용 DB의 관리자**입니다. 공용 DB 계정이 아닙니다.
- 학생 IAM: 서울 EC2 네트워크/인스턴스 등의 제한된 조회, 배정 서버 시작·중지·재부팅, 본인 S3 경로 조작, 본인 비밀번호 변경. IAM 권한 변경·액세스 키 생성·역할 전달·네트워크 변경·CloudFormation·자원 신규 생성·스냅샷 공유는 허용하지 않습니다.
- EC2 일부 조회 API는 다른 학생 자원 목록도 보여줍니다. 목록까지 숨기는 기능은 제공하지 않습니다. 비밀키·비밀번호는 목록/CloudFormation Outputs에 넣지 않습니다.
- IAM 정책과 동일한 permissions boundary를 설정합니다. 기존 계정의 리소스 기반 정책이나 조직 정책까지 분석하는 도구는 아닙니다. 새 사용자에게 그룹/추가 정책/직접 리소스 정책을 임의로 부여하지 마세요.
- 자원 이름과 스택 소유권을 확인한 후 관리 스택만 정리하며 LMS 서버·영상 보관 버킷은 대상으로 삼지 않습니다.

## 영상 대응

| 영상 | 학생 수행 | 운영자 제공 |
|---|---|---|
| AWS 01 | 로그인·서울 리전·실습 범위 확인 | 사용자별 로그인 정보 |
| AWS 02 | VPC·서브넷·라우팅 조회·흐름 그리기 | 네트워크 사전 구성 |
| AWS 03 | MobaXterm으로 SSH 접속 | 본인 서버 IP·ubuntu 사용자·개인 키 |
| AWS 04 | Nginx 설치·예제 전체 업로드·제목 변경·웹 확인 | 빈 Ubuntu 서버·예제 앱 |
| AWS 05 | 지정 버킷 `practice/`에 작은 파일 업로드·조회·삭제 | 본인 비공개 버킷의 직접 링크 |
| AWS 06 | 본인 서버에서 MySQL 클라이언트로 최소 쿼리 | DB 주소·labdb·labadmin·개별 비밀번호 |
| AWS 07 | 최소 권한 요청문 작성 | IAM 수정 권한은 불필요 |
| AWS 08 | 제출·보관/정리 목록 작성·업로드 파일 삭제·서버 중지 | 최종 인프라 삭제는 운영자 수행 |

S3/RDS를 끄면 해당 영상의 실제 업로드/DB 연결 미션은 수행할 수 없습니다. 전체 영상 실습에는 둘 다 켜세요.

## 실행 장소와 준비

**AWS 콘솔의 CloudShell**에서 관리자 신원으로 실행하는 방식을 권장합니다. Python 3, AWS CLI v2, ssh-keygen이 필요합니다. LMS의 읽기 전용 AWS 키를 관리자용으로 교체하지 마세요. 이 도구를 LMS 웹 서버에 연결하거나 학생에게 배포하지 마세요.

1. AWS 계정 ID와 서울 리전 확인.
2. Service Quotas에서 기존 사용량을 포함해 VPC/인터넷 게이트웨이, EC2 On-Demand Standard vCPU, RDS DB 인스턴스 한도 확인. 15명은 VPC 15개 이상과 EC2 30 vCPU 이상이 추가로 필요합니다. 기본 VPC 한도 5개이면 증설 필요.
3. EC2·EBS·공인 IPv4·RDS·S3는 과금될 수 있습니다. 무료 실습을 보장하지 않습니다. NAT Gateway는 만들지 않습니다. 학생별 신규 생성 권한은 주지 않아 생성 수를 사전 고정합니다. 저장소 업로드/네트워크 사용료까지 고정 상한을 보장하지는 않습니다.
4. 교육장 공인 IPv4 확인. 재택 학습은 출발지가 달라질 수 있으므로 개인별 설정/별도 접속망 설계가 필요합니다. 편의를 위해 SSH를 전체 공개하지 마세요.

## 1. 설정과 생성 목록 확인 (AWS 변경 없음)

저장소 루트에서:

```bash
cp infra/aws-lab/config.example.json infra/aws-lab/config.local.json
nano infra/aws-lab/config.local.json
python3 infra/aws-lab/lab.py plan --config infra/aws-lab/config.local.json
```

수정 항목:
- `lab_id`: 새 교육 실행마다 고유한 이름. 다른 환경과 공유하지 않습니다.
- `students`: 처음에는 `["s01", "s02"]`로 파일럿, 검증 후 나머지 학생 ID만 넣어서 추가 생성.
- `ssh_cidr`: 교육장 실제 공인 주소, 예: `실제공인IP/32`. 한 개의 IPv4 CIDR만 지원합니다.
- `instance_type`: t3.micro / t3.small, `volume_gb`: 8–30.
- `s3`, `rds`: true / false.
- `db_class`: db.t4g.micro / db.t4g.small.

`plan`은 자원을 생성하지 않고 선택 목록만 보여줍니다. 요금 견적이나 IAM 정책 시뮬레이션이 아닙니다.

## 2. 실제 생성 (과금 자원 생성)

운영자가 설정/한도를 확인한 뒤에만 실행합니다. 계정 ID는 비밀키가 아닙니다.

```bash
aws sts get-caller-identity
python3 infra/aws-lab/lab.py apply --config infra/aws-lab/config.local.json --confirm-account 실제12자리계정ID
```

학생별 순차 생성하며 RDS 때문에 시간이 걸립니다. 먼저 VPC/IGW 여유 한도를 읽기 전용으로 점검합니다. CloudFormation 이벤트에서 `CREATE_COMPLETE`를 확인하세요. AWS 실계정에서 스키마 검증과 생성이 성공해야 환경이 준비된 것입니다.

생성된 `.lab-state/<lab_id>-<student>/`에는:
- `credentials.json`: 해당 학생 콘솔 초기 비밀번호, 본인 DB 비밀번호
- `ssh-key`: 해당 학생 SSH 개인 키 (MobaXterm에서 선택)
- `outputs.json`: 콘솔 주소·서버 IP·S3 버킷 직접 링크·DB 주소
- `template.json`, `ssh-key.pub`: 관리 자료

**학생에게는 본인 로그인/키/접속 정보만 개별 전달합니다. 전체 디렉터리 묶음을 학생 단체방이나 공개 Git에 올리지 마세요.** 로컬 파일은 운영자만 읽도록 0600, 폴더는 0700으로 저장합니다. 사용자 첫 로그인 시 비밀번호 변경이 필요합니다. 별도 MFA 등록 권한은 이 기본 정책에 포함하지 않았습니다. 계정의 강제 MFA 정책이 있다면 별도 설계가 필요합니다.

CloudShell 자료도 유실될 수 있으므로 생성 직후 관리 가능한 비공개 장소로 보관하세요. 자격 증명은 홈페이지에 자동 표시하지 않습니다.

실패 시: 다른 학생까지 자동 진행하지 않고 중단합니다. 스택 이벤트를 확인하고 성공/실패 자원을 먼저 확인하세요. 기존 state를 덮어쓰거나 같은 이름의 계정을 가져오지 않습니다. 재시도는 실패 스택/키 파일을 운영자가 점검·정리한 뒤 수행합니다. 이 도구는 스택 업데이트/무인 재시도는 지원하지 않습니다.

## 3. 2명 파일럿 검증 (필수)

학생 s01/s02 각각 별도 브라우저 프로필로:
- 본인 첫 로그인/비밀번호 변경, 네트워크 조회, SSH 성공.
- Ubuntu에서 Nginx 설치, `examples/demo-app` **폴더 전체** 배포, 외부 HTTP와 버튼 동작 확인.
- 본인 S3 직접 링크로 이동 후 `practice/`에 업로드/다운로드/삭제 성공. 전체 버킷 목록 조회는 허용하지 않으므로 직접 링크 사용.
- 상대 학생 버킷 직접 링크·객체 읽기/쓰기 실패 확인.
- 상대 EC2 시작/중지/재부팅 실패, 본인 재부팅 성공 확인.
- EC2 신규 생성·보안 그룹 변경·다른 서비스 생성·IAM 정책 변경 실패 확인.
- 본인 웹 서버에서 본인 DB 연결 성공, 상대 DB 연결 실패 확인. `mysql -h 제공주소 -u labadmin -p labdb` 후 `SELECT 1; SELECT DATABASE();`. 비밀번호는 프롬프트에만 입력.
- RDS 콘솔 조회 권한은 주지 않습니다. 영상 06의 연결 미션은 제공 주소와 서버 내 클라이언트로 수행합니다.
- EC2 중지/시작 후 공인 IP가 바뀔 수 있으므로 콘솔에서 현재 IP를 확인합니다. 생성 시 outputs 파일의 IP는 자동 갱신되지 않습니다.
- 시험용 파일을 올린 상태에서 destroy 실행, 사용자/버킷/EC2/DB/VPC 삭제 완료 확인.

위 항목은 **검증 절차이며 수행 완료 기록이 아닙니다**. 계정의 SCP/리소스 정책/콘솔 추가 API 요구에 따라 보완이 필요할 수 있습니다.

## 4. 상태와 일괄 삭제

```bash
python3 infra/aws-lab/lab.py status --config infra/aws-lab/config.local.json
python3 infra/aws-lab/lab.py destroy --config infra/aws-lab/config.local.json --confirm-account 실제12자리계정ID
```

**destroy는 업로드 파일과 DB 데이터를 복구용 최종 스냅샷 없이 삭제합니다. 필요한 제출물을 먼저 보관하세요.** 설정의 학생 목록에 포함된 스택만 대상으로 합니다. 학생을 나눠 생성했다면 최종 전체 목록을 별도로 유지하세요.

삭제 순서: 스택의 LabId/StudentId/ManagedBy 검증 → 해당 학생 권한을 Deny로 변경 → 전용 S3 버킷 비우기 → 스택 삭제 대기. 생성/삭제는 원자적이지 않습니다. 중간 실패 시 완료된 학생과 남은 학생을 확인하세요. 이미 삭제된 학생은 config에서 제외하고 나머지를 진행합니다.

외부에서 버킷 버전 관리·Object Lock·삭제 방지·공용 연결을 추가하면 삭제가 막힐 수 있습니다. 버전 관리 버킷은 자동 비우지 않고 중단합니다. 별도로 만든 자원과 수동 스냅샷/백업은 자동 삭제 대상이 아닙니다. 스택 삭제 완료 후 계정 자원과 비용을 재확인하세요. 로컬 자격 증명은 자동 삭제하지 않으므로 보관 정책에 따라 폐기하세요.

## 로컬 검증

```bash
python3 -m unittest discover -s infra/aws-lab -p 'test_*.py' -v
```

공식 참고:
- https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ExamplePolicies_EC2.html
- https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html
- https://docs.aws.amazon.com/vpc/latest/userguide/amazon-vpc-limits.html
- https://documentation.ubuntu.com/aws/aws-how-to/instances/build-cloudformation-templates/

## 구현 시 확인한 검사 결과

- Python 단위 테스트 10개 통과: 자원 범위, 권한 경계, DB 접근 출발지, 비공개 버킷, 비밀값 출력 방지, 잘못된 삭제 대상/설정 거부 등.
- S3/RDS on/off 네 조합을 cfn-lint 서울 리전 스키마로 검사. W1011(비밀값에 동적 참조 권장)은 NoEcho 매개변수와 운영자 전용 0600 전달 파일을 쓰는 현재 배포 설계로 명시적으로 제외. Secrets Manager 동적 참조는 이 버전에 포함하지 않음.
- AWS API를 통한 실제 배포·로그인·교차 접근·삭제 시험은 미실행. IAM/서비스 정책 및 최신 콘솔 동작까지 보장하는 검증은 아님.

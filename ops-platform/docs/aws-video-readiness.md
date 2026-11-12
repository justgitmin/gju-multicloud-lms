# 광주대 AWS 영상 실습 준비

학교의 멀티클라우드 운영 계획(EC2·VPC·S3·RDS·IAM·운영 점검)과
현재 LMS AWS 8강, `/guide/aws`, 배포 템플릿을 대조한 구성입니다.
학교 계획안의 15명 내외 대신 이번에 확정된 멀티클라우드 학생 14명
(s01~s14)을 사용합니다. 실제 AWS 연결과 자원 생성 완료를 의미하지 않습니다.

## 준비 구성

| 영상 | 실제 환경 / 학생 작업 |
|---|---|
| AWS 01 | 개인 IAM 사용자, 서울 리전, 최초 비밀번호 변경, 허용 범위 확인 |
| AWS 02 | 공용 VPC 1개, 공인 웹 서브넷 1개, 사설 DB 서브넷 2개, IGW 경로 확인 |
| AWS 03 | SSH 개념은 영상으로 학습. 실제 접속은 개인 서버와 교육 전용 Session Manager 문서 |
| AWS 04 | Ubuntu 24.04, t3.micro, gp3 20GB. 학생이 Nginx와 예제 파일 전체를 설치 |
| AWS 05 | 학생별 비공개 S3, practice/ 경로 업로드·다운로드 |
| AWS 06 | 학생별 db.t4g.micro MySQL, SSD 20GB, labdb/labadmin. 본인 웹 서버에서만 3306 접근 |
| AWS 07 | 자기 서버·자기 S3 경로만 허용하는 IAM 경계, 네트워크·IAM 변경은 운영자 담당 |
| AWS 08 | 웹·저장소·DB 결과를 LMS에 제출. 세션 종료와 중지·삭제를 구분 |

프로필: `infra/aws-lab/config.gju-aws14.json`, 환경 이름 `gju-mc-2026-aws`.
IAM/EC2/S3/RDS는 각각 학생당 1개씩 총 14개이며, NAT Gateway는 생성하지 않습니다.
기본 환경에는 PEM/SSH 22 인바운드가 없습니다. 집 IP 등록은 필요하지 않습니다.
웹 80은 실습용으로 공개, DB는 비공개입니다. RDS는 비HA, 20GB, 자동 백업 보존 0일인
교육용 구성입니다. 생성 이후 사용 기간 동안 EC2·RDS·디스크·공인 IPv4 등의 비용이 발생합니다.

## 운영 순서

1. 기존 Ops의 AWS 연결을 등록합니다. 서울 리전, 실제 AWS 12자리 계정 ID,
   교육 인프라 생성 권한이 있는 운영자 인증정보를 사용합니다. 키는 채팅이나 학생 ZIP에 넣지 않습니다.
2. AWS 준비 화면의 **광주대 영상 실습 · 14명 설정 채우기**로 계획을 저장합니다.
   기존 NHN 교육을 선택하면 동일 이벤트의 저장 명단에서 이름을 연결합니다.
3. **생성 전 한도·사양 점검**을 실행합니다. VPC/IGW, 현재 EC2 Standard vCPU 사용량,
   RDS 개수·MySQL 사양 가용성을 실제 계정에서 조회합니다. 신규 14명은 t3.micro 기준
   추가 28 vCPU가 필요하므로 기본 한도로 생성 가능하다고 가정하지 않습니다.
4. **s01만 선택**하여 생성합니다. 계정·태그·자원 ID를 확인하고 SSM Agent Online,
   학생 IAM으로 지정 문서를 통한 ubuntu 접속, 웹 배포·외부 HTTP, S3 practice/ 업로드/다운로드,
   DB의 SELECT 1/SELECT DATABASE/시험 테이블을 실제 확인합니다.
5. 다른 학생 서버 세션·S3 경로와 IAM/네트워크 변경이 거절되는지 확인합니다.
   학생 초기 비밀번호 변경은 학생 본인이 수행합니다.
6. 검증 후 같은 환경에서 **s02~s14만 선택**하여 추가 생성합니다. 기존 s01 자료는 유지합니다.
   생성 기록이 있는 학생은 자동 재시도하거나 비밀번호를 덮어쓰지 않습니다.
7. **전체 학생별 ZIP 한 번에 다운로드** 후 운영자 전달 목록에서 준비된 학생 수를 확인합니다.
   내부 학생 ZIP만 해당 학생에게 전달합니다. 출력 미완료·식별 불일치는 제외됩니다.
8. AWS 실습·복습 퀴즈·결과 제출을 진행합니다. 최종 인프라 삭제는 운영자가 수행합니다.

한도 점검은 예산 차단이나 모든 AWS 할당량의 성공을 보증하지 않습니다. IAM·SSM·S3·RDS 등
실제 생성/접속 권한, 기존 환경 충돌, 가용 영역·계정 정책도 파일럿에서 확인해야 합니다.

## 학생별 ZIP

- `접속안내.txt`: 본인 IAM 로그인·초기 비밀번호, Session Manager 주소·서버·문서,
  S3 직접 주소, DB 접속 정보, 제출·종료 방법
- `access.json`: 같은 학생의 구조화된 접속 정보
- `웹앱_설치명령.txt`: 가이드와 동일한 Nginx 설치·예제 전체 다운로드·백업·배포 명령
- `demo-app/index.html`, `demo-app/assets/style.css`, `demo-app/assets/app.js`, README

예제 파일은 서버 터미널의 curl 명령으로 자동 다운로드됩니다. ZIP의 demo-app은 참고용
사본이며, Session Manager에서 PC 파일 업로드나 MobaXterm이 필수인 것은 아닙니다.
정적 앱 버튼은 실제 DB/API 연결 검증이 아닙니다. DB 검증은 MySQL 쿼리로 수행합니다.

출력의 Username·InstanceId·SessionDocument와 연결 계정을 대조하며, 운영자 키·다른 학생
비밀번호·CloudFormation 파라미터는 포함하지 않습니다. 기존 NHN ZIP/키/비밀번호는 변경하지 않습니다.

## 현재 상태 판정

계획 저장/코드 테스트와 실제 AWS 생성/실습 검증은 다릅니다. AWS 연결이 등록되지 않았다면
생성 완료나 학생 접속 성공으로 보고하지 않습니다. 배포 시 Ops만 갱신하고 운영 중인 LMS·DB·
Caddy·출석 서비스는 재시작하지 않습니다. LMS 가이드의 파일 다운로드 설명 보완은 다음 LMS
정기 배포 시 반영할 수 있으며, 기존 가이드의 다운로드 명령은 그대로 유효합니다.

사전 점검의 공식 API 근거:
- https://docs.aws.amazon.com/cli/latest/userguide/cli_service-quotas_code_examples.html
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/example_rds_DescribeAccountAttributes_section.html
- https://docs.aws.amazon.com/cli/latest/reference/rds/describe-orderable-db-instance-options.html
- https://docs.aws.amazon.com/systems-manager/latest/userguide/getting-started-specify-session-document.html

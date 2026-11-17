# 기존 AWS 학생 S3 권한 수정 (Ops)

1. 최신 main으로 Ops 서비스만 빌드·배포합니다. LMS 웹/DB와 학생 서버는 재시작하지 않습니다.
2. 교육 환경 일괄 준비 → AWS → 해당 환경 → 기존 학생 S3 권한 수정.
3. 대상 환경 이름, 실습 AWS 계정과 변경 내용을 확인하고 Ops 관리자 비밀번호를 입력합니다.
4. 기존 학생 S3 권한 수정을 실행합니다. 작업 기록에서 진행과 완료 여부를 확인합니다.
5. 학생 계정 S3 목록 → 본인 버킷 → 상위 목록 이동, EC2에서 URL 발급 → NHN PUT/GET을 확인합니다.

저장된 해당 연결의 인증만 사용합니다. 호스트의 Lightsail 역할을 사용하지 않습니다.
원문 API 응답이나 자격 증명은 작업 기록에 남기지 않습니다.
사용자 정책/권한 경계의 버킷 이름 목록 허용과 본인 EC2 역할의 practice/ PUT/GET만 추가합니다.
S3 버킷 이름 목록은 같은 AWS 계정의 다른 버킷 이름도 표시할 수 있지만 객체 접근은 본인 버킷만 허용합니다.
권한 경계 제거, 관리자 권한 전체 부여, Access Key 신규 발급은 하지 않습니다.

변경 세트에 IAM 자원 3개(Student, Boundary, NodeRole) 이외의 변경이나 교체가 있으면 중단합니다.
기존 사용자 정책과 경계가 다르거나 사용자 정의 OwnPracticeObjects가 있으면 자동으로 덮어쓰지 않습니다.
중간 실패 시 앞서 완료한 학생은 유지됩니다. CloudFormation 상태를 확인하고 재실행하세요.
실행 후 실제 사용자 검증이 필요하며 작업 성공만으로 모든 콘솔 부가기능이 허용됨을 의미하지 않습니다.

배포 명령 (기존 저장소·ops-platform/.env 사용):

```bash
cd ~/gju-multicloud-lms
git pull --ff-only origin main
docker compose -f ops-platform/compose.yaml build ops
docker compose -f ops-platform/compose.yaml up -d --no-deps ops
```

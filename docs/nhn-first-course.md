# NHN 먼저 학습하는 운영 방식

NHN 영상 8강 → NHN 실습(MobaXterm SSH) → AWS 영상 8강 → AWS 실습(Session Manager).
각 클라우드 영상 이수 직후 해당 쉬운 퀴즈를 풀 수 있습니다. 실습 승인 대기는 다음 영상 학습을 막지 않습니다.

- 학생 안내: `/guide/nhn`, `/guide/aws`. 로그인 필요.
- NHN은 기존 학생 서버를 사용하며 Bastion 웹 터미널을 추가 생성하지 않습니다.
- NHN 개인별 전달: IAM 콘솔 URL, 프로젝트/계정, 최초 비밀번호, 공인 IP, ubuntu 사용자, 해당 서버의 PEM 키. 키는 본인에게만 안전하게 전달합니다.
- SSH 22는 해당 학생의 현재 공인 IP/32를 운영자가 허용합니다. 운영자 IP만 등록한 파일럿은 학생 PC에서 접속되지 않습니다. HTTP 실습의 80번도 확인합니다.
- Object Storage 컨테이너·DB는 별도 배정이 필요합니다. 가이드 배포가 실제 자원 생성을 대신하지 않습니다.
- 현재 AWS 생성 도구는 SSH 키/22번 없이 Session Manager를 사용합니다. MobaXterm은 SSH용 키와 접근 설정을 별도로 제공한 인스턴스에서만 선택합니다. EC2 Instance Connect는 Session Manager와 다릅니다.
- 기존 영상 파일은 변경하지 않습니다. 영상의 생성/접속/순서 차이는 차시 미션과 가이드로 안내합니다. 기존 NHN 실습 제출문에 AWS 비교표가 있다면 AWS 학습 후 보완합니다.

## 운영 서버 반영

```bash
cd ~/gju-multicloud-lms
bash scripts/backup.sh
git pull --ff-only origin main
docker compose -f compose.yaml -f compose.prod.yaml build web tools
docker compose -f compose.yaml -f compose.prod.yaml --profile tools run --rm tools npm run db:order-course
docker compose -f compose.yaml -f compose.prod.yaml up -d --no-deps web
```

`COURSE_ORDER_OK`를 확인합니다. 알려진 16개 강의가 모두 있을 때만 하나의 트랜잭션으로 순서·과정명을 갱신합니다. 영상 키·시간·버전·진도·제출·퀴즈 기록을 변경하지 않습니다. 반복 실행 가능합니다. 이미 완료한 강의는 순서 변경 후에도 다시 볼 수 있습니다. 가이드는 운영자 역할로도 확인 가능합니다.

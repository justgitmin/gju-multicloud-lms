# NHN 우선 과정의 선택 영상 교체

변경 대상은 NHN 01·02·03·04·05·08 및 AWS 08입니다. 나머지 9편은 소스·MP4·자막·미디어 등록 정보를 유지합니다. 선택 이유와 변경 목록은 nhn-first-video-changes.json, 기술 검증은 nhn-first-video-verification.json을 참조합니다.

- NHN 01: AWS 없이 시작하는 입문과 학습 순서.
- NHN 02: AWS 선행 설명 없이 주소·길·문으로 네트워크 설명.
- NHN 03: 배정 서버의 MobaXterm SSH·키 선택, 첫 예제 앱으로 연결.
- NHN 04: NHN에서 처음 예제 앱을 배포하고 AWS 비교는 이후 수행.
- NHN 05: 앞선 S3 실습을 전제하지 않는 객체 저장소 설명.
- NHN 08: NHN 결과를 먼저 기록하고 AWS 실습 후 비교표 보완.
- AWS 08: NHN으로 넘어간다는 기존 마무리를 두 실습의 결과 비교로 변경.

NHN 06·07의 비교 미션은 NHN08과 실습 가이드의 안내에 따라 AWS 실습 후 보완합니다. 독립적으로 설명하는 개념 영상은 그대로 사용합니다.

사용자가 변경 대본의 Microsoft 음성 합성 서비스 전송을 승인한 뒤 동일 음성으로 제작했습니다. 음성 문장 범위·파일 디코딩·음성/영상 시간·페이지 경계·자막 일치의 기술 검증을 수행합니다. 사람의 전 구간 청취·발음 검수는 별도입니다.

## 반영 순서

1. GJU_NHN_First_Changed_7_Videos.zip의 압축을 해제합니다.
2. 포함된 courses 폴더 구조를 유지하여 기존 비공개 영상 버킷에 업로드합니다. 새 v2 경로의 MP4 7개와 captions-ko.vtt 7개입니다. 기존 v1 경로는 삭제하거나 덮어쓰지 않습니다. 버킷 전체를 공개하지 않습니다.
3. MP4는 video/mp4, 자막은 text/vtt Content-Type으로 업로드합니다. 포함된 UPLOAD_VIDEOS.ps1을 사용할 수도 있습니다.
4. LMS 운영 서버에서 다음을 실행합니다.

```bash
cd ~/gju-multicloud-lms
bash scripts/backup.sh
git pull --ff-only origin main
docker compose -f compose.yaml -f compose.prod.yaml build web tools
docker compose -f compose.yaml -f compose.prod.yaml --profile tools run --rm tools npm run media:register-course
docker compose -f compose.yaml -f compose.prod.yaml up -d --no-deps web
```

등록은 전체 16개 MP4와 16개 자막의 해시·크기·형식을 검증한 뒤 한 트랜잭션으로 실행합니다. 하나라도 누락되면 DB 등록 전에 실패합니다. 변경된 7편만 새 콘텐츠 버전이 되어 재이수가 필요할 수 있으며 과거 진도 기록은 보존합니다. 나머지 9편의 버전은 유지됩니다.

반영 후 학생 계정에서 NHN01 도입·NHN03 MobaXterm·NHN08/AWS08 마무리와 자막을 확인하세요. 이 파일 묶음 제작 자체가 운영 버킷 업로드나 서버 배포를 수행하지는 않습니다.

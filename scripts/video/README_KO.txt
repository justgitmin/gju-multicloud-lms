NHN 먼저 학습하는 과정 — 변경된 7편만 포함

NHN 01·02·03·04·05·08 / AWS 08의 음성·화면·자막 수정본입니다.
나머지 9편과 기존 v1 영상은 유지합니다. NHN06·07의 비교 미션은 NHN08 안내대로 AWS 실습 후 보완합니다.
기술적 음성 문장 누락·영상/음성 시간·페이지 전환·자막 동기화 검증을 수행했습니다. 사람의 최종 전 구간 청취·발음 검수는 별도입니다.

1. ZIP 전체를 압축 해제합니다.
2. S3에 courses 폴더의 구조를 유지하여 7개 MP4와 7개 VTT를 업로드합니다.
   MP4 Content-Type: video/mp4, VTT Content-Type: text/vtt. 버킷 공개 설정은 변경하지 않습니다.
   기존 v1 파일을 덮어쓰지 않고 v2 경로에 추가합니다.
3. AWS CLI를 사용하는 Windows에서는 압축 해제한 폴더에서 다음으로 업로드할 수 있습니다.
   powershell -ExecutionPolicy Bypass -File .\UPLOAD_VIDEOS.ps1 -Bucket 실제영상버킷이름 -Profile gju-operator
   해당 버킷에 접근 가능한 실제 프로필을 사용합니다. 버킷이나 프로필을 추측하지 마세요.
4. LMS 서버에서 수정된 main 코드를 받은 뒤 tools 이미지를 다시 빌드하고 등록합니다.
   git pull --ff-only origin main
   docker compose -f compose.yaml -f compose.prod.yaml build web tools
   docker compose -f compose.yaml -f compose.prod.yaml --profile tools run --rm tools npm run media:register-course
   docker compose -f compose.yaml -f compose.prod.yaml up -d --no-deps web
5. 16개 영상과 자막 검증 후 등록 성공 메시지를 확인합니다. 실패 시 DB 등록은 진행되지 않습니다.

실제 내용이 변경된 7편은 새 콘텐츠 버전으로 등록되므로 해당 강의의 재이수가 필요할 수 있습니다. 과거 기록은 남고 나머지 9편 버전은 유지됩니다.
학생 계정으로 NHN1 도입, NHN3 MobaXterm, NHN8/AWS8 마무리와 자막을 확인하세요.

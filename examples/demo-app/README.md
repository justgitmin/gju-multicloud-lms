# 공통 정적 앱
index.html과 assets 폴더 전체를 같은 상대 경로로 배포합니다.
이 앱은 DB·AWS·NHN API를 호출하지 않습니다. 선택한 환경 이름은 표시용이며 실제 상태를 검증하지 않습니다.
Ubuntu Nginx 예시 문서 루트는 /var/www/html이지만 기존 서버 설정을 먼저 확인하세요.
로컬 시험: 이 디렉터리에서 `python3 -m http.server 8080 --bind 127.0.0.1` 실행 후 브라우저로 localhost:8080 접속.

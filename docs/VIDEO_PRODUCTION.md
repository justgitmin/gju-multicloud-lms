# 자체 영상 제작 계획

AWS 8편 60분, NHN 8편 60분. 편별 주제·길이는 lib/curriculum.ts 기준.

## 형식
- 1920×1080 MP4, 자막 WebVTT, 대본 Markdown, 학습목표·실습 안내
- 직접 작성한 개념 설명·구조도·명령어 예시 사용
- 실제 콘솔 시연은 실제 계정에서 수행·녹화·검증한 경우만 표시
- 자동 생성 음성 사용 시 음질·발음·서비스 이용조건 검증
- 목표 길이에 맞춰 무의미한 정지 화면이나 반복으로 늘리지 않음

## 제작 순서
1. 계정·리전·권한·비용·종료 절차 대본
2. AWS 네트워크와 EC2 학습자료 및 영상 1편 제작
3. 음성·자막·글자 크기·실습 일치 검수
4. 나머지 AWS·NHN 콘텐츠 제작
5. ffprobe로 길이 검증, 해시와 버전 기록
6. 실제 지정된 버킷 업로드 및 승인 계정 재생 시험

영상은 아직 제작·업로드되지 않았다. S3 버킷과 배포 권한은 확정 후 연결한다.

## 첫 강의 제작
- `content/aws-01/lesson.json`: 8개 장면의 자체 대본·화면 문구·공식 출처.
- `scripts/video/render_lesson.py`: 한국어 합성 음성, 문장 단위 자막, 1920×1080 MP4 제작.
- Pillow·edge-tts, ffmpeg·ffprobe, 한국어 글꼴이 필요합니다. 글꼴은 재배포하지 않으며 `--font`로 제공해야 합니다.
- 실행 예: `python scripts/video/render_lesson.py content/aws-01/lesson.json /absolute/output --font /absolute/font.otf`
- 합성 음성은 ko-KR-SunHiNeural을 사용합니다. 임의의 사람 목소리를 복제하지 않습니다.
- 음성 서비스 연결·이용조건과 최종 청취·발음 검수는 실제 배포 전에 확인합니다. 재생 시간을 늘리기 위한 반복·무음은 추가하지 않습니다.
- MP4는 자막을 화면에 포함하며 별도 WebVTT도 생성합니다.
- 등록 예: `npm run media:register -- aws-01 /absolute/aws-01.mp4 /absolute/aws-01.vtt`
- 현재 S3·Lightsail 업로드 및 실제 학습자 재생 시험은 미실행입니다.

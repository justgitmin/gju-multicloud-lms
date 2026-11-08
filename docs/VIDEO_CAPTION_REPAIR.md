# 영문 기술 용어 자막 수정

전체 16편의 영상 내 자막과 VTT에서 발음용 한글 표기를 표준 영문으로 교정했습니다. 176개 문장을 수정했습니다.

- AWS, NHN Cloud, VPC, EC2, S3, IAM, RDS, SSH, IP/IPv4, TCP, CPU, API, HTTP/HTTPS, HTML, PC
- MySQL, Nginx, Ubuntu, Linux, GitHub, Lightsail, MP4, WebVTT, ETag, Access Denied
- A/B 선택지, SSH -i, TCP 22번, 예시 CIDR 주소

원본 음성용 narration은 유지하고 captions.py의 표시 계층에서만 변환합니다. 음성 합성 없이 검증된 캐시로 재렌더링했습니다. 영상 내 자막과 VTT는 동일한 표시 문자열 및 기존 프레임 타이밍을 사용합니다. 전체 16편의 음성 파형·화면 전환·자막 문장 검사를 통과했습니다.

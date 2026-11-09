export const awsMissions = [
  {
    "id": "aws-01",
    "title": "계정 확인",
    "task": "내 AWS 실습 환경에서 본인 계정·서울 리전·서버 ID를 확인합니다.",
    "skip": "개인 결제 계정을 만들지 않습니다.",
    "success": "본인 IAM 사용자와 서울 리전 확인",
    "step": 1
  },
  {
    "id": "aws-02",
    "title": "네트워크 확인",
    "task": "공유 VPC와 사용자→웹 서버→사설 DB 흐름을 확인합니다.",
    "skip": "VPC·서브넷·라우팅은 운영자가 준비합니다. 새로 만들거나 수정하지 않습니다.",
    "success": "네트워크 흐름을 한 줄로 설명",
    "step": 3
  },
  {
    "id": "aws-03",
    "title": "브라우저 접속",
    "task": "Session Manager에서 본인 서버와 지정 세션 문서를 선택합니다.",
    "skip": "영상의 SSH·MobaXterm·개인 키·집 IP 등록은 이번 실습에서 수행하지 않습니다.",
    "success": "whoami 결과 ubuntu",
    "step": 2
  },
  {
    "id": "aws-04",
    "title": "웹 앱 배포",
    "task": "가이드 명령으로 Nginx와 예제 앱 파일 전체를 배포합니다.",
    "skip": "이미 배정된 EC2를 사용합니다. 중복 생성하지 않습니다.",
    "success": "내 서버 공인 IP에서 제목·스타일·버튼 확인",
    "step": 4
  },
  {
    "id": "aws-05",
    "title": "S3 파일 실습",
    "task": "본인 S3 직접 링크의 practice/에 test.txt를 올리고 다운로드합니다.",
    "skip": "전체 버킷 목록이 안 보일 수 있습니다. 공개 설정을 바꾸지 않습니다.",
    "success": "다운로드한 파일 내용 일치",
    "step": 5
  },
  {
    "id": "aws-06",
    "title": "DB 연결",
    "task": "본인 학생 서버에서 mysql로 본인 DB에 연결합니다.",
    "skip": "RDS 생성·보안 그룹 변경은 하지 않습니다. 웹 앱 버튼은 DB 연결 증거가 아닙니다.",
    "success": "1과 labdb, 시험 테이블 조회 결과 확인",
    "step": 6
  },
  {
    "id": "aws-07",
    "title": "최소 권한 이해",
    "task": "허용된 작업과 제한된 작업을 한 줄씩 정리합니다.",
    "skip": "IAM 정책을 직접 수정하거나 다른 학생 자원을 변경하지 않습니다.",
    "success": "필요한 권한만 사용하는 이유 설명",
    "step": 7
  },
  {
    "id": "aws-08",
    "title": "제출과 복습",
    "task": "AWS 결과를 제출하고 AWS 복습 퀴즈를 풉니다.",
    "skip": "최종 인프라 삭제는 운영자 담당입니다. 세션을 종료하고 재사용 여부를 확인합니다.",
    "success": "AWS 8강 이수 후 AWS 퀴즈 바로 응시",
    "step": 8
  }
];

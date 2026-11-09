export const nhnMissions = [
  {
    "id": "nhn-01",
    "title": "계정과 프로젝트 확인",
    "task": "개별 안내의 IAM 콘솔에 로그인하고 본인 프로젝트를 선택합니다.",
    "skip": "LMS와 클라우드 계정은 별개입니다. 개인 결제 계정은 만들지 않습니다.",
    "success": "본인 프로젝트와 IAM ID 확인",
    "step": 1
  },
  {
    "id": "nhn-02",
    "title": "네트워크 확인",
    "task": "배정된 VPC·서브넷·인터넷 경로를 확인합니다.",
    "skip": "네트워크 생성·변경은 운영자가 담당합니다.",
    "success": "사용자→웹→DB 흐름 설명",
    "step": 3
  },
  {
    "id": "nhn-03",
    "title": "MobaXterm SSH 접속",
    "task": "개인 키와 본인 서버 공인 IP로 MobaXterm에 접속합니다.",
    "skip": "Bastion을 만들지 않습니다. SSH 허용 IP 등록은 운영자에게 요청합니다.",
    "success": "whoami 결과 ubuntu",
    "step": 2
  },
  {
    "id": "nhn-04",
    "title": "예제 웹 앱 배포",
    "task": "Nginx와 예제 앱 파일 전체를 배포합니다.",
    "skip": "AWS 수강 전에도 이 가이드의 같은 예제 앱으로 진행합니다.",
    "success": "제목·스타일·버튼 동작 확인",
    "step": 4
  },
  {
    "id": "nhn-05",
    "title": "Object Storage 파일 실습",
    "task": "배정된 컨테이너에 시험 파일을 올리고 내려받습니다.",
    "skip": "컨테이너가 없으면 운영자에게 요청합니다. 공개 전환하지 않습니다.",
    "success": "다운로드 내용 일치",
    "step": 5
  },
  {
    "id": "nhn-06",
    "title": "본인 DB 연결",
    "task": "학생 서버에서 배정된 DB에 접속합니다.",
    "skip": "DB 미배정이면 운영자에게 요청합니다. 직접 생성하지 않습니다.",
    "success": "SELECT 1 결과 확인",
    "step": 6
  },
  {
    "id": "nhn-07",
    "title": "상태와 로그 확인",
    "task": "Nginx 상태와 서비스 로그를 확인합니다.",
    "skip": "다른 학생의 설정이나 로그를 변경하지 않습니다.",
    "success": "상태와 로그 한 줄 설명",
    "step": 7
  },
  {
    "id": "nhn-08",
    "title": "제출과 쉬운 복습",
    "task": "NHN 결과를 제출하고 NHN 퀴즈로 바로 복습합니다.",
    "skip": "AWS 비교 항목은 AWS 학습 후 보완합니다. 인프라 삭제는 운영자 담당입니다.",
    "success": "NHN 8강 이수 후 NHN 퀴즈 응시",
    "step": 8
  }
];

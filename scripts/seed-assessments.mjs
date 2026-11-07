import {PrismaClient} from '@prisma/client';
const db=new PrismaClient();
const make=(prompt,options)=>({prompt,options});
const content=[{id:'aws',title:'AWS 핵심서비스 확인 평가',questions:[
make('EC2 인스턴스에 대한 인바운드 접근을 제한하는 설정은?', ['Security Group','S3 객체 키','결제 통화','리전 이름']),
make('웹 서버에는 공개 접근이 필요하지만 DB는 웹 서버에서만 접근해야 한다. 적절한 방식은?', ['DB를 모든 IP에 공개','DB 포트를 웹 서버 보안 그룹에만 허용','모든 방화벽 해제','DB 비밀번호를 웹 페이지에 게시']),
make('S3에 저장한 비공개 파일의 접근을 관리할 때 적절한 방법은?', ['버킷 전체 공개','AWS 키를 브라우저에 포함','최소 권한과 제한된 접근 권한 사용','비밀번호를 파일명으로 사용']),
make('최소 권한 원칙에 맞는 행동은?', ['모든 학생에게 관리자 권한 부여','루트 계정 공유','필요 없는 권한까지 미리 부여','실습에 필요한 작업과 리소스만 허용']),
make('실습을 마친 뒤 비용을 점검하는 방법은?', ['인스턴스만 중지하면 모든 비용 종료','잔여 DB·디스크·IP 등 과금 자원도 확인','브라우저만 종료','SSH 창만 닫기'])],key:[0,1,2,3,1]},
{id:'nhn',title:'NHN Cloud·멀티클라우드 비교 평가',questions:[
make('멀티클라우드 서비스를 비교하는 올바른 기준은?', ['상품명 철자가 같은지','콘솔 색상이 같은지','기능·보안·비용·운영 요구사항','로고 크기']),
make('프로젝트 권한을 관리할 때 적절한 방법은?', ['팀원 전원에게 불필요한 권한 부여','공용 관리자 비밀번호 게시','개인 키를 Git에 커밋','담당 업무에 맞는 최소 권한 부여']),
make('인스턴스 SSH 접속이 안 될 때 먼저 확인할 항목은?', ['네트워크 경로·보안 설정·주소·접속키','영상 배속','문서 글자색','브라우저 즐겨찾기 순서']),
make('운영 모니터링의 목적은?', ['모든 알림 끄기','서비스 상태·자원 사용·장애 징후 확인','비밀번호 공유','로그 삭제만 수행']),
make('AWS와 NHN에 같은 앱을 배포하는 실습의 핵심은?', ['양사 기능이 완전히 동일하다고 가정','코드를 전혀 다른 앱으로 변경','공통 구조와 플랫폼별 운영 차이 비교','보안을 모두 해제해 비교'])],key:[2,3,0,1,2]}];
try{await db.$transaction(async tx=>{
 for(const [index,item] of content.entries()){
 await tx.lab.upsert({where:{id:`${item.id}-lab`},create:{id:`${item.id}-lab`,courseId:'gju-multicloud-2026',title:item.id==='aws'?'AWS 웹 서비스 구축 실습':'NHN Cloud 구축·서비스 비교 실습',position:index+1,instructions:item.id==='aws'?'네트워크와 웹 서버 구성, 저장소 접근 설정, DB 연결 결과를 정리하세요.\n접속 결과와 오류 해결 과정, 리소스 정리 내역을 설명하고 필요한 증빙 주소를 첨부하세요.':'동일 웹 앱의 NHN 배포 결과, 네트워크·스토리지·DB 운영 결과를 정리하세요.\nAWS와의 기능 비교표 및 멀티클라우드 아키텍처 초안, 자원 정리 내역을 제출하세요.'},update:{}});
 await tx.quiz.upsert({where:{id:`${item.id}-quiz`},create:{id:`${item.id}-quiz`,courseId:'gju-multicloud-2026',title:item.title,questions:item.questions,answerKey:item.key},update:{}});
 }
});console.log('Two labs and two quizzes prepared. Existing content preserved.');}finally{await db.$disconnect();}

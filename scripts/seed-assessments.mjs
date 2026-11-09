import {PrismaClient} from '@prisma/client';
const db=new PrismaClient();
const make=(prompt,options)=>({prompt,options});
const content=[{"id":"aws","title":"AWS 쉬운 복습 퀴즈","questions":[{"prompt":"서버에 접속할 때 이번 실습에서 사용하는 방법은?","options":["브라우저 Session Manager","개인 SSH 키를 새로 만들기"]},{"prompt":"웹 페이지를 제공하는 프로그램은?","options":["MySQL","Nginx"]},{"prompt":"test.txt는 어디에 올리나요?","options":["다른 학생 버킷","내 S3 버킷의 practice/ 경로"]},{"prompt":"DB 연결은 어디에서 확인하나요?","options":["내 학생 서버의 터미널","개인 PC에서 공개 DB로 접속"]},{"prompt":"실습 인프라의 최종 삭제는 누가 하나요?","options":["학생이 공유 VPC까지 삭제","운영자가 일괄 정리"]}],"key":[0,1,1,0,1]},{"id":"nhn","title":"NHN Cloud 쉬운 복습 퀴즈","questions":[{"prompt":"NHN Cloud 실습을 시작할 때 확인할 것은?","options":["배정된 프로젝트와 권한","다른 학생의 비밀번호"]},{"prompt":"AWS와 NHN에 배포할 예제 앱은?","options":["서로 전혀 다른 앱","같은 예제 웹 앱"]},{"prompt":"Object Storage에 보관하는 것은?","options":["파일 같은 객체","서버 로그인 비밀번호를 공개한 목록"]},{"prompt":"서비스에 문제가 생기면 무엇을 확인하나요?","options":["모든 로그 삭제","서비스 상태와 로그"]},{"prompt":"다른 학생의 인프라는 어떻게 다루나요?","options":["임의로 바꾸지 않기","내 자원처럼 삭제하기"]}],"key":[0,1,0,1,0]}];
try{await db.$transaction(async tx=>{
 for(const [index,item] of content.entries()){
 await tx.lab.upsert({where:{id:`${item.id}-lab`},create:{id:`${item.id}-lab`,courseId:'gju-multicloud-2026',title:item.id==='aws'?'AWS 웹 서비스 구축 실습':'NHN Cloud 구축·서비스 비교 실습',position:index+1,instructions:item.id==='aws'?'네트워크와 웹 서버 구성, 저장소 접근 설정, DB 연결 결과를 정리하세요.\n접속 결과와 오류 해결 과정, 리소스 정리 내역을 설명하고 필요한 증빙 주소를 첨부하세요.':'동일 웹 앱의 NHN 배포 결과, 네트워크·스토리지·DB 운영 결과를 정리하세요.\nAWS와의 기능 비교표 및 멀티클라우드 아키텍처 초안, 자원 정리 내역을 제출하세요.'},update:{}});
 const existing=await tx.quiz.findUnique({where:{id:`${item.id}-quiz`}});
 const changed=existing&&(JSON.stringify(existing.questions)!==JSON.stringify(item.questions)||JSON.stringify(existing.answerKey)!==JSON.stringify(item.key));
 await tx.quiz.upsert({where:{id:`${item.id}-quiz`},create:{id:`${item.id}-quiz`,courseId:'gju-multicloud-2026',title:item.title,questions:item.questions,answerKey:item.key},update:{title:item.title,...(changed?{questions:item.questions,answerKey:item.key,version:{increment:1}}:{})}});
 }
});console.log('Easy quizzes prepared. Changed questions receive a new version; past attempts and lab content retained.');}finally{await db.$disconnect();}

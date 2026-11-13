import {NextResponse} from 'next/server';
import {currentUser,allowAttempt} from '../../../../lib/auth';
import {verifyPassword} from '../../../../lib/password.mjs';
import {db} from '../../../../lib/db';
import {labRequestAllowed,limitedJson,privateHeaders} from '../../../../lib/lab-http';
export const dynamic='force-dynamic';
export async function POST(request:Request){
 if(!labRequestAllowed(request))return NextResponse.json({error:'HTTPS와 실습 정보 보호 설정을 확인하세요.'},{status:403,headers:privateHeaders});
 const user=await currentUser();if(user?.role!=='ADMIN')return NextResponse.json({error:'관리자 로그인이 필요합니다.'},{status:403,headers:privateHeaders});
 if(!await allowAttempt('lab-roster',user.id,10))return NextResponse.json({error:'잠시 후 다시 요청하세요.'},{status:429,headers:privateHeaders});
 try{
  const input=await limitedJson(request,2000);
  if(typeof input.password!=='string'||input.password.length>128||!await verifyPassword(input.password,user.passwordHash))throw new Error('관리자 비밀번호를 확인하세요.');
  if(typeof input.courseId!=='string'||!input.courseId||input.courseId.length>100)throw new Error('과정을 선택하세요.');
  const course=await db.course.findFirst({where:{id:input.courseId,published:true},select:{id:true,title:true}});if(!course)throw new Error('공개된 교육과정을 선택하세요.');
  const rows=await db.enrollment.findMany({where:{courseId:course.id,status:'APPROVED',user:{role:'STUDENT'}},select:{id:true,user:{select:{id:true,name:true,email:true,studentNumber:true}},labAccess:{select:{labId:true,studentCode:true}}},orderBy:{id:'asc'},take:31});
  if(rows.length>30)throw new Error('현재 Ops는 환경당 최대 30명을 지원합니다. 교육을 나눠 주세요.');
  const roster={version:1,kind:'approved-enrollments',courseId:course.id,courseTitle:course.title,exportedAt:new Date().toISOString(),students:rows.map(e=>({userId:e.user.id,enrollmentId:e.id,name:e.user.name,email:e.user.email,studentNumber:e.user.studentNumber,assignedLabId:e.labAccess?.labId??'',assignedCode:e.labAccess?.studentCode??''}))};
  await db.labAccessAudit.create({data:{actorId:user.id,event:'EXPORT_APPROVED_ROSTER'}});
  return new NextResponse(JSON.stringify(roster,null,2),{headers:{...privateHeaders,'Content-Type':'application/json; charset=utf-8','Content-Disposition':'attachment; filename="lms-approved-students.json"'}});
 }catch(error){return NextResponse.json({error:error instanceof Error&&!error.message.includes('prisma')?error.message:'명단을 조회하지 못했습니다.'},{status:400,headers:privateHeaders});}
}

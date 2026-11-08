import {NextResponse} from 'next/server';
import {currentUser,allowAttempt} from '../../../lib/auth';
import {verifyPassword} from '../../../lib/password.mjs';
import {db} from '../../../lib/db';
import {decryptLab,labAad,type LabPublic} from '../../../lib/lab-secrets.mjs';
import {labRequestAllowed,limitedJson,privateHeaders} from '../../../lib/lab-http';
export const dynamic='force-dynamic';
export async function POST(request:Request){
 if(!labRequestAllowed(request))return NextResponse.json({error:'HTTPS 환경에서만 접속 정보를 제공합니다.'},{status:403,headers:privateHeaders});
 const user=await currentUser();if(!user)return NextResponse.json({error:'로그인이 필요합니다.'},{status:401,headers:privateHeaders});
 if(!await allowAttempt('lab-secret',user.id,10))return NextResponse.json({error:'요청이 많습니다. 15분 후 다시 시도하세요.'},{status:429,headers:privateHeaders});
 try{const {courseId,password,mode}=await limitedJson(request,2000);
  if(typeof courseId!=='string'||courseId.length>100||typeof password!=='string'||password.length>128||!await verifyPassword(password,user.passwordHash))throw new Error();
  const row=await db.labAccess.findFirst({where:{active:true,enrollment:{userId:user.id,courseId,status:'APPROVED',course:{published:true}}}});
  if(!row)throw new Error();const publicData=row.publicData as LabPublic;
  const secrets=decryptLab(row.secretData,labAad(row.enrollmentId,row));
  await db.labAccessAudit.create({data:{actorId:user.id,event:mode==='download'?'DOWNLOAD':'VIEW',assignmentId:row.id}});
  return NextResponse.json({publicData,secrets},{headers:privateHeaders});
 }catch{return NextResponse.json({error:'LMS 비밀번호와 본인 수강 승인·배정 상태를 확인하세요.'},{status:400,headers:privateHeaders});}
}

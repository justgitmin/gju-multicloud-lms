import {createHash,randomBytes} from 'node:crypto';
import {NextResponse} from 'next/server';
import {currentUser,allowAttempt} from '../../../../lib/auth';
import {verifyPassword} from '../../../../lib/password.mjs';
import {db} from '../../../../lib/db';
import {labRequestAllowed,limitedJson,privateHeaders} from '../../../../lib/lab-http';
export const dynamic='force-dynamic';
export async function POST(request:Request){
 if(!labRequestAllowed(request))return NextResponse.json({error:'HTTPS와 암호화 키 설정을 먼저 완료하세요.'},{status:403,headers:privateHeaders});
 const user=await currentUser();if(user?.role!=='ADMIN')return NextResponse.json({error:'관리자 로그인이 필요합니다.'},{status:403,headers:privateHeaders});
 if(!await allowAttempt('lab-token',user.id,5))return NextResponse.json({error:'요청이 많습니다. 잠시 후 다시 시도하세요.'},{status:429,headers:privateHeaders});
 try{const {password}=await limitedJson(request,2000);if(typeof password!=='string'||password.length>128||!await verifyPassword(password,user.passwordHash))throw new Error('비밀번호를 확인하세요.');
  const token=randomBytes(32).toString('hex');const expiresAt=new Date(Date.now()+15*60*1000);
  await db.labTransferToken.create({data:{tokenHash:createHash('sha256').update(token).digest('hex'),adminId:user.id,expiresAt}});
  await db.labAccessAudit.create({data:{actorId:user.id,event:'ISSUE_TRANSFER_TOKEN'}});
  return NextResponse.json({token,expiresAt:expiresAt.toISOString()},{headers:privateHeaders});
 }catch{return NextResponse.json({error:'비밀번호 또는 요청 형식을 확인하세요.'},{status:400,headers:privateHeaders});}
}

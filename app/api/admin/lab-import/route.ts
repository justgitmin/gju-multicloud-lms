import {createHash} from 'node:crypto';
import {NextResponse} from 'next/server';
import {currentUser,allowAttempt} from '../../../../lib/auth';
import {verifyPassword} from '../../../../lib/password.mjs';
import {db} from '../../../../lib/db';
import {importLabBatch} from '../../../../lib/lab-import';
import {labRequestAllowed,limitedJson,privateHeaders} from '../../../../lib/lab-http';
export const dynamic='force-dynamic';
export async function POST(request:Request){
 const bearer=request.headers.get('authorization');
 if(!labRequestAllowed(request,{bearer:!!bearer}))return NextResponse.json({error:'HTTPS와 암호화 키 설정이 필요합니다.'},{status:403,headers:privateHeaders});
 try{
  let actorId:string,tokenId:string|undefined;
  const input=await limitedJson(request);
  if(bearer){
   const token=bearer.startsWith('Bearer ')?bearer.slice(7):'';if(!/^[a-f0-9]{64}$/.test(token))throw new Error('전송 토큰을 확인하세요.');
   const row=await db.labTransferToken.findUnique({where:{tokenHash:createHash('sha256').update(token).digest('hex')}});
   if(!row||row.consumedAt||row.expiresAt<=new Date()||(await db.user.findUnique({where:{id:row.adminId}}))?.role!=='ADMIN')throw new Error('전송 토큰이 만료되었거나 이미 사용되었습니다.');
   actorId=row.adminId;tokenId=row.id;
  }else{
   const user=await currentUser();if(user?.role!=='ADMIN')throw new Error('관리자 로그인이 필요합니다.');actorId=user.id;
   if(!await allowAttempt('lab-import',user.id,10))throw new Error('요청이 많습니다. 잠시 후 다시 시도하세요.');
   if(typeof input.password!=='string'||input.password.length>128||!await verifyPassword(input.password,user.passwordHash))throw new Error('관리자 비밀번호를 확인하세요.');
  }
  const summary=await importLabBatch(input.batch,actorId,tokenId);
  return NextResponse.json({count:summary.length,students:summary},{headers:privateHeaders});
 }catch(error){const message=error instanceof Error&&!error.message.includes('prisma')&&!error.message.includes('Invalid')?error.message:'배정 충돌 또는 처리 오류입니다. 배정 현황을 확인하세요.';return NextResponse.json({error:message},{status:400,headers:privateHeaders});}
}

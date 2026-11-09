import {randomBytes} from 'node:crypto';
import {NextResponse} from 'next/server';
import {currentUser,allowAttempt} from '../../../../lib/auth';
import {db} from '../../../../lib/db';
import {hashPassword,verifyPassword} from '../../../../lib/password.mjs';
import {sameOrigin} from '../../../../lib/origin.mjs';
import {limitedJson,privateHeaders} from '../../../../lib/lab-http';
const reply=(body:object,status=200)=>NextResponse.json(body,{status,headers:privateHeaders});
export async function POST(request:Request){
 if(!sameOrigin(request.headers.get('origin'),request.headers.get('host'),process.env.APP_ORIGIN))return reply({error:'요청 주소를 확인하세요.'},403);
 const admin=await currentUser();if(admin?.role!=='ADMIN')return reply({error:'관리자 로그인이 필요합니다.'},403);
 if(!await allowAttempt('account-reset',admin.id,5))return reply({error:'15분 동안 5회까지 발급할 수 있습니다.'},429);
 let data;try{data=await limitedJson(request,4096);}catch{return reply({error:'입력 내용을 확인하세요.'},400);}
 if(!data||typeof data.userId!=='string'||data.userId.length>100||typeof data.adminPassword!=='string'||data.confirm!==true)return reply({error:'학생 확인과 관리자 비밀번호를 입력하세요.'},400);
 if(!await verifyPassword(data.adminPassword,admin.passwordHash))return reply({error:'관리자 비밀번호를 확인하세요.'},403);
 const target=await db.user.findUnique({where:{id:data.userId},select:{id:true,role:true,email:true}});
 if(!target||target.role!=='STUDENT')return reply({error:'학생 계정만 초기화할 수 있습니다.'},400);
 const password=randomBytes(18).toString('base64url');const passwordHash=await hashPassword(password);const expiresAt=new Date(Date.now()+24*60*60*1000);
 await db.$transaction(async tx=>{
  // Lock the operator revision against a concurrent credential reset/change.
  const active=await tx.user.updateMany({where:{id:admin.id,role:'ADMIN',passwordVersion:admin.passwordVersion},data:{passwordVersion:admin.passwordVersion}});
  if(active.count!==1)throw new Error('STALE_OPERATOR');
  await tx.user.update({where:{id:target.id},data:{passwordHash,passwordVersion:{increment:1},mustChangePassword:true,temporaryPasswordExpiresAt:expiresAt}});
  await tx.session.deleteMany({where:{userId:target.id}});
  await tx.accountAudit.create({data:{actorId:admin.id,targetUserId:target.id,event:'TEMPORARY_PASSWORD_ISSUED'}});
 });
 return reply({email:target.email,temporaryPassword:password,expiresAt:expiresAt.toISOString()});
}

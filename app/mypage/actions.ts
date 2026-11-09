'use server';
import {redirect} from 'next/navigation';
import {revalidatePath} from 'next/cache';
import {db} from '../../lib/db';
import {requireUser,allowAttempt,destroySession} from '../../lib/auth';
import {validPassword,verifyPassword,hashPassword} from '../../lib/password.mjs';
const value=(form:FormData,key:string)=>typeof form.get(key)==='string'?String(form.get(key)):'';
function fail(path:string,message:string):never{redirect(`${path}?error=${encodeURIComponent(message)}`);}
export async function updateProfile(form:FormData){
 const user=await requireUser();const name=value(form,'name').trim();
 if(name.length<2||name.length>60)fail('/mypage','이름은 2~60자로 입력하세요.');
 if(!await allowAttempt('profile',user.id,10))fail('/mypage','요청이 많습니다. 잠시 후 다시 시도하세요.');
 await db.user.update({where:{id:user.id},data:{name}});
 revalidatePath('/mypage');redirect('/mypage?saved=1');
}
export async function changePassword(form:FormData){
 const user=await requireUser({allowPasswordChange:true});
 if(!await allowAttempt('password-change',user.id,5))fail('/mypage/password','15분 동안 5회까지 시도할 수 있습니다.');
 const current=value(form,'currentPassword'),password=value(form,'password');
 if(!validPassword(password)||password!==value(form,'confirmation'))fail('/mypage/password','새 비밀번호 12~128자와 확인 값이 일치하는지 확인하세요.');
 if(current===password)fail('/mypage/password','현재 비밀번호와 다른 새 비밀번호를 입력하세요.');
 if(!await verifyPassword(current,user.passwordHash))fail('/mypage/password','현재 비밀번호를 확인하세요.');
 const passwordHash=await hashPassword(password);
 const changed=await db.$transaction(async tx=>{
  const result=await tx.user.updateMany({where:{id:user.id,passwordVersion:user.passwordVersion},data:{passwordHash,passwordVersion:{increment:1},mustChangePassword:false,temporaryPasswordExpiresAt:null}});
  if(result.count!==1)return false;
  await tx.session.deleteMany({where:{userId:user.id}});
  await tx.accountAudit.create({data:{actorId:user.id,targetUserId:user.id,event:'PASSWORD_CHANGED'}});return true;
 });
 if(!changed)fail('/mypage/password','계정 정보가 변경되었습니다. 다시 로그인하세요.');
 await destroySession();redirect('/login?changed=1');
}

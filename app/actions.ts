'use server';
import {redirect} from 'next/navigation';
import {revalidatePath} from 'next/cache';
import {Prisma} from '@prisma/client';
import {db} from '../lib/db';
import {hashPassword,verifyPassword,validPassword} from '../lib/password.mjs';
import {allowAttempt,createSession,destroySession,requireUser,requireAdmin} from '../lib/auth';
const value=(f:FormData,key:string)=>typeof f.get(key)==='string' ? String(f.get(key)) : '';
function fail(path:string,message:string):never { redirect(`${path}?error=${encodeURIComponent(message)}`); }
export async function register(form:FormData){
 if(process.env.ENABLE_REGISTRATION!=='true')fail('/register','현재 회원가입 준비 중입니다. 교육 운영자에게 문의하세요.');
 const email=value(form,'email').trim().toLowerCase();const name=value(form,'name').trim();const studentNumber=value(form,'studentNumber').trim();const password=value(form,'password');
 if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||email.length>254||name.length<2||name.length>60||studentNumber.length<2||studentNumber.length>30||!validPassword(password)||value(form,'consent')!=='on')fail('/register','입력 항목과 개인정보 안내 동의를 확인하세요. 비밀번호는 12~128자입니다.');
 if(!await allowAttempt('register','global',50)||!await allowAttempt('register',email,3))fail('/register','요청이 많습니다. 15분 후 다시 시도하세요.');
 try{const user=await db.user.create({data:{email,name,studentNumber,passwordHash:await hashPassword(password)}});await createSession(user.id);}
 catch(error){if(error instanceof Prisma.PrismaClientKnownRequestError&&error.code==='P2002')fail('/register','가입할 수 없는 이메일입니다. 기존 계정으로 로그인하거나 운영자에게 문의하세요.');throw error;}
 redirect('/classroom');
}
export async function login(form:FormData){
 const email=value(form,'email').trim().toLowerCase();const password=value(form,'password');
 if(email.length>254||password.length>128)fail('/login','이메일 또는 비밀번호를 확인하세요.');
 if(!await allowAttempt('login','global',300)||!await allowAttempt('login',email,10))fail('/login','로그인 시도가 많습니다. 15분 후 다시 시도하세요.');
 const user=await db.user.findUnique({where:{email}});
 // A valid dummy hash keeps missing-user attempts on the same scrypt path.
 const encoded=user?.passwordHash??`scrypt:${'0'.repeat(32)}:${'0'.repeat(128)}`;
 const valid=await verifyPassword(password,encoded);
 if(!user||!valid)fail('/login','이메일 또는 비밀번호를 확인하세요.');
 if(user.mustChangePassword&&(!user.temporaryPasswordExpiresAt||user.temporaryPasswordExpiresAt<=new Date()))fail('/login','임시 비밀번호가 만료되었습니다. 운영자에게 재발급을 요청하세요.');
 try{await createSession(user.id,user.passwordVersion);}catch(error){if(error instanceof Error&&error.message==='STALE_CREDENTIALS')fail('/login','비밀번호가 변경되었습니다. 다시 로그인하세요.');throw error;}
 redirect(user.mustChangePassword?'/mypage/password':user.role==='ADMIN'?'/admin':'/classroom');
}
export async function logout(){await destroySession();redirect('/login');}
export async function enroll(form:FormData){
 const user=await requireUser();const courseId=value(form,'courseId');
 const course=await db.course.findFirst({where:{id:courseId,published:true}});
 if(!course)fail('/classroom','신청할 수 없는 과정입니다.');
 await db.enrollment.upsert({where:{userId_courseId:{userId:user.id,courseId}},create:{userId:user.id,courseId},update:{}});
 revalidatePath('/classroom');redirect('/classroom');
}
export async function reviewEnrollment(form:FormData){
 await requireAdmin();const id=value(form,'enrollmentId');const status=value(form,'status');
 if(status!=='APPROVED'&&status!=='REJECTED')fail('/admin','올바르지 않은 승인 상태입니다.');
 await db.enrollment.update({where:{id},data:{status}});revalidatePath('/admin');revalidatePath('/classroom');
}

import { createHash,randomBytes } from 'node:crypto';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { db } from './db';
const cookieName='lms_session';
const digest=(value:string)=>createHash('sha256').update(value).digest('hex');
export async function currentUser(){
 const token=(await cookies()).get(cookieName)?.value;
 if(!token||!/^[a-f0-9]{64}$/.test(token))return null;
 const session=await db.session.findUnique({where:{tokenHash:digest(token)},include:{user:true}});
 if(!session||session.expiresAt<=new Date())return null;
 return session.user;
}
export async function requireUser(){const user=await currentUser();if(!user)redirect('/login');return user;}
export async function requireAdmin(){const user=await requireUser();if(user.role!=='ADMIN')redirect('/classroom');return user;}
export async function createSession(userId:string){
 const jar=await cookies();const previous=jar.get(cookieName)?.value;
 if(previous)await db.session.deleteMany({where:{tokenHash:digest(previous)}});
 const token=randomBytes(32).toString('hex');
 const expiresAt=new Date(Date.now()+7*24*60*60*1000);
 await db.session.create({data:{userId,tokenHash:digest(token),expiresAt}});
 jar.set(cookieName,token,{httpOnly:true,secure:(process.env.APP_ORIGIN??'').startsWith('https://'),sameSite:'lax',path:'/',expires:expiresAt});
}
export async function destroySession(){const jar=await cookies();const token=jar.get(cookieName)?.value;if(token)await db.session.deleteMany({where:{tokenHash:digest(token)}});jar.delete(cookieName);}
// Shared DB counters prevent per-process limit bypass. Deliberately avoid trusting proxy IP headers.
export async function allowAttempt(scope:string,identifier:string,limit:number){
 const windowMs=15*60*1000;const bucket=Math.floor(Date.now()/windowMs);
 const key=digest(`${scope}:${identifier}:${bucket}`);
 const row=await db.rateLimit.upsert({where:{key},create:{key,count:1,expiresAt:new Date((bucket+1)*windowMs)},update:{count:{increment:1}}});
 return row.count<=limit;
}

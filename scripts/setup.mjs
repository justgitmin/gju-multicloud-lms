import {PrismaClient} from '@prisma/client';
import {modules} from '../lib/curriculum.ts';
import {hashPassword,validPassword} from '../lib/password.mjs';
const db=new PrismaClient();
try{
 const email=process.env.ADMIN_EMAIL?.trim().toLowerCase();const password=process.env.ADMIN_PASSWORD;
 if(!email||!email.includes('@')||!validPassword(password))throw new Error('Set ADMIN_EMAIL and ADMIN_PASSWORD (12–128 characters) in the process environment.');
 const existing=await db.user.findUnique({where:{email}});
 if(existing)throw new Error('Account already exists. Refusing to change its password or role.');
 await db.$transaction(async tx=>{
 await tx.user.create({data:{email,name:'교육 운영자',passwordHash:await hashPassword(password),role:'ADMIN'}});
 await tx.course.upsert({where:{id:'gju-multicloud-2026'},create:{id:'gju-multicloud-2026',title:'AWS·NHN Cloud 멀티클라우드 운영',published:true},update:{}});
 });
 for(const [moduleIndex,module] of modules.entries()){for(const [i,title] of module.lessons.entries()){const id=`${module.id}-${String(i+1).padStart(2,'0')}`;await db.lesson.upsert({where:{id},create:{id,courseId:'gju-multicloud-2026',title,position:moduleIndex*8+i+1,durationSeconds:module.durationSeconds[i]},update:{}});}}
 console.log('Administrator and course initialized.');
}finally{await db.$disconnect();}

import {PrismaClient} from '@prisma/client';
import {modules} from '../lib/curriculum.ts';
const db=new PrismaClient();
try{await db.$transaction(async tx=>{
 await tx.course.upsert({where:{id:'gju-multicloud-2026'},create:{id:'gju-multicloud-2026',title:'NHN Cloud·AWS 멀티클라우드 운영',published:true},update:{}});
 for(const [mi,module] of modules.entries())for(const [i,title] of module.lessons.entries()){
 const id=`${module.id}-${String(i+1).padStart(2,'0')}`;
 await tx.lesson.upsert({where:{id},create:{id,courseId:'gju-multicloud-2026',title,position:mi*8+i+1,durationSeconds:module.durationSeconds[i]},update:{}});
 }
});console.log('16 lesson records prepared. Existing videos and versions preserved.');}finally{await db.$disconnect();}

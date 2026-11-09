import {PrismaClient} from '@prisma/client';
import {modules} from '../lib/curriculum.ts';
import {reorderCourse} from '../lib/course-order.mjs';
const db=new PrismaClient();
try{await db.$transaction(tx=>reorderCourse(tx,modules),{isolationLevel:'Serializable',timeout:30000});console.log('COURSE_ORDER_OK NHN videos → NHN practice → AWS videos → AWS practice. Existing media, versions, progress and attempts preserved.');}finally{await db.$disconnect();}

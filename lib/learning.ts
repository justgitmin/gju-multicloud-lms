import {canOpenLesson} from './lesson-prerequisite.mjs';
import {db} from './db';
import {currentUser} from './auth';
export async function lessonAccess(lessonId:string){
 const user=await currentUser();if(!user)return null;
 const lesson=await db.lesson.findUnique({where:{id:lessonId},include:{course:true}});
 if(!lesson||!lesson.course.published)return null;
 const enrollment=await db.enrollment.findUnique({where:{userId_courseId:{userId:user.id,courseId:lesson.courseId}}});
 if(!enrollment||enrollment.status!=='APPROVED')return null;
 const previous=await db.lesson.findMany({where:{courseId:lesson.courseId,position:{lt:lesson.position}},select:{id:true,version:true}});
 const done=await db.progress.findMany({where:{enrollmentId:enrollment.id,completedAt:{not:null}}});
 if(!canOpenLesson(lesson,previous,done))return null;
 return {user,lesson,enrollment};
}

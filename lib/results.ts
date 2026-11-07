import {db} from './db';
import {completion} from './assessment.mjs';
export async function results(enrollmentId:string){
 const enrollment=await db.enrollment.findUniqueOrThrow({where:{id:enrollmentId},include:{course:{include:{lessons:true,labs:true,quizzes:{select:{id:true,version:true}}}},progress:true,submissions:true,attempts:{select:{quizId:true,version:true,score:true}}}});
 const completedLessons=enrollment.course.lessons.filter(l=>enrollment.progress.some(p=>p.lessonId===l.id&&p.version===l.version&&p.completedAt)).length;
 const approvedLabs=enrollment.course.labs.filter(l=>enrollment.submissions.some(s=>s.labId===l.id&&s.status==='APPROVED')).length;
 const passedQuizzes=enrollment.course.quizzes.filter(q=>enrollment.attempts.some(a=>a.quizId===q.id&&a.version===q.version&&a.score>=70)).length;
 const counts={approved:enrollment.status==='APPROVED',lessons:enrollment.course.lessons.length,completedLessons,labs:enrollment.course.labs.length,approvedLabs,quizzes:enrollment.course.quizzes.length,passedQuizzes};
 return {...counts,complete:completion(counts)};
}

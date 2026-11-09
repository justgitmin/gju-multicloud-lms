import {completion} from './assessment.mjs';
import {quizProgress} from './quiz-progress.mjs';
export function learningJourney(course,enrollment){
 const done=l=>enrollment.progress.some(p=>p.lessonId===l.id&&p.version===l.version&&p.completedAt);
 const nextIndex=course.lessons.findIndex(l=>!done(l));
 const lessons=course.lessons.map((l,i)=>({...l,state:done(l)?'complete':i===nextIndex?'current':'locked'}));
 const counts={approved:enrollment.status==='APPROVED',lessons:lessons.length,completedLessons:lessons.filter(l=>l.state==='complete').length,labs:course.labs.length,approvedLabs:course.labs.filter(l=>enrollment.submissions.some(s=>s.labId===l.id&&s.status==='APPROVED')).length,quizzes:course.quizzes.length,passedQuizzes:course.quizzes.filter(q=>enrollment.attempts.some(a=>a.quizId===q.id&&a.version===q.version&&a.score>=70)).length};
 const total=counts.lessons+counts.labs+counts.quizzes;
 const achieved=counts.completedLessons+counts.approvedLabs+counts.passedQuizzes;
 const complete=completion(counts);
 return {lessons,counts,complete,percent:total?Math.min(complete?100:99,Math.floor(achieved/total*100)):0,next:lessons[nextIndex]??null,quizUnlocked:course.quizzes.some(q=>quizProgress(q.id,course.lessons,enrollment.progress).unlocked),pendingLabs:course.labs.filter(l=>enrollment.submissions.some(s=>s.labId===l.id&&s.status==='PENDING')).length};
}

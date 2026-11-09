export function quizProgress(quizId,lessons,progress){
 const prefix=quizId==='aws-quiz'?'aws-':quizId==='nhn-quiz'?'nhn-':null;
 const required=prefix?lessons.filter(l=>l.id.startsWith(prefix)):lessons;
 const completed=required.filter(l=>progress.some(p=>p.lessonId===l.id&&p.version===l.version&&p.completedAt)).length;
 return {total:required.length,completed,unlocked:required.length>0&&completed===required.length,label:prefix==='aws-'?'AWS':prefix==='nhn-'?'NHN Cloud':'전체'};
}

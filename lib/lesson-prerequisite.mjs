export function canOpenLesson(lesson,previous,progress){
 const done=l=>progress.some(p=>p.lessonId===l.id&&p.version===l.version&&p.completedAt);
 return done(lesson)||previous.every(done);
}

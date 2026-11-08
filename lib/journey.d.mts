type Lesson={id:string,title:string,version:number};
type Counts={approved:boolean,lessons:number,completedLessons:number,labs:number,approvedLabs:number,quizzes:number,passedQuizzes:number};
type JourneyLesson=Lesson&{state:'complete'|'current'|'locked'};
export function learningJourney(course:{lessons:Lesson[],labs:{id:string}[],quizzes:{id:string,version:number}[]},enrollment:{status:string,progress:{lessonId:string,version:number,completedAt:Date|null}[],submissions:{labId:string,status:string}[],attempts:{quizId:string,version:number,score:number}[]}):{lessons:JourneyLesson[],counts:Counts,complete:boolean,percent:number,next:JourneyLesson|null,quizUnlocked:boolean,pendingLabs:number};

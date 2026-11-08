export function grade(answers:unknown,key:unknown):number;
export function completion(input:{approved:boolean,lessons:number,completedLessons:number,labs:number,approvedLabs:number,quizzes:number,passedQuizzes:number}):boolean;
export function safeUrl(value:string):string|null;
export function csvCell(value:unknown):string;
export function canTakeQuiz(input:{lessons:number,completedLessons:number}):boolean;

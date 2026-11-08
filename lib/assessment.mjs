export function grade(answers,key){
 if(!Array.isArray(key)||key.length===0||!Array.isArray(answers)||answers.length!==key.length||answers.some(a=>!Number.isInteger(a)||a<0||a>3))throw new Error('INVALID_ANSWERS');
 return Math.round(answers.filter((a,i)=>a===key[i]).length/key.length*100);
}
export function completion({approved,lessons,completedLessons,labs,approvedLabs,quizzes,passedQuizzes}){
 return approved&&lessons>0&&labs>0&&quizzes>0&&completedLessons===lessons&&approvedLabs===labs&&passedQuizzes===quizzes;
}
export function safeUrl(value){if(!value)return null;try{const u=new URL(value);if(!['https:','http:'].includes(u.protocol)||u.username||u.password||value.length>2000)throw 0;return u.href;}catch{throw new Error('INVALID_URL');}}
export function csvCell(value){let text=String(value??'');if(/^[\s]*[=+@-]/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"';}

export function canTakeQuiz({lessons,completedLessons}){
 return lessons>0&&completedLessons===lessons;
}

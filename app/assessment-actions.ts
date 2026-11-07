'use server';
import {redirect} from 'next/navigation';
import {revalidatePath} from 'next/cache';
import {db} from '../lib/db';
import {requireAdmin,requireUser,allowAttempt} from '../lib/auth';
import {grade,safeUrl} from '../lib/assessment.mjs';
const text=(form:FormData,key:string)=>typeof form.get(key)==='string'?String(form.get(key)):'';
function fail(courseId:string,message:string):never{redirect(`/course/${encodeURIComponent(courseId)}?error=${encodeURIComponent(message)}`);}
async function approvedEnrollment(courseId:string){const user=await requireUser();const enrollment=await db.enrollment.findUnique({where:{userId_courseId:{userId:user.id,courseId}},include:{course:{select:{published:true}}}});if(!enrollment||enrollment.status!=='APPROVED'||!enrollment.course.published)redirect('/classroom');return enrollment;}
export async function submitLab(form:FormData){
 const lab=await db.lab.findUnique({where:{id:text(form,'labId')}});if(!lab)redirect('/classroom');const enrollment=await approvedEnrollment(lab.courseId);
 const content=text(form,'content').trim();if(content.length<30||content.length>15000)fail(lab.courseId,'실습 설명은 30~15,000자로 작성하세요.');
 let url;try{url=safeUrl(text(form,'url').trim());}catch{fail(lab.courseId,'결과물 주소는 http 또는 https 주소를 입력하세요.');}
 if(!await allowAttempt('lab-submit',enrollment.id,30))fail(lab.courseId,'제출 요청이 많습니다. 잠시 후 다시 시도하세요.');
 await db.submission.upsert({where:{enrollmentId_labId:{enrollmentId:enrollment.id,labId:lab.id}},create:{enrollmentId:enrollment.id,labId:lab.id,content,url},update:{content,url,status:'PENDING',feedback:'',reviewedBy:null,reviewedAt:null}});
 revalidatePath(`/course/${lab.courseId}`);revalidatePath('/admin/learning');redirect(`/course/${lab.courseId}?saved=lab`);
}
export async function submitQuiz(form:FormData){
 const quiz=await db.quiz.findUnique({where:{id:text(form,'quizId')}});if(!quiz)redirect('/classroom');const enrollment=await approvedEnrollment(quiz.courseId);
 if(!await allowAttempt('quiz',`${enrollment.id}:${quiz.id}`,5))fail(quiz.courseId,'15분 동안 5회까지 응시할 수 있습니다. 잠시 후 다시 시도하세요.');
 const questions=quiz.questions as {prompt:string,options:string[]}[];
 const values=questions.map((_,i)=>text(form,`answer-${i}`));
 if(values.some(v=>!/^[0-3]$/.test(v)))fail(quiz.courseId,'모든 문항에 답해주세요.');
 const answers=values.map(Number);let score;try{score=grade(answers,quiz.answerKey);}catch{fail(quiz.courseId,'답안을 처리할 수 없습니다. 운영자에게 문의하세요.');}
 await db.quizAttempt.create({data:{enrollmentId:enrollment.id,quizId:quiz.id,version:quiz.version,answers,score}});
 revalidatePath(`/course/${quiz.courseId}`);redirect(`/course/${quiz.courseId}?score=${score}`);
}
export async function reviewLab(form:FormData){
 const admin=await requireAdmin();const id=text(form,'submissionId');const status=text(form,'status');const feedback=text(form,'feedback').trim();
 if((status!=='APPROVED'&&status!=='REVISION')||feedback.length>3000||(status==='REVISION'&&!feedback))redirect('/admin/learning?error=feedback');
 const updatedAt=new Date(text(form,'updatedAt'));if(!Number.isFinite(updatedAt.getTime()))redirect('/admin/learning?error=stale');
 const submission=await db.submission.findUniqueOrThrow({where:{id},include:{lab:true}});
 const changed=await db.submission.updateMany({where:{id,updatedAt},data:{status,feedback,reviewedBy:admin.id,reviewedAt:new Date()}});
 if(changed.count!==1)redirect('/admin/learning?error=stale');
 revalidatePath('/admin/learning');revalidatePath(`/course/${submission.lab.courseId}`);
}

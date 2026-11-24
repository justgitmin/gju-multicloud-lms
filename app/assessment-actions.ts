'use server';
import {redirect} from 'next/navigation';
import {revalidatePath} from 'next/cache';
import {db} from '../lib/db';
import {requireAdmin,requireUser,allowAttempt} from '../lib/auth';
import {quizProgress} from '../lib/quiz-progress.mjs';
import {grade,safeUrl} from '../lib/assessment.mjs';
import {fileExtensions,maxSubmissionBytes,submissionCourses} from '../lib/submission-courses';
const text=(form:FormData,key:string)=>typeof form.get(key)==='string'?String(form.get(key)):'';
function fail(courseId:string,message:string):never{redirect(`/course/${encodeURIComponent(courseId)}?error=${encodeURIComponent(message)}`);}
async function approvedEnrollment(courseId:string){const user=await requireUser();const enrollment=await db.enrollment.findUnique({where:{userId_courseId:{userId:user.id,courseId}},include:{course:{select:{published:true}}}});if(!enrollment||enrollment.status!=='APPROVED'||!enrollment.course.published)redirect('/classroom');return enrollment;}
export async function submitLab(form:FormData){
 const lab=await db.lab.findUnique({where:{id:text(form,'labId')}});if(!lab)redirect('/classroom');const enrollment=await approvedEnrollment(lab.courseId);
 const content=text(form,'content').trim();if(content.length<30||content.length>15000)fail(lab.courseId,'실습 설명은 30~15,000자로 작성하세요.');
 let url;try{url=safeUrl(text(form,'url').trim());}catch{fail(lab.courseId,'결과물 주소는 http 또는 https 주소를 입력하세요.');}
 if(!await allowAttempt('lab-submit',enrollment.id,30))fail(lab.courseId,'제출 요청이 많습니다. 잠시 후 다시 시도하세요.');
 const upload=form.get('attachment');
 let file: {name:string;data:Uint8Array<ArrayBuffer>}|undefined;
 if(upload instanceof File&&upload.size>0){
  const name=upload.name.replace(/[\x00-\x1f\x7f/\\]/g,'_').slice(-180);
  const extension=name.split('.').pop()?.toLowerCase();
  if(upload.size>maxSubmissionBytes||!extension||!fileExtensions.includes(extension))fail(lab.courseId,'허용된 형식의 10MB 이하 파일을 첨부하세요.');
  file={name,data:new Uint8Array(await upload.arrayBuffer())};
 }
 if(!file&&submissionCourses.has(lab.courseId)){
  const existing=await db.submission.findUnique({
   where:{enrollmentId_labId:{enrollmentId:enrollment.id,labId:lab.id}},
   select:{file:{select:{submissionId:true}}}
  });
  if(!existing?.file)fail(lab.courseId,'산출물 파일을 첨부하세요.');
 }
 await db.submission.upsert({where:{enrollmentId_labId:{enrollmentId:enrollment.id,labId:lab.id}},create:{enrollmentId:enrollment.id,labId:lab.id,content,url,file:file?{create:file}:undefined},update:{content,url,file:file?{upsert:{create:file,update:file}}:undefined,status:'PENDING',feedback:'',reviewedBy:null,reviewedAt:null}});
 revalidatePath(`/course/${lab.courseId}`);revalidatePath('/admin/learning');redirect(`/course/${lab.courseId}?saved=lab`);
}
export async function submitQuiz(form:FormData){
 const quiz=await db.quiz.findUnique({where:{id:text(form,'quizId')}});if(!quiz)redirect('/classroom');const enrollment=await approvedEnrollment(quiz.courseId);
 const [lessons,progress]=await Promise.all([db.lesson.findMany({where:{courseId:quiz.courseId},select:{id:true,version:true}}),db.progress.findMany({where:{enrollmentId:enrollment.id},select:{lessonId:true,version:true,completedAt:true}})]);
 const gate=quizProgress(quiz.id,lessons,progress);
 if(!gate.unlocked)fail(quiz.courseId,gate.label+' 영상을 각각 95% 이상 시청한 후 평가에 응시할 수 있습니다.');
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
 if((status!=='APPROVED'&&status!=='REVISION')||feedback.length>3000||(status==='REVISION'&&!feedback))return {error:'보완 요청에는 피드백을 입력하세요. 피드백은 3,000자 이내입니다.'};
 const updatedAt=new Date(text(form,'updatedAt'));if(!Number.isFinite(updatedAt.getTime()))return {error:'제출물이 변경되었습니다. 새로고침 후 다시 검토하세요.'};
 const submission=await db.submission.findUnique({where:{id},include:{lab:true}});
 if(!submission)return {error:'제출물을 찾을 수 없습니다. 새로고침 후 확인하세요.'};
 const reviewedAt=new Date();
 const changed=await db.submission.updateMany({where:{id,updatedAt},data:{status,feedback,reviewedBy:admin.id,reviewedAt,updatedAt:reviewedAt}});
 if(changed.count!==1)return {error:'제출물이 변경되었습니다. 새로고침 후 다시 검토하세요.'};
 revalidatePath('/admin/learning');revalidatePath(`/course/${submission.lab.courseId}`);revalidatePath('/classroom');
 return {status,updatedAt:reviewedAt.toISOString()};
}

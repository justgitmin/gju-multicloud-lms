import {sameOrigin} from '../../../../../lib/origin.mjs';
import {randomBytes} from 'node:crypto';
import {db} from '../../../../../lib/db';
import {lessonAccess} from '../../../../../lib/learning';
import {advance,frontierOf} from '../../../../../lib/progress.mjs';
export const runtime='nodejs';
export async function POST(request:Request,{params}:{params:Promise<{id:string}>}){
 // Mutations require browser same-origin requests, in addition to the authenticated cookie.
 if(request.headers.get('sec-fetch-site')==='cross-site'||!sameOrigin(request.headers.get('origin'),request.headers.get('host'),process.env.APP_ORIGIN))return Response.json({error:'ORIGIN_DENIED'},{status:403});
 const {id}=await params;const access=await lessonAccess(id);
 if(!access)return Response.json({error:'수강 권한이나 이전 강의 이수 상태를 확인하세요.'},{status:403});
 if(!access.lesson.videoKey)return Response.json({error:'영상 준비 중입니다.'},{status:409});
 let body;try{body=await request.json();}catch{return Response.json({error:'INVALID_BODY'},{status:400});}
 const {enrollment,lesson}=access;
 const where={enrollmentId_lessonId_version:{enrollmentId:enrollment.id,lessonId:id,version:lesson.version}};
 if(body.action==='start'){
  const progress=await db.progress.upsert({where,create:{enrollmentId:enrollment.id,lessonId:id,version:lesson.version},update:{}});
  const frontier=frontierOf(progress.watchedRanges);const resume=progress.completedAt?progress.resumeSeconds:Math.min(progress.resumeSeconds,frontier);
  const playback=await db.playback.upsert({where:{enrollmentId_lessonId:{enrollmentId:enrollment.id,lessonId:id}},create:{id:randomBytes(24).toString('hex'),enrollmentId:enrollment.id,lessonId:id,version:lesson.version,lastPosition:resume},update:{id:randomBytes(24).toString('hex'),version:lesson.version,lastPosition:resume,lastAt:new Date(),revision:0}});
  return Response.json({sessionId:playback.id,resume,frontier,completed:!!progress.completedAt,duration:lesson.durationSeconds},{headers:{'Cache-Control':'no-store'}});
 }
 if(body.action!=='heartbeat'||typeof body.sessionId!=='string'||typeof body.position!=='number')return Response.json({error:'INVALID_BODY'},{status:400});
 try{
 const result=await db.$transaction(async tx=>{
  const playback=await tx.playback.findUnique({where:{id:body.sessionId}});
  if(!playback||playback.enrollmentId!==enrollment.id||playback.lessonId!==id||playback.version!==lesson.version)throw new Error('SESSION_REPLACED');
  const now=new Date();if(now.getTime()-playback.lastAt.getTime()>120000)throw new Error('SESSION_EXPIRED');
  const progress=await tx.progress.findUniqueOrThrow({where});
  const next=advance({position:body.position,lastPosition:playback.lastPosition,frontier:frontierOf(progress.watchedRanges),elapsed:(now.getTime()-playback.lastAt.getTime())/1000,duration:lesson.durationSeconds,completed:!!progress.completedAt});
  const claimed=await tx.playback.updateMany({where:{id:playback.id,revision:playback.revision},data:{lastAt:now,lastPosition:next.resume,revision:{increment:1}}});
  if(claimed.count!==1)throw new Error('RETRY');
  await tx.progress.update({where,data:{resumeSeconds:next.resume,watchedRanges:[[0,next.frontier]],completedAt:progress.completedAt??(next.completed?now:null)}});
  return next;
 });return Response.json(result,{headers:{'Cache-Control':'no-store'}});
 }catch(error){const message=error instanceof Error?error.message:'SAVE_FAILED';const known=['SEEK_BLOCKED','INVALID_POSITION','SESSION_REPLACED','SESSION_EXPIRED','RETRY'];return Response.json({error:known.includes(message)?message:'SAVE_FAILED'},{status:409});}
}

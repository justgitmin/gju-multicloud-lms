import {Prisma} from '@prisma/client';
import {db} from './db';
import {validateLabBatch,encryptLab,labAad,labKey} from './lab-secrets.mjs';
export async function importLabBatch(raw:unknown,actorId:string,tokenId?:string){
 const batch=validateLabBatch(raw);labKey();
 return db.$transaction(async tx=>{
  if(tokenId){const consumed=await tx.labTransferToken.updateMany({where:{id:tokenId,adminId:actorId,consumedAt:null,expiresAt:{gt:new Date()}},data:{consumedAt:new Date()}});if(consumed.count!==1)throw new Error('전송 토큰이 만료되었거나 이미 사용되었습니다.');}
  const summary=[];
  for(const entry of batch.entries){
   const enrollment=await tx.enrollment.findFirst({where:{courseId:batch.courseId,status:'APPROVED',course:{published:true},user:{email:entry.email,role:'STUDENT'}},include:{user:{select:{name:true,email:true,studentNumber:true}}}});
   if(!enrollment)throw new Error(`${entry.email}: 해당 과정의 승인된 학생 계정을 먼저 준비하세요.`);
   const existing=await tx.labAccess.findUnique({where:{accountId_labId_studentCode:{accountId:entry.accountId,labId:entry.labId,studentCode:entry.studentCode}}});
   if(existing&&existing.enrollmentId!==enrollment.id)throw new Error('이미 다른 학생에게 연결된 AWS 계정입니다. 먼저 기존 배정을 확인하세요.');
   const current=await tx.labAccess.findUnique({where:{enrollmentId:enrollment.id}});
   if(current&&(current.accountId!==entry.accountId||current.labId!==entry.labId||current.studentCode!==entry.studentCode))throw new Error(`${entry.email}: 기존 배정과 다릅니다. 자동 교체하지 않습니다.`);
   const assignment=await tx.labAccess.upsert({where:{enrollmentId:enrollment.id},create:{enrollmentId:enrollment.id,labId:entry.labId,studentCode:entry.studentCode,accountId:entry.accountId,publicData:entry.publicData,secretData:encryptLab(entry.secrets,labAad(enrollment.id,entry)),active:true},update:{publicData:entry.publicData,secretData:encryptLab(entry.secrets,labAad(enrollment.id,entry)),active:true}});
   await tx.labAccessAudit.create({data:{actorId,event:'IMPORT',assignmentId:assignment.id}});
   summary.push({name:enrollment.user.name,email:enrollment.user.email,studentCode:entry.studentCode,labId:entry.labId});
  }return summary;
 },{isolationLevel:Prisma.TransactionIsolationLevel.Serializable,timeout:15000});
}

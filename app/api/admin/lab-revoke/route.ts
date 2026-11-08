import {NextResponse} from 'next/server';
import {currentUser} from '../../../../lib/auth';
import {db} from '../../../../lib/db';
import {labRequestAllowed,limitedJson,privateHeaders} from '../../../../lib/lab-http';
export async function POST(request:Request){
 if(!labRequestAllowed(request))return NextResponse.json({error:'HTTPS 설정이 필요합니다.'},{status:403,headers:privateHeaders});
 const user=await currentUser();if(user?.role!=='ADMIN')return NextResponse.json({error:'관리자 로그인이 필요합니다.'},{status:403,headers:privateHeaders});
 try{const {id,action}=await limitedJson(request,1000);if(typeof id!=='string'||id.length>100||!['revoke','release'].includes(action))throw new Error();
 await db.$transaction(async tx=>{
  if(action==='release'){const row=await tx.labAccess.findUniqueOrThrow({where:{id}});if(row.active)throw new Error();await tx.labAccess.delete({where:{id}});}
  else await tx.labAccess.update({where:{id},data:{active:false}});
  await tx.labAccessAudit.create({data:{actorId:user.id,event:action==='release'?'RELEASE':'REVOKE',assignmentId:id}});
 });return NextResponse.json({ok:true},{headers:privateHeaders});
 }catch{return NextResponse.json({error:'배정 상태를 새로고침해서 확인하세요. 배정 삭제 전 열람 중지가 필요합니다.'},{status:400,headers:privateHeaders});}
}

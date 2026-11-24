import {currentUser} from '../../../../lib/auth';
import {db} from '../../../../lib/db';

export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}){
 const user=await currentUser();
 if(!user)return new Response(null,{status:401});
 const {id}=await params;
 const file=await db.submissionFile.findFirst({
  where:{submissionId:id,...(user.role==='ADMIN'?{}:{submission:{enrollment:{userId:user.id,status:'APPROVED',course:{published:true}}}})},
  select:{name:true,data:true}
 });
 if(!file)return new Response(null,{status:404});
 const filename=encodeURIComponent(file.name.toWellFormed()).replace(/['()*]/g,c=>'%'+c.charCodeAt(0).toString(16));
 return new Response(new Uint8Array(file.data),{headers:{
  'Content-Type':'application/octet-stream',
  'Content-Disposition':`attachment; filename="submission"; filename*=UTF-8''${filename}`,
  'Cache-Control':'private, no-store',
  'X-Content-Type-Options':'nosniff'
 }});
}

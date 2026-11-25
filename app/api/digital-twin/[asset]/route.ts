import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import {join} from 'node:path';
import {Readable} from 'node:stream';
import {currentUser} from '../../../../lib/auth';
import {db} from '../../../../lib/db';

const assets: Record<string,string> = {
 '01.mp4':'GJU_DigitalTwin_Lesson_01.mp4',
 '02.mp4':'GJU_DigitalTwin_Lesson_02.mp4',
 '03.mp4':'GJU_DigitalTwin_Lesson_03.mp4',
 'guide.html':'GJU_DigitalTwin_Lecture_Companion.html'
};
export async function GET(request:Request,{params}:{params:Promise<{asset:string}>}){
 const user=await currentUser();
 if(!user)return new Response(null,{status:401});
 const enrollment=await db.enrollment.findFirst({
  where:{userId:user.id,courseId:'gju-digital-twin-2026',status:'APPROVED',course:{published:true}},
  select:{id:true}
 });
 if(!enrollment&&user.role!=='ADMIN')return new Response(null,{status:403});
 const {asset}=await params;
 if(!Object.hasOwn(assets,asset))return new Response(null,{status:404});
 const path=join(process.env.MEDIA_ROOT??'/app/media','digital-twin',assets[asset]);
 const info=await stat(path).catch(()=>null);
 if(!info?.isFile()||!info.size)return new Response(null,{status:404});
 const headers=new Headers({'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'});
 if(asset==='guide.html'){
  headers.set('Content-Type','text/html; charset=utf-8');
  headers.set('Content-Security-Policy',"sandbox; default-src 'none'; style-src 'unsafe-inline'");
  headers.set('Content-Length',String(info.size));
  return new Response(Readable.toWeb(createReadStream(path)) as ReadableStream,{headers});
 }
 headers.set('Content-Type','video/mp4');
 headers.set('Accept-Ranges','bytes');
 const range=request.headers.get('range');
 let start=0,end=info.size-1;
 if(range){
  const match=/^bytes=(\d*)-(\d*)$/.exec(range);
  if(match&&(match[1]||match[2])){
   if(match[1]){
    start=Number(match[1]);
    if(match[2])end=Math.min(end,Number(match[2]));
   }else start=Math.max(0,info.size-Number(match[2]));
  }else start=info.size;
  if(!Number.isSafeInteger(start)||start>=info.size||start>end){
   headers.set('Content-Range',`bytes */${info.size}`);
   return new Response(null,{status:416,headers});
  }
  headers.set('Content-Range',`bytes ${start}-${end}/${info.size}`);
 }
 headers.set('Content-Length',String(end-start+1));
 return new Response(Readable.toWeb(createReadStream(path,{start,end})) as ReadableStream,{headers,status:range?206:200});
}

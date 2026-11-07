import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import path from 'node:path';
import {Readable} from 'node:stream';
import {lessonAccess} from '../../../../../lib/learning';
import {S3Client,GetObjectCommand} from '@aws-sdk/client-s3';
import {validMediaKey,captionKey} from '../../../../../lib/media-config.mjs';
import {parseRange} from '../../../../../lib/progress.mjs';
export const runtime='nodejs';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const access=await lessonAccess((await params).id);
 if(!access)return new Response('Forbidden',{status:403});
 const key=access.lesson.videoKey;
 // Only flat, explicitly registered MP4 filenames may be read. Media never lives in public/.
 const backend=process.env.MEDIA_BACKEND??'local';
 if(!key||!validMediaKey(key,backend))return new Response('Video unavailable',{status:404});
 const captions=new URL(request.url).searchParams.get('captions')==='1';
 if(backend==='s3'){
  if(!process.env.MEDIA_S3_BUCKET)return new Response('Media configuration unavailable',{status:503});
  const range=request.headers.get('range');
  if(range&&!/^bytes=(\d*)-(\d*)$/.test(range))return new Response(null,{status:416});
  try{
   const client=new S3Client({region:process.env.AWS_REGION??'ap-northeast-2'});
   const object=await client.send(new GetObjectCommand({Bucket:process.env.MEDIA_S3_BUCKET,Key:captions?captionKey(key,backend):key,...(range?{Range:range}:{})}));
   if(!object.Body)return new Response('Video unavailable',{status:404});
   const headers:Record<string,string>={'Content-Type':captions?'text/vtt; charset=utf-8':'video/mp4','Cache-Control':'private, no-store','Accept-Ranges':'bytes','X-Content-Type-Options':'nosniff'};
   if(object.ContentLength!==undefined)headers['Content-Length']=String(object.ContentLength);
   if(object.ContentRange)headers['Content-Range']=object.ContentRange;
   return new Response(object.Body.transformToWebStream() as ReadableStream<Uint8Array>,{status:object.ContentRange?206:200,headers});
  }catch(error){const status=(error as {$metadata?:{httpStatusCode?:number}}).$metadata?.httpStatusCode;return new Response('Media unavailable',{status:status===416?416:status===404?404:503});}
 }
 const filename=path.join(/* turbopackIgnore: true */ process.env.MEDIA_ROOT??path.join(process.cwd(),'media'),captions?captionKey(key,backend):key);
 let size;try{size=(await stat(/* turbopackIgnore: true */ filename)).size;}catch{return new Response('Video unavailable',{status:404});}
 let range;try{range=parseRange(request.headers.get('range'),size);}catch{return new Response(null,{status:416,headers:{'Content-Range':`bytes */${size}`}});}
 const headers:Record<string,string>={'Content-Type':captions?'text/vtt; charset=utf-8':'video/mp4','Accept-Ranges':'bytes','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Length':String(range?range.end-range.start+1:size)};
 if(range)headers['Content-Range']=`bytes ${range.start}-${range.end}/${size}`;
 const stream=Readable.toWeb(createReadStream(/* turbopackIgnore: true */ filename,range??undefined)) as ReadableStream<Uint8Array>;
 return new Response(stream,{status:range?206:200,headers});
}

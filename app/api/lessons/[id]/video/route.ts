import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import path from 'node:path';
import {Readable} from 'node:stream';
import {lessonAccess} from '../../../../../lib/learning';
import {parseRange} from '../../../../../lib/progress.mjs';
export const runtime='nodejs';
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 const access=await lessonAccess((await params).id);
 if(!access)return new Response('Forbidden',{status:403});
 const key=access.lesson.videoKey;
 // Only flat, explicitly registered MP4 filenames may be read. Media never lives in public/.
 if(!key||!/^[a-zA-Z0-9_-]+\.mp4$/.test(key))return new Response('Video unavailable',{status:404});
 const filename=path.join(/* turbopackIgnore: true */ process.env.MEDIA_ROOT??path.join(process.cwd(),'media'),key);
 let size;try{size=(await stat(/* turbopackIgnore: true */ filename)).size;}catch{return new Response('Video unavailable',{status:404});}
 let range;try{range=parseRange(request.headers.get('range'),size);}catch{return new Response(null,{status:416,headers:{'Content-Range':`bytes */${size}`}});}
 const headers:Record<string,string>={'Content-Type':'video/mp4','Accept-Ranges':'bytes','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Length':String(range?range.end-range.start+1:size)};
 if(range)headers['Content-Range']=`bytes ${range.start}-${range.end}/${size}`;
 const stream=Readable.toWeb(createReadStream(/* turbopackIgnore: true */ filename,range??undefined)) as ReadableStream<Uint8Array>;
 return new Response(stream,{status:range?206:200,headers});
}

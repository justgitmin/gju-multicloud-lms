import {labKey} from './lab-secrets.mjs';
import {sameOrigin} from './origin.mjs';
export const privateHeaders={'Cache-Control':'private, no-store, max-age=0','Pragma':'no-cache','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY'};
export function httpsLabReady(){try{const u=new URL(process.env.APP_ORIGIN??'');labKey();return u.protocol==='https:';}catch{return false;}}
export function labRequestAllowed(request:Request,{bearer=false}={}){
 if(!httpsLabReady()||request.headers.get('x-forwarded-proto')!=='https')return false;
 // Bearer requests are made by the operator GUI; it enforces TLS/certificate validation itself.
 if(bearer)return true;
 return sameOrigin(request.headers.get('origin'),request.headers.get('host'),process.env.APP_ORIGIN);
}
export async function limitedJson(request:Request,limit=100000){
 if(!request.headers.get('content-type')?.toLowerCase().startsWith('application/json'))throw new Error('JSON 요청이 필요합니다.');
 const reader=request.body?.getReader();if(!reader)throw new Error('빈 요청입니다.');let size=0;const parts:Uint8Array[]=[];
 try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>limit){await reader.cancel();throw new Error('전송 용량을 초과했습니다.');}parts.push(value);}}finally{reader.releaseLock();}
 return JSON.parse(Buffer.concat(parts).toString('utf8'));
}

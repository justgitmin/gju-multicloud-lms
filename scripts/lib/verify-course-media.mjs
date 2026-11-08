import {createHash} from 'node:crypto';

export async function verifyObject(getObject,bucket,key,{bytes,sha256,contentType}) {
 const response=await getObject({Bucket:bucket,Key:key});
 const body=response.Body;
 if(!body || !body[Symbol.asyncIterator])throw new Error(`Missing object body: ${key}`);
 try {
  const type=response.ContentType?.split(';')[0].trim().toLowerCase();
  if(type!==contentType)throw new Error(`Content-Type mismatch: ${key}; expected ${contentType}`);
  if(response.ContentLength!==bytes)throw new Error(`Object size mismatch: ${key}`);
  const hash=createHash('sha256');let received=0;
  for await(const chunk of body){received+=chunk.length;if(received>bytes)throw new Error(`Object exceeds expected size: ${key}`);hash.update(chunk);}
  if(received!==bytes || hash.digest('hex')!==sha256)throw new Error(`Object content mismatch: ${key}; upload the latest MP4 and VTT together`);
 } finally {body.destroy?.();}
}

export async function verifyCourseMedia({getObject,bucket,entries,readCaption,onVerified=()=>{}}){
 if(!bucket)throw new Error('Set MEDIA_S3_BUCKET');
 if(entries.length!==16 || new Set(entries.map(e=>e.id)).size!==16)throw new Error('Expected 16 unique media records');
 for(const item of entries){
  await verifyObject(getObject,bucket,item.s3Key,{bytes:item.bytes,sha256:item.sha256,contentType:'video/mp4'});
  const caption=await readCaption(item.id);
  await verifyObject(getObject,bucket,item.captionKey,{bytes:caption.length,sha256:createHash('sha256').update(caption).digest('hex'),contentType:'text/vtt'});
  onVerified(item.id);
 }
}

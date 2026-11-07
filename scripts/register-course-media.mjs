import fs from 'node:fs/promises';
import {PrismaClient} from '@prisma/client';
import {S3Client,HeadObjectCommand} from '@aws-sdk/client-s3';
const db=new PrismaClient();
try{
 const entries=JSON.parse(await fs.readFile(new URL('../content/media-manifest.json',import.meta.url),'utf8'));
 if(entries.length!==16)throw new Error('Expected 16 media records');
 const bucket=process.env.MEDIA_S3_BUCKET;if(!bucket)throw new Error('Set MEDIA_S3_BUCKET');
 const client=new S3Client({region:process.env.AWS_REGION??'ap-northeast-2'});
 for(const item of entries){
  const head=await client.send(new HeadObjectCommand({Bucket:bucket,Key:item.s3Key}));
  if(head.ContentLength!==item.bytes)throw new Error(`Object size mismatch: ${item.id}`);
  await client.send(new HeadObjectCommand({Bucket:bucket,Key:item.captionKey}));
 }
 await db.$transaction(async tx=>{
  for(const item of entries){const lesson=await tx.lesson.findUniqueOrThrow({where:{id:item.id}});
   if(lesson.videoKey===item.s3Key&&lesson.mediaSha256===item.sha256)continue;
   await tx.lesson.update({where:{id:item.id},data:{videoKey:item.s3Key,mediaSha256:item.sha256,durationSeconds:Math.ceil(item.durationSeconds),version:lesson.videoKey?{increment:1}:lesson.version}});
  }
 });
 console.log('16 videos and captions verified by object existence/size and registered. Full remote file hashes were not downloaded.');
}finally{await db.$disconnect();}

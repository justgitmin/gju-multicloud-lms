import fs from 'node:fs/promises';
import {PrismaClient} from '@prisma/client';
import {S3Client,GetObjectCommand} from '@aws-sdk/client-s3';
import {verifyCourseMedia} from './lib/verify-course-media.mjs';
const db=new PrismaClient();
try{
 const entries=JSON.parse(await fs.readFile(new URL('../content/media-manifest.json',import.meta.url),'utf8'));
 if(entries.length!==16)throw new Error('Expected 16 media records');
 const bucket=process.env.MEDIA_S3_BUCKET;if(!bucket)throw new Error('Set MEDIA_S3_BUCKET');
 const client=new S3Client({region:process.env.AWS_REGION??'ap-northeast-2'});
 await verifyCourseMedia({getObject:params=>client.send(new GetObjectCommand(params)),bucket,entries,
  readCaption:id=>fs.readFile(new URL(`../content/${id}/${id}.vtt`,import.meta.url)),onVerified:id=>console.log(`VERIFIED ${id} MP4 + VTT`)});
 await db.$transaction(async tx=>{
  for(const item of entries){const lesson=await tx.lesson.findUniqueOrThrow({where:{id:item.id}});
   if(lesson.videoKey===item.s3Key&&lesson.mediaSha256===item.sha256)continue;
   await tx.lesson.update({where:{id:item.id},data:{videoKey:item.s3Key,mediaSha256:item.sha256,durationSeconds:Math.ceil(item.durationSeconds),version:lesson.videoKey?{increment:1}:lesson.version}});
  }
 });
 console.log('16 videos and captions verified by full SHA-256, size and Content-Type; registered.');
}finally{await db.$disconnect();}

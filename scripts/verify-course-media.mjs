import fs from 'node:fs/promises';
import {S3Client,GetObjectCommand} from '@aws-sdk/client-s3';
import {verifyCourseMedia} from './lib/verify-course-media.mjs';
const entries=JSON.parse(await fs.readFile(new URL('../content/media-manifest.json',import.meta.url),'utf8'));
try {
 const client=new S3Client({region:process.env.AWS_REGION??'ap-northeast-2'});
 await verifyCourseMedia({getObject:params=>client.send(new GetObjectCommand(params)),bucket:process.env.MEDIA_S3_BUCKET,entries,
  readCaption:id=>fs.readFile(new URL(`../content/${id}/${id}.vtt`,import.meta.url)),onVerified:id=>console.log(`VERIFIED ${id} MP4 + VTT`)});
 console.log('MEDIA_VERIFICATION_OK 16 videos + 16 captions; database unchanged.');
} catch(error){console.error(error.message);process.exitCode=1;}

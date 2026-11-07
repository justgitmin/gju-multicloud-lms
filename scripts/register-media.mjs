import {PrismaClient} from '@prisma/client';
import {execFileSync} from 'node:child_process';
import {mkdir,copyFile,readFile} from 'node:fs/promises';
import {createHash,randomBytes} from 'node:crypto';
import path from 'node:path';
const [lessonId,source,captions]=process.argv.slice(2);const db=new PrismaClient();
try{
 if(!lessonId||!source)throw new Error('Usage: node scripts/register-media.mjs LESSON_ID /absolute/path/video.mp4');
 const lesson=await db.lesson.findUniqueOrThrow({where:{id:lessonId}});
 const probe=JSON.parse(execFileSync('ffprobe',['-v','error','-show_format','-show_streams','-of','json',path.resolve(source)],{encoding:'utf8'}));
 const duration=Number(probe.format.duration);
 if(!Number.isFinite(duration)||duration<=0||!probe.streams.some(s=>s.codec_type==='video')||!path.resolve(source).endsWith('.mp4'))throw new Error('Valid MP4 with a video stream is required.');
 const root=process.env.MEDIA_ROOT??path.join(process.cwd(),'media');await mkdir(root,{recursive:true});
 const key=`${randomBytes(16).toString('hex')}.mp4`;await copyFile(path.resolve(source),path.join(root,key));
 if(captions){const {readFile}=await import('node:fs/promises');const content=await readFile(path.resolve(captions),'utf8');if(!content.startsWith('WEBVTT'))throw new Error('Captions must be WebVTT.');await copyFile(path.resolve(captions),path.join(root,key.replace(/\.mp4$/,'.vtt')));}
 await db.lesson.update({where:{id:lesson.id},data:{videoKey:key,durationSeconds:Math.ceil(duration),mediaSha256:createHash('sha256').update(await readFile(path.resolve(source))).digest('hex'),version:lesson.videoKey?{increment:1}:lesson.version}});
 console.log('Media registered. New video version requires fresh completion. Previous records retained.');
}finally{await db.$disconnect();}

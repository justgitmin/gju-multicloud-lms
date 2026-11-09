import fs from 'node:fs/promises';import {spawn} from 'node:child_process';import {createRequire} from 'node:module';import {randomBytes} from 'node:crypto';
const root=process.cwd();if(process.env.LMS_INTEGRATION_TEST!=='true'||!process.env.DATABASE_URL)throw new Error('Use only a dedicated empty test database with LMS_INTEGRATION_TEST=true');
const require=createRequire(root+'/package.json');const {PrismaClient}=require('@prisma/client');
const env={...process.env,DATABASE_URL:process.env.DATABASE_URL,ENABLE_REGISTRATION:'true',NEXT_TELEMETRY_DISABLED:'1'};
await fs.mkdir(root+'/test-results/media',{recursive:true});await fs.writeFile(root+'/test-results/media/transport-fixture.mp4',Buffer.alloc(1024,1));env.MEDIA_ROOT=root+'/test-results/media';env.MEDIA_BACKEND='local';
let app;const prisma=new PrismaClient({datasources:{db:{url:env.DATABASE_URL}}});
async function run(args,extra={}){return new Promise((resolve,reject)=>{const c=spawn(process.execPath,args,{cwd:root,env:{...env,...extra},stdio:['ignore','pipe','pipe']});let text='';c.stdout.on('data',d=>text+=d);c.stderr.on('data',d=>text+=d);c.on('exit',code=>code===0?resolve(text):reject(new Error(text.slice(-1500))));});}
const report=[];function check(condition,label){if(!condition)throw new Error(label);report.push(label);console.log('PASS '+label);}
try{
 check(await prisma.course.count()===0,'Dedicated test database is empty and reachable');
 await prisma.$disconnect();
 const adminPassword=randomBytes(18).toString('hex');const studentPassword=randomBytes(18).toString('hex');
 await run(['scripts/setup.mjs'],{ADMIN_EMAIL:'admin@example.invalid',ADMIN_PASSWORD:adminPassword});
 await run(['scripts/seed-assessments.mjs']);
 // Simulate existing production ordering; preserve registered media through reorder.
 const before=await prisma.lesson.findMany();
 for(const l of before)await prisma.lesson.update({where:{id:l.id},data:{position:l.position+100}});
 for(const l of before)await prisma.lesson.update({where:{id:l.id},data:{position:l.id.startsWith('aws-')?Number(l.id.slice(-2)):8+Number(l.id.slice(-2))}});
 await prisma.lesson.update({where:{id:'aws-01'},data:{videoKey:'preserved.mp4'}});
 await run(['scripts/order-course.mjs']);
 await run(['scripts/order-course.mjs']);
 const ordered=await prisma.lesson.findMany({orderBy:{position:'asc'}});
 check(ordered[0].id==='nhn-01'&&ordered[8].id==='aws-01','Existing course reordered NHN first and remains idempotent');
 check(ordered[8].videoKey==='preserved.mp4'&&ordered.every(l=>before.find(b=>b.id===l.id).version===l.version),'Media and lesson versions retained by reorder');

 app=spawn(process.execPath,['node_modules/next/dist/bin/next','start','-p','3300','-H','127.0.0.1'],{cwd:root,env,stdio:['ignore','ignore','pipe']});app.stderr.on('data',()=>{});
 const base='http://127.0.0.1:3300';let ready=false;
 for(let i=0;i<100;i++){try{if((await fetch(base+'/api/health')).ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,200));}check(ready,'HTTP app starts');
 async function action(path,values,cookie=''){const page=await fetch(base+path,{headers:cookie?{cookie}:{},redirect:'manual'});const html=await page.text();const forms=html.match(/<form[\s\S]*?<\/form>/g)??[];const selected=forms.find(f=>Object.keys(values).every(k=>f.includes('name="'+k+'"'))&&['courseId','enrollmentId','labId','quizId'].every(k=>!(k in values)||f.includes('value="'+values[k]+'"')));const match=(selected??'').match(/name="(\$ACTION_ID_[^"]+)"/);if(!match)throw new Error('Missing action '+path);const form=new FormData();form.set(match[1],'');for(const [k,v]of Object.entries(values))form.set(k,v);return fetch(base+path,{method:'POST',headers:{origin:base,...(cookie?{cookie}:{})},body:form,redirect:'manual'});}
 let response=await fetch(base+'/');let home=await response.text();check(home.includes('로그인 →')&&!home.includes('로그아웃'),'Guest home shows login');
 response=await fetch(base+'/classroom',{redirect:'manual'});check(response.status===307,'Anonymous classroom access redirects');
 response=await action('/register',{name:'테스트 학생',studentNumber:'TEST-001',email:'student@example.invalid',password:studentPassword,consent:'on'});const studentCookie=response.headers.get('set-cookie')?.split(';')[0];check(!!studentCookie&&response.status===303,'Registration creates authenticated session');
 response=await fetch(base+'/',{headers:{cookie:studentCookie}});home=await response.text();check(home.includes('로그아웃')&&home.includes('테스트 학생')&&!home.includes('로그인 →'),'Authenticated home shows name and logout');
 check(/private|no-store/.test(response.headers.get('cache-control')??''),'Personalized home is not publicly cached');
 response=await fetch(base+'/login',{headers:{cookie:studentCookie},redirect:'manual'});check(response.status===307&&response.headers.get('location')==='/classroom','Authenticated student skips login form');
 response=await fetch(base+'/');check(!(await response.text()).includes('테스트 학생'),'Guest home does not leak another user identity');
 response=await fetch(base+'/admin',{headers:{cookie:studentCookie},redirect:'manual'});check(response.status===307,'Student cannot access admin page');
 response=await action('/classroom',{courseId:'gju-multicloud-2026'},studentCookie);let application=await prisma.enrollment.findFirstOrThrow({where:{user:{email:'student@example.invalid'}}});check(application.status==='PENDING','Enrollment starts pending');
 response=await fetch(base+'/learn/nhn-01',{headers:{cookie:studentCookie},redirect:'manual'});check(response.status===307,'Pending student cannot access lesson');
 response=await action('/login',{email:'admin@example.invalid',password:adminPassword});const adminCookie=response.headers.get('set-cookie')?.split(';')[0];check(!!adminCookie,'Admin login succeeds');
 response=await fetch(base+'/login',{headers:{cookie:adminCookie},redirect:'manual'});check(response.status===307&&response.headers.get('location')==='/admin','Authenticated admin skips login form');
 response=await action('/admin',{enrollmentId:application.id,status:'APPROVED'},adminCookie);application=await prisma.enrollment.findUniqueOrThrow({where:{id:application.id}});check(application.status==='APPROVED','Admin approves enrollment');
 response=await fetch(base+'/course/gju-multicloud-2026',{headers:{cookie:studentCookie}});let html=await response.text();check(response.ok&&html.includes('실습 제출')&&html.includes('/guide/nhn'),'Approved student sees NHN guide, labs and quizzes');
 response=await fetch(base+'/guide/nhn',{headers:{cookie:studentCookie}});check(response.ok&&(await response.text()).includes('MobaXterm'),'NHN SSH guide renders');
 response=await fetch(base+'/guide/aws',{headers:{cookie:studentCookie}});check(response.ok&&(await response.text()).includes('Session Manager'),'AWS browser guide renders');
 await prisma.lesson.update({where:{id:'nhn-01'},data:{videoKey:'transport-fixture.mp4',durationSeconds:10}});
 response=await fetch(base+'/api/lessons/nhn-01/video');check(response.status===403,'Anonymous video access denied');
 response=await fetch(base+'/api/lessons/nhn-01/video',{headers:{cookie:studentCookie,range:'bytes=0-9'}});check(response.status===206&&(await response.arrayBuffer()).byteLength===10,'Approved video transport supports byte ranges');
 response=await fetch(base+'/api/lessons/nhn-02/video',{headers:{cookie:studentCookie}});check(response.status===403,'Later lesson remains locked');
 async function playback(payload){return fetch(base+'/api/lessons/nhn-01/playback',{method:'POST',headers:{cookie:studentCookie,origin:base,'Content-Type':'application/json'},body:JSON.stringify(payload)});}
 response=await playback({action:'start'});const first=await response.json();check(response.ok&&first.resume===0,'Playback session starts with server state');
 response=await playback({action:'heartbeat',sessionId:first.sessionId,position:9.5});check(response.status===409,'Unseen forward jump is rejected by server');
 await prisma.playback.update({where:{id:first.sessionId},data:{lastAt:new Date(Date.now()-5000)}});
 response=await playback({action:'heartbeat',sessionId:first.sessionId,position:5});let progress=await response.json();check(response.ok&&progress.frontier===5&&!progress.completed,'Real elapsed playback advances progress');
 response=await playback({action:'start'});const second=await response.json();check(second.resume===5,'New session resumes saved position');
 response=await playback({action:'heartbeat',sessionId:first.sessionId,position:5});check(response.status===409,'Replaced playback session cannot save');
 await prisma.playback.update({where:{id:second.sessionId},data:{lastAt:new Date(Date.now()-5000)}});
 response=await playback({action:'heartbeat',sessionId:second.sessionId,position:9.5});progress=await response.json();check(response.ok&&progress.completed,'95 percent validated watch completes video');
 response=await fetch(base+'/learn/nhn-02',{headers:{cookie:studentCookie},redirect:'manual'});check(response.status===200,'Completion unlocks next lesson page');

 response=await action('/course/gju-multicloud-2026',{labId:'nhn-lab',content:'네트워크와 웹 서비스, 데이터베이스 연결 및 정리 결과를 기록한 테스트 제출입니다.',url:'https://example.com/work'},studentCookie);check(await prisma.submission.count()===1,'Student lab submission saved');
 // NHN eligibility must not wait for AWS lessons.
 const allLessons=await prisma.lesson.findMany({where:{courseId:'gju-multicloud-2026'}});
 const approved=await prisma.enrollment.findFirstOrThrow({where:{user:{email:'student@example.invalid'},courseId:'gju-multicloud-2026'}});
 for(const lesson of allLessons.filter(l=>l.id.startsWith('nhn-')))await prisma.progress.upsert({where:{enrollmentId_lessonId_version:{enrollmentId:approved.id,lessonId:lesson.id,version:lesson.version}},create:{enrollmentId:approved.id,lessonId:lesson.id,version:lesson.version,completedAt:new Date()},update:{completedAt:new Date()}});
 response=await action('/course/gju-multicloud-2026',{quizId:'nhn-quiz','answer-0':'0','answer-1':'1','answer-2':'0','answer-3':'1','answer-4':'0'},studentCookie);const attempt=await prisma.quizAttempt.findFirst();check(attempt?.score===100,'NHN quiz graded before AWS lessons are complete');
 response=await fetch(base+'/course/gju-multicloud-2026',{headers:{cookie:studentCookie}});html=await response.text();check(!html.includes('name="quizId" value="aws-quiz"'),'AWS quiz remains locked');
 response=await fetch(base+'/api/admin/results',{headers:{cookie:studentCookie}});check(response.status===403,'Student cannot export report');
 response=await fetch(base+'/api/admin/results',{headers:{cookie:adminCookie}});check(response.ok&&(await response.text()).includes('테스트 학생'),'Admin CSV report contains enrollment');
 response=await fetch(base+'/api/lessons/nhn-01/playback',{method:'POST',headers:{cookie:studentCookie,origin:'https://other.invalid','Content-Type':'application/json'},body:JSON.stringify({action:'start'})});check(response.status===403,'Cross-origin playback mutation rejected');
 response=await action('/',{},studentCookie);check(response.status===303,'Home logout submits session action');
 response=await fetch(base+'/',{headers:{cookie:studentCookie}});home=await response.text();check(home.includes('로그인 →')&&!home.includes('로그아웃'),'Revoked session returns home to guest state');
 response=await fetch(base+'/classroom',{headers:{cookie:studentCookie},redirect:'manual'});check(response.status===307,'Logged-out session cannot reopen classroom');
 const outcome={engine:'PostgreSQL',checks:report};await fs.mkdir(root+'/test-results',{recursive:true});await fs.writeFile(root+'/test-results/integration.json',JSON.stringify(outcome,null,2));
 console.log('INTEGRATION_OK '+report.length);
}catch(error){console.error('INTEGRATION_FAILED',error.message);process.exitCode=1;}finally{app?.kill();await prisma.$disconnect();}

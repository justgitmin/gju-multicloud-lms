import fs from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {createHash,randomBytes} from 'node:crypto';
import {PrismaClient} from '@prisma/client';
import {hashPassword} from '../lib/password.mjs';
if(process.env.LMS_INTEGRATION_TEST!=='true'||!process.env.DATABASE_URL)throw new Error('Use an isolated test database with LMS_INTEGRATION_TEST=true');
const db=new PrismaClient();const suffix=randomBytes(5).toString('hex');const ids=[];let app,course;const report=[];
function check(condition,message){if(!condition)throw new Error(message);report.push(message);console.log('PASS '+message);}
const base='http://127.0.0.1:3301',origin='https://lab-integration.invalid';
try{
 const password='Test9!'+randomBytes(16).toString('hex');const hash=await hashPassword(password);
 for(const [name,role] of [['admin','ADMIN'],['owner','STUDENT'],['other','STUDENT'],['third','STUDENT']])ids.push(await db.user.create({data:{email:`${name}-${suffix}@example.invalid`,name,passwordHash:hash,role}}));
 const [admin,owner,other,third]=ids;
 course=await db.course.create({data:{title:'Isolated lab integration '+suffix,published:true}});
 for(const user of [owner,other,third])await db.enrollment.create({data:{userId:user.id,courseId:course.id,status:'APPROVED'}});
 async function cookie(user){const token=randomBytes(32).toString('hex');await db.session.create({data:{userId:user.id,tokenHash:createHash('sha256').update(token).digest('hex'),expiresAt:new Date(Date.now()+600000)}});return 'lms_session='+token;}
 const adminCookie=await cookie(admin),ownerCookie=await cookie(owner),otherCookie=await cookie(other);
 app=spawn(process.execPath,['node_modules/next/dist/bin/next','start','-p','3301','-H','127.0.0.1'],{env:{...process.env,APP_ORIGIN:origin,LAB_CREDENTIALS_KEY:randomBytes(32).toString('base64'),NEXT_TELEMETRY_DISABLED:'1'},stdio:['ignore','ignore','pipe']});app.stderr.on('data',()=>{});
 let ready=false;for(let i=0;i<100;i++){try{if((await fetch(base+'/api/health')).ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}check(ready,'Lab test HTTP process starts');
 async function post(url,data,cookie='',token='',extra={}){return fetch(base+url,{method:'POST',headers:{'Content-Type':'application/json','x-forwarded-proto':'https',origin,...(cookie?{cookie}:{}),...(token?{authorization:'Bearer '+token}:{}),...extra},body:JSON.stringify(data)});}
 const labId='test-'+suffix;
 const make=(user,code)=>({email:user.email,labId,studentCode:code,accountId:'123456789012',region:'ap-northeast-2',username:labId+'-'+code,instanceId:'i-'+randomBytes(8).toString('hex'),sessionDocument:labId+'-shell',initialPassword:'Initial9!'+randomBytes(12).toString('hex')});
 const first=make(owner,'s01'),second=make(other,'s02');
 let r=await post('/api/admin/lab-token',{password},ownerCookie);check(r.status===403,'Student cannot mint operator transfer token');
 r=await post('/api/admin/lab-token',{password},adminCookie);let payload=await r.json();check(r.ok&&payload.token?.length===64,'Admin reauthentication mints short-lived transfer token');const token=payload.token;
 r=await post('/api/admin/lab-import',{batch:{version:1,courseId:course.id,entries:[first,second]}},'',token);check(r.ok&&(await r.json()).count===2,'Operator batch connects approved exact-email students');
 const assignment=await db.labAccess.findFirst({where:{labId,studentCode:'s01'}});check(assignment&&!assignment.secretData.includes(first.initialPassword),'Database stores ciphertext rather than plaintext password');
 r=await post('/api/admin/lab-import',{batch:{version:1,courseId:course.id,entries:[first]}},'',token);check(r.status===400,'Successful transfer token cannot be replayed');
 r=await fetch(base+'/classroom/lab?course='+course.id,{headers:{cookie:ownerCookie}});check(r.ok&&!(await r.text()).includes(first.initialPassword),'Student page does not embed secrets before reauthentication');
 r=await post('/api/lab-access',{courseId:course.id,password:'wrong'},ownerCookie);check(r.status===400,'Incorrect LMS password cannot reveal AWS secret');
 r=await post('/api/lab-access',{courseId:course.id,password,assignmentId:'forged'},ownerCookie);payload=await r.json();check(r.ok&&payload.secrets.initialPassword===first.initialPassword,'Owner retrieves only assigned credentials after password check');check(/no-store/.test(r.headers.get('cache-control')),'Credential response disables caching');
 r=await post('/api/lab-access',{courseId:course.id,password,assignmentId:assignment.id},otherCookie);payload=await r.json();check(r.ok&&payload.secrets.initialPassword===second.initialPassword,'Forged assignment ID cannot retrieve another student password');
 r=await post('/api/lab-access',{courseId:course.id,password},ownerCookie,'',{origin:'https://foreign.invalid'});check(r.status===403,'Cross-origin credential request is rejected');
 r=await post('/api/lab-access',{courseId:course.id,password},ownerCookie,'',{'x-forwarded-proto':'http'});check(r.status===403,'HTTP proxy request cannot reveal secret');
 r=await post('/api/lab-access',{courseId:course.id,password});check(r.status===401,'Anonymous secret retrieval rejected');
 r=await post('/api/admin/lab-import',{password,batch:{version:1,courseId:course.id,entries:[{...first,email:other.email}]}},adminCookie);check(r.status===400,'Existing AWS identity cannot silently move to another student');
 // A failed multi-row transfer must roll back both earlier assignments and token consumption.
 r=await post('/api/admin/lab-token',{password},adminCookie);const token2=(await r.json()).token;
 const thirdEntry=make(third,'s03'),missing=make({email:'missing-'+suffix+'@example.invalid'},'s04');
 r=await post('/api/admin/lab-import',{batch:{version:1,courseId:course.id,entries:[thirdEntry,missing]}},'',token2);check(r.status===400,'Mixed valid and unknown-recipient batch rejected');
 check(await db.labAccess.count({where:{labId,studentCode:'s03'}})===0,'Failed batch leaves no partial student assignment');
 const storedToken=await db.labTransferToken.findUnique({where:{tokenHash:createHash('sha256').update(token2).digest('hex')}});check(storedToken?.consumedAt===null,'Failed transaction does not consume transfer token');
 r=await post('/api/admin/lab-revoke',{id:assignment.id,action:'revoke'},adminCookie);check(r.ok,'Admin can stop student web disclosure');
 r=await post('/api/lab-access',{courseId:course.id,password},ownerCookie);check(r.status===400,'Revoked assignment no longer returns secrets');
 await db.enrollment.update({where:{userId_courseId:{userId:other.id,courseId:course.id}},data:{status:'REJECTED'}});
 r=await post('/api/lab-access',{courseId:course.id,password},otherCookie);check(r.status===400,'Rejected enrollment immediately loses credential access');
 await fs.mkdir('test-results',{recursive:true});await fs.writeFile('test-results/lab-integration.json',JSON.stringify({checks:report},null,2));console.log('LAB_INTEGRATION_OK '+report.length);
}finally{
 app?.kill();if(app)await new Promise(resolve=>{app.once('exit',resolve);setTimeout(resolve,1500)});
 if(course){await db.labAccess.deleteMany({where:{enrollment:{courseId:course.id}}});await db.enrollment.deleteMany({where:{courseId:course.id}});await db.course.delete({where:{id:course.id}});}
 await db.labTransferToken.deleteMany({where:{adminId:{in:ids.map(x=>x.id)}}});await db.labAccessAudit.deleteMany({where:{actorId:{in:ids.map(x=>x.id)}}});await db.user.deleteMany({where:{id:{in:ids.map(x=>x.id)}}});await db.$disconnect();
}

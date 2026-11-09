import fs from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {randomBytes,createHash} from 'node:crypto';
import {PrismaClient} from '@prisma/client';
import {hashPassword,verifyPassword} from '../lib/password.mjs';
if(process.env.LMS_INTEGRATION_TEST!=='true'||!process.env.DATABASE_URL)throw new Error('Dedicated test database required');
const db=new PrismaClient(),suffix=randomBytes(6).toString('hex'),base='http://127.0.0.1:3302',report=[];let app,course;const ids=[];
function check(value,label){if(!value)throw new Error(label);report.push(label);console.log('PASS '+label);}
async function session(user){const token=randomBytes(32).toString('hex');await db.session.create({data:{userId:user.id,passwordVersion:user.passwordVersion,tokenHash:createHash('sha256').update(token).digest('hex'),expiresAt:new Date(Date.now()+600000)}});return 'lms_session='+token;}
async function page(path,cookie=''){return fetch(base+path,{headers:cookie?{cookie}:{},redirect:'manual'});}
async function action(path,values,cookie=''){const html=await (await page(path,cookie)).text();const forms=html.match(/<form[\s\S]*?<\/form>/g)??[];const selected=forms.find(f=>Object.keys(values).filter(k=>k!=='userId').every(k=>f.includes('name="'+k+'"')));const match=selected?.match(/name="(\$ACTION_ID_[^"]+)"/);if(!match)throw new Error('Missing form '+path);const form=new FormData();form.set(match[1],'');for(const [k,v] of Object.entries(values))form.set(k,v);return fetch(base+path,{method:'POST',headers:{origin:base,...(cookie?{cookie}:{})},body:form,redirect:'manual'});}
async function reset(userId,password,cookie,origin=base){return fetch(base+'/api/admin/password-reset',{method:'POST',headers:{origin,cookie,'Content-Type':'application/json'},body:JSON.stringify({userId,adminPassword:password,confirm:true}),redirect:'manual'});}
try{
 const password='Account9!'+randomBytes(14).toString('hex'),newPassword='New9!'+randomBytes(18).toString('hex');
 for(const [name,role] of [['admin','ADMIN'],['student','STUDENT'],['other','STUDENT']])ids.push(await db.user.create({data:{name,email:`account-${name}-${suffix}@example.invalid`,studentNumber:name,passwordHash:await hashPassword(password),role}}));
 const [admin,student,other]=ids;const adminCookie=await session(admin),studentCookie=await session(student),otherCookie=await session(other);
 course=await db.course.create({data:{title:'Account test '+suffix,published:true}});const enrollment=await db.enrollment.create({data:{userId:student.id,courseId:course.id,status:'APPROVED'}});
 await db.labAccess.create({data:{enrollmentId:enrollment.id,labId:'account-test',studentCode:'s01',accountId:'123456789012',publicData:{},secretData:'unchanged-encrypted-fixture'}});
 app=spawn(process.execPath,['node_modules/next/dist/bin/next','start','-p','3302','-H','127.0.0.1'],{env:{...process.env,APP_ORIGIN:base},stdio:['ignore','ignore','pipe']});app.stderr.on('data',()=>{});
 let ready=false;for(let i=0;i<100;i++){try{if((await page('/api/health')).ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}check(ready,'Account HTTP test starts');
 check((await page('/mypage')).status===307,'Anonymous mypage redirects');
 let html=await (await page('/mypage',studentCookie)).text();check(html.includes(student.email)&&!html.includes(other.email),'Mypage exposes only own identity');
 check((await page('/admin/users',studentCookie)).status===307,'Students cannot open account administration');
 let response=await action('/mypage',{name:'변경 학생',userId:other.id},studentCookie);check(response.status===303&&(await db.user.findUnique({where:{id:student.id}})).name==='변경 학생'&&(await db.user.findUnique({where:{id:other.id}})).name===other.name,'Profile ignores forged target user');
 response=await action('/mypage/password',{currentPassword:'incorrect',password:newPassword,confirmation:newPassword},studentCookie);check(response.headers.get('location')?.includes('error='),'Wrong current password rejected');
 check((await reset(student.id,password,adminCookie,'https://foreign.invalid')).status===403,'Foreign origin reset rejected');
 check((await reset(other.id,password,studentCookie)).status===403,'Student cannot reset another account');
 check((await reset(student.id,'incorrect',adminCookie)).status===403,'Admin reauthentication required');
 check((await reset(admin.id,password,adminCookie)).status===400,'Administrator accounts excluded from student reset');
 response=await reset(student.id,password,adminCookie);const issued=await response.json();check(response.ok&&typeof issued.temporaryPassword==='string','Admin issues temporary password');check(response.headers.get('cache-control')?.includes('no-store'),'Temporary secret response is not cached');
 check((await db.session.count({where:{userId:student.id}}))===0,'Reset invalidates existing student sessions');check((await page('/mypage',studentCookie)).status===307,'Old session cannot open mypage');check((await page('/mypage',otherCookie)).status===200,'Other student session remains valid');
 response=await action('/login',{email:student.email,password});check(response.headers.get('location')?.includes('error='),'Old password no longer authenticates');
 response=await action('/login',{email:student.email,password:issued.temporaryPassword});let temporaryCookie=response.headers.get('set-cookie')?.split(';')[0];check(response.headers.get('location')==='/mypage/password'&&temporaryCookie,'Temporary login requires password change');
 check((await page('/classroom',temporaryCookie)).headers.get('location')==='/mypage/password','Temporary user cannot enter classroom');check((await page('/api/admin/results',temporaryCookie)).status===403,'Temporary session cannot bypass direct API guards');
 await db.user.update({where:{id:student.id},data:{temporaryPasswordExpiresAt:new Date(Date.now()-1000)}});
 check((await page('/mypage/password',temporaryCookie)).status===307,'Expired temporary session denied');response=await action('/login',{email:student.email,password:issued.temporaryPassword});check(response.headers.get('location')?.includes('error='),'Expired temporary password cannot log in');
 response=await reset(student.id,password,adminCookie);const second=await response.json();check(response.ok&&second.temporaryPassword!==issued.temporaryPassword,'Reissue rotates temporary password');
 response=await action('/login',{email:student.email,password:second.temporaryPassword});temporaryCookie=response.headers.get('set-cookie')?.split(';')[0];
 response=await action('/mypage/password',{currentPassword:second.temporaryPassword,password:newPassword,confirmation:newPassword},temporaryCookie);check(response.headers.get('location')==='/login?changed=1','Student sets own password and returns to login');
 const updated=await db.user.findUniqueOrThrow({where:{id:student.id}});check(!updated.mustChangePassword&&updated.temporaryPasswordExpiresAt===null&&await verifyPassword(newPassword,updated.passwordHash),'Password hash and temporary flags updated');check((await db.session.count({where:{userId:student.id}}))===0,'Password change revokes all sessions');
 check((await db.enrollment.findUnique({where:{id:enrollment.id}})).status==='APPROVED'&&(await db.labAccess.findUnique({where:{enrollmentId:enrollment.id}})).secretData==='unchanged-encrypted-fixture','Enrollment and assigned lab preserved');
 response=await action('/login',{email:student.email,password:newPassword});check(response.headers.get('location')==='/classroom','New password returns student to classroom');
 check(await db.accountAudit.count({where:{targetUserId:student.id}})===3,'Reset and password changes audited without secrets');
 // A stale in-flight login session must fail even if inserted after revocation.
 const staleCookie=await session(student);check((await page('/mypage',staleCookie)).status===307,'Credential version blocks a stale concurrent session');
 await fs.mkdir('test-results',{recursive:true});await fs.writeFile('test-results/accounts.json',JSON.stringify({checks:report},null,2));console.log('ACCOUNT_INTEGRATION_OK '+report.length);
}catch(e){console.error('ACCOUNT_INTEGRATION_FAILED',e.message);process.exitCode=1;}finally{app?.kill();if(course){await db.labAccess.deleteMany({where:{enrollment:{courseId:course.id}}});await db.enrollment.deleteMany({where:{courseId:course.id}});await db.course.delete({where:{id:course.id}});}await db.accountAudit.deleteMany({where:{targetUserId:{in:ids.map(u=>u.id)}}});await db.user.deleteMany({where:{id:{in:ids.map(u=>u.id)}}});await db.$disconnect();}

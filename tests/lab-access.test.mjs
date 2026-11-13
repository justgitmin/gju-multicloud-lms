import test from 'node:test';
import assert from 'node:assert/strict';
import {randomBytes} from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import ts from 'typescript';
import {encryptLab,decryptLab,labAad,labKey,validateLabBatch,labLinks} from '../lib/lab-secrets.mjs';
const require=createRequire(import.meta.url);
const key=randomBytes(32).toString('base64');
const entry={email:'Student@example.invalid',labId:'test-lab',studentCode:'s01',accountId:'123456789012',region:'ap-northeast-2',username:'test-lab-s01',instanceId:'i-0123456789abcdef0',sessionDocument:'test-lab-shell',initialPassword:'initial-password-test',bucketName:'private-lab-bucket',dbEndpoint:'student.database.ap-northeast-2.rds.amazonaws.com',dbPassword:'database-password-test'};
const batch=()=>({version:1,courseId:'course-test',entries:[{...entry}]});
function loadTs(filename,mocks){const file=path.resolve(filename);const source=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};new Function('require','exports','module',source)(id=>id in mocks?mocks[id]:require(id),exports,{exports});return exports;}
test('encrypted credentials are randomized and bind to a student enrollment',()=>{
 const secret={initialPassword:entry.initialPassword,dbPassword:entry.dbPassword};const aad=labAad('enrollment-a',entry);const first=encryptLab(secret,aad,key),second=encryptLab(secret,aad,key);
 assert.notEqual(first,second);assert.ok(!first.includes(entry.initialPassword));assert.deepEqual(decryptLab(first,aad,key),secret);
 assert.throws(()=>decryptLab(first,labAad('enrollment-b',entry),key));assert.throws(()=>decryptLab(first,aad,randomBytes(32).toString('base64')));
 const parts=first.split('.');parts[3]=Buffer.from('modified').toString('base64');assert.throws(()=>decryptLab(parts.join('.'),aad,key));
});
test('missing and malformed encryption keys fail closed',()=>{assert.throws(()=>labKey(''));assert.throws(()=>labKey('a'.repeat(44)));assert.equal(labKey(key).length,32);});
test('import excludes arbitrary URLs and administrator keys from retained fields',()=>{
 const b=batch();b.entries[0].AWS_SECRET_ACCESS_KEY='not-an-accepted-field';b.entries[0].sessionUrl='https://foreign.invalid';const e=validateLabBatch(b).entries[0];
 assert.equal(e.email,'student@example.invalid');assert.equal(e.publicData.initialPassword,undefined);assert.equal(e.publicData.AWS_SECRET_ACCESS_KEY,undefined);assert.match(labLinks(e.publicData).session,/^https:\/\/ap-northeast-2\.console\.aws\.amazon\.com/);
});
test('duplicate recipients, foreign DB hosts and mismatched AWS usernames are rejected',()=>{
 let b=batch();b.entries.push({...entry,studentCode:'s02',username:'test-lab-s02'});assert.throws(()=>validateLabBatch(b));
 b=batch();b.entries[0].dbEndpoint='https://foreign.invalid';assert.throws(()=>validateLabBatch(b));
 b=batch();b.entries[0].username='someone-else';assert.throws(()=>validateLabBatch(b));
});
test('HTTPS guard requires configured HTTPS, valid key, proxy TLS and matching browser origin',()=>{
 const old={origin:process.env.APP_ORIGIN,key:process.env.LAB_CREDENTIALS_KEY};process.env.APP_ORIGIN='https://lms.example.invalid';process.env.LAB_CREDENTIALS_KEY=key;
 try{const guard=loadTs('lib/lab-http.ts',{'./origin.mjs':{sameOrigin:(origin,host,configured)=>origin===configured},'./lab-secrets.mjs':{labKey}});
 const req=(origin,proto)=>new Request('http://internal/api',{headers:{origin,host:'lms.example.invalid',...(proto?{'x-forwarded-proto':proto}:{})}});
 assert.equal(guard.labRequestAllowed(req('https://lms.example.invalid','https')),true);
 assert.equal(guard.labRequestAllowed(req('https://foreign.invalid','https')),false);
 assert.equal(guard.labRequestAllowed(req('https://lms.example.invalid','http')),false);
 process.env.APP_ORIGIN='http://lms.example.invalid';assert.equal(guard.labRequestAllowed(req('http://lms.example.invalid','https')),false);
 }finally{if(old.origin===undefined)delete process.env.APP_ORIGIN;else process.env.APP_ORIGIN=old.origin;if(old.key===undefined)delete process.env.LAB_CREDENTIALS_KEY;else process.env.LAB_CREDENTIALS_KEY=old.key;}
});
test('student secret endpoint ignores forged assignment IDs and scopes lookup to approved owner',async()=>{
 const aad=labAad('enrollment-owner',entry);const row={...entry,enrollmentId:'enrollment-owner',id:'assignment-owner',publicData:validateLabBatch(batch()).entries[0].publicData,secretData:encryptLab({initialPassword:entry.initialPassword},aad,key)};
 let filter,audits=[];const route=loadTs('app/api/lab-access/route.ts',{
 '../../../lib/auth':{currentUser:async()=>({id:'student-owner',passwordHash:'hash'}),allowAttempt:async()=>true},
 '../../../lib/password.mjs':{verifyPassword:async(p)=>p==='correct-password'},
 '../../../lib/db':{db:{labAccess:{findFirst:async({where})=>{filter=where;return row;}},labAccessAudit:{create:async data=>audits.push(data)}}},
 '../../../lib/lab-secrets.mjs':{decryptLab:(v,a)=>decryptLab(v,a,key),labAad},
 '../../../lib/lab-http':{labRequestAllowed:()=>true,limitedJson:request=>request.json(),privateHeaders:{'Cache-Control':'private, no-store'}}
 });
 const r=await route.POST(new Request('https://lms.example.invalid/api/lab-access',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({courseId:'course-test',password:'correct-password',assignmentId:'someone-else'})}));
 assert.equal(r.status,200);assert.equal(filter.enrollment.userId,'student-owner');assert.equal(filter.enrollment.status,'APPROVED');assert.equal(filter.enrollment.course.published,true);assert.equal(filter.active,true);assert.equal(filter.id,undefined);assert.equal(audits.length,1);assert.match(r.headers.get('cache-control'),/no-store/);
 const body=await r.json();assert.equal(body.secrets.initialPassword,entry.initialPassword);
});
test('student endpoint refuses incorrect reauthentication before reading assignment',async()=>{
 let reads=0;const route=loadTs('app/api/lab-access/route.ts',{
 '../../../lib/auth':{currentUser:async()=>({id:'student',passwordHash:'hash'}),allowAttempt:async()=>true},
 '../../../lib/password.mjs':{verifyPassword:async()=>false},
 '../../../lib/db':{db:{labAccess:{findFirst:async()=>{reads++;return null}}}},
 '../../../lib/lab-secrets.mjs':{decryptLab,labAad},
 '../../../lib/lab-http':{labRequestAllowed:()=>true,limitedJson:request=>request.json(),privateHeaders:{'Cache-Control':'no-store'}}
 });
 const r=await route.POST(new Request('https://lms.example.invalid/api/lab-access',{method:'POST',body:JSON.stringify({courseId:'course-test',password:'wrong'})}));assert.equal(r.status,400);assert.equal(reads,0);
});
test('import refuses reassignment of an AWS identity already owned by another student',async()=>{
 let writes=0;const tx={enrollment:{findFirst:async()=>({id:'new-enrollment',user:{name:'student',email:entry.email}})},labAccess:{findUnique:async()=>({enrollmentId:'old-enrollment'}),upsert:async()=>{writes++}}};
 const importer=loadTs('lib/lab-import.ts',{'@prisma/client':{Prisma:{TransactionIsolationLevel:{Serializable:'Serializable'}}},'./db':{db:{$transaction:async fn=>fn(tx)}},'./lab-secrets.mjs':{validateLabBatch,encryptLab,labAad,labKey:()=>labKey(key)}});
 await assert.rejects(()=>importer.importLabBatch(batch(),'operator'),/다른 학생/);assert.equal(writes,0);
});

test('stable LMS identities survive validation and never enter public or secret fields',()=>{
 const b=batch();b.entries[0]={...b.entries[0],userId:'student-id',enrollmentId:'enrollment-id'};
 const value=validateLabBatch(b).entries[0];assert.equal(value.userId,'student-id');assert.equal(value.enrollmentId,'enrollment-id');assert.equal(value.publicData.userId,undefined);assert.equal(value.secrets.userId,undefined);
 b.entries[0].enrollmentId='';assert.throws(()=>validateLabBatch(b));
});
test('import binds stable user and enrollment IDs instead of guessing by a changed email',async()=>{
 let query,writes=0;const tx={enrollment:{findFirst:async args=>{query=args.where;return null}},labAccess:{upsert:async()=>{writes++}}};
 const importer=loadTs('lib/lab-import.ts',{'@prisma/client':{Prisma:{TransactionIsolationLevel:{Serializable:'Serializable'}}},'./db':{db:{$transaction:async fn=>fn(tx)}},'./lab-secrets.mjs':{validateLabBatch,encryptLab,labAad,labKey:()=>labKey(key)}});
 const b=batch();b.entries[0]={...b.entries[0],userId:'student-id',enrollmentId:'enrollment-id'};
 await assert.rejects(()=>importer.importLabBatch(b,'operator'));assert.equal(query.id,'enrollment-id');assert.equal(query.user.id,'student-id');assert.equal(query.user.email,undefined);assert.equal(query.status,'APPROVED');assert.equal(writes,0);
});

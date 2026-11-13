import {createCipheriv,createDecipheriv,randomBytes} from 'node:crypto';
export function labKey(encoded=process.env.LAB_CREDENTIALS_KEY){
 if(typeof encoded!=='string'||!/^([A-Za-z0-9+/]{43}=)$/.test(encoded))throw new Error('실습 정보 암호화 키가 준비되지 않았습니다.');
 const key=Buffer.from(encoded,'base64');if(key.length!==32)throw new Error('실습 정보 암호화 키를 확인하세요.');return key;
}
export function encryptLab(value,aad,encoded){const key=labKey(encoded);const iv=randomBytes(12);const c=createCipheriv('aes-256-gcm',key,iv);c.setAAD(Buffer.from(aad));const data=Buffer.concat([c.update(JSON.stringify(value),'utf8'),c.final()]);return ['v1',iv.toString('base64'),c.getAuthTag().toString('base64'),data.toString('base64')].join('.');}
export function decryptLab(value,aad,encoded){const [version,iv,tag,data,...rest]=value.split('.');if(version!=='v1'||rest.length||!iv||!tag||!data)throw new Error('저장된 실습 정보를 확인하세요.');const c=createDecipheriv('aes-256-gcm',labKey(encoded),Buffer.from(iv,'base64'),{authTagLength:16});if(Buffer.from(iv,'base64').length!==12||Buffer.from(tag,'base64').length!==16)throw new Error('Invalid encrypted payload');c.setAAD(Buffer.from(aad));c.setAuthTag(Buffer.from(tag,'base64'));return JSON.parse(Buffer.concat([c.update(Buffer.from(data,'base64')),c.final()]).toString('utf8'));}
export function labAad(enrollmentId,entry){return JSON.stringify([enrollmentId,entry.accountId,entry.labId,entry.studentCode]);}
export function validateLabBatch(input){
 if(!input||input.version!==1||typeof input.courseId!=='string'||!input.courseId||input.courseId.length>100||!Array.isArray(input.entries)||!input.entries.length||input.entries.length>30)throw new Error('전송 형식을 확인하세요.');
 const emails=new Set(),identities=new Set();
 const entries=input.entries.map(e=>{
  if(!e||typeof e.email!=='string')throw new Error('학생 이메일이 필요합니다.');const email=e.email.trim().toLowerCase();
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||email.length>254||emails.has(email))throw new Error('학생 이메일 형식 또는 중복을 확인하세요.');emails.add(email);
  if(!/^[a-z][a-z0-9-]{2,24}$/.test(e.labId)||!/^s\d{2}$/.test(e.studentCode)||!/^\d{12}$/.test(e.accountId)||e.region!=='ap-northeast-2'||!/^i-[a-f0-9]{8,17}$/.test(e.instanceId)||e.username!==e.labId+'-'+e.studentCode||e.sessionDocument!==e.labId+'-shell')throw new Error('AWS 환경 식별자를 확인하세요.');
  const identity=[e.accountId,e.labId,e.studentCode].join(':');if(identities.has(identity))throw new Error('AWS 학생 계정이 중복되었습니다.');identities.add(identity);
  if(typeof e.initialPassword!=='string'||e.initialPassword.length<12||e.initialPassword.length>128)throw new Error('초기 비밀번호 형식을 확인하세요.');
  if(e.bucketName!==undefined&&!/^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$/.test(e.bucketName))throw new Error('S3 버킷 이름을 확인하세요.');
  if(e.dbEndpoint!==undefined&&(!/^[a-z0-9.-]+\.ap-northeast-2\.rds\.amazonaws\.com$/.test(e.dbEndpoint)||typeof e.dbPassword!=='string'||e.dbPassword.length<12||e.dbPassword.length>128))throw new Error('DB 접속 정보를 확인하세요.');
  if(e.userId!==undefined&&(typeof e.userId!=='string'||!/^[a-zA-Z0-9_-]{1,100}$/.test(e.userId)||typeof e.enrollmentId!=='string'||!/^[a-zA-Z0-9_-]{1,100}$/.test(e.enrollmentId)))throw new Error('LMS 학생 식별자를 확인하세요.');
  const publicData={accountId:e.accountId,labId:e.labId,studentCode:e.studentCode,region:e.region,username:e.username,instanceId:e.instanceId,sessionDocument:e.sessionDocument};
  if(e.bucketName)publicData.bucketName=e.bucketName;
  if(e.dbEndpoint)publicData.dbEndpoint=e.dbEndpoint;
  return {email,...(e.userId?{userId:e.userId,enrollmentId:e.enrollmentId}:{}),...publicData,publicData,secrets:{initialPassword:e.initialPassword,...(e.dbEndpoint?{dbPassword:e.dbPassword}:{})}};
 });return {courseId:input.courseId,entries};
}
export function labLinks(d){return {login:`https://${d.accountId}.signin.aws.amazon.com/console/`,session:`https://${d.region}.console.aws.amazon.com/systems-manager/session-manager/start-session?region=${d.region}&target=${d.instanceId}&documentName=${d.sessionDocument}`,...(d.bucketName?{s3:`https://s3.console.aws.amazon.com/s3/buckets/${d.bucketName}?region=${d.region}&prefix=practice/&showversions=false`}:{})};}

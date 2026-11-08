export type LabPublic={accountId:string,labId:string,studentCode:string,region:string,username:string,instanceId:string,sessionDocument:string,bucketName?:string,dbEndpoint?:string};
export type LabSecret={initialPassword:string,dbPassword?:string};
export function labKey(encoded?:string):Buffer;
export function encryptLab(value:LabSecret,aad:string,encoded?:string):string;
export function decryptLab(value:string,aad:string,encoded?:string):LabSecret;
export function labAad(enrollmentId:string,entry:Pick<LabPublic,'accountId'|'labId'|'studentCode'>):string;
export function validateLabBatch(input:unknown):{courseId:string,entries:(LabPublic&{email:string,publicData:LabPublic,secrets:LabSecret})[]};
export function labLinks(d:LabPublic):{login:string,session:string,s3?:string};

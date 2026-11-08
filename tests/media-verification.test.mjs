import test from 'node:test';
import assert from 'node:assert/strict';
import {Readable} from 'node:stream';
import {createHash} from 'node:crypto';
import {verifyObject,verifyCourseMedia} from '../scripts/lib/verify-course-media.mjs';
const expected=Buffer.from('latest captions');
const spec={bytes:expected.length,sha256:createHash('sha256').update(expected).digest('hex'),contentType:'text/vtt'};
function client(bytes=expected,type='text/vtt; charset=utf-8',length=bytes.length){return async()=>({Body:Readable.from([bytes.subarray(0,4),bytes.subarray(4)]),ContentLength:length,ContentType:type});}
test('streamed content matches bytes and full SHA-256',async()=>{await verifyObject(client(),'bucket','caption',spec);});
test('same-sized stale caption is rejected',async()=>{await assert.rejects(verifyObject(client(Buffer.from('older! captions')),'bucket','caption',spec),/content mismatch/);});
test('wrong MIME type and truncated streams are rejected',async()=>{
 await assert.rejects(verifyObject(client(expected,'application/octet-stream'),'bucket','caption',spec),/Content-Type/);
 await assert.rejects(verifyObject(client(expected.subarray(0,8),'text/vtt',expected.length),'bucket','caption',spec),/content mismatch/);
});
test('course rejects duplicate records before any remote reads',async()=>{
 await assert.rejects(verifyCourseMedia({getObject:()=>assert.fail('must not read'),bucket:'bucket',entries:Array(16).fill({id:'aws-01'})}),/unique/);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
function auth(session){const source=ts.transpileModule(fs.readFileSync('lib/auth.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};const mocks={'node:crypto':{createHash:()=>({update:()=>({digest:()=>''})})},'next/headers':{cookies:async()=>({get:()=>({value:'a'.repeat(64)})})},'next/navigation':{redirect:path=>{throw new Error('REDIRECT '+path)}},'./db':{db:{session:{findUnique:async()=>session}}}};new Function('require','exports','module',source)(id=>mocks[id],exports,{exports});return exports;}
const session=()=>({expiresAt:new Date(Date.now()+600000),passwordVersion:2,user:{id:'owner',passwordVersion:2,mustChangePassword:false}});
test('a stale credential session is rejected even if revocation raced with login',async()=>{const s=session();s.passwordVersion=1;assert.equal(await auth(s).currentUser(),null);});
test('temporary credentials only authorize password-change path',async()=>{const s=session();s.user.mustChangePassword=true;s.user.temporaryPasswordExpiresAt=new Date(Date.now()+600000);const a=auth(s);assert.equal(await a.currentUser(),null);assert.equal((await a.currentUser({allowPasswordChange:true})).id,'owner');await assert.rejects(a.requireUser(),/REDIRECT \/mypage\/password/);assert.equal((await a.requireUser({allowPasswordChange:true})).id,'owner');});
test('expired temporary credentials do not authorize even the password form',async()=>{const s=session();s.user.mustChangePassword=true;s.user.temporaryPasswordExpiresAt=new Date(Date.now()-1000);assert.equal(await auth(s).currentUser({allowPasswordChange:true}),null);});

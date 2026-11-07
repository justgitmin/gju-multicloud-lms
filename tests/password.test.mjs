import test from 'node:test';
import assert from 'node:assert/strict';
import {hashPassword,verifyPassword,validPassword} from '../lib/password.mjs';
test('password hashing uses unique salt and verifies only matching password',async()=>{const a=await hashPassword('valid-password-123');const b=await hashPassword('valid-password-123');assert.notEqual(a,b);assert.equal(await verifyPassword('valid-password-123',a),true);assert.equal(await verifyPassword('wrong-password-123',a),false);});
test('rejects malformed hashes and oversized input',async()=>{assert.equal(await verifyPassword('test','scrypt:bad:hash'),false);assert.equal(await verifyPassword('x'.repeat(129),'invalid'),false);assert.equal(validPassword('short'),false);assert.equal(validPassword('x'.repeat(12)),true);assert.equal(validPassword('x'.repeat(129)),false);await assert.rejects(hashPassword('short'));});

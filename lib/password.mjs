import {randomBytes,scrypt as scryptCallback,timingSafeEqual} from 'node:crypto';
import {promisify} from 'node:util';
const scrypt=promisify(scryptCallback);
export function validPassword(password){return typeof password==='string' && password.length>=12 && password.length<=128;}
export async function hashPassword(password){
 if(!validPassword(password)) throw new Error('Password must contain 12–128 characters');
 const salt=randomBytes(16).toString('hex');
 const key=await scrypt(password,salt,64);
 return `scrypt:${salt}:${key.toString('hex')}`;
}
export async function verifyPassword(password,encoded){
 if(typeof password!=='string'||password.length>128) return false;
 const parts=encoded.split(':');
 if(parts.length!==3||parts[0]!=='scrypt'||!/^[a-f0-9]{32}$/.test(parts[1])||!/^[a-f0-9]{128}$/.test(parts[2]))return false;
 const key=await scrypt(password,parts[1],64);
 return timingSafeEqual(key,Buffer.from(parts[2],'hex'));
}

'use client';
import {useState} from 'react';
export default function ResetPassword({id,name,email}:{id:string,name:string,email:string}){
 const [open,setOpen]=useState(false),[pending,setPending]=useState(false),[error,setError]=useState('');
 const [issued,setIssued]=useState<{temporaryPassword:string,expiresAt:string}|null>(null);
 async function reset(event:React.FormEvent<HTMLFormElement>){
  event.preventDefault();if(pending)return;setPending(true);setError('');setIssued(null);
  const form=event.currentTarget;const data=new FormData(form);
  try{const response=await fetch('/api/admin/password-reset',{method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',body:JSON.stringify({userId:id,adminPassword:data.get('adminPassword'),confirm:data.get('confirm')==='on'})});const result=await response.json();if(!response.ok)throw new Error(result.error??'발급에 실패했습니다.');setIssued(result);form.reset();}catch(e){setError(e instanceof Error?e.message:'요청에 실패했습니다.');}finally{setPending(false);}
 }
 return <div><button className="smallbutton" type="button" onClick={()=>{setOpen(!open);setIssued(null);setError('');}}>{open?'닫기':'비밀번호 초기화'}</button>{open&&<div className="lab-secret">{issued?<div role="status"><b>{name} · {email}</b><p>임시 비밀번호 <code>{issued.temporaryPassword}</code></p><p>발급 후 24시간 유효합니다. 학생 본인에게 개별 전달하세요. 첫 로그인 후 변경해야 합니다.</p><p>이 창을 닫으면 다시 표시되지 않습니다. 다시 발급하면 이전 임시 비밀번호는 사용할 수 없습니다.</p><button type="button" className="smallbutton" onClick={()=>{setIssued(null);setOpen(false);}}>전달 완료 · 닫기</button></div>:<form onSubmit={reset} className="assessmentform"><b>{name} · {email}</b><p>기존 비밀번호와 모든 로그인 세션이 무효화됩니다. 학생 본인 확인 후 발급하세요.</p><label>관리자 본인의 비밀번호<input name="adminPassword" type="password" autoComplete="current-password" required maxLength={128}/></label><label className="check"><input type="checkbox" name="confirm" required/>초기화 대상 학생을 확인했습니다.</label>{error&&<p role="alert" className="error">{error}</p>}<button className="button" disabled={pending}>{pending?'발급 중…':'임시 비밀번호 발급'}</button></form>}</div>}</div>;
}

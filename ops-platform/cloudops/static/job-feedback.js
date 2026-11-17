'use strict';
for (const form of document.querySelectorAll('form[data-job-feedback]')) {
 let busy=false;
 const status=document.createElement('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');form.append(status);
 const link=document.createElement('a');link.href='/#jobs';link.textContent='작업 기록 보기';link.hidden=true;form.append(link);
 const buttons=[...form.querySelectorAll('button')];
 const lock=value=>{busy=value;buttons.forEach(b=>b.disabled=value);};
 form.addEventListener('submit',async event=>{
  event.preventDefault();if(busy)return;
  const data=new FormData(form);if(event.submitter?.name)data.set(event.submitter.name,event.submitter.value);
  lock(true);status.textContent='요청을 보내는 중입니다…';link.hidden=true;
  let id='';
  try {
   const response=await fetch(form.action,{method:'POST',body:new URLSearchParams(data),headers:{Accept:'application/json'}});
   if(!response.ok){
    status.textContent=response.status===401?'로그인이 만료되었습니다. 다시 로그인해 주세요.':response.status===409?'실행 중인 작업이 있습니다. 작업 기록을 확인하세요.':'접수 실패: 관리자 비밀번호·확인 체크·환경 이름·계정을 확인하세요.';
    lock(false);link.hidden=false;return;
   }
   const result=await response.json();id=result.jobId;if(!/^[a-f0-9]{32}$/.test(id))throw new Error('receipt');
   form.querySelector('[name="password"]').value='';
   status.textContent='✓ 작업이 접수되었습니다. 대기 중 · '+id.slice(0,10);link.hidden=false;
  } catch {
   status.textContent='접수 여부를 확인하지 못했습니다. 중복 실행하지 말고 작업 기록을 먼저 확인하세요.';link.hidden=false;return;
  }
  const poll=async()=>{
   try {
    const response=await fetch('/api/overview',{cache:'no-store'});if(!response.ok)throw new Error('status');
    const data=await response.json();const job=data.jobs.find(j=>j.id===id);if(!job)throw new Error('missing');
    const labels={QUEUED:'대기 중',RUNNING:'실행 중',SUCCEEDED:'완료',FAILED:'실패',INTERRUPTED:'중단됨'};
    status.textContent=(job.status==='SUCCEEDED'?'✓ ':'')+(labels[job.status]||job.status)+' · '+job.message+' · '+id.slice(0,10);
    if(['QUEUED','RUNNING'].includes(job.status)){setTimeout(poll,5000);return;}
    lock(false);
   } catch {status.textContent='작업은 접수됐지만 진행 상태를 가져오지 못했습니다. 작업 기록을 확인하세요.';}
  };
  setTimeout(poll,1500);
 });
}

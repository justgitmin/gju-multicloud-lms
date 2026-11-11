'use strict';
const provider=document.querySelector('#provider');
if(provider){const show=()=>{for(const el of document.querySelectorAll('[data-providers]')){el.hidden=!el.dataset.providers.split(' ').includes(provider.value);for(const input of el.querySelectorAll('input'))input.disabled=el.hidden;}};provider.addEventListener('change',()=>{document.querySelector('#region').value={AWS:'ap-northeast-2',NHN:'KR1',NCP:'KR'}[provider.value];show();});show();}
for(const el of document.querySelectorAll('[data-end]')){const now=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul'}).format(new Date());if(el.dataset.end<now){el.classList.add('expired');el.append(' · 종료일 경과');}}
if(document.querySelector('#active-jobs'))setInterval(async()=>{try{const response=await fetch('/api/overview',{cache:'no-store'});if(response.status===401){location.assign('/login');return;}if(!response.ok)return;const data=await response.json();document.querySelector('#active-jobs').textContent=data.jobs.filter(j=>['QUEUED','RUNNING'].includes(j.status)).length;for(const j of data.jobs){const row=document.querySelector(`[data-job="${j.id}"]`);if(row){row.querySelector('.job-status').textContent=j.status;row.querySelector('.job-message').textContent=j.message;}}for(const r of data.resources){const row=document.querySelector(`[data-resource="${r.id}"]`);if(row){row.querySelector('.state').textContent=r.missing?'목록에서 미확인':r.state;row.querySelector('.ip').textContent=r.ip||'주소 없음';}}}catch{}},15000);

// Progressive navigation: without JavaScript the existing anchors/forms still work.
const views=[...document.querySelectorAll('[data-view]')];
if(views.length){
 const panels=[...document.querySelectorAll('[data-vendor-panel]')];
 function route(){
  let raw='overview';try{raw=decodeURIComponent(location.hash.slice(1)||'overview');}catch{}
  const [page,cloud]=raw.split('/');
  const target=document.getElementById(page);
  let view=views.find(v=>v.dataset.view===page);
  let vendor=['AWS','NHN','NCP'].includes(cloud)?cloud:'NHN';
  if(!view&&target){view=target.closest('[data-view]');const panel=target.closest('[data-vendor-panel]');if(panel)vendor=panel.dataset.vendorPanel;}
  if(!view)view=views.find(v=>v.dataset.view==='overview');
  for(const v of views)v.hidden=v!==view;
  const refresh=document.querySelector('.header-actions a');if(refresh)refresh.href=location.pathname+location.search+location.hash;
  for(const p of panels)p.hidden=p.dataset.vendorPanel!==vendor;
  for(const a of document.querySelectorAll('[data-vendor]')){if(a.dataset.vendor===vendor)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');}
  for(const a of document.querySelectorAll('.sidebar nav a')){if(a.getAttribute('href')==='#'+view.dataset.view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');}
  if(['resources','connections'].includes(view.dataset.view))filterCloud(view,['AWS','NHN','NCP'].includes(cloud)?cloud:'all');
  if(target&&target!==view&&target.id!=='overview'){for(let p=target.parentElement;p&&p!==view;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;target.scrollIntoView({block:'start'});}
  else window.scrollTo({top:0});
 }
 function filterCloud(view,cloud){
  const items=[...view.querySelectorAll('[data-cloud-row],[data-cloud-card]')];
  for(const item of items)item.hidden=cloud!=='all'&&(item.dataset.cloudRow||item.dataset.cloudCard)!==cloud;
  for(const b of view.querySelectorAll('[data-cloud-filter]'))b.setAttribute('aria-pressed',String(b.dataset.cloudFilter===cloud));
  const empty=view.querySelector('.filter-empty');if(empty)empty.hidden=items.some(item=>!item.hidden)||cloud==='all';
 }
 for(const b of document.querySelectorAll('[data-cloud-filter]'))b.addEventListener('click',()=>{const view=b.closest('[data-view]');location.hash=view.dataset.view+(b.dataset.cloudFilter==='all'?'':'/'+b.dataset.cloudFilter);});
 window.addEventListener('hashchange',route);route();
}

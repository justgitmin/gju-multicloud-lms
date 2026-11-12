'use strict';
const provider=document.querySelector('#provider');
if(provider){const show=()=>{for(const el of document.querySelectorAll('[data-providers]')){el.hidden=!el.dataset.providers.split(' ').includes(provider.value);for(const input of el.querySelectorAll('input'))input.disabled=el.hidden;}};provider.addEventListener('change',()=>{setRegions();show();});setRegions();show();}
function setRegions(){const region=document.querySelector('#region');if(!region||!provider)return;const options={AWS:[['ap-northeast-2','서울'],['ap-northeast-1','도쿄'],['us-east-1','버지니아'],['us-west-2','오리건']],NHN:[['KR1','판교'],['KR2','평촌'],['JP1','도쿄']],NCP:[['KR','한국'],['JPN','일본']]};region.replaceChildren(...options[provider.value].map(([value,label])=>new Option(label+' ('+value+')',value)));}
for(const el of document.querySelectorAll('[data-end]')){const now=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul'}).format(new Date());if(el.dataset.end<now){el.classList.add('expired');el.append(' · 종료일 경과');}}
if(document.querySelector('#active-jobs'))setInterval(async()=>{try{const response=await fetch('/api/overview',{cache:'no-store'});if(response.status===401){location.assign('/login');return;}if(!response.ok)return;const data=await response.json();document.querySelector('#active-jobs').textContent=data.jobs.filter(j=>['QUEUED','RUNNING'].includes(j.status)).length;for(const j of data.jobs){const row=document.querySelector(`[data-job="${j.id}"]`);if(row){row.querySelector('.job-status').textContent=j.status;row.querySelector('.job-message').textContent=j.message;}}for(const r of data.resources){const row=document.querySelector(`[data-resource="${r.id}"]`);if(row){row.querySelector('.state').textContent=r.missing?'목록에서 미확인':r.state;row.querySelector('.ip').textContent=r.ip||'주소 없음';}}for(const observation of data.observations||[]){const row=document.querySelector(`[data-observation="${observation.id}"]`);if(row&&observation.updated>Number(row.dataset.checkedAt)){const notice=document.querySelector('#resource-new-data');if(notice){notice.hidden=false;notice.querySelector('a').href='/'+location.hash;}}}}catch{}},15000);

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
  const title=document.querySelector('#page-title');if(title)title.textContent={overview:'통합 현황',resources:'자원 관리',events:'교육·해커톤',connections:'클라우드 연결',prepare:'교육 환경 준비',jobs:'작업 기록',users:'계정·권한',audit:'감사 기록',security:'내 계정'}[view.dataset.view]||'운영 콘솔';
  try{sessionStorage.setItem('ops-return','/'+location.hash);}catch{}
  const refresh=document.querySelector('.header-actions a');if(refresh)refresh.href=location.pathname+location.search+location.hash;
  for(const p of panels)p.hidden=p.dataset.vendorPanel!==vendor;
  for(const a of document.querySelectorAll('[data-vendor]')){if(a.dataset.vendor===vendor)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');}
  for(const a of document.querySelectorAll('.sidebar nav a')){if(a.getAttribute('href')==='#'+view.dataset.view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');}
  if(['resources','connections'].includes(view.dataset.view))filterCloud(view,['AWS','NHN','NCP'].includes(cloud)?cloud:'all');
  if(target&&target!==view&&target.id!=='overview'){for(let p=target.parentElement;p&&p!==view;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;target.scrollIntoView({block:'start'});}
  else window.scrollTo({top:0});
  restoreConsoleState();filterResourceRows();
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

function saveConsoleState(){
 if(!document.querySelector('[data-view]'))return;
 try{sessionStorage.setItem('ops-ui:'+location.hash,JSON.stringify({y:scrollY,details:[...document.querySelectorAll('details')].map((d,i)=>d.open?i:-1).filter(i=>i>=0),controls:Object.fromEntries([...document.querySelectorAll('[data-control]')].map(x=>[x.dataset.control,x.value]))}));}catch{}
}
function restoreConsoleState(){
 try{const saved=JSON.parse(sessionStorage.getItem('ops-ui:'+location.hash)||'null');if(!saved)return;const all=[...document.querySelectorAll('details')];for(const i of saved.details||[])if(all[i])all[i].open=true;for(const c of document.querySelectorAll('[data-control]'))if(saved.controls&&Object.hasOwn(saved.controls,c.dataset.control))c.value=saved.controls[c.dataset.control];requestAnimationFrame(()=>window.scrollTo({top:saved.y||0}));}catch{}
}
for(const form of document.querySelectorAll('form[method=post]'))form.addEventListener('submit',()=>{saveConsoleState();let field=form.querySelector('[name="_return"]');if(!field){field=document.createElement('input');field.type='hidden';field.name='_return';form.append(field);}field.value='/'+(location.hash||'#overview');});
for(const a of document.querySelectorAll('.sidebar a,.vendor-nav a'))a.addEventListener('click',saveConsoleState);
window.addEventListener('pagehide',saveConsoleState);
for(const a of document.querySelectorAll('[data-return-link]')){if(a.getAttribute('href')==='/#overview'){try{const path=sessionStorage.getItem('ops-return');if(/^\/#[A-Za-z0-9_/-]+$/.test(path||''))a.href=path;}catch{}}}
function filterResourceRows(){
 const root=document.querySelector('#resources');if(!root)return;
 const cloud=root.querySelector('[data-cloud-filter][aria-pressed=true]')?.dataset.cloudFilter||'all';
 const kind=root.querySelector('[data-resource-kind]')?.value||'all',event=root.querySelector('[data-resource-event]')?.value||'all',search=(root.querySelector('[data-resource-search]')?.value||'').trim().toLowerCase();
 for(const row of root.querySelectorAll('[data-selection-row]')){
  row.hidden=(cloud!=='all'&&row.dataset.cloudRow!==cloud)||(kind!=='all'&&(kind==='related'?['server','database','container'].includes(row.dataset.kind):row.dataset.kind!==kind))||(event!=='all'&&row.dataset.event!==event)||!(row.dataset.search||'').toLowerCase().includes(search);
  const input=row.querySelector('[data-resource-select]');if(row.hidden&&input)input.checked=false;
 }
 updateSelection();
}
function updateSelection(){
 const action=document.querySelector('[data-resource-action]')?.value||'STOP';
 const selected=[];
 for(const row of document.querySelectorAll('[data-selection-row]')){
  const input=row.querySelector('[data-resource-select]');if(!input)continue;
  input.disabled=row.hidden||!row.dataset.actions.split(',').includes(action);
  if(input.disabled)input.checked=false;
  if(input.checked)selected.push(input.dataset.name);
 }
 const count=document.querySelector('#selected-count');if(count)count.textContent=String(selected.length);
 const review=document.querySelector('#selection-review');if(review)review.textContent=selected.length?selected.join(' · '):'한 개를 선택하면 개별 작업, 여러 개를 선택하면 일괄 작업입니다.';
 const deletion=document.querySelector('[data-delete-fields]');if(deletion){deletion.hidden=action!=='DELETE';for(const input of deletion.querySelectorAll('input')){input.disabled=deletion.hidden;input.required=!deletion.hidden;}}
 const all=document.querySelector('[data-select-visible]');if(all){const eligible=[...document.querySelectorAll('[data-resource-select]:not(:disabled)')];all.checked=eligible.length>0&&eligible.every(i=>i.checked);all.indeterminate=eligible.some(i=>i.checked)&&!all.checked;}
}
for(const control of document.querySelectorAll('[data-resource-kind],[data-resource-event],[data-resource-search]'))control.addEventListener('input',()=>{filterResourceRows();saveConsoleState();});
document.querySelector('[data-resource-action]')?.addEventListener('change',updateSelection);
for(const input of document.querySelectorAll('[data-resource-select]'))input.addEventListener('change',updateSelection);
document.querySelector('[data-select-visible]')?.addEventListener('change',event=>{for(const input of document.querySelectorAll('[data-resource-select]:not(:disabled)'))input.checked=event.target.checked;updateSelection();});
filterResourceRows();

for(const button of document.querySelectorAll('[data-aws-course-profile]'))button.addEventListener('click',()=>{const form=button.closest('form');for(const [name,value] of Object.entries({lab_id:'gju-mc-2026-aws',count:'14',instance:'t3.micro',volume:'20'}))form.elements.namedItem(name).value=value;form.elements.namedItem('s3').checked=true;form.elements.namedItem('rds').checked=true;});

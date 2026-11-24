import {PortalHeader,PortalFooter} from '../../components/PortalChrome';
import ReviewForm from './ReviewForm';import {requireAdmin} from '../../../lib/auth';import {db} from '../../../lib/db';import {results} from '../../../lib/results';
export const dynamic='force-dynamic';
export default async function Learning({searchParams}:{searchParams:Promise<{error?:string;reviewed?:string}>}){await requireAdmin();const {error,reviewed}=await searchParams;const enrollments=await db.enrollment.findMany({where:{status:'APPROVED'},include:{user:{select:{name:true,studentNumber:true}},course:{select:{title:true}}},take:200,orderBy:{id:'desc'}});const summaries=await Promise.all(enrollments.map(e=>results(e.id)));const submissions=await db.submission.findMany({include:{lab:true,file:{select:{name:true}},enrollment:{include:{user:{select:{id:true,name:true,studentNumber:true}},course:{select:{title:true}}}}},orderBy:[{updatedAt:'desc'},{id:'desc'}]});
const groups=new Map<string,typeof submissions>();
for(const submission of submissions){
 const id=submission.enrollment.user.id;
 const group=groups.get(id);
 if(group)group.push(submission);else groups.set(id,[submission]);
}
const collator=new Intl.Collator('ko-KR',{numeric:true});
const students=[...groups.entries()].sort(([aId,[a]],[bId,[b]])=>collator.compare(a.enrollment.user.name,b.enrollment.user.name)||collator.compare(a.enrollment.user.studentNumber??'',b.enrollment.user.studentNumber??'')||aId.localeCompare(bId));
return <><PortalHeader active="learning"/><main id="portal-content" className="portal-main"><section className="classhero"><h1>학습·실습 관리</h1><p>현재 버전의 영상·실습·평가 결과로 온라인 기준 충족 여부를 계산합니다.</p></section><div className="tablewrap"><table><thead><tr><th>학생</th><th>과정</th><th>영상</th><th>실습</th><th>평가</th><th>온라인 기준</th></tr></thead><tbody>{enrollments.map((e,i)=>{const r=summaries[i];return <tr key={e.id}><td>{e.user.name}<br/>{e.user.studentNumber}</td><td>{e.course.title}</td><td>{r.completedLessons}/{r.lessons}</td><td>{r.approvedLabs}/{r.labs}</td><td>{r.passedQuizzes}/{r.quizzes}</td><td>{r.complete?'충족':'미충족'}</td></tr>;})}</tbody></table></div><h2>실습 검토 · 학생 {students.length}명</h2><p>제출한 실습의 검토 상태입니다. 학생 이름을 펼치면 제출 내용과 검토 버튼을 볼 수 있습니다.</p>{error&&<p className="error">보완 요청 피드백 또는 제출물 변경 여부를 확인하세요. 새로고침 후 다시 검토해 주세요.</p>}{students.length===0&&<p>아직 제출된 실습이 없습니다.</p>}{students.map(([id,items])=>{
 const {name,studentNumber}=items[0].enrollment.user;
 const approved=items.filter(s=>s.status==='APPROVED').length;
 const pending=items.filter(s=>s.status==='PENDING').length;
 const revision=items.filter(s=>s.status==='REVISION').length;
 const allPassed=approved===items.length;
 return <details key={id} className="card quiz" open={items.some(s=>s.id===reviewed)||undefined}>
 <summary style={{cursor:'pointer',padding:'8px 0'}}><strong>{name}</strong> {studentNumber&&<span>({studentNumber})</span>}{' '}
 <strong style={{color:allPassed?'#166534':'#92400e'}}>{allPassed?'전체 통과':approved>0?'일부 통과':revision>0?'미통과':'검토 대기'}</strong>
 {' · '}통과 {approved}/{items.length}{pending>0&&` · 검토 대기 ${pending}건`}{revision>0&&` · 보완 요청 ${revision}건`}
 </summary>
 {items.map(s=><article id={`submission-${s.id}`} key={s.id} className="card quiz" style={{scrollMarginTop:100}}><h3>{s.enrollment.course.title} · {s.lab.title}</h3>{reviewed===s.id&&<p role="status" style={{background:"#e8f5ed",padding:12,color:"#14532d"}}>검토 결과가 저장되었습니다. 현재 상태: {{PENDING:"검토 대기",APPROVED:"통과",REVISION:"보완 요청"}[s.status]}</p>}<p>상태: {{PENDING:'검토 대기',APPROVED:'통과',REVISION:'보완 요청'}[s.status]} · 최종 변경 {s.updatedAt.toLocaleString("ko-KR",{timeZone:"Asia/Seoul"})} KST</p><p className="preline">{s.content}</p>{s.file&&<p><a href={`/api/submission-files/${s.id}`}>첨부 내려받기 · {s.file.name}</a></p>}{s.url&&<a href={s.url} target="_blank" rel="noopener noreferrer">제출 증빙 확인 ↗</a>}<ReviewForm submissionId={s.id} updatedAt={s.updatedAt.toISOString()} status={s.status} feedback={s.feedback??''}/></article>)}</details>})}</main><PortalFooter/></>}

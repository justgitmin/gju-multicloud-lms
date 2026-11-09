import Link from 'next/link';
import {PortalHeader,PortalFooter} from '../components/PortalChrome';
import {requireUser} from '../../lib/auth';
import {db} from '../../lib/db';
import {results} from '../../lib/results';
import {updateProfile} from './actions';
export const dynamic='force-dynamic';
export default async function MyPage({searchParams}:{searchParams:Promise<{saved?:string,error?:string}>}){
 const user=await requireUser();const query=await searchParams;
 const enrollments=await db.enrollment.findMany({where:{userId:user.id},include:{course:{select:{title:true,published:true}}},orderBy:{id:'desc'}});
 const courses=await Promise.all(enrollments.map(async e=>({...e,summary:e.status==='APPROVED'?await results(e.id):null})));
 return <><PortalHeader active="mypage"/><main id="portal-content" className="portal-main"><section className="classhero"><div className="eyebrow">MY ACCOUNT</div><h1>마이페이지</h1><p>내 정보와 학습 현황을 한곳에서 확인하세요.</p></section>{query.saved&&<p role="status">이름이 저장되었습니다.</p>}{query.error&&<p role="alert" className="error">{query.error}</p>}
 <div className="cards"><section className="card"><h2>내 정보</h2><dl className="lab-details"><dt>이메일</dt><dd>{user.email}</dd><dt>학번·학생 번호</dt><dd>{user.studentNumber??'미등록'}</dd><dt>계정 구분</dt><dd>{user.role==='ADMIN'?'관리자':'학생'}</dd></dl><p>이메일과 학번 수정은 운영자에게 문의하세요. AWS 로그인 계정은 LMS 계정과 별개입니다.</p><form action={updateProfile} className="assessmentform"><label>이름<input name="name" autoComplete="name" required minLength={2} maxLength={60} defaultValue={user.name}/></label><button className="button">이름 저장</button></form></section>
 <section className="card"><h2>계정 보안</h2><p>현재 비밀번호를 확인한 후 새 비밀번호로 변경할 수 있습니다. 변경하면 모든 기기에서 로그아웃됩니다.</p><Link className="button" href="/mypage/password">비밀번호 변경 →</Link></section></div>
 <h2>나의 수강 현황</h2>{courses.map(e=><section className="card" key={e.id}><h3>{e.course.title}</h3><span className="status">{{APPROVED:'수강 승인',PENDING:'승인 대기',REJECTED:'신청 반려'}[e.status]}</span>{e.summary&&<><p>영상 {e.summary.completedLessons}/{e.summary.lessons} · 실습 {e.summary.approvedLabs}/{e.summary.labs} · 퀴즈 {e.summary.passedQuizzes}/{e.summary.quizzes}</p><p>{e.summary.complete?'온라인 학습 기준 충족':'학습 진행 중'}</p>{e.course.published&&<Link className="smallbutton" href={`/course/${e.courseId}`}>학습·실습·평가 →</Link>}</>}</section>)}{!courses.length&&<p>신청한 과정이 없습니다. 내 강의실에서 수강신청을 해주세요.</p>}<Link className="button" href="/classroom">내 강의실 →</Link></main><PortalFooter/></>;
}

import {PortalHeader,PortalFooter} from '../components/PortalChrome';
import {requireUser} from '../../lib/auth';
import {db} from '../../lib/db';
import {enroll} from '../actions';
import Journey from './Journey';
export const dynamic='force-dynamic';
const statuses={PENDING:'승인 대기',APPROVED:'수강 승인',REJECTED:'신청 반려 · 운영자 문의'};
export default async function Classroom({searchParams}:{searchParams:Promise<{error?:string}>}){
 const user=await requireUser();const {error}=await searchParams;
 const courses=await db.course.findMany({where:{published:true},include:{enrollments:{where:{userId:user.id},include:{progress:true,submissions:{select:{labId:true,status:true}},attempts:{select:{quizId:true,version:true,score:true}}}},lessons:{orderBy:{position:'asc'}},labs:{select:{id:true}},quizzes:{select:{id:true,version:true}}},orderBy:{title:'asc'}});
 return <><PortalHeader active="classroom"/><main id="portal-content" className="portal-main"><section className="classhero"><div className="eyebrow">MY CLASSROOM</div><h1>한 걸음씩, 함께 성장해요.</h1><p>{user.name}님의 학습 여정과 다음 도전을 확인하세요.</p></section>{error&&<p role="alert" className="error">{error}</p>}
 {courses.map(course=>{const application=course.enrollments[0];return application?.status==='APPROVED'?<Journey key={course.id} course={course} enrollment={application}/>:<article className="card" key={course.id}><div className="eyebrow">MULTI-CLOUD PROGRAM</div><h3>{course.title}</h3>{application?<div className="status">{statuses[application.status]}</div>:<><p>신청 후 운영자가 확인하면 수강 권한이 부여됩니다.</p><form action={enroll}><input type="hidden" name="courseId" value={course.id}/><button className="button">수강신청 →</button></form></>}</article>})}
 {courses.length===0&&<aside>현재 신청 가능한 과정이 없습니다.</aside>}</main><PortalFooter/></>;
}

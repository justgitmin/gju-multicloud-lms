import Link from 'next/link';
import {submissionCourses} from '../../lib/submission-courses';
import {PortalHeader,PortalFooter} from '../components/PortalChrome';
import {requireUser} from '../../lib/auth';
import {db} from '../../lib/db';
import Journey from './Journey';
export const dynamic='force-dynamic';
const statuses={PENDING:'승인 대기',APPROVED:'수강 승인',REJECTED:'신청 반려 · 운영자 문의'};
export default async function Classroom({searchParams}:{searchParams:Promise<{error?:string}>}){
 const user=await requireUser();const {error}=await searchParams;
 const courses=await db.course.findMany({where:user.role==='ADMIN'?{}:{published:true},include:{enrollments:{where:{userId:user.id},include:{progress:true,submissions:{select:{labId:true,status:true}},attempts:{select:{quizId:true,version:true,score:true}}}},lessons:{orderBy:{position:'asc'}},labs:{select:{id:true}},quizzes:{select:{id:true,version:true}}},orderBy:{title:'asc'}});
 return <><PortalHeader active="classroom"/><main id="portal-content" className="portal-main"><section className="classhero"><div className="eyebrow">MY CLASSROOM</div><h1>한 걸음씩, 함께 성장해요.</h1><p>{user.name}님의 학습 여정과 다음 도전을 확인하세요.</p></section>{error&&<p role="alert" className="error">{error}</p>}
 {courses.filter(course=>user.role==='ADMIN'||course.enrollments[0]?.status==='APPROVED').map(course=>{
 const application=course.enrollments[0];
 if(user.role==='ADMIN')return <article className="card" key={course.id}><h2>{course.title}</h2><Link className="button" href={`/course/${course.id}`}>과정 미리보기 →</Link></article>;
 if(submissionCourses.has(course.id))return <article className="card" key={course.id}><h2>{course.title}</h2><Link className="button" href={`/course/${course.id}`}>강의·교안·산출물 →</Link></article>;
 return <Journey key={course.id} course={course} enrollment={application}/>;
 })}
 {!courses.some(course=>user.role==='ADMIN'||course.enrollments[0]?.status==='APPROVED')&&<aside>아직 배정된 과정이 없습니다. 관리자가 수강 명단을 확인한 후 배정합니다.</aside>}</main><PortalFooter/></>;
}

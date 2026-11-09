import {PortalHeader,PortalFooter} from '../../components/PortalChrome';
import {requireAdmin} from '../../../lib/auth';
import {db} from '../../../lib/db';
import ResetPassword from './ResetPassword';
export const dynamic='force-dynamic';
export default async function Users({searchParams}:{searchParams:Promise<{q?:string}>}){
 await requireAdmin();const {q=''}=await searchParams;const search=q.trim().slice(0,100);
 const users=await db.user.findMany({where:{role:'STUDENT',...(search?{OR:[{name:{contains:search,mode:'insensitive'}},{email:{contains:search,mode:'insensitive'}},{studentNumber:{contains:search,mode:'insensitive'}}]}:{})},select:{id:true,name:true,email:true,studentNumber:true,mustChangePassword:true,temporaryPasswordExpiresAt:true},orderBy:{createdAt:'desc'},take:100});
 return <><PortalHeader active="users"/><main id="portal-content" className="portal-main"><section className="classhero"><div className="eyebrow">STUDENT ACCOUNTS</div><h1>학생 계정 관리</h1><p>수강신청 전 학생도 검색할 수 있습니다. 학생 본인 확인 후 임시 비밀번호를 개별 전달하세요. AWS 비밀번호에는 영향을 주지 않습니다.</p></section><form method="get" className="assessmentform"><label>이름·이메일·학번 검색<input type="search" name="q" defaultValue={search} maxLength={100}/></label><button className="smallbutton">검색</button></form><p>최근 가입 순 최대 100명 표시</p><div className="tablewrap"><table><thead><tr><th>학생</th><th>이메일</th><th>비밀번호 상태</th><th>처리</th></tr></thead><tbody>{users.map(u=><tr key={u.id}><td><b>{u.name}</b><br/>{u.studentNumber}</td><td>{u.email}</td><td>{u.mustChangePassword?(u.temporaryPasswordExpiresAt&&u.temporaryPasswordExpiresAt>new Date()?'임시 비밀번호 · 변경 필요':'임시 비밀번호 만료 · 재발급 필요'):'본인 비밀번호 사용'}</td><td><ResetPassword id={u.id} name={u.name} email={u.email}/></td></tr>)}</tbody></table>{!users.length&&<p>검색 결과가 없습니다.</p>}</div></main><PortalFooter/></>;
}

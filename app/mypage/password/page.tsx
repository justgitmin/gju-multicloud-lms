import Link from 'next/link';
import {PortalHeader,PortalFooter} from '../../components/PortalChrome';
import {requireUser} from '../../../lib/auth';
import {changePassword} from '../actions';
export const dynamic='force-dynamic';
export default async function PasswordPage({searchParams}:{searchParams:Promise<{error?:string}>}){
 const user=await requireUser({allowPasswordChange:true});const {error}=await searchParams;
 return <><PortalHeader/><main id="portal-content" className="account"><section className="panel"><div className="eyebrow">ACCOUNT SECURITY</div><h1>{user.mustChangePassword?'새 비밀번호를 설정하세요':'비밀번호 변경'}</h1><p>{user.mustChangePassword?'운영자가 발급한 임시 비밀번호로 로그인했습니다. 학습을 시작하기 전에 본인만 아는 비밀번호로 변경하세요.':'변경 후 모든 기기에서 로그아웃됩니다. 새 비밀번호로 다시 로그인해 주세요.'}</p>{error&&<p role="alert" className="error">{error}</p>}<form action={changePassword}><label>{user.mustChangePassword?'임시 비밀번호':'현재 비밀번호'}<input type="password" name="currentPassword" autoComplete="current-password" required maxLength={128}/></label><label>새 비밀번호 · 12~128자<input type="password" name="password" autoComplete="new-password" required minLength={12} maxLength={128}/></label><label>새 비밀번호 확인<input type="password" name="confirmation" autoComplete="new-password" required minLength={12} maxLength={128}/></label><button className="button">변경하고 다시 로그인 →</button></form>{!user.mustChangePassword&&<p><Link href="/mypage">마이페이지로 돌아가기</Link></p>}</section></main><PortalFooter/></>;
}

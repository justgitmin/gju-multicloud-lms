import Link from 'next/link';
import {requireUser} from '../../../lib/auth';
import {db} from '../../../lib/db';
import {httpsLabReady} from '../../../lib/lab-http';
import {labLinks,type LabPublic} from '../../../lib/lab-secrets.mjs';
import {PortalHeader,PortalFooter} from '../../components/PortalChrome';
import LabPanel from './LabPanel';
export const dynamic='force-dynamic';
export default async function LabPage({searchParams}:{searchParams:Promise<{course?:string}>}){
 const user=await requireUser();const {course}=await searchParams;
 const row=await db.labAccess.findFirst({where:{active:true,enrollment:{userId:user.id,courseId:course??'',status:'APPROVED',course:{published:true}}}});
 const ready=httpsLabReady();const info=row?.publicData as LabPublic|undefined;const links=info?labLinks(info):null;
 return <><PortalHeader active="classroom"/><main id="portal-content" className="portal-main"><section className="classhero"><div className="eyebrow">MY AWS LAB</div><h1>내 AWS 실습 환경</h1><p>{user.name}님에게 배정된 실습 환경입니다. 다른 학생에게 접속 정보를 공유하지 마세요.</p><Link className="smallbutton" href="/classroom">내 강의실</Link></section>{!ready?<aside>HTTPS 및 접속 정보 보호 설정을 준비 중입니다. 현재는 비밀번호를 제공하지 않습니다.</aside>:!info||!links?<aside>아직 배정된 환경이 없거나 열람이 중지되었습니다. 수강 승인 후 운영자에게 배정을 요청하세요.</aside>:<><section className="card"><h2>{info.labId} · {info.studentCode}</h2><dl className="lab-details"><dt>IAM 사용자명</dt><dd>{info.username}</dd><dt>AWS 계정 / 리전</dt><dd>{info.accountId} / 서울</dd><dt>본인 서버</dt><dd>{info.instanceId}</dd><dt>세션 문서</dt><dd>{info.sessionDocument}</dd>{info.dbEndpoint&&<><dt>본인 DB 주소</dt><dd>{info.dbEndpoint}<br/>DB 이름: labdb · 사용자: labadmin</dd></>}</dl><div className="lab-links"><a className="button" href={links.login} target="_blank" rel="noopener noreferrer">AWS 로그인 →</a><a className="button" href={links.session} target="_blank" rel="noopener noreferrer">브라우저 터미널 →</a>{links.s3&&<a className="smallbutton" href={links.s3} target="_blank" rel="noopener noreferrer">본인 S3 열기</a>}</div><p>학생 IAM 사용자로 AWS에 먼저 로그인하세요. Session Manager에서 본인 서버와 위 세션 문서를 선택합니다. 로그인이나 문서 선택은 AWS 화면에서 진행하며 이 버튼이 자동 로그인하지는 않습니다.</p><Link href="/guide/aws" style={{textDecoration:'underline'}}>AWS 실습 따라 하기 →</Link></section><LabPanel courseId={course??''} info={info}/></>}</main><PortalFooter/></>;
}

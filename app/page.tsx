import Link from 'next/link';
import {currentUser} from '../lib/auth';
import {logout} from './actions';
import s from './home.module.css';

const photos={classroom:'https://images.unsplash.com/photo-1524178232363-1fb2b075b655?auto=format&fit=crop&w=1600&q=85'};
const courses = [
  {title: '멀티클라우드 운영', label: '온라인 학습', description: 'NHN Cloud와 AWS에서 네트워크, 서버, 스토리지와 데이터베이스를 구성하고 운영합니다.'},
  {title: '클라우드 네이티브', label: '컴퓨터공학과', description: 'NHN Cloud 본사 방문과 강의 내용을 바탕으로 클라우드 인프라를 구성하고 실습 결과를 정리합니다.'},
  {title: '디지털트윈', label: '기계자동차학과', description: 'NHN Cloud에서 디지털트윈 실습에 활용할 서버와 네트워크를 구성하고 결과를 정리합니다.'},
  {title: 'MLOps', label: '모델 학습·운영', description: '모델을 학습하고 성능을 비교한 뒤, 모델 선정 근거와 실험 기록을 정리합니다.'},
];
const notices=[{title:'온라인 학습관 이용 안내',body:'내 강의실에서 승인된 과정에 입장하세요. 영상 학습 위치와 이수 기록을 저장하여 이어서 학습할 수 있습니다.'},{title:'수강신청 및 승인 절차 안내',body:'계정으로 로그인한 뒤 내 강의실에서 수강신청하세요. 운영자가 승인하면 영상 학습과 실습·평가를 이용할 수 있습니다. 계정 발급과 로그인 문제는 교육 운영자에게 문의해 주세요.'},{title:'실습 전 계정과 비용을 확인해 주세요',body:'실습에 사용할 클라우드 계정과 권한을 확인하세요. 실습 종료 후 인스턴스·DB·디스크·IP 등 과금 자원이 남아 있는지 점검해 주세요.'}];
export default async function Home(){const user=await currentUser({allowPasswordChange:true});return <div className={s.home}>
<a className={s.skip} href="#content">본문 바로가기</a>
<div className={s.utility}><div className={s.wrap}><span>광주대학교 인공지능 부트캠프</span><div className={s.sessionControls}>{user?<><span className={s.sessionName}>{user.name}님</span><Link href={user.mustChangePassword?'/mypage/password':'/mypage'}>마이페이지</Link><form action={logout}><button type="submit">로그아웃</button></form></>:<Link href="/login">로그인 →</Link>}</div></div></div>
<header className={s.header}><div className={s.wrap}><Link className={s.logo} href="/" aria-label="GJU Cloud Campus 홈">GJU <span>CLOUD CAMPUS</span></Link><nav aria-label="주 메뉴"><a href="#about">과정 소개</a><a href="#courses">교육과정</a><a href="#guide">학습 안내</a><a href="#notices">공지사항</a></nav><Link className={s.primary} href="/classroom">내 강의실 <span aria-hidden="true">↗</span></Link></div></header>
<main className={s.main} id="content">
<section id="about" className={s.hero}><div className={s.heroCopy}><div className={s.kicker}>GJU CLOUD CAMPUS</div><h1>광주대학교<br/>클라우드·AI 실습 포털</h1><p>교육과정을 확인하고 내 강의실에서 학습과 실습 산출물 제출을 진행하세요.</p><div className={s.actions}><a className={s.primary} href="#courses">교육과정 보기 <span aria-hidden="true">→</span></a><a className={s.textLink} href="#guide">학습 방법 안내</a></div></div><figure className={s.heroPhoto}><img src={photos.classroom} alt="교육장에서 함께 학습하는 수강생들의 모습 — 교육 환경 예시 이미지" fetchPriority="high"/><figcaption>배움에서 실무로, GJU CLOUD CAMPUS <small>교육 환경 예시 이미지</small></figcaption></figure></section>
<div className={s.facts}><dl className={s.wrap}>{[['교육과정','4개 과정'],['실습 환경','NHN Cloud · AWS'],['학습 활동','과정별 학습 · 실습 제출'],['수강 절차','신청 후 운영자 승인']].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></div>
<div className={s.wrap}>
<section id="courses" className={s.courses}><div className={s.heading}><div><h2>교육과정</h2><span>COURSES</span></div><Link className={s.textLink} href="/classroom">내 강의실로 이동 →</Link></div>
<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%, 260px),1fr))',gap:16}}>
  {courses.map(course => <article className={s.courseBody} key={course.title} style={{border:'1px solid #d9e3df',borderRadius:16,background:'#fff',padding:24}}>
    <p className={s.meta}>{course.label}</p>
    <h3>{course.title}</h3>
    <p>{course.description}</p>
  </article>)}
</div></section>
<div className={s.bottom}><section id="notices" className={s.notices}><div className={s.heading}><div><h2>공지사항</h2></div><span className={s.minor}>학습관 이용 안내</span></div>{notices.map((n,i)=><details key={n.title}><summary><span>안내 0{i+1}</span><strong>{n.title}</strong><b aria-hidden="true">+</b></summary><p>{n.body}</p></details>)}</section><section id="guide" className={s.guide}><h2>처음 이용하시나요?</h2><p>학습을 시작하는 절차를 안내해 드립니다.</p><ol>{[['로그인','운영 안내에 따라 계정을 준비해 주세요.'],['수강신청','내 강의실에서 과정을 신청하세요.'],['승인 후 학습','승인된 과정에 들어가 학습 안내를 확인하고 실습 산출물을 제출하세요.']].map(([title,body],i)=><li key={title}><span>0{i+1}</span><div><b>{title}</b><p>{body}</p></div></li>)}</ol><details><summary>멀티클라우드 과정 온라인 이수 기준</summary><p>영상별 95% 이상 시청하면 영상 이수로 인정됩니다. 각 클라우드의 영상 8개를 이수하면 해당 복습 퀴즈가 열립니다. 필수 실습 전체 통과와 평가별 70점 이상이 온라인 학습 수료 기준입니다. 학교 공식 수료 판정은 별도입니다.</p></details><Link className={s.textLink} href="/classroom">내 강의실로 이동 →</Link></section></div>
</div></main><footer className={s.footer}><div className={s.wrap}><div><b>광주대학교</b><span>인공지능 부트캠프 · 클라우드·AI 실습 포털</span></div><nav aria-label="하단 메뉴"><a href="#courses">교육과정</a><a href="#guide">학습 안내</a><Link href="/classroom">내 강의실</Link></nav><small>GJU CLOUD CAMPUS</small></div></footer></div>}

import './globals.css';
import AuthHistoryRefresh from './components/AuthHistoryRefresh';
export const metadata = { title: '광주대학교 | 멀티클라우드 캠퍼스', description: 'AWS·NHN Cloud 멀티클라우드 운영 학습 플랫폼' };
export default function Layout({children}:{children:React.ReactNode}) { return <html lang="ko"><body><AuthHistoryRefresh/>{children}</body></html>; }

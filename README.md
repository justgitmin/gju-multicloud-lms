# gju-multicloud-lms
광주대학교 AWS·NHN Cloud 멀티클라우드 온라인 학습 플랫폼.

## 현재 상태
기본 Next.js 앱, 과정 안내, AWS·NHN 커리큘럼, Prisma 데이터 모델, Docker Compose 골격과 DB 백업 스크립트가 준비되어 있습니다.
**로그인·진도 저장·영상·퀴즈는 아직 제공하지 않습니다. 운영용 LMS로 공개하지 마세요.**

## 로컬 실행
Node.js 24 사용.
```bash
npm ci
npm run dev
```

## 검증
```bash
npm run db:generate
npm run typecheck
npm run build
```

## 서버 준비
`.env.example`을 `.env`로 복사하고 고유한 DB 비밀번호와 DATABASE_URL을 설정합니다. DB 비밀번호의 URL 예약문자는 URL 인코딩해야 합니다. DB 포트는 외부 공개하지 않습니다.
현재 Docker Compose는 기본 구조 검증용입니다. HTTPS·인증·마이그레이션·복구 검증 후 운영 배포 절차를 제공합니다.

## 문서
- [구현 계획](docs/IMPLEMENTATION.md)
- [자체 영상 제작](docs/VIDEO_PRODUCTION.md)

실제 환경변수·학생 정보·영상 원본·백업 파일은 커밋하지 않습니다.

BEGIN;
CREATE TABLE "SubmissionFile" (
    "submissionId" TEXT PRIMARY KEY REFERENCES "Submission"("id") ON DELETE CASCADE ON UPDATE CASCADE,
    "name" TEXT NOT NULL,
    "data" BYTEA NOT NULL
);
INSERT INTO "Course" ("id","title","published") VALUES
('gju-cloud-native-2026','클라우드 네이티브',true),
('gju-digital-twin-2026','디지털트윈',true),
('gju-mlops-2026','MLOps',true)
ON CONFLICT ("id") DO NOTHING;
INSERT INTO "Lab" ("id","courseId","title","instructions","position") VALUES
('gju-cloud-native-2026-artifact','gju-cloud-native-2026','NHN Cloud 인프라 구축 실습','네트워크·서버·보안 그룹 구성과 서버 접속 확인 화면을 PDF로 정리하세요. 구성과 확인 결과를 설명하세요.',1),
('gju-digital-twin-2026-artifact','gju-digital-twin-2026','NHN Cloud 디지털트윈 실습 환경 구축','서버·네트워크 생성과 접속 확인 화면을 PDF로 정리하고, 해당 구성을 디지털트윈에서 어떻게 활용할지 설명하세요.',1),
('gju-mlops-2026-artifact','gju-mlops-2026','모델 학습·비교 및 선정 실습','실행한 노트북, 모델 비교 결과, 최종 모델 선정 이유와 실험 기록을 제출하세요. 여러 파일은 ZIP 하나로 묶어 제출하세요.',1)
ON CONFLICT ("id") DO NOTHING;
COMMIT;

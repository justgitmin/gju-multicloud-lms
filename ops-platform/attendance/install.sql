BEGIN;
SET LOCAL lock_timeout='3s';
CREATE TABLE IF NOT EXISTS "LmsAccessEvidence" (
 id bigserial PRIMARY KEY,
 "userId" text NOT NULL REFERENCES "User"(id),
 kind text NOT NULL CHECK(kind IN ('LOGIN','LEARNING_ACTIVITY','MANUAL_ATTENDANCE')),
 "eventAt" timestamptz NOT NULL,
 "recordedAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 "evidenceKey" text NOT NULL UNIQUE,
 "registeredBy" text,
 note text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS lms_access_evidence_user_time ON "LmsAccessEvidence"("userId","eventAt");
CREATE OR REPLACE FUNCTION lms_record_login() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM "User" WHERE id=NEW."userId" AND role='STUDENT') THEN
  INSERT INTO "LmsAccessEvidence"("userId",kind,"eventAt","evidenceKey",note)
  VALUES(NEW."userId",'LOGIN',clock_timestamp(),'login:'||NEW.id,'인증 세션 생성 시 서버에서 기록한 실제 로그인 시각') ON CONFLICT DO NOTHING;
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS lms_login_evidence ON "Session";
CREATE TRIGGER lms_login_evidence AFTER INSERT ON "Session" FOR EACH ROW EXECUTE FUNCTION lms_record_login();
CREATE OR REPLACE FUNCTION lms_record_learning() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE learner text; seen_at timestamptz;
BEGIN
 SELECT e."userId" INTO learner FROM "Enrollment" e JOIN "User" u ON u.id=e."userId" WHERE e.id=NEW."enrollmentId" AND u.role='STUDENT';
 IF learner IS NOT NULL THEN
  seen_at=clock_timestamp();
  INSERT INTO "LmsAccessEvidence"("userId",kind,"eventAt","evidenceKey",note)
  VALUES(learner,'LEARNING_ACTIVITY',seen_at,'learning:'||learner||':'||to_char(seen_at AT TIME ZONE 'Asia/Seoul','YYYY-MM-DD HH24:MI'),'서버에 도달한 영상 학습 요청. 분 단위 중복 제거; 시청 완료·체류 시간 증명과는 구분') ON CONFLICT DO NOTHING;
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS lms_learning_evidence ON "Playback";
CREATE TRIGGER lms_learning_evidence AFTER INSERT OR UPDATE ON "Playback" FOR EACH ROW EXECUTE FUNCTION lms_record_learning();
COMMIT;

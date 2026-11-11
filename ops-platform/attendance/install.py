"""Run on the LMS host. Add evidence capture and a dedicated read-only viewer role.
Never prints credentials. Takes a live DB backup first; never restarts LMS or Ops.
"""
import datetime,json,os,secrets,subprocess
from pathlib import Path
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[2]
os.chdir(ROOT)
def run(args,**kw):return subprocess.run(args,check=True,text=True,capture_output=True,**kw).stdout
compose=['docker','compose','-f','compose.yaml','-f','compose.prod.yaml']
def sql(text):return run(compose+['exec','-T','db','sh','-c','exec psql -X -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At'],input=text)
# Backups and evidence exports are server-private and excluded from git.
run(['bash','scripts/backup.sh'])
source=Path(__file__).with_name('install.sql').read_text()
sql(source)
# Only the 14-person batch roster is used; it never enters source control.
rosters=run(['docker','exec','tbit-cloud-ops-ops-1','python','-c',"import sqlite3,json;d=sqlite3.connect('/data/ops.sqlite3');print(json.dumps([json.loads(x[0]).get('roster',{}) for x in d.execute('SELECT config FROM nhn_bootstrap')]))"])
people={v['name'] for roster in json.loads(rosters) for v in roster.values()}
if not people:raise RuntimeError('No saved student roster; no attendance was backfilled.')
# Explicit operator instruction: 2026-11-11 17:30 KST. This is manual attribution,
# not a fabricated login event. Snapshot requires same-day valid session or learning.
start='2026-11-11T17:30:00+09:00'
quoted=','.join("'"+x.replace("'","''")+"'" for x in sorted(people))
candidates=f'''SELECT json_build_object('userId',u.id,'name',u.name,'email',u.email,
 'sessionSeen',EXISTS(SELECT 1 FROM "Session" s WHERE s."userId"=u.id AND s."passwordVersion"=u."passwordVersion" AND s."expiresAt">now() AND s."expiresAt"-interval '7 days'>='2026-11-11T00:00:00+09:00'::timestamptz),
 'learningAt',(SELECT max(p."lastAt") FROM "Playback" p JOIN "Enrollment" e ON e.id=p."enrollmentId" WHERE e."userId"=u.id))::text
 FROM "User" u WHERE u.role='STUDENT' AND u.name IN ({quoted})
 AND (SELECT count(*) FROM "User" x WHERE x.name=u.name AND x.role='STUDENT')=1
 AND (EXISTS(SELECT 1 FROM "Session" s WHERE s."userId"=u.id AND s."passwordVersion"=u."passwordVersion" AND s."expiresAt">now() AND s."expiresAt"-interval '7 days'>='2026-11-11T00:00:00+09:00'::timestamptz)
 OR EXISTS(SELECT 1 FROM "Playback" p JOIN "Enrollment" e ON e.id=p."enrollmentId" WHERE e."userId"=u.id AND p."lastAt">='{start}'::timestamptz))'''
snapshot=[json.loads(x) for x in sql(candidates).splitlines() if x.strip()]
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
backup=ROOT/'backups'/'attendance-manual-20261111.json'
# Preserve the original snapshot on reruns; never expand attendance silently.
if backup.exists():snapshot=json.loads(backup.read_text())['students']
else:
 backup.write_text(json.dumps({'capturedAt':now,'attendanceAt':start,'requestedBy':'sm@tbit.co.kr','source':'사용자 요청에 따른 17:30 수동 출석 등록. 당일 유효 로그인 세션 또는 수업 시작 후 학습 기록 확인. 실제 로그인 시각 아님.','students':snapshot},ensure_ascii=False,indent=2));backup.chmod(0o600)
for student in snapshot:
 uid=student['userId'].replace("'","''")
 note='운영자 요청으로 수업 시작 17:30에 수동 출석 등록. 등록 당시 당일 로그인 세션 또는 학습 기록 확인. 실제 로그인 시각을 소급한 것이 아님. 근거 스냅샷 attendance-manual-20261111.json 보관.'
 sql(f'''INSERT INTO "LmsAccessEvidence"("userId",kind,"eventAt","evidenceKey","registeredBy",note) VALUES('{uid}','MANUAL_ATTENDANCE','{start}','manual:2026-11-11:{uid}','sm@tbit.co.kr','{note}') ON CONFLICT DO NOTHING;''')
# A dedicated SELECT-only role is used by the viewer. Generate or preserve its secret.
envfile=ROOT/'ops-platform'/'attendance.env'
if not envfile.exists():
 password=secrets.token_hex(32)
 dbid=run(compose+['ps','-q','db']).strip()
 config=json.loads(run(['docker','inspect',dbid]))[0]
 env=dict(x.split('=',1) for x in config['Config']['Env'] if '=' in x)
 dbname=env.get('POSTGRES_DB','lms')
 sql("DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='lms_attendance') THEN CREATE ROLE lms_attendance LOGIN; END IF; END $$; ALTER ROLE lms_attendance PASSWORD '"+password+"'; ALTER ROLE lms_attendance SET default_transaction_read_only=on; GRANT CONNECT ON DATABASE \""+dbname.replace('"','""')+"\" TO lms_attendance; GRANT USAGE ON SCHEMA public TO lms_attendance; GRANT SELECT ON \"User\",\"LmsAccessEvidence\" TO lms_attendance;")
 envfile.write_text('ATTENDANCE_DATABASE_URL=postgresql://lms_attendance:'+password+'@db:5432/'+quote(dbname,safe='')+'\n');envfile.chmod(0o600)
print('ATTENDANCE_INSTALLED: actual future login/activity capture enabled; manual 17:30 records='+str(len(snapshot)))
print('MANUAL_NAMES: '+', '.join(x['name'] for x in snapshot))

"""Deploy only the attendance viewer and gracefully reload Caddy routing."""
import datetime,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];os.chdir(ROOT)
def run(args,**kw):return subprocess.run(args,check=True,text=True,**kw)
run(['python3','ops-platform/attendance/install.py'])
run(['docker','compose','-f','ops-platform/compose.attendance.yaml','--project-directory','ops-platform','up','-d','--build','attendance'])
# Confirm health before changing the proxy. No LMS or Ops containers are recreated.
for attempt in range(30):
 check=subprocess.run(['docker','exec','tbit-cloud-ops-attendance-1','python','-c',"import urllib.request;urllib.request.urlopen('http://127.0.0.1:8781/health')"],capture_output=True)
 if check.returncode==0:break
 time.sleep(1)
else:raise RuntimeError('Attendance viewer not ready; existing proxy preserved.')
p=ROOT/'Caddyfile';old=p.read_text();needle='reverse_proxy tbit-cloud-ops-ops-1:8780'
new='''handle /attendance* {
        reverse_proxy tbit-cloud-ops-attendance-1:8781
    }
    handle {
        reverse_proxy tbit-cloud-ops-ops-1:8780
    }'''
if 'reverse_proxy tbit-cloud-ops-attendance-1:8781' not in old:
 if old.count(needle)!=1:raise RuntimeError('Unexpected proxy config; existing file preserved.')
 backup=ROOT/'backups'/('Caddyfile-attendance-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.write_text(old)
 p.write_text(old.replace(needle,new))
 try:
  run(['docker','compose','-f','compose.yaml','-f','compose.prod.yaml','exec','-T','caddy','caddy','validate','--config','/etc/caddy/Caddyfile','--adapter','caddyfile'])
  run(['docker','compose','-f','compose.yaml','-f','compose.prod.yaml','exec','-T','caddy','caddy','reload','--config','/etc/caddy/Caddyfile','--adapter','caddyfile'])
 except BaseException:p.write_text(old);raise
print('ATTENDANCE_READY https://ops.tbitcloud.com/attendance; LMS and Ops worker were not restarted.')

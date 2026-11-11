"""Generate a private environment file without putting secrets in shell history."""
import base64,os,secrets
from pathlib import Path
from urllib.parse import urlparse
os.umask(0o077);path=Path(__file__).parent/'.env'
if path.exists():raise SystemExit('.env가 이미 있습니다. 기존 암호화 키를 덮어쓰지 않습니다.')
origin=input('관리자 서비스 HTTPS 주소 (예: https://ops.example.com): ').strip().rstrip('/');u=urlparse(origin)
if u.scheme!='https' or not u.hostname or u.path or u.query or u.fragment or u.username or u.password:raise SystemExit('HTTPS 도메인 주소만 입력하세요.')
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:f.write('OPS_ORIGIN='+origin+'\nOPS_MASTER_KEY='+base64.b64encode(secrets.token_bytes(32)).decode()+'\nOPS_DEV=0\n')
print('서버 설정을 생성했습니다. 암호화 키는 출력하지 않았습니다. .env를 별도로 안전하게 백업하세요.')

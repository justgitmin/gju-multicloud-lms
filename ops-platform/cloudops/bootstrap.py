import getpass,os,re
from pathlib import Path
from .store import Store
from .security import Vault,password_hash

def main():
 os.umask(0o077);Vault(os.environ.get('OPS_MASTER_KEY',''));db=Store(Path(os.environ.get('OPS_DATA_DIR','/data'))/'ops.sqlite3')
 if db.one("SELECT id FROM users WHERE active=1 AND role='ADMIN'"):raise SystemExit('관리자가 이미 있습니다. 웹 화면에서 계정을 추가하세요.')
 email=input('관리자 이메일: ').strip().lower()
 if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise SystemExit('이메일 형식 확인')
 password=getpass.getpass('관리자 비밀번호 (12~128자): ')
 if password!=getpass.getpass('비밀번호 재입력: '):raise SystemExit('비밀번호 불일치')
 db.execute("INSERT INTO users(email,name,password,role) VALUES(?,?,?,'ADMIN')",(email,'관리자',password_hash(password)));db.audit(email,'BOOTSTRAP');print('관리자 준비 완료. 비밀번호는 해시로만 저장했습니다.')
if __name__=='__main__':main()

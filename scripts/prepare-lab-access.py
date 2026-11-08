#!/usr/bin/env python3
"""Prepare encrypted lab storage without DNS, HTTPS or Caddy changes."""
import argparse
from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import secrets
import shutil

spec=importlib.util.spec_from_file_location('https_settings',Path(__file__).with_name('configure-https.py'))
settings=importlib.util.module_from_spec(spec);spec.loader.exec_module(settings)


def prepare(root,apply=False):
    root=Path(root);env=root/'.env'
    if not env.exists():raise ValueError('LMS 서버의 .env가 필요합니다.')
    original=env.read_text();key,created=settings.existing_key(original)
    if not apply:return {'created':created,'applied':False}
    if not created:return {'created':False,'applied':False}
    folder=root/'backups'/('lab-storage-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+secrets.token_hex(3))
    folder.mkdir(parents=True,mode=0o700)
    shutil.copyfile(env,folder/'env.before');os.chmod(folder/'env.before',0o600)
    text=settings.update_env(original,{'LAB_CREDENTIALS_KEY':key})
    temporary=env.with_name('.env.lab-prepare-tmp')
    fd=os.open(temporary,os.O_CREAT|os.O_WRONLY|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(text)
    os.replace(temporary,env);os.chmod(env,0o600)
    shutil.copyfile(env,folder/'env.after');os.chmod(folder/'env.after',0o600)
    return {'created':True,'applied':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');args=p.parse_args()
    result=prepare(Path(__file__).resolve().parents[1],args.apply)
    if result['applied']:print('암호화 키 준비 완료. 키는 화면에 출력하지 않습니다. .env 백업은 backups/에 보관합니다.')
    elif not result['created']:print('기존 암호화 키 확인 완료. 값을 변경하지 않았습니다.')
    else:print('암호화 키 생성이 필요합니다. --apply를 추가하면 .env에 저장합니다.')
    print('APP_ORIGIN·SITE_ADDRESS·Caddyfile은 변경하지 않았습니다. DNS/인증서 작업은 실행하지 않습니다.')
    print('서버 반영은 DB 백업 → web/tools 빌드 → db:migrate → web 재생성 순서로 진행하세요.')
    print('현재 HTTP 상태에서는 학생 비밀번호 조회·배정 전송이 계속 차단됩니다.')


if __name__=='__main__':
    try:main()
    except Exception as e:raise SystemExit(str(e))

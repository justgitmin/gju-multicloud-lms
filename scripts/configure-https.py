#!/usr/bin/env python3
"""Prepare Caddy/.env for public HTTPS. No DNS/account changes or Docker deployment."""
import argparse
import base64
from datetime import datetime, timezone
import ipaddress
import os
from pathlib import Path
import re
import secrets
import shutil
import socket


def domain_name(value):
    value=value.strip().lower().encode('idna').decode('ascii')
    if len(value)>253 or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',value):
        raise ValueError('도메인 이름만 입력하세요. http://, 경로, 포트, IP 주소는 사용할 수 없습니다.')
    return value


def update_env(text,values):
    lines=text.splitlines();out=[];seen=set()
    for line in lines:
        match=re.match(r'^\s*([A-Z_][A-Z0-9_]*)\s*=',line)
        if match and match[1] in values:
            if match[1] not in seen:out.append(match[1]+'='+values[match[1]]);seen.add(match[1])
        else:out.append(line)
    for key,value in values.items():
        if key not in seen:out.append(key+'='+value)
    return '\n'.join(out)+'\n'


def existing_key(text):
    matches=re.findall(r'^\s*LAB_CREDENTIALS_KEY\s*=\s*(.*?)\s*$',text,re.M)
    keys=[m.strip().strip('"\'') for m in matches if m.strip().strip('"\'')]
    if not keys:return base64.b64encode(secrets.token_bytes(32)).decode(),True
    if len(set(keys))!=1:raise ValueError('중복된 암호화 키 값이 다릅니다. 자동 변경하지 않습니다.')
    try:decoded=base64.b64decode(keys[0],validate=True)
    except Exception:raise ValueError('기존 암호화 키 형식을 확인하세요. 자동 교체하지 않습니다.') from None
    if len(decoded)!=32:raise ValueError('기존 암호화 키 길이를 확인하세요. 자동 교체하지 않습니다.')
    return keys[0],False


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--domain',required=True);p.add_argument('--public-ip',required=True);p.add_argument('--apply',action='store_true');args=p.parse_args()
    domain=domain_name(args.domain);ip=ipaddress.IPv4Address(args.public_ip)
    root=Path(__file__).resolve().parents[1];env=root/'.env'
    if not env.exists():raise ValueError('서버 저장소에 .env가 필요합니다.')
    print('HTTPS 도메인:',domain);print('예상 A 레코드:',str(ip));print('변경 예정: APP_ORIGIN, SITE_ADDRESS, 암호화 키(없을 때만 생성), Caddyfile')
    try:addresses=socket.getaddrinfo(domain,None,type=socket.SOCK_STREAM)
    except socket.gaierror:raise ValueError('DNS에서 도메인을 찾지 못했습니다. 먼저 A 레코드를 서버 공인 IP로 연결하세요.') from None
    ipv4={a[4][0] for a in addresses if a[0]==socket.AF_INET};ipv6={a[4][0] for a in addresses if a[0]==socket.AF_INET6}
    if ipv4!={str(ip)}:raise ValueError('DNS A 레코드가 예상 서버 IP와 다릅니다. DNS 설정과 전파 상태를 확인하세요.')
    if ipv6:raise ValueError('AAAA 레코드가 있습니다. 서버 IPv6 연결을 별도로 검증하거나 불필요한 AAAA를 제거하세요.')
    original=env.read_text();key,created=existing_key(original)
    if not args.apply:
        print('검사 완료. 아직 파일을 변경하지 않았습니다. 실제 적용하려면 --apply를 추가하세요.');return
    backup=root/'backups'/('https-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+secrets.token_hex(3))
    backup.mkdir(parents=True,mode=0o700);shutil.copyfile(env,backup/'env.before');os.chmod(backup/'env.before',0o600)
    caddy=root/'Caddyfile'
    if caddy.exists():shutil.copyfile(caddy,backup/'Caddyfile.before')
    new=update_env(original,{'APP_ORIGIN':'https://'+domain,'SITE_ADDRESS':domain,'LAB_CREDENTIALS_KEY':key})
    temp=env.with_name('.env.https-tmp');fd=os.open(temp,os.O_CREAT|os.O_WRONLY|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(new)
    os.replace(temp,env);os.chmod(env,0o600)
    shutil.copyfile(env,backup/'env.after');os.chmod(backup/'env.after',0o600)
    caddy.write_text('{$SITE_ADDRESS} {\n    encode zstd gzip\n    reverse_proxy web:3000\n}\n')
    print('설정 저장 완료. 암호화 키:', '신규 생성(화면에 출력하지 않음)' if created else '기존 키 유지')
    print('백업 폴더:',backup)
    print('아직 Docker를 재배포하지 않았습니다. 운영 안내의 빌드·마이그레이션·재생성 순서로 적용하세요.')
    print('기존/신규 .env와 DB 백업은 운영자 전용으로 보관하세요. 키를 잃으면 저장된 비밀번호를 복구할 수 없습니다.')


if __name__=='__main__':
    try:main()
    except Exception as e:raise SystemExit(str(e))

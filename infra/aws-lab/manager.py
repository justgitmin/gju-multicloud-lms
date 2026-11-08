#!/usr/bin/env python3
"""Local operator GUI. Python standard library + authenticated AWS CLI v2 only."""
import argparse
import concurrent.futures
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import webbrowser

import lab

HERE = Path(__file__).resolve().parent
ALLOWED_KEYS = {'lab_id','region','students','instance_type','volume_gb','s3','rds','db_class','ami_parameter','access_mode'}


class Manager:
    def __init__(self, root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.configs=self.root/'configs';self.configs.mkdir(exist_ok=True,mode=0o700)
        self.state=self.root/'state';self.state.mkdir(exist_ok=True,mode=0o700)
        self.token=secrets.token_urlsafe(32)
        self.lock=threading.Lock();self.job={'running':False,'logs':[],'exit_code':None}
        self.process=None
    def path(self,name):
        if not isinstance(name,str) or not re.fullmatch(r'[a-z][a-z0-9-]{2,24}',name):raise ValueError('환경 이름은 영문 소문자로 시작하는 3~25자 영문·숫자·하이픈입니다.')
        return self.configs/(name+'.json')
    def save(self,raw):
        c={k:v for k,v in raw.items() if k in ALLOWED_KEYS}
        if c.get('access_mode')!='ssm':raise ValueError('GUI는 IP 등록 없는 Session Manager 방식을 사용합니다.')
        # Validate in a temporary file outside the retained config before atomic replacement.
        name=c.get('lab_id');path=self.path(name);tmp=path.with_suffix('.pending')
        try:
            tmp.write_text(json.dumps(c,indent=2),encoding='utf-8');os.chmod(tmp,0o600)
            lab.load_config(tmp,True)
            tmp.replace(path)
        finally:tmp.unlink(missing_ok=True)
        return c
    def read(self,name):return lab.load_config(self.path(name))
    def config_list(self):
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(self.configs.glob('*.json'))]
    def cli_env(self,profile=''):
        if not isinstance(profile,str) or len(profile)>100 or '\x00' in profile:raise ValueError('잘못된 AWS 프로필 이름')
        env=os.environ.copy();env['PYTHONUNBUFFERED']='1';env['PYTHONIOENCODING']='utf-8';env['AWS_PAGER']=''
        if profile:env['AWS_PROFILE']=profile
        return env
    def identity(self,profile=''):
        run=subprocess.run(['aws','--region','ap-northeast-2','sts','get-caller-identity','--output','json','--no-cli-pager'],capture_output=True,text=True,encoding='utf-8',errors='replace',env=self.cli_env(profile),timeout=30)
        if run.returncode:raise ValueError(run.stderr.strip() or 'AWS 인증 확인 실패')
        d=json.loads(run.stdout);return {'account':d['Account'],'arn':d['Arn']}
    def start(self,action,name,students,profile,account,confirm):
        if action not in ['apply','status','destroy']:raise ValueError('지원하지 않는 작업')
        c=self.read(name)
        if not isinstance(students,list) or not students or len(students)!=len(set(students)) or any(x not in c['students'] for x in students):raise ValueError('설정에 있는 학생을 선택하세요.')
        if action in ['apply','destroy']:
            if confirm != name:raise ValueError('확인란에 환경 이름을 정확히 입력하세요.')
            if not re.fullmatch(r'\d{12}',account or ''):raise ValueError('AWS 계정을 먼저 확인하세요.')
            if self.identity(profile)['account'] != account:raise ValueError('AWS 계정이 바뀌었습니다. 다시 확인하세요.')
        with self.lock:
            if self.job['running']:raise ValueError('다른 작업이 진행 중입니다.')
            selected=dict(c,students=students)
            # GUI never overwrites existing credentials; new courses use a new environment name.
            if action=='apply' and any((self.state/(name+'-'+s)).exists() for s in students):raise ValueError('기존 학생 자료가 있습니다. 새 학생만 선택하거나 새 환경 이름을 사용하세요. 상태를 확인하지 않고 파일을 지우지 마세요.')
            snapshot=self.root/'active-operation.json';snapshot.write_text(json.dumps(selected),encoding='utf-8');os.chmod(snapshot,0o600)
            args=[sys.executable,'-u',str(HERE/'lab.py'),action,'--config',str(snapshot),'--state',str(self.state)]
            if action in ['apply','destroy']:args+=['--confirm-account',account]
            self.job={'running':True,'action':action,'environment':name,'students':students,'logs':[],'exit_code':None,'started':datetime.now(timezone.utc).isoformat()}
            try:self.process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=self.cli_env(profile))
            except Exception:
                self.job['running']=False;raise
            threading.Thread(target=self.collect,daemon=True).start()
        return self.job_state()
    def collect(self):
        process=self.process
        for line in process.stdout:
            with self.lock:self.job['logs']=(self.job['logs']+[line.rstrip()])[-1500:]
        code=process.wait()
        with self.lock:self.job.update(running=False,exit_code=code)
    def job_state(self):
        with self.lock:return json.loads(json.dumps(self.job))
    def kit(self,name,student):
        c=self.read(name)
        if student not in c['students']:raise ValueError('알 수 없는 학생')
        folder=self.state/(name+'-'+student)
        credentials=json.loads((folder/'credentials.json').read_text(encoding='utf-8'))
        outputs=json.loads((folder/'outputs.json').read_text(encoding='utf-8'))
        # Explicit action only; never list passwords in dashboard/status/logs.
        lines=['학생 개인 접속 안내 — 본인만 보관',f"환경: {name} / 학생: {student}",f"콘솔: {outputs['LoginUrl']}",f"사용자: {outputs['Username']}",f"초기 비밀번호: {credentials['initial_password']}",'첫 로그인 시 비밀번호를 변경하세요. 변경 후 초기 비밀번호는 사용할 수 없습니다.',f"서버 ID: {outputs['InstanceId']}",f"세션 문서: {outputs.get('SessionDocument','')}",f"브라우저 접속: {outputs.get('SessionConsoleUrl','')}",'Session Manager → 세션 시작 → 본인 서버 → 위 세션 문서 선택. SSH 키/집 IP 등록 불필요.']
        if outputs.get('S3ConsoleUrl'):lines.append('S3 직접 링크: '+outputs['S3ConsoleUrl'])
        if outputs.get('DbEndpoint'):lines += ['DB 주소: '+outputs['DbEndpoint'],'DB 이름: labdb','DB 사용자: '+credentials['db_user'],'DB 비밀번호: '+credentials['db_password']]
        lines+=['서버 IP는 중지/시작 후 바뀔 수 있습니다. AWS 콘솔에서 현재 값을 확인하세요.','다른 학생에게 공유하거나 공개 게시하지 마세요.']
        return {'filename':name+'-'+student+'-private.txt','content':'\n'.join(lines)}


def make_handler(manager):
    class Handler(BaseHTTPRequestHandler):
        server_version='LabManager'
        def log_message(self,*args):pass
        def allowed_host(self):return self.headers.get('Host') in [f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}']
        def reply(self,status,data,content_type='application/json; charset=utf-8'):
            body=data.encode('utf-8') if isinstance(data,str) else json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers();self.wfile.write(body)
        def do_GET(self):
            if not self.allowed_host():return self.reply(403,{'error':'로컬 접속만 허용됩니다.'})
            if self.path=='/':
                html=(HERE/'manager.html').read_text(encoding='utf-8').replace('__CSRF__',manager.token)
                return self.reply(200,html,'text/html; charset=utf-8')
            return self.reply(404,{'error':'Not found'})
        def do_POST(self):
            if not self.allowed_host() or not secrets.compare_digest(self.headers.get('X-Lab-Token',''),manager.token):return self.reply(403,{'error':'인증되지 않은 로컬 요청'})
            origin=self.headers.get('Origin')
            if origin and origin not in [f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}']:return self.reply(403,{'error':'외부 출처 요청 차단'})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply(415,{'error':'JSON required'})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if n<0 or n>40000:raise ValueError('요청 크기 초과')
                d=json.loads(self.rfile.read(n))
                if self.path=='/api/init':out={'configs':manager.config_list(),'default':json.loads((HERE/'config.example.json').read_text()),'aws_installed':bool(shutil.which('aws')),'storage':str(manager.root)}
                elif self.path=='/api/save':out=manager.save(d['config'])
                elif self.path=='/api/identity':out=manager.identity(d.get('profile',''))
                elif self.path=='/api/job':out=manager.job_state()
                elif self.path=='/api/start':out=manager.start(d['action'],d['name'],d['students'],d.get('profile',''),d.get('account',''),d.get('confirm',''))
                elif self.path=='/api/kit':out=manager.kit(d['name'],d['student'])
                else:return self.reply(404,{'error':'Not found'})
                self.reply(200,out)
            except Exception as e:self.reply(400,{'error':str(e)})
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8765);parser.add_argument('--data-dir',default=str(Path.home()/'.gju-lab-manager'));parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    manager=Manager(args.data_dir)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(manager))
    url=f'http://127.0.0.1:{server.server_port}'
    print('운영자 GUI:',url,flush=True);print('작업 중에는 이 창을 닫지 마세요. 종료: Ctrl+C',flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()

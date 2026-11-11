import contextlib,json,os,sqlite3,time
from pathlib import Path
SCHEMA='''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('ADMIN','OPERATOR','VIEWER')),active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),csrf TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS attempts(key TEXT PRIMARY KEY,count INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS connections(id TEXT PRIMARY KEY,name TEXT NOT NULL,provider TEXT NOT NULL,region TEXT NOT NULL,account TEXT NOT NULL,secret TEXT NOT NULL,writable INTEGER NOT NULL DEFAULT 0,revision INTEGER NOT NULL DEFAULT 1,last_sync REAL,error TEXT);
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,name TEXT NOT NULL,ends TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS resources(id TEXT PRIMARY KEY,connection_id TEXT NOT NULL REFERENCES connections(id),remote_id TEXT NOT NULL,name TEXT NOT NULL,state TEXT NOT NULL,ip TEXT NOT NULL,flavor TEXT NOT NULL,event_id TEXT REFERENCES events(id),owner TEXT NOT NULL DEFAULT '',seen REAL NOT NULL,missing INTEGER NOT NULL DEFAULT 0,UNIQUE(connection_id,remote_id));
CREATE TABLE IF NOT EXISTS environments(id TEXT PRIMARY KEY,connection_id TEXT NOT NULL REFERENCES connections(id),event_id TEXT NOT NULL REFERENCES events(id),lab_id TEXT NOT NULL UNIQUE,config TEXT NOT NULL,state TEXT NOT NULL DEFAULT '',created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,actor INTEGER NOT NULL REFERENCES users(id),connection_id TEXT REFERENCES connections(id),revision INTEGER,kind TEXT NOT NULL,target TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,updated REAL NOT NULL,message TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_job_per_connection ON jobs(connection_id) WHERE status IN ('QUEUED','RUNNING');
CREATE TABLE IF NOT EXISTS nhn_batches(id TEXT PRIMARY KEY,connection_id TEXT NOT NULL REFERENCES connections(id),event_id TEXT NOT NULL REFERENCES events(id),name TEXT NOT NULL,config TEXT NOT NULL,secret TEXT NOT NULL,state TEXT NOT NULL DEFAULT '',planned REAL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS nhn_items(batch_id TEXT NOT NULL REFERENCES nhn_batches(id),student TEXT NOT NULL,summary TEXT NOT NULL,status TEXT NOT NULL,message TEXT NOT NULL,updated REAL NOT NULL,PRIMARY KEY(batch_id,student));
CREATE UNIQUE INDEX IF NOT EXISTS one_nhn_batch_scope ON nhn_batches(connection_id,name);
CREATE TABLE IF NOT EXISTS audits(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,event TEXT NOT NULL,target TEXT NOT NULL,result TEXT NOT NULL,created REAL NOT NULL);
'''
class Store:
 def __init__(self,path):
  self.path=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  with self.connect() as db:db.executescript(SCHEMA);db.execute('PRAGMA journal_mode=WAL')
  os.chmod(path,0o600)
 @contextlib.contextmanager
 def connect(self):
  db=sqlite3.connect(self.path,timeout=20);db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA busy_timeout=20000')
  try:yield db;db.commit()
  except BaseException:db.rollback();raise
  finally:db.close()
 def all(self,sql,args=()):
  with self.connect() as db:return [dict(r) for r in db.execute(sql,args).fetchall()]
 def one(self,sql,args=()):
  rows=self.all(sql,args);return rows[0] if rows else None
 def execute(self,sql,args=()):
  with self.connect() as db:return db.execute(sql,args).rowcount
 def audit(self,actor,event,target='',result='OK'):
  self.execute('INSERT INTO audits(actor,event,target,result,created) VALUES(?,?,?,?,?)',(str(actor),event,str(target),result,time.time()))
 def rate(self,key,limit):
  key=f'{key}:{int(time.time()//900)}'
  with self.connect() as db:
   db.execute('INSERT INTO attempts VALUES(?,1) ON CONFLICT(key) DO UPDATE SET count=count+1',(key,))
   return db.execute('SELECT count FROM attempts WHERE key=?',(key,)).fetchone()[0]<=limit

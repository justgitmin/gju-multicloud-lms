"""Consistent SQLite snapshot. Back up the master key separately, not in this file."""
import os,sqlite3,datetime
from pathlib import Path
os.umask(0o077);target=Path('/data/backups');target.mkdir(exist_ok=True,mode=0o700);file=target/('ops-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.sqlite3')
with sqlite3.connect('/data/ops.sqlite3') as source,sqlite3.connect(file) as destination:source.backup(destination)
file.chmod(0o600);print('BACKUP_OK',file.name)

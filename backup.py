"""Use PostgreSQL pg_dump to make a consistent SQL backup."""
import datetime,os,shutil,subprocess
from pathlib import Path
import config
settings=config.load(prompt=True)
executable=shutil.which('pg_dump')
if not executable:
    candidates=sorted(Path('C:/Program Files/PostgreSQL').glob('*/bin/pg_dump.exe'),reverse=True)
    executable=str(candidates[0]) if candidates else None
if not executable:raise SystemExit('pg_dump not found. Use pgAdmin: right-click relief360 → Backup, or add PostgreSQL bin to PATH.')
folder=config.ROOT/'backups';folder.mkdir(exist_ok=True)
path=folder/('relief360-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.sql')
env=os.environ.copy()
if 'password' in settings:env['PGPASSWORD']=settings['password']
subprocess.run([executable,'--host',settings['host'],'--port',str(settings['port']),'--username',settings['user'],'--dbname',settings['dbname'],'--file',str(path),'--no-owner','--no-privileges'],env=env,check=True)
print('Backup created:',path)

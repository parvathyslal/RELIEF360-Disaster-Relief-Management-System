"""Read local PostgreSQL settings without putting passwords in source code."""
import os,json,getpass
from pathlib import Path
ROOT=Path(__file__).parent
FILE=ROOT/'db_config.json'
def load(prompt=False):
    values=json.loads(FILE.read_text()) if FILE.exists() else {}
    settings={key:os.environ.get(env,values.get(key,default)) for key,env,default in [('host','PGHOST','localhost'),('port','PGPORT',5432),('dbname','PGDATABASE','relief360'),('user','PGUSER','postgres')]}
    settings['port']=int(settings['port']);settings['connect_timeout']=10
    password=os.environ.get('PGPASSWORD')
    if password is None and prompt:password=getpass.getpass('PostgreSQL password (the password for your postgres server user): ')
    if password is not None:settings['password']=password
    return settings

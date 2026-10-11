"""Initialize RELIEF360 tables in the user's existing PostgreSQL database."""
import getpass,json
import config,store,psycopg

def main():
    settings=config.load()
    print('RELIEF360 PostgreSQL setup — your existing database will be kept.')
    for key,label in [('host','Server host'),('port','Server port'),('dbname','Database name'),('user','PostgreSQL username')]:
        entered=input(f'{label} [{settings[key]}]: ').strip()
        if entered:settings[key]=int(entered) if key=='port' else entered
    settings['password']=getpass.getpass('PostgreSQL password (not saved to a file): ')
    try:
        store.initialize(settings)
        saved={k:settings[k] for k in ['host','port','dbname','user']}
        config.FILE.write_text(json.dumps(saved,indent=2)+'\n')
        print('Connected successfully. Tables and demonstration accounts are ready.')
        print('In pgAdmin: relief360 → Schemas → public → Tables. Right-click Tables → Refresh.')
        print('Next: run START_WINDOWS.bat or python server.py.')
    except psycopg.Error as error:
        print('Setup failed:',error)
        print('Check your server password and PostgreSQL connection settings. No database was dropped.')
        raise SystemExit(1)
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Local RELIEF360 server. Run: python server.py"""
import argparse, csv, io, json, os, secrets, psycopg, time, threading
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import urlsplit,parse_qs
from pathlib import Path
import store,config
SESSIONS={};FAILURES={};LOCK=threading.Lock()
def rollback_safely(db):
    try:db.rollback()
    except psycopg.Error:db.close()  # A broken connection cannot be reused; closing also aborts its transaction.

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(store.ROOT),**kw)
    def log_message(self,fmt,*args):pass
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','same-origin');super().end_headers()
    def send_json(self,data,status=200,headers=None):
        body=json.dumps(data,default=str).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(body)
    def session(self):
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:return None
        token=cookie.get('relief360_session');token=token.value if token else None
        with LOCK:
            s=SESSIONS.get(token)
            if s and s['expires']>time.time():return s
            if token:SESSIONS.pop(token,None)
        return None
    def body(self):
        try:n=int(self.headers.get('Content-Length','0'))
        except ValueError:raise store.Invalid('Invalid request length')
        if not 0<n<=100000:raise store.Invalid('Invalid request size')
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise store.Invalid('JSON content type required')
        try:p=json.loads(self.rfile.read(n))
        except (ValueError,UnicodeDecodeError):raise store.Invalid('Invalid JSON')
        if not isinstance(p,dict):raise store.Invalid('JSON object required')
        return p
    def do_GET(self):
        path=urlsplit(self.path).path
        if path.startswith('/api/'):return self.api('GET')
        # Only serve explicit public assets/pages; DB, source, tests and backups never exposed.
        allowed={p.name for p in store.ROOT.glob('*.html')}
        if path=='/':path='/index.html'
        public=path=='/login.html' or path.startswith('/css/') or path.startswith('/js/')
        if path.lstrip('/') not in allowed and not path.startswith(('/css/','/js/')):return self.send_error(404)
        if '..' in path or '%' in path:return self.send_error(404)
        if not public and not self.session():
            self.send_response(302);self.send_header('Location','/login.html');self.end_headers();return
        self.path=path;super().do_GET()
    def do_HEAD(self):self.send_error(405)
    def do_POST(self):self.api('POST')
    def api(self,method):
        try:db=store.connect(self.server.db_path)
        except psycopg.Error:return self.send_json({'error':'PostgreSQL is unavailable. Check that the database server is running.'},503)
        try:
            path=urlsplit(self.path).path;parts=path.strip('/').split('/');s=self.session()
            if method=='POST':
                origin=self.headers.get('Origin')
                if origin and origin!='http://'+self.headers.get('Host',''):return self.send_json({'error':'Invalid request origin'},403)
                p=self.body()
            if path=='/api/login' and method=='POST':
                email=store.text(p,'email').lower();password=store.text(p,'password');key=(self.client_address[0],email)
                with LOCK:
                    attempts=[t for t in FAILURES.get(key,[]) if time.time()-t<300]
                    FAILURES[key]=attempts
                    if len(attempts)>=10:return self.send_json({'error':'Too many attempts. Try again in five minutes.'},429)
                user=db.execute("SELECT * FROM USER_ACCOUNT WHERE lower(email)=lower(%s) AND status='Active'",(email,)).fetchone()
                if not user or not store.password_ok(password,user['password_hash']):
                    with LOCK:FAILURES[key].append(time.time())
                    return self.send_json({'error':'Incorrect email or password'},401)
                token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
                with LOCK:SESSIONS[token]={'user_id':user['user_id'],'csrf':csrf,'expires':time.time()+8*3600};FAILURES.pop(key,None)
                return self.send_json({'ok':True},headers={'Set-Cookie':'relief360_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'})
            if not s:return self.send_json({'error':'Please sign in'},401)
            user=db.execute('SELECT user_id,name,email,role,status FROM USER_ACCOUNT WHERE user_id=%s',(s['user_id'],)).fetchone()
            if not user or user['status']!='Active':return self.send_json({'error':'Account inactive'},401)
            user=dict(user)
            if method=='POST' and not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),s['csrf']):return self.send_json({'error':'Invalid session token. Reload the page.'},403)
            if path=='/api/me' and method=='GET':return self.send_json(dict(user=user,csrf=s['csrf'],permissions=[m for m,roles in store.WRITERS.items() if user['role'] in roles]))
            if path=='/api/logout' and method=='POST':
                with LOCK:
                    for key,value in list(SESSIONS.items()):
                        if value is s:del SESSIONS[key]
                return self.send_json({'ok':True},headers={'Set-Cookie':'relief360_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
            if path=='/api/users':
                if user['role']!='admin':return self.send_json({'error':'Administrator access required'},403)
                if method=='GET':return self.send_json(store.rows(db,'SELECT user_id,name,email,role,phone,status FROM USER_ACCOUNT ORDER BY user_id'))
                email=store.text(p,'email').lower();password=store.text(p,'password')
                if '@' not in email:raise store.Invalid('Enter a valid email')
                if not 10<=len(password)<=128:raise store.Invalid('Password must have 10–128 characters')
                role=store.choice(p,'role',['admin','ngo','medical','volunteer'])
                id=store.insert(db,'USER_ACCOUNT',dict(name=store.text(p,'name'),email=email,password_hash=store.password_hash(password),role=role,phone=store.text(p,'phone',False)))
                db.commit();return self.send_json({'ok':True,'id':id},201)
            if path=='/api/password' and method=='POST':
                pw=store.text(p,'new_password');old=store.text(p,'old_password');record=db.execute('SELECT password_hash FROM USER_ACCOUNT WHERE user_id=%s',(user['user_id'],)).fetchone()
                if not store.password_ok(old,record[0]):raise store.Invalid('Current password is incorrect')
                if not 10<=len(pw)<=128:raise store.Invalid('Password must have 10–128 characters')
                db.execute('UPDATE USER_ACCOUNT SET password_hash=%s WHERE user_id=%s',(store.password_hash(pw),user['user_id']));db.commit();return self.send_json({'ok':True})
            if method=='GET':
                if path=='/api/lookups':return self.send_json(store.lookups(db))
                if path=='/api/dashboard':return self.send_json(store.dashboard(db))
                if path=='/api/reports':return self.send_json(store.reports(db))
                if len(parts)==2 and parts[1] in store.QUERIES:return self.send_json(store.listing(db,parts[1]))
                if len(parts)==4 and parts[3]=='history':return self.send_json(store.history(db,parts[1],int(parts[2])))
                if path=='/api/export':
                    name=parse_qs(urlsplit(self.path).query).get('report',['occupancy'])[0];r=store.reports(db)
                    if name not in r:raise store.Invalid('Unknown report')
                    out=io.StringIO();data=r[name]
                    if data:
                        writer=csv.DictWriter(out,fieldnames=list(data[0]));writer.writeheader()
                        for row in data:writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for k,v in row.items()})
                    body=out.getvalue().encode();self.send_response(200);self.send_header('Content-Type','text/csv; charset=utf-8');self.send_header('Content-Disposition','attachment; filename='+name+'.csv');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
            elif len(parts)>=2 and parts[1] in store.WRITERS:
                module=parts[1]
                if user['role'] not in store.WRITERS[module]:return self.send_json({'error':'Your role cannot modify this module'},403)
                db.execute("SELECT pg_advisory_xact_lock(3602026)")
                if len(parts)==2:id=store.create(db,module,p,user)
                elif len(parts)==4:id=store.action(db,module,int(parts[2]),parts[3],p,user)
                else:raise store.Invalid('Unknown operation')
                db.commit();return self.send_json({'ok':True,'id':id},201)
            self.send_json({'error':'Not found'},404)
        except (store.Invalid,ValueError,TypeError) as e:rollback_safely(db);self.send_json({'error':str(e)},400)
        except psycopg.IntegrityError as e:
            rollback_safely(db);message='This record conflicts with an existing record or relationship.'
            if 'one_active' in str(e) or 'VEHICLE_ALLOCATION.vehicle_id' in str(e):message='Vehicle is already allocated.'
            self.send_json({'error':message},409)
        except Exception as e:rollback_safely(db);print('Server error:',type(e).__name__,str(e));self.send_json({'error':'Server error. Check the server terminal.'},500)
        finally:db.close()
def make_server(db_path,host='127.0.0.1',port=8000):
    store.initialize(db_path);server=ThreadingHTTPServer((host,port),Handler);server.db_path=db_path;return server
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8000);args=parser.parse_args()
    try:
        settings=config.load(prompt=True);server=make_server(settings,port=args.port)
    except psycopg.Error as error:
        print('Could not connect/setup PostgreSQL:',error)
        print('Check that PostgreSQL is running, relief360 exists, and the host/port/user/password are correct.')
        raise SystemExit(1)
    print(f'RELIEF360 ready: http://localhost:{args.port}/login.html\nDatabase: {settings["dbname"]} on {settings["host"]}:{settings["port"]}\nPress Ctrl+C to stop.')
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
if __name__=='__main__':main()

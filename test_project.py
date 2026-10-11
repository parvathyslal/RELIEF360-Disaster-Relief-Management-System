"""Integration tests against the real HTTP server and an explicitly configured disposable PostgreSQL database."""
import unittest,tempfile,threading,json,urllib.request,urllib.error,http.cookiejar,psycopg,concurrent.futures
from pathlib import Path
import server,store,config,os
class ProjectTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.path=config.load()
  if not os.environ.get('RELIEF360_TEST_DATABASE') or not cls.path['dbname'].endswith('_test'):
   raise unittest.SkipTest('Set RELIEF360_TEST_DATABASE=1 only for a disposable PostgreSQL test database. See README.')
  cls.server=server.make_server(cls.path,port=0);cls.url='http://127.0.0.1:'+str(cls.server.server_port);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
 def client(self,email='admin@relief360.local'):
  jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));self.call(opener,'login',{'email':email,'password':'Relief360!2026'},expected=200);return opener,self.call(opener,'me')['csrf']
 def call(self,opener,path,body=None,csrf='',expected=200):
  r=urllib.request.Request(self.url+'/api/'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-CSRF-Token':csrf})
  try:
   with opener.open(r) as response:status=response.status;data=response.read()
  except urllib.error.HTTPError as e:status=e.code;data=e.read()
  self.assertEqual(status,expected,data.decode());return json.loads(data)
 def create(self,o,c,module,p):return self.call(o,module,p,c,201)['id']
 def test_01_auth_and_static(self):
  o=urllib.request.build_opener();self.call(o,'dashboard',expected=401);self.call(o,'login',{'email':'admin@relief360.local','password':'wrong'},expected=401)
  o,c=self.client();self.call(o,'alerts',{},expected=403)
  for path in ['/server.py','/store.py','/database/schema.sql','/data/relief360.db','/../server.py']:
   try:o.open(self.url+path);self.fail('Private file exposed')
   except urllib.error.HTTPError as e:self.assertEqual(e.code,404)
  self.call(o,'logout',{},c);self.call(o,'me',expected=401)
 def test_02_all_workflows(self):
  o,c=self.client();d=self.create(o,c,'disasters',dict(disaster_name='Integration flood',disaster_type='Flood',location='Test',severity='High',start_date='2026-10-01'))
  a=self.create(o,c,'camps',dict(disaster_id=d,camp_name='Source',location='A',capacity=10));b=self.create(o,c,'camps',dict(disaster_id=d,camp_name='Target',location='B',capacity=10))
  v=self.create(o,c,'victims',dict(disaster_id=d,full_name='Resident <script>alert(1)</script>',gender='Female',date_of_birth='2000-01-01',camp_id=a))
  self.call(o,f'victims/{v}/transfer',{'camp_id':b},c,201);h=self.call(o,f'victims/{v}/history');self.assertEqual(len(h),2);self.assertEqual(sum(x['status']=='Active' for x in h),1)
  self.call(o,f'victims/{v}/edit',{'full_name':'Updated resident'},c,201)
  m=self.create(o,c,'missing-persons',dict(disaster_id=d,missing_name='Resident',age=26,gender='Female',last_seen_location='Test',last_seen_date='2026-10-01',reporter_name='Reporter',reporter_phone='123'))
  self.call(o,f'missing-persons/{m}/match',dict(matched_victim_id=v,status='Family Reunited'),c,201)
  vol=self.create(o,c,'volunteers',dict(full_name='Test volunteer',phone='123',primary_skill='Rescue'))
  self.call(o,f'volunteers/{vol}/assign',dict(disaster_id=d,camp_id=b,task_description='Supply delivery'),c,201)
  self.assertEqual(len(self.call(o,f'volunteers/{vol}/history')),1)
  don=self.create(o,c,'donations',dict(disaster_id=d,donor_name='Test donor',amount='123.45',donation_date='2026-10-01',payment_mode='UPI'))
  donation=next(r for r in self.call(o,'donations') if r['donation_id']==don);self.assertEqual(donation['amount'],12345);self.assertTrue(donation['receipt_no'])
  item=self.create(o,c,'inventory',dict(camp_id=a,item_name='Integration water',category='Water',unit='bottles',reorder_level=2,quantity=20))
  tx=self.create(o,c,'distribution',dict(source_camp_id=a,target_type='camp',target_id=b,distributed_by=vol,items=[dict(item_id=item,quantity=7)]))
  tx2=self.create(o,c,'distribution',dict(source_camp_id=b,target_type='victim',target_id=v,items=[dict(item_id=item,quantity=2)]))
  stocks={(r['camp_id'],r['item_id']):r['quantity_on_hand'] for r in self.call(o,'inventory')};self.assertEqual(stocks[a,item],13);self.assertEqual(stocks[b,item],5)
  before=len(self.call(o,'distribution'));self.call(o,'distribution',dict(source_camp_id=a,target_type='camp',target_id=b,items=[dict(item_id=item,quantity=999)]),c,400);self.assertEqual(len(self.call(o,'distribution')),before)
  medical=self.create(o,c,'medical',dict(victim_id=v,assigned_medical_user_id=3,condition_summary='First aid',priority='Low'))
  self.call(o,f'medical/{medical}/treat',dict(treatment_details='Dressing',status='Closed'),c,201)
  vehicle=self.create(o,c,'vehicles',dict(vehicle_no='TEST-001',vehicle_type='Truck',capacity=8,driver_name='Test Driver',driver_phone='123',fuel_percentage=25))
  self.call(o,f'vehicles/{vehicle}/allocate',dict(disaster_id=d,camp_id=b,purpose='Delivery',from_location='A',to_location='B'),c,201)
  self.call(o,f'vehicles/{vehicle}/allocate',dict(disaster_id=d,purpose='Double',from_location='A',to_location='B'),c,409)
  self.call(o,f'vehicles/{vehicle}/return',{},c,201);self.assertEqual(self.call(o,f'vehicles/{vehicle}/history')[0]['status'],'Returned')
  alert=self.create(o,c,'alerts',dict(disaster_id=d,camp_id=b,alert_type='Test alert',severity='Critical',message='Test instructions'));self.call(o,f'alerts/{alert}/resolve',{},c,201)
  for module in store.QUERIES:self.assertIsInstance(self.call(o,module),list)
  self.assertIn('metrics',self.call(o,'dashboard'));self.assertIn('donations',self.call(o,'reports'))
  with o.open(self.url+'/api/export?report=donations') as r:self.assertIn(b'total_rupees',r.read())
  self.call(o,f'victims/{v}/release',{},c,201);self.call(o,f'camps/{b}/close',{},c,201);self.call(o,f'camps/{a}/close',{},c,201);self.call(o,f'disasters/{d}/close',{},c,201)
 def test_03_role_denial(self):
  for email,module in [('volunteer@relief360.local','inventory'),('medical@relief360.local','donations'),('ngo@relief360.local','alerts')]:
   o,c=self.client(email);self.call(o,module,{},c,403)
 def test_04_integrity(self):
  o,c=self.client();self.call(o,'camps',dict(disaster_id=1,camp_name='Bad',location='Bad',capacity=-1),c,400)
  self.call(o,'victims',dict(disaster_id=1,full_name='Bad DOB',gender='Female',date_of_birth='2099-01-01'),c,400)
  d=self.create(o,c,'disasters',dict(disaster_name='Other flood',disaster_type='Flood',location='Test',severity='Low',start_date='2026-10-01'))
  camp=self.create(o,c,'camps',dict(disaster_id=d,camp_name='Other camp',location='Test',capacity=1))
  self.call(o,'victims',dict(disaster_id=1,full_name='Wrong disaster',gender='Female',camp_id=camp),c,400)
  v=self.create(o,c,'victims',dict(disaster_id=d,full_name='First resident',gender='Female',camp_id=camp))
  self.call(o,'victims',dict(disaster_id=d,full_name='Over capacity',gender='Male',camp_id=camp),c,400)
  self.call(o,f'camps/{camp}/close',{},c,400)
  db=store.connect(self.path)
  with self.assertRaises(psycopg.IntegrityError):db.execute('INSERT INTO VICTIM_CAMP_ASSIGNMENT(victim_id,camp_id) VALUES(1,%s)',(camp,))
  db.rollback();db.close();db=store.connect(self.path);self.assertEqual(db.execute('SELECT 1').fetchone()[0],1);db.close()
 def test_05_concurrent_stock(self):
  o,c=self.client();item=self.create(o,c,'inventory',dict(camp_id=1,item_name='Concurrent stock',category='Test',unit='pieces',reorder_level=0,quantity=5))
  def send():
   req=urllib.request.Request(self.url+'/api/distribution',data=json.dumps(dict(source_camp_id=1,target_type='camp',target_id=2,items=[dict(item_id=item,quantity=4)])).encode(),headers={'Content-Type':'application/json','X-CSRF-Token':c})
   try:return o.open(req).status
   except urllib.error.HTTPError as e:return e.code
  with concurrent.futures.ThreadPoolExecutor(2) as pool:codes=list(pool.map(lambda _:send(),range(2)))
  self.assertEqual(sorted(codes),[201,400]);stock=next(r for r in self.call(o,'inventory') if r['camp_id']==1 and r['item_id']==item);self.assertEqual(stock['quantity_on_hand'],1)
 def test_06_accounts_password_csrf_and_money(self):
  o,c=self.client()
  user=self.call(o,'users',dict(name='New medical user',email='new@relief360.local',password='NewPassword123!',role='medical'),c,201)
  self.assertGreater(user['id'],4)
  self.call(o,'password',dict(old_password='wrong',new_password='ChangedPassword123!'),c,400)
  self.call(o,'password',dict(old_password='Relief360!2026',new_password='ChangedPassword123!'),c)
  fresh=urllib.request.build_opener();self.call(fresh,'login',dict(email='admin@relief360.local',password='Relief360!2026'),expected=401)
  self.call(fresh,'login',dict(email='admin@relief360.local',password='ChangedPassword123!'))
  self.call(o,'password',dict(old_password='ChangedPassword123!',new_password='Relief360!2026'),c)
  self.call(o,'donations',dict(disaster_id=1,donor_name='Bad money',amount='1.001',donation_date='2026-10-01',payment_mode='Cash'),c,400)
  self.call(o,'donations',dict(disaster_id=1,donor_name='Bad money',amount='NaN',donation_date='2026-10-01',payment_mode='Cash'),c,400)
  self.call(o,'users',dict(name='Invalid role',email='bad@local',password='NewPassword123!',role='root'),c,400)
 def test_07_multi_item_rollback(self):
  o,c=self.client();stocks=self.call(o,'inventory');first=next(x for x in stocks if x['camp_id']==1 and x['item_id']==1);before=first['quantity_on_hand']
  self.call(o,'distribution',dict(source_camp_id=1,target_type='camp',target_id=2,items=[dict(item_id=1,quantity=1),dict(item_id=2,quantity=999999)]),c,400)
  current=next(x for x in self.call(o,'inventory') if x['camp_id']==1 and x['item_id']==1);self.assertEqual(current['quantity_on_hand'],before)
  self.create(o,c,'distribution',dict(source_camp_id=1,target_type='camp',target_id=2,items=[dict(item_id=1,quantity=1),dict(item_id=2,quantity=1)]))
  self.call(o,'distribution',dict(source_camp_id=1,target_type='camp',target_id=2,items=[dict(item_id=1,quantity=1),dict(item_id=1,quantity=1)]),c,400)
 def test_08_restart_persistence(self):
  db=store.connect(self.path);n=db.execute('SELECT COUNT(*) FROM DISASTER').fetchone()[0];db.close();store.initialize(self.path);db=store.connect(self.path);self.assertEqual(db.execute('SELECT COUNT(*) FROM DISASTER').fetchone()[0],n);self.assertEqual(db.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'").fetchone()[0],24);db.close()
 def test_09_pgadmin_edits_and_deferred_assertions(self):
  o,c=self.client();db=store.connect(self.path)
  db.execute("UPDATE CAMP SET camp_name='Changed in SQL' WHERE camp_id=1");db.commit();db.close()
  self.assertEqual(next(x for x in self.call(o,'camps') if x['camp_id']==1)['camp_name'],'Changed in SQL')
  db=store.connect(self.path)
  with self.assertRaises(psycopg.IntegrityError):
   db.execute("INSERT INTO DISTRIBUTION(disaster_id) VALUES(1)");db.commit()
  db.rollback();db.close()
if __name__=='__main__':unittest.main(verbosity=2)

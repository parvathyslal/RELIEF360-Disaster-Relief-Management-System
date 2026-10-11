"""Database, validation and transactional application services. Python standard library only."""
import psycopg, hashlib, secrets, hmac, datetime, json, decimal
from pathlib import Path
ROOT=Path(__file__).parent
class Invalid(ValueError): pass

def password_hash(password):
    salt=secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),200000).hex()
def password_ok(password,value):
    salt,digest=value.split(':')
    return hmac.compare_digest(digest,hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),200000).hex())
class HybridRow(dict):
    def __getitem__(self,key):
        if isinstance(key,int):return list(self.values())[key]
        return super().__getitem__(key)
def row_factory(cursor):
    names=[column.name for column in (cursor.description or [])]
    return lambda values:HybridRow(zip(names,values))
def connect(settings):
    return psycopg.connect(**settings,row_factory=row_factory,options='-c search_path=public,pg_catalog -c timezone=Asia/Kolkata')
def rows(db,sql,args=()): return [dict(r) for r in db.execute(sql,args)]
def insert(db,table,values):
    keys=list(values)
    primary={'USER_ACCOUNT':'user_id','DISASTER':'disaster_id','CAMP':'camp_id','VICTIM':'victim_id','VICTIM_CAMP_ASSIGNMENT':'assignment_id','MISSING_REPORT':'report_id','VOLUNTEER':'volunteer_id','VOLUNTEER_ASSIGNMENT':'assignment_id','VOLUNTEER_CAMP_ASSIGNMENT':'assignment_id','DONOR':'donor_id','DONATION':'donation_id','INVENTORY_ITEM':'item_id','DISTRIBUTION':'distribution_id','DISTRIBUTION_SOURCE':'distribution_id','CAMP_DISTRIBUTION':'distribution_id','VICTIM_DISTRIBUTION':'distribution_id','MEDICAL_CASE':'case_id','VEHICLE':'vehicle_id','VEHICLE_ALLOCATION':'allocation_id','VEHICLE_CAMP_ALLOCATION':'allocation_id','ALERT':'alert_id','CAMP_ALERT':'alert_id'}
    key=primary.get(table,keys[0])
    return db.execute(f'INSERT INTO {table} ({",".join(keys)}) VALUES ({",".join("%s" for k in keys)}) RETURNING {key}',[values[k] for k in keys]).fetchone()[0]

def text(p,k,required=True):
    v=str(p.get(k,'')).strip()
    if required and not v: raise Invalid(k.replace('_',' ')+' is required')
    if len(v)>4000: raise Invalid(k+' is too long')
    return v
def integer(p,k,min_value=1):
    try:
        v=int(str(p.get(k,'')))
    except (ValueError,TypeError): raise Invalid(k.replace('_',' ')+' must be a whole number')
    if v<min_value: raise Invalid(k.replace('_',' ')+' is too small')
    return v
def date(p,k,optional=False):
    v=text(p,k,not optional)
    if not v and optional:return None
    try: datetime.date.fromisoformat(v)
    except ValueError:raise Invalid(k+' must be a valid date')
    return v
def existing(db,table,key,id):
    r=db.execute(f'SELECT * FROM {table} WHERE {key}=%s',(id,)).fetchone()
    if not r:raise Invalid(table.lower().replace('_',' ')+' does not exist')
    if table=='DISASTER' and r['status']=='Closed':raise Invalid('This disaster is closed')
    return r
def same_camp(db,camp,disaster):
    c=existing(db,'CAMP','camp_id',camp)
    if c['disaster_id']!=disaster:raise Invalid('Camp and record must belong to the same disaster')
    if c['status']!='Open':raise Invalid('Choose an open camp')
    return c
def choice(p,k,allowed):
    v=text(p,k)
    if v not in allowed:raise Invalid('Invalid '+k)
    return v
def money(p):
    try:
        value=decimal.Decimal(str(p.get('amount','')))
        if not value.is_finite() or value<=0 or value>1000000000000 or value.as_tuple().exponent < -2:raise ValueError()
        return int(value*100)
    except (decimal.InvalidOperation,ValueError,OverflowError):raise Invalid('Enter a positive amount with at most two decimal places')
def assign_victim(db,victim,camp):
    v=existing(db,'VICTIM','victim_id',victim);c=same_camp(db,camp,v['disaster_id'])
    old=db.execute("SELECT * FROM VICTIM_CAMP_ASSIGNMENT WHERE victim_id=%s AND status='Active'",(victim,)).fetchone()
    if old and old['camp_id']==camp:raise Invalid('Victim is already assigned to this camp')
    occupancy=db.execute("SELECT COUNT(*) FROM VICTIM_CAMP_ASSIGNMENT WHERE camp_id=%s AND status='Active'",(camp,)).fetchone()[0]
    if occupancy>=c['capacity']:raise Invalid('Camp is full; choose another camp')
    db.execute("UPDATE VICTIM_CAMP_ASSIGNMENT SET status='Released',released_at=CURRENT_TIMESTAMP WHERE victim_id=%s AND status='Active'",(victim,))
    insert(db,'VICTIM_CAMP_ASSIGNMENT',dict(victim_id=victim,camp_id=camp))
    db.execute("UPDATE VICTIM SET status='Sheltered' WHERE victim_id=%s",(victim,))

def initialize(path):
    db=connect(path);db.execute((ROOT/'database/schema.sql').read_text(),prepare=False)
    if not db.execute('SELECT 1 FROM USER_ACCOUNT LIMIT 1').fetchone():
        accounts=[('EOC Administrator','admin@relief360.local','admin'),('NGO Coordinator','ngo@relief360.local','ngo'),('Medical Officer','medical@relief360.local','medical'),('Field Volunteer','volunteer@relief360.local','volunteer')]
        user_ids=[insert(db,'USER_ACCOUNT',dict(name=name,email=email,role=role,password_hash=password_hash('Relief360!2026'))) for name,email,role in accounts]
        d=insert(db,'DISASTER',dict(disaster_type='Flood',disaster_name='Demo Kerala Flood Response',location='Alappuzha',severity='High',start_date=datetime.date.today().isoformat(),latitude=9.49,longitude=76.33))
        c=insert(db,'CAMP',dict(disaster_id=d,camp_name='Demo Central Relief Camp',location='Alappuzha',capacity=100,contact_phone='0477-0000000',latitude=9.49,longitude=76.34))
        insert(db,'CAMP',dict(disaster_id=d,camp_name='Demo Community Shelter',location='Kuttanad',capacity=80,latitude=9.43,longitude=76.44))
        v=insert(db,'VICTIM',dict(disaster_id=d,full_name='Demo Resident',gender='Female',date_of_birth='1990-01-01'));assign_victim(db,v,c)
        insert(db,'VOLUNTEER',dict(full_name='Demo Field Volunteer',phone='9000000000',primary_skill='Logistics',user_id=user_ids[3]))
        for name,cat,unit,qty,reorder in [('Food kits','Food','kits',500,100),('Drinking water','Water','litres',1000,200),('First aid kits','Medical','kits',15,20)]:
            i=insert(db,'INVENTORY_ITEM',dict(item_name=name,category=cat,unit=unit,reorder_level=reorder));insert(db,'CAMP_INVENTORY',dict(camp_id=c,item_id=i,quantity_on_hand=qty))
        insert(db,'VEHICLE',dict(vehicle_no='DEMO-KL-001',vehicle_type='Ambulance',capacity=4,driver_name='Demo Driver',driver_phone='9000000001'))
        insert(db,'ALERT',dict(disaster_id=d,created_by=user_ids[0],alert_type='Demo flood warning',severity='High',message='Demonstration data only. Check official instructions for actual emergencies.'))
    db.commit();db.close()

READ_ONLY={'volunteer'}
WRITERS={'disasters':{'admin'},'camps':{'admin','ngo'},'victims':{'admin','ngo','volunteer'},'missing-persons':{'admin','ngo','volunteer'},'volunteers':{'admin','ngo'},'donations':{'admin','ngo'},'inventory':{'admin','ngo'},'distribution':{'admin','ngo'},'medical':{'admin','medical'},'vehicles':{'admin','ngo'},'alerts':{'admin'}}

def create(db,module,p,user):
    if module=='disasters':
        vals={k:text(p,k) for k in ['disaster_name','disaster_type','location']};vals.update(severity=choice(p,'severity',['Critical','High','Moderate','Low']),start_date=date(p,'start_date'),description=text(p,'description',False))
        for k,lo,hi in [('latitude',-90,90),('longitude',-180,180)]:
            if p.get(k) not in (None,''):
                try:vals[k]=float(p[k])
                except ValueError:raise Invalid('Invalid coordinates')
                if not lo<=vals[k]<=hi:raise Invalid('Coordinates out of range')
        return insert(db,'DISASTER',vals)
    if module=='camps':
        d=integer(p,'disaster_id');existing(db,'DISASTER','disaster_id',d)
        vals=dict(disaster_id=d,camp_name=text(p,'camp_name'),location=text(p,'location'),capacity=integer(p,'capacity'),contact_phone=text(p,'contact_phone',False))
        for k,lo,hi in [('latitude',-90,90),('longitude',-180,180)]:
            if p.get(k) not in (None,''):
                try: vals[k]=float(p[k])
                except ValueError:raise Invalid('Invalid coordinates')
                if not lo<=vals[k]<=hi:raise Invalid('Coordinates out of range')
        return insert(db,'CAMP',vals)
    if module=='victims':
        d=integer(p,'disaster_id');existing(db,'DISASTER','disaster_id',d)
        dob=date(p,'date_of_birth',True)
        if dob and dob>datetime.date.today().isoformat():raise Invalid('Date of birth cannot be in the future')
        v=insert(db,'VICTIM',dict(disaster_id=d,full_name=text(p,'full_name'),gender=choice(p,'gender',['Female','Male','Other','Prefer not to say']),date_of_birth=dob,phone=text(p,'phone',False),address=text(p,'address',False),medical_notes=text(p,'medical_notes',False)))
        if p.get('camp_id'):assign_victim(db,v,integer(p,'camp_id'))
        return v
    if module=='missing-persons':
        d=integer(p,'disaster_id');existing(db,'DISASTER','disaster_id',d);age=integer(p,'age',0)
        if age>130:raise Invalid('Age must be at most 130')
        seen=date(p,'last_seen_date')
        if seen>datetime.date.today().isoformat():raise Invalid('Last seen date cannot be in the future')
        return insert(db,'MISSING_REPORT',dict(disaster_id=d,missing_name=text(p,'missing_name'),age=age,gender=text(p,'gender'),identifying_marks=text(p,'identifying_marks',False),last_seen_location=text(p,'last_seen_location'),last_seen_date=seen,reporter_name=text(p,'reporter_name'),reporter_phone=text(p,'reporter_phone')))
    if module=='volunteers':return insert(db,'VOLUNTEER',dict(full_name=text(p,'full_name'),phone=text(p,'phone'),email=text(p,'email',False),primary_skill=text(p,'primary_skill')))
    if module=='donations':
        d=integer(p,'disaster_id');existing(db,'DISASTER','disaster_id',d)
        donor=integer(p,'donor_id') if p.get('donor_id') else insert(db,'DONOR',dict(donor_name=text(p,'donor_name'),phone=text(p,'phone',False),email=text(p,'email',False)))
        existing(db,'DONOR','donor_id',donor)
        return insert(db,'DONATION',dict(donor_id=donor,disaster_id=d,amount=money(p),donation_date=date(p,'donation_date'),payment_mode=text(p,'payment_mode'),transaction_ref=text(p,'transaction_ref',False),receipt_no='R360-'+secrets.token_hex(6).upper()))
    if module=='inventory':
        camp=integer(p,'camp_id');existing(db,'CAMP','camp_id',camp)
        if p.get('item_id'):item=integer(p,'item_id');existing(db,'INVENTORY_ITEM','item_id',item)
        else:item=insert(db,'INVENTORY_ITEM',dict(item_name=text(p,'item_name'),category=text(p,'category'),unit=text(p,'unit'),reorder_level=integer(p,'reorder_level',0)))
        qty=integer(p,'quantity',0)
        db.execute('INSERT INTO CAMP_INVENTORY(camp_id,item_id,quantity_on_hand) VALUES(%s,%s,%s) ON CONFLICT(camp_id,item_id) DO UPDATE SET quantity_on_hand=CAMP_INVENTORY.quantity_on_hand+excluded.quantity_on_hand,last_updated=CURRENT_TIMESTAMP',(camp,item,qty));return item
    if module=='distribution':
        source=integer(p,'source_camp_id');c=existing(db,'CAMP','camp_id',source);d=c['disaster_id'];same_camp(db,source,d)
        target=choice(p,'target_type',['camp','victim']);tid=integer(p,'target_id')
        if target=='camp':
            same_camp(db,tid,d)
            if tid==source:raise Invalid('Source and destination camps must differ')
        else:
            v=existing(db,'VICTIM','victim_id',tid)
            if v['disaster_id']!=d:raise Invalid('Victim must belong to the source camp disaster')
        lines=p.get('items')
        if not isinstance(lines,list) or not 1<=len(lines)<=100:raise Invalid('Add at least one distribution item (maximum 100)')
        seen=set();checked=[]
        for line in lines:
            if not isinstance(line,dict):raise Invalid('Invalid distribution line')
            item=integer(line,'item_id');qty=integer(line,'quantity')
            if item in seen:raise Invalid('Each item can appear only once')
            seen.add(item);existing(db,'INVENTORY_ITEM','item_id',item)
            stock=db.execute('SELECT quantity_on_hand FROM CAMP_INVENTORY WHERE camp_id=%s AND item_id=%s',(source,item)).fetchone()
            if not stock or stock[0]<qty:raise Invalid('Insufficient source stock for item '+str(item))
            checked.append((item,qty))
        vol=integer(p,'distributed_by') if p.get('distributed_by') else None
        if vol:existing(db,'VOLUNTEER','volunteer_id',vol)
        tx=insert(db,'DISTRIBUTION',dict(disaster_id=d,distributed_by=vol,notes=text(p,'notes',False)))
        insert(db,'DISTRIBUTION_SOURCE',dict(distribution_id=tx,camp_id=source))
        insert(db,'CAMP_DISTRIBUTION' if target=='camp' else 'VICTIM_DISTRIBUTION',dict(distribution_id=tx,**{target+'_id':tid}))
        for item,qty in checked:
            db.execute('UPDATE CAMP_INVENTORY SET quantity_on_hand=quantity_on_hand-%s,last_updated=CURRENT_TIMESTAMP WHERE camp_id=%s AND item_id=%s',(qty,source,item));insert(db,'DISTRIBUTION_ITEM',dict(distribution_id=tx,item_id=item,quantity=qty))
            if target=='camp':db.execute('INSERT INTO CAMP_INVENTORY(camp_id,item_id,quantity_on_hand) VALUES(%s,%s,%s) ON CONFLICT(camp_id,item_id) DO UPDATE SET quantity_on_hand=CAMP_INVENTORY.quantity_on_hand+excluded.quantity_on_hand,last_updated=CURRENT_TIMESTAMP',(tid,item,qty))
        # Cross-table mandatory target/line assertions are checked before API transaction commit.
        n=db.execute('SELECT (SELECT COUNT(*) FROM CAMP_DISTRIBUTION WHERE distribution_id=%s)+(SELECT COUNT(*) FROM VICTIM_DISTRIBUTION WHERE distribution_id=%s)',(tx,tx)).fetchone()[0]
        if n!=1 or not db.execute('SELECT 1 FROM DISTRIBUTION_ITEM WHERE distribution_id=%s',(tx,)).fetchone():raise Invalid('Incomplete distribution')
        return tx
    if module=='medical':
        v=integer(p,'victim_id');existing(db,'VICTIM','victim_id',v);medical=integer(p,'assigned_medical_user_id') if p.get('assigned_medical_user_id') else user['user_id']
        return insert(db,'MEDICAL_CASE',dict(victim_id=v,assigned_medical_user_id=medical,condition_summary=text(p,'condition_summary'),priority=choice(p,'priority',['Critical','High','Moderate','Low'])))
    if module=='vehicles':
        fuel=integer(p,'fuel_percentage',0)
        if fuel>100:raise Invalid('Fuel percentage cannot exceed 100')
        return insert(db,'VEHICLE',dict(vehicle_no=text(p,'vehicle_no').upper(),vehicle_type=text(p,'vehicle_type'),capacity=integer(p,'capacity'),driver_name=text(p,'driver_name'),driver_phone=text(p,'driver_phone'),fuel_percentage=fuel))
    if module=='alerts':
        d=integer(p,'disaster_id');existing(db,'DISASTER','disaster_id',d)
        a=insert(db,'ALERT',dict(disaster_id=d,created_by=user['user_id'],alert_type=text(p,'alert_type'),severity=choice(p,'severity',['Critical','High','Moderate','Low']),message=text(p,'message')))
        if p.get('camp_id'):c=integer(p,'camp_id');same_camp(db,c,d);insert(db,'CAMP_ALERT',dict(alert_id=a,camp_id=c))
        return a
    raise Invalid('Unknown module')

def action(db,module,id,act,p,user):
    if act=='edit' and module in ('disasters','camps','victims','volunteers','vehicles'):
        config={'disasters':('DISASTER','disaster_id',['disaster_name','location','description']),'camps':('CAMP','camp_id',['camp_name','location','contact_phone']),'victims':('VICTIM','victim_id',['full_name','phone','address','medical_notes']),'volunteers':('VOLUNTEER','volunteer_id',['full_name','phone','email','primary_skill']),'vehicles':('VEHICLE','vehicle_id',['driver_name','driver_phone'])}
        table,key,fields=config[module];existing(db,table,key,id);vals={k:text(p,k,k not in ['description','phone','email','address','medical_notes','contact_phone']) for k in fields if k in p}
        if not vals:raise Invalid('No fields to update')
        db.execute(f'UPDATE {table} SET '+','.join(k+'=%s' for k in vals)+f' WHERE {key}=%s',list(vals.values())+[id])
    elif module=='victims':
        existing(db,'VICTIM','victim_id',id)
        if act=='transfer':assign_victim(db,id,integer(p,'camp_id'))
        elif act=='release':
            db.execute("UPDATE VICTIM_CAMP_ASSIGNMENT SET status='Released',released_at=CURRENT_TIMESTAMP WHERE victim_id=%s AND status='Active'",(id,));db.execute("UPDATE VICTIM SET status='Released' WHERE victim_id=%s",(id,))
        else:raise Invalid('Unknown action')
        elif module=='missing-persons' and act=='match':
        r = existing(db, 'MISSING_REPORT', 'report_id', id)
        v = integer(p, 'matched_victim_id')
        victim = existing(db, 'VICTIM', 'victim_id', v)

        if r['status'] != 'Searching':
            raise Invalid('This missing-person report has already been resolved')

        if victim['disaster_id'] != r['disaster_id']:
            raise Invalid('Matched victim must belong to the same disaster')

        # Check gender when both records have comparable values
        if (r['gender'] in ('Male', 'Female')
                and victim['gender'] in ('Male', 'Female')
                and r['gender'] != victim['gender']):
            raise Invalid('Gender mismatch. Verify the person before matching')

        # Check age when date of birth is available
        if victim['date_of_birth']:
            today = datetime.date.today()
            dob = victim['date_of_birth']

            if isinstance(dob, str):
                dob = datetime.date.fromisoformat(dob)

            age = today.year - dob.year - (
                (today.month, today.day) < (dob.month, dob.day)
            )

            if abs(age - r['age']) > 2:
                raise Invalid('Age mismatch. Verify the person before matching')

        status = choice(p, 'status', ['Found', 'Family Reunited'])

        db.execute(
            'UPDATE MISSING_REPORT SET matched_victim_id=%s, status=%s WHERE report_id=%s',
            (v, status, id)
        )
    elif module=='volunteers':
        existing(db,'VOLUNTEER','volunteer_id',id)
        if act=='assign':
            d=integer(p,'disaster_id');existing(db,'DISASTER','disaster_id',d)
            a=insert(db,'VOLUNTEER_ASSIGNMENT',dict(volunteer_id=id,disaster_id=d,task_description=text(p,'task_description'),shift=text(p,'shift',False)))
            if p.get('camp_id'):c=integer(p,'camp_id');same_camp(db,c,d);insert(db,'VOLUNTEER_CAMP_ASSIGNMENT',dict(assignment_id=a,camp_id=c))
        elif act=='complete':db.execute("UPDATE VOLUNTEER_ASSIGNMENT SET status='Completed' WHERE volunteer_id=%s AND status='Active'",(id,))
        else:raise Invalid('Unknown action')
    elif module=='medical' and act=='treat':
        m=existing(db,'MEDICAL_CASE','case_id',id)
        if user['role']=='medical' and m['assigned_medical_user_id'] not in (None,user['user_id']):raise Invalid('This case is assigned to another medical officer')
        status=choice(p,'status',['Open','Under Treatment','Closed']);treatment=text(p,'treatment_details')
        db.execute('UPDATE MEDICAL_CASE SET treatment_details=%s,treatment_date=CURRENT_TIMESTAMP,status=%s WHERE case_id=%s',(treatment,status,id))
    elif module=='vehicles':
        vehicle=existing(db,'VEHICLE','vehicle_id',id)
        if act=='allocate':
            if vehicle['status']!='Available':raise Invalid('Vehicle is not available')
            d=integer(p,'disaster_id');existing(db,'DISASTER','disaster_id',d)
            a=insert(db,'VEHICLE_ALLOCATION',dict(vehicle_id=id,disaster_id=d,purpose=text(p,'purpose'),from_location=text(p,'from_location'),to_location=text(p,'to_location')))
            if p.get('camp_id'):c=integer(p,'camp_id');same_camp(db,c,d);insert(db,'VEHICLE_CAMP_ALLOCATION',dict(allocation_id=a,camp_id=c))
        elif act=='return':db.execute("UPDATE VEHICLE_ALLOCATION SET status='Returned',returned_at=CURRENT_TIMESTAMP WHERE vehicle_id=%s AND status='Active'",(id,))
        else:raise Invalid('Unknown action')
    elif module=='alerts' and act=='resolve':existing(db,'ALERT','alert_id',id);db.execute("UPDATE ALERT SET status='Resolved' WHERE alert_id=%s",(id,))
    elif module=='disasters' and act=='close':
        existing(db,'DISASTER','disaster_id',id)
        if db.execute("SELECT 1 FROM CAMP WHERE disaster_id=%s AND status='Open'",(id,)).fetchone():raise Invalid('Close all camps before closing the disaster')
        db.execute("UPDATE DISASTER SET status='Closed' WHERE disaster_id=%s",(id,))
    elif module=='camps' and act=='close':
        existing(db,'CAMP','camp_id',id)
        if db.execute("SELECT 1 FROM VICTIM_CAMP_ASSIGNMENT WHERE camp_id=%s AND status='Active'",(id,)).fetchone():raise Invalid('Transfer or release residents before closing the camp')
        db.execute("UPDATE CAMP SET status='Closed' WHERE camp_id=%s",(id,))
    else:raise Invalid('Unknown action')
    return id

QUERIES={
'disasters':'''SELECT d.*, (SELECT COUNT(*) FROM CAMP c WHERE c.disaster_id=d.disaster_id AND c.status='Open') camps_active,(SELECT COUNT(*) FROM VICTIM v WHERE v.disaster_id=d.disaster_id) victims FROM DISASTER d ORDER BY disaster_id DESC''',
'camps':'''SELECT c.*,d.disaster_name FROM camp_occupancy c JOIN DISASTER d USING(disaster_id) ORDER BY camp_id DESC''',
'victims':'''SELECT v.*,d.disaster_name,c.camp_name,a.camp_id FROM VICTIM v JOIN DISASTER d USING(disaster_id) LEFT JOIN VICTIM_CAMP_ASSIGNMENT a ON a.victim_id=v.victim_id AND a.status='Active' LEFT JOIN CAMP c ON c.camp_id=a.camp_id ORDER BY v.victim_id DESC''',
'missing-persons':'''SELECT r.*,d.disaster_name,v.full_name matched_name FROM MISSING_REPORT r JOIN DISASTER d USING(disaster_id) LEFT JOIN VICTIM v ON v.victim_id=r.matched_victim_id ORDER BY report_id DESC''',
'volunteers':'''SELECT v.*,(SELECT STRING_AGG(task_description,'; ') FROM VOLUNTEER_ASSIGNMENT a WHERE a.volunteer_id=v.volunteer_id AND a.status='Active') tasks FROM VOLUNTEER v ORDER BY volunteer_id DESC''',
'donations':'''SELECT t.*,d.donor_name,s.disaster_name FROM DONATION t JOIN DONOR d USING(donor_id) JOIN DISASTER s USING(disaster_id) ORDER BY donation_id DESC''',
'inventory':'''SELECT * FROM stock_report ORDER BY camp_id,item_id''',
'distribution':'''SELECT d.*,s.camp_name source_camp,COALESCE(c.camp_name,v.full_name) recipient,CASE WHEN c.camp_id IS NOT NULL THEN 'camp' ELSE 'victim' END target_type,vol.full_name volunteer FROM DISTRIBUTION d JOIN DISTRIBUTION_SOURCE ds USING(distribution_id) JOIN CAMP s ON s.camp_id=ds.camp_id LEFT JOIN CAMP_DISTRIBUTION cd USING(distribution_id) LEFT JOIN CAMP c ON c.camp_id=cd.camp_id LEFT JOIN VICTIM_DISTRIBUTION vd USING(distribution_id) LEFT JOIN VICTIM v ON v.victim_id=vd.victim_id LEFT JOIN VOLUNTEER vol ON vol.volunteer_id=d.distributed_by ORDER BY distribution_id DESC''',
'medical':'''SELECT m.*,v.full_name,v.disaster_id,u.name medical_user FROM MEDICAL_CASE m JOIN VICTIM v USING(victim_id) LEFT JOIN USER_ACCOUNT u ON u.user_id=m.assigned_medical_user_id ORDER BY case_id DESC''',
'vehicles':'''SELECT v.*,a.allocation_id,a.disaster_id,a.purpose,a.to_location,a.assigned_at FROM VEHICLE v LEFT JOIN VEHICLE_ALLOCATION a ON a.vehicle_id=v.vehicle_id AND a.status='Active' ORDER BY v.vehicle_id DESC''',
'alerts':'''SELECT a.*,d.disaster_name,u.name creator,c.camp_name FROM ALERT a JOIN DISASTER d USING(disaster_id) JOIN USER_ACCOUNT u ON u.user_id=a.created_by LEFT JOIN CAMP_ALERT ca USING(alert_id) LEFT JOIN CAMP c ON c.camp_id=ca.camp_id ORDER BY alert_id DESC'''}
def listing(db,module):
    if module not in QUERIES:raise Invalid('Unknown module')
    data=rows(db,QUERIES[module])
    if module=='distribution':
        for record in data:record['items']=rows(db,'SELECT di.*,i.item_name,i.unit FROM DISTRIBUTION_ITEM di JOIN INVENTORY_ITEM i USING(item_id) WHERE distribution_id=%s',(record['distribution_id'],))
    return data

def lookups(db):
    return dict(disasters=rows(db,"SELECT disaster_id id,disaster_name name FROM DISASTER WHERE status!='Closed'"),camps=rows(db,"SELECT camp_id id,camp_name name,disaster_id FROM CAMP WHERE status='Open'"),victims=rows(db,'SELECT victim_id id,full_name name,disaster_id FROM VICTIM'),volunteers=rows(db,"SELECT volunteer_id id,full_name name FROM VOLUNTEER WHERE status='Active'"),items=rows(db,'SELECT item_id id,item_name||\' (\'||unit||\')\' name FROM INVENTORY_ITEM'),donors=rows(db,'SELECT donor_id id,donor_name name FROM DONOR'),medical_users=rows(db,"SELECT user_id id,name FROM USER_ACCOUNT WHERE role IN ('admin','medical') AND status='Active'"))

def reports(db):
    return dict(
        occupancy=rows(
            db,
            'SELECT camp_name, capacity, occupancy, occupancy_percent FROM camp_occupancy'
        ),

        low_stock=rows(
            db,
            'SELECT camp_name, item_name, quantity_on_hand, reorder_level, unit FROM stock_report WHERE low_stock=TRUE'
        ),

        donations=rows(
            db,
            'SELECT d.disaster_name, COUNT(t.donation_id) contributions, '
            'COALESCE(SUM(t.amount), 0)/100.0 total_rupees '
            'FROM DISASTER d LEFT JOIN DONATION t USING(disaster_id) '
            'GROUP BY d.disaster_id'
        ),

        missing=rows(
            db,
            'SELECT d.disaster_name, r.status, COUNT(*) reports '
            'FROM MISSING_REPORT r JOIN DISASTER d USING(disaster_id) '
            'GROUP BY d.disaster_id, r.status'
        ),

        fleet=rows(
            db,
            'SELECT vehicle_no, vehicle_type, driver_name, fuel_percentage '
            'FROM VEHICLE ORDER BY vehicle_id'
        )
    )
def history(db,module,id):
    queries={'victims':('SELECT a.*,c.camp_name FROM VICTIM_CAMP_ASSIGNMENT a JOIN CAMP c USING(camp_id) WHERE victim_id=%s ORDER BY assignment_id DESC','VICTIM','victim_id'),'volunteers':('SELECT a.*,c.camp_name FROM VOLUNTEER_ASSIGNMENT a LEFT JOIN VOLUNTEER_CAMP_ASSIGNMENT ca USING(assignment_id) LEFT JOIN CAMP c USING(camp_id) WHERE volunteer_id=%s ORDER BY assignment_id DESC','VOLUNTEER','volunteer_id'),'vehicles':('SELECT a.* FROM VEHICLE_ALLOCATION a WHERE vehicle_id=%s ORDER BY allocation_id DESC','VEHICLE','vehicle_id')}
    if module not in queries:raise Invalid('History is not available for this module')
    sql,table,key=queries[module];existing(db,table,key,id);return rows(db,sql,(id,))
def dashboard(db):
    count=lambda sql:db.execute(sql).fetchone()[0]
    camps=listing(db,'camps');disasters=listing(db,'disasters');alerts=listing(db,'alerts');stock=listing(db,'inventory')
    return dict(metrics=dict(activeDisasters=count("SELECT COUNT(*) FROM DISASTER WHERE status!='Closed'"),openReliefCamps=count("SELECT COUNT(*) FROM CAMP WHERE status='Open'"),shelteredVictims=count("SELECT COUNT(*) FROM VICTIM_CAMP_ASSIGNMENT WHERE status='Active'"),deployedVolunteers=count("SELECT COUNT(DISTINCT volunteer_id) FROM VOLUNTEER_ASSIGNMENT WHERE status='Active'"),missingPersons=count("SELECT COUNT(*) FROM MISSING_REPORT WHERE status='Searching'"),criticalAlerts=count("SELECT COUNT(*) FROM ALERT WHERE status='Active' AND severity='Critical'")),disasters=[dict(id=d['disaster_id'],name=d['disaster_name'],coordinates=[d['latitude'],d['longitude']],severity=d['severity'],location=d['location'],district='',affectedPopulation=d['victims'],status=d['status']) for d in disasters if d['latitude'] is not None and d['longitude'] is not None],camps=[dict(id=c['camp_id'],name=c['camp_name'],coordinates=[c['latitude'],c['longitude']],occupancy=c['occupancy'],capacity=c['capacity'],location=c['location'],district='',manager='Camp contact',phone=c['contact_phone'],facilities=[]) for c in camps if c['latitude'] is not None and c['longitude'] is not None],occupancyCamps=[dict(name=c['camp_name'],occupancy=c['occupancy'],capacity=c['capacity']) for c in camps],alerts=[dict(priority='CRITICAL' if a['severity']=='Critical' else 'WARNING' if a['severity']=='High' else 'INFO',title=a['alert_type'],message=a['message'],time=a['created_at']) for a in alerts if a['status']=='Active'],resourceStock=[dict(item=s['item_name']+' · '+s['camp_name'],available=s['quantity_on_hand'],unit=s['unit'],percent=min(100,round(100*s['quantity_on_hand']/max(1,s['reorder_level']*2)))) for s in stock],recentActivity=[])

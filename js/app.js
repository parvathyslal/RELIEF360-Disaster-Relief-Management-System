const Relief360App={
  user:null,csrf:'',permissions:[],
  async request(url,body){
    const response=await fetch('/api/'+url,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':this.csrf},body:body===undefined?undefined:JSON.stringify(body)});
    const data=await response.json();
    if(!response.ok){if(response.status===401&&url!=='login')location.href='login.html';throw new Error(data.error||'Request failed');}return data;
  },
  async init(){
    try{const me=await this.request('me');this.user=me.user;this.csrf=me.csrf;this.permissions=me.permissions;
      document.querySelectorAll('#sessionUserName').forEach(el=>el.textContent=me.user.name);
      document.querySelectorAll('#sessionUserRole').forEach(el=>el.textContent=me.user.role.toUpperCase());
      if(me.user.role==='admin'){const profile=document.querySelector('.user-profile-menu');if(profile){const btn=document.createElement('button');btn.className='btn btn-sm btn-light border';btn.textContent='User accounts';btn.onclick=()=>ModuleUI.accounts();profile.append(btn);}}
      document.querySelectorAll('a[href="login.html"],#logoutBtn').forEach(el=>el.onclick=async e=>{e.preventDefault();try{await this.request('logout',{});location.href='login.html';}catch(err){this.showToast(err.message,'danger');}});
      document.querySelectorAll('a[href="#"]').forEach(el=>{if(el.id!=='logoutBtn'){el.textContent='Change password';el.onclick=e=>{e.preventDefault();ModuleUI.password();};}});
      document.querySelectorAll('.sidebar-link .badge').forEach(el=>el.remove());
      const profile=document.querySelector('.user-profile-menu');if(profile){const button=document.createElement('button');button.className='btn btn-sm btn-light border';button.textContent='Change password';button.onclick=()=>ModuleUI.password();profile.append(button);}
      document.querySelectorAll('.sidebar-toggle-btn').forEach(el=>el.onclick=()=>{const sidebar=document.getElementById('sidebar');if(innerWidth<992)sidebar.classList.toggle('active');else sidebar.classList.toggle('collapsed');});
      const tick=()=>{const el=document.getElementById('eocClock');if(el)el.textContent=new Date().toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST';};tick();setInterval(tick,1000);
      if(document.getElementById('moduleRoot'))await ModuleUI.init();
      else if(document.getElementById('reportsRoot'))await ModuleUI.reports();
      else if(document.getElementById('metricActiveDisasters')){
        const data=await this.request('dashboard');
        // Old dashboard templates insert strings as HTML; escape every database string first.
        const clean=v=>typeof v==='string'?ModuleUI.escape(v):Array.isArray(v)?v.map(clean):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).map(([k,x])=>[k,clean(x)])):v;
        window.Relief360Data=clean(data);DashboardController.init();
        const banner=document.querySelector('.active-disaster-banner');if(banner)banner.textContent='Live database · '+data.metrics.activeDisasters+' active disasters · demonstration records are labeled Demo';
        const feed=document.getElementById('recentActivityFeed');if(feed)feed.innerHTML='<li class="p-3 text-muted">All totals reflect saved records. View operational pages for transaction history.</li>';
        const counter=document.querySelector('.active-incident-badge');if(counter)counter.textContent='Live relief operations';
      }
    }catch(e){this.showToast(e.message,'danger');}
  },
  showToast(message,type='info'){let el=document.getElementById('notice');if(!el){el=document.createElement('div');el.id='notice';document.body.append(el);}el.className='notice '+type;el.textContent=message;el.hidden=false;clearTimeout(this.timer);this.timer=setTimeout(()=>el.hidden=true,6000);}
};
document.addEventListener('DOMContentLoaded',()=>Relief360App.init());

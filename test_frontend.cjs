// Lightweight DOM-stub checks for page rendering. Not a browser visual test.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const modules=['disasters','camps','victims','missing-persons','volunteers','donations','inventory','distribution','medical','vehicles','alerts'];
for(const module of modules){
 const nodes={};const document={getElementById(id){return nodes[id]??={innerHTML:'',onclick:null};},querySelectorAll(){return[];}};
 const context={document,location:{pathname:'/'+module+'.html'},Relief360App:{permissions:modules,request:async()=>[],showToast(){}}};vm.createContext(context);
 vm.runInContext(fs.readFileSync(__dirname+'/js/modules.js','utf8')+';globalThis.UI=ModuleUI',context);const ui=context.UI;
 ui.data=[Object.fromEntries(ui.columns[module].map(k=>[k,k==='items'?[{item_name:'<script>bad</script>',quantity:1,unit:'kits'}]:k==='amount'?12345:k==='low_stock'?1:'<img src=x onerror=bad()>']))];
 ui.data[0][ui.keys[module]]=1;ui.render();assert(nodes.moduleRoot.innerHTML.includes('Search records'));assert(!nodes.liveRows.innerHTML.includes('<img src=x'));assert(!nodes.liveRows.innerHTML.includes('<script>bad'));
 for(const field of ui.fields[module]){const html=ui.field(field);assert(html.includes('name="'+field[0]+'"'));assert(html.includes('for="field_'+field[0]+'"'));}
 const page=fs.readFileSync(__dirname+'/'+module+'.html','utf8');assert(page.includes('id="moduleRoot"'));assert(!page.includes('mockData.js'));assert(!/<script>/.test(page));
}
const context={document:{addEventListener(){}},location:{},fetch(){},setTimeout,clearTimeout};vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/js/app.js','utf8')+';globalThis.App=Relief360App',context);
(async()=>{context.App.csrf='test';let captured;context.fetch=async(url,opts)=>{captured={url,opts};return{ok:true,status:201,json:async()=>({ok:true})};};await context.App.request('inventory',{quantity:1});assert(captured.opts.headers['X-CSRF-Token']==='test');assert(captured.url==='/api/inventory');assert(captured.opts.method==='POST');console.log('PASS: 11 module renderings, form field mapping, escaped database values and API request wiring.');})().catch(e=>{console.error(e);process.exit(1);});

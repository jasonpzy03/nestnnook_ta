const ts=require('../frontend/node_modules/typescript');
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
let fetchImpl;const exportsObject={};
const source=ts.transpileModule(fs.readFileSync('frontend/src/portfolio.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,experimentalDecorators:true}}).outputText;
class Emitter{count=0;emit(){this.count++;}}
vm.runInNewContext(source,{exports:exportsObject,require:name=>name==='@angular/core'?{Component:()=>()=>{},Input:()=>()=>{},Output:()=>()=>{},EventEmitter:Emitter}:name==='./language'?{translate:text=>text}:{},fetch:(...args)=>fetchImpl(...args),console,Date,Intl,Error});
const {Portfolio}=exportsObject;
const response=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
const seed={unit:'16-03',room:'02',rent:1200,parking:150,start_date:'2026-10-25',last_rental_date:'2027-04-30',active:true};

(async()=>{
  const capture=new Portfolio();capture.mode='capture';capture.seed=seed;capture.ngOnInit();
  assert.equal(capture.editor,'room');assert.equal(capture.rental.rent,1200);assert.notEqual(capture.rental,seed);
  let calls=[];
  const existing={...seed,kind:'room',id:'room-id',revision:'v1',rent:1000};
  fetchImpl=async(url,options)=>{calls.push({url,...options});return response({detail:{message:'Review existing record',record:existing}},409);};
  await capture.save();
  assert.equal(capture.saved.count,0);assert.equal(capture.rental.rent,1200);assert.equal(capture.conflict.rent,1000);
  assert.equal(calls[0].method,'POST');assert(!('revision' in JSON.parse(calls[0].body)));
  fetchImpl=async(url,options)=>{calls.push({url,...options});return response({...seed,kind:'room',id:'room-id',revision:'v2'});};
  await capture.save(true);
  assert.equal(calls[1].method,'PUT');assert.equal(calls[1].url,'/api/portfolio/rooms/room-id');
  assert.equal(JSON.parse(calls[1].body).revision,'v1');assert.equal(JSON.parse(calls[1].body).rent,1200);
  assert.equal(capture.saved.count,1);

  const failed=new Portfolio();failed.mode='capture';failed.seed=seed;failed.ngOnInit();
  fetchImpl=async()=>response({detail:'Storage unavailable'},503);
  await failed.save();assert.equal(failed.saved.count,0);assert.equal(failed.error,'Storage unavailable');assert.equal(failed.rental.rent,1200);
  failed.cancel();assert.equal(failed.cancelled.count,1);

  const ongoing=new Portfolio();ongoing.mode='capture';ongoing.ngOnInit();ongoing.rental={...seed,start_date:'',last_rental_date:'',parking:null};
  let resolveSave;calls=[];
  fetchImpl=(url,options)=>{calls.push({url,...options});return new Promise(resolve=>resolveSave=resolve);};
  const pending=ongoing.save();await ongoing.save();assert.equal(calls.length,1,'Ignore double taps while saving');
  const body=JSON.parse(calls[0].body);assert.equal(body.start_date,null);assert.equal(body.last_rental_date,null);assert.equal(body.parking,0);
  resolveSave(response({}));await pending;

  const dashboard=new Portfolio();const pendingLoads=[];
  fetchImpl=url=>new Promise(resolve=>pendingLoads.push({url,resolve}));
  dashboard.month='2026-10';const oct=dashboard.load();dashboard.month='2026-11';const nov=dashboard.load();
  pendingLoads[1].resolve(response({month:'2026-11',net_income:200}));await nov;
  pendingLoads[0].resolve(response({month:'2026-10',net_income:100}));await oct;
  assert.equal(dashboard.data.month,'2026-11','Slow previous requests must not overwrite selected month');
  fetchImpl=async()=>response({detail:'Unavailable'},503);await dashboard.load();assert.equal(dashboard.data,null,'Do not leave stale totals visible after failed refresh');
  dashboard.month='';await dashboard.load();assert.equal(dashboard.error,'Choose a valid month.');

  const removing=new Portfolio();removing.removal=existing;calls=[];
  fetchImpl=async(url,options)=>{calls.push({url,...options});return response({detail:'This record was changed'},409);};
  await removing.remove();assert.equal(calls[0].method,'DELETE');assert(calls[0].url.endsWith('?revision=v1'));assert.equal(removing.error,'This record was changed');
  console.log('Portfolio capture, explicit duplicate updates, save errors, double-tap protection, monthly refresh races and revision-aware removal passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});

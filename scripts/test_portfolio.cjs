const ts=require('../frontend/node_modules/typescript');
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
let fetchImpl;const exportsObject={};
const source=ts.transpileModule(fs.readFileSync('frontend/src/portfolio.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,experimentalDecorators:true}}).outputText;
class Emitter{count=0;emit(){this.count++;}}
vm.runInNewContext(source,{exports:exportsObject,require:name=>name==='@angular/core'?{Component:()=>()=>{},Optional:()=>()=>{},Input:()=>()=>{},Output:()=>()=>{},EventEmitter:Emitter}:name==='./language'?{translate:text=>text}:{},fetch:(...args)=>fetchImpl(...args),console,Date,Intl,Error});
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
  const inventory=new Portfolio();inventory.editProperty();inventory.bedroomCount=3;inventory.resizeBedrooms();
  assert.equal(inventory.property.rooms.length,3);inventory.property.rooms[0].standard_rent=1000;
  inventory.bedroomCount=1;inventory.resizeBedrooms();assert.equal(inventory.property.rooms.length,3,'Reducing count must not silently discard entered rooms');
  inventory.removePropertyRoom(1);assert.equal(inventory.bedroomCount,2);assert.equal(inventory.property.rooms[0].standard_rent,1000);
  inventory.property.standard_parking_rent=250;inventory.property.unit='A';inventory.property.rooms[1].standard_rent=800;calls=[];
  fetchImpl=async(url,options)=>{calls.push({url,...options});return response(options?{}:{units:[]});};
  await inventory.save();assert.equal(calls[0].url,'/api/portfolio/units');assert.equal(JSON.parse(calls[0].body).rooms.length,2);assert.equal(JSON.parse(calls[0].body).standard_parking_rent,250);
  const property={id:'unit-id',revision:'p1',kind:'unit',unit:'A',property_name:'Test',address:'Street',bathrooms:1,carparks:1,notes:'',rooms:[{room:'1',standard_rent:900}],occupancy_rate:50,vacancy_loss:450,bedrooms:1,room_rows:[]};
  inventory.editProperty(property);assert.equal(inventory.property.standard_parking_rent,null,'Older units need an advertised parking price');inventory.property.rooms[0].standard_rent=950;assert.equal(property.rooms[0].standard_rent,900,'Editing must not mutate loaded records');
  calls=[];await inventory.save();assert.equal(calls[0].method,'PUT');assert.equal(JSON.parse(calls[0].body).revision,'p1');
  inventory.data={units:[property],occupancy_rate:25,vacancy_loss:900,total_bedrooms:2,total_carparks:3};
  assert.equal(inventory.occupancySummary.bedrooms,2);inventory.unitFilter='unit-id';assert.equal(inventory.visibleUnits.length,0);inventory.mode='properties';inventory.openUnit('unit-id');assert.equal(inventory.visibleUnits.length,1);assert.equal(inventory.occupancySummary.occupancy_rate,50);
  inventory.data.rooms=[{...existing,unit:' Unit A ',room:'1'}];assert.equal(inventory.unitRentals.length,1);inventory.search='street';assert.equal(inventory.filteredProperties.length,1);inventory.search='missing';assert.equal(inventory.filteredProperties.length,0);inventory.addUnitRental();assert.equal(inventory.rental.unit,'A');inventory.backToUnits();assert.equal(inventory.selectedUnitId,'');
  inventory.assignRental(property,{room:'1',standard_rent:900,rental:null});assert.equal(inventory.rental.unit,'A');assert.equal(inventory.rental.rent,900);
  inventory.assignRental(property,{rental:{...existing,tenant_name:'Alex'}});assert.equal(inventory.editId,existing.id);assert.equal(inventory.rental.tenant_name,'Alex');
  const costs=new Portfolio();costs.month='2026-10';
  const costProperty={...property,fixed_costs:{house_rental:'1000',wifi:'100',indah_water:'8'},monthly_costs:{'2026-09':{electricity:'80',water:'20',others:[{name:'Repair',amount:'50'}]}}};
  costs.editProperty(costProperty);assert.equal(costs.property.fixed_costs.house_rental,1000);assert.equal(costs.monthlyCosts.electricity,null);assert.equal(costs.othersReviewed,false);
  assert.equal(costs.monthlyCosts.cleaning,null);costs.monthlyCosts.cleaning=45.50;costs.monthlyCosts.electricity=120;costs.monthlyCosts.water=0;costs.addOtherCost();costs.otherCosts[0]={name:'Cleaning',amount:30};calls=[];
  await costs.save();let savedCosts=JSON.parse(calls[0].body);
  assert.equal(savedCosts.monthly_costs['2026-09'].others[0].amount,'50');assert.equal(savedCosts.monthly_costs['2026-10'].others[0].name,'Cleaning');assert.equal(savedCosts.monthly_costs['2026-10'].water,0);assert.equal(savedCosts.monthly_costs['2026-10'].cleaning,45.50);
  assert(!costProperty.monthly_costs['2026-10'],'Editing must not mutate the saved history');
  costs.month='2026-09';costs.editProperty(costProperty);assert.equal(costs.monthlyCosts.electricity,80);assert.equal(costs.otherCosts[0].amount,50);
  costs.removeOtherCost(0);assert.equal(costs.othersReviewed,false);costs.othersReviewed=true;
  // A reviewed stale update keeps another staff member's edits to other months.
  costs.conflict={...costProperty,revision:'p2',monthly_costs:{...costProperty.monthly_costs,'2026-11':{electricity:200,water:10,others:[]}}};calls=[];
  await costs.save(true);savedCosts=JSON.parse(calls[0].body);
  assert.equal(savedCosts.revision,'p2');assert.equal(savedCosts.monthly_costs['2026-11'].electricity,200);assert.equal(savedCosts.monthly_costs['2026-09'].others.length,0);
  costs.month='2026-12';costs.editProperty(costProperty);calls=[];await costs.save();savedCosts=JSON.parse(calls[0].body);
  assert.equal(savedCosts.monthly_costs['2026-12'].electricity,null);assert.equal(savedCosts.monthly_costs['2026-12'].others,null,'Unentered costs must remain missing, not confirmed zero');
  const correction=new Portfolio();correction.editRoom(existing);correction.rental.unit='Corrected';calls=[];
  fetchImpl=async(url,options)=>{calls.push({url,...options});return response({detail:'A rental already exists for the corrected unit and room. No records were changed.'},409);};
  await correction.save();assert.equal(calls[0].url,'/api/portfolio/rooms/room-id');assert.equal(JSON.parse(calls[0].body).unit,'Corrected');
  assert.equal(correction.conflict,null,'A destination collision must not offer to replace the other rental');assert.equal(correction.rental.unit,'Corrected');
  console.log('Portfolio capture, explicit duplicate updates, save errors, double-tap protection, monthly refresh races and revision-aware removal passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});

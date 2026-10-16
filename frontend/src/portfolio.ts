import { Component, Input, Output, EventEmitter, OnInit, OnDestroy, OnChanges, Optional } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzI18nService, en_GB, zh_CN } from 'ng-zorro-antd/i18n';
import { DateInput, displayDate } from './date-input';
import { Language, translate } from './language';

export interface RentalInput {security_deposit?:number|null;access_deposit?:number|null; unit:string; room:string; rent:number|null; parking:number|null; start_date:string; last_rental_date:string; active:boolean; tenant_name?:string; }
interface ParkingInput {carpark_deposit?:number|null;unit:string;space:string;rent:number|null;start_date:string;last_rental_date:string;active:boolean;tenant_name:string;}
interface ParkingRecord extends ParkingInput {id:string;revision:string;kind:'parking';rent:number;expected:number;rental_days:number;}
interface FixedCosts {house_rental:number|null;wifi:number|null;indah_water:number|null;}
interface MonthlyCosts {cleaning:number|null;electricity:number|null;water:number|null;others:{name:string;amount:number|null}[]|null;}
export interface PropertyInput {standard_parking_rent:number|null;fixed_costs:FixedCosts;monthly_costs:Record<string,MonthlyCosts>;unit:string; property_name:string; address:string; bathrooms:number; carparks:number; notes:string; rooms:{room:string;standard_rent:number|null}[];}
export interface PropertyRecord extends Omit<PropertyInput,'fixed_costs'|'monthly_costs'> {id:string;revision:string;kind:'unit';fixed_costs?:FixedCosts;monthly_costs?:Record<string,MonthlyCosts>;}
interface OccupancyRoom {id:string;room:string;standard_rent:number;tenant_name:string;rental:RentalRecord|null;occupied_days:number;vacant_days:number;vacancy_loss:number;expected_income:number;}
interface UnitProjection extends PropertyRecord {parking_rate_missing:boolean;parking_over_capacity:boolean;fixed_costs:FixedCosts;selected_month_costs:MonthlyCosts;fixed_expenses:number;variable_expenses:number;total_expenses:number;net_income:number;missing_expenses:string[];bedrooms:number;room_rows:OccupancyRoom[];occupied_room_days:number;available_room_days:number;occupancy_rate:number;vacancy_loss:number;potential_room_rent:number;expected_income:number;}
interface RentalRecord extends RentalInput {id:string; revision:string; kind:'room'; rent:number; parking:number; expected:number; rental_days:number;}
interface ExpenseRecord {id:string; revision:string; kind:'expense'; name:string; amount:number;}
interface Projection {parking:ParkingRecord[];earning_parking:number;parking_rate_missing_units:number;variable_expenses:number;total_expenses:number;missing_expense_units:number;month:string; rooms:RentalRecord[]; expenses:ExpenseRecord[]; rental_income:number; fixed_expenses:number; net_income:number; earning_rooms:number;units:UnitProjection[];total_bedrooms:number;total_carparks:number;occupancy_rate:number|null;vacancy_loss:number;unlinked_rentals:number;occupied_room_days:number;available_room_days:number;}
const emptyRental=():RentalInput=>({security_deposit:null,access_deposit:null,unit:'',room:'',rent:null,parking:0,start_date:'',last_rental_date:'',active:true,tenant_name:''});
const emptyParking=():ParkingInput=>({carpark_deposit:null,unit:'',space:'',rent:null,start_date:'',last_rental_date:'',active:true,tenant_name:''});
const emptyMonthly=():MonthlyCosts=>({electricity:null,water:null,cleaning:null,others:null});
const emptyProperty=():PropertyInput=>({standard_parking_rent:null,fixed_costs:{house_rental:0,wifi:0,indah_water:0},monthly_costs:{},unit:'',property_name:'',address:'',bathrooms:0,carparks:0,notes:'',rooms:[{room:'01',standard_rent:null}]});

@Component({selector:'rental-portfolio',standalone:true,imports:[CommonModule,FormsModule,NzTableModule,DateInput],templateUrl:'./portfolio.html'})
export class Portfolio implements OnInit, OnDestroy, OnChanges {
  constructor(@Optional() private i18n:NzI18nService|null=null){}
  ngOnChanges(){this.i18n?.setLocale(this.language==='zh'?zh_CN:en_GB);}
  @Input() language:Language='en';
  @Input() addresses:string[]=[];
  @Input() addressError='';
  @Input() mode:'dashboard'|'properties'|'capture'='dashboard';
  @Input() seed:RentalInput|null=null;
  @Output() saved=new EventEmitter<void>();
  @Output() cancelled=new EventEmitter<void>();
  month=(()=>{const parts=new Intl.DateTimeFormat('en',{timeZone:'Asia/Singapore',year:'numeric',month:'2-digit'}).formatToParts(new Date());return parts.find(p=>p.type==='year')!.value+'-'+parts.find(p=>p.type==='month')!.value;})();
  data:Projection|null=null; loading=false; saving=false; error=''; notice='';
  editor:''|'room'|'parking'|'expense'|'unit'=''; rental=emptyRental(); parking=emptyParking(); expense={name:'',amount:null as number|null}; property=emptyProperty(); bedroomCount=1;
  unitFilter=''; selectedUnitId=''; search=''; showUnlinked=false;
  displayDate=displayDate;
  get selectedUnit(){return this.data?.units.find(u=>u.id===this.selectedUnitId);}
  get filteredProperties(){const query=this.search.trim().toLowerCase();return (this.data?.units||[]).filter(u=>(u.unit+' '+u.address).toLowerCase().includes(query));}
  get unitRentals(){if(this.showUnlinked){const ids=new Set(this.data?.units.flatMap(u=>u.room_rows.map(r=>r.id)));return (this.data?.rooms||[]).filter(r=>!ids.has(r.id));}return (this.data?.rooms||[]).filter(r=>this.normaliseUnit(r.unit)===this.normaliseUnit(this.selectedUnit?.unit||''));}
  get unitParking(){return (this.data?.parking||[]).filter(r=>this.normaliseUnit(r.unit)===this.normaliseUnit(this.selectedUnit?.unit||''));}
  editParking(row?:ParkingRecord){
    this.clearEditor();this.editor='parking';this.parking={...emptyParking(),unit:this.selectedUnit?.unit||'',rent:this.selectedUnit?.standard_parking_rent??null};
    if(row){this.parking={carpark_deposit:row.carpark_deposit==null?null:Number(row.carpark_deposit),unit:this.data?.units.find(u=>this.normaliseUnit(u.unit)===this.normaliseUnit(row.unit))?.unit||row.unit,space:row.space,rent:Number(row.rent),start_date:row.start_date||'',last_rental_date:row.last_rental_date||'',active:row.active,tenant_name:row.tenant_name||''};this.editId=row.id;this.revision=row.revision;}
    this.focusEditor();
  }
  depositTotal(row:RentalInput|ParkingInput):number|null{const amounts='space' in row?[row.carpark_deposit]:[row.security_deposit,row.access_deposit];return amounts.some(amount=>amount==null)?null:Math.round(amounts.reduce<number>((sum,amount)=>sum+Number(amount),0)*100)/100;}
  normaliseUnit(value:string){return value.trim().replace(/^(?:unit\s+|#)/i,'').replace(/\s+/g,'').toLowerCase();}
  openUnit(id:string){this.clearEditor();this.selectedUnitId=id;this.showUnlinked=false;}
  backToUnits(){this.clearEditor();this.selectedUnitId='';this.showUnlinked=false;}
  addUnitRental(){this.editRoom();this.rental.unit=this.selectedUnit?.unit||'';}

  expenseMonth=''; monthlyCosts=emptyMonthly(); otherCosts:{name:string;amount:number|null}[]=[]; othersReviewed=false;
  fixedCostFields:{key:keyof FixedCosts;label:string}[]=[{key:'house_rental',label:'House Rental'},{key:'wifi',label:'WIFI'},{key:'indah_water',label:'Indah Water (sewerage)'}];
  editId=''; revision=''; conflict:RentalRecord|ParkingRecord|ExpenseRecord|PropertyRecord|null=null;
  removal:RentalRecord|ParkingRecord|ExpenseRecord|PropertyRecord|null=null;
  private loadVersion=0; private destroyed=false;
  t(value:string){return translate(value,this.language);}
  get visibleUnits(){return this.mode==='properties'&&this.selectedUnit?[this.selectedUnit]:[];}
  get occupancySummary(){const unit=this.data?.units?.find(u=>u.id===this.unitFilter);return unit?{occupancy_rate:unit.occupancy_rate,vacancy_loss:unit.vacancy_loss,bedrooms:unit.bedrooms,carparks:unit.carparks}:{occupancy_rate:this.data?.occupancy_rate??null,vacancy_loss:this.data?.vacancy_loss||0,bedrooms:this.data?.total_bedrooms||0,carparks:this.data?.total_carparks||0};}
  editProperty(row?:PropertyRecord){
    this.clearEditor();this.editor='unit';this.expenseMonth=this.month;this.focusEditor();
    if(row){
      const costs=row.fixed_costs||{house_rental:0,wifi:0,indah_water:0};
      this.property={standard_parking_rent:row.standard_parking_rent==null?null:Number(row.standard_parking_rent),unit:row.unit,property_name:row.property_name,address:row.address,bathrooms:row.bathrooms,carparks:row.carparks,notes:row.notes,
        fixed_costs:{house_rental:Number(costs.house_rental),wifi:Number(costs.wifi),indah_water:Number(costs.indah_water)},
        monthly_costs:JSON.parse(JSON.stringify(row.monthly_costs||{})),rooms:row.rooms.map(r=>({...r,standard_rent:Number(r.standard_rent)}))};
      this.bedroomCount=row.rooms.length;this.editId=row.id;this.revision=row.revision;
      const monthly=this.property.monthly_costs[this.expenseMonth]||emptyMonthly();
      this.monthlyCosts={cleaning:monthly.cleaning==null?null:Number(monthly.cleaning),electricity:monthly.electricity===null?null:Number(monthly.electricity),water:monthly.water===null?null:Number(monthly.water),others:null};
      this.otherCosts=(monthly.others||[]).map(item=>({name:item.name,amount:Number(item.amount)}));this.othersReviewed=monthly.others!==null;
    }
  }
  addOtherCost(){if(this.otherCosts.length<50){this.otherCosts.push({name:'',amount:null});this.othersReviewed=true;this.conflict=null;}}
  removeOtherCost(index:number){this.otherCosts.splice(index,1);if(!this.otherCosts.length)this.othersReviewed=false;this.conflict=null;}
  expenseLabel(key:string){return ({electricity:'Electricity',water:'Water',cleaning:'Cleaning fees',others:'Others'} as Record<string,string>)[key]||key;}
  focusEditor(){if(typeof requestAnimationFrame==='function')requestAnimationFrame(()=>document.querySelector<HTMLElement>('.portfolio-editor')?.scrollIntoView({behavior:'smooth',block:'start'}));}
  resizeBedrooms(){
    const count=Number(this.bedroomCount);if(!Number.isInteger(count)||count<1||count>30)return;
    // Keep entered rows until staff explicitly remove them; reducing a count must not discard values.
    while(this.property.rooms.length<count){let number=this.property.rooms.length+1;while(number===4||this.property.rooms.some(r=>Number(r.room.replace(/^(?:room\s*|r)/i,''))===number))number++;this.property.rooms.push({room:String(number).padStart(2,'0'),standard_rent:null});}
    this.bedroomCount=this.property.rooms.length;this.conflict=null;
  }
  removePropertyRoom(index:number){if(this.property.rooms.length>1){this.property.rooms.splice(index,1);this.bedroomCount=this.property.rooms.length;this.conflict=null;}}
  assignRental(unit:UnitProjection,room:OccupancyRoom){if(room.rental){this.editRoom(room.rental);}else{this.editRoom();this.rental={...emptyRental(),unit:unit.unit,room:room.room,rent:room.standard_rent};}}
  ngOnInit(){if(this.mode==='capture'){this.rental={...emptyRental(),...this.seed};this.editor='room';}else void this.load();}
  ngOnDestroy(){this.destroyed=true;this.loadVersion++;}
  async request(path:string,options?:RequestInit):Promise<any>{
    const response=await fetch('/api/portfolio'+path,options);
    const body=await response.json().catch(()=>({}));
    if(!response.ok){
      if(response.status===409&&body.detail?.record)this.conflict=body.detail.record;
      throw Error(typeof body.detail==='string'?body.detail:typeof body.detail?.message==='string'?body.detail.message:
        Array.isArray(body.detail)&&body.detail[0]?.msg?body.detail[0].msg.replace(/^Value error, /,''):response.status===422?'Check the amounts and dates, then try again.':'Rental portfolio is unavailable. Please try again.');
    }
    return body;
  }
  async load(){
    const version=++this.loadVersion;this.error='';this.loading=true;this.data=null;
    if(!/^(?:19|[2-9]\d)\d{2}-(?:0[1-9]|1[0-2])$/.test(this.month)){this.error='Choose a valid month.';this.loading=false;return;}
    try{const result=await this.request('?month='+this.month);if(version===this.loadVersion){this.data=result;if(this.selectedUnitId&&!result.units?.some((u:PropertyRecord)=>u.id===this.selectedUnitId))this.selectedUnitId='';if(this.unitFilter&&!result.units?.some((u:PropertyRecord)=>u.id===this.unitFilter))this.unitFilter='';}}
    catch(e){if(version===this.loadVersion)this.error=e instanceof Error?e.message:'Rental portfolio is unavailable. Please try again.';}
    finally{if(version===this.loadVersion)this.loading=false;}
  }
  editRoom(row?:RentalRecord){
    this.clearEditor();this.editor='room';this.focusEditor();
    if(row){this.rental={security_deposit:row.security_deposit==null?null:Number(row.security_deposit),access_deposit:row.access_deposit==null?null:Number(row.access_deposit),unit:row.unit,room:row.room,rent:Number(row.rent),parking:Number(row.parking),start_date:row.start_date||'',last_rental_date:row.last_rental_date||'',active:row.active,tenant_name:row.tenant_name||''};this.editId=row.id;this.revision=row.revision;}
  }
  editExpense(row?:ExpenseRecord){this.clearEditor();this.editor='expense';this.focusEditor();if(row){this.expense={name:row.name,amount:Number(row.amount)};this.editId=row.id;this.revision=row.revision;}}
  clearEditor(){this.monthlyCosts=emptyMonthly();this.otherCosts=[];this.othersReviewed=false;this.expenseMonth='';this.editor='';this.rental=emptyRental();this.parking=emptyParking();this.expense={name:'',amount:null};this.property=emptyProperty();this.bedroomCount=1;this.editId='';this.revision='';this.conflict=null;this.error='';this.notice='';this.removal=null;}
  cancel(){if(this.saving)return;this.clearEditor();if(this.mode==='capture')this.cancelled.emit();}
  async save(replace=false){
    if(this.saving)return;
    const conflict=replace?this.conflict:null;
    if(replace&&!conflict)return;
    const collection=this.editor==='parking'?'parking':this.editor==='room'?'rooms':this.editor==='unit'?'units':'expenses';
    const id=conflict?.id||this.editId;const revision=conflict?.revision||this.revision;
    if(this.editor==='unit'){
      const history=conflict?.kind==='unit'?conflict.monthly_costs:this.property.monthly_costs;
      this.property.monthly_costs={...(history||{}),[this.expenseMonth]:{cleaning:this.monthlyCosts.cleaning??null,electricity:this.monthlyCosts.electricity??null,water:this.monthlyCosts.water??null,others:this.othersReviewed?this.otherCosts.map(item=>({...item})):null}};
    }
    const payload=this.editor==='parking'?{...this.parking,start_date:this.parking.start_date||null,last_rental_date:this.parking.last_rental_date||null}:this.editor==='room'?{...this.rental,parking:this.rental.parking??0,start_date:this.rental.start_date||null,last_rental_date:this.rental.last_rental_date||null}:this.editor==='unit'?{...this.property}:{...this.expense};
    this.saving=true;this.error='';this.conflict=null;
    try{
      await this.request('/'+collection+(id?'/'+id:''),{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,...(id?{revision}:{})})});
      if(this.destroyed)return;
      this.clearEditor();this.notice='Rental portfolio saved.';
      if(this.mode==='capture')this.saved.emit();else await this.load();
    }catch(e){if(!this.destroyed)this.error=e instanceof Error?e.message:'Could not save the rental portfolio. Please try again.';}
    finally{this.saving=false;}
  }
  async remove(){
    if(!this.removal||this.saving)return;
    const row=this.removal;this.saving=true;this.error='';this.conflict=null;
    try{await this.request('/'+(row.kind==='parking'?'parking':row.kind==='room'?'rooms':row.kind==='unit'?'units':'expenses')+'/'+row.id+'?revision='+encodeURIComponent(row.revision),{method:'DELETE'});
      this.removal=null;this.notice='Record removed.';await this.load();
    }catch(e){this.removal=null;this.conflict=null;this.error=e instanceof Error?e.message:'Could not save the rental portfolio. Please try again.';}
    finally{this.saving=false;}
  }
}

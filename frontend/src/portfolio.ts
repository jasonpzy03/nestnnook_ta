import { Component, Input, Output, EventEmitter, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Language, translate } from './language';

export interface RentalInput { unit:string; room:string; rent:number|null; parking:number|null; start_date:string; last_rental_date:string; active:boolean; tenant_name?:string; }
export interface PropertyInput {unit:string; property_name:string; address:string; bathrooms:number; carparks:number; notes:string; rooms:{room:string;standard_rent:number|null}[];}
export interface PropertyRecord extends PropertyInput {id:string;revision:string;kind:'unit';}
interface OccupancyRoom {id:string;room:string;standard_rent:number;tenant_name:string;rental:RentalRecord|null;occupied_days:number;vacant_days:number;vacancy_loss:number;expected_income:number;}
interface UnitProjection extends PropertyRecord {bedrooms:number;room_rows:OccupancyRoom[];occupied_room_days:number;available_room_days:number;occupancy_rate:number;vacancy_loss:number;potential_room_rent:number;expected_income:number;}
interface RentalRecord extends RentalInput {id:string; revision:string; kind:'room'; rent:number; parking:number; expected:number; rental_days:number;}
interface ExpenseRecord {id:string; revision:string; kind:'expense'; name:string; amount:number;}
interface Projection {month:string; rooms:RentalRecord[]; expenses:ExpenseRecord[]; rental_income:number; fixed_expenses:number; net_income:number; earning_rooms:number;units:UnitProjection[];total_bedrooms:number;total_carparks:number;occupancy_rate:number|null;vacancy_loss:number;unlinked_rentals:number;occupied_room_days:number;available_room_days:number;}
const emptyRental=():RentalInput=>({unit:'',room:'',rent:null,parking:0,start_date:'',last_rental_date:'',active:true,tenant_name:''});
const emptyProperty=():PropertyInput=>({unit:'',property_name:'',address:'',bathrooms:0,carparks:0,notes:'',rooms:[{room:'01',standard_rent:null}]});

@Component({selector:'rental-portfolio',standalone:true,imports:[CommonModule,FormsModule],templateUrl:'./portfolio.html'})
export class Portfolio implements OnInit, OnDestroy {
  @Input() language:Language='en';
  @Input() addresses:string[]=[];
  @Input() addressError='';
  @Input() mode:'dashboard'|'capture'='dashboard';
  @Input() seed:RentalInput|null=null;
  @Output() saved=new EventEmitter<void>();
  @Output() cancelled=new EventEmitter<void>();
  month=(()=>{const parts=new Intl.DateTimeFormat('en',{timeZone:'Asia/Singapore',year:'numeric',month:'2-digit'}).formatToParts(new Date());return parts.find(p=>p.type==='year')!.value+'-'+parts.find(p=>p.type==='month')!.value;})();
  data:Projection|null=null; loading=false; saving=false; error=''; notice='';
  editor:''|'room'|'expense'|'unit'=''; rental=emptyRental(); expense={name:'',amount:null as number|null}; property=emptyProperty(); bedroomCount=1;
  unitFilter='';
  editId=''; revision=''; conflict:RentalRecord|ExpenseRecord|PropertyRecord|null=null;
  removal:RentalRecord|ExpenseRecord|PropertyRecord|null=null;
  private loadVersion=0; private destroyed=false;
  t(value:string){return translate(value,this.language);}
  get visibleUnits(){return this.data?.units?.filter(u=>!this.unitFilter||u.id===this.unitFilter)||[];}
  get occupancySummary(){const unit=this.data?.units?.find(u=>u.id===this.unitFilter);return unit?{occupancy_rate:unit.occupancy_rate,vacancy_loss:unit.vacancy_loss,bedrooms:unit.bedrooms,carparks:unit.carparks}:{occupancy_rate:this.data?.occupancy_rate??null,vacancy_loss:this.data?.vacancy_loss||0,bedrooms:this.data?.total_bedrooms||0,carparks:this.data?.total_carparks||0};}
  editProperty(row?:PropertyRecord){this.clearEditor();this.editor='unit';this.focusEditor();if(row){this.property={unit:row.unit,property_name:row.property_name,address:row.address,bathrooms:row.bathrooms,carparks:row.carparks,notes:row.notes,rooms:row.rooms.map(r=>({...r,standard_rent:Number(r.standard_rent)}))};this.bedroomCount=row.rooms.length;this.editId=row.id;this.revision=row.revision;}}
  focusEditor(){if(typeof requestAnimationFrame==='function')requestAnimationFrame(()=>document.querySelector<HTMLElement>('.portfolio-editor')?.scrollIntoView({behavior:'smooth',block:'start'}));}
  resizeBedrooms(){
    const count=Number(this.bedroomCount);if(!Number.isInteger(count)||count<1||count>30)return;
    // Keep entered rows until staff explicitly remove them; reducing a count must not discard values.
    while(this.property.rooms.length<count){let number=this.property.rooms.length+1;while(this.property.rooms.some(r=>Number(r.room.replace(/^(?:room\s*|r)/i,''))===number))number++;this.property.rooms.push({room:String(number).padStart(2,'0'),standard_rent:null});}
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
    try{const result=await this.request('?month='+this.month);if(version===this.loadVersion){this.data=result;if(this.unitFilter&&!result.units?.some((u:PropertyRecord)=>u.id===this.unitFilter))this.unitFilter='';}}
    catch(e){if(version===this.loadVersion)this.error=e instanceof Error?e.message:'Rental portfolio is unavailable. Please try again.';}
    finally{if(version===this.loadVersion)this.loading=false;}
  }
  editRoom(row?:RentalRecord){
    this.clearEditor();this.editor='room';this.focusEditor();
    if(row){this.rental={unit:row.unit,room:row.room,rent:Number(row.rent),parking:Number(row.parking),start_date:row.start_date||'',last_rental_date:row.last_rental_date||'',active:row.active,tenant_name:row.tenant_name||''};this.editId=row.id;this.revision=row.revision;}
  }
  editExpense(row?:ExpenseRecord){this.clearEditor();this.editor='expense';this.focusEditor();if(row){this.expense={name:row.name,amount:Number(row.amount)};this.editId=row.id;this.revision=row.revision;}}
  clearEditor(){this.editor='';this.rental=emptyRental();this.expense={name:'',amount:null};this.property=emptyProperty();this.bedroomCount=1;this.editId='';this.revision='';this.conflict=null;this.error='';this.notice='';this.removal=null;}
  cancel(){if(this.saving)return;this.clearEditor();if(this.mode==='capture')this.cancelled.emit();}
  async save(replace=false){
    if(this.saving)return;
    const conflict=replace?this.conflict:null;
    if(replace&&!conflict)return;
    const collection=this.editor==='room'?'rooms':this.editor==='unit'?'units':'expenses';
    const id=conflict?.id||this.editId;const revision=conflict?.revision||this.revision;
    const payload=this.editor==='room'?{...this.rental,parking:this.rental.parking??0,start_date:this.rental.start_date||null,last_rental_date:this.rental.last_rental_date||null}:this.editor==='unit'?{...this.property}:{...this.expense};
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
    try{await this.request('/'+(row.kind==='room'?'rooms':row.kind==='unit'?'units':'expenses')+'/'+row.id+'?revision='+encodeURIComponent(row.revision),{method:'DELETE'});
      this.removal=null;this.notice='Record removed.';await this.load();
    }catch(e){this.removal=null;this.conflict=null;this.error=e instanceof Error?e.message:'Could not save the rental portfolio. Please try again.';}
    finally{this.saving=false;}
  }
}

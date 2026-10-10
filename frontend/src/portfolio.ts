import { Component, Input, Output, EventEmitter, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Language, translate } from './language';

export interface RentalInput { unit:string; room:string; rent:number|null; parking:number|null; start_date:string; last_rental_date:string; active:boolean; }
interface RentalRecord extends RentalInput {id:string; revision:string; kind:'room'; rent:number; parking:number; expected:number; rental_days:number;}
interface ExpenseRecord {id:string; revision:string; kind:'expense'; name:string; amount:number;}
interface Projection {month:string; rooms:RentalRecord[]; expenses:ExpenseRecord[]; rental_income:number; fixed_expenses:number; net_income:number; earning_rooms:number;}
const emptyRental=():RentalInput=>({unit:'',room:'',rent:null,parking:0,start_date:'',last_rental_date:'',active:true});

@Component({selector:'rental-portfolio',standalone:true,imports:[CommonModule,FormsModule],templateUrl:'./portfolio.html'})
export class Portfolio implements OnInit, OnDestroy {
  @Input() language:Language='en';
  @Input() mode:'dashboard'|'capture'='dashboard';
  @Input() seed:RentalInput|null=null;
  @Output() saved=new EventEmitter<void>();
  @Output() cancelled=new EventEmitter<void>();
  month=(()=>{const parts=new Intl.DateTimeFormat('en',{timeZone:'Asia/Singapore',year:'numeric',month:'2-digit'}).formatToParts(new Date());return parts.find(p=>p.type==='year')!.value+'-'+parts.find(p=>p.type==='month')!.value;})();
  data:Projection|null=null; loading=false; saving=false; error=''; notice='';
  editor:''|'room'|'expense'=''; rental=emptyRental(); expense={name:'',amount:null as number|null};
  editId=''; revision=''; conflict:RentalRecord|ExpenseRecord|null=null;
  removal:RentalRecord|ExpenseRecord|null=null;
  private loadVersion=0; private destroyed=false;
  t(value:string){return translate(value,this.language);}
  ngOnInit(){if(this.mode==='capture'){this.rental={...emptyRental(),...this.seed};this.editor='room';}else void this.load();}
  ngOnDestroy(){this.destroyed=true;this.loadVersion++;}
  async request(path:string,options?:RequestInit):Promise<any>{
    const response=await fetch('/api/portfolio'+path,options);
    const body=await response.json().catch(()=>({}));
    if(!response.ok){
      if(response.status===409&&body.detail?.record)this.conflict=body.detail.record;
      throw Error(typeof body.detail==='string'?body.detail:typeof body.detail?.message==='string'?body.detail.message:
        response.status===422?'Check the amounts and dates, then try again.':'Rental portfolio is unavailable. Please try again.');
    }
    return body;
  }
  async load(){
    const version=++this.loadVersion;this.error='';this.loading=true;this.data=null;
    if(!/^(?:19|[2-9]\d)\d{2}-(?:0[1-9]|1[0-2])$/.test(this.month)){this.error='Choose a valid month.';this.loading=false;return;}
    try{const result=await this.request('?month='+this.month);if(version===this.loadVersion)this.data=result;}
    catch(e){if(version===this.loadVersion)this.error=e instanceof Error?e.message:'Rental portfolio is unavailable. Please try again.';}
    finally{if(version===this.loadVersion)this.loading=false;}
  }
  editRoom(row?:RentalRecord){
    this.clearEditor();this.editor='room';
    if(row){this.rental={unit:row.unit,room:row.room,rent:Number(row.rent),parking:Number(row.parking),start_date:row.start_date||'',last_rental_date:row.last_rental_date||'',active:row.active};this.editId=row.id;this.revision=row.revision;}
  }
  editExpense(row?:ExpenseRecord){this.clearEditor();this.editor='expense';if(row){this.expense={name:row.name,amount:Number(row.amount)};this.editId=row.id;this.revision=row.revision;}}
  clearEditor(){this.editor='';this.rental=emptyRental();this.expense={name:'',amount:null};this.editId='';this.revision='';this.conflict=null;this.error='';this.notice='';this.removal=null;}
  cancel(){if(this.saving)return;this.clearEditor();if(this.mode==='capture')this.cancelled.emit();}
  async save(replace=false){
    if(this.saving)return;
    const conflict=replace?this.conflict:null;
    if(replace&&!conflict)return;
    const collection=this.editor==='room'?'rooms':'expenses';
    const id=conflict?.id||this.editId;const revision=conflict?.revision||this.revision;
    const payload=this.editor==='room'?{...this.rental,parking:this.rental.parking??0,start_date:this.rental.start_date||null,last_rental_date:this.rental.last_rental_date||null}:{...this.expense};
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
    try{await this.request('/'+(row.kind==='room'?'rooms':'expenses')+'/'+row.id+'?revision='+encodeURIComponent(row.revision),{method:'DELETE'});
      this.removal=null;this.notice='Record removed.';await this.load();
    }catch(e){this.removal=null;this.conflict=null;this.error=e instanceof Error?e.message:'Could not save the rental portfolio. Please try again.';}
    finally{this.saving=false;}
  }
}

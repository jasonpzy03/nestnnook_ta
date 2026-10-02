import { Component, OnInit, OnDestroy, HostListener } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { expiryDate } from './dates';


interface Field { key: string; label: string; type?: string; required?: boolean; placeholder?: string; wide?: boolean; }
interface Inventory { name: string; quantity: number; condition: string; remarks: string; }
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };
const inventoryNames = ['Bedframe / Divan','Mattress','Pillow','Makeup table','Chair','Plant decor','Curtain','Wardrobe','Wall decor frame','Rubbish bin','Blanket','Mattress cover','Air conditioner','Air conditioner remote','Ceiling fan','Fan remote','Access card','Room key','Main door key'];
const fresh = (): Record<string, any> => ({tenant_name:'',tenant_id:'',nationality:'Malaysian',phone:'',email:'',occupation:'',employer:'',vehicle:'',emergency_name:'',emergency_id:'',emergency_relationship:'',emergency_phone:'',guardian_name:'',guardian_id:'',property:'',room:'',address:'',agreement_date:today(),start_date:today(),end_date:'',aircon:true,rent:null,parking:null,security_deposit:null,access_deposit:null,advance_rent:null,agreement_fee:null,reference:'',special_conditions:'',room_condition:'Good',room_remarks:'',makeup_table_drawer:'not_applicable',meter_reading:'',include_aml:true,inventory:inventoryNames.map(name=>({name,quantity:1,condition:'Good',remarks:''})),company:{name:'NEST & NOOK PROPERTY CARE',registration:'202603156166 (KT0615852-M)',address:'#16-03, Trellis Residences, 80100, J.B, Johor.',contact:'Cheryl Pua',phone:'+60111-3380335',email:'pzhenying@gmail.com',bank:'OCBC BANK',account_name:'NEST & NOOK PROPERTY CARE',account_number:'7101403930'}});
@Component({selector:'app-root',standalone:true,imports:[CommonModule,FormsModule],templateUrl:'./app.html'})
export class App implements OnInit, OnDestroy {

  wordPdfAvailable=true;
  shareOpen=false; sharePreparing=false; sharing=false; shareMessage=''; shareError=''; shareFiles:File[]=[];
  private shareAbort?:AbortController;
  get canShareFiles(){return this.supportsShare(this.shareFiles);}
  supportsShare(files:File[]){try{return files.length>0&&typeof navigator.share==='function'&&typeof navigator.canShare==='function'&&navigator.canShare({files});}catch{return false;}}
  addresses:string[]=[]; newAddress=''; addingAddress=false; savingAddress=false; addressError=''; expiryMonths=0;
  d = fresh(); step=0; page='templates'; settings=false; resetPrompt=false; busy=false; status=''; error=''; format='pdf'; ready=false;
  previewUrl=''; previewPages:string[]=[]; previewLoading=false; previewError=''; previewTitle=''; previewSession=0;
  steps=['Tenant details','Tenancy & payments','Move-in checklist','Review & generate'];
  docs=[{id:'tenancy',name:'Tenancy agreement',description:'AC or non-AC tenancy agreement.',selected:false,tag:'AGREEMENT'}, {id:'rules',name:'House rules',description:'House guidelines and tenant acknowledgement.',selected:false,tag:'GUIDELINES'}, {id:'move_in',name:'Move-in form',description:'Registration, emergency contact and inventory.',selected:false,tag:'CHECK-IN'}, {id:'offer',name:'Letter of offer',description:'Offer to rent and payment breakdown.',selected:false,tag:'OFFER LETTER'}];
  tenantFields:Field[]=[{key:'tenant_name',label:'Full name',required:true,placeholder:'As shown on IC or passport',wide:true},{key:'tenant_id',label:'IC / Passport number',required:true,placeholder:'e.g. 900101-01-1234'},{key:'nationality',label:'Nationality'},{key:'phone',label:'Phone number',type:'tel',placeholder:'+60'},{key:'email',label:'Email address',type:'email',placeholder:'tenant@example.com'},{key:'occupation',label:'Occupation',placeholder:'e.g. Software engineer'},{key:'employer',label:'Company / Employer'},{key:'vehicle',label:'Vehicle registration',placeholder:'If applicable'}];
  emergencyFields:Field[]=[{key:'emergency_name',label:'Contact name'},{key:'emergency_relationship',label:'Relationship'},{key:'emergency_phone',label:'Phone number',type:'tel'},{key:'emergency_id',label:'IC / Passport number'}];
  propertyFields:Field[]=[{key:'property',label:'Unit number',required:true,placeholder:'e.g. A7-1-2404'},{key:'room',label:'Room number',required:true,placeholder:'e.g. 06'},{key:'address',label:'Property address',required:true,wide:true},{key:'agreement_date',label:'Agreement / Signing date',type:'date',required:true},{key:'start_date',label:'Move-in / Commencement date',type:'date',required:true},{key:'end_date',label:'Expiry date',type:'date',required:true},{key:'reference',label:'Invoice number',placeholder:'Generated automatically if left blank'}];
  moneyFields:Field[]=[{key:'rent',label:'Monthly room rental'},{key:'parking',label:'Monthly car park rental'},{key:'security_deposit',label:'Refundable room deposit'},{key:'access_deposit',label:'Refundable access card deposit'},{key:'advance_rent',label:'Advance / Pro-rated rental'},{key:'agreement_fee',label:'Agreement fee'}];
  companyFields:Field[]=[{key:'name',label:'Company name'},{key:'registration',label:'SSM registration number'},{key:'address',label:'Company address',wide:true},{key:'contact',label:'Contact person'},{key:'phone',label:'Phone number'},{key:'email',label:'Email address'},{key:'bank',label:'Bank name'},{key:'account_name',label:'Beneficiary name'},{key:'account_number',label:'Account number'}];
  get hasMoveIn(){return this.selected.some(x=>x.id==='move_in');}
  get hasAgreement(){return this.selected.some(x=>['tenancy','offer'].includes(x.id));}
  get hasTenancy(){return this.selected.some(x=>x.id==='tenancy');}
  get hasOffer(){return this.selected.some(x=>x.id==='offer');}
  get activeSteps(){return [0,...(this.hasAgreement?[1]:[]),...(this.hasMoveIn?[2]:[]),3];}
  get stepNumber(){return this.activeSteps.indexOf(this.step)+1;}
  get visibleTenantFields(){return this.tenantFields.filter(f=>this.hasMoveIn||(this.hasAgreement?['tenant_name','tenant_id','phone','email']:['tenant_name','tenant_id']).includes(f.key));}
  get selected(){return this.docs.filter(x=>x.selected)}
  get total(){return ['security_deposit','access_deposit','advance_rent','agreement_fee'].reduce((s,k)=>s+Number(this.d[k]||0),0)}
  get inventory():Inventory[]{return this.d['inventory'];}
  signOut(){if(!window.confirm('Sign out? Unsaved form details will be cleared.'))return;this.closePreview();this.closeShare();this.d=fresh();const form=document.createElement('form');form.method='post';form.action='/logout';document.body.appendChild(form);form.submit();}
  async ngOnInit(){await this.loadAddresses();try{const r=await fetch('/api/health');this.ready=r.ok;if(r.ok){this.wordPdfAvailable=(await r.json()).word_pdf_available!==false;if(!this.wordPdfAvailable)this.format='source';}if(r.status===401)window.location.assign('/login');}catch{this.ready=false;}}
  async loadAddresses(){try{const r=await fetch('/api/addresses');if(!r.ok)throw Error('Could not load saved addresses. Reload to try again.');this.addresses=(await r.json()).addresses;}catch(e){this.addressError=e instanceof Error?e.message:'Could not load addresses.';}}
  async addAddress(){
    const address=this.newAddress.trim();if(!address){this.addressError='Enter an address.';return;}
    this.savingAddress=true;this.addressError='';
    try{const r=await fetch('/api/addresses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address})});const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Could not save the address.');this.addresses=data.addresses;this.d['address']=data.selected;this.newAddress='';this.addingAddress=false;}catch(e){this.addressError=e instanceof Error?e.message:'Could not save the address.';}finally{this.savingAddress=false;}
  }
  chooseTerm(months:number){this.expiryMonths=months;this.updateExpiry();}
  updateExpiry(){
    if(!this.expiryMonths||!this.d['start_date'])return;
    this.d['end_date']=expiryDate(this.d['start_date'],this.expiryMonths);
  }
  startDocuments(id?:string){
    if(id)this.docs.forEach(doc=>doc.selected=doc.id===id);
    if(!this.selected.length){this.error='Choose at least one document.';return;}
    if(!this.wordPdfAvailable)this.format='source';
    this.page='studio';this.go(0);
  }
  back(){const index=this.activeSteps.indexOf(this.step);if(index>0)this.go(this.activeSteps[index-1]);else this.page='templates';}
  go(n:number){this.step=n;this.error='';this.status='';window.scrollTo({top:0,behavior:'smooth'});}
  next(form:HTMLFormElement){if(form.reportValidity()){if(this.step===1&&this.d['end_date']<this.d['start_date']){this.error='Expiry date must be on or after the move-in date.';return;}this.go(this.activeSteps[Math.min(this.activeSteps.length-1,this.activeSteps.indexOf(this.step)+1)]);}}
  validate(ids:string[]):boolean{
    const agreement=ids.some(id=>['tenancy','offer'].includes(id));
    const moveIn=ids.includes('move_in');
    for(const [idx,fields] of [[0,agreement||moveIn?this.tenantFields:[]],[1,agreement?this.propertyFields:[]]] as [number,Field[]][]){
      const missing=fields.find(f=>f.required&&!String(this.d[f.key]||'').trim());
      if(missing){this.go(idx);this.error=`Please enter ${missing.label.toLowerCase()}.`;return false;}
    }
    if(agreement&&this.d['end_date']<this.d['start_date']){this.go(1);this.error='Expiry date must be on or after the move-in date.';return false;}
    if(agreement&&this.moneyFields.some(f=>this.d[f.key]!=null && this.d[f.key]!=='' && (typeof this.d[f.key]!=='number'||!Number.isFinite(this.d[f.key])||Number(this.d[f.key])<0||Number(this.d[f.key])>1000000))){this.go(1);this.error='Enter a valid amount between RM 0 and RM 1,000,000 for every payment.';return false;}
    if(!ids.length){this.error='Choose at least one document to generate.';return false;}
    if(moveIn&&!this.d['agreement_date']){this.go(2);this.error='Enter the signing date.';return false;}
    return true;
  }
  documentDetails(documentIds:string[],blankRules=false){
    if(documentIds.includes('offer')&&!String(this.d['reference']||'').trim()){
      const bytes=crypto.getRandomValues(new Uint8Array(5));
      const suffix=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('').toUpperCase();
      this.d['reference']=`NN-${(this.d['agreement_date']||today()).replaceAll('-','')}-${suffix}`;
    }
    const agreement=documentIds.some(id=>['tenancy','offer'].includes(id));
    const moveIn=documentIds.includes('move_in');
    const fields=agreement?this.tenantFields.concat(this.propertyFields,this.moneyFields):moveIn?this.tenantFields.concat(this.emergencyFields):this.tenantFields.filter(f=>['tenant_name','tenant_id'].includes(f.key));
    const details:Record<string,any>=blankRules?{tenant_name:'-',tenant_id:'-'}:Object.fromEntries(fields.map(f=>[f.key,this.d[f.key]]));
    details['company']=this.d['company'];
    if(agreement)for(const key of ['aircon','guardian_name','guardian_id','special_conditions','include_aml'])details[key]=this.d[key];
    if(moveIn)for(const key of ['agreement_date','inventory','room_condition','room_remarks','makeup_table_drawer','meter_reading',...this.emergencyFields.map(f=>f.key)])details[key]=this.d[key];
    if(agreement)for(const f of this.moneyFields)details[f.key]=this.d[f.key]||0;
    return JSON.parse(JSON.stringify(details));
  }
  async generate(ids?:string[],preview=false,blankRules=false,outputFormat?:string){
    this.error='';this.status='';const documentIds=ids||this.selected.map(x=>x.id);if(!blankRules&&!this.validate(documentIds))return;
    const details=this.documentDetails(documentIds,blankRules);
    this.busy=true;
    try{
      const response=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({details,documents:documentIds,format:preview?'pdf':outputFormat||this.format})});
      if(!response.ok){const err=await response.json();throw new Error(Array.isArray(err.detail)?err.detail.map((x:any)=>`${x.loc.slice(2).join(' ')}: ${x.msg}`).join('; '):typeof err.detail==='string'?err.detail:'Could not generate documents. Please try again.');}
      const blob=await response.blob();
      if(preview){this.closePreview();this.previewUrl=URL.createObjectURL(blob);this.previewTitle=this.docs.find(x=>x.id===ids?.[0])?.name||'Document';await this.renderPreview(blob);}
      else{const filename=response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1]||'nest-and-nook-documents.zip';this.download(blob,filename);this.status='Documents generated. Check your downloads.';window.scrollTo({top:0,behavior:'smooth'});}
      this.ready=true;
    }catch(e){this.error=e instanceof Error?e.message:'The server is unavailable. Please try again.';window.scrollTo({top:0,behavior:'smooth'});}finally{this.busy=false;}
  }
  async prepareShare(ids?:string[],blankRules=false){
    if(this.busy)return;
    this.error='';this.status='';
    const documentIds=ids||this.selected.map(doc=>doc.id);
    if(!blankRules&&!this.validate(documentIds))return;
    const details=this.documentDetails(documentIds,blankRules);
    this.closeShare();
    const controller=new AbortController();this.shareAbort=controller;
    this.shareOpen=true;this.sharePreparing=true;this.busy=true;
    try{
      const files:File[]=[];
      for(const id of documentIds){
        const response=await fetch('/api/generate',{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({details,documents:[id],format:'pdf'})});
        if(!response.ok){const err=await response.json();throw Error(typeof err.detail==='string'?err.detail:'Could not prepare PDFs. Check the form details and try again.');}
        if(!response.headers.get('Content-Type')?.startsWith('application/pdf'))throw Error('The server did not return a PDF. Sign in again and retry.');
        const blob=await response.blob();
        const name=response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1]||`nest-and-nook-${id}.pdf`;
        files.push(new File([blob],name,{type:'application/pdf'}));
      }
      if(controller.signal.aborted)return;
      this.shareFiles=files;
    }catch(e){
      if(!controller.signal.aborted)this.shareError=e instanceof Error?e.message:'Could not prepare PDFs. Try again.';
    }finally{
      if(this.shareAbort===controller){this.sharePreparing=false;this.busy=false;}
    }
  }
  async sharePrepared(files:File[]=this.shareFiles){
    if(this.sharing||!this.supportsShare(files))return;
    this.sharing=true;this.shareError='';this.shareMessage='';
    try{
      // Files are already prepared: invoke sharing directly from this button tap on iOS.
      await navigator.share({files});
      this.shareMessage='Share sheet closed. You can share the PDFs again if needed.';
    }catch(e){
      if(e instanceof Error&&e.name==='AbortError')this.shareMessage='Sharing cancelled. Your PDFs are still ready.';
      else this.shareError='Could not share these PDFs together. Try sharing one below, or save it to Files.';
    }finally{this.sharing=false;}
  }
  closeShare(){
    this.shareAbort?.abort();this.shareAbort=undefined;
    if(this.sharePreparing)this.busy=false;
    this.shareOpen=false;this.sharePreparing=false;this.sharing=false;
    this.shareFiles=[];this.shareMessage='';this.shareError='';
  }
  download(blob:Blob,name:string){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
  saveDraft(){this.download(new Blob([JSON.stringify({version:1,details:this.d,documents:this.selected.map(doc=>doc.id)},null,2)],{type:'application/json'}),'nest-and-nook-draft.json');this.status='Draft saved to your device. It contains the tenant’s personal details.';}
  async loadDraft(event:Event){
    const input=event.target as HTMLInputElement;const file=input.files?.[0];if(!file)return;
    try{
      if(file.size>100000)throw Error('Draft file is too large.');
      const parsed=JSON.parse(await file.text());const src=parsed.details;const base=fresh();
      if(parsed.version!==1||!src||typeof src!=='object')throw Error('Choose a Nest & Nook draft file.');
      // Copy only known fields. Never merge arbitrary object keys from an imported file.
      for(const key of Object.keys(base)){
        if(key==='company'){for(const k of Object.keys(base.company)){if(typeof src.company?.[k]==='string'&&src.company[k].length<=300)base.company[k]=src.company[k];}}
        else if(key==='inventory'){
          if(!Array.isArray(src.inventory)||src.inventory.length>30)throw Error('Invalid inventory in draft.');
          base.inventory=src.inventory.map((i:any)=>{if(typeof i.name!=='string'||i.name.length>200||!Number.isInteger(i.quantity)||i.quantity<0||i.quantity>100||!['Not supplied','Good','Fair','Damaged'].includes(i.condition)||typeof i.remarks!=='string'||i.remarks.length>300)throw Error('Invalid inventory in draft.');return {name:i.name,quantity:i.quantity,condition:i.condition,remarks:i.remarks};});
        }else if(src[key]!==undefined){
          if(this.moneyFields.some(f=>f.key===key)){
            const value=src[key];
            if(value===null||value===''){base[key]=null;continue;}
            if(typeof value!=='number'||!Number.isFinite(value)||value<0||value>1000000)throw Error('Invalid amount in draft: '+key);
            base[key]=value;continue;
          }
          if(typeof src[key]!==typeof base[key]||(typeof src[key]==='string'&&src[key].length>3000))throw Error('Invalid field in draft: '+key);base[key]=src[key];
        }
      }
      this.d=base;this.expiryMonths=0;if(Array.isArray(parsed.documents))this.docs.forEach(doc=>doc.selected=parsed.documents.includes(doc.id));this.page=this.selected.length?'studio':'templates';this.go(0);this.status='Draft loaded. Review the details before generating documents.';
    }catch(e){this.error=e instanceof Error?e.message:'Unable to read draft.';}finally{input.value='';}
  }
  reset(){this.closeShare();this.page='templates';this.docs.forEach(doc=>doc.selected=false);this.d=fresh();this.expiryMonths=0;this.resetPrompt=false;this.go(0);this.closePreview();}
  async renderPreview(blob:Blob){
    this.previewLoading=true;this.previewError='';const session=this.previewSession;
    let pdfDocument:any;
    try{
      const pdfjs=await import('pdfjs-dist');
      pdfjs.GlobalWorkerOptions.workerSrc='/pdf.worker.min.mjs';
      pdfDocument=await pdfjs.getDocument({data:new Uint8Array(await blob.arrayBuffer())}).promise;
      for(let n=1;n<=pdfDocument.numPages;n++){
        if(session!==this.previewSession)break;
        const page=await pdfDocument.getPage(n);const view=page.getViewport({scale:1.4});
        const canvas=document.createElement('canvas');canvas.width=Math.ceil(view.width);canvas.height=Math.ceil(view.height);
        const context=canvas.getContext('2d');if(!context)throw Error('Canvas is unavailable.');
        await page.render({canvasContext:context,canvas,viewport:view}).promise;
        const png=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(Error('Could not render preview.')),'image/png'));
        if(session===this.previewSession)this.previewPages.push(URL.createObjectURL(png));
        canvas.width=canvas.height=0;
      }
    }catch{if(session===this.previewSession)this.previewError='Preview could not be displayed. You can still open or download the PDF above.';}
    finally{await pdfDocument?.destroy();if(session===this.previewSession)this.previewLoading=false;}
  }
  closePreview(){this.previewSession++;if(this.previewUrl)URL.revokeObjectURL(this.previewUrl);this.previewPages.forEach(url=>URL.revokeObjectURL(url));this.previewPages=[];this.previewUrl='';this.previewLoading=false;this.previewError='';}
  @HostListener('document:keydown', ['$event'])
  modalKeyboard(event:KeyboardEvent){
    if(!this.settings&&!this.resetPrompt&&!this.previewUrl&&!this.shareOpen)return;
    if(event.key==='Escape'){this.settings=false;this.resetPrompt=false;this.closePreview();if(!this.sharing)this.closeShare();}
    if(event.key==='Tab'){
      const items=Array.from(document.querySelectorAll<HTMLElement>('.modal button:not([disabled]), .modal input, .modal select, .modal a[href], .modal textarea'));
      const first=items[0],last=items[items.length-1];
      if(!first)return;
      if(event.shiftKey&&(document.activeElement===first||!items.includes(document.activeElement as HTMLElement))){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&(document.activeElement===last||!items.includes(document.activeElement as HTMLElement))){event.preventDefault();first.focus();}
    }
  }
  ngOnDestroy(){this.closePreview();this.closeShare();}
}
bootstrapApplication(App).catch(console.error);

import { expiryDate } from './dates';

export interface ImportedField { key:string; label:string; value:string|number; }
export interface TenantImport { fields:ImportedField[]; notes:string[]; months:number; }

const labels:Record<string,string> = {
  tenant_name:'Full name', tenant_id:'IC / Passport number', nationality:'Nationality',
  email:'Email address', phone:'Phone number', occupation:'Occupation', employer:'Company / Employer',
  emergency_name:'Emergency contact name', emergency_id:'Emergency IC / Passport number',
  emergency_relationship:'Emergency relationship', emergency_phone:'Emergency phone number',
  property:'Unit number', room:'Room number', rent:'Monthly room rental', start_date:'Move-in date',
  end_date:'Expiry date', advance_rent:'Advance / Pro-rated rental',
  security_deposit:'Refundable room deposit', access_deposit:'Refundable access card deposit', agreement_fee:'Agreement fee',
};
const moneyKeys = new Set(['rent','advance_rent','security_deposit','access_deposit','agreement_fee']);
const normal = (value:string) => value.toLowerCase().replace(/[.*_]/g,'').replace(/\s+/g,' ').trim();
const empty = (value:string) => /^(?:[-–—]|nil|n\/?a|rm)?$/i.test(value.trim());

function dateValue(value:string):string|null {
  let y:number,m:number,d:number;
  let match=value.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if(match){[,y,m,d]=match.map(Number);}
  else {
    match=value.match(/^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})$/);
    if(match){[,d,m,y]=match.map(Number);}
    else {
      const named=value.match(/^(\d{1,2})\s+([a-z]+)\s+(\d{4})$/i);
      if(!named)return null;
      d=Number(named[1]);y=Number(named[3]);
      m=['january','february','march','april','may','june','july','august','september','october','november','december'].findIndex(name=>name===named[2].toLowerCase()||name.slice(0,3)===named[2].toLowerCase())+1;
    }
  }
  const date=new Date(y,m-1,d);
  if(y<1900||y>9999||date.getFullYear()!==y||date.getMonth()!==m-1||date.getDate()!==d)return null;
  return `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
}

/** Parse locally; tenant messages never need to leave the browser for importing. */
export function parseTenantMessage(message:string):TenantImport {
  const fields=new Map<string,ImportedField>();const notes:string[]=[];const conflicts=new Set<string>();
  let section='tenant',months=0;let invalidTerm=false;
  const add=(key:string,value:string|number)=>{
    if(conflicts.has(key))return;
    if(fields.has(key)&&fields.get(key)!.value!==value){fields.delete(key);conflicts.add(key);notes.push(`${labels[key]} has conflicting values. Enter it manually.`);return;}
    fields.set(key,{key,label:labels[key],value});
  };
  if(message.length>20000)return {fields:[],notes:['Paste a message of fewer than 20,000 characters.'],months:0};
  for(const raw of message.split(/\r?\n/)){
    const line=raw.replace(/\*/g,'').trim();if(!line)continue;
    const heading=normal(line).replace(/:$/,'');
    const headings:Record<string,string>={'tenant registration':'tenant','emergency contact':'emergency','room reservation':'reservation','balance payable upon move in':'balance','bank in':'bank'};
    if(headings[heading]){section=headings[heading];continue;}
    if(section==='bank')continue;
    const colon=line.indexOf(':');
    if(colon<0){notes.push(`Could not read: ${line}`);continue;}
    const label=normal(line.slice(0,colon));const value=line.slice(colon+1).trim();if(empty(value))continue;
    if(label==='tenure'){
      const term=value.match(/^(\d+)\s*(years?|yrs?|months?|mths?)$/i);
      const count=term?Number(term[1])*(/^(year|yr)/i.test(term[2])?12:1):0;
      if(![6,12].includes(count)||(months&&months!==count)){invalidTerm=true;notes.push('Tenure could not be applied. Choose the expiry date manually.');}
      else months=count;
      continue;
    }
    if(label.includes('booking fee'))continue;
    if(label==='prorated rental'||label==='pro-rated rental')continue;
    if(label==='total'){
      notes.push(`${line} — not imported; check the payment breakdown before generating.`);continue;
    }
    if(label==='working at my/sg'){
      notes.push(`${line} — work location has no matching field.`);continue;
    }
    const shared:Record<string,string>={'room':'room','unit':'property','rental':'rent','move in date':'start_date','move-in date':'start_date','prorated rental':'advance_rent','pro-rated rental':'advance_rent','refundable deposit':'security_deposit','refundable room deposit':'security_deposit','refundable card deposit':'access_deposit','refundable access card deposit':'access_deposit','contract fee':'agreement_fee'};
    const personal:Record<string,string>={'name':'tenant_name','nationality':'nationality','email':'email','passport/ic no':'tenant_id','ic/passport no':'tenant_id','contact no':'phone','phone':'phone','phone number':'phone','occupation':'occupation','company':'employer','employer':'employer'};
    const emergency:Record<string,string>={'name':'emergency_name','relationship':'emergency_relationship','passport/ic no':'emergency_id','ic/passport no':'emergency_id','contact no':'emergency_phone','phone':'emergency_phone','phone number':'emergency_phone'};
    const key=section==='emergency'?emergency[label]:shared[label]||(section==='tenant'?personal[label]:undefined);
    if(!key){notes.push(`${line} — no matching field.`);continue;}
    if(moneyKeys.has(key)){
      const amount=value.replace(/^RM\s*/i,'').trim();
      if(!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/.test(amount)||Number(amount.replace(/,/g,''))>1000000){notes.push(`${labels[key]}: invalid amount “${value}”. Enter it manually.`);continue;}
      add(key,Number(amount.replace(/,/g,'')));
    }else if(key==='start_date'){
      const date=dateValue(value);if(date)add(key,date);else notes.push(`Move-in date “${value}” could not be read. Use DD/MM/YYYY.`);
    }else if(value.length>200){notes.push(`${labels[key]} is too long. Enter it manually.`);}
    else add(key,value);
  }
  if(invalidTerm)months=0;
  if(months){
    const start=fields.get('start_date');
    if(start)add('end_date',expiryDate(String(start.value),months));
    else months=0;
  }
  return {fields:[...fields.values()],notes:[...new Set(notes)],months};
}

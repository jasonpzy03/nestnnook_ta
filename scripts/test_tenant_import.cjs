const ts=require('../frontend/node_modules/typescript');
const fs=require('fs');
const vm=require('vm');
const assert=require('assert/strict');
function load(name){
  const mod={exports:{}};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(`frontend/src/${name}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports:mod.exports,require:id=>load(id.replace('./','')),Date});
  return mod.exports;
}
const parse=load('tenant-import').parseTenantMessage;
const values=result=>Object.fromEntries(result.fields.map(f=>[f.key,f.value]));
const message=`*Tenant Registration*
Room: 02
Name: Alex Tan
Nationality: Malaysian
Email: alex@example.com
Passport/IC No: 001234-01-5678
Working at MY/SG: SG
Occupation: Engineer

*Emergency Contact*
Name: Jamie Tan
Relationship: Sister
Passport/IC No: 991234-01-5678
Contact No: +60123456789

*Room Reservation*
Unit: 16-03
Room: 02
Rental: RM1,200.50
Move in date: 01/10/2026
Tenure: 1 Year
Booking Fee: RM300

*Balance payable upon move in*
Prorated Rental: RM600
Refundable Deposit: RM1,200.50
Refundable Card Deposit: RM100
Contract Fee: RM100
(-) Booking Fee: RM300
*Total: RM1701*

*Bank in*
OCBC Bank
Name: Nest & Nook Property Care
Account No: 7101403930`;
const imported=parse(message),v=values(imported);
assert.deepEqual(v,{room:'02',tenant_name:'Alex Tan',nationality:'Malaysian',email:'alex@example.com',tenant_id:'001234-01-5678',occupation:'Engineer',emergency_name:'Jamie Tan',emergency_relationship:'Sister',emergency_id:'991234-01-5678',emergency_phone:'+60123456789',property:'16-03',rent:1200.5,start_date:'2026-10-01',security_deposit:1200.5,access_deposit:100,agreement_fee:100,end_date:'2027-09-30'});
assert.equal(imported.months,12);
assert(imported.notes.some(n=>n.includes('work location')));
assert(!imported.notes.some(n=>n.includes('Booking Fee')));
assert.equal(parse('Tenure: 1 Year\nBooking Fee: RM300\n(-) Booking Fee: RM300').notes.length,0);
assert.equal(values(parse('Name:\nRental: RM\nRoom: -\nEmail: NA')).tenant_name,undefined);
assert.equal(parse('Name:\nRental: RM\nRoom: -\nEmail: NA').fields.length,0);
assert.equal(values(parse('Room: 01\nRoom Reservation\nRoom: 02')).room,undefined);
assert(parse('Room: 01\nRoom Reservation\nRoom: 02').notes.some(n=>n.includes('conflicting')));
assert.equal(values(parse('Move in date: 31/02/2026\nTenure: 1 Year')).end_date,undefined);
assert.equal(values(parse('Move in date: 2026-08-31\nTenure: 6 months')).end_date,'2027-02-28');
assert.equal(values(parse('Move in date: 3 Oct 2026\nTenure: 12 months')).end_date,'2027-10-02');
assert.equal(values(parse('Rental: RM1,20\nContract Fee: -100')).rent,undefined);
assert.equal(values(parse('Rental: RM0')).rent,0);
assert.equal(values(parse('Move in date: 01/10/2026\nTenure: 2 years')).end_date,undefined);
assert.equal(values(parse('Name: Tenant\nBank in\nName: Bank company')).tenant_name,'Tenant');
assert.equal(parse('x'.repeat(20001)).fields.length,0);
assert.equal(values(parse('Room Reservation\nMove in date: 1/2/26')).start_date,undefined);
assert.equal(values(parse('Emergency Contact\nContact No: 00123')).emergency_phone,'00123');
console.log('Tenant import checks passed: complete form, sections, money, dates, conflicts, blanks and limits.');

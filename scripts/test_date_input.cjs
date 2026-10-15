const ts=require('../frontend/node_modules/typescript'),fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const mod={};
vm.runInNewContext(ts.transpileModule(fs.readFileSync('frontend/src/date-input.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,experimentalDecorators:true}}).outputText,{exports:mod,require:()=>({Directive:()=>()=>{},HostListener:()=>()=>{},forwardRef:f=>f}),Date});
assert.equal(mod.parseDate('29/02/2024'),'2024-02-29');
for(const v of ['29/02/2025','31/04/2026','10/13/2026','2026-10-15','1/2/2026'])assert.equal(mod.parseDate(v),null);
assert.equal(mod.parseDate(''),'');assert.equal(mod.displayDate('2026-10-15'),'15/10/2026');
const input={value:'',setCustomValidity(v){this.error=v;}};const directive=new mod.DateInput({nativeElement:input});let result;directive.registerOnChange(v=>result=v);
directive.writeValue('2026-10-15');assert.equal(input.value,'15/10/2026');input.value='31/04/2026';directive.input();assert(input.error);input.value='30/04/2026';directive.input();assert.equal(result,'2026-04-30');assert.equal(input.error,'');
console.log('DD/MM/YYYY display, ISO storage, invalid dates and leap years passed.');

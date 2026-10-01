const ts=require('../frontend/node_modules/typescript');
const fs=require('fs');
const vm=require('vm');
const assert=require('assert/strict');
const mod={exports:{}};
vm.runInNewContext(ts.transpileModule(fs.readFileSync('frontend/src/dates.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports:mod.exports,Date});
const expiry=mod.exports.expiryDate;
for(const [start,months,end] of [['2026-10-01',6,'2027-03-31'],['2026-10-01',12,'2027-09-30'],['2026-08-31',6,'2027-02-28'],['2024-02-29',12,'2025-02-28'],['2023-08-31',6,'2024-02-29']])assert.equal(expiry(start,months),end);
console.log('5 expiry date cases passed');

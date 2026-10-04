const ts=require('../frontend/node_modules/typescript');
const fs=require('fs');
const vm=require('vm');
const assert=require('assert/strict');
const mod={exports:{}};
vm.runInNewContext(ts.transpileModule(fs.readFileSync('frontend/src/dates.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports:mod.exports,Date});
const expiry=mod.exports.expiryDate;
for(const [start,months,end] of [['2026-10-01',6,'2027-03-31'],['2026-10-01',12,'2027-09-30'],['2026-08-31',6,'2027-02-28'],['2024-02-29',12,'2025-02-28'],['2023-08-31',6,'2024-02-29']])assert.equal(expiry(start,months),end);
console.log('5 expiry date cases passed');

const prorate=mod.exports.proratedRental;
for(const [start,rent,expected] of [
 ['2026-10-17',1000,483.87],['2026-10-01',1000,1000],['2026-10-31',1000,32.26],
 ['2026-04-17',1000,466.67],['2026-02-17',1000,428.57],['2028-02-17',1000,448.28],
 ['2026-04-16',100.01,50.01],['2026-10-17',0,0],['2026-10-17',null,null],
 ['',1000,null],['2026-02-30',1000,null],['2026-13-01',1000,null]
])assert.equal(prorate(start,rent),expected);
console.log('12 prorated rental cases passed');

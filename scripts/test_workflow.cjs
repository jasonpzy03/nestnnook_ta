const ts=require('../frontend/node_modules/typescript');
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const exportsObject={};
const source=ts.transpileModule(fs.readFileSync('frontend/src/main.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,experimentalDecorators:true}}).outputText;
vm.runInNewContext(source,{exports:exportsObject,require:(name)=>name==='@angular/core'?{Component:()=>()=>{},HostListener:()=>()=>{}}:name==='@angular/platform-browser'?{bootstrapApplication:()=>Promise.resolve()}:name==='./language'?{readLanguagePreference:()=> 'en',detectLanguage:()=> 'en',translate:text=>text}:name==='./dates'?{expiryDate:()=>''}:{},document:{cookie:''},window:{scrollTo(){}},console,Date});
const app=new exportsObject.App();
const form={reportValidity:()=>true};
for(const [id,path] of [['offer',[0,1,3]],['tenancy',[0,1,3]],['move_in',[0,2,3]],['rules',[0,3]]]){
  app.startDocuments(id);assert.equal(JSON.stringify(app.activeSteps),JSON.stringify(path));
  app.d.end_date='2027-10-01';
  for(const expected of path.slice(1)){app.next(form);assert.equal(app.step,expected);}
  app.back();assert.equal(app.step,path[path.length-2]);
}
app.docs.forEach(doc=>doc.selected=true);assert.equal(JSON.stringify(app.activeSteps),'[0,1,2,3]');
app.startDocuments('offer');app.d.tenant_name='Test';app.d.tenant_id='TEST';app.d.property='';assert.equal(app.validate(['offer']),false);
app.startDocuments('move_in');assert.equal(app.validate(['move_in']),true);
app.startDocuments('rules');app.d.tenant_name='';app.d.tenant_id='';assert.equal(app.validate(['rules']),true);
console.log('Document paths, back navigation, bundles and validation passed');
app.d.reference='TEST';app.d.aircon=true;app.d.aircon_kwh=65;
assert.equal(app.documentDetails(['tenancy']).aircon_kwh,65);
assert.equal(app.documentDetails(['offer']).aircon_kwh,undefined);
app.d.aircon=false;assert.equal(app.documentDetails(['tenancy']).aircon_kwh,undefined);
app.d.aircon=true;app.d.aircon_kwh=null;assert.equal(app.validate(['tenancy']),false);
app.reset();assert.equal(app.d.aircon_kwh,40);
console.log('AC allowance payload, validation and reset checks passed');

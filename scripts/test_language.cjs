const ts=require('../frontend/node_modules/typescript');
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
function load(name,globals={}){
  const mod={exports:{}};
  const source=ts.transpileModule(fs.readFileSync(`frontend/src/${name}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,experimentalDecorators:true}}).outputText;
  vm.runInNewContext(source,{exports:mod.exports,require:id=>id.startsWith('./')?load(id.slice(2)):id==='@angular/core'?{Component:()=>()=>{},HostListener:()=>()=>{}}:id==='@angular/platform-browser'?{bootstrapApplication:()=>Promise.resolve()}:{},Date,console,...globals});
  return mod.exports;
}
const language=load('language');
for(const [langs,expected] of [[['zh-CN','en'],'zh'],[['zh-TW'],'zh'],[['en-SG','zh'],'en'],[['fr','zh-SG'],'zh'],[['fr'],'en'],[[],'en']])assert.equal(language.detectLanguage(langs),expected);
for(const [cookie,expected] of [['','auto'],['other=1; nest_language=zh','zh'],['nest_language=en','en'],['nest_language=auto','auto'],['nest_language=invalid','auto']])assert.equal(language.readLanguagePreference(cookie),expected);
assert.equal(language.translate('Full name','zh'),'姓名');
assert.equal(language.translate('Alex Tan','zh'),'Alex Tan');
assert.equal(language.translate('Full name','en'),'Full name');
assert.equal(language.translate('Download 3 documents','zh'),'下载3份文件');
assert.equal(language.translate('Room number has conflicting values. Enter it manually.','zh'),'房间号码有不同的值，请手动填写。');
// Every explicit static translation in the Angular template has a Chinese entry.
const template=fs.readFileSync('frontend/src/app.html','utf8').replaceAll('&quot;','"').replaceAll('&#x27;',"'");
for(const match of template.matchAll(/\bt\(("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')\)/g)){
  const key=match[1].slice(1,-1);assert(Object.hasOwn(language.chinese,key),`Missing translation: ${key}`);
}
const document={cookie:'',documentElement:{lang:''},title:''};
const navigator={languages:['zh-SG'],language:'zh-SG'};
const {App}=load('main',{document,navigator,location:{protocol:'https:'},window:{scrollTo(){}}});
const app=new App();app.updateLanguage();assert.equal(app.language,'zh');assert.equal(document.documentElement.lang,'zh-Hans');
app.d.tenant_name='Test';app.d.reference='TEST-1';app.d.room_condition='Good';
const before=JSON.stringify(app.documentDetails(['offer','move_in']));
app.setLanguage('en');assert.equal(app.language,'en');assert.match(document.cookie,/nest_language=en/);assert.match(document.cookie,/Secure/);
assert.equal(JSON.stringify(app.documentDetails(['offer','move_in'])),before,'Language must never alter document values');
app.setLanguage('auto');assert.equal(app.language,'zh');navigator.languages=['en-SG'];app.updateLanguage();assert.equal(app.language,'en');
assert.equal(app.d.room_condition,'Good');
console.log('Language detection, preference, translation coverage and unchanged document payload checks passed.');

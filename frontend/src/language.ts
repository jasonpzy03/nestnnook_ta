export type Language = 'en'|'zh';
export type LanguagePreference = Language|'auto';
export const LANGUAGE_COOKIE='nest_language';

export function detectLanguage(languages:readonly string[]):Language {
  for(const language of languages){
    if(/^zh(?:-|$)/i.test(language))return 'zh';
    if(/^en(?:-|$)/i.test(language))return 'en';
  }
  return 'en';
}
export function readLanguagePreference(cookie:string):LanguagePreference {
  const value=cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith(LANGUAGE_COOKIE+'='))?.split('=')[1];
  return value==='en'||value==='zh'?value:'auto';
}

export const chinese:Record<string,string> = {
  'Tenancy type':'租约类型',
  'New tenant':'新租客',
  'Renewal':'续租',
  'Choose New tenant or Renewal.':'请选择新租客或续租。',
  'The extension note applies only to new tenants with a six-month tenure.':'延期租金说明仅适用于租期为六个月的新租客。',
  'Car park rental agreement':'停车位租赁协议',
  'Choose an address':'选择地址',
  'Separate car park dates, rental and deposits.':'独立的停车位租期、租金和押金。',
  'CAR PARK':'停车位',
  'Car park details':'停车位资料',
  'Lot':'车位 / 单位编号',
  'Commencement date':'起租日期',
  'Car park rental':'停车位租金',
  'Deposit':'押金',
  'Earnest deposit (automatic)':'预付租金（自动计算）',
  'Tenant details and separate car park terms.':'租客资料及独立的停车位租赁条款。',
  'Car park dates and payments are separate from the tenancy agreement.':'停车位租期和费用与房间租约分开填写。',
  'Car park expiry date must be on or after its commencement date.':'停车位到期日不得早于起租日。',
  'Pro-rated rental (automatic)':'按比例租金（自动计算）',
  'Monthly rent ÷ days in the move-in month × remaining days, including move-in day.':'月租 ÷ 入住月份天数 × 剩余天数（包含入住当天）。',
  'Included air-conditioning electricity (kWh)':'包含的冷气用电量（kWh）',
  'Included allowance in the AC tenancy agreement.':'有冷气租约中包含的用电额度。',
  'Enter an electricity allowance between 0 and 100,000 kWh.':'请输入0至100,000 kWh之间的用电额度，可包含小数。',
  'Auto':'自动',
  'TEAM TOOLS':'团队工具', 'Create documents':'制作文件', 'Choose documents':'选择文件', 'Company details':'公司资料',
  'Property management':'物业管理','Sign out':'退出登录','Workspace':'工作区','No saved tenant records':'不保存租客记录','＋ New tenancy':'＋ 新租约',
  'Create':'制作','selected':'已选','Continue with selected →':'继续制作所选文件 →','Saved draft':'已保存的草稿','Load draft':'载入草稿','← Change documents':'← 更改所选文件','Draft':'草稿','Save draft':'保存草稿',
  'STEP 0':'第 0','OF 0':'步，共 0','Paste tenant registration / reservation':'粘贴租客登记／预订资料',
  'Paste the completed WhatsApp message, then review the fields below. Blank lines leave existing inputs unchanged. Dates use DD/MM/YYYY.':'粘贴已填写的 WhatsApp 信息，然后核对下方资料。空白项目不会覆盖现有输入。日期格式为日/月/年（DD/MM/YYYY）。',
  'Tenant message':'租客信息','Review fields':'核对资料','These values will replace the matching inputs. Property address and air conditioning stay as selected.':'以下资料将填入相应栏位。物业地址及冷气选项将保留原来的选择。','Fill':'填入','fields':'项资料',
  'No completed fields found. Paste the filled form including its section headings.':'未找到已填写的资料。请粘贴完整表格，并保留各部分的标题。','Check these lines':'请检查以下内容','Not filled / needs review':'未填入／需要核对',
  'PERSONAL INFORMATION':'个人资料','Emergency contact':'紧急联系人','Optional':'选填','* Required':'* 必填','Included in the tenant registration form.':'将显示在租客登记表中。',
  'Guardian details':'监护人资料','For tenants under 18':'适用于未满18岁的租客','Guardian name':'监护人姓名','Guardian IC / Passport':'监护人身份证／护照号码',
  'ROOM & AGREEMENT':'房间与租约','With air conditioning':'有冷气','Without air conditioning':'无冷气','Uses the full':'使用完整的','template, including its payment dates and notice periods.':'模板，包括付款日期及通知期限。',
  'Select an address':'选择物业地址','(from draft)':'（来自草稿）','The unit number is added before this address in the tenancy agreement.':'租约中会在此地址前加上单位号码。','New property address':'新物业地址',
  '6 months':'6个月','1 year':'1年','Ends the day before the anniversary of the move-in date. You can also choose a date.':'租期于入住日期满期的前一天结束。您也可以自行选择日期。',
  'Rental & deposits':'租金与押金','Enter the agreed amounts. Leave unused amounts blank; documents show a dash.':'输入双方同意的金额。不适用的项目请留空，文件中将显示横线。','Total payable on offer letter':'租赁要约书应付总额','Deposits + advance rental + one-time fees':'押金＋预付租金＋一次性费用',
  'The non-AC agreement has no access deposit or agreement fee row. The offer lists the agreement fee separately.':'无冷气租约没有门禁卡押金或合约费栏位。租赁要约书会单独列出合约费。',
  'Special conditions for the offer letter':'租赁要约书附加条款','Signing date':'签署日期','Room condition':'房间状况','Not recorded':'未记录','Good':'良好','Fair':'一般','Damaged':'损坏','Room remarks':'房间备注','Makeup table drawer':'梳妆台抽屉','Not applicable':'不适用','With drawer':'有抽屉','Without drawer':'无抽屉','Starting electricity meter reading':'入住时电表读数','Room inventory':'房间物品清单','items':'件物品',
  'Items start at quantity 1 and Good condition. Adjust items not supplied or damaged; use remarks for card and key numbers.':'物品默认为数量1、状况良好。请调整未提供或已损坏的物品，并在备注中填写卡号及钥匙号码。','Qty':'数量','Condition':'状况','Not supplied':'未提供','Remarks':'备注','TENANT':'租客','PROPERTY':'物业','TENANCY':'租期','Edit':'编辑','/ month':'／月',
  'Documents to generate':'要生成的文件','PDF templates are missing from this installation. Download Word documents instead.':'系统缺少 PDF 模板，请下载 Word 文件。','Preview ↗':'预览 ↗','Edit move-in checklist →':'编辑入住清单 →','Offer letter enclosure':'租赁要约书附件','Original third page':'原模板第三页',
  'Included by default to retain the complete original. The supplied enclosure states that the company is a reporting institution and the tenant declined to provide ID. Include it only if both statements apply.':'默认包含此附件，以保留完整原稿。附件声明公司为报告机构，且租客拒绝提供身份证明。仅在这两项声明均属实时保留。','Include the supplied AML acknowledgement':'包含原有反洗钱（AML）确认书',
  'Download format':'下载格式','Share PDFs sends separate PDF files to your phone’s share sheet. Downloads use the selected format; multiple downloads come as a ZIP.':'“分享 PDF”会将独立 PDF 文件发送到手机的分享菜单。下载会使用所选格式；多个文件会打包为 ZIP。','PDF · Ready to print':'PDF · 可直接打印','Word · Editable documents':'Word · 可编辑文件','Review the document previews and company details before signing.':'签署前请核对文件预览及公司资料。','← Back':'← 返回','Continue':'继续','Share PDFs':'分享 PDF','DOCUMENT SUMMARY':'文件摘要','Monthly rental':'月租','Offer total':'要约书总额','Draft files':'草稿文件','Save the current form to a file, or load a saved draft.':'将当前表格保存为文件，或载入已保存的草稿。','Tenant details stay in this session unless you save a draft or download documents.':'除非保存草稿或下载文件，否则租客资料仅保留在当前会话中。','Internal team use':'仅供内部团队使用',
  'Pre-filled from your business card and AC agreement. These details appear in generated documents.':'已根据名片及有冷气租约预填。这些资料会显示在生成的文件中。','Done':'完成','Start a new tenancy?':'开始新租约？','This clears the current form. Save a draft first if you need these details later.':'这会清空当前表格。如需保留资料，请先保存草稿。','Keep editing':'继续编辑','Start new':'开始新租约','Open PDF in a new tab':'在新标签页打开 PDF','or':'或','download preview':'下载预览','Rendering document pages…':'正在载入文件页面…','Page':'第','of':'页，共','Preparing your PDFs…':'正在准备 PDF…','separate PDF':'份独立 PDF','ready. Choose WhatsApp in the share sheet, then select your customer.':'已准备好。请在分享菜单中选择 WhatsApp，然后选择客户。','Sharing these files together is unavailable in this browser. Try an individual Share button, or download a PDF and share it from Files. On iPhone, open the website in Safari using its HTTPS address.':'此浏览器无法同时分享这些文件。请逐个分享，或下载 PDF 后从“文件”分享。iPhone 用户请在 Safari 中使用 HTTPS 地址打开网站。','Share':'分享','Download':'下载',
  'Tenancy agreement':'租赁协议','House rules':'房屋守则','Move-in form':'入住登记表','Letter of offer':'租赁要约书','tenancy agreement':'租赁协议','house rules':'房屋守则','move-in form':'入住登记表','letter of offer':'租赁要约书',
  'AC or non-AC tenancy agreement.':'有冷气或无冷气租约。','House guidelines and tenant acknowledgement.':'房屋使用守则及租客确认。','Registration, emergency contact and inventory.':'登记资料、紧急联系人及物品清单。','Offer to rent and payment breakdown.':'租赁要约及付款明细。','AGREEMENT':'租约','GUIDELINES':'守则','CHECK-IN':'入住','OFFER LETTER':'要约书',
  'Tenant details':'租客资料','Tenancy & payments':'租期与付款','Move-in checklist':'入住清单','Review & generate':'核对并生成',
  'Full name':'姓名','IC / Passport number':'身份证／护照号码','Nationality':'国籍','Phone number':'电话号码','Email address':'电子邮箱','Occupation':'职业','Company / Employer':'公司／雇主','Vehicle registration':'车牌号码','Contact name':'联系人姓名','Relationship':'关系','Unit number':'单位号码','Room number':'房间号码','Property address':'物业地址','Agreement / Signing date':'合约／签署日期','Move-in / Commencement date':'入住／起租日期','Expiry date':'到期日期','Invoice number':'发票号码','Monthly room rental':'每月房租','Monthly car park rental':'每月停车位租金','Refundable room deposit':'可退还房间押金','Refundable access card deposit':'可退还门禁卡押金','Advance / Pro-rated rental':'预付／按比例计算的租金','Agreement fee':'合约费',
  'Company name':'公司名称','SSM registration number':'SSM 注册号码','Company address':'公司地址','Contact person':'联系人','Bank name':'银行名称','Beneficiary name':'收款人名称','Account number':'银行账号',
  'As shown on IC or passport':'与身份证或护照上的姓名一致','e.g. 900101-01-1234':'例如：900101-01-1234','e.g. Software engineer':'例如：软件工程师','If applicable':'如适用','e.g. A7-1-2404':'例如：A7-1-2404','e.g. 06':'例如：06','Generated automatically if left blank':'留空则自动生成','Any additional conditions agreed with the tenant':'与租客同意的其他附加条款','e.g. Light scuffs near door':'例如：门旁有轻微刮痕','e.g. 125.40 kWh':'例如：125.40 kWh',
  'Bedframe / Divan':'床架／床座','Mattress':'床垫','Pillow':'枕头','Makeup table':'梳妆台','Chair':'椅子','Plant decor':'装饰植物','Curtain':'窗帘','Wardrobe':'衣柜','Wall decor frame':'墙上装饰画框','Rubbish bin':'垃圾桶','Blanket':'毯子','Mattress cover':'床垫套','Air conditioner':'冷气机','Air conditioner remote':'冷气遥控器','Ceiling fan':'吊扇','Fan remote':'风扇遥控器','Access card':'门禁卡','Room key':'房间钥匙','Main door key':'大门钥匙',
  'Complete the details for your selected documents.':'填写所选文件所需的资料。','Choose one document or select several to prepare together.':'选择一份文件，或同时制作多份文件。','Optional tenant name and IC, then review and generate.':'租客姓名及身份证号码选填，然后核对并生成。','Tenant details and inventory only.':'仅需租客资料及物品清单。','Tenant details and tenancy terms. No move-in checklist.':'填写租客资料及租约条款，无需入住清单。','Enter the tenant’s personal and contact details.':'输入租客个人资料及联系方式。','Enter the property, dates and payment amounts.':'输入物业、日期及付款金额。','Record inventory quantities and condition at handover.':'记录交接时物品的数量及状况。','Check the details and download your selected documents.':'核对资料并下载所选文件。',
  'Cancel':'取消','＋ Add address':'＋ 添加地址','Saving…':'正在保存…','Save address':'保存地址','Not entered':'未填写','With AC':'有冷气','Without AC':'无冷气','AC':'有冷气','non-AC':'无冷气','Non-AC':'无冷气','Expiry required':'请填写到期日期','Preparing documents…':'正在准备文件…','document':'份文件','documents':'份文件','Sharing…':'正在分享…',
  'Emergency contact name':'紧急联系人姓名','Emergency IC / Passport number':'紧急联系人身份证／护照号码','Emergency relationship':'与紧急联系人的关系','Emergency phone number':'紧急联系电话','Move-in date':'入住日期',
  'Sign out? Unsaved form details will be cleared.':'退出登录？未保存的表格资料将被清除。','Could not load saved addresses. Reload to try again.':'无法载入已保存的地址，请刷新后重试。','Could not load addresses.':'无法载入地址。','Enter an address.':'请输入地址。','Could not save the address.':'无法保存地址。','Choose at least one document.':'请至少选择一份文件。','Expiry date must be on or after the move-in date.':'到期日期不能早于入住日期。','Enter a valid amount between RM 0 and RM 1,000,000 for every payment.':'各付款项目请输入 RM 0 至 RM 1,000,000 之间的有效金额。','Choose at least one document to generate.':'请至少选择一份要生成的文件。','Enter the signing date.':'请输入签署日期。','Could not generate documents. Please try again.':'无法生成文件，请重试。','Documents generated. Check your downloads.':'文件已生成，请查看下载列表。','The server is unavailable. Please try again.':'服务器暂时无法连接，请重试。','Could not prepare PDFs. Check the form details and try again.':'无法准备 PDF，请核对表格资料后重试。','The server did not return a PDF. Sign in again and retry.':'服务器未返回 PDF，请重新登录后重试。','Could not prepare PDFs. Try again.':'无法准备 PDF，请重试。','Share sheet closed. You can share the PDFs again if needed.':'分享菜单已关闭。如有需要，可以再次分享 PDF。','Sharing cancelled. Your PDFs are still ready.':'已取消分享，PDF 文件仍可使用。','Could not share these PDFs together. Try sharing one below, or save it to Files.':'无法同时分享这些 PDF。请逐个分享，或保存至“文件”。','Draft saved to your device. It contains the tenant’s personal details.':'草稿已保存至您的设备，其中包含租客个人资料。','Draft file is too large.':'草稿文件过大。','Choose a Nest & Nook draft file.':'请选择 Nest & Nook 草稿文件。','Invalid inventory in draft.':'草稿中的物品清单无效。','Draft loaded. Review the details before generating documents.':'草稿已载入，请在生成文件前核对资料。','Unable to read draft.':'无法读取草稿。','Preview could not be displayed. You can still open or download the PDF above.':'无法显示预览，您仍可打开或下载上方的 PDF。',
  'Move-in date changed. Choose the expiry date in Tenancy & payments.':'入住日期已更改，请在“租期与付款”中选择到期日期。','Tenure could not be applied. Choose the expiry date manually.':'无法套用租期，请手动选择到期日期。','Paste a message of fewer than 20,000 characters.':'请粘贴少于20,000个字符的信息。',
  'Nest and Nook home':'Nest & Nook 首页','Main navigation':'主导航','Document creation steps':'文件制作步骤','Air conditioning':'冷气选项','Close company details':'关闭公司资料','Close preview':'关闭预览','Close sharing':'关闭分享',
  'Language':'语言','System language':'跟随系统','Team access or cloud storage is temporarily unavailable. Try again later.':'团队登录或云端存储暂时不可用，请稍后重试。','Your session has ended. Sign in again.':'会话已结束，请重新登录。','Request blocked. Reload this website and try again.':'请求被阻止，请刷新网站后重试。',
  'Saved addresses could not be read. Contact the host administrator.':'无法读取已保存的地址，请联系系统管理员。','Saved addresses are temporarily unavailable.':'已保存的地址暂时不可用。','The saved address list is full.':'已保存的地址数量已达上限。','Address storage is temporarily unavailable. Try again later.':'地址存储暂时不可用，请稍后重试。','Address could not be saved. Try again or contact the host administrator.':'无法保存地址，请重试或联系系统管理员。',
  'The Word template structure changed. Rebuild the PDF field map.':'Word 模板结构已更改，请重新生成 PDF 字段映射。','Converted PDF template is missing. Rebuild the PDF templates.':'缺少已转换的 PDF 模板，请重新生成。','A document template changed. Rebuild and verify the PDF field map before generating PDFs.':'文件模板已更改，请重新生成并检查 PDF 字段映射后再制作 PDF。',
};

// Dynamic messages keep personal data intact; only the surrounding UI is translated.
const patterns:Array<[RegExp,(match:RegExpMatchArray)=>string]> = [
  [/^Filled (\d+) fields\. Review the details before generating documents\.$/,m=>`已填入${m[1]}项资料。生成文件前请核对。`],
  [/^Download (\d+) documents?$/,m=>`下载${m[1]}份文件`],
  [/^Please enter (.+)\.$/,m=>`请填写${translate(m[1],'zh')}。`],
  [/^(.+) has conflicting values\. Enter it manually\.$/,m=>`${translate(m[1],'zh')}有不同的值，请手动填写。`],
  [/^(.+): invalid amount “(.+)”\. Enter it manually\.$/,m=>`${translate(m[1],'zh')}：金额“${m[2]}”无效，请手动填写。`],
  [/^Move-in date “(.+)” could not be read\. Use DD\/MM\/YYYY\.$/,m=>`无法识别入住日期“${m[1]}”。请使用日/月/年（DD/MM/YYYY）。`],
  [/^(.+) is too long\. Enter it manually\.$/,m=>`${translate(m[1],'zh')}过长，请手动填写。`],
  [/^Could not read: (.+)$/,m=>`无法识别：${m[1]}`],
  [/^(.+) — work location has no matching field\.$/,m=>`${m[1]} — 工作地点没有对应栏位。`],
  [/^(.+) — no matching field\.$/,m=>`${m[1]} — 没有对应栏位。`],
  [/^(.+) — not imported; check the payment breakdown before generating\.$/,m=>`${m[1]} — 未填入；生成文件前请核对付款明细。`],
  [/^Invalid (amount in draft|field in draft): (.+)$/,m=>`草稿资料无效：${m[2]}`],
  [/^(.+) is too long for the PDF template\. Shorten this value or download Word format\.$/,m=>`${m[1]} 超出 PDF 模板可容纳的长度。请缩短内容或下载 Word 格式。`],
  [/^(.+) contains a character unsupported by the PDF fonts\.$/,m=>`${m[1]} 包含 PDF 字体不支持的字符。`],
];
const lowercaseChinese=new Map(Object.entries(chinese).map(([key,value])=>[key.toLowerCase(),value]));
export function translate(text:string,language:Language):string {
  if(language==='en'||!text)return text;
  if(Object.hasOwn(chinese,text))return chinese[text];
  const translated=lowercaseChinese.get(text.toLowerCase());
  if(translated)return translated;
  for(const [pattern,render] of patterns){const match=text.match(pattern);if(match)return render(match);}
  return text;
}

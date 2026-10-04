export function proratedRental(start:string, rent:number|null):number|null {
  if(!start || rent===null || !Number.isFinite(rent) || rent<0)return null;
  const match=/^(\d{4})-(\d{2})-(\d{2})$/.exec(start);
  if(!match)return null;
  const [,year,month,day]=match.map(Number);
  if(month<1||month>12)return null;
  const leap=year%4===0&&(year%100!==0||year%400===0);
  const days=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31][month-1];
  if(day<1||day>days)return null;
  // Calculate in cents, rounding only the final amount, with move-in day included.
  return Math.round(Math.round(rent*100)*(days-day+1)/days)/100;
}

export function expiryDate(start:string, months:number):string {
  if(!start || ![6,12].includes(months))return '';
  const [y,m,day]=start.split('-').map(Number);
  const target=new Date(y,m-1+months,1);
  const last=new Date(target.getFullYear(),target.getMonth()+1,0).getDate();
  // If the anniversary day does not exist, use the target month's last day.
  target.setDate(Math.min(day,last+1));target.setDate(target.getDate()-1);
  return `${target.getFullYear()}-${String(target.getMonth()+1).padStart(2,'0')}-${String(target.getDate()).padStart(2,'0')}`;
}

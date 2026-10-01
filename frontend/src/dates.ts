export function expiryDate(start:string, months:number):string {
  if(!start || ![6,12].includes(months))return '';
  const [y,m,day]=start.split('-').map(Number);
  const target=new Date(y,m-1+months,1);
  const last=new Date(target.getFullYear(),target.getMonth()+1,0).getDate();
  // If the anniversary day does not exist, use the target month's last day.
  target.setDate(Math.min(day,last+1));target.setDate(target.getDate()-1);
  return `${target.getFullYear()}-${String(target.getMonth()+1).padStart(2,'0')}-${String(target.getDate()).padStart(2,'0')}`;
}

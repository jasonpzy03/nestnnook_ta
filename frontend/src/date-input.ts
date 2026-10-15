import { Directive, ElementRef, forwardRef, HostListener } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export function displayDate(value:string|null|undefined):string {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split('-').reverse().join('/') : value || '';
}
export function parseDate(value:string):string|null {
  if(!value)return '';
  if(!/^\d{2}\/\d{2}\/\d{4}$/.test(value))return null;
  const [day,month,year]=value.split('/').map(Number);
  const date=new Date(0);date.setFullYear(year,month-1,day);date.setHours(0,0,0,0);
  return year>=1900&&year<=9999&&date.getFullYear()===year&&date.getMonth()===month-1&&date.getDate()===day ? value.split('/').reverse().join('-') : null;
}

// Keep API/draft dates in ISO format while making the staff input format explicit.
@Directive({selector:'input[appDate]',standalone:true,providers:[{provide:NG_VALUE_ACCESSOR,useExisting:forwardRef(()=>DateInput),multi:true}],host:{type:'text',placeholder:'DD/MM/YYYY',inputmode:'numeric',maxlength:'10'}})
export class DateInput implements ControlValueAccessor {
  private change:(value:string)=>void=()=>{};
  private touched:()=>void=()=>{};
  constructor(private element:ElementRef<HTMLInputElement>){}
  writeValue(value:string){this.element.nativeElement.value=displayDate(value);this.element.nativeElement.setCustomValidity('');}
  registerOnChange(fn:(value:string)=>void){this.change=fn;}
  registerOnTouched(fn:()=>void){this.touched=fn;}
  setDisabledState(disabled:boolean){this.element.nativeElement.disabled=disabled;}
  @HostListener('input') input(){const input=this.element.nativeElement;const value=parseDate(input.value);input.setCustomValidity(value===null?'Enter a valid date as DD/MM/YYYY.':'');this.change(value===null?input.value:value);}
  @HostListener('blur') blur(){this.touched();}
}

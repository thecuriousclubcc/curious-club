import { THEMES, themeVars } from './themes'
import { EPOCH_DAY, FLIP_HOUR, PERIOD_DAYS } from './rotation'

/**
 * The theme has to be on <html> before first paint, otherwise every launch
 * flashes the fallback palette — which on a 3-day rotation would read as the
 * app being broken. That means a synchronous inline script, which means the
 * rotation maths exists twice: once in lib/rotation.ts for the app and tests,
 * and once here as a string. Keep them in step; tests/rotation.test.ts guards
 * the real one.
 */
export function themeBootstrapScript(): string {
  const varsById: Record<string, Record<string, string>> = {}
  for (const theme of THEMES) varsById[theme.id] = themeVars(theme)
  const ids = THEMES.map((t) => t.id)

  return `(function(){try{
var IDS=${JSON.stringify(ids)},V=${JSON.stringify(varsById)},P=${PERIOD_DAYS},F=${FLIP_HOUR},E=${EPOCH_DAY};
function day(d){var s=new Date(d.getTime()-F*3600000);return Math.floor((s.getTime()-s.getTimezoneOffset()*60000)/86400000);}
function sh(n,seed){var a=[],i;for(i=0;i<n;i++)a[i]=i;var s=(Math.imul(seed,2654435761)+1)&0x7fffffff;for(i=n-1;i>0;i--){s=(Math.imul(s,1103515245)+12345)&0x7fffffff;var j=s%(i+1),t=a[i];a[i]=a[j];a[j]=t;}return a;}
var off=0,pin=null;
try{off=parseInt(localStorage.getItem('ima.shuffle')||'0',10)||0;pin=localStorage.getItem('ima.pin');}catch(e){}
var slot=Math.floor((day(new Date())-E)/P)+off;
var id=(pin&&V[pin])?pin:IDS[sh(IDS.length,Math.floor(slot/IDS.length))[((slot%IDS.length)+IDS.length)%IDS.length]];
var vars=V[id],root=document.documentElement,k;
for(k in vars)root.style.setProperty(k,vars[k]);
root.setAttribute('data-theme',id);
root.setAttribute('data-texture',vars['--texture']);
var m=document.querySelector('meta[name="theme-color"]');
if(!m){m=document.createElement('meta');m.setAttribute('name','theme-color');document.head.appendChild(m);}
m.setAttribute('content',vars['--ground']);
}catch(e){}})();`
}

(async()=>{
const T='CARMAX-SIM:';
let raw='';
try{raw=await navigator.clipboard.readText();}catch(e){}
if(!raw||raw.indexOf(T)!==0){raw=prompt('Cole aqui os dados do cliente copiados no Integrador Carmax (Ctrl+V):')||'';}
if(raw.indexOf(T)!==0){alert('Dados da Carmax não encontrados. No integrador, toque em "Copiar para os bancos" e tente de novo.');return;}
let d;try{d=JSON.parse(raw.slice(T.length));}catch(e){alert('Dados inválidos.');return;}
const R=[
['cpf',/\bcpf\b|000\.000\.000-00/i,d.cpf],
['nascimento',/nasc|birth|dd\/mm\/aaaa/i,d.nasc],
['celular',/celular|telefone|\bfone\b|phone|whats|\(00\)/i,d.tel],
['e-mail',/e-?mail/i,d.email],
['placa',/placa/i,d.placa],
['entrada',/entrada/i,d.entrada],
['valor do veículo',/valor\s*(do\s*)?(ve[ií]culo|bem|compra|carro)|pre[cç]o\s*(do\s*)?(ve[ií]culo|bem)/i,d.valor],
['nome',/(^|\s)nome(\s*completo)?(\s*do\s*cliente)?(\s|$|\*)|full\s*name/i,d.nome]
];
const NAO=/m[aã]e|pai|social|fantasia|empresa|busca|pesquis|search|revenda|vendedor|operador|agente|loja/i;
const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden';};
const ctx=e=>{let s=[e.placeholder,e.getAttribute('aria-label'),e.name,e.id,e.getAttribute('formcontrolname'),e.getAttribute('data-testid')].join(' ');
if(e.labels)for(const l of e.labels)s+=' '+l.innerText;
let p=e.parentElement;for(let i=0;i<3&&p;i++,p=p.parentElement){const t=(p.innerText||'').trim();if(t&&t.length<90){s+=' '+t;break;}}
return s;};
const tipar=(el,txt)=>{el.focus();const pr=Object.getPrototypeOf(el);const set=Object.getOwnPropertyDescriptor(pr,'value').set;
set.call(el,'');el.dispatchEvent(new Event('input',{bubbles:true}));
for(const ch of String(txt)){const c=ch.charCodeAt(0);
el.dispatchEvent(new KeyboardEvent('keydown',{key:ch,keyCode:c,bubbles:true}));
const kp=new KeyboardEvent('keypress',{key:ch,charCode:c,keyCode:c,which:c,bubbles:true,cancelable:true});el.dispatchEvent(kp);
if(!kp.defaultPrevented){const ml=el.maxLength>0?el.maxLength:9999;if(el.value.length<ml){set.call(el,el.value+ch);}el.dispatchEvent(new InputEvent('input',{data:ch,inputType:'insertText',bubbles:true}));}
el.dispatchEvent(new KeyboardEvent('keyup',{key:ch,keyCode:c,bubbles:true}));}
el.dispatchEvent(new Event('change',{bubbles:true}));el.dispatchEvent(new Event('blur',{bubbles:true}));};
if(window.__carmaxSim){window.__carmaxSim.parar();}
const feitos={},cont={};const pend=()=>R.filter(([nm,,val])=>val&&!feitos[nm]).map(r=>r[0]);
const box=document.createElement('div');box.style.cssText='position:fixed;z-index:2147483647;right:16px;bottom:16px;max-width:330px;background:#111;color:#fff;padding:12px 14px;border-radius:12px;font:14px/1.4 sans-serif;box-shadow:0 8px 30px rgba(0,0,0,.35)';document.body.appendChild(box);
let fim=Date.now()+120000,timer;
const desenhar=()=>{const f=Object.keys(feitos),p=pend();box.innerHTML='<b style="color:#ff5a5f">Carmax</b> · '+(p.length&&Date.now()<fim?'preenchendo automaticamente…':'pronto')+'<br>'+(f.length?'✓ '+f.join(', '):'Aguardando os campos aparecerem…')+(p.length&&Date.now()<fim?'<br><small style="opacity:.75">Faltam: '+p.join(', ')+'. Vá avançando no banco que eu completo.</small>':'')+'<br><small style="opacity:.75">Confira tudo antes de simular.</small> <button style="margin-left:6px;background:#333;color:#fff;border:0;border-radius:6px;padding:3px 8px;cursor:pointer">'+(p.length&&Date.now()<fim?'Parar':'Fechar')+'</button>';box.querySelector('button').onclick=parar;};
const parar=()=>{clearInterval(timer);box.remove();window.__carmaxSim=null;};
window.__carmaxSim={parar};
const passada=()=>{const campos=[...document.querySelectorAll('input')].filter(e=>/^(text|tel|email|number|search|date|)$/i.test(e.type)&&!e.disabled&&!e.readOnly&&vis(e)&&e!==document.activeElement&&!e.value&&!e.__carmax);
for(const[nm,re,val]of R){if(!val||feitos[nm])continue;
for(const e of campos){if(e.__carmax)continue;const c=ctx(e);if(!re.test(c)||(nm!=='cpf'&&NAO.test(c))||(nm==='cpf'&&/busca|pesquis|search|revenda/i.test(c)))continue;
if(e.type==='date'&&nm==='nascimento'){const m=val.split('/');const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(e,m[2]+'-'+m[1]+'-'+m[0]);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}
else tipar(e,val);
e.__carmax=1;cont[nm]=(cont[nm]||0)+1;feitos[nm]=1;break;}}
desenhar();if(!pend().length||Date.now()>fim){clearInterval(timer);setTimeout(()=>{if(window.__carmaxSim)parar();},8000);}};
passada();timer=setInterval(passada,800);
})();

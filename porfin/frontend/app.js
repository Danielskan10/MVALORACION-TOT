const API='';

// ── TEMA CLARO / OSCURO ────────────────────────────────────────────────────────
function _PL(){
  const light=document.documentElement.dataset.theme==='light';
  const txt=light?'#1f2328':'#8b949e';
  const grid=light?'#d0d7de':'#21262d';
  return{
    paper_bgcolor:'transparent',plot_bgcolor:'transparent',
    font:{color:txt,size:10,family:'Inter'},
    margin:{t:10,b:35,l:50,r:15},
    legend:{bgcolor:'transparent',font:{size:9}},
    xaxis:{gridcolor:grid,zerolinecolor:grid},
    yaxis:{gridcolor:grid,zerolinecolor:grid},
  };
}
// PL como getter para que sea siempre fresco
const PL={get paper_bgcolor(){return _PL().paper_bgcolor},get plot_bgcolor(){return _PL().plot_bgcolor},get font(){return _PL().font},get margin(){return _PL().margin},get legend(){return _PL().legend},get xaxis(){return _PL().xaxis},get yaxis(){return _PL().yaxis}};

// toggleTema: alias para compatibilidad (nav.js exporta toggleTheme)
function toggleTema(){
  if(typeof toggleTheme==='function')toggleTheme();
  if(_resumen){cargarResumen(document.getElementById('sel-fecha').value);}
}
document.addEventListener('sk-theme-change',()=>{
  if(_resumen)cargarResumen(document.getElementById('sel-fecha').value);
});

let _resumen=null,_erroresData=null,_causData=null,_posData=[];
let _fondosData=null,_tirData596=null,_tirData575=null,_tirActivo='596',_fondoSel=null;
let _up596=null,_up575=null,_up583=null;

function debounce(fn,ms){let t;return(...a)=>{clearTimeout(t);t=setTimeout(()=>fn(...a),ms);};}
async function fetchJSON(u){const r=await fetch(API+u);if(!r.ok)throw new Error(`${r.status}`);return r.json();}
function fmt(n,d=0){if(n==null||isNaN(n))return'—';const a=Math.abs(n);if(a>=1e12)return(n/1e12).toFixed(1)+' T';if(a>=1e9)return(n/1e9).toFixed(1)+' MM';if(a>=1e6)return(n/1e6).toFixed(1)+' M';return Number(n).toLocaleString('es-CO',{minimumFractionDigits:d,maximumFractionDigits:d});}
function fmtN(n,d=2){if(n==null||n===undefined||n==='')return'—';const x=parseFloat(n);if(isNaN(x))return String(n);if(d>2)return x.toFixed(d);return x.toLocaleString('es-CO',{minimumFractionDigits:2,maximumFractionDigits:2});}
function nc(n){return n==null?'':n>=0?'n-pos':'n-neg';}
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function setKpi(id,val,cls){const el=document.getElementById(id);if(!el)return;el.textContent=val;if(cls)el.parentElement.className='kpi '+cls;}

// ── TABS ─────────────────────────────────────────────────────────────────────
function showTab(id,el){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(t=>t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
  if(id==='tab-config')cargarConfig();
  if(id==='tab-logs')cargarLogs();
  if(id==='tab-causaciones'&&_causData&&document.getElementById('wrap-causaciones').innerHTML.includes('spinner'))renderCausaciones();
  if(id==='tab-fondos'&&!_fondosData)cargarFondos();
  if(id==='tab-tir'&&!_tirData596)cargarTir();
  if(id==='tab-errores'){if(_erroresData&&document.getElementById('wrap-errores').innerHTML.includes('spinner'))renderErrores();if(_erroresData)_renderErrorCharts();}
  if(id==='tab-portafolios'&&document.getElementById('wrap-portafolios').innerHTML.includes('spinner'))cargarPortafolios();
  if(id==='tab-monedas'&&document.getElementById('wrap-monedas-596').innerHTML.includes('spinner'))cargarMonedasTab();
  if(id==='tab-operaciones'&&!_ops583Data.length)cargarOps583();
  if(id==='tab-analisis')renderAnalisis();
  if(id==='tab-variaciones'){
    const fi=document.getElementById('var-fecha-i');
    const ff=document.getElementById('var-fecha-f');
    if(fi&&!fi.options.length){
      fetchJSON('/api/porfin/fechas').then(d=>poblarSelectsVariaciones((d.fechas||[]).slice().reverse())).catch(()=>{});
    }
  }
}

// ── UPLOAD ───────────────────────────────────────────────────────────────────
function abrirUpload(){
  const f=document.getElementById('sel-fecha').value;
  if(f)document.getElementById('up-fecha').value=f;
  document.getElementById('modal-upload').classList.add('open');
}
function cerrarUpload(){document.getElementById('modal-upload').classList.remove('open');}
function handleFile(inp,tipo){
  const f=inp.files[0];if(!f)return;
  if(tipo==='596'){_up596=f;document.getElementById('name-596').textContent=f.name;}
  else if(tipo==='575'){_up575=f;document.getElementById('name-575').textContent=f.name;}
  else if(tipo==='583'){_up583=f;document.getElementById('name-583').textContent=f.name;}
}
function handleDrop(ev,tipo){
  ev.preventDefault();document.getElementById('drop-'+tipo).classList.remove('drag-over');
  const f=ev.dataTransfer.files[0];if(!f)return;
  if(tipo==='596'){_up596=f;document.getElementById('name-596').textContent=f.name;}
  else if(tipo==='575'){_up575=f;document.getElementById('name-575').textContent=f.name;}
  else if(tipo==='583'){_up583=f;document.getElementById('name-583').textContent=f.name;}
}
async function subirArchivos(){
  const fecha=document.getElementById('up-fecha').value.trim();
  const msg=document.getElementById('upload-msg');
  if(!fecha||!/^\d{8}$/.test(fecha)){msg.innerHTML='<span style="color:var(--red2)">Fecha inválida. Formato: YYYYMMDD</span>';return;}
  const archivos=[{file:_up596,tipo:'596'},{file:_up575,tipo:'575'},{file:_up583,tipo:'583'}].filter(a=>a.file);
  if(!archivos.length){msg.innerHTML='<span style="color:var(--red2)">Selecciona al menos un archivo.</span>';return;}
  const fill=document.getElementById('prog-fill');
  msg.innerHTML='Subiendo...';let ok=0;
  for(let i=0;i<archivos.length;i++){
    fill.style.width=Math.round((i/archivos.length)*100)+'%';
    const fd=new FormData();fd.append('fecha',fecha);fd.append('file',archivos[i].file);
    try{const r=await fetch('/api/upload',{method:'POST',body:fd});const j=await r.json();if(j.ok)ok++;else msg.innerHTML+=`<br>Error ${archivos[i].tipo}: ${j.detail||'?'}`;}
    catch(e){msg.innerHTML+=`<br>Error: ${e.message}`;}
  }
  fill.style.width='100%';
  if(ok>0){msg.innerHTML=`<span style="color:var(--green2)">✓ ${ok} archivo(s) subido(s).</span>`;setTimeout(()=>{cerrarUpload();cargarFechas();},1200);}
}

// ── CARGA PRINCIPAL ───────────────────────────────────────────────────────────
async function cargarFechas(){
  const sel=document.getElementById('sel-fecha');
  try{
    const d=await fetchJSON('/api/porfin/fechas');
    const fechas=(d.fechas||[]).slice().reverse();
    sel.innerHTML=fechas.map(f=>`<option value="${f}">${f.slice(0,4)}-${f.slice(4,6)}-${f.slice(6)}</option>`).join('');
    poblarSelectsVariaciones(fechas);
    if(fechas.length)cargarTodo();
  }catch(e){sel.innerHTML='<option value="">Error</option>';}
}

async function cargarTodo(){
  const fecha=document.getElementById('sel-fecha').value;
  if(!fecha)return;
  _fondosData=null;_tirData596=null;_tirData575=null;_fondoSel=null;_ops583Data=[];_ops583Raw=null;
  ['wrap-causaciones','wrap-errores','wrap-portafolios','wrap-monedas-596','wrap-fondos','wrap-tir','wrap-ops']
    .forEach(id=>{const el=document.getElementById(id);if(el)el.innerHTML='<div class="empty"><span class="spinner"></span></div>';});
  document.getElementById('wrap-fondo-detalle').style.display='none';
  document.getElementById('wrap-fondos-lista').style.display='block';
  await Promise.all([cargarResumen(fecha),cargarPosiciones()]);
  cargarTirBadge(fecha);
}

async function cargarResumen(fecha){
  try{
    _resumen=await fetchJSON(`/api/porfin/resumen/${fecha}`);
    if(_resumen.error){
      document.getElementById('alertas-banner-wrap').innerHTML=`<div class="banner err">⚠ ${_resumen.error}</div>`;
      return;
    }
    const total=_resumen.total_posiciones||0,sinP=_resumen.sin_precio||0,conP=total-sinP;
    setKpi('kpi-total',fmt(total),'blue');
    document.getElementById('kpi-archivo-596').textContent=_resumen.archivo_596||'596';
    document.getElementById('kpi-archivo-575').textContent=_resumen.archivo_575||'575 — total día';
    setKpi('kpi-con-precio',fmt(conP),conP===total?'ok':conP>total*.7?'warn':'err');
    setKpi('kpi-sin-precio',fmt(sinP),sinP===0?'ok':sinP<100?'warn':'err');
    setKpi('kpi-vlr-total',fmt(_resumen.valor_mercado_total),'purple');
    setKpi('kpi-causacion',fmt(_resumen.causacion_mercado_total),'');

    document.getElementById('alertas-banner-wrap').innerHTML=sinP>0
      ?`<div class="banner warn">⚠ <strong>${sinP.toLocaleString()}</strong> posiciones sin precio. Revisar proveedores Infovalmer.</div>`
      :`<div class="banner ok">✓ Todas las posiciones tienen precio cargado.</div>`;

    // Gráficas resumen
    const esp=_resumen.distribucion_especie||{};
    document.getElementById('cnt-especie').textContent=Object.keys(esp).length;
    if(Object.keys(esp).length){
      const k=Object.keys(esp).slice(0,12).reverse(),v=k.map(x=>esp[x]);
      Plotly.newPlot('chart-especie',[{type:'bar',orientation:'h',x:v,y:k,marker:{color:'#1f6feb'}}],
        {...PL,margin:{t:5,b:20,l:110,r:20}},{responsive:true,displayModeBar:false});
    }
    const port=_resumen.distribucion_portafolio||{};
    if(Object.keys(port).length){
      Plotly.newPlot('chart-portafolio',[{type:'pie',labels:Object.keys(port),values:Object.values(port),hole:.4,
        marker:{colors:['#1f6feb','#3fb950','#e3b341','#f85149','#bc8cff','#58a6ff','#f0883e']},textinfo:'label+percent'}],
        {...PL,margin:{t:5,b:5,l:5,r:5}},{responsive:true,displayModeBar:false});
      const selP=document.getElementById('fil-portafolio'),prev=selP.value;
      selP.innerHTML='<option value="">Todos</option>'+Object.keys(port).map(p=>`<option value="${p}">${p}</option>`).join('');
      if(prev)selP.value=prev;
    }
    const mon=_resumen.distribucion_moneda||{};
    if(Object.keys(mon).length){
      Plotly.newPlot('chart-moneda',[{type:'pie',labels:Object.keys(mon),values:Object.values(mon),hole:.4,
        marker:{colors:['#3fb950','#58a6ff','#e3b341','#f85149','#bc8cff']},textinfo:'label+percent'}],
        {...PL,margin:{t:5,b:5,l:5,r:5}},{responsive:true,displayModeBar:false});
      const selM=document.getElementById('fil-moneda'),prev=selM.value;
      selM.innerHTML='<option value="">Todas</option>'+Object.keys(mon).map(m=>`<option value="${m}">${m}</option>`).join('');
      if(prev)selM.value=prev;
    }
  }catch(e){console.error('resumen',e);}
  cargarErroresGrafica(fecha);
  cargarCausacionesGrafica(fecha);
}

async function cargarErroresGrafica(fecha){
  try{
    _erroresData=await fetchJSON(`/api/porfin/errores/${fecha}`);
    const rt=_erroresData.resumen_tipo||{};
    if(Object.keys(rt).length){
      Plotly.newPlot('chart-errores',[{type:'bar',x:Object.keys(rt),y:Object.values(rt),
        marker:{color:['#f85149','#f0883e','#e3b341','#8b949e']}}],
        {...PL},{responsive:true,displayModeBar:false});
    }
  }catch(e){}
}

async function cargarCausacionesGrafica(fecha){
  try{
    _causData=await fetchJSON(`/api/porfin/causaciones/${fecha}`);
    const cm=_causData.causacion_mercado_total,ct=_causData.causacion_tir_total;
    if(cm!=null&&ct!=null){
      Plotly.newPlot('chart-causacion',[
        {type:'bar',name:'Mer',x:['Causación'],y:[cm],marker:{color:'#3fb950'}},
        {type:'bar',name:'TIR',x:['Causación'],y:[ct],marker:{color:'#58a6ff'}},
      ],{...PL,barmode:'group'},{responsive:true,displayModeBar:false});
    }
    document.getElementById('pills-causacion').innerHTML=[
      ['Mer Total',fmt(cm),'green'],['TIR Total',fmt(ct),'blue'],
      ['Dif Mer-TIR',fmt(_causData.diferencia_mer_tir),'yellow'],
      ['Vlr Hoy',fmt(_causData.vlr_mercado_hoy),'purple'],
      ['Delta',fmt(_causData.delta_valoracion),'orange'],
    ].map(([l,v,c])=>`<span class="pill ${c}"><span>${l}</span><strong>${v}</strong></span>`).join('');
    if(document.getElementById('tab-causaciones').classList.contains('active'))renderCausaciones();
  }catch(e){}
}

// ── POSICIONES 596 ────────────────────────────────────────────────────────────
async function cargarPosiciones(){
  const fecha=document.getElementById('sel-fecha').value;
  if(!fecha)return;
  const params=new URLSearchParams();
  const b=document.getElementById('fil-busqueda').value;
  const m=document.getElementById('fil-moneda').value;
  const p=document.getElementById('fil-portafolio').value;
  const a=document.getElementById('solo-alertas').checked;
  if(b)params.set('busqueda',b);if(m)params.set('moneda',m);if(p)params.set('portafolio',p);
  if(a)params.set('solo_alertas','true');params.set('limit','3000');
  const wrap=document.getElementById('wrap-596');
  wrap.innerHTML='<div class="empty"><span class="spinner"></span></div>';
  try{
    _posData=await fetchJSON(`/api/porfin/posiciones/${fecha}?${params}`);
    render596(_posData);
    document.getElementById('count-596').textContent=`${_posData.length} registros`;
    document.getElementById('kpi-obs').textContent=_posData.filter(r=>r.OBS).length;
  }catch(e){wrap.innerHTML=`<div class="empty">Error: ${e.message}</div>`;}
}

function render596(rows){
  const wrap=document.getElementById('wrap-596');
  if(!rows.length){wrap.innerHTML='<div class="empty">Sin posiciones para los filtros aplicados</div>';return;}
  const cols=['CLASE','ESPECIE','TITULO','ISIN','NEMO','EMISION','VCTO','NOMINAL','MONEDA','VLR_MERCADO','PRECIO','TIR','TASA_MER','DURACION','PORTAFOLIO','LLAVE','PUC'];
  const avail=cols.filter(c=>rows[0].hasOwnProperty(c));
  let html=`<table><thead><tr>${avail.map(c=>`<th>${c}</th>`).join('')}<th>OBS</th></tr></thead><tbody>`;
  for(const r of rows){
    const isA=r.ALERTA===true,hasO=r.OBS&&r.OBS.trim();
    html+=`<tr class="${isA?'alert-row':hasO?'obs-row':''}">`;
    for(const c of avail){
      const v=r[c];
      if(v==null||v===false){html+=`<td>—</td>`;continue;}
      if(['VLR_MERCADO','VLR_MER_OR','NOMINAL'].includes(c))html+=`<td class="${nc(v)}">${fmt(v,2)}</td>`;
      else if(['PRECIO','TIR','TASA_MER','DURACION'].includes(c))html+=`<td class="n-pos">${fmtN(v,6)}</td>`;
      else html+=`<td>${String(v).trim()}</td>`;
    }
    const rid=r._ROW_ID!=null?r._ROW_ID:'';const ov=r.OBS||'';
    html+=`<td><div class="obs-cell">
      <input class="obs-input ${ov?'has-obs':''}" id="obs-${rid}" value="${esc(ov)}" placeholder="obs..." data-row="${rid}" data-modulo="porfin596"/>
      <button class="obs-btn" onclick="guardarObs('${rid}','porfin596')" title="Guardar">✓</button>
    </div></td></tr>`;
  }
  html+='</tbody></table>';
  wrap.innerHTML=html;
  wrap.querySelectorAll('.obs-input').forEach(inp=>{
    inp.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();guardarObs(inp.dataset.row,inp.dataset.modulo);}});
  });
}

// ── OBSERVACIONES ─────────────────────────────────────────────────────────────
async function guardarObs(rowId,modulo){
  const fecha=document.getElementById('sel-fecha').value;
  const inp=document.getElementById('obs-'+rowId);
  if(!inp)return;
  const obs=inp.value.trim();
  try{
    const r=await fetch(`/api/porfin/observaciones/${fecha}`,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({fila:String(rowId),obs,modulo})});
    const j=await r.json();
    if(j.ok){
      inp.classList.toggle('has-obs',!!obs);
      inp.closest('tr').className=obs?'obs-row':'';
      inp.style.borderBottomColor='var(--green2)';
      setTimeout(()=>{inp.style.borderBottomColor='';},700);
      document.getElementById('kpi-obs').textContent=_posData.filter(r=>r.OBS).length;
    }
  }catch(e){}
}

// ── CAUSACIONES 575 ────────────────────────────────────────────────────────────
function renderCausaciones(){
  if(!_causData||!_causData.detalle)return;
  const busq=(document.getElementById('fil-busq-575').value||'').toUpperCase();
  const soloA=document.getElementById('solo-alertas-575').checked;
  let rows=_causData.detalle||[];
  if(busq)rows=rows.filter(r=>['ESPECIE','TITULO','ISIN'].some(c=>r[c]&&String(r[c]).toUpperCase().includes(busq)));
  if(soloA)rows=rows.filter(r=>r.DIF_MER_TIR!=null&&Math.abs(r.DIF_MER_TIR)>1);
  document.getElementById('count-575').textContent=`${rows.length} registros`;
  const wrap=document.getElementById('wrap-causaciones');
  if(!rows.length){wrap.innerHTML='<div class="empty">Sin registros</div>';return;}
  const cols=['ESPECIE','TITULO','ISIN','VCTO','NOMINAL','VLR_MER_ANT','VLR_MER_HOY','CAUSACION_MER','CAUSACION_TIR','DIF_MER_TIR','PRECIO','TIR','MONEDA','PORTAFOLIO'];
  const avail=cols.filter(c=>rows[0].hasOwnProperty(c));
  let html=`<table><thead><tr>${avail.map(c=>`<th>${c}</th>`).join('')}<th>OBS</th></tr></thead><tbody>`;
  for(const r of rows){
    const dif=r.DIF_MER_TIR,isA=dif!=null&&Math.abs(dif)>1,hasO=r.OBS&&r.OBS.trim();
    html+=`<tr class="${isA?'alert-row':hasO?'obs-row':''}">`;
    for(const c of avail){
      const v=r[c];if(v==null){html+=`<td>—</td>`;continue;}
      if(['VLR_MER_ANT','VLR_MER_HOY','CAUSACION_MER','CAUSACION_TIR','DIF_MER_TIR','NOMINAL'].includes(c))html+=`<td class="${nc(v)}">${fmt(v,2)}</td>`;
      else if(['PRECIO','TIR'].includes(c))html+=`<td>${fmtN(v,6)}</td>`;
      else html+=`<td>${String(v).trim()}</td>`;
    }
    const rid=r._ROW_ID!=null?r._ROW_ID:'';const ov=r.OBS||'';
    html+=`<td><div class="obs-cell">
      <input class="obs-input ${ov?'has-obs':''}" id="obs575-${rid}" value="${esc(ov)}" placeholder="obs..." data-row="${rid}" data-modulo="porfin575"/>
      <button class="obs-btn" onclick="guardarObs575('${rid}')" title="✓">✓</button>
    </div></td></tr>`;
  }
  html+='</tbody></table>';
  wrap.innerHTML=html;
  wrap.querySelectorAll('.obs-input').forEach(inp=>{
    inp.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();guardarObs575(inp.dataset.row);}});
  });
}

async function guardarObs575(rowId){
  const fecha=document.getElementById('sel-fecha').value;
  const inp=document.getElementById('obs575-'+rowId);
  if(!inp)return;
  const obs=inp.value.trim();
  try{
    const r=await fetch(`/api/porfin/observaciones/${fecha}`,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({fila:String(rowId),obs,modulo:'porfin575'})});
    const j=await r.json();
    if(j.ok){inp.classList.toggle('has-obs',!!obs);inp.style.borderBottomColor='var(--green2)';setTimeout(()=>{inp.style.borderBottomColor='';},700);}
  }catch(e){}
}

// ── ERRORES ────────────────────────────────────────────────────────────────────
function renderErrores(){
  if(!_erroresData)return;
  let errores=_erroresData.errores||[];
  const sev=document.getElementById('fil-severidad').value;
  const tipo=document.getElementById('fil-tipo-error').value;
  const busq=(document.getElementById('fil-busq-error').value||'').toUpperCase();
  if(sev)errores=errores.filter(e=>e.severidad===sev);
  if(tipo)errores=errores.filter(e=>e.tipo===tipo);
  if(busq)errores=errores.filter(e=>(e.isin+e.especie+e.portafolio).toUpperCase().includes(busq));
  document.getElementById('count-errores').textContent=`${errores.length} errores`;
  const wrap=document.getElementById('wrap-errores');
  if(!errores.length){wrap.innerHTML='<div class="empty" style="color:var(--green2)">✓ Sin errores para los filtros aplicados</div>';return;}
  const sMap={'ALTO':'badge-red','MEDIO':'badge-yellow','BAJO':'badge-green'};
  let html='<table><thead><tr><th>Sev.</th><th>Tipo</th><th>ISIN</th><th>Especie</th><th>Portafolio</th><th>Detalle</th></tr></thead><tbody>';
  for(const e of errores){
    html+=`<tr class="${e.severidad==='ALTO'?'alert-row':''}">
      <td><span class="badge ${sMap[e.severidad]||''}">${e.severidad}</span></td>
      <td>${e.tipo}</td><td>${e.isin||'—'}</td><td>${e.especie||'—'}</td>
      <td>${e.portafolio||'—'}</td>
      <td style="color:var(--muted2);max-width:280px;white-space:normal;font-size:.72rem;">${e.detalle}</td>
    </tr>`;
  }
  html+='</tbody></table>';
  wrap.innerHTML=html;
}

// ── PORTAFOLIOS y MONEDAS se definen más abajo (versión con gráficas) ──────────

// ── FONDOS ────────────────────────────────────────────────────────────────────
async function cargarFondos(){
  const fecha=document.getElementById('sel-fecha').value;
  if(!fecha)return;
  try{
    _fondosData=await fetchJSON(`/api/porfin/fondos/${fecha}`);
    renderFondos();
    const fondos=(_fondosData.fondos||[]).slice(0,15);
    if(fondos.length){
      const names=fondos.map(f=>f.FONDO).reverse();
      const vals=fondos.map(f=>f.vlr_hoy).reverse();
      const colors=fondos.map(f=>Math.abs(f.dif_caus||0)>1e6?'#f85149':'#1f6feb').reverse();
      Plotly.newPlot('chart-fondos',[{
        type:'bar',orientation:'h',x:vals,y:names,marker:{color:colors},
        text:fondos.map(f=>fmt(f.vlr_hoy)).reverse(),textposition:'outside',
      }],{...PL,margin:{t:5,b:25,l:55,r:80},xaxis:{...PL.xaxis,tickformat:',.0s'}},{responsive:true,displayModeBar:false});
    }
    document.getElementById('kpi-fondos-row').innerHTML=[
      ['Total fondos',_fondosData.total_fondos,'var(--blue2)'],
      ['Vlr Mercado',fmt(_fondosData.total_vlr_mercado),'var(--purple2)'],
      ['Causación Mer.',fmt(_fondosData.total_causacion_mer),'var(--green2)'],
      ['Fondos c/alerta',(_fondosData.fondos||[]).filter(f=>Math.abs(f.dif_caus||0)>1e6).length,'var(--red2)'],
    ].map(([l,v,c])=>`<div style="background:var(--surface2);border:1px solid var(--border2);border-radius:var(--radius-lg);padding:.65rem .85rem;">
      <div style="font-size:.65rem;color:var(--muted);text-transform:uppercase;margin-bottom:.25rem;">${l}</div>
      <div style="font-size:1.1rem;font-weight:700;color:${c}">${v}</div>
    </div>`).join('');
    _renderFondoCausChart();
    const monData=await fetchJSON(`/api/porfin/monedas_fondos/${fecha}`);
    if(monData.length){
      Plotly.newPlot('chart-mon-fondos',[{type:'pie',labels:monData.map(m=>m.MON_NORM),values:monData.map(m=>Math.abs(m.vlr_hoy)),
        hole:.4,textinfo:'label+percent',
        marker:{colors:['#1f6feb','#3fb950','#e3b341','#f85149','#bc8cff','#58a6ff','#f0883e','#8b949e']},
      }],{...PL,margin:{t:5,b:5,l:5,r:5}},{responsive:true,displayModeBar:false});
    }
  }catch(e){document.getElementById('wrap-fondos').innerHTML=`<div class="empty">Error: ${e.message}</div>`;}
}

function renderFondos(){
  if(!_fondosData)return;
  let fondos=_fondosData.fondos||[];
  const busq=(document.getElementById('fil-busq-fondo').value||'').toUpperCase();
  const soloAl=document.getElementById('solo-alertas-fondo').checked;
  if(busq)fondos=fondos.filter(f=>f.FONDO.toUpperCase().includes(busq));
  if(soloAl)fondos=fondos.filter(f=>Math.abs(f.dif_caus||0)>1e6);
  const wrap=document.getElementById('wrap-fondos');
  if(!fondos.length){wrap.innerHTML='<div class="empty">Sin fondos</div>';return;}
  const totalVlr=fondos.reduce((s,f)=>s+(f.vlr_hoy||0),0);
  let html=`<table><thead><tr>
    <th>Fondo</th><th>Portafolios</th><th>Posiciones</th>
    <th>Vlr Hoy</th><th>%</th><th>Delta Valor</th>
    <th>Caus Mer</th><th>Caus TIR</th><th>Dif Caus</th><th></th>
  </tr></thead><tbody>`;
  for(const f of fondos){
    const pct=totalVlr?((f.vlr_hoy/totalVlr)*100).toFixed(1):'—';
    const difAlert=Math.abs(f.dif_caus||0)>1e6;
    html+=`<tr class="${difAlert?'alert-row':''}">
      <td><strong style="color:var(--blue2);cursor:pointer;" onclick="seleccionarFondo('${f.FONDO}')">${f.FONDO}</strong></td>
      <td>${f.portafolios}</td><td>${f.posiciones.toLocaleString()}</td>
      <td class="${nc(f.vlr_hoy)}">${fmt(f.vlr_hoy,2)}</td>
      <td style="color:var(--muted)">${pct}%</td>
      <td class="${nc(f.delta_valor)}">${fmt(f.delta_valor,2)}</td>
      <td class="${nc(f.caus_mer)}">${fmt(f.caus_mer,2)}</td>
      <td class="${nc(f.caus_tir)}">${fmt(f.caus_tir,2)}</td>
      <td class="${difAlert?'n-neg':nc(f.dif_caus)}">${fmt(f.dif_caus,2)}</td>
      <td><button class="btn btn-ghost btn-sm" onclick="seleccionarFondo('${f.FONDO}')">Ver →</button></td>
    </tr>`;
  }
  const totDelta=fondos.reduce((s,f)=>s+(f.delta_valor||0),0);
  const totCM=fondos.reduce((s,f)=>s+(f.caus_mer||0),0);
  const totCT=fondos.reduce((s,f)=>s+(f.caus_tir||0),0);
  const totDif=fondos.reduce((s,f)=>s+(f.dif_caus||0),0);
  html+=`<tr style="font-weight:700;border-top:2px solid var(--border2);background:var(--surface2);">
    <td colspan="3">TOTAL (${fondos.length})</td>
    <td class="${nc(totalVlr)}">${fmt(totalVlr,2)}</td><td>100%</td>
    <td class="${nc(totDelta)}">${fmt(totDelta,2)}</td>
    <td class="${nc(totCM)}">${fmt(totCM,2)}</td>
    <td class="${nc(totCT)}">${fmt(totCT,2)}</td>
    <td class="${nc(totDif)}">${fmt(totDif,2)}</td><td></td>
  </tr>`;
  html+='</tbody></table>';
  wrap.innerHTML=html;
}

function seleccionarFondo(fondo){
  _fondoSel=fondo;
  document.getElementById('fondo-detalle-titulo').textContent=`Fondo ${fondo} — detalle`;
  document.getElementById('wrap-fondos-lista').style.display='none';
  document.getElementById('wrap-fondo-detalle').style.display='block';
  cargarFondoDetalle();
}
function limpiarFondoSeleccionado(){
  _fondoSel=null;
  document.getElementById('wrap-fondos-lista').style.display='block';
  document.getElementById('wrap-fondo-detalle').style.display='none';
}

async function cargarFondoDetalle(){
  if(!_fondoSel)return;
  const fecha=document.getElementById('sel-fecha').value;
  const mon=document.getElementById('fil-mon-detalle').value;
  const soloAl=document.getElementById('solo-alertas-detalle').checked;
  const wrap=document.getElementById('wrap-fondo-detalle-tabla');
  wrap.innerHTML='<div class="empty"><span class="spinner"></span></div>';
  try{
    const params=new URLSearchParams();
    if(mon)params.set('moneda',mon);if(soloAl)params.set('solo_alertas','true');
    const rows=await fetchJSON(`/api/porfin/fondos/${fecha}/${_fondoSel}?${params}`);
    const vlrTot=rows.reduce((s,r)=>s+(r.VLR_MER_HOY||0),0);
    const causTot=rows.reduce((s,r)=>s+(r.CAUSACION_MER||0),0);
    const alertas=rows.filter(r=>r.ALERTA_CAUS).length;
    document.getElementById('kpi-fondo-sel').innerHTML=[
      ['Posiciones',rows.length,'var(--blue2)'],['Vlr Hoy',fmt(vlrTot,2),'var(--purple2)'],
      ['Caus Mer',fmt(causTot,2),'var(--green2)'],['Alertas',alertas,alertas?'var(--red2)':'var(--green2)'],
    ].map(([l,v,c])=>`<span class="fondo-kpi"><span>${l}: </span><strong style="color:${c}">${v}</strong></span>`).join('');
    if(!rows.length){wrap.innerHTML='<div class="empty">Sin posiciones</div>';return;}
    const cols=['PORTAFOLIO','ESPECIE','TITULO','ISIN','VCTO','NOMINAL','MON_NORM','VLR_MER_ANT','VLR_MER_HOY','CAUSACION_MER','CAUSACION_TIR','DIF_MER_TIR','PRECIO','TIR','METODO','ESTADO'];
    const avail=cols.filter(c=>rows[0].hasOwnProperty(c));
    let html=`<table><thead><tr>${avail.map(c=>`<th>${c}</th>`).join('')}<th>OBS</th></tr></thead><tbody>`;
    for(const r of rows){
      const isA=r.ALERTA_CAUS===true,hasO=r.OBS&&r.OBS.trim();
      html+=`<tr class="${isA?'alert-row':hasO?'obs-row':''}">`;
      for(const c of avail){
        const v=r[c];if(v==null||v===false){html+=`<td>—</td>`;continue;}
        if(['VLR_MER_ANT','VLR_MER_HOY','CAUSACION_MER','CAUSACION_TIR','DIF_MER_TIR','NOMINAL'].includes(c))html+=`<td class="${nc(v)}">${fmt(v,2)}</td>`;
        else if(['PRECIO','TIR'].includes(c))html+=`<td>${fmtN(v,6)}</td>`;
        else html+=`<td>${String(v).trim()}</td>`;
      }
      const rid=r._ROW_ID!=null?r._ROW_ID:'';const ov=r.OBS||'';
      html+=`<td><div class="obs-cell">
        <input class="obs-input ${ov?'has-obs':''}" id="obs-fd-${rid}" value="${esc(ov)}" placeholder="obs..." data-row="${rid}" data-modulo="porfin575"/>
        <button class="obs-btn" onclick="guardarObsFondo('${rid}')" title="✓">✓</button>
      </div></td></tr>`;
    }
    html+='</tbody></table>';
    wrap.innerHTML=html;
    wrap.querySelectorAll('.obs-input').forEach(inp=>{inp.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();guardarObsFondo(inp.dataset.row);}});});
  }catch(e){wrap.innerHTML=`<div class="empty">Error: ${e.message}</div>`;}
}

async function guardarObsFondo(rowId){
  const fecha=document.getElementById('sel-fecha').value;
  const inp=document.getElementById('obs-fd-'+rowId);if(!inp)return;
  const obs=inp.value.trim();
  try{
    const r=await fetch(`/api/porfin/observaciones/${fecha}`,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({fila:String(rowId),obs,modulo:'porfin575'})});
    const j=await r.json();
    if(j.ok){inp.classList.toggle('has-obs',!!obs);inp.style.borderBottomColor='var(--green2)';setTimeout(()=>{inp.style.borderBottomColor='';},700);}
  }catch(e){}
}

// ── ALERTAS TIR/DV ────────────────────────────────────────────────────────────
async function cargarTirBadge(fecha){
  try{
    const d=await fetchJSON(`/api/porfin/alertas_tir/${fecha}`);
    _tirData596=d;
    const badge=document.getElementById('tir-badge');
    if(d.total_alertas>0){badge.style.display='inline-block';badge.textContent=d.total_alertas;}
  }catch(e){}
}

async function cargarTir(){
  const fecha=document.getElementById('sel-fecha').value;if(!fecha)return;
  if(!_tirData596){try{_tirData596=await fetchJSON(`/api/porfin/alertas_tir/${fecha}`);}catch(e){}}
  try{
    const cfg=await fetchJSON(`/api/porfin/config_columnas/${fecha}`);
    document.getElementById('tir-config-info').innerHTML=
      `<strong>Columnas 596:</strong> METODO="${cfg['596'].col_metodo}" (DV=al vencimiento) | `+
      `FUENTE_TIT="${cfg['596'].col_fuente}" (1DV=al vencimiento) | `+
      `Mét="${cfg['596'].col_met_curva}" (TC=Tasa Cupón/TIR implícita) &nbsp;·&nbsp; `+
      `<strong>575:</strong> METODO="${cfg['575'].col_metodo}" | Mét="${cfg['575'].col_met_curva}"`;
  }catch(e){}
  showTirTab('596');
}

async function showTirTab(archivo){
  _tirActivo=archivo;
  document.getElementById('btn-tir-596').className='subtab'+(archivo==='596'?' active':'');
  document.getElementById('btn-tir-575').className='subtab'+(archivo==='575'?' active':'');
  const fecha=document.getElementById('sel-fecha').value;
  if(archivo==='575'&&!_tirData575){
    try{_tirData575=await fetchJSON(`/api/porfin/alertas_tir_575/${fecha}`);}catch(e){_tirData575={alertas:[]};}
  }
  renderTir();
}

function renderTir(){
  const data=_tirActivo==='596'?_tirData596:_tirData575;
  if(!data){document.getElementById('wrap-tir').innerHTML='<div class="empty"><span class="spinner"></span></div>';return;}
  const busq=(document.getElementById('fil-busq-tir').value||'').toUpperCase();
  const motFil=document.getElementById('fil-motivo-tir').value.toUpperCase();
  let alertas=data.alertas||[];
  if(busq)alertas=alertas.filter(a=>(a.isin+a.especie+(a.portafolio||'')).toUpperCase().includes(busq));
  if(motFil)alertas=alertas.filter(a=>a.motivo.toUpperCase().includes(motFil));
  document.getElementById('count-tir').textContent=`${alertas.length} alertas`;
  const resumen=data.resumen_motivo||{};
  document.getElementById('tir-resumen').innerHTML=Object.entries(resumen).map(([k,v])=>
    `<span class="pill red"><span>${k}</span><strong>${v}</strong></span>`).join('');
  const wrap=document.getElementById('wrap-tir');
  if(!alertas.length){wrap.innerHTML='<div class="empty" style="color:var(--green2)">✓ Sin títulos valorando a TIR/curva propia.</div>';return;}
  const cols596=['motivo','isin','especie','emision','vcto','metodo','fuente_tit','met_curva','precio','tir','portafolio','nominal','vlr_mercado'];
  const cols575=['motivo','isin','especie','metodo','met_curva','precio','tir','vlr_mer_hoy','causacion_mer','portafolio'];
  const cols=_tirActivo==='596'?cols596:cols575;
  const avail=cols.filter(c=>alertas[0].hasOwnProperty(c));
  let html=`<table><thead><tr>${avail.map(c=>`<th>${c.toUpperCase()}</th>`).join('')}</tr></thead><tbody>`;
  for(const a of alertas){
    html+=`<tr class="alert-row">`;
    for(const c of avail){
      const v=a[c];if(v==null){html+=`<td>—</td>`;continue;}
      if(c==='motivo')html+=`<td style="white-space:normal;max-width:180px;"><span class="badge badge-red">${v}</span></td>`;
      else if(['nominal','vlr_mercado','vlr_mer_hoy','causacion_mer'].includes(c))html+=`<td class="${nc(v)}">${fmt(v,2)}</td>`;
      else if(['precio','tir'].includes(c))html+=`<td>${fmtN(v,6)}</td>`;
      else html+=`<td>${String(v).trim()}</td>`;
    }
    html+='</tr>';
  }
  html+='</tbody></table>';
  wrap.innerHTML=html;
}

// ── EXPORT ────────────────────────────────────────────────────────────────────
function descargarExcel(){
  const fecha=document.getElementById('sel-fecha').value;
  if(!fecha){alert('Selecciona una fecha.');return;}
  window.location=`/api/porfin/excel/${fecha}`;
}
function exportarCSV(){
  if(!_posData.length){alert('No hay datos cargados.');return;}
  const keys=Object.keys(_posData[0]).filter(k=>k!=='_ROW_ID');
  const csv=[keys.join(','),..._posData.map(r=>keys.map(k=>{const v=r[k];if(v==null)return'';if(typeof v==='string'&&v.includes(','))return`"${v}"`;return v;}).join(','))].join('\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8;'}));
  a.download=`porfin_${document.getElementById('sel-fecha').value}.csv`;a.click();
}
function toggleSoloAlertas(){
  const cb=document.getElementById('solo-alertas');cb.checked=!cb.checked;cargarPosiciones();
}

// ── VERIFICACIÓN ──────────────────────────────────────────────────────────────
let _verifData=[], _verifCausData=[], _verifSubtab='valoracion';

function switchVerifSubtab(sub,el){
  _verifSubtab=sub;
  document.querySelectorAll('.subtab').forEach(b=>{
    if(b.id&&b.id.startsWith('vsubtab'))b.classList.remove('active');
  });
  el.classList.add('active');
  document.getElementById('wrap-verif-valoracion').style.display=sub==='valoracion'?'':'none';
  document.getElementById('wrap-verif-causacion').style.display=sub==='causacion'?'':'none';
}

async function cargarVerificacion(){
  const fecha=document.getElementById('sel-fecha').value;
  if(!fecha){alert('Selecciona una fecha.');return;}
  const umbPct=parseFloat(document.getElementById('verif-umbral-pct').value)||1;
  const umbAbs=parseFloat(document.getElementById('verif-umbral-abs').value)||1000;
  const soloAl=document.getElementById('verif-solo-alertas').checked;
  const port=document.getElementById('verif-portafolio').value.trim();

  // Verificación valoración
  const wv=document.getElementById('wrap-verificacion');
  wv.innerHTML='<div class="empty"><span class="spinner"></span> Calculando verificación de valoración…</div>';
  try{
    const params=new URLSearchParams({umbral_pct:umbPct,umbral_abs:umbAbs});
    if(soloAl)params.set('solo_alertas','true');
    if(port)params.set('portafolio',port);
    const d=await fetchJSON(`/api/porfin/verificacion/${fecha}?${params}`);
    _verifData=d.filas||[];

    document.getElementById('kv-total').textContent=fmt(d.total);
    document.getElementById('kv-con-precio').textContent=fmt(d.con_precio_infovalmer);
    document.getElementById('kv-sin-precio').textContent=fmt(d.sin_precio_infovalmer);
    document.getElementById('kv-alertas').textContent=fmt(d.total_alertas);
    document.getElementById('kv-sin-tipo').textContent=fmt(d.sin_tipo);

    const badge=document.getElementById('verif-badge');
    if(d.total_alertas>0){badge.textContent=d.total_alertas;badge.style.display='';}
    else{badge.style.display='none';}

    renderVerifTable();
    _renderVerifCharts();
  }catch(e){wv.innerHTML=`<div class="empty">Error: ${e.message}</div>`;}

  // Verificación causación
  const wc=document.getElementById('wrap-verif-caus-tabla');
  wc.innerHTML='<div class="empty"><span class="spinner"></span> Calculando verificación de causación…</div>';
  try{
    const params=new URLSearchParams({umbral_abs:umbAbs});
    if(soloAl)params.set('solo_alertas','true');
    if(port)params.set('portafolio',port);
    const d2=await fetchJSON(`/api/porfin/verificacion_causacion/${fecha}?${params}`);
    _verifCausData=d2.filas||[];

    document.getElementById('kvc-total').textContent=fmt(d2.total);
    document.getElementById('kvc-alertas').textContent=fmt(d2.total_alertas);
    document.getElementById('kvc-dif-total').textContent=fmtN(d2.dif_total_causacion);
    document.getElementById('kvc-int-div').textContent=fmtN(d2.total_int_div||0);
    const el583=document.getElementById('kvc-583');
    el583.textContent=d2.tiene_583?'✓ Disponible':'✗ No encontrado';
    el583.style.color=d2.tiene_583?'var(--green2)':'var(--muted)';

    // Banner 583 faltante
    const ban583=document.getElementById('banner-583-faltante');
    if(ban583)ban583.style.display=d2.tiene_583?'none':'flex';

    renderVerifCausTable();
  }catch(e){wc.innerHTML=`<div class="empty">Error causación: ${e.message}</div>`;}
}

function renderVerifTable(){
  const wrap=document.getElementById('wrap-verificacion');
  if(!_verifData.length){wrap.innerHTML='<div class="empty">Sin datos — verifica que Especies.csv esté configurado en Ajustes.</div>';return;}
  const cols=['ESPECIE','TITULO','ISIN','KEYA','PORTAFOLIO','TIPO','MONEDA','NOMINAL',
              'PRECIO_PORFIN','PRECIO_INFOVALMER','FACTOR_MONEDA',
              'VALORACION_PORFIN','VALORACION_MANUAL','DIF_ABS','DIF_PCT','ALERTA','MOTIVO_ALERTA'];
  const show=cols.filter(c=>_verifData.some(r=>r[c]!=null&&r[c]!==''));
  let html=`<table class="data-table"><thead><tr>${show.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>`;
  for(const r of _verifData){
    const alerta=r.ALERTA;
    const cls=alerta?'style="background:rgba(185,28,28,.18);"':'';
    html+=`<tr ${cls}>`;
    for(const c of show){
      const v=r[c];
      let cell='';
      if(v==null){cell='<td style="color:var(--muted)">—</td>';}
      else if(c==='ALERTA'){cell=`<td>${v?'<span style="color:var(--red2);font-weight:700">⚠</span>':'<span style="color:var(--green2)">✓</span>'}</td>`;}
      else if(c==='DIF_PCT'&&v!=null){const cl=Math.abs(v)>5?'c-err':Math.abs(v)>1?'c-warn':'';cell=`<td class="${cl}">${v.toFixed(4)}%</td>`;}
      else if(c==='DIF_ABS'&&v!=null){const cl=Math.abs(v)>1000000?'c-err':Math.abs(v)>1000?'c-warn':'';cell=`<td class="${cl}">${fmtN(v)}</td>`;}
      else if(['NOMINAL','VLR_MER_OR','VALORACION_PORFIN','VALORACION_MANUAL'].includes(c)&&typeof v==='number'){cell=`<td style="text-align:right">${fmtN(v)}</td>`;}
      else if(['PRECIO_PORFIN','PRECIO_INFOVALMER','FACTOR_MONEDA'].includes(c)&&typeof v==='number'){cell=`<td style="text-align:right">${v.toFixed(6)}</td>`;}
      else{cell=`<td>${String(v||'').trim()}</td>`;}
      html+=cell;
    }
    html+='</tr>';
  }
  html+='</tbody></table>';
  wrap.innerHTML=html;
}

function renderVerifCausTable(){
  const wrap=document.getElementById('wrap-verif-caus-tabla');
  if(!_verifCausData.length){wrap.innerHTML='<div class="empty">Sin datos de causación.</div>';return;}
  const cols=['ESPECIE','TITULO','ISIN','PORTAFOLIO','MONEDA','NOMINAL',
              'VLR_MER_ANT','VLR_MER_HOY','INT_DIV','CAUSACION_MER_PORFIN','CAUSACION_TIR_PORFIN',
              'CAUSACION_MANUAL','METODO_CAUS','DIF_CAUSACION','ALERTA','MOTIVO'];
  const show=cols.filter(c=>_verifCausData.some(r=>r[c]!=null&&r[c]!==''));
  let html=`<table class="data-table"><thead><tr>${show.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>`;
  for(const r of _verifCausData){
    const alerta=r.ALERTA;
    const cls=alerta?'style="background:rgba(185,28,28,.18);"':'';
    html+=`<tr ${cls}>`;
    for(const c of show){
      const v=r[c];
      let cell='';
      if(v==null){cell='<td style="color:var(--muted)">—</td>';}
      else if(c==='ALERTA'){cell=`<td>${v?'<span style="color:var(--red2);font-weight:700">⚠</span>':'<span style="color:var(--green2)">✓</span>'}</td>`;}
      else if(c==='DIF_CAUSACION'&&v!=null){const cl=Math.abs(v)>1000000?'c-err':Math.abs(v)>1000?'c-warn':'';cell=`<td class="${cl}">${fmtN(v)}</td>`;}
      else if(['NOMINAL','VLR_MER_ANT','VLR_MER_HOY','INT_DIV','CAUSACION_MER_PORFIN','CAUSACION_TIR_PORFIN','CAUSACION_MANUAL'].includes(c)&&typeof v==='number'){cell=`<td style="text-align:right">${fmtN(v)}</td>`;}
      else{cell=`<td>${String(v||'').trim()}</td>`;}
      html+=cell;
    }
    html+='</tr>';
  }
  html+='</tbody></table>';
  wrap.innerHTML=html;
}

function exportarVerifCSV(){
  const data=_verifSubtab==='causacion'?_verifCausData:_verifData;
  if(!data.length){alert('Primero calcula la verificación.');return;}
  const keys=Object.keys(data[0]);
  const csv=[keys.join(','),...data.map(r=>keys.map(k=>{const v=r[k];if(v==null)return'';if(typeof v==='string'&&v.includes(','))return`"${v}"`;return v;}).join(','))].join('\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8;'}));
  a.download=`verificacion_${_verifSubtab}_${document.getElementById('sel-fecha').value}.csv`;a.click();
}

// fmtN definida arriba (versión unificada)

// ── OPERACIONES 583 ───────────────────────────────────────────────────────────
let _ops583Data=[], _ops583Raw=null;

async function cargarOps583(){
  const fecha=document.getElementById('sel-fecha').value;
  if(!fecha)return;
  const wrap=document.getElementById('wrap-ops');
  wrap.innerHTML='<div class="empty"><span class="spinner"></span> Cargando operaciones 583…</div>';
  try{
    _ops583Raw=await fetchJSON(`/api/porfin/operaciones/${fecha}`);
    if(_ops583Raw.error){
      wrap.innerHTML=`<div class="empty">⚠ ${_ops583Raw.error} — Carga el archivo 583 en ⬆ Cargar</div>`;
      return;
    }
    _ops583Data=_ops583Raw.registros||[];

    // KPIs
    document.getElementById('ops-total').textContent=fmt(_ops583Raw.total_registros);
    document.getElementById('ops-intdiv').textContent=fmtN(_ops583Raw.total_int_div||0);
    document.getElementById('ops-incret').textContent=fmtN(_ops583Raw.total_inc_ret||0);
    document.getElementById('ops-archivo').textContent=_ops583Raw.archivo||'—';

    // Badge tab
    const tipos=_ops583Raw.tipos_transaccion||{};
    const badge=document.getElementById('ops-badge');
    if(_ops583Raw.total_registros>0){badge.textContent=_ops583Raw.total_registros;badge.style.display='';}

    // Poblar filtro tipo
    const sel=document.getElementById('fil-tipo-ops');
    sel.innerHTML='<option value="">Todos los tipos</option>'+
      Object.keys(tipos).sort().map(t=>`<option value="${t}">${t} (${tipos[t]})</option>`).join('');

    renderOps();
    _renderOpsCharts();
  }catch(e){
    wrap.innerHTML=`<div class="empty">Sin archivo 583 para ${fecha}. Cárgalo en ⬆ Cargar.</div>`;
  }
}

function renderOps(){
  if(!_ops583Data.length){return;}
  const busq=(document.getElementById('fil-busq-ops').value||'').toUpperCase();
  const tipo=document.getElementById('fil-tipo-ops').value.toUpperCase();
  let rows=_ops583Data;
  if(busq)rows=rows.filter(r=>['ISIN','ESPECIE','CONSEC','PORTAFOLIO'].some(c=>r[c]&&String(r[c]).toUpperCase().includes(busq)));
  if(tipo)rows=rows.filter(r=>r.TRANSACCION&&r.TRANSACCION.toUpperCase().includes(tipo));
  document.getElementById('count-ops').textContent=`${rows.length} registros`;
  const wrap=document.getElementById('wrap-ops');
  if(!rows.length){wrap.innerHTML='<div class="empty">Sin registros para los filtros aplicados</div>';return;}
  const cols=['TRANSACCION','TIPO_OPER','CONSEC','ESPECIE','ISIN','MONEDA','VAL_OPERACION','PRECIO_OPE','VR_RECIBIDO','PORTAFOLIO'];
  const avail=cols.filter(c=>rows[0].hasOwnProperty(c));
  let html=`<table><thead><tr>${avail.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>`;
  const _cls=t=>{
    if(!t)return '';t=t.toUpperCase();
    if(t.includes('COBRO'))return 'style="background:rgba(63,185,80,.08);"';
    if(t.includes('RETIRO'))return 'style="background:rgba(248,81,73,.08);"';
    if(t.includes('INCREMENTO'))return 'style="background:rgba(88,166,255,.08);"';
    return '';
  };
  for(const r of rows){
    html+=`<tr ${_cls(r.TRANSACCION)}>`;
    for(const c of avail){
      const v=r[c];if(v==null){html+=`<td>—</td>`;continue;}
      if(c==='TRANSACCION'){
        const t=String(v).trim().toUpperCase();
        const bc=t.includes('COBRO')?'badge-green':t.includes('RETIRO')?'badge-red':t.includes('INCREMENTO')?'badge-blue':'badge-yellow';
        html+=`<td><span class="badge ${bc}">${v}</span></td>`;
      }else if(['VAL_OPERACION','VR_RECIBIDO'].includes(c)&&typeof v==='number'){
        html+=`<td class="${nc(v)}">${fmt(v,2)}</td>`;
      }else if(c==='PRECIO_OPE'&&typeof v==='number'){
        html+=`<td>${fmtN(v,6)}</td>`;
      }else{html+=`<td>${String(v).trim()}</td>`;}
    }
    html+='</tr>';
  }
  html+='</tbody></table>';
  wrap.innerHTML=html;
}

function exportarOpsCSV(){
  if(!_ops583Data.length){alert('No hay datos de operaciones cargados.');return;}
  const keys=Object.keys(_ops583Data[0]).filter(k=>k!=='_ROW_ID');
  const csv=[keys.join(','),..._ops583Data.map(r=>keys.map(k=>{const v=r[k];if(v==null)return'';if(typeof v==='string'&&v.includes(','))return`"${v}"`;return v;}).join(','))].join('\n');
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8;'}));
  a.download=`operaciones_583_${document.getElementById('sel-fecha').value}.csv`;a.click();
}

// ── PORTAFOLIOS (mejorado con gráficas) ───────────────────────────────────────
async function cargarPortafolios(){
  const fecha=document.getElementById('sel-fecha').value;
  try{
    const rows=await fetchJSON(`/api/porfin/portafolios/${fecha}`);
    const wrap=document.getElementById('wrap-portafolios');
    if(!rows.length){wrap.innerHTML='<div class="empty">Sin datos</div>';return;}
    const total=rows.reduce((s,r)=>s+(r.valor_mercado||0),0);
    // Gráficas
    const names=(rows.map(r=>r.PORTAFOLIO||r.portafolio||'—')).reverse();
    const vals=rows.map(r=>r.valor_mercado||0).reverse();
    Plotly.newPlot('chart-port-bar',[{
      type:'bar',orientation:'h',x:vals,y:names,
      marker:{color:vals.map(v=>v<0?'#f85149':'#1f6feb')},
      text:vals.map(v=>fmt(v)),textposition:'outside',
    }],{...PL,margin:{t:5,b:20,l:70,r:80},xaxis:{...PL.xaxis,tickformat:',.2s'}},{responsive:true,displayModeBar:false});
    const posNames=rows.map(r=>r.PORTAFOLIO||r.portafolio||'—');
    const posVals=rows.map(r=>r.posiciones||0);
    const colors=['#1f6feb','#3fb950','#e3b341','#f85149','#bc8cff','#58a6ff','#f0883e','#8b949e','#39d353','#f78166','#d2a8ff','#ffa657'];
    Plotly.newPlot('chart-port-pie',[{
      type:'pie',labels:posNames,values:rows.map(r=>Math.abs(r.valor_mercado||0)),
      hole:.35,textinfo:'label+percent',marker:{colors},
      hovertemplate:'<b>%{label}</b><br>%{percent}<br>Valor: %{value:,.0f}<extra></extra>',
    }],{...PL,margin:{t:5,b:5,l:5,r:5}},{responsive:true,displayModeBar:false});
    // Tabla
    let html='<table><thead><tr><th>Portafolio</th><th>Posiciones</th><th>Valor Mercado</th><th>%</th><th>Barra</th></tr></thead><tbody>';
    const maxV=Math.max(...rows.map(r=>Math.abs(r.valor_mercado||0)));
    for(const r of rows){
      const portKey=r.PORTAFOLIO||r.portafolio||'—';
      const pct=total?((r.valor_mercado/total)*100):0;
      const barW=maxV?(Math.abs(r.valor_mercado)/maxV*100).toFixed(1):0;
      html+=`<tr>
        <td><strong>${portKey}</strong></td>
        <td>${(r.posiciones||0).toLocaleString()}</td>
        <td class="${nc(r.valor_mercado)}">${fmt(r.valor_mercado,2)}</td>
        <td style="color:var(--muted)">${pct.toFixed(1)}%</td>
        <td style="min-width:120px;"><div style="background:var(--border2);border-radius:2px;height:6px;"><div style="width:${barW}%;height:100%;background:${r.valor_mercado<0?'var(--red2)':'var(--blue2)'};border-radius:2px;"></div></div></td>
      </tr>`;
    }
    html+=`<tr style="font-weight:700;border-top:2px solid var(--border2);background:var(--surface2);">
      <td>TOTAL (${rows.length})</td><td>${rows.reduce((s,r)=>s+(r.posiciones||0),0).toLocaleString()}</td>
      <td class="${nc(total)}">${fmt(total,2)}</td><td>100%</td><td></td></tr>`;
    html+='</tbody></table>';
    wrap.innerHTML=html;
  }catch(e){document.getElementById('wrap-portafolios').innerHTML=`<div class="empty">Error: ${e.message}</div>`;}
}

async function cargarMonedasTab(){
  const fecha=document.getElementById('sel-fecha').value;
  try{
    const rows=await fetchJSON(`/api/porfin/monedas/${fecha}`);
    const wrap=document.getElementById('wrap-monedas-596');
    if(!rows.length){wrap.innerHTML='<div class="empty">Sin datos</div>';return;}
    const names=rows.map(r=>r.MONEDA||'—');
    const vals=rows.map(r=>r.valor_mercado||0);
    const posArr=rows.map(r=>r.posiciones||0);
    const colors=['#1f6feb','#3fb950','#e3b341','#f85149','#bc8cff','#58a6ff','#f0883e','#8b949e'];
    Plotly.newPlot('chart-mon-bar',[{
      type:'bar',x:names,y:vals,
      marker:{color:colors},
      text:vals.map(v=>fmt(v)),textposition:'outside',
    }],{...PL,margin:{t:20,b:30,l:60,r:15},yaxis:{...PL.yaxis,tickformat:',.2s'}},{responsive:true,displayModeBar:false});
    Plotly.newPlot('chart-mon-pos',[{
      type:'bar',x:names,y:posArr,
      marker:{color:colors.map((c,i)=>c)},
      text:posArr.map(v=>v.toLocaleString()),textposition:'outside',
    }],{...PL,margin:{t:20,b:30,l:45,r:15}},{responsive:true,displayModeBar:false});
    const total=rows.reduce((s,r)=>s+(r.valor_mercado||0),0);
    let html='<table><thead><tr><th>Moneda</th><th>Posiciones</th><th>Valor Mercado COP</th><th>%</th></tr></thead><tbody>';
    for(const r of rows){
      const pct=total?((r.valor_mercado/total)*100).toFixed(1):'—';
      html+=`<tr><td><strong>${r.MONEDA||'—'}</strong></td><td>${(r.posiciones||0).toLocaleString()}</td><td class="${nc(r.valor_mercado)}">${fmt(r.valor_mercado,2)}</td><td style="color:var(--muted)">${pct}%</td></tr>`;
    }
    html+='</tbody></table>';
    wrap.innerHTML=html;
  }catch(e){}
}

// ── TAB ANÁLISIS ──────────────────────────────────────────────────────────────
function renderAnalisis(){
  const rows=_posData;
  if(!rows||!rows.length){
    ['chart-scatter-ptir','chart-hist-vlr','chart-clase','chart-vlr-vs-nom','chart-vcto-dist','chart-concentracion','chart-tir-box']
      .forEach(id=>{const el=document.getElementById(id);if(el)el.innerHTML='<div class="empty">Carga datos primero</div>';});
    return;
  }
  const PL2=_PL();

  // Scatter precio vs TIR
  const withPT=rows.filter(r=>r.PRECIO!=null&&r.TIR!=null);
  if(withPT.length){
    const byPort={};
    withPT.forEach(r=>{const p=r.PORTAFOLIO||'Otros';if(!byPort[p])byPort[p]={x:[],y:[],text:[]};byPort[p].x.push(r.PRECIO);byPort[p].y.push(r.TIR);byPort[p].text.push(r.ISIN||r.ESPECIE||'');});
    const colors=['#1f6feb','#3fb950','#e3b341','#f85149','#bc8cff','#58a6ff','#f0883e','#8b949e'];
    const traces=Object.entries(byPort).slice(0,8).map(([name,d],i)=>({
      type:'scatter',mode:'markers',name,x:d.x,y:d.y,text:d.text,
      marker:{color:colors[i%colors.length],size:5,opacity:.75},
      hovertemplate:'<b>%{text}</b><br>Precio: %{x:.4f}<br>TIR: %{y:.4f}<extra></extra>',
    }));
    Plotly.newPlot('chart-scatter-ptir',traces,{...PL2,showlegend:true,legend:{font:{size:8}},margin:{t:5,b:35,l:50,r:10},xaxis:{...PL2.xaxis,title:{text:'Precio',font:{size:9}}},yaxis:{...PL2.yaxis,title:{text:'TIR',font:{size:9}}}},{responsive:true,displayModeBar:false});
  }

  // Histograma valor mercado
  const vals=rows.filter(r=>r.VLR_MERCADO!=null&&r.VLR_MERCADO>0).map(r=>r.VLR_MERCADO);
  if(vals.length){
    Plotly.newPlot('chart-hist-vlr',[{type:'histogram',x:vals,nbinsx:30,marker:{color:'#1f6feb',opacity:.8},hovertemplate:'%{x:,.0f}<br>%{y} posiciones<extra></extra>'}],
      {...PL2,margin:{t:5,b:35,l:55,r:10},xaxis:{...PL2.xaxis,tickformat:',.2s'},yaxis:{...PL2.yaxis,title:{text:'Posiciones',font:{size:9}}}},{responsive:true,displayModeBar:false});
  }

  // Por clase
  const clases={};
  rows.forEach(r=>{const c=String(r.CLASE||'Sin clase').trim();clases[c]=(clases[c]||0)+1;});
  if(Object.keys(clases).length){
    Plotly.newPlot('chart-clase',[{type:'pie',labels:Object.keys(clases),values:Object.values(clases),hole:.4,
      marker:{colors:['#1f6feb','#3fb950','#e3b341','#f85149','#bc8cff']},textinfo:'label+percent'}],
      {...PL2,margin:{t:5,b:5,l:5,r:5}},{responsive:true,displayModeBar:false});
  }

  // Vlr mercado vs nominal (top 30 por VLR_MERCADO)
  const top30=rows.filter(r=>r.VLR_MERCADO!=null&&r.NOMINAL!=null).sort((a,b)=>Math.abs(b.VLR_MERCADO)-Math.abs(a.VLR_MERCADO)).slice(0,30);
  if(top30.length){
    const labels=top30.map(r=>(r.ISIN||r.ESPECIE||'?').slice(0,10));
    Plotly.newPlot('chart-vlr-vs-nom',[
      {type:'bar',name:'Vlr Mercado',x:labels,y:top30.map(r=>r.VLR_MERCADO),marker:{color:'#1f6feb'}},
      {type:'bar',name:'Nominal',x:labels,y:top30.map(r=>r.NOMINAL),marker:{color:'#3fb950',opacity:.7}},
    ],{...PL2,barmode:'group',margin:{t:5,b:50,l:60,r:10},xaxis:{...PL2.xaxis,tickangle:-45,tickfont:{size:7}},yaxis:{...PL2.yaxis,tickformat:',.2s'}},{responsive:true,displayModeBar:false});
  }

  // Distribución por vencimiento (año)
  const vctoMap={};
  rows.forEach(r=>{
    const v=String(r.VCTO||'').trim();
    let yr='Sin vcto';
    const m=v.match(/(\d{4})/);if(m)yr=m[1];
    vctoMap[yr]=(vctoMap[yr]||0)+(r.VLR_MERCADO||0);
  });
  const vctoSorted=Object.entries(vctoMap).sort((a,b)=>a[0].localeCompare(b[0]));
  if(vctoSorted.length){
    Plotly.newPlot('chart-vcto-dist',[{
      type:'bar',x:vctoSorted.map(e=>e[0]),y:vctoSorted.map(e=>e[1]),
      marker:{color:'#bc8cff'},hovertemplate:'%{x}<br>%{y:,.0f}<extra></extra>',
    }],{...PL2,margin:{t:5,b:35,l:60,r:10},xaxis:{...PL2.xaxis,tickangle:-45},yaxis:{...PL2.yaxis,tickformat:',.2s'}},{responsive:true,displayModeBar:false});
  }

  // Concentración top-10 (% del total)
  const withVal=rows.filter(r=>r.VLR_MERCADO>0).sort((a,b)=>b.VLR_MERCADO-a.VLR_MERCADO);
  const totalVlr=withVal.reduce((s,r)=>s+r.VLR_MERCADO,0);
  const top10=withVal.slice(0,10);
  const top10Pct=top10.reduce((s,r)=>s+r.VLR_MERCADO,0)/totalVlr*100;
  const rest=100-top10Pct;
  Plotly.newPlot('chart-concentracion',[{
    type:'pie',labels:[...top10.map(r=>(r.ISIN||r.ESPECIE||'?').slice(0,12)),'Resto'],
    values:[...top10.map(r=>r.VLR_MERCADO),withVal.slice(10).reduce((s,r)=>s+r.VLR_MERCADO,0)],
    hole:.45,textinfo:'label+percent',
    marker:{colors:['#f85149','#f0883e','#e3b341','#3fb950','#58a6ff','#1f6feb','#bc8cff','#8b949e','#39d353','#f78166','#cccccc']},
  }],{...PL2,margin:{t:5,b:5,l:5,r:5}},{responsive:true,displayModeBar:false});

  // Box TIR por portafolio (top 6)
  const ports=[...new Set(rows.filter(r=>r.TIR!=null).map(r=>r.PORTAFOLIO||'—'))].slice(0,6);
  if(ports.length){
    const boxTraces=ports.map((p,i)=>{
      const tirs=rows.filter(r=>(r.PORTAFOLIO||'—')===p&&r.TIR!=null).map(r=>r.TIR);
      return{type:'box',name:p,y:tirs,marker:{color:['#1f6feb','#3fb950','#e3b341','#f85149','#bc8cff','#58a6ff'][i%6]},boxmean:true};
    });
    Plotly.newPlot('chart-tir-box',boxTraces,{...PL2,margin:{t:5,b:45,l:45,r:10},xaxis:{...PL2.xaxis,tickangle:-30,tickfont:{size:7}},showlegend:false},{responsive:true,displayModeBar:false});
  }
}

// ── TAB VARIACIONES ───────────────────────────────────────────────────────────
let _variacionesData=[];

function poblarSelectsVariaciones(fechas){
  const fi=document.getElementById('var-fecha-i');
  const ff=document.getElementById('var-fecha-f');
  if(!fi||!ff||!fechas.length)return;
  const opts=fechas.map(f=>`<option value="${f}">${f.slice(0,4)}-${f.slice(4,6)}-${f.slice(6)}</option>`).join('');
  fi.innerHTML=opts;
  ff.innerHTML=opts;
  if(fechas.length>1){fi.value=fechas[fechas.length-2];ff.value=fechas[fechas.length-1];}
  else{fi.value=fechas[0];ff.value=fechas[0];}
}

async function cargarVariaciones(){
  const fi=document.getElementById('var-fecha-i').value;
  const ff=document.getElementById('var-fecha-f').value;
  const umbral=parseFloat(document.getElementById('var-umbral').value)||5;
  if(!fi||!ff){alert('Selecciona las dos fechas.');return;}
  const wrap=document.getElementById('wrap-variaciones');
  wrap.innerHTML='<div class="empty"><span class="spinner"></span> Calculando variaciones…</div>';
  try{
    _variacionesData=await fetchJSON(`/api/porfin/variaciones/${fi}/${ff}?umbral=${umbral}`);
    // KPIs
    const total=_variacionesData.length;
    const anorm=_variacionesData.filter(r=>r.ANORMAL).length;
    const sumA=_variacionesData.filter(r=>r.ANORMAL).reduce((s,r)=>s+Math.abs(r.VAR_ABS||0),0);
    document.getElementById('kpi-variaciones-row').innerHTML=[
      ['Total posiciones',fmt(total),'c-blue'],
      ['Variaciones anormales',fmt(anorm),'c-err'],
      ['% anormales',total?(anorm/total*100).toFixed(1)+'%':'—','c-warn'],
      ['Σ Var. abs. anormales',fmt(sumA),'c-purple'],
    ].map(([l,v,c])=>`<div class="kpi-pill"><div class="kpi-pill-val ${c}">${v}</div><div class="kpi-pill-info"><div class="kpi-pill-label">${l}</div></div></div>`).join('');

    // Gráfica barras: top 15 var abs
    const top15abs=[..._variacionesData].sort((a,b)=>Math.abs(b.VAR_ABS||0)-Math.abs(a.VAR_ABS||0)).slice(0,15);
    const labsAbs=top15abs.map(r=>(r.ISIN||r.ESPECIE||'?').slice(0,12)).reverse();
    const valsAbs=top15abs.map(r=>r.VAR_ABS||0).reverse();
    Plotly.newPlot('chart-var-abs',[{
      type:'bar',orientation:'h',x:valsAbs,y:labsAbs,
      marker:{color:valsAbs.map(v=>v<0?'#f85149':'#3fb950')},
      hovertemplate:'%{y}<br>%{x:,.0f}<extra></extra>',
    }],{...PL,margin:{t:5,b:20,l:80,r:20},xaxis:{...PL.xaxis,tickformat:',.2s'}},{responsive:true,displayModeBar:false});

    // Gráfica barras: top 15 var pct
    const top15pct=[..._variacionesData].sort((a,b)=>Math.abs(b.VAR_PCT||0)-Math.abs(a.VAR_PCT||0)).slice(0,15);
    const labsPct=top15pct.map(r=>(r.ISIN||r.ESPECIE||'?').slice(0,12)).reverse();
    const valsPct=top15pct.map(r=>r.VAR_PCT||0).reverse();
    const anormPct=top15pct.map(r=>r.ANORMAL).reverse();
    Plotly.newPlot('chart-var-pct',[{
      type:'bar',orientation:'h',x:valsPct,y:labsPct,
      marker:{color:valsPct.map((v,i)=>anormPct[i]?'#f85149':v<0?'#f0883e':'#3fb950')},
      hovertemplate:'%{y}<br>%{x:.2f}%<extra></extra>',
    }],{...PL,margin:{t:5,b:20,l:80,r:20}},{responsive:true,displayModeBar:false});

    // Histograma de variaciones %
    const allPct=_variacionesData.filter(r=>r.VAR_PCT!=null).map(r=>r.VAR_PCT);
    if(allPct.length){
      Plotly.newPlot('chart-var-hist',[{
        type:'histogram',x:allPct,nbinsx:40,
        marker:{color:'#58a6ff',opacity:.8},
        hovertemplate:'%{x:.1f}%<br>%{y} posiciones<extra></extra>',
      }],{...PL,margin:{t:5,b:35,l:45,r:10},xaxis:{...PL.xaxis,title:{text:'Variación %',font:{size:9}}},yaxis:{...PL.yaxis,title:{text:'Posiciones',font:{size:9}}}},{responsive:true,displayModeBar:false});
    }

    renderVariaciones();
  }catch(e){wrap.innerHTML=`<div class="empty">Error: ${e.message}</div>`;}
}

function renderVariaciones(){
  if(!_variacionesData.length)return;
  const soloAn=document.getElementById('var-solo-anormal').checked;
  const busq=(document.getElementById('var-busq').value||'').toUpperCase();
  let rows=[..._variacionesData];
  if(soloAn)rows=rows.filter(r=>r.ANORMAL);
  if(busq)rows=rows.filter(r=>((r.ISIN||'')+(r.ESPECIE||'')).toUpperCase().includes(busq));
  document.getElementById('count-variaciones').textContent=`${rows.length} registros`;
  const wrap=document.getElementById('wrap-variaciones');
  if(!rows.length){wrap.innerHTML='<div class="empty">Sin registros para los filtros</div>';return;}
  const cols=['ISIN','ESPECIE','VAL_I','VAL_F','VAR_ABS','VAR_PCT','ANORMAL'];
  const avail=cols.filter(c=>rows[0].hasOwnProperty(c));
  let html=`<table><thead><tr>${avail.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>`;
  for(const r of rows){
    const isA=r.ANORMAL;
    html+=`<tr class="${isA?'alert-row':''}">`;
    for(const c of avail){
      const v=r[c];
      if(c==='ANORMAL'){html+=`<td>${v?'<span style="color:var(--red2);font-weight:700">⚠</span>':'<span style="color:var(--green2)">✓</span>'}</td>`;}
      else if(c==='VAR_PCT'){const cl=Math.abs(v||0)>10?'c-err':Math.abs(v||0)>5?'c-warn':'';html+=`<td class="${cl}">${v!=null?v.toFixed(4)+'%':'—'}</td>`;}
      else if(['VAL_I','VAL_F','VAR_ABS'].includes(c)){html+=`<td class="${nc(v)}">${fmt(v,2)}</td>`;}
      else{html+=`<td>${String(v||'').trim()}</td>`;}
    }
    html+='</tr>';
  }
  html+='</tbody></table>';
  wrap.innerHTML=html;
}

function exportarVariacionesCSV(){
  if(!_variacionesData.length){alert('Primero calcula las variaciones.');return;}
  const keys=Object.keys(_variacionesData[0]);
  const csv=[keys.join(','),..._variacionesData.map(r=>keys.map(k=>{const v=r[k];if(v==null)return'';if(typeof v==='string'&&v.includes(','))return`"${v}"`;return v;}).join(','))].join('\n');
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8;'}));
  a.download=`variaciones_${document.getElementById('var-fecha-i').value}_${document.getElementById('var-fecha-f').value}.csv`;
  a.click();
}

// ── ANÁLISIS: hook en showTab ─────────────────────────────────────────────────
// (el renderizado se hace en showTab)

// ── VERIFICACIÓN: gráficas post-cálculo ──────────────────────────────────────
function _renderVerifCharts(){
  if(!_verifData.length)return;
  document.getElementById('charts-verif-row').style.display='';
  const PL2=_PL();
  // Histograma de diferencias %
  const dPcts=_verifData.filter(r=>r.DIF_PCT!=null).map(r=>r.DIF_PCT);
  if(dPcts.length){
    Plotly.newPlot('chart-verif-hist',[{type:'histogram',x:dPcts,nbinsx:30,marker:{color:'#f0883e',opacity:.8},hovertemplate:'%{x:.2f}%<br>%{y}<extra></extra>'}],
      {...PL2,margin:{t:5,b:35,l:40,r:10},xaxis:{...PL2.xaxis,title:{text:'Dif %',font:{size:9}}}},{responsive:true,displayModeBar:false});
  }
  // Scatter porfin vs manual (solo alertas)
  const alertas=_verifData.filter(r=>r.ALERTA&&r.VALORACION_PORFIN!=null&&r.VALORACION_MANUAL!=null);
  if(alertas.length){
    Plotly.newPlot('chart-verif-scatter',[
      {type:'scatter',mode:'markers',name:'Alertas',x:alertas.map(r=>r.VALORACION_MANUAL),y:alertas.map(r=>r.VALORACION_PORFIN),
        text:alertas.map(r=>r.ISIN||r.ESPECIE||''),marker:{color:'#f85149',size:6},
        hovertemplate:'<b>%{text}</b><br>Manual: %{x:,.0f}<br>Porfin: %{y:,.0f}<extra></extra>'},
      {type:'scatter',mode:'lines',name:'Línea 45°',x:[Math.min(...alertas.map(r=>r.VALORACION_MANUAL)),Math.max(...alertas.map(r=>r.VALORACION_MANUAL))],
        y:[Math.min(...alertas.map(r=>r.VALORACION_MANUAL)),Math.max(...alertas.map(r=>r.VALORACION_MANUAL))],
        line:{color:'#3fb950',dash:'dash',width:1},showlegend:false},
    ],{...PL2,margin:{t:5,b:35,l:55,r:10},xaxis:{...PL2.xaxis,tickformat:',.2s',title:{text:'Manual',font:{size:9}}},yaxis:{...PL2.yaxis,tickformat:',.2s',title:{text:'Porfin',font:{size:9}}}},{responsive:true,displayModeBar:false});
  }
  // Alertas por tipo activo
  const tipoMap={};
  _verifData.filter(r=>r.ALERTA).forEach(r=>{const t=r.TIPO||'Sin tipo';tipoMap[t]=(tipoMap[t]||0)+1;});
  if(Object.keys(tipoMap).length){
    Plotly.newPlot('chart-verif-tipo',[{type:'bar',x:Object.keys(tipoMap),y:Object.values(tipoMap),marker:{color:'#f85149'}}],
      {...PL2,margin:{t:5,b:50,l:35,r:10},xaxis:{...PL2.xaxis,tickangle:-30,tickfont:{size:8}}},{responsive:true,displayModeBar:false});
  }
}

// ── ERRORES: gráficas ─────────────────────────────────────────────────────────
function _renderErrorCharts(){
  if(!_erroresData)return;
  const PL2=_PL();
  const rs=_erroresData.resumen_severidad||{};
  const rt=_erroresData.resumen_tipo||{};
  const errores=_erroresData.errores||[];
  // Por severidad
  if(Object.keys(rs).length){
    Plotly.newPlot('chart-err-sev',[{
      type:'pie',labels:Object.keys(rs),values:Object.values(rs),hole:.4,
      marker:{colors:['#f85149','#e3b341','#3fb950']},textinfo:'label+value',
    }],{...PL2,margin:{t:5,b:5,l:5,r:5}},{responsive:true,displayModeBar:false});
  }
  // Por tipo
  if(Object.keys(rt).length){
    Plotly.newPlot('chart-err-tipo',[{type:'bar',x:Object.keys(rt),y:Object.values(rt),marker:{color:'#f0883e'}}],
      {...PL2,margin:{t:5,b:40,l:35,r:10},xaxis:{...PL2.xaxis,tickangle:-20,tickfont:{size:8}}},{responsive:true,displayModeBar:false});
  }
  // Por portafolio
  const portMap={};
  errores.forEach(e=>{const p=e.portafolio||'Sin portafolio';portMap[p]=(portMap[p]||0)+1;});
  const portSorted=Object.entries(portMap).sort((a,b)=>b[1]-a[1]).slice(0,10);
  if(portSorted.length){
    Plotly.newPlot('chart-err-port',[{type:'bar',x:portSorted.map(e=>e[0]),y:portSorted.map(e=>e[1]),marker:{color:'#e3b341'}}],
      {...PL2,margin:{t:5,b:50,l:35,r:10},xaxis:{...PL2.xaxis,tickangle:-30,tickfont:{size:8}}},{responsive:true,displayModeBar:false});
  }
}

// ── OPERACIONES 583: gráficas ─────────────────────────────────────────────────
function _renderOpsCharts(){
  if(!_ops583Raw)return;
  document.getElementById('charts-ops-row').style.display='';
  const PL2=_PL();
  const tipos=_ops583Raw.tipos_transaccion||{};
  // Por tipo (conteo)
  Plotly.newPlot('chart-ops-tipo',[{type:'bar',x:Object.keys(tipos),y:Object.values(tipos),
    marker:{color:Object.keys(tipos).map(t=>t.includes('COBRO')?'#3fb950':t.includes('RETIRO')?'#f85149':t.includes('COMPRA')?'#1f6feb':'#e3b341')},
  }],{...PL2,margin:{t:5,b:55,l:35,r:10},xaxis:{...PL2.xaxis,tickangle:-30,tickfont:{size:8}}},{responsive:true,displayModeBar:false});
  // Por tipo (valor)
  const rows=_ops583Data;
  const valMap={};
  rows.forEach(r=>{const t=r.TRANSACCION||'?';valMap[t]=(valMap[t]||0)+(r.VR_RECIBIDO||0);});
  Plotly.newPlot('chart-ops-valor',[{type:'bar',x:Object.keys(valMap),y:Object.values(valMap),
    marker:{color:Object.keys(valMap).map(t=>valMap[t]>=0?'#3fb950':'#f85149')},
    hovertemplate:'%{x}<br>%{y:,.0f}<extra></extra>',
  }],{...PL2,margin:{t:5,b:55,l:55,r:10},xaxis:{...PL2.xaxis,tickangle:-30,tickfont:{size:8}},yaxis:{...PL2.yaxis,tickformat:',.2s'}},{responsive:true,displayModeBar:false});
}

// ── FONDOS: gráfica Caus Mer vs TIR ──────────────────────────────────────────
function _renderFondoCausChart(){
  if(!_fondosData)return;
  const fondos=(_fondosData.fondos||[]).slice(0,12);
  if(!fondos.length)return;
  const names=fondos.map(f=>f.FONDO).reverse();
  const cm=fondos.map(f=>f.caus_mer||0).reverse();
  const ct=fondos.map(f=>f.caus_tir||0).reverse();
  Plotly.newPlot('chart-caus-mer-tir',[
    {type:'bar',orientation:'h',name:'Caus Mercado',x:cm,y:names,marker:{color:'#3fb950'}},
    {type:'bar',orientation:'h',name:'Caus TIR',x:ct,y:names,marker:{color:'#58a6ff',opacity:.8}},
  ],{...PL,barmode:'group',margin:{t:5,b:20,l:55,r:15},xaxis:{...PL.xaxis,tickformat:',.2s'},legend:{font:{size:8}}},{responsive:true,displayModeBar:false});
}

// ── CONFIG ────────────────────────────────────────────────────────────────────
async function cargarConfig(){
  try{
    const c=await fetchJSON('/api/config');
    document.getElementById('cfg-data-dir').value=c.data_dir||'';
    document.getElementById('cfg-ref-especies').value=c.ref_especies||'';
    document.getElementById('cfg-ref-fcpe').value=c.ref_fcpe||'';
    document.getElementById('cfg-ref-fiduciaria').value=c.ref_fiduciaria||'';
    document.getElementById('cfg-ref-fondos').value=c.ref_fondos||'';
    document.getElementById('cfg-ref-fcp').value=c.ref_fcp||'';
    document.getElementById('cfg-umbral-causacion').value=c.umbral_dif_causacion??1;
    document.getElementById('cfg-umbral-valoracion').value=c.umbral_dif_valoracion??1000;
    document.getElementById('cfg-umbral-valoracion-pct').value=c.umbral_dif_valoracion_pct??1;
    document.getElementById('cfg-host').value=c.host||'0.0.0.0';
    document.getElementById('cfg-port').value=c.port||8002;
  }catch(e){console.warn('Config load error',e);}
}
async function guardarConfig(){
  const msg=document.getElementById('cfg-msg');
  msg.textContent='Guardando...';
  const body={
    data_dir:document.getElementById('cfg-data-dir').value,
    ref_especies:document.getElementById('cfg-ref-especies').value,
    ref_fcpe:document.getElementById('cfg-ref-fcpe').value,
    ref_fiduciaria:document.getElementById('cfg-ref-fiduciaria').value,
    ref_fondos:document.getElementById('cfg-ref-fondos').value,
    ref_fcp:document.getElementById('cfg-ref-fcp').value,
    umbral_dif_causacion:parseFloat(document.getElementById('cfg-umbral-causacion').value)||1,
    umbral_dif_valoracion:parseFloat(document.getElementById('cfg-umbral-valoracion').value)||1000,
    umbral_dif_valoracion_pct:parseFloat(document.getElementById('cfg-umbral-valoracion-pct').value)||1,
    host:document.getElementById('cfg-host').value,
    port:parseInt(document.getElementById('cfg-port').value)||8002,
  };
  try{
    const r=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    msg.style.color=j.ok?'var(--green)':'var(--red)';
    msg.textContent=j.ok?'Guardado correctamente':(j.msg||'Error');
  }catch(e){msg.style.color='var(--red)';msg.textContent='Error: '+e.message;}
  setTimeout(()=>{msg.textContent='';msg.style.color='';},3000);
}

// ── LOGS ──────────────────────────────────────────────────────────────────────
let _logRaw=[],_logTimer=null;
async function cargarLogs(){
  try{
    _logRaw=await fetchJSON('/api/logs?limit=300');
    filtrarLogs();
    document.getElementById('log-count').textContent=_logRaw.length+' entradas';
  }catch(e){document.getElementById('log-wrap').innerHTML='<div class="empty">Error cargando logs</div>';}
}
function filtrarLogs(){
  const level=document.getElementById('log-level').value;
  const rows=level?_logRaw.filter(l=>l.level===level):_logRaw;
  const colors={ERROR:'var(--red)',WARNING:'var(--yellow)',INFO:'var(--muted)',DEBUG:'#555'};
  document.getElementById('log-wrap').innerHTML=rows.slice().reverse().map(l=>
    `<div class="log-entry"><span class="log-ts">${l.ts}</span><span class="log-lv" style="color:${colors[l.level]||'var(--muted)'}">${l.level}</span><span class="log-msg">${escHtml?escHtml(l.msg):esc(l.msg)}</span></div>`
  ).join('');
}
function toggleLogAuto(){
  if(document.getElementById('log-auto').checked){
    _logTimer=setInterval(cargarLogs,5000);
  }else{
    clearInterval(_logTimer);_logTimer=null;
  }
}

// ── INIT ──────────────────────────────────────────────────────────────────────
cargarFechas();
document.getElementById('modal-upload').addEventListener('click',e=>{if(e.target===e.currentTarget)cerrarUpload();});
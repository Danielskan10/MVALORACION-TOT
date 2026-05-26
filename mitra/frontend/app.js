const API='';
function fmt(v,d=4){return v==null?'—':typeof v==='number'?v.toLocaleString('es-CO',{minimumFractionDigits:d,maximumFractionDigits:d}):String(v);}
function fmtCOP(v){return v==null?'—':'$'+fmt(v,0);}
function fmtPct(v){if(v==null)return'—';const c=Math.abs(v)>5?'err':Math.abs(v)>2?'warn':'ok';return`<span class="${c}">${v.toFixed(4)}%</span>`;}
function showTab(id,el){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(t=>t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
  if(id==='tab-config')cargarConfig();
  if(id==='tab-logs')cargarLogs();
}
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

// ── CONFIG ────────────────────────────────────────────────────────────────────
async function cargarConfig(){
  try{
    const c=await fetchJSON('/api/config');
    document.getElementById('cfg-data-dir').value=c.data_dir||'';
    document.getElementById('cfg-umbral-variacion').value=c.umbral_variacion_pct??5;
    document.getElementById('cfg-umbral-causacion').value=c.umbral_dif_causacion??1;
    document.getElementById('cfg-host').value=c.host||'0.0.0.0';
    document.getElementById('cfg-port').value=c.port||8003;
  }catch(e){console.warn('Config load error',e);}
}
async function guardarConfig(){
  const msg=document.getElementById('cfg-msg');
  msg.textContent='Guardando...';
  const body={
    data_dir:document.getElementById('cfg-data-dir').value,
    umbral_variacion_pct:parseFloat(document.getElementById('cfg-umbral-variacion').value)||5,
    umbral_dif_causacion:parseFloat(document.getElementById('cfg-umbral-causacion').value)||1,
    host:document.getElementById('cfg-host').value,
    port:parseInt(document.getElementById('cfg-port').value)||8003,
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
    `<div class="log-entry"><span class="log-ts">${l.ts}</span><span class="log-lv" style="color:${colors[l.level]||'var(--muted)'}">${l.level}</span><span class="log-msg">${esc(l.msg)}</span></div>`
  ).join('');
}
function toggleLogAuto(){
  if(document.getElementById('log-auto').checked){
    _logTimer=setInterval(cargarLogs,5000);
  }else{
    clearInterval(_logTimer);_logTimer=null;
  }
}
async function fetchJSON(url){const r=await fetch(API+url);if(!r.ok)throw new Error(r.statusText);return r.json();}

async function cargarFechas(){
  const sel=document.getElementById('sel-fecha');
  const selAnt=document.getElementById('sel-fecha-ant');
  try{
    const data=await fetchJSON('/api/mitra/fechas');
    const f=(data.fechas||[]).reverse();
    sel.innerHTML=f.map(x=>`<option value="${x}">${x.slice(0,4)}-${x.slice(4,6)}-${x.slice(6)}</option>`).join('');
    selAnt.innerHTML='<option value="">— ninguna —</option>'+f.map(x=>`<option value="${x}">${x.slice(0,4)}-${x.slice(4,6)}-${x.slice(6)}</option>`).join('');
    if(f.length>1)selAnt.value=f[1];
    if(f.length)cargarTodo();
  }catch(e){sel.innerHTML='<option>Error</option>';}
}

async function cargarTodo(){
  const fecha=document.getElementById('sel-fecha').value;
  if(!fecha)return;
  await Promise.all([
    cargarResumen(fecha), cargarPosiciones(), cargarCausaciones(fecha),
    cargarDifPorfin(fecha), cargarVariaciones(), cargarMonedas(fecha)
  ]);
}

async function cargarResumen(fecha){
  try{
    const d=await fetchJSON(`/api/mitra/resumen/${fecha}`);
    if(d.error){return;}
    document.getElementById('kpi-pos').textContent=d.total_posiciones??'—';
    document.getElementById('kpi-val-di').textContent=fmtCOP(d.suma_valoracion_di);
    document.getElementById('kpi-val-df').textContent=fmtCOP(d.suma_valoracion_df);
    document.getElementById('kpi-causac').textContent=fmtCOP(d.suma_causacion);
    const tot=(d.alertas_causacion||0)+(d.alertas_precio||0)+(d.sin_precio||0);
    document.getElementById('kpi-alertas').textContent=tot;
    document.getElementById('kpi-alertas').className='val '+(tot>0?'err':'ok');

    if(d.distribucion_tipo&&Object.keys(d.distribucion_tipo).length){
      const e=Object.entries(d.distribucion_tipo).sort((a,b)=>b[1]-a[1]);
      const colors=['#58a6ff','#3fb950','#f0883e','#bc8cff','#e3b341','#f85149'];
      Plotly.newPlot('chart-tipos',[{type:'pie',labels:e.map(x=>x[0]),values:e.map(x=>x[1]),
        marker:{colors},textinfo:'label+percent',hole:.35}],
        {paper_bgcolor:'transparent',font:{color:'#e6edf3',size:11},legend:{bgcolor:'transparent'},margin:{t:10,b:10,l:10,r:10}},{responsive:true,displayModeBar:false});
    }
    if(d.fuentes_precio&&Object.keys(d.fuentes_precio).length){
      const e=Object.entries(d.fuentes_precio).sort((a,b)=>b[1]-a[1]);
      const colors=['#f0883e','#58a6ff','#3fb950','#bc8cff','#e3b341'];
      Plotly.newPlot('chart-fuentes',[{type:'bar',x:e.map(x=>x[0]),y:e.map(x=>x[1]),
        marker:{color:colors},text:e.map(x=>x[1]),textposition:'auto'}],
        {paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#e6edf3',size:11},
         margin:{t:10,b:40,l:40,r:10},xaxis:{gridcolor:'#30363d'},yaxis:{gridcolor:'#30363d'}},{responsive:true,displayModeBar:false});
    }

    // Filtros dinámicos
    const filTipo=document.getElementById('fil-tipo');
    filTipo.innerHTML='<option value="">Todos los tipos</option>'+Object.keys(d.distribucion_tipo||{}).map(t=>`<option>${t}</option>`).join('');
    const filFuente=document.getElementById('fil-fuente');
    filFuente.innerHTML='<option value="">Todas las fuentes</option>'+Object.keys(d.fuentes_precio||{}).map(t=>`<option>${t}</option>`).join('');
  }catch(e){console.error(e);}
}

async function cargarPosiciones(){
  const fecha=document.getElementById('sel-fecha').value;
  const bus=document.getElementById('bus-pos').value;
  const tipo=document.getElementById('fil-tipo').value;
  const fuente=document.getElementById('fil-fuente').value;
  const soloAlertas=document.getElementById('chk-alertas').checked;
  const soloCurva=document.getElementById('chk-curva').checked;
  const wrap=document.getElementById('wrap-posiciones');
  wrap.innerHTML='<div class="empty"><span class="spinner"></span></div>';
  try{
    let url=`/api/mitra/posiciones/${fecha}?solo_alertas=${soloAlertas}&marcado_curva=${soloCurva}`;
    if(bus)url+=`&busqueda=${encodeURIComponent(bus)}`;
    if(tipo)url+=`&tipo=${encodeURIComponent(tipo)}`;
    if(fuente)url+=`&fuente=${encodeURIComponent(fuente)}`;
    const data=await fetchJSON(url);
    if(!data.length){wrap.innerHTML='<div class="empty">Sin posiciones</div>';return;}
    const cols=Object.keys(data[0]);
    let html=`<table><thead><tr>${cols.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>`;
    data.forEach(r=>{
      const alerta=r.OBSERVACION&&r.OBSERVACION!=='OK';
      html+=`<tr style="${alerta?'background:#f8514908;':''}">${cols.map(c=>{
        const v=r[c];
        if(c==='OBSERVACION')return`<td><span class="badge ${v==='OK'?'badge-green':'badge-red'}" style="white-space:normal;max-width:250px;">${v}</span></td>`;
        if(c==='FUENTE')return`<td><span class="badge badge-orange">${v??'—'}</span></td>`;
        if(c==='MARCADO_ACTIVO'){const s=String(v||'').toUpperCase();return`<td><span class="badge ${s.includes('CURVA')||s.includes('TIR')?'badge-yellow':'badge-blue'}">${v??'—'}</span></td>`;}
        if(typeof v==='number')return`<td>${fmt(v,4)}</td>`;
        return`<td>${v??'—'}</td>`;
      }).join('')}</tr>`;
    });
    html+='</tbody></table>';
    wrap.innerHTML=html;
  }catch(e){wrap.innerHTML=`<div class="empty">Error: ${e.message}</div>`;}
}

async function cargarCausaciones(fecha){
  const wrap=document.getElementById('wrap-causaciones');
  wrap.innerHTML='<div class="empty"><span class="spinner"></span></div>';
  try{
    const d=await fetchJSON(`/api/mitra/causaciones/${fecha}`);
    if(d.error){wrap.innerHTML=`<div class="empty">${d.error}</div>`;return;}

    document.getElementById('resumen-causac').innerHTML=`
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin-bottom:1rem;">
        <div style="background:var(--surface2);padding:.75rem 1rem;border-radius:8px;"><div style="color:var(--muted);font-size:.75rem;text-transform:uppercase;">Val. DI Total</div><div style="font-size:1.2rem;font-weight:700;">${fmtCOP(d.suma_valoracion_di)}</div></div>
        <div style="background:var(--surface2);padding:.75rem 1rem;border-radius:8px;"><div style="color:var(--muted);font-size:.75rem;text-transform:uppercase;">Val. DF Total</div><div style="font-size:1.2rem;font-weight:700;">${fmtCOP(d.suma_valoracion_df)}</div></div>
        <div style="background:var(--surface2);padding:.75rem 1rem;border-radius:8px;"><div style="color:var(--muted);font-size:.75rem;text-transform:uppercase;">Causación (DF-DI)</div><div style="font-size:1.2rem;font-weight:700;">${fmtCOP(d.suma_causacion_total)}</div></div>
        <div style="background:var(--surface2);padding:.75rem 1rem;border-radius:8px;"><div style="color:var(--muted);font-size:.75rem;text-transform:uppercase;">Alertas</div><div style="font-size:1.2rem;font-weight:700;color:${d.total_alertas_causacion>0?'var(--red)':'var(--green)'};">${d.total_alertas_causacion}</div></div>
      </div>`;

    if(d.por_tipo&&d.por_tipo.length){
      const tipos=d.por_tipo;
      Plotly.newPlot('chart-causac-tipo',[
        {name:'Val. DI',type:'bar',x:tipos.map(t=>t.TIPO||''),y:tipos.map(t=>t.suma_valoracion_di||0),marker:{color:'#58a6ff'}},
        {name:'Val. DF',type:'bar',x:tipos.map(t=>t.TIPO||''),y:tipos.map(t=>t.suma_valoracion_df||0),marker:{color:'#3fb950'}},
        {name:'Causación',type:'bar',x:tipos.map(t=>t.TIPO||''),y:tipos.map(t=>t.suma_causacion_calc||0),marker:{color:'#f0883e'}},
      ],{barmode:'group',paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#e6edf3',size:10},
         margin:{t:10,b:60,l:60,r:10},xaxis:{tickangle:-30,gridcolor:'#30363d'},yaxis:{gridcolor:'#30363d'},legend:{bgcolor:'transparent'}},{responsive:true,displayModeBar:false});
    }

    const rows=d.alertas.length?d.alertas:d.por_tipo||[];
    if(!rows.length){wrap.innerHTML='<div class="empty">Sin datos</div>';return;}
    const cols=Object.keys(rows[0]);
    let html=`<table><thead><tr>${cols.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>`;
    rows.forEach(r=>{
      html+=`<tr>${cols.map(c=>{const v=r[c];return`<td>${typeof v==='number'?fmt(v,2):v??'—'}</td>`;}).join('')}</tr>`;
    });
    html+='</tbody></table>';
    wrap.innerHTML=html;
  }catch(e){wrap.innerHTML=`<div class="empty">Error: ${e.message}</div>`;}
}

async function cargarDifPorfin(fecha){
  const wrap=document.getElementById('wrap-dif');
  wrap.innerHTML='<div class="empty"><span class="spinner"></span></div>';
  try{
    const d=await fetchJSON(`/api/mitra/diferencias_porfin/${fecha}`);
    if(d.error){wrap.innerHTML=`<div class="empty">${d.error}</div>`;return;}

    document.getElementById('resumen-dif').innerHTML=`
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin-bottom:1rem;">
        <div style="background:var(--surface2);padding:.75rem 1rem;border-radius:8px;"><div style="color:var(--muted);font-size:.75rem;text-transform:uppercase;">Títulos Cruzados</div><div style="font-size:1.2rem;font-weight:700;">${d.total_cruzados}</div></div>
        <div style="background:var(--surface2);padding:.75rem 1rem;border-radius:8px;"><div style="color:var(--muted);font-size:.75rem;text-transform:uppercase;">Causación Mitra</div><div style="font-size:1.2rem;font-weight:700;">${fmtCOP(d.suma_causacion_mitra)}</div></div>
        <div style="background:var(--surface2);padding:.75rem 1rem;border-radius:8px;"><div style="color:var(--muted);font-size:.75rem;text-transform:uppercase;">Causación Porfin</div><div style="font-size:1.2rem;font-weight:700;">${fmtCOP(d.suma_causacion_porfin)}</div></div>
        <div style="background:var(--surface2);padding:.75rem 1rem;border-radius:8px;"><div style="color:var(--muted);font-size:.75rem;text-transform:uppercase;">Diferencia Total</div><div style="font-size:1.2rem;font-weight:700;color:${Math.abs(d.diferencia_total||0)>1000?'var(--red)':'var(--green)'};">${fmtCOP(d.diferencia_total)}</div></div>
      </div>`;

    const rows=(d.detalle||[]).slice(0,15);
    if(rows.length){
      Plotly.newPlot('chart-dif-porfin',[
        {name:'Mitra',type:'bar',x:rows.map(r=>r.ID||''),y:rows.map(r=>r.CAUSACION_MITRA||0),marker:{color:'#58a6ff'}},
        {name:'Porfin',type:'bar',x:rows.map(r=>r.ID||''),y:rows.map(r=>r.CAUSACION_PORFIN||0),marker:{color:'#3fb950'}},
      ],{barmode:'group',paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#e6edf3',size:10},
         margin:{t:10,b:70,l:60,r:10},xaxis:{tickangle:-40,gridcolor:'#30363d'},yaxis:{gridcolor:'#30363d'},legend:{bgcolor:'transparent'}},{responsive:true,displayModeBar:false});
    }

    if(!d.detalle||!d.detalle.length){wrap.innerHTML='<div class="empty">Sin datos de cruce</div>';return;}
    let html=`<table><thead><tr><th>ID</th><th>Causación Mitra</th><th>Causación Porfin</th><th>Diferencia</th><th>Estado</th></tr></thead><tbody>`;
    d.detalle.forEach(r=>{
      const alerta=r.ALERTA;
      html+=`<tr style="${alerta?'background:#f8514908;':''}">
        <td><strong>${r.ID}</strong></td><td>${fmtCOP(r.CAUSACION_MITRA)}</td><td>${fmtCOP(r.CAUSACION_PORFIN)}</td>
        <td style="color:${Math.abs(r.DIF_CAUSACION_PORFIN||0)>1000?'var(--red)':'inherit'}">${fmtCOP(r.DIF_CAUSACION_PORFIN)}</td>
        <td><span class="badge ${alerta?'badge-red':'badge-green'}">${alerta?'⚠ ALERTA':'OK'}</span></td></tr>`;
    });
    html+='</tbody></table>';
    wrap.innerHTML=html;
  }catch(e){wrap.innerHTML=`<div class="empty">Error: ${e.message}</div>`;}
}

async function cargarVariaciones(){
  const fechaFin=document.getElementById('sel-fecha').value;
  const fechaIni=document.getElementById('sel-fecha-ant').value;
  const umbral=document.getElementById('umbral').value;
  const wrap=document.getElementById('wrap-variaciones');
  if(!fechaIni||!fechaFin||fechaIni===fechaFin){wrap.innerHTML='<div class="empty">Selecciona dos fechas distintas</div>';return;}
  wrap.innerHTML='<div class="empty"><span class="spinner"></span></div>';
  try{
    const data=await fetchJSON(`/api/mitra/variaciones/${fechaIni}/${fechaFin}?umbral=${umbral}`);
    if(!data.length){wrap.innerHTML='<div class="empty">Sin variaciones</div>';return;}
    let html=`<table><thead><tr><th>ID</th><th>Precio ${fechaIni}</th><th>Precio ${fechaFin}</th><th>VAR ABS</th><th>VAR %</th><th>Val. DI</th><th>Val. DF</th><th>Estado</th></tr></thead><tbody>`;
    data.forEach(r=>{
      html+=`<tr><td><strong>${r.ID}</strong></td><td>${fmt(r.PRECIO_I,6)}</td><td>${fmt(r.PRECIO_F,6)}</td>
      <td>${fmt(r.VAR_PRECIO_ABS,6)}</td><td>${fmtPct(r.VAR_PRECIO_PCT)}</td>
      <td>${fmtCOP(r.VAL_I)}</td><td>${fmtCOP(r.VAL_F)}</td>
      <td><span class="badge ${r.ANORMAL?'badge-red':'badge-green'}">${r.ANORMAL?'⚠ ANORMAL':'OK'}</span></td></tr>`;
    });
    html+='</tbody></table>';
    wrap.innerHTML=html;
  }catch(e){wrap.innerHTML=`<div class="empty">Error: ${e.message}</div>`;}
}

async function cargarMonedas(fecha){
  const wrap=document.getElementById('wrap-monedas');
  wrap.innerHTML='<div class="empty"><span class="spinner"></span></div>';
  try{
    const data=await fetchJSON(`/api/mitra/monedas/${fecha}`);
    if(!data.length){wrap.innerHTML='<div class="empty">Sin datos de monedas</div>';return;}
    const cols=Object.keys(data[0]);
    let html=`<table><thead><tr>${cols.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>`;
    data.forEach(r=>{
      html+=`<tr>${cols.map(c=>{const v=r[c];return`<td>${typeof v==='number'?fmt(v,6):v??'—'}</td>`;}).join('')}</tr>`;
    });
    html+='</tbody></table>';
    wrap.innerHTML=html;
  }catch(e){wrap.innerHTML=`<div class="empty">No hay archivo de monedas para esta fecha</div>`;}
}

cargarFechas();
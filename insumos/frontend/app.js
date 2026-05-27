/* ═══════════════════════════════════════════════════════════
   INSUMOS app.js v3 — Skandia MVALORACION
   Requiere: /static/nav.js  (toggleTheme, getPL, fmtNum, escHtml, debounce)
═══════════════════════════════════════════════════════════ */
'use strict';

// ── ESTADO GLOBAL ────────────────────────────────────────
const S = {
  fecha:    '',
  fechas:   [],
  umbral:   3,
  alertas:  [],
  spData:   [],
  tabData:  {},
  mdData:   null,
  histPanel:null,
  sortCol:  {},
  sortDir:  {},
  logRaw:   [],
  logTimer: null,
};

// ── UTILS ─────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const J = async url => { const r = await fetch(url); if(!r.ok) throw new Error(r.status); return r.json(); };
const esc = s => String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const fmtP = (n,d=4) => n==null||isNaN(n)?'—':Number(n).toLocaleString('es-CO',{minimumFractionDigits:d,maximumFractionDigits:d});
const fmtPct = (n,d=2) => n==null||isNaN(n)?'—':(n>=0?'+':'')+Number(n).toFixed(d)+'%';
const clsPct = n => n==null?'v0':n>0?'vU':'vD';
const COLORS = ['#00A65A','#0A84FF','#FF9500','#BF5AF2','#FFD60A','#FF3B30','#00C96E','#58a6ff'];

function PL(ov={}) {
  const dark = document.documentElement.getAttribute('data-theme') !== 'light';
  const txt  = dark ? '#8E8E93' : '#6C6C70';
  const grid = dark ? '#252525' : '#E5E5EA';
  return {
    paper_bgcolor:'transparent', plot_bgcolor:'transparent',
    font:{color:txt, size:10, family:'Inter,system-ui,sans-serif'},
    margin:{t:12,b:36,l:52,r:14},
    legend:{bgcolor:'transparent',font:{size:9}},
    xaxis:{gridcolor:grid,zerolinecolor:grid,tickfont:{size:9}},
    yaxis:{gridcolor:grid,zerolinecolor:grid,tickfont:{size:9}},
    colorway:COLORS,
    ...ov
  };
}

// ── TABS ──────────────────────────────────────────────────
function showTab(id, el) {
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
  if (id==='tab-alertas')     renderAlertas();
  if (id==='tab-multidia')    cargarMultidia();
  if (id==='tab-curvas')      cargarCurvas();
  if (id==='tab-sp')          cargarTabla('SP');
  if (id==='tab-sw')          cargarTabla('SW');
  if (id==='tab-sv')          cargarTabla('SV');
  if (id==='tab-mx')          cargarTabla('MX');
  if (id==='tab-notas')       cargarTabla('NOTAS');
  if (id==='tab-config')      cargarConfig();
  if (id==='tab-conversor')   cargarStatusCache();
  if (id==='tab-logs')        cargarLogs();
}

// ── INIT ──────────────────────────────────────────────────
async function cargarFechas() {
  const sel = $('sel-fecha');
  try {
    const d = await J('/api/insumos/fechas');
    S.fechas = (d.fechas||[]).slice().reverse();
    sel.innerHTML = S.fechas.map(f=>`<option value="${f}">${f.slice(0,4)}-${f.slice(4,6)}-${f.slice(6)}</option>`).join('');
    if (S.fechas.length) { S.fecha = S.fechas[0]; cargarTodo(); }
  } catch(e) { sel.innerHTML='<option value="">Sin fechas</option>'; }
}

async function cargarTodo() {
  S.fecha = $('sel-fecha').value;
  S.umbral = parseFloat($('inp-umbral').value)||3;
  if (!S.fecha) return;
  S.tabData = {}; S.alertas = []; S.spData = []; S.mdData = null; _curvaData = null;
  actualizarBadgesFecha();
  // Sincronizar campo conversor con la fecha activa
  const convFecha = $('conv-fecha');
  if (convFecha && !convFecha.value) convFecha.value = S.fecha;
  await Promise.all([cargarResumen(), cargarAlertasDia()]);
}

// ── RESUMEN KPIs ──────────────────────────────────────────
async function cargarResumen() {
  try {
    const data = await J(`/api/insumos/resumen/${S.fecha}`);
    const sp = data.find(d=>d.proveedor==='SP')||{};
    const sw = data.find(d=>d.proveedor==='SW')||{};
    const mx = data.find(d=>d.proveedor==='MX')||{};
    const notas = data.find(d=>d.proveedor==='NOTAS')||{};
    const tot = data.reduce((s,d)=>s+(d.total||0),0);
    const prov = data.filter(d=>d.disponible).length;
    $('kpi-titulos').textContent  = (sp.total||0).toLocaleString('es-CO');
    $('kpi-prov').textContent     = prov+'/'+data.length;
    $('kpi-sp-pm').textContent    = sp.precio_promedio != null ? fmtP(sp.precio_promedio,4) : '—';
    $('kpi-mx').textContent       = (mx.total||0).toLocaleString('es-CO');
    $('kpi-notas').textContent    = (notas.total||0).toLocaleString('es-CO');
    $('kpi-sw').textContent       = (sw.total||0).toLocaleString('es-CO');
  } catch(e) { console.warn('resumen',e); }
}

function actualizarBadgesFecha() {
  const f = S.fecha;
  $('lbl-fecha-activa').textContent = f ? `${f.slice(0,4)}-${f.slice(4,6)}-${f.slice(6)}` : '—';
}

// ── ALERTAS DIA ───────────────────────────────────────────
async function cargarAlertasDia() {
  const wrap = $('wrap-alertas');
  wrap.innerHTML = '<div class="empty"><span class="spinner"></span> Calculando alertas...</div>';
  try {
    const d = await J(`/api/insumos/alertas/${S.fecha}?umbral_pct=${S.umbral}`);
    S.alertas = d.alertas || [];
    $('kpi-alertas').textContent   = S.alertas.length;
    $('kpi-criticas').textContent  = d.criticas||0;
    $('kpi-fecha-ant').textContent = d.fecha_ant ? `${d.fecha_ant.slice(0,4)}-${d.fecha_ant.slice(4,6)}-${d.fecha_ant.slice(6)}` : '—';
    renderBannerAlerta(d);
    renderAlertas();
    renderTopVariaciones();
    renderRallyCards();
    renderHeatmap();
    renderChartAlertas();
  } catch(e) {
    wrap.innerHTML = `<div class="empty">Sin fecha anterior disponible para comparar.</div>`;
    S.alertas = [];
    renderTopVariaciones();
    renderRallyCards();
    renderHeatmap();
  }
}

function renderBannerAlerta(d) {
  const tot = d.total||0;
  const cls = tot === 0 ? 'ab-ok' : d.criticas > 0 ? 'ab-crit' : 'ab-warn';
  const ic  = tot === 0 ? '✓' : d.criticas > 0 ? '⚠' : '↑';
  $('banner-alertas').className = `alert-banner ${cls}`;
  $('banner-alertas').innerHTML = `
    <span class="ab-cnt">${ic}</span>
    <span><strong>${tot} alertas</strong> con variación &gt;${S.umbral}% vs ${d.fecha_ant||'N/A'}</span>
    <span style="margin-left:auto;display:flex;gap:6px;">
      ${d.criticas ? `<span class="sev sC">${d.criticas} CRÍTICAS</span>` : ''}
      ${d.altas    ? `<span class="sev sA">${d.altas} ALTAS</span>` : ''}
      ${d.medias   ? `<span class="sev sM">${d.medias} MEDIAS</span>` : ''}
    </span>`;
}

// ── TABLA ALERTAS ─────────────────────────────────────────
let _alertSort = {col:'VAR_PCT', dir:-1};

function renderAlertas() {
  const busq  = ($('fil-busq-alertas')||{}).value||'';
  const fuente= ($('fil-fuente-alertas')||{}).value||'';
  const sev   = ($('fil-sev-alertas')||{}).value||'';
  let rows = [...S.alertas];
  if (busq)   rows = rows.filter(r=>esc(r.ISIN).toUpperCase().includes(busq.toUpperCase()));
  if (fuente) rows = rows.filter(r=>r.FUENTE===fuente);
  if (sev)    rows = rows.filter(r=>r.SEVERIDAD===sev);

  rows.sort((a,b) => _alertSort.dir * (Math.abs(b[_alertSort.col]||0) - Math.abs(a[_alertSort.col]||0)));

  $('cnt-alertas').textContent = rows.length;
  const wrap = $('wrap-alertas');
  if (!rows.length) { wrap.innerHTML='<div class="empty">Sin alertas para el filtro seleccionado.</div>'; return; }

  wrap.innerHTML = `<table>
    <thead><tr>
      <th onclick="sortAlertas('SEVERIDAD')">SEV</th>
      <th onclick="sortAlertas('ISIN')">ISIN / ID</th>
      <th onclick="sortAlertas('FUENTE')">Fuente</th>
      <th onclick="sortAlertas('PRECIO_HOY')">Precio hoy</th>
      <th onclick="sortAlertas('PRECIO_ANT')">Precio ant.</th>
      <th onclick="sortAlertas('VAR_PCT')" class="${_alertSort.col==='VAR_PCT'?(_alertSort.dir>0?'asc':'desc'):''}">Var %</th>
    </tr></thead>
    <tbody>${rows.map(r=>`
      <tr class="${r.SEVERIDAD==='CRITICA'?'rc':r.SEVERIDAD==='ALTA'?'ra':''}" onclick="abrirHistorial('${esc(r.ISIN)}','${r.FUENTE}')">
        <td><span class="sev ${r.SEVERIDAD==='CRITICA'?'sC':r.SEVERIDAD==='ALTA'?'sA':r.SEVERIDAD==='MEDIA'?'sM':'sB'}">${r.SEVERIDAD}</span></td>
        <td><strong>${esc(r.ISIN)}</strong></td>
        <td><span style="font-size:.6rem;background:var(--surf2);padding:.08rem .3rem;border-radius:3px;">${esc(r.FUENTE)}</span></td>
        <td>${fmtP(r.PRECIO_HOY,6)}</td>
        <td>${fmtP(r.PRECIO_ANT,6)}</td>
        <td><span class="vp ${clsPct(r.VAR_PCT)}">${fmtPct(r.VAR_PCT)}</span></td>
      </tr>`).join('')}
    </tbody></table>`;
}

function sortAlertas(col) {
  _alertSort.dir = _alertSort.col===col ? -_alertSort.dir : -1;
  _alertSort.col = col;
  renderAlertas();
}

// ── TOP VARIACIONES ───────────────────────────────────────
function renderTopVariaciones() {
  const sube = [...S.alertas].sort((a,b)=>b.VAR_PCT-a.VAR_PCT).slice(0,8);
  const baja = [...S.alertas].sort((a,b)=>a.VAR_PCT-b.VAR_PCT).slice(0,8);

  function filas(arr, cls) {
    if (!arr.length) return '<div class="empty" style="padding:1rem;">Sin datos</div>';
    return arr.map((r,i)=>`
      <div class="top-row" onclick="abrirHistorial('${esc(r.ISIN)}','${r.FUENTE}')">
        <span class="top-rank">${i+1}</span>
        <span class="top-id">${esc(r.ISIN)}</span>
        <span class="top-src">${esc(r.FUENTE)}</span>
        <span class="vp ${cls}">${fmtPct(r.VAR_PCT)}</span>
      </div>`).join('');
  }

  $('top-sube').innerHTML = filas(sube,'vU');
  $('top-baja').innerHTML = filas(baja,'vD');
}

// ── RALLY CARDS ───────────────────────────────────────────
function renderRallyCards() {
  const top = [...S.alertas]
    .sort((a,b)=>Math.abs(b.VAR_PCT)-Math.abs(a.VAR_PCT))
    .slice(0,10);
  const wrap = $('rally-wrap');
  if (!top.length) { wrap.innerHTML='<div class="empty">Sin alertas</div>'; return; }

  const fuentes = ['SP','SW','SV','MX','NOTAS','TP'];
  const srcColor = {SP:'#0A84FF',SW:'#BF5AF2',SV:'#FF9500',MX:'#00A65A',NOTAS:'#FFD60A',TP:'#FF3B30'};

  wrap.innerHTML = top.map(r => {
    const up = r.VAR_PCT > 0;
    const col = srcColor[r.FUENTE]||'#8E8E93';
    return `<div class="rally-card" style="--rc:${col};" onclick="abrirHistorial('${esc(r.ISIN)}','${r.FUENTE}')">
      <div class="rc-src">${esc(r.FUENTE)}</div>
      <div class="rc-id">${esc(r.ISIN)}</div>
      <div class="rc-pct ${up?'rc-up':'rc-dn'}">${fmtPct(r.VAR_PCT)}</div>
      <div class="rc-det">${fmtP(r.PRECIO_ANT,4)} → ${fmtP(r.PRECIO_HOY,4)}</div>
    </div>`;
  }).join('');
}

// ── HEATMAP ───────────────────────────────────────────────
function renderHeatmap() {
  const wrap = $('heatmap-wrap');
  // Usar todos los que tengan variación (no solo alertas)
  const rows = [...S.alertas].sort((a,b)=>Math.abs(b.VAR_PCT)-Math.abs(a.VAR_PCT)).slice(0,60);
  if (!rows.length) { wrap.innerHTML='<div class="empty">Sin variaciones</div>'; return; }

  const maxAbs = Math.max(...rows.map(r=>Math.abs(r.VAR_PCT)),0.01);
  wrap.innerHTML = rows.map(r=>{
    const pct = r.VAR_PCT;
    const intensity = Math.min(Math.abs(pct)/maxAbs,1);
    const up = pct>0;
    const base = up ? [255,59,48] : [0,166,90];
    const alpha = 0.25 + intensity*0.7;
    const bg = `rgba(${base[0]},${base[1]},${base[2]},${alpha.toFixed(2)})`;
    const id = esc(r.ISIN).slice(0,8);
    return `<div class="hm-cell" style="background:${bg};" title="${esc(r.ISIN)} ${fmtPct(pct)}" onclick="abrirHistorial('${esc(r.ISIN)}','${r.FUENTE}')">
      <div class="hm-id">${id}</div>
      <div class="hm-pct">${fmtPct(pct,1)}</div>
    </div>`;
  }).join('');
}

// ── GRÁFICAS PANEL ALERTAS ────────────────────────────────
function renderChartAlertas() {
  if (!S.alertas.length) return;
  // Distribución por fuente
  const fuenteMap = {};
  S.alertas.forEach(a=>{ fuenteMap[a.FUENTE]=(fuenteMap[a.FUENTE]||0)+1; });
  Plotly.newPlot('chart-por-fuente',[{
    type:'bar', x:Object.keys(fuenteMap), y:Object.values(fuenteMap),
    marker:{color:COLORS},
    text:Object.values(fuenteMap), textposition:'auto',
  }],{...PL(), margin:{t:8,b:32,l:32,r:8}, showlegend:false},{responsive:true,displayModeBar:false});

  // Histograma de variaciones
  const pcts = S.alertas.map(a=>a.VAR_PCT).filter(v=>v!=null);
  Plotly.newPlot('chart-hist-var',[{
    type:'histogram', x:pcts, nbinsx:20,
    marker:{color:pcts.map(v=>v>0?'rgba(255,59,48,.7)':'rgba(0,166,90,.7)')},
  }],{...PL(), barmode:'overlay', margin:{t:8,b:36,l:42,r:8}, showlegend:false, xaxis:{...PL().xaxis,title:{text:'Var %',font:{size:9}}},},{responsive:true,displayModeBar:false});

  // Scatter precio_ant vs precio_hoy
  const xs = S.alertas.map(a=>a.PRECIO_ANT);
  const ys = S.alertas.map(a=>a.PRECIO_HOY);
  const lbls = S.alertas.map(a=>esc(a.ISIN));
  Plotly.newPlot('chart-scatter-var',[{
    type:'scatter', mode:'markers',
    x:xs, y:ys, text:lbls,
    hovertemplate:'%{text}<br>Ant: %{x:.4f}<br>Hoy: %{y:.4f}<extra></extra>',
    marker:{
      color:S.alertas.map(a=>a.VAR_PCT),
      colorscale:[[0,'#00A65A'],[0.5,'#FFD60A'],[1,'#FF3B30']],
      size:7, opacity:.8, showscale:true,
      colorbar:{thickness:8,len:.7,tickfont:{size:8}},
    },
  }],{...PL(), margin:{t:8,b:40,l:52,r:8},
    xaxis:{...PL().xaxis, title:{text:'Precio anterior',font:{size:9}}},
    yaxis:{...PL().yaxis, title:{text:'Precio hoy',font:{size:9}}},
  },{responsive:true,displayModeBar:false});
}

// ── MULTIDIA ──────────────────────────────────────────────
async function cargarMultidia() {
  const wrap = $('wrap-multidia');
  if (S.mdData) { renderMultidia(); return; }
  wrap.innerHTML = '<div class="empty"><span class="spinner"></span></div>';
  try {
    const prov = $('sel-prov-md').value||'SP';
    const dias  = parseInt($('inp-dias-md').value)||10;
    S.mdData = await J(`/api/insumos/alertas_multidia/${S.fecha}?umbral_pct=${S.umbral}&proveedor=${prov}&dias=${dias}`);
    renderMultidia();
  } catch(e) { wrap.innerHTML=`<div class="empty">Error: ${esc(e.message)}</div>`; }
}

function renderMultidia() {
  const d = S.mdData;
  if (!d||!d.series) { $('wrap-multidia').innerHTML='<div class="empty">Sin datos</div>'; return; }
  const series = d.series;

  // Cards resumen
  $('md-cards').innerHTML = series.map(s=>{
    const nivel = s.anormales===0?'md-n c0':s.anormales<=3?'md-n c1':'md-n c2';
    const fa = s.fecha_ant;
    return `<div class="md-cell">
      <div class="md-fecha">${fa.slice(0,4)}-${fa.slice(4,6)}-${fa.slice(6)}</div>
      <div class="${nivel}">${s.anormales}</div>
      <div style="font-size:.58rem;color:var(--muted2);">${s.total} títulos · max ${fmtPct(s.max_var)}</div>
    </div>`;
  }).join('');

  // Gráfica evolución
  Plotly.newPlot('chart-multidia',[
    {
      name:'Alertas >umbral', type:'bar',
      x:series.map(s=>s.fecha_ant), y:series.map(s=>s.anormales),
      marker:{color:series.map(s=>s.anormales===0?'rgba(0,166,90,.6)':s.anormales<=3?'rgba(255,149,0,.7)':'rgba(255,59,48,.7)')},
    },
    {
      name:'Max Var %', type:'scatter', mode:'lines+markers',
      x:series.map(s=>s.fecha_ant), y:series.map(s=>s.max_var),
      yaxis:'y2', line:{color:'#BF5AF2',width:2}, marker:{size:5},
    }
  ],{...PL(), barmode:'group',
    yaxis:{...PL().yaxis, title:{text:'N alertas',font:{size:9}}},
    yaxis2:{overlaying:'y',side:'right',showgrid:false,title:{text:'Max Var %',font:{size:9}},tickfont:{size:9}},
    margin:{t:8,b:40,l:42,r:52},
  },{responsive:true,displayModeBar:false});

  $('wrap-multidia').innerHTML='';
}

function recargarMultidia() { S.mdData=null; cargarMultidia(); }

// ── CURVAS RENTA FIJA (SP) ────────────────────────────────
let _curvaData = null, _curvaFiltro = '';

async function cargarCurvas() {
  if (_curvaData) { renderCurvas(); return; }
  $('wrap-curvas').innerHTML='<div class="empty"><span class="spinner"></span></div>';
  try {
    _curvaData = await J(`/api/insumos/sp_curvas/${S.fecha}`);
    // Chips de tipo_tasa
    const chips = $('curva-chips');
    chips.innerHTML = ['Todos',...(_curvaData.tipos||[])].map((t,i)=>
      `<span class="tipo-chip ${i===0?'active':''}" onclick="filtrarCurva('${t}',this)">${t}</span>`
    ).join('');
    _curvaFiltro='';
    renderCurvas();
  } catch(e) { $('wrap-curvas').innerHTML=`<div class="empty">Error: ${esc(e.message)}</div>`; }
}

function filtrarCurva(tipo, el) {
  document.querySelectorAll('.tipo-chip').forEach(c=>c.classList.remove('active'));
  el.classList.add('active');
  _curvaFiltro = tipo==='Todos' ? '' : tipo;
  renderCurvas();
}

function renderCurvas() {
  if (!_curvaData) return;
  let curvas = _curvaData.curvas||[];
  if (_curvaFiltro) curvas = curvas.filter(c=>c.tipo===_curvaFiltro);

  const traces = curvas.map((c,i)=>({
    name: c.tipo,
    type: 'scatter', mode:'markers+lines',
    x: c.puntos.map(p=>p.Plazo),
    y: c.puntos.map(p=>p.TIR),
    text: c.puntos.map(p=>`${p.NEMO||p.ID}<br>Precio: ${fmtP(p.PRECIO,4)}<br>TIR: ${fmtP(p.TIR,4)}%<br>Vcto: ${p.Vcto||'—'}`),
    hoverinfo:'text',
    marker:{size:5, color:COLORS[i%COLORS.length]},
    line:{color:COLORS[i%COLORS.length], width:1.5},
  }));

  Plotly.newPlot('chart-curvas', traces, {
    ...PL(),
    margin:{t:8,b:44,l:52,r:14},
    xaxis:{...PL().xaxis, title:{text:'Plazo (días)',font:{size:9}}},
    yaxis:{...PL().yaxis, title:{text:'TIR (%)',font:{size:9}}},
  },{responsive:true, displayModeBar:false});

  // Tabla resumida
  const pts = curvas.flatMap(c=>c.puntos).slice(0,200);
  if (!pts.length) { $('wrap-curvas').innerHTML='<div class="empty">Sin puntos con TIR y Plazo.</div>'; return; }
  $('wrap-curvas').innerHTML=`<table>
    <thead><tr><th>NEMO</th><th>ISIN</th><th>Tipo_Tasa</th><th>Plazo</th><th>TIR</th><th>Precio</th><th>Vcto</th><th>Moneda</th></tr></thead>
    <tbody>${pts.map(p=>`<tr onclick="abrirHistorial('${esc(p.ID||'')}','SP')">
      <td><strong>${esc(p.NEMO||p.ID)}</strong></td>
      <td style="color:var(--muted);">${esc(p.ISIN||'—')}</td>
      <td>${esc(p.Tipo_Tasa||'—')}</td>
      <td>${fmtP(p.Plazo,0)}</td>
      <td>${fmtP(p.TIR,4)}</td>
      <td>${fmtP(p.PRECIO,4)}</td>
      <td>${esc(p.Vcto||'—')}</td>
      <td>${esc(p.Moneda||'—')}</td>
    </tr>`).join('')}</tbody></table>`;
}

// ── TABLAS GENÉRICAS ──────────────────────────────────────
const COLS_SHOW = {
  SP:    ['NEMO','ISIN','Tipo_Tasa','Plazo','Moneda','P_SUCIO','P_LIMPIO','TIR','PRECIO'],
  SW:    ['NEMO','Tipo_Registro','PRECIO'],
  SV:    ['Codigo','Tipo','Plazo','Tasa'],
  MX:    null, // todas
  NOTAS: null,
  TP:    ['Codigo','ISIN','PRECIO'],
};

async function cargarTabla(prov) {
  const wid = 'wrap-'+prov.toLowerCase().replace('_','-');
  const wrap = $(wid);
  if (!wrap) return;
  const busq = ($(('fil-busq-'+prov.toLowerCase()).replace('_','-'))||{}).value||'';
  if (S.tabData[prov+busq] && !busq) { renderTabla(prov, S.tabData[prov], wrap); return; }
  wrap.innerHTML='<div class="empty"><span class="spinner"></span></div>';
  try {
    let url = `/api/insumos/${prov.toLowerCase()}/${S.fecha}?limit=2000`;
    if (busq) url+='&busqueda='+encodeURIComponent(busq);
    const data = await J(url);
    if (!busq) S.tabData[prov]=data;
    renderTabla(prov, data, wrap);
  } catch(e) { wrap.innerHTML=`<div class="empty">Error: ${esc(e.message)}</div>`; }
}

function renderTabla(prov, data, wrap) {
  if (!data||!data.length) { wrap.innerHTML='<div class="empty">Sin datos</div>'; return; }
  let cols = COLS_SHOW[prov] || Object.keys(data[0]);
  cols = cols.filter(c=>data[0].hasOwnProperty(c)||true).filter(c=>c in data[0]);
  if (!cols.length) cols = Object.keys(data[0]);

  const isNumCol = c => typeof data[0][c]==='number';

  wrap.innerHTML=`<table>
    <thead><tr>${cols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead>
    <tbody>${data.slice(0,500).map(r=>`<tr onclick="abrirHistorial('${esc(r.ID||r.ISIN||r.NEMO||'')}','${prov}')">
      ${cols.map(c=>{
        const v = r[c];
        if (c==='PRECIO'||c==='P_SUCIO'||c==='P_LIMPIO'||c==='TIR'||c==='Tasa') return`<td><strong>${fmtP(v,4)}</strong></td>`;
        if (typeof v==='number') return`<td>${fmtP(v,4)}</td>`;
        return`<td>${esc(v??'—')}</td>`;
      }).join('')}
    </tr>`).join('')}</tbody></table>`;
}

// ── HISTORIAL POR ISIN (SLIDE PANEL) ─────────────────────
async function abrirHistorial(isin, fuente) {
  if (!isin || isin==='—') return;
  const panel = $('slide-hist');
  panel.classList.add('open');
  $('sp-titulo').textContent = isin;
  $('sp-fuente').textContent = fuente;
  $('sp-body').innerHTML='<div class="empty"><span class="spinner"></span></div>';

  try {
    const d = await J(`/api/insumos/historico/${encodeURIComponent(isin)}?proveedor=${fuente}&max_fechas=60`);
    const pts = d.puntos||[];
    if (!pts.length) { $('sp-body').innerHTML='<div class="empty">Sin histórico disponible.</div>'; return; }

    const precioAct = d.precio_actual;
    const precioMin = d.precio_min;
    const precioMax = d.precio_max;
    const varTotal  = pts.length>1 ? ((pts[pts.length-1].precio-pts[0].precio)/Math.abs(pts[0].precio)*100) : null;
    const rally30   = pts.length>1 ? ((precioMax-precioMin)/Math.abs(precioMin)*100) : null;

    // KPIs
    const kpis = [
      {l:'Precio actual', v:fmtP(precioAct,4)},
      {l:'Mín hist.',     v:fmtP(precioMin,4)},
      {l:'Máx hist.',     v:fmtP(precioMax,4)},
      {l:'Var. período',  v:fmtPct(varTotal), cls:varTotal>0?'n-pos':varTotal<0?'n-neg':''},
      {l:'Rally máx.',    v:fmtPct(rally30,1)},
      {l:'Observaciones', v:pts.length+' fechas'},
    ];

    // Var % diaria para coloring
    const varPcts = pts.map(p=>p.var_pct);
    const hasAlerta = varPcts.some(v=>Math.abs(v||0)>S.umbral);

    $('sp-body').innerHTML = `
      <div class="sp-kpis">${kpis.map(k=>`<div class="sp-kpi"><span class="sp-kpi-lbl">${k.l}</span><span class="sp-kpi-val ${k.cls||''}">${k.v}</span></div>`).join('')}</div>
      ${hasAlerta ? `<div style="padding:.5rem .75rem;background:rgba(255,149,0,.1);border:1px solid rgba(255,149,0,.3);border-radius:var(--r);font-size:.72rem;color:#FF9500;margin-bottom:10px;">⚠ Variaciones &gt;${S.umbral}% detectadas en este histórico</div>`:''}
      <div id="chart-sp-hist" style="height:220px;"></div>
      <div id="chart-sp-var" style="height:140px;margin-top:8px;"></div>
      <div style="margin-top:10px;" id="wrap-hist-tabla"></div>`;

    // Gráfica precio
    Plotly.newPlot('chart-sp-hist',[
      {
        type:'scatter', mode:'lines+markers',
        x:pts.map(p=>p.fecha), y:pts.map(p=>p.precio),
        name:'Precio',
        line:{color:'#0A84FF',width:2},
        marker:{
          size:pts.map(p=>Math.abs(p.var_pct||0)>S.umbral?8:5),
          color:pts.map(p=>Math.abs(p.var_pct||0)>S.umbral?'#FF3B30':'#0A84FF'),
        },
        hovertemplate:'%{x}<br>Precio: %{y:.4f}<extra></extra>',
      },
      ...(pts[0].TIR!=null ? [{
        type:'scatter', mode:'lines',
        x:pts.map(p=>p.fecha), y:pts.map(p=>p.TIR),
        name:'TIR', yaxis:'y2',
        line:{color:'#00A65A',width:1.5,dash:'dot'},
        hovertemplate:'%{x}<br>TIR: %{y:.4f}%<extra></extra>',
      }] : [])
    ],{...PL(),
      yaxis2:{overlaying:'y',side:'right',showgrid:false,tickfont:{size:9}},
      margin:{t:8,b:36,l:52,r:pts[0].TIR!=null?46:14},
      xaxis:{...PL().xaxis, tickangle:-30},
    },{responsive:true,displayModeBar:false});

    // Barras variación diaria
    Plotly.newPlot('chart-sp-var',[{
      type:'bar',
      x:pts.map(p=>p.fecha),
      y:pts.map(p=>p.var_pct||0),
      marker:{color:pts.map(p=>(p.var_pct||0)>0?'rgba(255,59,48,.75)':'rgba(0,166,90,.75)')},
      hovertemplate:'%{x}<br>Var: %{y:.4f}%<extra></extra>',
      name:'Var %',
    }],{...PL(),
      margin:{t:4,b:36,l:46,r:14},
      xaxis:{...PL().xaxis,tickangle:-30},
      yaxis:{...PL().yaxis,title:{text:'Var %',font:{size:9}}},
      shapes:[{type:'line',x0:pts[0].fecha,x1:pts[pts.length-1].fecha,y0:S.umbral,y1:S.umbral,line:{color:'rgba(255,59,48,.4)',dash:'dot',width:1}},
              {type:'line',x0:pts[0].fecha,x1:pts[pts.length-1].fecha,y0:-S.umbral,y1:-S.umbral,line:{color:'rgba(0,166,90,.4)',dash:'dot',width:1}}],
    },{responsive:true,displayModeBar:false});

    // Tabla histórico
    $('wrap-hist-tabla').innerHTML=`<div class="twrap" style="max-height:200px;"><table>
      <thead><tr><th>Fecha</th><th>Precio</th><th>Var Abs</th><th>Var %</th>${pts[0].TIR!=null?'<th>TIR</th>':''}</tr></thead>
      <tbody>${[...pts].reverse().map(p=>`<tr>
        <td>${p.fecha}</td>
        <td><strong>${fmtP(p.precio,4)}</strong></td>
        <td>${p.var_abs!=null?fmtP(p.var_abs,4):'—'}</td>
        <td><span class="vp ${clsPct(p.var_pct)}">${p.var_pct!=null?fmtPct(p.var_pct):'—'}</span></td>
        ${pts[0].TIR!=null?`<td>${fmtP(p.TIR,4)}</td>`:''}
      </tr>`).join('')}</tbody></table></div>`;
  } catch(e) { $('sp-body').innerHTML=`<div class="empty">Error: ${esc(e.message)}</div>`; }
}

function cerrarHistorial() { $('slide-hist').classList.remove('open'); }

// ── CONFIG ────────────────────────────────────────────────
async function cargarConfig() {
  try {
    const c = await J('/api/config');
    $('cfg-data-dir').value          = c.data_dir||'';
    $('cfg-infovalmer').value        = c.infovalmer_dir||'';
    $('cfg-umbral').value            = c.umbral_variacion_pct??3;
    $('cfg-host').value              = c.host||'0.0.0.0';
    $('cfg-port').value              = c.port||8001;
  } catch(e) { console.warn('config',e); }
}

async function guardarConfig() {
  const msg = $('cfg-msg');
  msg.textContent='Guardando...';
  const body = {
    data_dir:           $('cfg-data-dir').value,
    infovalmer_dir:     $('cfg-infovalmer').value,
    umbral_variacion_pct: parseFloat($('cfg-umbral').value)||3,
    host:               $('cfg-host').value,
    port:               parseInt($('cfg-port').value)||8001,
  };
  try {
    const r = await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j = await r.json();
    msg.style.color = j.ok?'var(--sk-green)':'var(--sk-red)';
    msg.textContent = j.ok?'Guardado correctamente':'Error al guardar';
  } catch(e) { msg.style.color='var(--sk-red)'; msg.textContent='Error: '+e.message; }
  setTimeout(()=>{ msg.textContent=''; msg.style.color=''; },3000);
}

// ── CONVERSOR ─────────────────────────────────────────────
async function cargarStatusCache() {
  const fecha = $('conv-fecha').value || S.fecha;
  if (!fecha) return;
  $('conv-fecha').value = fecha;
  const wrap = $('conv-tabla');
  wrap.innerHTML = '<div class="empty"><span class="spinner"></span> Verificando cache...</div>';
  try {
    const s = await J(`/api/insumos/cache/${fecha}`);
    _renderCacheTabla(s, wrap);
  } catch(e) { wrap.innerHTML=`<div class="empty" style="color:var(--sk-red);">Error: ${esc(e.message)}</div>`; }
}

function _renderCacheTabla(s, wrap) {
  const provs = Object.entries(s.proveedores||{});
  const totalOk = s.convertidos||0;
  const total   = s.total||provs.length;
  const completo = s.completo;

  wrap.innerHTML = `
    <div style="margin-bottom:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
      <span style="font-size:.75rem;font-weight:800;color:${completo?'var(--sk-green)':'var(--sk-orange)'};">
        ${completo ? '✓ Cache completo' : '⚠ Cache incompleto'} — ${totalOk}/${total} proveedores
      </span>
      <span style="font-size:.65rem;color:var(--muted2);">Infovalmer: ${esc(s.infovalmer||'')}</span>
    </div>
    <div class="twrap">
    <table>
      <thead><tr>
        <th>Proveedor</th>
        <th>PKL (cache)</th>
        <th>Excel (infovalmer)</th>
      </tr></thead>
      <tbody>${provs.map(([prov, v])=>`
        <tr>
          <td><strong>${esc(prov)}</strong></td>
          <td>${v.cache
            ? `<span style="color:var(--sk-green);font-weight:700;">✓ ok</span>`
            : `<span style="color:var(--sk-red);">✗ falta</span>`}</td>
          <td>${v.excel
            ? `<span style="color:var(--sk-green);font-weight:700;">✓ ok</span>`
            : `<span style="color:var(--muted2);">— pendiente</span>`}</td>
        </tr>`).join('')}
      </tbody>
    </table>
    </div>`;
}

async function convertirFecha() {
  const fecha = $('conv-fecha').value || S.fecha;
  const msg   = $('conv-msg');
  const fill  = $('conv-fill');
  const force = ($('conv-force')||{}).checked || false;
  if (!fecha) { msg.textContent = 'Selecciona una fecha'; return; }
  msg.innerHTML = '<span style="color:var(--muted2);">Convirtiendo en paralelo...</span>';
  fill.style.width = '10%';
  const wrap = $('conv-tabla');
  wrap.innerHTML = '<div class="empty"><span class="spinner"></span> Procesando...</div>';
  try {
    const r = await fetch(`/api/insumos/convertir/${fecha}?force=${force}&excel=true`, {method:'POST'});
    if (!r.ok) throw new Error(r.status);
    const d = await r.json();
    fill.style.width = '100%';
    const ok = (d.resultados||[]).filter(x=>x.cache_ok&&!x.omitido).length;
    const om = (d.resultados||[]).filter(x=>x.omitido).length;
    const er = (d.resultados||[]).filter(x=>!x.cache_ok).length;
    msg.innerHTML = `
      <span style="color:var(--sk-green);">✓ ${ok} convertidos</span>
      ${om ? `<span style="color:var(--muted2);margin-left:8px;">${om} ya existían</span>` : ''}
      ${er ? `<span style="color:var(--sk-red);margin-left:8px;">✗ ${er} errores</span>` : ''}`;
    // Mostrar tabla detallada de resultados
    wrap.innerHTML = `
      <div class="twrap">
      <table>
        <thead><tr><th>Proveedor</th><th>Filas</th><th>Estado</th><th>Excel</th></tr></thead>
        <tbody>${(d.resultados||[]).map(x=>`
          <tr>
            <td><strong>${esc(x.proveedor)}</strong></td>
            <td style="text-align:right;">${(x.filas||0).toLocaleString('es-CO')}</td>
            <td>${x.omitido
              ? '<span style="color:var(--muted2);">ya existía</span>'
              : x.cache_ok
                ? '<span style="color:var(--sk-green);font-weight:700;">✓ convertido</span>'
                : `<span style="color:var(--sk-red);">✗ ${esc(x.error||'error')}</span>`}
            </td>
            <td>${x.xlsx
              ? `<span style="color:var(--sk-green);">✓</span>`
              : '<span style="color:var(--muted2);">—</span>'}</td>
          </tr>`).join('')}
        </tbody>
      </table>
      </div>
      <div style="margin-top:8px;font-size:.65rem;color:var(--muted2);">
        Excel guardado en: ${esc(d.status?.infovalmer||'carpeta infovalmer del día')}
      </div>`;
    // Recargar datos con la nueva fecha
    S.tabData = {}; S.alertas = []; S.mdData = null; _curvaData = null;
    cargarTodo();
  } catch(e) {
    fill.style.width = '0';
    msg.innerHTML = `<span style="color:var(--sk-red);">Error: ${esc(e.message)}</span>`;
  }
}

// ── LOGS ──────────────────────────────────────────────────
async function cargarLogs() {
  try {
    S.logRaw = await J('/api/logs?limit=300');
    filtrarLogs();
    $('log-cnt').textContent = S.logRaw.length;
  } catch(e) { $('log-wrap').innerHTML='<div class="empty">Error cargando logs</div>'; }
}

function filtrarLogs() {
  const nivel = ($('log-nivel')||{}).value||'';
  const rows  = nivel ? S.logRaw.filter(l=>l.level===nivel) : S.logRaw;
  $('log-wrap').innerHTML = rows.slice().reverse().map(l=>`
    <div class="log-entry">
      <span class="log-ts">${esc(l.ts)}</span>
      <span class="log-lv ${l.level}">${l.level}</span>
      <span class="log-msg">${esc(l.msg)}</span>
    </div>`).join('');
}

function toggleLogAuto() {
  if ($('log-auto').checked) {
    S.logTimer = setInterval(cargarLogs, 5000);
  } else {
    clearInterval(S.logTimer); S.logTimer=null;
  }
}

// ── REACTIVIDAD TEMA ──────────────────────────────────────
document.addEventListener('sk-theme-change', ()=>{
  _curvaData = null;
  if (document.getElementById('chart-curvas')) renderCurvas();
  if (S.alertas.length) {
    renderChartAlertas();
  }
});

// ── ARRANQUE ──────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', ()=>{
  // Cerrar slide al clic fuera
  document.addEventListener('click', e=>{
    const panel = $('slide-hist');
    if (panel&&panel.classList.contains('open')&&!panel.contains(e.target)) {
      const row = e.target.closest('.top-row,.rally-card,.hm-cell,.twrap tr,.top-row');
      if (!row) cerrarHistorial();
    }
  });
  cargarFechas();
});

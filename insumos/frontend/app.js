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
  if (id==='tab-conversor')   { verificarConectividad(); cargarStatusCache(); }
  if (id==='tab-logs')        cargarLogs();
}

// ── INIT ──────────────────────────────────────────────────
function _fmtFecha(f) {
  return f ? `${f.slice(0,4)}-${f.slice(4,6)}-${f.slice(6)}` : '';
}

async function cargarFechas() {
  const sel = $('sel-fecha');
  sel.innerHTML = '<option value="">Cargando...</option>';
  try {
    const d = await J('/api/insumos/fechas');
    S.fechas = (d.fechas||[]).slice().reverse();
    if (!S.fechas.length) {
      sel.innerHTML = '<option value="">Sin fechas — verifica ruta en Config</option>';
      _actualizarSelectorFechaAnt();
      return;
    }
    // Llenar selector principal
    sel.innerHTML = S.fechas.map(f =>
      `<option value="${f}">${_fmtFecha(f)}</option>`
    ).join('');
    // Fijar fecha activa ANTES de actualizar el selector de comparación
    S.fecha = S.fechas[0];
    sel.value = S.fecha;
    _actualizarSelectorFechaAnt();
    cargarTodo();
  } catch(e) {
    sel.innerHTML = '<option value="">Error cargando fechas</option>';
    console.error('cargarFechas', e);
  }
}

function _actualizarSelectorFechaAnt() {
  const selAnt = $('sel-fecha-ant');
  if (!selAnt) return;
  // Todas las fechas EXCEPTO la activa actual
  const otras = S.fechas.filter(f => f !== S.fecha);
  selAnt.innerHTML = '<option value="">-- Auto (anterior) --</option>' +
    otras.map(f => `<option value="${f}">${_fmtFecha(f)}</option>`).join('');
}

async function cargarTodo() {
  S.fecha = $('sel-fecha').value;
  S.umbral = parseFloat($('inp-umbral').value)||3;
  if (!S.fecha) return;
  S.tabData = {}; S.alertas = []; S.spData = []; S.mdData = null; _curvaData = null;
  actualizarBadgesFecha();
  _actualizarSelectorFechaAnt();
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
  S.umbral = parseFloat($('inp-umbral').value)||3;
  const fechaAnt = ($('sel-fecha-ant')||{}).value || '';
  try {
    let url = `/api/insumos/alertas/${S.fecha}?umbral_pct=${S.umbral}`;
    if (fechaAnt) url += `&fecha_ant=${fechaAnt}`;
    const d = await J(url);
    S.alertas = d.alertas || [];
    S.fechaAnt = d.fecha_ant || '';
    // Actualizar selector con las fechas disponibles que devuelve el backend
    if (d.fechas_disponibles && d.fechas_disponibles.length) {
      S.fechas = d.fechas_disponibles.slice().reverse();
      _actualizarSelectorFechaAnt();
      // Restaurar selección
      if (fechaAnt) $('sel-fecha-ant').value = fechaAnt;
    }
    $('kpi-alertas').textContent   = S.alertas.length;
    $('kpi-criticas').textContent  = d.criticas||0;
    $('kpi-fecha-ant').textContent = d.fecha_ant
      ? `${d.fecha_ant.slice(0,4)}-${d.fecha_ant.slice(4,6)}-${d.fecha_ant.slice(6)}` : '—';
    renderBannerAlerta(d);
    renderAlertas();
    renderTopVariaciones();
    renderRallyCards();
    renderHeatmap();
    renderChartAlertas();
  } catch(e) {
    wrap.innerHTML = `<div class="empty">Sin fecha anterior disponible para comparar.</div>`;
    S.alertas = [];
    S.fechaAnt = '';
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

// Detectar si las alertas usan precio grande (>100) para decidir decimales
function _decAlertas(rows) {
  const ps = rows.map(r=>r.PRECIO_HOY).filter(v=>v!=null&&!isNaN(v));
  return ps.length && ps.some(v=>Math.abs(v)>50) ? 2 : 4;
}

function renderAlertas() {
  const busq     = ($('fil-busq-alertas')||{}).value||'';
  const fuente   = ($('fil-fuente-alertas')||{}).value||'';
  const sev      = ($('fil-sev-alertas')||{}).value||'';
  const soloSube = ($('fil-solo-subida')||{}).checked||false;
  const soloBaja = ($('fil-solo-bajada')||{}).checked||false;
  let rows = [...S.alertas];

  // Filtros
  if (busq)     rows = rows.filter(r=>{
    const haystack = [r.ISIN,r.ID,r.NEMO,r.Descripcion,r.FUENTE].map(v=>String(v||'').toUpperCase()).join(' ');
    return haystack.includes(busq.toUpperCase());
  });
  if (fuente)   rows = rows.filter(r=>r.FUENTE===fuente);
  if (sev)      rows = rows.filter(r=>r.SEVERIDAD===sev);
  if (soloSube) rows = rows.filter(r=>(r.VAR_PCT||0)>0);
  if (soloBaja) rows = rows.filter(r=>(r.VAR_PCT||0)<0);

  // Ordenar
  const numCols = ['VAR_PCT','VAR_ABS','PRECIO_HOY','PRECIO_ANT'];
  rows.sort((a,b)=>{
    const av = numCols.includes(_alertSort.col) ? Math.abs(a[_alertSort.col]||0) : String(a[_alertSort.col]||'');
    const bv = numCols.includes(_alertSort.col) ? Math.abs(b[_alertSort.col]||0) : String(b[_alertSort.col]||'');
    if (typeof av==='number') return _alertSort.dir*(bv-av);
    return _alertSort.dir*(av<bv?-1:av>bv?1:0);
  });

  $('cnt-alertas').textContent = rows.length+' filas';
  const wrap = $('wrap-alertas');
  if (!rows.length) { wrap.innerHTML='<div class="empty">Sin alertas para el filtro seleccionado.</div>'; return; }

  const dec = _decAlertas(rows);
  const thCls = col => _alertSort.col===col ? (_alertSort.dir>0?'th-asc':'th-desc') : '';
  const fa = S.fechaAnt || '—';

  wrap.innerHTML = `<table>
    <thead><tr>
      <th onclick="sortAlertas('SEVERIDAD')" class="${thCls('SEVERIDAD')}">SEV</th>
      <th onclick="sortAlertas('FUENTE')" class="${thCls('FUENTE')}">Fuente</th>
      <th onclick="sortAlertas('ID')" class="${thCls('ID')}">ISIN / ID</th>
      <th onclick="sortAlertas('NEMO')" class="${thCls('NEMO')}">NEMO</th>
      <th style="color:var(--muted);font-weight:400;font-size:.6rem;">Info</th>
      <th onclick="sortAlertas('PRECIO_HOY')" class="${thCls('PRECIO_HOY')}" title="${S.fecha}">P. Hoy</th>
      <th onclick="sortAlertas('PRECIO_ANT')" class="${thCls('PRECIO_ANT')}" title="${fa}">P. ${fa.slice(0,4)?fa.slice(4,6)+'/'+fa.slice(6):'Ant.'}</th>
      <th onclick="sortAlertas('VAR_ABS')" class="${thCls('VAR_ABS')}">Var $</th>
      <th onclick="sortAlertas('VAR_PCT')" class="${thCls('VAR_PCT')}">Var %</th>
    </tr></thead>
    <tbody>${rows.map(r=>{
      const sevCls = r.SEVERIDAD==='CRITICA'?'sC':r.SEVERIDAD==='ALTA'?'sA':'sM';
      const rowCls = r.SEVERIDAD==='CRITICA'?'rc':r.SEVERIDAD==='ALTA'?'ra':'';
      // Info extra del proveedor
      const infoParts = [];
      if (r.Tipo_Tasa)     infoParts.push(r.Tipo_Tasa);
      if (r.Tipo)          infoParts.push(r.Tipo);
      if (r.Moneda)        infoParts.push(r.Moneda);
      if (r.Plazo)         infoParts.push(r.Plazo+'d');
      if (r.Vcto)          infoParts.push('Vcto:'+r.Vcto);
      if (r.Tipo_Registro) infoParts.push(r.Tipo_Registro);
      const infoStr = infoParts.slice(0,3).join(' · ');
      const desc = r.Descripcion || r.Emisor || '';
      const nemo = r.NEMO || r.Codigo || '';
      const id   = r.ID || r.ISIN || '';
      return `<tr class="${rowCls}" onclick="abrirHistorial('${esc(id)}','${r.FUENTE}')">
        <td><span class="sev ${sevCls}">${r.SEVERIDAD}</span></td>
        <td><span class="src-badge src-${r.FUENTE}">${esc(r.FUENTE)}</span></td>
        <td><strong class="isin-cell" title="${esc(desc)}">${esc(id)}</strong></td>
        <td class="nemo-cell">${esc(nemo)||'—'}</td>
        <td style="font-size:.6rem;color:var(--muted2);">${esc(infoStr)||'—'}</td>
        <td class="num-cell"><strong>${fmtP(r.PRECIO_HOY,dec)}</strong></td>
        <td class="num-cell muted">${fmtP(r.PRECIO_ANT,dec)}</td>
        <td class="num-cell"><span class="vp ${clsPct(r.VAR_ABS)}">${r.VAR_ABS!=null?(r.VAR_ABS>=0?'+':'')+fmtP(r.VAR_ABS,dec):'—'}</span></td>
        <td class="num-cell"><span class="vp ${clsPct(r.VAR_PCT)}">${fmtPct(r.VAR_PCT)}</span></td>
      </tr>`;
    }).join('')}
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
    return arr.map((r,i)=>{
      const id   = r.NEMO || r.ID || r.ISIN || '—';
      const sub  = r.NEMO ? (r.ID||r.ISIN||'') : '';
      const dec  = Math.abs(r.PRECIO_HOY||0)>50 ? 2 : 4;
      return `<div class="top-row" onclick="abrirHistorial('${esc(r.ID||r.ISIN)}','${r.FUENTE}')">
        <span class="top-rank">${i+1}</span>
        <div style="flex:1;min-width:0;">
          <div class="top-id">${esc(id)}</div>
          ${sub?`<div style="font-size:.58rem;color:var(--muted2);overflow:hidden;text-overflow:ellipsis;">${esc(sub)}</div>`:''}
        </div>
        <span class="top-src">${esc(r.FUENTE)}</span>
        <div style="text-align:right;">
          <div class="vp ${cls}">${fmtPct(r.VAR_PCT)}</div>
          <div style="font-size:.58rem;color:var(--muted2);">${fmtP(r.PRECIO_ANT,dec)} &rarr; ${fmtP(r.PRECIO_HOY,dec)}</div>
        </div>
      </div>`;
    }).join('');
  }

  $('top-sube').innerHTML = filas(sube,'vU');
  $('top-baja').innerHTML = filas(baja,'vD');
}

// ── RALLY CARDS ───────────────────────────────────────────
function renderRallyCards() {
  const top = [...S.alertas]
    .sort((a,b)=>Math.abs(b.VAR_PCT)-Math.abs(a.VAR_PCT))
    .slice(0,12);
  const wrap = $('rally-wrap');
  if (!top.length) { wrap.innerHTML='<div class="empty">Sin alertas</div>'; return; }

  const srcColor = {SP:'#0A84FF',SW:'#BF5AF2',SV:'#FF9500',MX:'#00A65A',MX_RV:'#00C96E',NOTAS:'#FFD60A',TP:'#FF3B30'};

  wrap.innerHTML = top.map(r => {
    const up  = r.VAR_PCT > 0;
    const col = srcColor[r.FUENTE]||'#8E8E93';
    const id  = r.NEMO || r.ID || r.ISIN || '—';
    const sub = r.NEMO ? (r.ID||r.ISIN||'') : '';
    const dec = Math.abs(r.PRECIO_HOY||0)>50 ? 2 : 4;
    const infoTag = [r.Tipo_Tasa, r.Moneda, r.Vcto].filter(Boolean).slice(0,2).join(' · ');
    return `<div class="rally-card" style="--rc:${col};" onclick="abrirHistorial('${esc(r.ID||r.ISIN)}','${r.FUENTE}')">
      <div class="rc-src">${esc(r.FUENTE)}</div>
      <div class="rc-id">${esc(id)}</div>
      ${sub?`<div style="font-size:.55rem;color:rgba(255,255,255,.5);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(sub)}</div>`:''}
      ${infoTag?`<div style="font-size:.52rem;color:rgba(255,255,255,.45);margin-top:1px;">${esc(infoTag)}</div>`:''}
      <div class="rc-pct ${up?'rc-up':'rc-dn'}">${fmtPct(r.VAR_PCT)}</div>
      <div class="rc-det">${fmtP(r.PRECIO_ANT,dec)} &rarr; ${fmtP(r.PRECIO_HOY,dec)}</div>
      ${r.VAR_ABS!=null?`<div style="font-size:.55rem;color:rgba(255,255,255,.5);margin-top:2px;">${up?'+':''}${fmtP(r.VAR_ABS,dec)} abs.</div>`:''}
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
    $('cfg-infovalmer').value = c.infovalmer_dir||'';
    $('cfg-umbral').value     = c.umbral_variacion_pct??3;
    $('cfg-host').value       = c.host||'0.0.0.0';
    $('cfg-port').value       = c.port||8001;
    // Mostrar estado de infovalmer
    const exists = c.infovalmer_dir_exists;
    const msg = $('cfg-msg');
    if (msg) {
      msg.style.color = exists ? 'var(--sk-green)' : 'var(--sk-red)';
      msg.textContent = exists ? '✓ Carpeta Infovalmer accesible' : '✗ Carpeta Infovalmer no encontrada';
    }
  } catch(e) { console.warn('config', e); }
}

async function guardarConfig() {
  const msg = $('cfg-msg');
  msg.textContent = 'Guardando...'; msg.style.color = '';
  const body = {
    infovalmer_dir:       $('cfg-infovalmer').value,
    umbral_variacion_pct: parseFloat($('cfg-umbral').value)||3,
    host:                 $('cfg-host').value,
    port:                 parseInt($('cfg-port').value)||8001,
  };
  try {
    const r = await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j = await r.json();
    msg.style.color = j.ok ? 'var(--sk-green)' : 'var(--sk-red)';
    msg.textContent = j.ok ? 'Guardado correctamente' : 'Error al guardar';
  } catch(e) { msg.style.color='var(--sk-red)'; msg.textContent='Error: '+e.message; }
  setTimeout(()=>{ msg.textContent=''; msg.style.color=''; }, 3000);
}

// ── CONECTIVIDAD VPN ──────────────────────────────────────
async function verificarConectividad() {
  const dot   = $('vpn-dot');
  const lbl   = $('vpn-lbl');
  const cdot  = $('conv-vpn-dot');
  const cmsg  = $('conv-vpn-msg');
  if (lbl) lbl.textContent = '...';
  try {
    const d = await J('/api/insumos/conectividad');
    const ok  = d.principal_accesible;
    const nf  = d.fechas_disponibles?.length || 0;
    const col = ok ? '#00A65A' : '#FF9500';
    const txt = ok
      ? `Infovalmer OK (${nf} fechas)`
      : (d.infovalmer_dir ? 'Sin VPN / ruta no accesible' : 'Sin configurar');

    if (dot)  { dot.style.background  = col; }
    if (lbl)  { lbl.textContent = txt; lbl.style.color = col; }
    if (cdot) { cdot.style.background = col; }
    if (cmsg) {
      cmsg.textContent = d.mensaje || txt;
      cmsg.style.color = ok ? 'var(--sk-green)' : '#FF9500';
    }

    // Si encontró fechas y el selector está vacío (o en estado de error), recargar
    if (ok && nf > 0 && !S.fechas.length) {
      cargarFechas();
    }

    // Mostrar rutas disponibles en el panel conversor
    if (d.bases && d.bases.length) {
      const infoEl = $('conv-vpn-info');
      if (infoEl) {
        const rutasHtml = d.bases.map(b=>`
          <span style="display:inline-flex;align-items:center;gap:4px;padding:.1rem .4rem;border-radius:3px;background:${b.accesible?'rgba(0,166,90,.1)':'rgba(255,149,0,.1)'};border:1px solid ${b.accesible?'rgba(0,166,90,.25)':'rgba(255,149,0,.25)'};font-size:.6rem;margin-right:4px;">
            <span style="width:5px;height:5px;border-radius:50%;background:${b.accesible?'#00A65A':'#FF9500'};flex-shrink:0;"></span>
            ${esc(b.ruta)} ${b.accesible?`(${b.n_fechas} fechas)`:'sin acceso'}
          </span>`).join('');
        infoEl.innerHTML = `
          <span id="conv-vpn-dot" style="width:9px;height:9px;border-radius:50%;background:${col};flex-shrink:0;"></span>
          <span id="conv-vpn-msg" style="color:${ok?'var(--sk-green)':'#FF9500'};">${esc(d.mensaje)}</span>
          <div style="margin-left:8px;display:flex;flex-wrap:wrap;gap:3px;">${rutasHtml}</div>
          <button class="btn btn-ghost btn-sm" style="margin-left:auto;padding:.15rem .5rem;" onclick="verificarConectividad()">Verificar VPN</button>`;
      }
    }
  } catch(e) {
    if (dot) dot.style.background = '#FF3B30';
    if (lbl) { lbl.textContent = 'Error'; lbl.style.color = '#FF3B30'; }
    if (cmsg) cmsg.textContent = 'Error verificando conexion';
  }
}

// ── CONVERSOR ─────────────────────────────────────────────
async function cargarStatusCache() {
  const fecha = $('conv-fecha').value || S.fecha;
  if (!fecha) return;
  $('conv-fecha').value = fecha;
  const wrap = $('conv-tabla');
  $('conv-live').style.display = 'none';
  wrap.innerHTML = '<div class="empty"><span class="spinner"></span> Verificando cache...</div>';
  try {
    const s = await J(`/api/insumos/cache/${fecha}`);
    _renderCacheTabla(s, wrap);
  } catch(e) { wrap.innerHTML=`<div class="empty" style="color:var(--sk-red);">Error: ${esc(e.message)}</div>`; }
}

function _renderCacheTabla(s, wrap) {
  const provs   = Object.entries(s.proveedores||{});
  const pklOk   = s.pkl_ok  ?? 0;
  const xlsxOk  = s.xlsx_ok ?? 0;
  const total   = s.total   || provs.length;
  const compPkl = pklOk === total;
  const compXls = xlsxOk === total;

  // Colores de fuente
  const srcColor = {SP:'#0A84FF',SW:'#BF5AF2',SV:'#FF9500',MX:'#00A65A',
                    MX_RV:'#00C96E',NOTAS:'#FFD60A',TP:'#FF3B30',SB:'#8E8E93',MONEDAS:'#58a6ff'};

  wrap.innerHTML = `
    <div style="margin-bottom:10px;display:flex;gap:12px;flex-wrap:wrap;align-items:center;">
      <span style="font-size:.75rem;font-weight:800;color:${compPkl?'var(--sk-green)':'#FF9500'};">
        Cache: ${pklOk}/${total} ${compPkl?'&#x2713;':'&#x26A0;'}
      </span>
      <span style="font-size:.75rem;font-weight:800;color:${compXls?'var(--sk-green)':'#FF9500'};">
        Excel: ${xlsxOk}/${total} ${compXls?'&#x2713;':'&#x26A0;'}
      </span>
      <span style="font-size:.62rem;color:var(--muted2);overflow:hidden;text-overflow:ellipsis;">
        ${esc(s.pkl_dir||'')}
      </span>
    </div>
    <div class="twrap" style="max-height:320px;">
    <table>
      <thead><tr>
        <th>Proveedor</th>
        <th style="text-align:center;">Cache (.pkl)</th>
        <th style="text-align:center;">Excel</th>
        <th>Ruta pkl</th>
      </tr></thead>
      <tbody>${provs.map(([prov, v])=>`
        <tr>
          <td><span class="src-badge src-${prov}" style="color:${srcColor[prov]||'var(--muted)'}">${esc(prov)}</span></td>
          <td style="text-align:center;">${v.pkl
            ? `<span style="color:var(--sk-green);font-weight:700;">&#x2713; ok</span>`
            : `<span style="color:#FF9500;">&#x25CB; falta</span>`}</td>
          <td style="text-align:center;">${v.xlsx
            ? `<span style="color:var(--sk-green);font-weight:700;">&#x2713; ok</span>`
            : `<span style="color:var(--muted2);">&#x2014;</span>`}</td>
          <td style="font-size:.59rem;color:var(--muted2);max-width:300px;overflow:hidden;text-overflow:ellipsis;">
            ${v.pkl ? esc(v.pkl_path||'') : '—'}
          </td>
        </tr>`).join('')}
      </tbody>
    </table>
    </div>`;
}

// Estado en vivo de la tabla de conversión
const _liveRows = {};   // proveedor → <tr> element

function _initLiveTabla(proveedores) {
  const tbody = $('conv-live-body');
  tbody.innerHTML = '';
  Object.keys(_liveRows).forEach(k => delete _liveRows[k]);
  const srcColor = {SP:'#0A84FF',SW:'#BF5AF2',SV:'#FF9500',MX:'#00A65A',
                    MX_RV:'#00C96E',NOTAS:'#FFD60A',TP:'#FF3B30',SB:'#8E8E93',MONEDAS:'#58a6ff'};
  proveedores.forEach(p => {
    const tr = document.createElement('tr');
    tr.id = `conv-row-${p}`;
    tr.innerHTML = `
      <td><span class="src-badge" style="background:rgba(128,128,128,.1);color:${srcColor[p]||'var(--muted)'};">${p}</span></td>
      <td id="conv-st-${p}" style="color:var(--muted2);font-size:.72rem;">En espera...</td>
      <td id="conv-fi-${p}" style="text-align:right;color:var(--muted2);">—</td>
      <td id="conv-pk-${p}" style="text-align:center;">—</td>
      <td id="conv-xl-${p}" style="text-align:center;">—</td>
      <td id="conv-tm-${p}" style="text-align:right;color:var(--muted2);">—</td>`;
    tbody.appendChild(tr);
    _liveRows[p] = tr;
  });
}

function _updateLiveRow(ev) {
  const p = ev.proveedor;
  if (!p || !$(`conv-st-${p}`)) return;
  const stEl = $(`conv-st-${p}`);
  const fiEl = $(`conv-fi-${p}`);
  const pkEl = $(`conv-pk-${p}`);
  const xlEl = $(`conv-xl-${p}`);
  const tmEl = $(`conv-tm-${p}`);

  if (ev.error) {
    stEl.innerHTML = `<span style="color:#FF3B30;">&#x2717; ${esc(ev.msg||'Error')}</span>`;
  } else if (ev.omitido) {
    stEl.innerHTML = `<span style="color:var(--muted2);">ya existia</span>`;
    fiEl.textContent = (ev.filas||0).toLocaleString('es-CO');
    pkEl.innerHTML = `<span style="color:var(--sk-green);">&#x2713;</span>`;
    xlEl.innerHTML = `<span style="color:var(--sk-green);">&#x2713;</span>`;
  } else if (ev.cache_ok) {
    stEl.innerHTML = `<span style="color:var(--sk-green);font-weight:700;">&#x2713; OK</span>`;
    fiEl.textContent = (ev.filas||0).toLocaleString('es-CO');
    pkEl.innerHTML = `<span style="color:var(--sk-green);">&#x2713;</span>`;
    xlEl.innerHTML = `<span style="color:var(--sk-green);">&#x2713;</span>`;
    if (ev.tiempo_s != null) tmEl.textContent = ev.tiempo_s+'s';
  } else {
    // En progreso
    const pct = ev.pct || 0;
    stEl.innerHTML = `<span style="color:var(--muted);">${esc(ev.msg||'...')}</span>
      <div style="height:3px;background:var(--surf2);border-radius:2px;margin-top:3px;width:100%;">
        <div style="height:3px;background:#0A84FF;border-radius:2px;width:${pct}%;transition:width .3s;"></div>
      </div>`;
  }
}

async function convertirFecha() {
  const fecha = $('conv-fecha').value || S.fecha;
  const msg   = $('conv-msg');
  const fill  = $('conv-fill');
  const force = ($('conv-force')||{}).checked || false;
  const btnC  = $('btn-convertir');
  if (!fecha) { if(msg) msg.textContent = 'Selecciona una fecha'; return; }

  // Bloquear botón
  if (btnC) { btnC.disabled=true; btnC.textContent='Convirtiendo...'; }
  if (msg)  msg.textContent = 'Conectando...';
  if (fill) fill.style.width = '2%';

  // Ocultar tabla estática, mostrar tabla en vivo
  $('conv-tabla').style.display = 'none';
  $('conv-live').style.display  = 'block';
  const PROVS = ['SP','SW','SV','TP','MX','MX_RV','NOTAS','SB','MONEDAS'];
  _initLiveTabla(PROVS);

  // ── Conectar SSE ANTES de lanzar el POST ─────────────────────────
  let sseOk = false;
  const evtSrc = new EventSource(`/api/insumos/convertir_progreso/${fecha}`);

  evtSrc.onmessage = ev => {
    try {
      const d = JSON.parse(ev.data);
      if (d.done) {
        evtSrc.close();
        if (btnC) { btnC.disabled=false; btnC.textContent='▶ Convertir'; }
        if (fill) fill.style.width = '100%';
        if (msg) msg.textContent = d.msg || 'Completado';
        // Recargar estado cache
        setTimeout(()=>{
          $('conv-tabla').style.display = '';
          $('conv-live').style.display  = 'none';
          cargarStatusCache();
          S.tabData={}; S.alertas=[]; S.mdData=null; _curvaData=null;
          cargarTodo();
        }, 1200);
        return;
      }
      // Actualizar barra global
      if (d.pct != null && fill) fill.style.width = d.pct+'%';
      if (d.msg && msg)  msg.textContent = (d.proveedor?`[${d.proveedor}] `:'') + d.msg;
      // Actualizar fila del proveedor
      _updateLiveRow(d);
    } catch(_) {}
  };

  evtSrc.onerror = () => {
    if (!sseOk) {
      // SSE no disponible — fallback sin progreso
      evtSrc.close();
    }
  };

  // Pequeña pausa para que SSE se conecte antes del POST
  await new Promise(r => setTimeout(r, 150));
  sseOk = true;

  try {
    const r = await fetch(`/api/insumos/convertir/${fecha}?force=${force}`, {method:'POST'});
    if (!r.ok) throw new Error(r.status);
    // El cierre lo hace el evento SSE "done"
  } catch(e) {
    evtSrc.close();
    if (btnC) { btnC.disabled=false; btnC.textContent='▶ Convertir'; }
    if (fill) fill.style.width = '0';
    if (msg)  msg.innerHTML = `<span style="color:var(--sk-red);">Error: ${esc(e.message)}</span>`;
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
  // Verificar conectividad VPN al inicio (no bloquea la carga)
  verificarConectividad().catch(()=>{});
  cargarFechas();
});

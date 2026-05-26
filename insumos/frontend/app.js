/**
 * MVALORACION — Módulo Insumos
 * Depende de: /static/shared/nav.js  (toggleTheme, apiFetch, getPL, fmtNum, escHtml, nc, debounce)
 */

/* ═══════════════════════════════════════════════════════
   ESTADO GLOBAL
═══════════════════════════════════════════════════════ */
const State = {
  fecha:        '',
  proveedores:  [], // ['SP','SW','SV','MX',...]
  tabsLoaded:   new Set(),
  // datos cacheados por tab
  alertas:      null,
  alertasMulti: null,
  spData:       null,  // renta fija curvas
  tablaData:    {},    // { SP: [...], SW: [...], ... }
  // panel histórico
  histIsin:     null,
  histProv:     null,
};

/* ═══════════════════════════════════════════════════════
   BOOT
═══════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  initThemeListener();
  cargarFechas();
});

function initThemeListener() {
  document.addEventListener('sk-theme-change', () => {
    // Re-dibujar gráficas activas cuando cambia el tema
    const active = document.querySelector('.panel.active');
    if (!active) return;
    const id = active.id.replace('tab-', '');
    if (id === 'alertas')  renderAlertasCharts();
    if (id === 'curvas')   renderCurvas();
    if (id === 'historico') { /* nada, se redibuja al abrir */ }
  });
}

/* ═══════════════════════════════════════════════════════
   FECHAS Y TOOLBAR
═══════════════════════════════════════════════════════ */
async function cargarFechas() {
  const sel = document.getElementById('sel-fecha');
  sel.innerHTML = '<option>Cargando…</option>';
  try {
    const data = await apiFetch('/api/insumos/fechas');
    const fechas = (Array.isArray(data) ? data : (data.fechas || [])).slice().reverse();
    if (!fechas.length) { sel.innerHTML = '<option value="">Sin fechas</option>'; return; }
    sel.innerHTML = fechas.map(f =>
      `<option value="${f}">${f.slice(0,4)}-${f.slice(4,6)}-${f.slice(6)}</option>`
    ).join('');
    State.fecha = fechas[0];
    onFechaChange();
  } catch (e) {
    sel.innerHTML = '<option value="">Error cargando fechas</option>';
    console.error(e);
  }
}

function onFechaChange() {
  State.fecha = document.getElementById('sel-fecha').value;
  if (!State.fecha) return;
  // Reset estado
  State.tabsLoaded.clear();
  State.alertas     = null;
  State.alertasMulti = null;
  State.spData      = null;
  State.tablaData   = {};
  closeHistPanel();
  // Cargar overview y tab activo
  cargarResumen();
  const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab;
  if (activeTab) loadTab(activeTab, true);
}

/* ═══════════════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════════════ */
function irTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + tabId));
  loadTab(tabId, false);
}

function loadTab(tabId, force = false) {
  if (!force && State.tabsLoaded.has(tabId)) return;
  State.tabsLoaded.add(tabId);
  switch (tabId) {
    case 'alertas':   cargarAlertas();   break;
    case 'multidia':  cargarMultidia();  break;
    case 'curvas':    cargarCurvas();    break;
    case 'sp':        cargarTabla('SP'); break;
    case 'sw':        cargarTabla('SW'); break;
    case 'sv':        cargarTabla('SV'); break;
    case 'mx':        cargarTabla('MX'); break;
    case 'notas':     cargarTabla('NOTAS'); break;
    case 'conversor': initConversor();   break;
  }
}

/* ═══════════════════════════════════════════════════════
   RESUMEN / KPIs
═══════════════════════════════════════════════════════ */
async function cargarResumen() {
  const fecha = State.fecha;
  // Alertas críticas → strip
  try {
    const data = await apiFetch(`/api/insumos/alertas/${fecha}?max_dias=1`);
    const alertas = data.alertas || [];
    const crit = alertas.filter(a => a.SEVERIDAD === 'CRITICA' || a.SEVERIDAD === 'ALTA');
    const strip = document.getElementById('alertStrip');
    if (crit.length) {
      strip.textContent = `⚠️ ${crit.length} alerta${crit.length > 1 ? 's' : ''} crítica${crit.length > 1 ? 's' : ''} detectada${crit.length > 1 ? 's' : ''} — clic en pestaña Alertas`;
      strip.classList.add('show');
    } else {
      strip.classList.remove('show');
    }
    // KPIs
    setKpi('kpi-alertas', crit.length, crit.length > 0 ? 'var(--sk-red)' : 'var(--sk-green)',
      crit.length > 0 ? 'alertas críticas/altas' : '✓ sin alertas críticas');
    setKpi('kpi-total-alertas', alertas.length, 'var(--sk-orange)', 'variaciones detectadas');
    State.alertas = data;
  } catch {}

  // Fechas disponibles → contar proveedores
  try {
    const pdata = await apiFetch(`/api/insumos/proveedores/${fecha}`);
    const provs = pdata.proveedores || [];
    State.proveedores = provs;
    setKpi('kpi-proveedores', provs.length, 'var(--sk-blue)', provs.join(' · ') || 'ninguno');
  } catch {
    setKpi('kpi-proveedores', '—', 'var(--muted)', 'sin datos');
  }

  // Fecha display
  const f = State.fecha;
  document.getElementById('kpi-fecha-val').textContent = f ? `${f.slice(6)}.${f.slice(4,6)}.${f.slice(0,4)}` : '—';
}

function setKpi(id, val, color, sub) {
  const el = document.getElementById(id);
  if (!el) return;
  const valEl = el.querySelector('.kpi-val');
  const subEl = el.querySelector('.kpi-sub');
  if (valEl) { valEl.textContent = val; if (color) valEl.style.color = color; }
  if (subEl && sub != null) subEl.textContent = sub;
}

/* ═══════════════════════════════════════════════════════
   TAB: ALERTAS (día actual)
═══════════════════════════════════════════════════════ */
async function cargarAlertas() {
  const fecha = State.fecha;
  const wrap  = document.getElementById('wrap-alertas');
  const pieEl = document.getElementById('chart-alertas-pie');
  const barEl = document.getElementById('chart-alertas-bar');

  wrap.innerHTML = '<div class="loading"><span class="spin"></span> Cargando alertas…</div>';

  try {
    const data = State.alertas || await apiFetch(`/api/insumos/alertas/${fecha}?max_dias=1`);
    State.alertas = data;
    const alertas = data.alertas || [];

    if (!alertas.length) {
      wrap.innerHTML = '<div class="sect-empty">✅ Sin variaciones de precio detectadas para esta fecha.</div>';
      if (pieEl) pieEl.innerHTML = '';
      if (barEl) barEl.innerHTML = '';
      return;
    }

    // Gráficas
    renderAlertasCharts(alertas);

    // Tabla
    renderTablaAlertas(alertas);
  } catch (e) {
    wrap.innerHTML = `<div class="sect-empty" style="color:var(--sk-red)">Error: ${escHtml(e.message)}</div>`;
  }
}

function renderAlertasCharts(alertas) {
  if (!alertas) alertas = State.alertas?.alertas || [];
  if (!alertas.length) return;

  const PL = getPL();

  // Pie por severidad
  const sevMap = {};
  alertas.forEach(a => { sevMap[a.SEVERIDAD || 'MEDIA'] = (sevMap[a.SEVERIDAD || 'MEDIA'] || 0) + 1; });
  const sevColors = { CRITICA: '#FF3B30', ALTA: '#FF9500', MEDIA: '#FFD60A', BAJA: '#00A65A' };
  const pieEl = document.getElementById('chart-alertas-pie');
  if (pieEl && typeof Plotly !== 'undefined') {
    Plotly.newPlot(pieEl, [{
      type: 'pie', labels: Object.keys(sevMap), values: Object.values(sevMap),
      hole: .45, textinfo: 'label+value',
      marker: { colors: Object.keys(sevMap).map(s => sevColors[s] || '#8E8E93') },
    }], { ...PL, margin: { t: 5, b: 5, l: 5, r: 5 } }, { responsive: true, displayModeBar: false });
  }

  // Bar: top variaciones %
  const sorted = [...alertas].sort((a, b) => Math.abs(b.VAR_PCT || 0) - Math.abs(a.VAR_PCT || 0)).slice(0, 15);
  const barEl = document.getElementById('chart-alertas-bar');
  if (barEl && typeof Plotly !== 'undefined') {
    const labels = sorted.map(a => (a.ISIN || a.NEMOTECNICO || '?').slice(0, 14)).reverse();
    const vals   = sorted.map(a => a.VAR_PCT || 0).reverse();
    Plotly.newPlot(barEl, [{
      type: 'bar', orientation: 'h', x: vals, y: labels,
      marker: { color: vals.map(v => v < 0 ? '#00A65A' : '#FF3B30') },
      hovertemplate: '<b>%{y}</b><br>Var: %{x:.4f}%<extra></extra>',
    }], {
      ...PL, margin: { t: 5, b: 25, l: 100, r: 15 },
      xaxis: { ...PL.xaxis, title: { text: 'Variación %', font: { size: 9 } } },
    }, { responsive: true, displayModeBar: false });
  }
}

function renderTablaAlertas(alertas) {
  const wrap = document.getElementById('wrap-alertas');
  // Filtros
  const busq = (document.getElementById('fil-alerta-busq')?.value || '').toUpperCase();
  const sev  = document.getElementById('fil-alerta-sev')?.value || '';
  const prov = document.getElementById('fil-alerta-prov')?.value || '';

  let rows = alertas;
  if (busq) rows = rows.filter(r => (r.ISIN + r.NEMOTECNICO + r.TITULO).toUpperCase().includes(busq));
  if (sev)  rows = rows.filter(r => r.SEVERIDAD === sev);
  if (prov) rows = rows.filter(r => r.PROVEEDOR === prov);

  document.getElementById('cnt-alertas').textContent = rows.length;

  if (!rows.length) { wrap.innerHTML = '<div class="sect-empty">Sin alertas para los filtros aplicados</div>'; return; }

  const COLS = ['PROVEEDOR','ISIN','NEMOTECNICO','TITULO','PRECIO_ANT','PRECIO_HOY','VAR_ABS','VAR_PCT','SEVERIDAD'];
  const avail = COLS.filter(c => rows[0].hasOwnProperty(c));

  let html = `<table><thead><tr>
    ${avail.map(c => `<th>${c}</th>`).join('')}
    <th>HISTÓRICO</th>
  </tr></thead><tbody>`;

  for (const r of rows) {
    const rowCls = r.SEVERIDAD === 'CRITICA' ? 'row-alert' : r.SEVERIDAD === 'ALTA' ? 'row-warn' : '';
    html += `<tr class="${rowCls}">`;
    for (const c of avail) {
      const v = r[c];
      if (v == null) { html += '<td>—</td>'; continue; }
      if (c === 'SEVERIDAD') {
        const cls = { CRITICA: 'sev-critica', ALTA: 'sev-alta', MEDIA: 'sev-media', BAJA: 'sev-baja' }[v] || '';
        html += `<td><span class="sev-badge ${cls}">${v}</span></td>`;
      } else if (c === 'VAR_PCT') {
        const vp = typeof v === 'number' ? v : parseFloat(v);
        const cls = vp > 0 ? 'vp-up' : vp < 0 ? 'vp-dn' : 'vp-zero';
        html += `<td><span class="vp ${cls}">${vp > 0 ? '▲' : vp < 0 ? '▼' : ''}${Math.abs(vp).toFixed(4)}%</span></td>`;
      } else if (c === 'VAR_ABS') {
        html += `<td class="${nc(v)}">${fmtNum(v, 4)}</td>`;
      } else if (['PRECIO_ANT','PRECIO_HOY'].includes(c)) {
        html += `<td>${typeof v === 'number' ? v.toFixed(6) : v}</td>`;
      } else {
        html += `<td>${escHtml(v)}</td>`;
      }
    }
    // Botón histórico
    const isin = r.ISIN || '';
    const prov = r.PROVEEDOR || '';
    html += `<td><button class="btn btn-ghost btn-sm" onclick="abrirHist('${escHtml(isin)}','${escHtml(prov)}')" title="Ver histórico">📈</button></td>`;
    html += '</tr>';
  }
  html += '</tbody></table>';
  wrap.innerHTML = `<div class="twrap">${html}</div>`;
}

// Re-renderizar con filtros
function filtrarAlertas() {
  if (!State.alertas) return;
  renderTablaAlertas(State.alertas.alertas || []);
}

/* ═══════════════════════════════════════════════════════
   TAB: ALERTAS MULTI-DÍA
═══════════════════════════════════════════════════════ */
async function cargarMultidia() {
  const fecha   = State.fecha;
  const maxDias = parseInt(document.getElementById('sel-max-dias')?.value || '5');
  const wrap    = document.getElementById('wrap-multidia');

  wrap.innerHTML = '<div class="loading"><span class="spin"></span> Comparando fechas anteriores…</div>';

  try {
    const data = await apiFetch(`/api/insumos/alertas_multidia/${fecha}?max_dias=${maxDias}`);
    State.alertasMulti = data;

    const fechas   = data.fechas_comparadas || [];
    const resumen  = data.resumen_por_fecha || {};
    const alertas  = data.alertas_persistentes || data.alertas || [];

    // Mini tarjetas por fecha
    const grid = document.getElementById('multiday-cards');
    if (grid) {
      grid.innerHTML = fechas.map(f => {
        const cnt   = resumen[f]?.total || 0;
        const crit  = resumen[f]?.criticas || 0;
        const cls   = crit > 0 ? 'crit' : cnt > 0 ? 'warn' : 'ok';
        const df    = `${f.slice(6)}.${f.slice(4,6)}.${f.slice(0,4)}`;
        return `<div class="md-card">
          <div class="md-card-fecha">${df}</div>
          <div class="md-card-count ${cls}">${cnt}</div>
          <div style="font-size:.6rem;color:var(--muted)">${crit} críticas</div>
        </div>`;
      }).join('');
    }

    if (!alertas.length) {
      wrap.innerHTML = '<div class="sect-empty">✅ Sin alertas persistentes en el período.</div>';
      return;
    }

    // Tabla
    const COLS = ['PROVEEDOR','ISIN','NEMOTECNICO','TITULO','DIAS_CON_ALERTA','VAR_PCT_MAX','SEVERIDAD_MAX'];
    const avail = COLS.filter(c => alertas[0].hasOwnProperty(c));
    let html = `<table><thead><tr>${avail.map(c => `<th>${c.replace(/_/g,' ')}</th>`).join('')}<th>HISTÓRICO</th></tr></thead><tbody>`;

    for (const r of alertas) {
      const rowCls = (r.SEVERIDAD_MAX === 'CRITICA') ? 'row-alert' : (r.DIAS_CON_ALERTA >= 3) ? 'row-warn' : '';
      html += `<tr class="${rowCls}">`;
      for (const c of avail) {
        const v = r[c];
        if (v == null) { html += '<td>—</td>'; continue; }
        if (c === 'SEVERIDAD_MAX') {
          const cls = { CRITICA:'sev-critica', ALTA:'sev-alta', MEDIA:'sev-media', BAJA:'sev-baja' }[v] || '';
          html += `<td><span class="sev-badge ${cls}">${v}</span></td>`;
        } else if (c === 'VAR_PCT_MAX') {
          html += `<td><span class="vp ${v > 0 ? 'vp-up' : 'vp-dn'}">${Math.abs(v).toFixed(4)}%</span></td>`;
        } else if (c === 'DIAS_CON_ALERTA') {
          html += `<td><strong style="color:${v >= 3 ? 'var(--sk-red)' : 'var(--sk-orange)'}">${v}d</strong></td>`;
        } else {
          html += `<td>${escHtml(v)}</td>`;
        }
      }
      const isin = r.ISIN || '';
      const prov = r.PROVEEDOR || '';
      html += `<td><button class="btn btn-ghost btn-sm" onclick="abrirHist('${escHtml(isin)}','${escHtml(prov)}')">📈</button></td></tr>`;
    }
    html += '</tbody></table>';
    wrap.innerHTML = `<div class="twrap">${html}</div>`;
  } catch (e) {
    wrap.innerHTML = `<div class="sect-empty" style="color:var(--sk-red)">Error: ${escHtml(e.message)}</div>`;
  }
}

/* ═══════════════════════════════════════════════════════
   TAB: CURVAS RENTA FIJA (SP)
═══════════════════════════════════════════════════════ */
async function cargarCurvas() {
  const fecha   = State.fecha;
  const tipo    = document.getElementById('sel-tipo-tasa')?.value || '';
  const chartEl = document.getElementById('chart-curvas');

  if (chartEl) chartEl.innerHTML = '<div class="loading"><span class="spin"></span> Cargando curvas…</div>';

  try {
    const qs   = tipo ? `?tipo_tasa=${encodeURIComponent(tipo)}` : '';
    const data = await apiFetch(`/api/insumos/sp_curvas/${fecha}${qs}`);
    State.spData = data;
    renderCurvas(data);
  } catch (e) {
    if (chartEl) chartEl.innerHTML = `<div class="sect-empty" style="color:var(--sk-red)">Error: ${escHtml(e.message)}</div>`;
  }
}

function renderCurvas(data) {
  data = data || State.spData;
  if (!data) return;
  const PL     = getPL({ margin: { t: 20, b: 45, l: 55, r: 20 } });
  const series = data.series || [];
  const chartEl = document.getElementById('chart-curvas');
  if (!chartEl || typeof Plotly === 'undefined') return;

  if (!series.length) {
    chartEl.innerHTML = '<div class="sect-empty">Sin datos SP para esta fecha. Verifica que los archivos estén convertidos.</div>';
    return;
  }

  const COLORES = ['#00A65A','#0A84FF','#FF9500','#FF3B30','#BF5AF2','#FFD60A','#00C96E'];
  const traces  = series.map((s, i) => ({
    type: 'scatter', mode: 'markers',
    name: s.tipo_tasa || `Serie ${i + 1}`,
    x: s.plazo, y: s.tir,
    text: s.isin || [],
    marker: { color: COLORES[i % COLORES.length], size: 6, opacity: .8 },
    hovertemplate: '<b>%{text}</b><br>Plazo: %{x:.0f}d<br>TIR: %{y:.4f}%<extra></extra>',
    customdata: (s.isin || []).map((isin, j) => ({ isin, prov: 'SP' })),
  }));

  Plotly.newPlot(chartEl, traces, {
    ...PL,
    xaxis: { ...PL.xaxis, title: { text: 'Plazo (días)', font: { size: 10 } } },
    yaxis: { ...PL.yaxis, title: { text: 'TIR (%)', font: { size: 10 } } },
    showlegend: true,
  }, { responsive: true, displayModeBar: false });

  // Clic en punto → abrir histórico
  chartEl.on('plotly_click', ev => {
    const pt = ev.points?.[0];
    if (!pt) return;
    const cd = pt.customdata;
    if (cd?.isin) abrirHist(cd.isin, cd.prov);
  });

  // Leyenda de tipos de tasa
  const leyenda = document.getElementById('curvas-leyenda');
  if (leyenda) {
    leyenda.innerHTML = series.map((s, i) => `
      <div class="curva-legend-item">
        <div class="curva-legend-dot" style="background:${COLORES[i % COLORES.length]}"></div>
        <span>${s.tipo_tasa || 'Tipo ' + (i+1)}</span>
        <span style="color:var(--muted)">(${(s.isin || []).length})</span>
      </div>
    `).join('');
  }

  // Estadísticas resumen
  const total = series.reduce((s, serie) => s + (serie.isin || []).length, 0);
  const statsEl = document.getElementById('curvas-stats');
  if (statsEl) statsEl.textContent = `${total} títulos en ${series.length} tipo${series.length !== 1 ? 's' : ''} de tasa`;
}

/* ═══════════════════════════════════════════════════════
   TABS: TABLAS DE PROVEEDORES (SP, SW, SV, MX, NOTAS)
═══════════════════════════════════════════════════════ */
async function cargarTabla(prov) {
  const fecha = State.fecha;
  const wrapId = `wrap-${prov.toLowerCase()}`;
  const wrap   = document.getElementById(wrapId);
  if (!wrap) return;

  wrap.innerHTML = '<div class="loading"><span class="spin"></span> Cargando datos…</div>';

  try {
    const busq = (document.getElementById(`fil-${prov.toLowerCase()}-busq`)?.value || '').trim();
    const qs   = busq ? `?busqueda=${encodeURIComponent(busq)}&limit=500` : '?limit=500';
    const data = await apiFetch(`/api/insumos/datos/${fecha}/${prov}${qs}`);
    const rows = Array.isArray(data) ? data : (data.datos || data.rows || []);

    State.tablaData[prov] = rows;

    if (!rows.length) {
      wrap.innerHTML = '<div class="sect-empty">Sin datos para esta fecha/proveedor.</div>';
      return;
    }

    const cols   = Object.keys(rows[0]).filter(c => c !== '_idx');
    const numSet = new Set(['PRECIO','TIR','PLAZO','DURACION','NOMINAL','VLR_MERCADO','PRECIO_ANT','VAR_ABS','VAR_PCT']);

    let html = `<div class="twrap"><table><thead><tr>
      ${cols.map(c => `<th>${c}</th>`).join('')}
      <th>HIST.</th>
    </tr></thead><tbody>`;

    for (const r of rows) {
      html += '<tr>';
      for (const c of cols) {
        const v = r[c];
        if (v == null) { html += '<td>—</td>'; continue; }
        if (numSet.has(c) && typeof v === 'number') {
          const dec = ['TIR','PRECIO','VAR_PCT'].includes(c) ? 6 : 2;
          html += `<td class="${nc(v)}">${v.toFixed(dec)}</td>`;
        } else {
          html += `<td>${escHtml(v)}</td>`;
        }
      }
      const isin = r.ISIN || r.NEMOTECNICO || '';
      html += `<td><button class="btn btn-ghost btn-sm" onclick="abrirHist('${escHtml(isin)}','${prov}')" title="Histórico">📈</button></td>`;
      html += '</tr>';
    }

    html += `</tbody></table></div>`;
    html += `<div style="font-size:.65rem;color:var(--muted);margin-top:5px">${rows.length} registros</div>`;
    wrap.innerHTML = html;
  } catch (e) {
    wrap.innerHTML = `<div class="sect-empty" style="color:var(--sk-red)">Error cargando ${prov}: ${escHtml(e.message)}</div>`;
  }
}

function filtrarTabla(prov) {
  // Forzar re-carga con el nuevo filtro
  State.tabsLoaded.delete(prov.toLowerCase());
  cargarTabla(prov);
}

/* ═══════════════════════════════════════════════════════
   PANEL HISTÓRICO (slide-in derecha)
═══════════════════════════════════════════════════════ */
async function abrirHist(isin, prov) {
  if (!isin) return;
  State.histIsin = isin;
  State.histProv = prov;

  const panel = document.getElementById('hist-panel');
  const title = document.getElementById('hist-title');
  const body  = document.getElementById('hist-body');

  if (title) title.textContent = `${isin} — ${prov}`;
  if (body)  body.innerHTML = '<div class="loading"><span class="spin"></span> Cargando histórico…</div>';
  if (panel) panel.classList.add('open');

  try {
    const data = await apiFetch(`/api/insumos/historico/${encodeURIComponent(isin)}?proveedor=${prov}&max_fechas=30`);
    renderHistPanel(data, isin, prov);
  } catch (e) {
    if (body) body.innerHTML = `<div class="sect-empty" style="color:var(--sk-red)">Error: ${escHtml(e.message)}</div>`;
  }
}

function closeHistPanel() {
  const panel = document.getElementById('hist-panel');
  if (panel) panel.classList.remove('open');
}

function renderHistPanel(data, isin, prov) {
  const body   = document.getElementById('hist-body');
  const puntos = data.puntos || data.historico || [];

  if (!puntos.length) {
    body.innerHTML = '<div class="sect-empty">Sin datos históricos.</div>';
    return;
  }

  const fechas  = puntos.map(p => p.FECHA || p.fecha);
  const precios = puntos.map(p => p.PRECIO || p.precio);
  const tires   = puntos.map(p => p.TIR    || p.tir);

  const PL = getPL({ margin: { t: 10, b: 30, l: 50, r: 15 } });

  // Gráfica precio
  const chartDiv = document.createElement('div');
  chartDiv.style.cssText = 'width:100%;height:180px;margin-bottom:10px;';
  body.innerHTML = '';
  body.appendChild(chartDiv);

  const traces = [{
    type: 'scatter', mode: 'lines+markers', name: 'Precio',
    x: fechas, y: precios,
    line: { color: '#00A65A', width: 2 },
    marker: { size: 4 },
  }];
  if (tires.some(t => t != null)) {
    traces.push({
      type: 'scatter', mode: 'lines+markers', name: 'TIR',
      x: fechas, y: tires,
      yaxis: 'y2', line: { color: '#0A84FF', width: 1.5, dash: 'dot' },
      marker: { size: 3 },
    });
  }

  if (typeof Plotly !== 'undefined') {
    Plotly.newPlot(chartDiv, traces, {
      ...PL, showlegend: true,
      yaxis2: { overlaying: 'y', side: 'right', gridcolor: 'transparent', tickfont: { size: 8 } },
    }, { responsive: true, displayModeBar: false });
  }

  // Mini tabla
  const tablaDiv = document.createElement('div');
  tablaDiv.className = 'twrap';
  tablaDiv.style.maxHeight = '220px';
  let th = '<tr><th>FECHA</th><th>PRECIO</th>' + (tires.some(t=>t!=null) ? '<th>TIR</th>' : '') + '</tr>';
  let rows = puntos.slice().reverse().map(p => {
    const precio = p.PRECIO ?? p.precio;
    const tir    = p.TIR    ?? p.tir;
    return `<tr>
      <td>${p.FECHA || p.fecha}</td>
      <td>${precio != null ? precio.toFixed(6) : '—'}</td>
      ${tires.some(t=>t!=null) ? `<td>${tir != null ? tir.toFixed(6) : '—'}</td>` : ''}
    </tr>`;
  }).join('');
  tablaDiv.innerHTML = `<table><thead>${th}</thead><tbody>${rows}</tbody></table>`;
  body.appendChild(tablaDiv);
}

/* ═══════════════════════════════════════════════════════
   TAB: CONVERSOR
═══════════════════════════════════════════════════════ */
function initConversor() {
  // Solo inicializa la UI, no hace nada hasta que el usuario presiona
}

async function convertirArchivos() {
  const fecha  = State.fecha;
  const btn    = document.getElementById('btn-convertir');
  const status = document.getElementById('conv-status-msg');
  const result = document.getElementById('conv-result');

  if (btn) btn.disabled = true;
  if (status) status.innerHTML = '<span class="spin"></span> Convirtiendo archivos…';

  try {
    const data = await apiFetch(`/api/insumos/convertir/${fecha}`, { method: 'POST' });
    const resumen = data.resumen || {};
    if (status) status.innerHTML = `✅ Conversión completada`;
    if (result) {
      result.innerHTML = Object.entries(resumen).map(([k, v]) =>
        `<div><strong>${k}:</strong> ${v.ok ? `✓ ${v.filas} filas` : `✗ ${v.error || 'error'}`}</div>`
      ).join('');
    }
    // Recargar fechas por si apareció una nueva
    cargarFechas();
  } catch (e) {
    if (status) status.innerHTML = `<span style="color:var(--sk-red)">❌ Error: ${escHtml(e.message)}</span>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

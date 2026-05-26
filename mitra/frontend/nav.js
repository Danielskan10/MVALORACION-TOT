/**
 * MVALORACION — Shared Navigation & Theme
 * Incluir ANTES del cierre de </body> en cada módulo.
 * Uso: <script src="/static/shared/nav.js"></script>
 *
 * Espera que el HTML tenga:
 *   data-module="insumos|porfin|mitra|dashboard"  en <html>
 *   id="themeBtn"   → botón de toggle tema
 *   id="navDot"     → punto de estado API
 *   id="navStatusTxt" → texto de estado
 */

/* ── THEME ─────────────────────────────────────────────────────── */
function _themeBtn() {
  return document.getElementById('themeBtn') || document.getElementById('btn-theme');
}

(function initTheme() {
  const saved = localStorage.getItem('sk-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  document.addEventListener('DOMContentLoaded', () => {
    const btn = _themeBtn();
    if (btn) btn.textContent = saved === 'dark' ? 'Moon' : 'Sun';
  });
})();

function toggleTheme() {
  const curr = document.documentElement.getAttribute('data-theme');
  const next = curr === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('sk-theme', next);
  const btn = _themeBtn();
  if (btn) btn.textContent = next === 'dark' ? 'Moon' : 'Sun';
  document.dispatchEvent(new CustomEvent('sk-theme-change', { detail: { theme: next } }));
}

/* ── API STATUS ────────────────────────────────────────────────── */
async function checkApiStatus() {
  const dot = document.getElementById('navDot');
  const txt = document.getElementById('navStatusTxt');
  try {
    const r = await fetch('/api/config');
    if (r.ok) {
      if (dot) dot.className = 'nav-status-dot ok';
      if (txt) txt.textContent = 'Conectado';
    } else throw new Error();
  } catch {
    if (dot) dot.className = 'nav-status-dot err';
    if (txt) txt.textContent = 'Sin conexión';
  }
}

/* ── UTILS GLOBALES ────────────────────────────────────────────── */
/** Formatea número con separador de miles colombiano */
function fmtNum(n, decimals = 0) {
  if (n == null || isNaN(n)) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e12) return (n / 1e12).toFixed(1) + ' T';
  if (abs >= 1e9)  return (n / 1e9).toFixed(1) + ' MM';
  if (abs >= 1e6)  return (n / 1e6).toFixed(1) + ' M';
  return Number(n).toLocaleString('es-CO', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Escapa HTML para insertar en innerHTML */
function escHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/** Fetch JSON con error handling */
async function apiFetch(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    const body = await r.text().catch(() => '');
    throw new Error(`HTTP ${r.status}: ${body.slice(0, 120)}`);
  }
  return r.json();
}

/** Debounce */
function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

/** Clase CSS para número positivo/negativo */
function nc(n) { return n == null ? '' : n >= 0 ? 'n-pos' : 'n-neg'; }

/* ── PLOTLY LAYOUT FACTORY ─────────────────────────────────────── */
function getPL(overrides = {}) {
  const dark = document.documentElement.getAttribute('data-theme') !== 'light';
  const txt  = dark ? '#8E8E93' : '#6C6C70';
  const grid = dark ? '#252525' : '#E5E5EA';
  const base = {
    paper_bgcolor: 'transparent',
    plot_bgcolor:  'transparent',
    font: { color: txt, size: 10, family: 'Inter, system-ui, sans-serif' },
    margin: { t: 10, b: 35, l: 50, r: 15 },
    legend: { bgcolor: 'transparent', font: { size: 9 } },
    xaxis: { gridcolor: grid, zerolinecolor: grid, tickfont: { size: 9 } },
    yaxis: { gridcolor: grid, zerolinecolor: grid, tickfont: { size: 9 } },
    colorway: ['#00A65A','#0A84FF','#FF9500','#FF3B30','#BF5AF2','#FFD60A','#00C96E','#FF6B6B'],
  };
  return { ...base, ...overrides };
}

/* ── BOOT ──────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  checkApiStatus();
});

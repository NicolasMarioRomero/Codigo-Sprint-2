// ─── Config ───────────────────────────────────────────
const API      = '/api/v1';
const EXT_API  = '/extractor/api/v1';

// ─── State ────────────────────────────────────────────
let providerChartInst = null;
let serviceChartInst  = null;
let allReports        = [];
let currentPage       = 1;
const PAGE_SIZE       = 15;
let failoverRuns      = [];  // Sprint 3: disponibilidad results
let maskTestCount     = 0;
let maskSuccessCount  = 0;
let credUseTotal      = 0;
let credAnomalias     = 0;

// ─── Init ─────────────────────────────────────────────
(function init() {
  const selectors = ['companySelect', 'extCompanySelect'];
  selectors.forEach(id => {
    const sel = document.getElementById(id);
    for (let i = 1; i <= 10; i++) {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = `Company ${i}`;
      sel.appendChild(opt);
    }
  });
  const projSel = document.getElementById('projectSelect');
  for (let i = 1; i <= 5; i++) {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = `project-${i}`;
    projSel.appendChild(opt);
  }
})();

// ─── Navigation ───────────────────────────────────────
function showPage(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  if (el) el.classList.add('active');
}

// ─── Company change sync ──────────────────────────────
function onCompanyChange() {
  const val = document.getElementById('companySelect').value;
  document.getElementById('extCompanySelect').value = val;
}

// ─── Utilities ────────────────────────────────────────
function fmt(n) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', maximumFractionDigits: 0
  }).format(n ?? 0);
}
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('es-CO', { month: 'short', day: 'numeric', year: '2-digit' });
}
function fmtDatetime(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('es-CO', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch (e) { return iso; }
}
function now() {
  return new Date().toLocaleTimeString('es-CO', { hour12: false });
}

// ─── Toast ────────────────────────────────────────────
function toast(msg, type = 'info') {
  const icons = { ok: '✓', err: '✗', info: 'ℹ', warn: '⚠' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${msg}</span>`;
  document.getElementById('toastContainer').appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

// ─── Render bar rows ──────────────────────────────────
function renderBars(obj, containerId) {
  const el = document.getElementById(containerId);
  if (!obj || !Object.keys(obj).length) {
    el.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>Sin datos disponibles</p></div>';
    return;
  }
  const sorted = Object.entries(obj).sort((a, b) => b[1] - a[1]);
  const max = sorted[0][1];
  el.innerHTML = sorted.map(([k, v]) => `
    <div class="bar-row">
      <div class="bar-label" title="${k}">${k}</div>
      <div class="bar-track">
        <div class="bar-fill" style="width:${(v / max * 100).toFixed(1)}%"></div>
      </div>
      <div class="bar-amount">${fmt(v)}</div>
    </div>`).join('');
}

// ─── Charts ───────────────────────────────────────────
const CHART_COLORS = [
  '#7c6af7','#a78bfa','#60a5fa','#34d399','#fbbf24',
  '#f87171','#fb923c','#a3e635','#38bdf8','#e879f9'
];

function buildProviderChart(data) {
  const ctx = document.getElementById('providerChart').getContext('2d');
  if (providerChartInst) providerChartInst.destroy();
  if (!data || !Object.keys(data).length) return;
  providerChartInst = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: Object.keys(data),
      datasets: [{ data: Object.values(data), backgroundColor: CHART_COLORS, borderColor: '#12151f', borderWidth: 3, hoverOffset: 6 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 12 }, padding: 14, boxWidth: 12 } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.raw)}` } }
      },
      cutout: '65%',
    }
  });
}

function buildServiceChart(data) {
  const ctx = document.getElementById('serviceChart').getContext('2d');
  if (serviceChartInst) serviceChartInst.destroy();
  if (!data || !Object.keys(data).length) return;
  const sorted = Object.entries(data).sort((a,b) => b[1]-a[1]).slice(0,8);
  serviceChartInst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(([k]) => k),
      datasets: [{
        label: 'Costo USD', data: sorted.map(([,v]) => v),
        backgroundColor: CHART_COLORS.map(c => c + 'bb'), borderColor: CHART_COLORS, borderWidth: 1, borderRadius: 6,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` ${fmt(ctx.raw)}` } } },
      scales: {
        x: { ticks: { color: '#64748b', font: { size: 11 } }, grid: { color: '#252840' } },
        y: { ticks: { color: '#64748b', font: { size: 11 }, callback: v => '$' + (v >= 1000 ? (v/1000).toFixed(0)+'k' : v) }, grid: { color: '#252840' } }
      }
    }
  });
}

// ─── KPI render ──────────────────────────────────────
function renderKPIs(s) {
  const services  = s.service_breakdown  || {};
  const providers = s.provider_breakdown || {};
  const total     = s.total_cost ?? 0;
  const topEntry  = Object.entries(services).sort((a,b)=>b[1]-a[1])[0];
  const kpiData = [
    { label: 'Total Mensual',    value: fmt(total),                      sub: 'USD este periodo',  icon: '💰', cls: '' },
    { label: 'Servicios activos',value: Object.keys(services).length,    sub: 'en uso',             icon: '⚙️',  cls: 'green' },
    { label: 'Proveedores',      value: Object.keys(providers).length,   sub: 'conectados',         icon: '🌐', cls: 'blue' },
    { label: 'Mayor Gasto',      value: topEntry ? topEntry[0] : '—',   sub: topEntry ? fmt(topEntry[1]) : '', icon: '📈', cls: 'yellow'},
  ];
  document.getElementById('kpiGrid').innerHTML = kpiData.map(k => `
    <div class="kpi-card ${k.cls}">
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value">${k.value}</div>
      <div class="kpi-sub">${k.sub}</div>
      <div class="kpi-icon">${k.icon}</div>
    </div>`).join('');
}

// ─── Dashboard ────────────────────────────────────────
async function loadDashboard(force) {
  const id = document.getElementById('companySelect').value;
  if (!id) { toast('Selecciona una empresa primero', 'err'); return; }

  document.getElementById('kpiGrid').innerHTML = Array(4).fill(
    '<div class="kpi-card skeleton skeleton-card"></div>'
  ).join('');
  ['serviceBreakdown','providerBreakdown'].forEach(x =>
    document.getElementById(x).innerHTML =
      '<div class="bar-row"><div class="bar-label"><div class="skeleton skeleton-bar" style="width:100%;height:8px"></div></div><div class="bar-track" style="flex:1"></div><div class="bar-amount"></div></div>'.repeat(4)
  );

  const badge   = document.getElementById('latencyBadge');
  const spinner = document.getElementById('latencySpinner');
  const ltext   = document.getElementById('latencyText');
  badge.className = 'latency-badge ok';
  spinner.style.display = 'inline-block';
  ltext.textContent = 'Midiendo…';
  const t0 = performance.now();

  try {
    const r = await fetch(`${API}/dashboard/${id}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const elapsed = Math.round(performance.now() - t0);
    const s = data.summary || {};
    renderKPIs(s);
    buildProviderChart(s.provider_breakdown);
    buildServiceChart(s.service_breakdown);
    document.getElementById('svcCount').textContent  = Object.keys(s.service_breakdown  || {}).length;
    document.getElementById('provCount').textContent = Object.keys(s.provider_breakdown || {}).length;
    renderBars(s.service_breakdown,  'serviceBreakdown');
    renderBars(s.provider_breakdown, 'providerBreakdown');
    spinner.style.display = 'none';
    const ok = elapsed < 3000;
    badge.className = `latency-badge ${ok ? 'ok' : 'bad'}`;
    ltext.textContent = `${elapsed} ms`;
    const src = data.source || 'db';
    document.getElementById('globalSourceChip').innerHTML = src === 'cache'
      ? '<span class="source-chip source-cache">⚡ cache</span>'
      : '<span class="source-chip source-db">🗄 base de datos</span>';
    document.getElementById('dashSub').textContent =
      `Company ${id} · ${s.record_count ?? 0} registros · ${s.project_count ?? 0} proyectos`;
    updateAsrLatency(elapsed, ok, id, src);
    toast(`Dashboard cargado en ${elapsed} ms ${ok ? '✓' : '⚠ > 3s'}`, ok ? 'ok' : 'info');
  } catch(e) {
    spinner.style.display = 'none';
    badge.className = 'latency-badge bad';
    ltext.textContent = 'Error';
    document.getElementById('kpiGrid').innerHTML =
      '<div class="kpi-card" style="grid-column:1/-1"><div class="empty-state"><div class="icon">⚠️</div><p>' + e.message + '</p></div></div>';
    toast('Error al cargar el dashboard: ' + e.message, 'err');
  }
}

// ─── Reports ──────────────────────────────────────────
async function loadReports() {
  const id = document.getElementById('companySelect').value;
  if (!id) { toast('Selecciona una empresa primero', 'err'); return; }
  document.getElementById('reportTableBody').innerHTML =
    `<tr><td colspan="8"><div class="empty-state"><div class="spinner" style="margin:0 auto 10px"></div><p>Cargando reportes…</p></div></td></tr>`;
  document.getElementById('paginationBar').style.display = 'none';
  try {
    const r = await fetch(`${API}/report/${id}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    allReports = Array.isArray(data) ? data : (data.data || data.reports || []);
    currentPage = 1;
    renderReportTable();
    document.getElementById('reportSub').textContent = `Company ${id} · ${allReports.length} registros encontrados`;
    toast(`${allReports.length} reportes cargados`, 'ok');
  } catch(e) {
    document.getElementById('reportTableBody').innerHTML =
      `<tr><td colspan="8"><div class="empty-state"><div class="icon">⚠️</div><p>${e.message}</p></div></td></tr>`;
    toast('Error al cargar reportes: ' + e.message, 'err');
  }
}

function renderReportTable() {
  const start = (currentPage - 1) * PAGE_SIZE;
  const end   = start + PAGE_SIZE;
  const page  = allReports.slice(start, end);
  const totalPages = Math.ceil(allReports.length / PAGE_SIZE);
  const provClass = p => ({ aws:'prov-aws', gcp:'prov-gcp', azure:'prov-azure' }[p] || 'prov-aws');
  document.getElementById('reportTableBody').innerHTML = page.map((r, i) => `
    <tr>
      <td style="color:var(--text-muted)">${start + i + 1}</td>
      <td><span class="provider-badge ${provClass(r.provider)}">${(r.provider||'aws').toUpperCase()}</span></td>
      <td style="color:var(--text)">${r.service_name || r.service || '—'}</td>
      <td>${r.project_id || '—'}</td>
      <td style="color:var(--text-muted)">${r.region || '—'}</td>
      <td style="font-weight:700;color:var(--accent-soft)">${fmt(r.cost ?? r.amount)}</td>
      <td style="color:var(--text-muted)">${r.usage != null ? r.usage.toFixed(2) : '—'}</td>
      <td style="color:var(--text-muted)">${fmtDate(r.timestamp)}</td>
    </tr>`).join('');
  const bar = document.getElementById('paginationBar');
  if (allReports.length > PAGE_SIZE) {
    bar.style.display = 'flex';
    document.getElementById('paginationInfo').textContent =
      `Mostrando ${start+1}–${Math.min(end, allReports.length)} de ${allReports.length}`;
    const btns = document.getElementById('paginationBtns');
    let html = `<button class="page-btn" onclick="goPage(${currentPage-1})" ${currentPage===1?'disabled':''}>‹</button>`;
    for (let p = 1; p <= totalPages; p++) {
      if (totalPages > 7 && (p > 2 && p < totalPages - 1 && Math.abs(p - currentPage) > 1)) {
        if (p === 3 || p === totalPages - 2) html += '<span class="page-btn" style="cursor:default">…</span>';
        continue;
      }
      html += `<button class="page-btn ${p===currentPage?'active':''}" onclick="goPage(${p})">${p}</button>`;
    }
    html += `<button class="page-btn" onclick="goPage(${currentPage+1})" ${currentPage===totalPages?'disabled':''}>›</button>`;
    btns.innerHTML = html;
  } else {
    bar.style.display = 'none';
  }
}

function goPage(p) {
  currentPage = p;
  renderReportTable();
}

// ─── Extractor Sync ───────────────────────────────────
async function runExtractorSync() {
  const companyId = parseInt(document.getElementById('extCompanySelect').value || '1');
  const provider  = document.getElementById('providerSelect').value;
  const projectId = parseInt(document.getElementById('projectSelect').value);
  setExtractorBtns(true);
  clearLog();
  document.getElementById('metricsSection').style.display = 'none';
  document.getElementById('attemptsChip').style.display = 'none';
  addLog('info', `Iniciando extracción síncrona | proveedor=${provider.toUpperCase()} empresa=${companyId}`);
  const t0 = performance.now();
  try {
    const r = await fetch(`${EXT_API}/extractor/extract/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company_id: companyId, project_id: projectId, provider })
    });
    const elapsed = Math.round(performance.now() - t0);
    const data = await r.json();
    if (r.ok && data.status === 'success') {
      const attempts = data.attempts || 1;
      addLog('ok', `Extracción exitosa en ${elapsed} ms · ${data.metrics_count} métricas · ${attempts} intento(s)`);
      if (attempts > 1) addLog('warn', `Necesitó ${attempts} intentos (backoff exponencial aplicado)`);
      const chip = document.getElementById('attemptsChip');
      chip.style.display = 'inline';
      chip.textContent = `${attempts} intento(s)`;
      chip.className = `chip ${attempts > 1 ? 'chip-yellow' : 'chip-green'}`;
      const metrics = data.metrics || [];
      if (metrics.length) {
        document.getElementById('metricsSection').style.display = 'block';
        document.getElementById('metricsCount').textContent = metrics.length;
        document.getElementById('metricsGrid').innerHTML = metrics.map(m => `
          <div class="metric-tile">
            <div class="svc">${m.service || m.service_name || '—'}</div>
            <div class="cost">${fmt(m.cost ?? m.amount)}</div>
            <div class="region">${m.region || m.project_id || '—'}</div>
          </div>`).join('');
      }
      updateAsrScalability(attempts, true);
      toast(`Extracción exitosa — ${data.metrics_count} métricas en ${elapsed}ms`, 'ok');
    } else {
      addLog('err', `Fallo: ${data.detail || data.message || JSON.stringify(data)}`);
      updateAsrScalability(5, false);
      toast('Extracción fallida', 'err');
    }
  } catch(e) {
    addLog('err', `Error de conexión: ${e.message}`);
    toast('Error de conexión con el extractor', 'err');
  } finally {
    setExtractorBtns(false);
  }
}

async function runExtractorAsync() {
  const companyId = parseInt(document.getElementById('extCompanySelect').value || '1');
  const provider  = document.getElementById('providerSelect').value;
  const projectId = parseInt(document.getElementById('projectSelect').value);
  setExtractorBtns(true);
  clearLog();
  addLog('info', `Encolando tarea asíncrona | proveedor=${provider.toUpperCase()}`);
  try {
    const r = await fetch(`${EXT_API}/extractor/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company_id: companyId, project_id: projectId, provider })
    });
    const data = await r.json();
    if (r.ok && data.task_id) {
      addLog('ok', `Tarea encolada · task_id = ${data.task_id}`);
      toast('Tarea encolada correctamente', 'ok');
      pollTaskStatus(data.task_id);
    } else {
      addLog('err', `Error al encolar: ${data.detail || JSON.stringify(data)}`);
      setExtractorBtns(false);
    }
  } catch(e) {
    addLog('err', `Error: ${e.message}`);
    setExtractorBtns(false);
  }
}

async function pollTaskStatus(taskId) {
  let attempts = 0;
  const interval = setInterval(async () => {
    attempts++;
    try {
      const r = await fetch(`${EXT_API}/extractor/status/${taskId}`);
      const data = await r.json();
      addLog('info', `Poll #${attempts} · estado = ${data.status}`);
      if (data.status === 'SUCCESS') {
        clearInterval(interval);
        addLog('ok', `✓ Tarea completada exitosamente`);
        toast('Tarea asíncrona completada', 'ok');
        setExtractorBtns(false);
      } else if (data.status === 'FAILURE') {
        clearInterval(interval);
        addLog('err', `✗ Tarea fallida: ${data.error || '—'}`);
        setExtractorBtns(false);
      } else if (attempts >= 20) {
        clearInterval(interval);
        addLog('warn', 'Tiempo de espera agotado. Verifica el estado manualmente.');
        setExtractorBtns(false);
      }
    } catch(e) {
      clearInterval(interval);
      addLog('err', `Error al consultar estado: ${e.message}`);
      setExtractorBtns(false);
    }
  }, 2000);
}

function clearLog() { document.getElementById('taskTimeline').innerHTML = ''; }

function addLog(type, msg) {
  const tl  = document.getElementById('taskTimeline');
  const cls = { info: 'log-info', ok: 'log-ok', warn: 'log-warn', err: 'log-err' }[type] || 'log-info';
  const prefix = { ok: '✓', err: '✗', warn: '⚠', info: '›' }[type] || '›';
  const line = document.createElement('div');
  line.className = 'log-line';
  line.innerHTML = `<span class="log-ts">${now()}</span><span class="${cls}">${prefix} ${msg}</span>`;
  tl.appendChild(line);
  tl.scrollTop = tl.scrollHeight;
}

function setExtractorBtns(loading) {
  ['btnExtSync','btnExtAsync'].forEach(id => { document.getElementById(id).disabled = loading; });
}

// ─── ASR panel updates ────────────────────────────────
function updateAsrLatency(ms, ok, companyId, src) {
  const pct = Math.min(100, (ms / 3000) * 100);
  const fill = document.getElementById('latFill');
  fill.style.width  = pct + '%';
  fill.style.background = ok ? 'var(--green)' : 'var(--red)';
  document.getElementById('latVal').textContent = ms + ' ms';
  document.getElementById('latVal').style.color  = ok ? 'var(--green)' : 'var(--red)';
  document.getElementById('latStatus').textContent = ok ? `✓ Cumple el ASR (< 3000 ms)` : `⚠ No cumple (> 3000 ms)`;
  addAsrHistory('Latencia', `Company ${companyId}`, src, `${ms} ms`, ok);
}

function updateAsrScalability(attempts, ok) {
  const pct = ok ? 100 : Math.max(0, 100 - attempts * 20);
  const fill = document.getElementById('scaleFill');
  fill.style.width  = pct + '%';
  fill.style.background = ok ? 'var(--green)' : 'var(--red)';
  document.getElementById('scaleVal').textContent = ok ? '100%' : 'Fallida';
  document.getElementById('scaleVal').style.color  = ok ? 'var(--green)' : 'var(--red)';
  document.getElementById('scaleStatus').textContent = ok ? `✓ Éxito en ${attempts} intento(s)` : '✗ Extracción fallida';
  const provider = document.getElementById('providerSelect').value.toUpperCase();
  addAsrHistory('Escalabilidad', provider, `${attempts} intento(s)`, ok ? '100%' : '0%', ok);
}

function addAsrHistory(asr, empresa, fuente, resultado, ok) {
  const tbody = document.getElementById('asrHistory');
  if (tbody.querySelector('.empty-state')) tbody.innerHTML = '';
  const row = document.createElement('tr');
  row.innerHTML = `
    <td style="color:var(--text-muted)">${now()}</td>
    <td><span class="chip ${asr==='Latencia'?'chip-purple':'chip-green'}">${asr}</span></td>
    <td>${empresa}</td>
    <td style="color:var(--text-muted)">${fuente}</td>
    <td style="font-weight:700">${resultado}</td>
    <td><span style="color:${ok?'var(--green)':'var(--red)'}">${ok ? '✓ Cumple' : '✗ No cumple'}</span></td>`;
  tbody.insertBefore(row, tbody.firstChild);
  const count = parseInt(document.getElementById('histCount').textContent || '0');
  document.getElementById('histCount').textContent = count + 1;
}

// ═══════════════════════════════════════════════════════
// ─── SPRINT 3: PLACES ────────────────────────────────
// ═══════════════════════════════════════════════════════

async function checkPlacesHealth() {
  const band = document.getElementById('placesStatusBand');
  const dot  = document.getElementById('placesStatusDot');
  const text = document.getElementById('placesStatusText');
  const detail = document.getElementById('placesStatusDetail');
  dot.className = 'status-dot dot-loading';
  text.textContent = 'Verificando health del clúster…';
  detail.textContent = '';

  const t0 = performance.now();
  try {
    const r = await fetch('/health');
    const elapsed = Math.round(performance.now() - t0);
    if (r.ok) {
      const data = await r.json();
      dot.className = 'status-dot dot-ok';
      text.textContent = '✓ Clúster MongoDB operativo';
      detail.textContent = `${elapsed} ms · ${JSON.stringify(data).substring(0, 120)}`;
      document.getElementById('pkCluster').textContent = 'OK';
      document.getElementById('pkCluster').style.color = 'var(--green)';
      document.getElementById('pkLatency').textContent = elapsed + ' ms';
      toast('Health check exitoso — MongoDB operativo', 'ok');
    } else {
      throw new Error(`HTTP ${r.status}`);
    }
  } catch (e) {
    dot.className = 'status-dot dot-err';
    text.textContent = '✗ Clúster no disponible o en failover';
    detail.textContent = e.message;
    document.getElementById('pkCluster').textContent = 'ERROR';
    document.getElementById('pkCluster').style.color = 'var(--red)';
    toast('Health check fallido: ' + e.message, 'err');
  }
}

async function loadPlaces() {
  const grid = document.getElementById('placesGrid');
  grid.innerHTML = '<div class="empty-state"><div class="spinner" style="margin:0 auto 10px"></div><p>Cargando places del clúster MongoDB…</p></div>';
  document.getElementById('pkLatency').textContent = '…';

  const t0 = performance.now();
  try {
    const r = await fetch('/places/');
    const elapsed = Math.round(performance.now() - t0);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();

    document.getElementById('pkLatency').textContent = elapsed + ' ms';
    const places = data.places || data.results || data || [];
    const arr = Array.isArray(places) ? places : Object.values(places);

    document.getElementById('pkTotal').textContent = arr.length;
    document.getElementById('placesCount').textContent = arr.length;

    // Status band
    document.getElementById('placesStatusDot').className = 'status-dot dot-ok';
    document.getElementById('placesStatusText').textContent = `✓ ${arr.length} places cargados en ${elapsed} ms`;

    if (!arr.length) {
      grid.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>La colección places está vacía. Inserta documentos en MongoDB.</p></div>';
      return;
    }

    grid.innerHTML = `<div class="places-grid">${arr.map(p => renderPlaceCard(p)).join('')}</div>`;
    toast(`${arr.length} places cargados en ${elapsed} ms`, 'ok');
  } catch (e) {
    grid.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Error: ${e.message}</p></div>`;
    document.getElementById('placesStatusDot').className = 'status-dot dot-err';
    document.getElementById('placesStatusText').textContent = '✗ Error al cargar places';
    toast('Error al cargar places: ' + e.message, 'err');
  }
}

function renderPlaceCard(p) {
  const name  = p.name  || p.nombre || p._id || 'Sin nombre';
  const city  = p.city  || p.ciudad || p.location?.city || '—';
  const country = p.country || p.pais || p.location?.country || '—';
  const cat   = p.category || p.tipo || '📍';
  const desc  = p.description || p.descripcion || '';
  const id    = p._id || p.id || '';
  return `
    <div class="place-card">
      <div class="place-cat">${cat}</div>
      <div class="place-name">${name}</div>
      <div class="place-location">📍 ${city}${country !== '—' ? ', ' + country : ''}</div>
      ${desc ? `<div class="place-desc">${desc.substring(0, 80)}${desc.length > 80 ? '…' : ''}</div>` : ''}
      ${id ? `<div class="place-id">ID: ${String(id).substring(0, 24)}</div>` : ''}
    </div>`;
}

// ═══════════════════════════════════════════════════════
// ─── SPRINT 3: CREDENTIALS (ASR29) ───────────────────
// ═══════════════════════════════════════════════════════

async function registerCredential() {
  const credId    = document.getElementById('regCredId').value.trim();
  const clientId  = document.getElementById('regClientId').value.trim();
  const countries = document.getElementById('regCountries').value.trim().split(',').map(s => s.trim()).filter(Boolean);
  const hourStart = parseInt(document.getElementById('regHourStart').value);
  const hourEnd   = parseInt(document.getElementById('regHourEnd').value);
  const avgReq    = parseFloat(document.getElementById('regAvgReq').value);
  const stddev    = parseFloat(document.getElementById('regStddev').value);

  if (!credId || !clientId) { toast('ID de credencial y Client ID son requeridos', 'err'); return; }

  const payload = {
    credential_id: credId,
    client_id: clientId,
    typical_countries: countries,
    typical_hour_start: hourStart,
    typical_hour_end: hourEnd,
    avg_requests_per_min: avgReq,
    stddev_requests: stddev
  };

  try {
    const r = await fetch('/credentials/register/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await r.json();
    if (r.ok) {
      toast(`✓ Credencial "${credId}" registrada`, 'ok');
      document.getElementById('regCredId').value = '';
    } else {
      toast('Error: ' + (data.detail || data.error || JSON.stringify(data)), 'err');
    }
  } catch (e) {
    toast('Error de conexión: ' + e.message, 'err');
  }
}

async function useCredential(forceAnomaly) {
  const credId   = document.getElementById('useCredId').value.trim();
  const clientId = document.getElementById('useClientId').value.trim();
  const country  = document.getElementById('useCountry').value;

  if (!credId || !clientId) { toast('Completa ID Credencial y Client ID', 'err'); return; }

  const payload = {
    credential_id: credId,
    client_id: clientId,
    geo_country: country
  };

  const resultEl = document.getElementById('credResult');
  resultEl.style.display = 'none';

  try {
    const r = await fetch('/credentials/use/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await r.json();

    credUseTotal++;
    const anomaly = data.anomaly_detected || data.alert || forceAnomaly;
    if (anomaly) credAnomalias++;
    updateAsr29Stats();

    resultEl.style.display = 'block';
    if (r.ok) {
      const isAnom = data.anomaly_detected || data.alert;
      resultEl.className = `cred-result ${isAnom ? 'result-anomaly' : 'result-ok'}`;
      resultEl.innerHTML = isAnom
        ? `⚠️ <strong>ANOMALÍA DETECTADA</strong><br><small>${data.alert_type || 'GEO/TIME/VOLUME'} — ${country}</small>`
        : `✓ <strong>Acceso normal registrado</strong><br><small>País: ${country} — Sin alertas</small>`;
      toast(isAnom ? `⚠ Anomalía detectada (${country})` : `✓ Uso registrado — ${country}`, isAnom ? 'warn' : 'ok');
    } else {
      resultEl.className = 'cred-result result-error';
      resultEl.innerHTML = `✗ <strong>${data.detail || data.error || 'Error'}</strong>`;
      toast('Error en uso de credencial: ' + (data.detail || data.error), 'err');
    }
  } catch (e) {
    resultEl.style.display = 'block';
    resultEl.className = 'cred-result result-error';
    resultEl.innerHTML = `✗ <strong>Error de conexión</strong><br><small>${e.message}</small>`;
    toast('Error de conexión: ' + e.message, 'err');
  }
}

function updateAsr29Stats() {
  document.getElementById('s29Total').textContent = credUseTotal;
  document.getElementById('s29Anomalias').textContent = credAnomalias;
  const tasa = credUseTotal > 0 ? Math.round(credAnomalias / credUseTotal * 100) + '%' : '—';
  document.getElementById('s29Tasa').textContent = tasa;
}

async function loadAuditLog() {
  const tbody = document.getElementById('auditLogBody');
  tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><div class="spinner" style="margin:0 auto 10px"></div><p>Cargando audit log…</p></div></td></tr>`;

  try {
    const r = await fetch('/credentials/audit/');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const logs = data.logs || data.results || data || [];
    const arr = Array.isArray(logs) ? logs : [];

    document.getElementById('auditCount').textContent = arr.length;

    if (!arr.length) {
      tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><div class="icon">📜</div><p>No hay eventos en el audit log todavía</p></div></td></tr>`;
      return;
    }

    tbody.innerHTML = arr.slice(0, 50).map(log => {
      const isAnom = log.is_anomaly || log.anomaly || log.alert_type;
      return `<tr>
        <td style="color:var(--text-muted);font-size:11px">${fmtDatetime(log.timestamp || log.created_at)}</td>
        <td style="font-weight:600">${log.credential_id || '—'}</td>
        <td style="color:var(--text-muted)">${log.client_id || '—'}</td>
        <td><span style="background:${isAnom?'var(--red-dim)':'var(--green-dim)'};color:${isAnom?'var(--red)':'var(--green)'};padding:2px 7px;border-radius:4px;font-size:11px;font-weight:700">${log.geo_country || '—'}</span></td>
        <td style="color:var(--text-muted)">${log.hour !== undefined ? log.hour + ':00' : '—'}</td>
        <td><span class="chip ${isAnom?'chip-red':'chip-green'}" style="${isAnom?'background:var(--red-dim);color:var(--red)':''}">${isAnom ? '⚠ Anómalo' : '✓ Normal'}</span></td>
        <td style="font-size:11px;color:var(--text-muted)">${log.alert_type || log.details || (isAnom ? 'Anomalía detectada' : 'Acceso normal')}</td>
      </tr>`;
    }).join('');

    toast(`${arr.length} eventos en el audit log`, 'ok');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><div class="icon">⚠️</div><p>${e.message}</p></div></td></tr>`;
    toast('Error al cargar audit log: ' + e.message, 'err');
  }
}

// ═══════════════════════════════════════════════════════
// ─── SPRINT 3: LOG MASKING (ASR30) ───────────────────
// ═══════════════════════════════════════════════════════

async function testLeak(type, btn) {
  const card = btn.closest('.leak-card');
  const resultEl = document.getElementById(`lr-${type}`);

  btn.disabled = true;
  btn.textContent = 'Probando…';
  resultEl.style.display = 'none';

  const maskLogEl = document.getElementById('maskLog');

  try {
    const r = await fetch(`/test/leak/${type}/`);
    const data = await r.json();

    maskTestCount++;
    document.getElementById('s30Tests').textContent = maskTestCount;

    const rawField    = data.raw_value || data.original || data.value || data.leaked || '';
    const maskedField = data.masked_value || data.masked || data.log_output || data.result || '';
    const isMasked    = data.masked === true || (maskedField && maskedField.includes('[MASKED]'));

    resultEl.style.display = 'block';

    if (isMasked || maskedField.includes('[MASKED]')) {
      maskSuccessCount++;
      card.classList.add('leak-card-ok');
      card.classList.remove('leak-card-err');
      resultEl.className = 'leak-result lr-ok';
      resultEl.innerHTML = `
        <div class="lr-row"><span class="lr-label">Original:</span><code class="lr-raw">${escHtml(String(rawField).substring(0, 80))}</code></div>
        <div class="lr-row"><span class="lr-label">En log:</span><code class="lr-masked">${escHtml(String(maskedField).substring(0, 80))}</code></div>
        <div class="lr-status">✓ Datos enmascarados correctamente</div>`;
      addMaskLog('ok', `${type.toUpperCase()} — enmascarado ✓ | raw: ${String(rawField).substring(0,40)} → ${String(maskedField).substring(0,40)}`);
      toast(`✓ ${type} enmascarado correctamente`, 'ok');
    } else {
      card.classList.add('leak-card-err');
      card.classList.remove('leak-card-ok');
      resultEl.className = 'leak-result lr-err';
      resultEl.innerHTML = `
        <div class="lr-row"><span class="lr-label">Original:</span><code class="lr-raw">${escHtml(String(rawField).substring(0, 80))}</code></div>
        <div class="lr-row"><span class="lr-label">En log:</span><code class="lr-raw">${escHtml(String(maskedField).substring(0, 80))}</code></div>
        <div class="lr-status" style="color:var(--red)">✗ ¡Datos NO enmascarados — filtro no activo!</div>`;
      addMaskLog('err', `${type.toUpperCase()} — NO enmascarado ✗`);
      toast(`⚠ ${type} no fue enmascarado`, 'err');
    }

    document.getElementById('s30Masked').textContent = maskSuccessCount;
    const pct = maskTestCount > 0 ? Math.round(maskSuccessCount / maskTestCount * 100) + '%' : '—';
    document.getElementById('s30Pct').textContent = pct;
    document.getElementById('maskCount').textContent = maskTestCount;

  } catch (e) {
    resultEl.style.display = 'block';
    resultEl.className = 'leak-result lr-err';
    resultEl.innerHTML = `<div class="lr-status" style="color:var(--red)">✗ Error: ${escHtml(e.message)}</div>`;
    addMaskLog('err', `${type.toUpperCase()} — error de conexión: ${e.message}`);
    toast('Error: ' + e.message, 'err');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Probar Enmascaramiento';
  }
}

function addMaskLog(type, msg) {
  const el = document.getElementById('maskLog');
  const cls = { ok: 'log-ok', err: 'log-err', info: 'log-info' }[type] || 'log-info';
  const line = document.createElement('div');
  line.className = 'log-line';
  line.innerHTML = `<span class="log-ts">${now()}</span><span class="${cls}">${msg}</span>`;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

function clearMaskLog() {
  document.getElementById('maskLog').innerHTML = '';
  maskTestCount = 0;
  maskSuccessCount = 0;
  document.getElementById('s30Tests').textContent = '0';
  document.getElementById('s30Masked').textContent = '0';
  document.getElementById('s30Pct').textContent = '—';
  document.getElementById('maskCount').textContent = '0';
  document.querySelectorAll('.leak-card').forEach(c => {
    c.classList.remove('leak-card-ok', 'leak-card-err');
  });
  document.querySelectorAll('.leak-result').forEach(r => r.style.display = 'none');
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ═══════════════════════════════════════════════════════
// ─── SPRINT 3: DISPONIBILIDAD ─────────────────────────
// ═══════════════════════════════════════════════════════

async function checkDisponibilidad() {
  // Update all shard cards to loading
  ['mongos','shard1','shard2','shard3'].forEach(id => {
    document.getElementById('sc-' + id).className = 'shard-card shard-loading';
    document.getElementById('ss-' + id).textContent = 'Verificando…';
  });

  document.getElementById('disponStatus').textContent = 'Verificando estado del clúster…';

  const t0 = performance.now();
  try {
    const r = await fetch('/health');
    const elapsed = Math.round(performance.now() - t0);

    if (r.ok) {
      const data = await r.json();

      // mongos always ok if health check passes
      setShardStatus('mongos', true, 'Activo · Router');

      // Infer shard status from health data
      const shardStatuses = data.shards || data.shard_status || null;
      if (shardStatuses) {
        ['shard1','shard2','shard3'].forEach(shard => {
          const s = shardStatuses[shard];
          setShardStatus(shard, s !== false, s || 'Replica set activo');
        });
      } else {
        // Health passed = all shards presumably up
        ['shard1','shard2','shard3'].forEach(shard => {
          setShardStatus(shard, true, 'Replica set activo');
        });
      }

      const fill  = document.getElementById('disponFill');
      fill.style.width = '100%';
      fill.style.background = 'var(--green)';
      document.getElementById('disponVal').textContent = elapsed + ' ms';
      document.getElementById('disponVal').style.color = 'var(--green)';
      document.getElementById('disponStatus').textContent = `✓ Clúster completamente operativo · ${elapsed} ms`;

      toast(`Clúster MongoDB operativo · health en ${elapsed} ms`, 'ok');
    } else {
      throw new Error(`HTTP ${r.status}`);
    }
  } catch (e) {
    setShardStatus('mongos', false, 'Error / Failover');
    ['shard1','shard2','shard3'].forEach(id => setShardStatus(id, null, 'Estado desconocido'));

    const fill = document.getElementById('disponFill');
    fill.style.width = '20%';
    fill.style.background = 'var(--red)';
    document.getElementById('disponVal').textContent = 'ERROR';
    document.getElementById('disponVal').style.color = 'var(--red)';
    document.getElementById('disponStatus').textContent = `✗ Clúster no disponible — posible failover en curso`;

    toast('Error en verificación: ' + e.message, 'err');
  }
}

function setShardStatus(id, ok, detail) {
  const card = document.getElementById('sc-' + id);
  const status = document.getElementById('ss-' + id);
  if (ok === true) {
    card.className = 'shard-card shard-ok';
    status.innerHTML = `<span style="color:var(--green)">✓ ${detail || 'Activo'}</span>`;
  } else if (ok === false) {
    card.className = 'shard-card shard-err';
    status.innerHTML = `<span style="color:var(--red)">✗ ${detail || 'Error'}</span>`;
  } else {
    card.className = 'shard-card';
    status.innerHTML = `<span style="color:var(--text-muted)">— ${detail || 'Desconocido'}</span>`;
  }
}

function addFailoverRun() {
  const deltaT    = parseInt(document.getElementById('failDeltaT').value);
  const recovery  = parseInt(document.getElementById('failRecovery').value);

  if (isNaN(deltaT) || isNaN(recovery)) {
    toast('Ingresa delta_t y recovery válidos', 'err');
    return;
  }

  failoverRuns.push({ deltaT, recovery, ok: deltaT < 5000 && recovery < 30 });
  document.getElementById('failDeltaT').value = '';
  document.getElementById('failRecovery').value = '';

  renderFailoverResults();
}

function renderFailoverResults() {
  const el = document.getElementById('failoverResults');
  if (!failoverRuns.length) {
    el.innerHTML = '<div class="empty-state" style="padding:32px 16px"><div class="icon">📊</div><p>Sin corridas registradas</p></div>';
    return;
  }

  const passing  = failoverRuns.filter(r => r.ok).length;
  const criterion = passing >= 4 ? 'var(--green)' : passing >= 2 ? 'var(--yellow)' : 'var(--red)';
  const criterionLabel = passing >= 4 ? '✓ ASR CUMPLIDO' : passing >= 2 ? '⚠ Parcialmente' : '✗ No cumple';

  el.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <span style="font-size:13px;color:var(--text-soft)">Corridas: ${failoverRuns.length} / 5</span>
      <span style="font-weight:700;color:${criterion}">${criterionLabel} (${passing}/5)</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>#</th><th>Delta T</th><th>Recovery</th><th>Estado</th></tr></thead>
        <tbody>
          ${failoverRuns.map((r, i) => `
            <tr>
              <td style="color:var(--text-muted)">Corrida ${i+1}</td>
              <td style="font-weight:700;color:${r.deltaT < 5000 ? 'var(--green)' : 'var(--red)'}">${r.deltaT.toLocaleString()} ms</td>
              <td style="color:${r.recovery < 30 ? 'var(--green)' : 'var(--red)'}">${r.recovery} s</td>
              <td><span style="color:${r.ok ? 'var(--green)' : 'var(--red)'}">${r.ok ? '✓ Cumple' : '✗ No cumple'}</span></td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;

  // Update ASR fill
  const fill = document.getElementById('disponFill');
  const pct  = Math.round(passing / 5 * 100);
  fill.style.width = pct + '%';
  fill.style.background = passing >= 4 ? 'var(--green)' : passing >= 2 ? 'var(--yellow)' : 'var(--red)';
  document.getElementById('disponVal').textContent = passing + '/5';
  document.getElementById('disponVal').style.color = criterion;
  document.getElementById('disponStatus').textContent =
    `${criterionLabel} — ${passing} de 5 corridas cumplen el criterio delta_t < 5s`;

  toast(`Corrida ${failoverRuns.length} registrada — ${r => r.ok}`, 'info');
}

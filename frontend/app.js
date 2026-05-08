// ─── Config ───────────────────────────────────────────
const API      = '/api/v1';
const EXT_API  = '/extractor/api/v1';

// ─── State ────────────────────────────────────────────
let providerChartInst = null;
let serviceChartInst  = null;
let allReports        = [];
let currentPage       = 1;
const PAGE_SIZE       = 15;
const asrHistory      = [];  // local measurement log

// ─── Init ─────────────────────────────────────────────
(function init() {
  // Populate company selects
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

  // Populate project select
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
  return new Date(iso).toLocaleDateString('es-CO', {
    month: 'short', day: 'numeric', year: '2-digit'
  });
}

function now() {
  return new Date().toLocaleTimeString('es-CO', { hour12: false });
}

// ─── Toast ────────────────────────────────────────────
function toast(msg, type = 'info') {
  const icons = { ok: '✓', err: '✗', info: 'ℹ' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type]}</span><span>${msg}</span>`;
  document.getElementById('toastContainer').appendChild(el);
  setTimeout(() => el.remove(), 4000);
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
      datasets: [{
        data: Object.values(data),
        backgroundColor: CHART_COLORS,
        borderColor: '#12151f',
        borderWidth: 3,
        hoverOffset: 6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: { color: '#94a3b8', font: { size: 12 }, padding: 14, boxWidth: 12 }
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.label}: ${fmt(ctx.raw)}`
          }
        }
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
        label: 'Costo USD',
        data: sorted.map(([,v]) => v),
        backgroundColor: CHART_COLORS.map(c => c + 'bb'),
        borderColor: CHART_COLORS,
        borderWidth: 1,
        borderRadius: 6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: ctx => ` ${fmt(ctx.raw)}` }
        }
      },
      scales: {
        x: {
          ticks: { color: '#64748b', font: { size: 11 } },
          grid:  { color: '#252840' }
        },
        y: {
          ticks: {
            color: '#64748b', font: { size: 11 },
            callback: v => '$' + (v >= 1000 ? (v/1000).toFixed(0)+'k' : v)
          },
          grid: { color: '#252840' }
        }
      }
    }
  });
}

// ─── KPI skeleton → real ──────────────────────────────
function renderKPIs(s) {
  const services  = s.service_breakdown  || {};
  const providers = s.provider_breakdown || {};
  const total     = s.total_cost ?? 0;
  const topEntry  = Object.entries(services).sort((a,b)=>b[1]-a[1])[0];

  const kpiData = [
    { label: 'Total Mensual', value: fmt(total),                    sub: 'USD este periodo',             icon: '💰', cls: '' },
    { label: 'Servicios activos', value: Object.keys(services).length, sub: 'en uso',                   icon: '⚙️',  cls: 'green' },
    { label: 'Proveedores',    value: Object.keys(providers).length, sub: 'conectados',                  icon: '🌐', cls: 'blue' },
    { label: 'Mayor Gasto',    value: topEntry ? topEntry[0] : '—',  sub: topEntry ? fmt(topEntry[1]) : '',icon: '📈', cls: 'yellow'},
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

  // Reset UI
  document.getElementById('kpiGrid').innerHTML = Array(4).fill(
    '<div class="kpi-card skeleton skeleton-card"></div>'
  ).join('');
  ['serviceBreakdown','providerBreakdown'].forEach(x =>
    document.getElementById(x).innerHTML =
      '<div class="bar-row"><div class="bar-label"><div class="skeleton skeleton-bar" style="width:100%;height:8px"></div></div><div class="bar-track" style="flex:1"></div><div class="bar-amount"></div></div>'.repeat(4)
  );

  // Latency badge spinner
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

    // KPIs
    renderKPIs(s);

    // Charts
    buildProviderChart(s.provider_breakdown);
    buildServiceChart(s.service_breakdown);

    // Bars
    document.getElementById('svcCount').textContent  = Object.keys(s.service_breakdown  || {}).length;
    document.getElementById('provCount').textContent = Object.keys(s.provider_breakdown || {}).length;
    renderBars(s.service_breakdown,  'serviceBreakdown');
    renderBars(s.provider_breakdown, 'providerBreakdown');

    // Latency badge
    spinner.style.display = 'none';
    const ok = elapsed < 3000;
    badge.className = `latency-badge ${ok ? 'ok' : 'bad'}`;
    ltext.textContent = `${elapsed} ms`;

    // Source chip
    const src = data.source || 'db';
    const chipHtml = src === 'cache'
      ? '<span class="source-chip source-cache">⚡ cache</span>'
      : '<span class="source-chip source-db">🗄 base de datos</span>';
    document.getElementById('globalSourceChip').innerHTML = chipHtml;

    // Sub text
    document.getElementById('dashSub').textContent =
      `Company ${id} · ${s.record_count ?? 0} registros · ${s.project_count ?? 0} proyectos`;

    // Update ASR latency panel
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
    document.getElementById('reportSub').textContent =
      `Company ${id} · ${allReports.length} registros encontrados`;
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

  const provClass = p => {
    const m = {'aws':'prov-aws','gcp':'prov-gcp','azure':'prov-azure'};
    return m[p] || 'prov-aws';
  };

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

  // Pagination
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

      if (attempts > 1) {
        addLog('warn', `Necesitó ${attempts} intentos (backoff exponencial aplicado)`);
      }

      // Attempts chip
      const chip = document.getElementById('attemptsChip');
      chip.style.display = 'inline';
      chip.textContent = `${attempts} intento(s)`;
      chip.className = `chip ${attempts > 1 ? 'chip-yellow' : 'chip-green'}`;

      // Show metrics
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

      // Update ASR scalability
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

// ─── Extractor Async ──────────────────────────────────
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
  const maxAttempts = 20;

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
      } else if (attempts >= maxAttempts) {
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

// ─── Log helpers ─────────────────────────────────────
function clearLog() {
  document.getElementById('taskTimeline').innerHTML = '';
}

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
  ['btnExtSync','btnExtAsync'].forEach(id => {
    document.getElementById(id).disabled = loading;
  });
}

// ─── ASR panel updates ────────────────────────────────
function updateAsrLatency(ms, ok, companyId, src) {
  const pct = Math.min(100, (ms / 3000) * 100);
  const fill = document.getElementById('latFill');
  fill.style.width  = pct + '%';
  fill.style.background = ok ? 'var(--green)' : 'var(--red)';
  document.getElementById('latVal').textContent = ms + ' ms';
  document.getElementById('latVal').style.color  = ok ? 'var(--green)' : 'var(--red)';
  document.getElementById('latStatus').textContent =
    ok ? `✓ Cumple el ASR (< 3000 ms)` : `⚠ No cumple (> 3000 ms)`;

  // History
  addAsrHistory('Latencia', `Company ${companyId}`, src, `${ms} ms`, ok);
}

function updateAsrScalability(attempts, ok) {
  const pct = ok ? 100 : Math.max(0, 100 - attempts * 20);
  const fill = document.getElementById('scaleFill');
  fill.style.width  = pct + '%';
  fill.style.background = ok ? 'var(--green)' : 'var(--red)';
  document.getElementById('scaleVal').textContent = ok ? '100%' : 'Fallida';
  document.getElementById('scaleVal').style.color  = ok ? 'var(--green)' : 'var(--red)';
  document.getElementById('scaleStatus').textContent =
    ok ? `✓ Éxito en ${attempts} intento(s)` : '✗ Extracción fallida';

  const provider = document.getElementById('providerSelect').value.toUpperCase();
  addAsrHistory('Escalabilidad', provider, `${attempts} intento(s)`, ok ? '100%' : '0%', ok);
}

function addAsrHistory(asr, empresa, fuente, resultado, ok) {
  const tbody = document.getElementById('asrHistory');

  // Remove empty state
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

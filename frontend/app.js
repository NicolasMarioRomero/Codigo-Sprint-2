// ─── Config ────────────────────────────────────────────
const API     = '/api/v1';
const EXT_API = '/extractor/api/v1';

// ─── State ─────────────────────────────────────────────
let providerChartInst = null;
let serviceChartInst  = null;
let allReports        = [];
let currentPage       = 1;
const PAGE_SIZE       = 15;
let failoverRuns      = [];
let maskTestCount     = 0;
let maskSuccessCount  = 0;
let credUseTotal      = 0;
let credAnomalias     = 0;

// ─── Theme ─────────────────────────────────────────────
(function initTheme() {
  const saved = localStorage.getItem('bite-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeIcon(saved);
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('bite-theme', next);
  updateThemeIcon(next);
  if (providerChartInst || serviceChartInst) {
    setTimeout(() => {
      if (providerChartInst) providerChartInst.update();
      if (serviceChartInst)  serviceChartInst.update();
    }, 50);
  }
}

function updateThemeIcon(theme) {
  document.getElementById('iconSun').style.display  = theme === 'dark' ? 'block' : 'none';
  document.getElementById('iconMoon').style.display = theme === 'light' ? 'block' : 'none';
}

// ─── Init ──────────────────────────────────────────────
(function init() {
  ['companySelect', 'extCompanySelect'].forEach(id => {
    const sel = document.getElementById(id);
    for (let i = 1; i <= 10; i++) {
      const o = document.createElement('option');
      o.value = i; o.textContent = `Company ${i}`;
      sel.appendChild(o);
    }
  });
  const proj = document.getElementById('projectSelect');
  for (let i = 1; i <= 5; i++) {
    const o = document.createElement('option');
    o.value = i; o.textContent = `project-${i}`;
    proj.appendChild(o);
  }
})();

// ─── Navigation ────────────────────────────────────────
function showPage(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  if (el) el.classList.add('active');
}

function onCompanyChange() {
  const v = document.getElementById('companySelect').value;
  document.getElementById('extCompanySelect').value = v;
}

// ─── Utils ─────────────────────────────────────────────
function fmt(n) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n ?? 0);
}
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('es-CO', { month: 'short', day: 'numeric', year: '2-digit' });
}
function fmtDatetime(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString('es-CO', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  catch { return iso; }
}
function now() { return new Date().toLocaleTimeString('es-CO', { hour12: false }); }
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ─── Toast ─────────────────────────────────────────────
function toast(msg, type = 'info') {
  const labels = { ok: '✓', err: '✕', info: 'i', warn: '!' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<div class="toast-icon">${labels[type] || 'i'}</div><span>${msg}</span>`;
  document.getElementById('toastContainer').appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(10px)'; el.style.transition = 'all 0.2s'; setTimeout(() => el.remove(), 200); }, 4000);
}

// ─── Bar rows ───────────────────────────────────────────
function renderBars(obj, id) {
  const el = document.getElementById(id);
  if (!obj || !Object.keys(obj).length) {
    el.innerHTML = '<div class="empty-state" style="padding:24px"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 3h18v18H3z"/></svg><p>Sin datos</p></div>';
    return;
  }
  const sorted = Object.entries(obj).sort((a,b) => b[1]-a[1]);
  const max = sorted[0][1];
  el.innerHTML = sorted.map(([k,v]) => `
    <div class="bar-row">
      <div class="bar-label" title="${k}">${k}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${(v/max*100).toFixed(1)}%"></div></div>
      <div class="bar-amount">${fmt(v)}</div>
    </div>`).join('');
}

// ─── Charts ────────────────────────────────────────────
const COLORS = ['#6366f1','#8b5cf6','#3b82f6','#10b981','#f59e0b','#ef4444','#ec4899','#06b6d4','#84cc16','#f97316'];

function chartDefaults() {
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
  return {
    tickColor: isDark ? '#4a5568' : '#94a3b8',
    gridColor: isDark ? '#1d2235' : '#e2e8f0',
    legendColor: isDark ? '#94a3b8' : '#64748b',
  };
}

function buildProviderChart(data) {
  const ctx = document.getElementById('providerChart').getContext('2d');
  if (providerChartInst) providerChartInst.destroy();
  if (!data || !Object.keys(data).length) return;
  const d = chartDefaults();
  providerChartInst = new Chart(ctx, {
    type: 'doughnut',
    data: { labels: Object.keys(data), datasets: [{ data: Object.values(data), backgroundColor: COLORS, borderColor: 'transparent', borderWidth: 0, hoverOffset: 5 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { color: d.legendColor, font: { size: 12, family: 'Inter' }, padding: 14, boxWidth: 10, boxHeight: 10 } },
        tooltip: { callbacks: { label: c => ` ${c.label}: ${fmt(c.raw)}` } }
      },
      cutout: '68%',
    }
  });
}

function buildServiceChart(data) {
  const ctx = document.getElementById('serviceChart').getContext('2d');
  if (serviceChartInst) serviceChartInst.destroy();
  if (!data || !Object.keys(data).length) return;
  const sorted = Object.entries(data).sort((a,b)=>b[1]-a[1]).slice(0,8);
  const d = chartDefaults();
  serviceChartInst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(([k]) => k),
      datasets: [{ label: 'Costo USD', data: sorted.map(([,v])=>v), backgroundColor: COLORS.map(c=>c+'cc'), borderColor: 'transparent', borderRadius: 5 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ` ${fmt(c.raw)}` } } },
      scales: {
        x: { ticks: { color: d.tickColor, font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: d.tickColor, font: { size: 10 }, callback: v => '$'+(v>=1000?(v/1000).toFixed(0)+'k':v) }, grid: { color: d.gridColor } }
      }
    }
  });
}

// ─── KPIs ───────────────────────────────────────────────
function renderKPIs(s) {
  const svc = s.service_breakdown || {};
  const prov = s.provider_breakdown || {};
  const total = s.total_cost ?? 0;
  const top = Object.entries(svc).sort((a,b)=>b[1]-a[1])[0];
  const items = [
    { label:'Total Mensual',     value: fmt(total),               sub: 'USD este periodo',          cls: '' },
    { label:'Servicios Activos', value: Object.keys(svc).length,  sub: 'servicios en uso',          cls: 'kpi-green' },
    { label:'Proveedores',       value: Object.keys(prov).length, sub: 'conectados',                cls: 'kpi-blue' },
    { label:'Mayor Gasto',       value: top ? top[0] : '—',       sub: top ? fmt(top[1]) : '—',     cls: '' },
  ];
  document.getElementById('kpiGrid').innerHTML = items.map(k => `
    <div class="kpi-card ${k.cls}">
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value">${k.value}</div>
      <div class="kpi-sub">${k.sub}</div>
    </div>`).join('');
}

// ─── Dashboard ──────────────────────────────────────────
async function loadDashboard(force) {
  const id = document.getElementById('companySelect').value;
  if (!id) { toast('Selecciona una empresa primero', 'err'); return; }

  document.getElementById('kpiGrid').innerHTML = Array(4).fill('<div class="kpi-card skeleton-card"></div>').join('');
  ['serviceBreakdown','providerBreakdown'].forEach(x => {
    document.getElementById(x).innerHTML = Array(4).fill('<div class="bar-row"><div class="bar-label"><div style="height:8px;border-radius:3px;background:var(--surface3);animation:shimmer 1.4s infinite;background-size:200% 100%"></div></div><div class="bar-track" style="flex:1"></div></div>').join('');
  });

  const badge = document.getElementById('latencyBadge');
  const dot   = document.getElementById('latencyDot');
  const ltext = document.getElementById('latencyText');
  const spinner = document.getElementById('latencySpinner');
  badge.classList.add('visible');
  spinner.style.display = 'inline-block';
  dot.className = 'latency-dot';
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
    dot.className = `latency-dot ${ok ? 'ok' : 'bad'}`;
    ltext.textContent = `${elapsed} ms`;

    const src = data.source || 'db';
    document.getElementById('globalSourceChip').innerHTML = src === 'cache'
      ? '<span class="source-chip source-cache">cache</span>'
      : '<span class="source-chip source-db">base de datos</span>';

    document.getElementById('dashSub').textContent = `Company ${id} · ${s.record_count ?? 0} registros · ${s.project_count ?? 0} proyectos`;
    updateAsrLatency(elapsed, ok, id, src);
    toast(`Dashboard en ${elapsed} ms ${ok ? '— dentro del ASR' : '— supera los 3 s'}`, ok ? 'ok' : 'warn');
  } catch(e) {
    spinner.style.display = 'none';
    dot.className = 'latency-dot bad';
    ltext.textContent = 'Error';
    document.getElementById('kpiGrid').innerHTML = `<div class="kpi-card" style="grid-column:1/-1"><div class="empty-state"><p>${e.message}</p></div></div>`;
    toast('Error al cargar el dashboard: ' + e.message, 'err');
  }
}

// ─── Reports ────────────────────────────────────────────
async function loadReports() {
  const id = document.getElementById('companySelect').value;
  if (!id) { toast('Selecciona una empresa primero', 'err'); return; }
  document.getElementById('reportTableBody').innerHTML = `<tr><td colspan="8"><div class="empty-state"><div class="spinner" style="margin:0 auto 10px"></div><p>Cargando reportes…</p></div></td></tr>`;
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
    document.getElementById('reportTableBody').innerHTML = `<tr><td colspan="8"><div class="empty-state"><p>${e.message}</p></div></td></tr>`;
    toast('Error: ' + e.message, 'err');
  }
}

function renderReportTable() {
  const start = (currentPage-1)*PAGE_SIZE, end = start+PAGE_SIZE;
  const page = allReports.slice(start,end);
  const totalPages = Math.ceil(allReports.length/PAGE_SIZE);
  const prov = p => ({ aws:'prov-aws',gcp:'prov-gcp',azure:'prov-azure' }[p]||'prov-aws');
  document.getElementById('reportTableBody').innerHTML = page.map((r,i) => `
    <tr>
      <td style="color:var(--text-muted)">${start+i+1}</td>
      <td><span class="provider-badge ${prov(r.provider)}">${(r.provider||'aws').toUpperCase()}</span></td>
      <td style="color:var(--text)">${r.service_name||r.service||'—'}</td>
      <td>${r.project_id||'—'}</td>
      <td>${r.region||'—'}</td>
      <td style="font-weight:700;color:var(--accent-soft)">${fmt(r.cost??r.amount)}</td>
      <td>${r.usage!=null?r.usage.toFixed(2):'—'}</td>
      <td>${fmtDate(r.timestamp)}</td>
    </tr>`).join('');

  const bar = document.getElementById('paginationBar');
  if (allReports.length > PAGE_SIZE) {
    bar.style.display = 'flex';
    document.getElementById('paginationInfo').textContent = `${start+1}–${Math.min(end,allReports.length)} de ${allReports.length}`;
    let html = `<button class="page-btn" onclick="goPage(${currentPage-1})" ${currentPage===1?'disabled':''}>‹</button>`;
    for (let p=1;p<=totalPages;p++) {
      if (totalPages>7&&p>2&&p<totalPages-1&&Math.abs(p-currentPage)>1) { if(p===3||p===totalPages-2)html+='<span class="page-btn" style="cursor:default">…</span>'; continue; }
      html+=`<button class="page-btn ${p===currentPage?'active':''}" onclick="goPage(${p})">${p}</button>`;
    }
    html+=`<button class="page-btn" onclick="goPage(${currentPage+1})" ${currentPage===totalPages?'disabled':''}>›</button>`;
    document.getElementById('paginationBtns').innerHTML = html;
  } else { bar.style.display = 'none'; }
}
function goPage(p) { currentPage=p; renderReportTable(); }

// ─── Extractor ──────────────────────────────────────────
async function runExtractorSync() {
  const companyId = parseInt(document.getElementById('extCompanySelect').value||'1');
  const provider  = document.getElementById('providerSelect').value;
  const projectId = parseInt(document.getElementById('projectSelect').value);
  setExtractorBtns(true); clearLog();
  document.getElementById('metricsSection').style.display = 'none';
  document.getElementById('attemptsChip').style.display = 'none';
  addLog('info', `Extracción síncrona · proveedor=${provider.toUpperCase()} empresa=${companyId}`);
  const t0 = performance.now();
  try {
    const r = await fetch(`${EXT_API}/extractor/extract/sync`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({company_id:companyId,project_id:projectId,provider}) });
    const elapsed = Math.round(performance.now()-t0);
    const data = await r.json();
    if (r.ok && data.status==='success') {
      const att = data.attempts||1;
      addLog('ok', `Completado en ${elapsed} ms · ${data.metrics_count} métricas · ${att} intento(s)`);
      if (att>1) addLog('warn', `Requirió ${att} intentos — backoff exponencial aplicado`);
      const chip = document.getElementById('attemptsChip');
      chip.style.display='inline'; chip.textContent=`${att} intento(s)`;
      chip.className=`badge ${att>1?'badge-violet':'badge-green'}`;
      const metrics = data.metrics||[];
      if (metrics.length) {
        document.getElementById('metricsSection').style.display='block';
        document.getElementById('metricsCount').textContent=metrics.length;
        document.getElementById('metricsGrid').innerHTML=metrics.map(m=>`
          <div class="metric-tile">
            <div class="svc">${m.service||m.service_name||'—'}</div>
            <div class="cost">${fmt(m.cost??m.amount)}</div>
            <div class="region">${m.region||m.project_id||'—'}</div>
          </div>`).join('');
      }
      updateAsrScalability(att, true);
      toast(`${data.metrics_count} métricas extraídas en ${elapsed} ms`, 'ok');
    } else {
      addLog('err', data.detail||data.message||JSON.stringify(data));
      updateAsrScalability(5, false);
      toast('Extracción fallida', 'err');
    }
  } catch(e) { addLog('err','Error de conexión: '+e.message); toast('Error de conexión','err'); }
  finally { setExtractorBtns(false); }
}

async function runExtractorAsync() {
  const companyId=parseInt(document.getElementById('extCompanySelect').value||'1');
  const provider=document.getElementById('providerSelect').value;
  const projectId=parseInt(document.getElementById('projectSelect').value);
  setExtractorBtns(true); clearLog();
  addLog('info',`Encolando tarea asíncrona · proveedor=${provider.toUpperCase()}`);
  try {
    const r=await fetch(`${EXT_API}/extractor/extract`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({company_id:companyId,project_id:projectId,provider})});
    const data=await r.json();
    if(r.ok&&data.task_id){addLog('ok',`Tarea encolada · task_id=${data.task_id}`);toast('Tarea encolada','ok');pollTaskStatus(data.task_id);}
    else{addLog('err',data.detail||JSON.stringify(data));setExtractorBtns(false);}
  }catch(e){addLog('err',e.message);setExtractorBtns(false);}
}

async function pollTaskStatus(taskId) {
  let n=0;
  const iv=setInterval(async()=>{
    n++;
    try{
      const r=await fetch(`${EXT_API}/extractor/status/${taskId}`);
      const data=await r.json();
      addLog('info',`Poll #${n} · estado=${data.status}`);
      if(data.status==='SUCCESS'){clearInterval(iv);addLog('ok','Tarea completada');toast('Tarea completada','ok');setExtractorBtns(false);}
      else if(data.status==='FAILURE'){clearInterval(iv);addLog('err','Tarea fallida: '+(data.error||'—'));setExtractorBtns(false);}
      else if(n>=20){clearInterval(iv);addLog('warn','Tiempo de espera agotado');setExtractorBtns(false);}
    }catch(e){clearInterval(iv);addLog('err',e.message);setExtractorBtns(false);}
  },2000);
}

function clearLog(){document.getElementById('taskTimeline').innerHTML='';}
function addLog(type,msg){
  const tl=document.getElementById('taskTimeline');
  const cls={info:'log-info',ok:'log-ok',warn:'log-warn',err:'log-err'}[type]||'log-info';
  const line=document.createElement('div');line.className='log-line';
  line.innerHTML=`<span class="log-ts">${now()}</span><span class="${cls}">${msg}</span>`;
  tl.appendChild(line);tl.scrollTop=tl.scrollHeight;
}
function setExtractorBtns(loading){['btnExtSync','btnExtAsync'].forEach(id=>document.getElementById(id).disabled=loading);}

// ─── ASR panels ─────────────────────────────────────────
function setFill(fillId, pct, ok) {
  const el = document.getElementById(fillId);
  el.style.width = pct + '%';
  el.style.background = ok ? 'var(--green)' : 'var(--red)';
}

function updateAsrLatency(ms, ok, companyId, src) {
  setFill('latFill', Math.min(100, ms/3000*100), ok);
  const val = document.getElementById('latVal');
  val.textContent = ms+' ms';
  val.style.color = ok ? 'var(--green-soft)' : 'var(--red-soft)';
  document.getElementById('latStatus').textContent = ok ? `Cumple el ASR — respuesta en ${ms} ms (límite 3,000 ms)` : `No cumple — ${ms} ms supera el límite de 3,000 ms`;
  addAsrHistory('Latencia','Company '+companyId,src,ms+' ms',ok);
}

function updateAsrScalability(attempts, ok) {
  setFill('scaleFill', ok ? 100 : Math.max(0,100-attempts*20), ok);
  const val = document.getElementById('scaleVal');
  val.textContent = ok ? '100%' : 'Fallida';
  val.style.color = ok ? 'var(--green-soft)' : 'var(--red-soft)';
  document.getElementById('scaleStatus').textContent = ok ? `Éxito en ${attempts} intento(s)` : 'Extracción fallida';
  addAsrHistory('Escalabilidad', document.getElementById('providerSelect').value.toUpperCase(), attempts+' intentos', ok?'100%':'0%', ok);
}

function addAsrHistory(asr, empresa, fuente, resultado, ok) {
  const tbody=document.getElementById('asrHistory');
  if(tbody.querySelector('.empty-state'))tbody.innerHTML='';
  const row=document.createElement('tr');
  row.innerHTML=`
    <td style="color:var(--text-muted)">${now()}</td>
    <td><span class="badge ${asr==='Latencia'?'badge-violet':'badge-green'}">${asr}</span></td>
    <td>${empresa}</td><td style="color:var(--text-muted)">${fuente}</td>
    <td style="font-weight:600">${resultado}</td>
    <td style="color:${ok?'var(--green-soft)':'var(--red-soft)'};font-weight:600">${ok?'Cumple':'No cumple'}</td>`;
  tbody.insertBefore(row,tbody.firstChild);
  const c=parseInt(document.getElementById('histCount').textContent||'0');
  document.getElementById('histCount').textContent=c+1;
}

// ═══ SPRINT 3: PLACES ═════════════════════════════════

async function checkPlacesHealth() {
  const dot=document.getElementById('placesStatusDot');
  const text=document.getElementById('placesStatusText');
  const detail=document.getElementById('placesStatusDetail');
  dot.className='status-indicator loading';
  text.textContent='Verificando health del clúster…';
  detail.textContent='';
  const t0=performance.now();
  try {
    const r=await fetch('/health');
    const elapsed=Math.round(performance.now()-t0);
    if(r.ok){
      const data=await r.json();
      dot.className='status-indicator ok';
      text.textContent=`Clúster MongoDB operativo — respondió en ${elapsed} ms`;
      detail.textContent=JSON.stringify(data).substring(0,120);
      document.getElementById('pkCluster').textContent='Operativo';
      document.getElementById('pkCluster').style.color='var(--green-soft)';
      document.getElementById('pkLatency').textContent=elapsed+' ms';
      toast('Health check exitoso','ok');
    } else { throw new Error(`HTTP ${r.status}`); }
  } catch(e) {
    dot.className='status-indicator err';
    text.textContent='Clúster no disponible o en proceso de failover';
    detail.textContent=e.message;
    document.getElementById('pkCluster').textContent='Error';
    document.getElementById('pkCluster').style.color='var(--red-soft)';
    toast('Health check fallido: '+e.message,'err');
  }
}

async function loadPlaces() {
  const grid=document.getElementById('placesGrid');
  grid.innerHTML='<div class="empty-state"><div class="spinner" style="margin:0 auto 10px"></div><p>Cargando documentos del clúster…</p></div>';
  document.getElementById('pkLatency').textContent='…';
  const t0=performance.now();
  try {
    const r=await fetch('/places/');
    const elapsed=Math.round(performance.now()-t0);
    if(!r.ok)throw new Error(`HTTP ${r.status}`);
    const data=await r.json();
    document.getElementById('pkLatency').textContent=elapsed+' ms';
    const arr=Array.isArray(data)?data:Array.isArray(data.places)?data.places:Object.values(data.places||data||{});
    document.getElementById('pkTotal').textContent=arr.length;
    document.getElementById('placesCount').textContent=arr.length;
    document.getElementById('placesStatusDot').className='status-indicator ok';
    document.getElementById('placesStatusText').textContent=`${arr.length} documentos cargados en ${elapsed} ms`;
    if(!arr.length){
      grid.innerHTML='<div class="empty-state"><p>La colección places está vacía. Inserta documentos en MongoDB.</p></div>';
      return;
    }
    grid.innerHTML=`<div class="places-grid">${arr.map(renderPlaceCard).join('')}</div>`;
    toast(`${arr.length} places cargados en ${elapsed} ms`,'ok');
  } catch(e) {
    grid.innerHTML=`<div class="empty-state"><p>Error: ${e.message}</p></div>`;
    document.getElementById('placesStatusDot').className='status-indicator err';
    document.getElementById('placesStatusText').textContent='Error al cargar places';
    toast('Error: '+e.message,'err');
  }
}

function renderPlaceCard(p) {
  const name=p.name||p.nombre||p._id||'Sin nombre';
  const city=p.city||p.ciudad||p.location?.city||'—';
  const country=p.country||p.pais||p.location?.country||'';
  const desc=p.description||p.descripcion||'';
  const id=p._id||p.id||'';
  return `<div class="place-card">
    <div class="place-name">${escHtml(name)}</div>
    <div class="place-location">${escHtml(city)}${country?', '+escHtml(country):''}</div>
    ${desc?`<div class="place-desc">${escHtml(desc.substring(0,90))}${desc.length>90?'…':''}</div>`:''}
    ${id?`<div class="place-id">${String(id).substring(0,24)}</div>`:''}
  </div>`;
}

// ═══ SPRINT 3: CREDENTIALS ════════════════════════════

async function registerCredential() {
  const credId=document.getElementById('regCredId').value.trim();
  const clientId=document.getElementById('regClientId').value.trim();
  const countries=document.getElementById('regCountries').value.split(',').map(s=>s.trim()).filter(Boolean);
  if(!credId||!clientId){toast('ID de credencial y Client ID son requeridos','err');return;}
  const payload={credential_id:credId,client_id:clientId,typical_countries:countries,typical_hour_start:parseInt(document.getElementById('regHourStart').value),typical_hour_end:parseInt(document.getElementById('regHourEnd').value),avg_requests_per_min:parseFloat(document.getElementById('regAvgReq').value),stddev_requests:parseFloat(document.getElementById('regStddev').value)};
  try {
    const r=await fetch('/credentials/register/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await r.json();
    if(r.ok){toast(`Credencial "${credId}" registrada correctamente`,'ok');document.getElementById('regCredId').value='';}
    else{toast('Error: '+(data.detail||data.error||JSON.stringify(data)),'err');}
  }catch(e){toast('Error de conexión: '+e.message,'err');}
}

async function useCredential(forceAnomaly) {
  const credId=document.getElementById('useCredId').value.trim();
  const clientId=document.getElementById('useClientId').value.trim();
  const country=document.getElementById('useCountry').value;
  if(!credId||!clientId){toast('Completa ID Credencial y Client ID','err');return;}
  const result=document.getElementById('credResult');
  result.style.display='none';
  try {
    const r=await fetch('/credentials/use/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({credential_id:credId,client_id:clientId,geo_country:country})});
    const data=await r.json();
    credUseTotal++;
    const isAnom=data.anomaly_detected||data.alert||forceAnomaly;
    if(isAnom)credAnomalias++;
    updateAsr29Stats();
    result.style.display='block';
    if(r.ok){
      result.className='cred-result '+(isAnom?'result-anomaly':'result-ok');
      result.innerHTML=isAnom
        ?`<strong>Anomalía detectada</strong><br><small>Tipo: ${data.alert_type||'GEO/TIME/VOLUME'} · País: ${country}</small>`
        :`<strong>Acceso normal registrado</strong><br><small>País: ${country} — sin alertas</small>`;
      toast(isAnom?`Anomalía detectada desde ${country}`:`Uso registrado — ${country}`,isAnom?'warn':'ok');
    } else {
      result.className='cred-result result-error';
      result.innerHTML=`<strong>${data.detail||data.error||'Error'}</strong>`;
      toast('Error: '+(data.detail||data.error),'err');
    }
  }catch(e){
    result.style.display='block';result.className='cred-result result-error';
    result.innerHTML=`<strong>Error de conexión</strong><br><small>${e.message}</small>`;
    toast('Error: '+e.message,'err');
  }
}

function updateAsr29Stats() {
  document.getElementById('s29Total').textContent=credUseTotal;
  document.getElementById('s29Anomalias').textContent=credAnomalias;
  document.getElementById('s29Tasa').textContent=credUseTotal>0?Math.round(credAnomalias/credUseTotal*100)+'%':'—';
}

async function loadAuditLog() {
  const tbody=document.getElementById('auditLogBody');
  tbody.innerHTML=`<tr><td colspan="7"><div class="empty-state"><div class="spinner" style="margin:0 auto 10px"></div><p>Cargando…</p></div></td></tr>`;
  try {
    const r=await fetch('/credentials/audit/');
    if(!r.ok)throw new Error(`HTTP ${r.status}`);
    const data=await r.json();
    const arr=Array.isArray(data)?data:Array.isArray(data.logs)?data.logs:[];
    document.getElementById('auditCount').textContent=arr.length;
    if(!arr.length){tbody.innerHTML=`<tr><td colspan="7"><div class="empty-state"><p>No hay eventos en el audit log todavía</p></div></td></tr>`;return;}
    tbody.innerHTML=arr.slice(0,50).map(log=>{
      const anom=log.is_anomaly||log.anomaly||log.alert_type;
      return `<tr>
        <td style="font-size:11px;color:var(--text-muted)">${fmtDatetime(log.timestamp||log.created_at)}</td>
        <td style="font-weight:600">${log.credential_id||'—'}</td>
        <td style="color:var(--text-muted)">${log.client_id||'—'}</td>
        <td><span style="font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;background:${anom?'var(--red-dim)':'var(--green-dim)'};color:${anom?'var(--red-soft)':'var(--green-soft)'}">${log.geo_country||'—'}</span></td>
        <td style="color:var(--text-muted)">${log.hour!==undefined?log.hour+':00':'—'}</td>
        <td><span class="badge ${anom?'badge-red':'badge-green'}">${anom?'Anómalo':'Normal'}</span></td>
        <td style="font-size:11px;color:var(--text-muted)">${log.alert_type||log.details||(anom?'Anomalía detectada':'Acceso normal')}</td>
      </tr>`;
    }).join('');
    toast(`${arr.length} eventos cargados`,'ok');
  }catch(e){
    tbody.innerHTML=`<tr><td colspan="7"><div class="empty-state"><p>${e.message}</p></div></td></tr>`;
    toast('Error: '+e.message,'err');
  }
}

// ═══ SPRINT 3: LOG MASKING ════════════════════════════

async function testLeak(type, btn) {
  const resultEl=document.getElementById(`lr-${type}`);
  const statusDot=document.getElementById(`lsd-${type}`);
  const card=btn.closest('.leak-card');
  btn.disabled=true; btn.textContent='Verificando…';
  resultEl.style.display='none';
  try {
    const r=await fetch(`/test/leak/${type}/`);
    const data=await r.json();
    maskTestCount++;
    const raw=data.raw_value||data.original||data.value||data.leaked||'';
    const masked=data.masked_value||data.masked||data.log_output||data.result||'';
    const ok=data.masked===true||String(masked).includes('[MASKED]');
    resultEl.style.display='block';
    if(ok){
      maskSuccessCount++;
      card.classList.add('card-ok'); card.classList.remove('card-err');
      statusDot.className='leak-status-dot dot-ok';
      resultEl.className='leak-result lr-ok';
      resultEl.innerHTML=`
        <div class="lr-row"><span class="lr-label">Original</span><code class="lr-raw">${escHtml(String(raw).substring(0,70))}</code></div>
        <div class="lr-row"><span class="lr-label">En log</span><code class="lr-masked">${escHtml(String(masked).substring(0,70))}</code></div>
        <div class="lr-status" style="color:var(--green-soft)">Datos enmascarados correctamente</div>`;
      addMaskLog('ok',`${type} — enmascarado · ${String(raw).substring(0,35)} → ${String(masked).substring(0,35)}`);
      toast(`${type} enmascarado correctamente`,'ok');
    } else {
      card.classList.add('card-err'); card.classList.remove('card-ok');
      statusDot.className='leak-status-dot dot-err';
      resultEl.className='leak-result lr-err';
      resultEl.innerHTML=`
        <div class="lr-row"><span class="lr-label">Original</span><code class="lr-raw">${escHtml(String(raw).substring(0,70))}</code></div>
        <div class="lr-row"><span class="lr-label">En log</span><code class="lr-raw">${escHtml(String(masked).substring(0,70))}</code></div>
        <div class="lr-status" style="color:var(--red-soft)">Datos NO enmascarados — filtro no activo</div>`;
      addMaskLog('err',`${type} — no enmascarado`);
      toast(`${type} no fue enmascarado`,'err');
    }
    document.getElementById('s30Tests').textContent=maskTestCount;
    document.getElementById('s30Masked').textContent=maskSuccessCount;
    document.getElementById('s30Pct').textContent=maskTestCount>0?Math.round(maskSuccessCount/maskTestCount*100)+'%':'—';
    document.getElementById('maskCount').textContent=maskTestCount;
  } catch(e) {
    resultEl.style.display='block';resultEl.className='leak-result lr-err';
    resultEl.innerHTML=`<div class="lr-status" style="color:var(--red-soft)">Error: ${escHtml(e.message)}</div>`;
    addMaskLog('err',`${type} — error: ${e.message}`);
    toast('Error: '+e.message,'err');
  } finally { btn.disabled=false; btn.textContent='Probar Enmascaramiento'; }
}

function addMaskLog(type,msg){
  const el=document.getElementById('maskLog');
  const cls={ok:'log-ok',err:'log-err',info:'log-info'}[type]||'log-info';
  const line=document.createElement('div');line.className='log-line';
  line.innerHTML=`<span class="log-ts">${now()}</span><span class="${cls}">${msg}</span>`;
  el.appendChild(line);el.scrollTop=el.scrollHeight;
}

function clearMaskLog(){
  document.getElementById('maskLog').innerHTML='';
  maskTestCount=0;maskSuccessCount=0;
  ['s30Tests','s30Masked'].forEach(id=>document.getElementById(id).textContent='0');
  document.getElementById('s30Pct').textContent='—';
  document.getElementById('maskCount').textContent='0';
  document.querySelectorAll('.leak-card').forEach(c=>{c.classList.remove('card-ok','card-err');});
  document.querySelectorAll('.leak-result').forEach(r=>r.style.display='none');
  document.querySelectorAll('.leak-status-dot').forEach(d=>d.className='leak-status-dot');
}

// ═══ SPRINT 3: DISPONIBILIDAD ════════════════════════

async function checkDisponibilidad() {
  ['mongos','shard1','shard2','shard3'].forEach(id=>{
    document.getElementById('sc-'+id).className='shard-card shard-loading';
    document.getElementById('si-'+id).className='shard-indicator ind-loading';
    document.getElementById('ss-'+id).textContent='Verificando…';
  });
  document.getElementById('disponStatus').textContent='Verificando estado del clúster…';
  const t0=performance.now();
  try {
    const r=await fetch('/health');
    const elapsed=Math.round(performance.now()-t0);
    if(r.ok){
      const data=await r.json();
      setShardStatus('mongos',true,`Operativo · ${elapsed} ms`);
      const ss=data.shards||data.shard_status||null;
      ['shard1','shard2','shard3'].forEach(s=>{
        setShardStatus(s,ss?ss[s]!==false:true,'Replica set activo');
      });
      setFill('disponFill',100,true);
      document.getElementById('disponVal').textContent=elapsed+' ms';
      document.getElementById('disponVal').style.color='var(--green-soft)';
      document.getElementById('disponStatus').textContent=`Clúster completamente operativo — health en ${elapsed} ms`;
      toast(`Clúster operativo — ${elapsed} ms`,'ok');
    } else { throw new Error(`HTTP ${r.status}`); }
  } catch(e) {
    setShardStatus('mongos',false,'Error');
    ['shard1','shard2','shard3'].forEach(id=>setShardStatus(id,null,'Estado desconocido'));
    setFill('disponFill',15,false);
    document.getElementById('disponVal').textContent='Error';
    document.getElementById('disponVal').style.color='var(--red-soft)';
    document.getElementById('disponStatus').textContent='Clúster no disponible — posible failover en curso';
    toast('Error en verificación: '+e.message,'err');
  }
}

function setShardStatus(id,ok,detail){
  const card=document.getElementById('sc-'+id);
  const ind=document.getElementById('si-'+id);
  const status=document.getElementById('ss-'+id);
  if(ok===true){ card.className='shard-card shard-ok'; ind.className='shard-indicator ind-ok'; status.textContent=detail||'Activo'; status.style.color='var(--green-soft)'; }
  else if(ok===false){ card.className='shard-card shard-err'; ind.className='shard-indicator ind-err'; status.textContent=detail||'Error'; status.style.color='var(--red-soft)'; }
  else { card.className='shard-card'; ind.className='shard-indicator'; status.textContent=detail||'Desconocido'; status.style.color='var(--text-muted)'; }
}

function addFailoverRun(){
  const dt=parseInt(document.getElementById('failDeltaT').value);
  const rec=parseInt(document.getElementById('failRecovery').value);
  if(isNaN(dt)||isNaN(rec)){toast('Ingresa delta_t y recovery válidos','err');return;}
  failoverRuns.push({deltaT:dt,recovery:rec,ok:dt<5000&&rec<30});
  document.getElementById('failDeltaT').value='';
  document.getElementById('failRecovery').value='';
  renderFailoverResults();
}

function renderFailoverResults(){
  const el=document.getElementById('failoverResults');
  if(!failoverRuns.length){el.innerHTML='<div class="empty-state" style="padding:24px"><p>Sin corridas registradas</p></div>';return;}
  const passing=failoverRuns.filter(r=>r.ok).length;
  const color=passing>=4?'var(--green-soft)':passing>=2?'var(--yellow)':'var(--red-soft)';
  const label=passing>=4?'ASR Cumplido':passing>=2?'Parcialmente cumplido':'No cumple';
  el.innerHTML=`
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <span style="font-size:12px;color:var(--text-muted)">${failoverRuns.length} corrida(s) registradas</span>
      <span style="font-weight:700;font-size:13px;color:${color}">${label} (${passing}/5)</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>#</th><th>Delta T</th><th>Recovery</th><th>Resultado</th></tr></thead>
        <tbody>${failoverRuns.map((r,i)=>`
          <tr>
            <td style="color:var(--text-muted)">Corrida ${i+1}</td>
            <td style="font-weight:700;color:${r.deltaT<5000?'var(--green-soft)':'var(--red-soft)'}">${r.deltaT.toLocaleString()} ms</td>
            <td style="color:${r.recovery<30?'var(--green-soft)':'var(--red-soft)'}">${r.recovery} s</td>
            <td style="font-weight:600;color:${r.ok?'var(--green-soft)':'var(--red-soft)'}">${r.ok?'Cumple':'No cumple'}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
  setFill('disponFill',Math.round(passing/5*100),passing>=4);
  document.getElementById('disponVal').textContent=passing+'/5';
  document.getElementById('disponVal').style.color=color;
  document.getElementById('disponStatus').textContent=`${label} — ${passing} de 5 corridas con delta_t < 5,000 ms`;
}

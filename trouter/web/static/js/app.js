// travelrouter dashboard — vanilla JS, no build step (Pi Zero friendly).
const CSRF = document.querySelector('meta[name=csrf]').content;
const $ = (s, r = document) => r.querySelector(s);

async function api(path, opts = {}) {
  opts.headers = Object.assign({'Content-Type': 'application/json',
    'X-CSRF-Token': CSRF}, opts.headers || {});
  const r = await fetch(path, opts);
  if (r.status === 401) { location.href = '/login'; return; }
  return r;
}
const get = p => api(p).then(r => r.json());
const post = (p, b) => api(p, {method: 'POST', body: JSON.stringify(b || {})}).then(r => r.json());

const fmtUptime = s => {
  const d = Math.floor(s/86400), h = Math.floor(s%86400/3600), m = Math.floor(s%3600/60);
  return (d?d+'d ':'') + h + 'h ' + m + 'm';
};

// ---- view router -----------------------------------------------------
const views = {};
let current = 'dashboard';
document.querySelectorAll('.nav').forEach(a => a.addEventListener('click', () => {
  document.querySelectorAll('.nav').forEach(n => n.classList.remove('active'));
  a.classList.add('active');
  current = a.dataset.view;
  $('#viewTitle').textContent = a.textContent;
  render();
}));
$('#logout').addEventListener('click', async () => { await post('/api/logout'); location.href='/login'; });

function render() { (views[current] || (() => {}))(); }

// ---- dashboard -------------------------------------------------------
views.dashboard = async () => {
  const s = await get('/api/system/summary');
  if (!s) return;
  const aps = await get('/api/aps');
  const clients = await get('/api/clients');
  $('#view').innerHTML = `
    <div class="grid">
      <div class="card"><h3>Uptime</h3><div class="metric">${fmtUptime(s.uptime_s)}</div></div>
      <div class="card"><h3>CPU temp</h3><div class="metric">${s.cpu_temp_c ?? '–'}°C</div>
        <div class="sub">load ${s.loadavg.join(' / ')}</div></div>
      <div class="card"><h3>Memory</h3><div class="metric">${s.mem.pct}%</div>
        <div class="sub">${s.mem.used_mb} / ${s.mem.total_mb} MB</div></div>
      <div class="card"><h3>Disk</h3><div class="metric">${s.disk.pct}%</div>
        <div class="sub">${s.disk.used_gb} / ${s.disk.total_gb} GB</div></div>
      <div class="card"><h3>Active APs</h3><div class="metric">${aps.filter(a=>a.enabled).length}</div>
        <div class="sub">${aps.length} configured</div></div>
      <div class="card"><h3>Clients</h3><div class="metric">${clients.length}</div></div>
      <div class="card"><h3>Kernel</h3><div class="sub">${s.kernel}</div>
        <div class="sub">${s.os}</div></div>
    </div>`;
};

// ---- interfaces ------------------------------------------------------
views.interfaces = async () => {
  const ifs = await get('/api/interfaces');
  $('#view').innerHTML = `<div class="card"><table>
    <tr><th>Name</th><th>Type</th><th>Driver</th><th>Bands</th><th>AP</th><th>Status</th></tr>
    ${ifs.map(i => `<tr>
      <td>${i.last_name||'–'}<div class="sub">${i.mac}</div></td>
      <td>${i.kind}</td><td>${i.driver||'–'}</td>
      <td>${(i.capabilities.bands||[]).join(', ')||'–'}</td>
      <td>${i.capabilities.ap_supported ? 'yes' : '–'}</td>
      <td><span class="tag ${i.present?'on':'off'}">${i.present?'present':'absent'}</span></td>
    </tr>`).join('')}</table></div>`;
};

// ---- access points ---------------------------------------------------
views.aps = async () => {
  const aps = await get('/api/aps');
  $('#view').innerHTML = `<div class="card"><table>
    <tr><th>Name</th><th>SSID</th><th>Band/Ch</th><th>Policy</th><th>Status</th></tr>
    ${aps.map(a => `<tr><td>${a.name}</td><td>${a.ssid}</td>
      <td>${a.band}GHz / ${a.channel}</td><td>${a.routing_policy}</td>
      <td><span class="tag ${a.enabled?'on':'off'}">${a.enabled?'on':'off'}</span></td></tr>`).join('')}
    </table>
    <p class="sub" style="margin-top:12px">Editing APs uses the transactional
    apply flow: validate → apply → confirm within ${'{'}timeout{'}'}s or auto-revert.
    Wire the edit form to POST /api/aps/apply, then call beginConfirm(resp).</p>
    </div>`;
};

// ---- clients ---------------------------------------------------------
views.clients = async () => {
  const cs = await get('/api/clients');
  $('#view').innerHTML = `<div class="card"><table>
    <tr><th>Host</th><th>IP</th><th>MAC</th><th>Actions</th></tr>
    ${cs.map(c => `<tr><td>${c.label||c.hostname||'?'}</td><td>${c.ip}</td>
      <td>${c.mac}</td>
      <td class="row">
        <button class="btn" onclick="clientAction('${c.mac}','${c.blocked?'allow':'block'}')">${c.blocked?'Allow':'Block'}</button>
      </td></tr>`).join('')}</table></div>`;
};
window.clientAction = async (mac, action) => { await post(`/api/clients/${mac}/action`, {action}); render(); };

// ---- system ----------------------------------------------------------
views.system = async () => {
  $('#view').innerHTML = `<div class="card row" style="gap:12px;flex-wrap:wrap">
    <button class="btn" onclick="post('/api/system/restart-networking')">Restart networking</button>
    <button class="btn danger" onclick="confirm('Reboot?')&&post('/api/system/reboot')">Reboot</button>
    <button class="btn danger" onclick="confirm('Shut down?')&&post('/api/system/shutdown')">Shutdown</button>
  </div>`;
};
views.vpn = () => $('#view').innerHTML = `<div class="card sub">VPN profiles: GET/POST /api/vpn. Per-AP policy is set on each AP.</div>`;
views.files = () => $('#view').innerHTML = `<div class="card sub">File manager API live at /api/files (sandboxed to /srv/files).</div>`;
views.scripts = () => $('#view').innerHTML = `<div class="card sub">Script runner API live at /api/scripts (sandboxed to /home/pi/scripts).</div>`;

// ---- recommendations -------------------------------------------------
const dismissed = new Set();
async function loadRecs() {
  const recs = await get('/api/recommendations');
  $('#recs').innerHTML = (recs||[]).filter(r => !dismissed.has(r.id)).map(r => `
    <div class="rec"><div><b>${r.title}</b><div class="sub">${r.body}</div></div>
    <span class="x" onclick="dismissRec('${r.id}')">✕</span></div>`).join('');
}
window.dismissRec = id => { dismissed.add(id); loadRecs(); };

// ---- confirmation countdown (anti-lockout) ---------------------------
let confirmTimer = null;
window.beginConfirm = (resp) => {
  if (!resp || !resp.confirm_required) return;
  const overlay = $('#confirmOverlay');
  overlay.classList.remove('hidden');
  let remaining = Math.max(1, (resp.deadline - Math.floor(Date.now()/1000)));
  $('#countdown').textContent = remaining;
  clearInterval(confirmTimer);
  confirmTimer = setInterval(() => {
    remaining--; $('#countdown').textContent = remaining;
    if (remaining <= 0) { clearInterval(confirmTimer); overlay.classList.add('hidden'); }
  }, 1000);
  $('#confirmBtn').onclick = async () => {
    await post('/api/aps/confirm', {txid: resp.txid});
    clearInterval(confirmTimer); overlay.classList.add('hidden'); render();
  };
  $('#revertBtn').onclick = async () => {
    await post('/api/aps/rollback', {txid: resp.txid});
    clearInterval(confirmTimer); overlay.classList.add('hidden'); render();
  };
};

// Resume a pending confirmation after a page reload.
async function resumePending() {
  const p = await get('/api/aps/pending');
  if (p && p.id && p.state === 'applied' && p.deadline) {
    beginConfirm({confirm_required: true, txid: p.id, deadline: p.deadline});
  }
}

// ---- live updates ----------------------------------------------------
function connectEvents() {
  const es = new EventSource('/api/events');
  es.onmessage = e => { try { const d = JSON.parse(e.data);
    if (d.type === 'interfaces-changed') render(); } catch (_) {} };
  es.onerror = () => { es.close(); setTimeout(connectEvents, 5000); };
}

async function pollStatus() {
  const s = await get('/api/system/summary');
  const pill = $('#netStatus');
  if (s) { pill.textContent = 'online · ' + fmtUptime(s.uptime_s); pill.className = 'status-pill ok'; }
  else { pill.textContent = 'offline'; pill.className = 'status-pill bad'; }
}

// boot
render(); loadRecs(); resumePending(); connectEvents(); pollStatus();
setInterval(() => { if (current === 'dashboard') render(); pollStatus(); loadRecs(); }, 5000);

/**
 * ToolStore Management SPA — Application Logic
 * Talks to the local management API (same origin, port 8765).
 */

// ═══════════════════════════════════════════════════════════════════════
// State
// ═══════════════════════════════════════════════════════════════════════

let state = {
  config: null,
  mcpServers: {},
  skills: {},
  tools: {},
};

// ═══════════════════════════════════════════════════════════════════════
// API helpers
// ═══════════════════════════════════════════════════════════════════════

const api = {
  async _fetch(method, path, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(path, opts);
    const data = await res.json();
    if (!res.ok && data.error) throw new Error(data.error);
    return data;
  },
  getConfig()           { return this._fetch('GET', '/api/config'); },
  listMcp()             { return this._fetch('GET', '/api/mcp/servers'); },
  addMcp(cfg)           { return this._fetch('POST', '/api/mcp/servers', cfg); },
  connectMcp(id)        { return this._fetch('POST', `/api/mcp/servers/${id}/connect`); },
  disconnectMcp(id)     { return this._fetch('POST', `/api/mcp/servers/${id}/disconnect`); },
  removeMcp(id)         { return this._fetch('DELETE', `/api/mcp/servers/${id}`); },
  listSkills()          { return this._fetch('GET', '/api/skills'); },
  registerSkill(cfg)    { return this._fetch('POST', '/api/skills', cfg); },
  removeSkill(name)     { return this._fetch('DELETE', `/api/skills/${name}`); },
  patchTool(name, cfg)  { return this._fetch('PATCH', `/api/tools/${name}`, cfg); },
};

// ═══════════════════════════════════════════════════════════════════════
// Toast
// ═══════════════════════════════════════════════════════════════════════

function toast(msg, type) {
  type = type || 'success';
  const el = document.createElement('div');
  el.className = 'ts-toast ' + type;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(function () { el.remove(); }, 3000);
}

// ═══════════════════════════════════════════════════════════════════════
// Tabs
// ═══════════════════════════════════════════════════════════════════════

document.querySelectorAll('.ts-tab').forEach(function (btn) {
  btn.addEventListener('click', function () {
    document.querySelectorAll('.ts-tab').forEach(function (b) { b.classList.remove('active'); });
    document.querySelectorAll('.ts-tab-panel').forEach(function (p) { p.classList.remove('active'); });
    btn.classList.add('active');
    var tab = btn.dataset.tab;
    var panel = document.getElementById('tab-' + tab);
    if (panel) panel.classList.add('active');
    if (tab === 'mcp') refreshMcp();
    if (tab === 'skills') refreshSkills();
    if (tab === 'tools') refreshTools();
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Modals
// ═══════════════════════════════════════════════════════════════════════

function openModal(id) {
  document.getElementById('modal-overlay').classList.remove('hidden');
  document.getElementById(id).classList.remove('hidden');
}

function closeModal(id) {
  document.getElementById('modal-overlay').classList.add('hidden');
  document.getElementById(id).classList.add('hidden');
}

document.getElementById('modal-overlay').addEventListener('click', function () {
  document.querySelectorAll('.ts-modal:not(.hidden)').forEach(function (m) { closeModal(m.id); });
});

document.querySelectorAll('.ts-modal-close, [data-close]').forEach(function (el) {
  el.addEventListener('click', function () {
    closeModal(el.dataset.close || el.closest('.ts-modal').id);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// MCP transport toggle
// ═══════════════════════════════════════════════════════════════════════

function showMcpFields(transport) {
  document.getElementById('mcp-sse-fields').classList.toggle('hidden', transport !== 'sse');
  document.getElementById('mcp-stdio-fields').classList.toggle('hidden', transport !== 'stdio');
  document.getElementById('mcp-folder-fields').classList.toggle('hidden', transport !== 'folder');
}

document.getElementById('mcp-transport').addEventListener('change', function () {
  showMcpFields(this.value);
});

// ═══════════════════════════════════════════════════════════════════════
// Load all
// ═══════════════════════════════════════════════════════════════════════

async function loadAll() {
  updateStatus('loading', 'loading…');
  try {
    state.config = await api.getConfig();
    state.tools = state.config.tools || {};
    state.skills = state.config.skills || {};
    state.mcpServers = await api.listMcp();
    updateStatus('ok', 'connected');
  } catch (e) {
    updateStatus('error', 'server unreachable');
  }
  refreshMcp();
}

function updateStatus(type, text) {
  var dot = document.getElementById('ts-status');
  var txt = document.getElementById('ts-status-text');
  dot.className = 'ts-status-dot';
  if (type === 'ok') dot.style.background = 'var(--ts-success)';
  if (type === 'loading') dot.style.background = 'var(--ts-warn)';
  if (type === 'error') dot.style.background = 'var(--ts-danger)';
  txt.textContent = text;
}

// ═══════════════════════════════════════════════════════════════════════
// MCP Servers tab
// ═══════════════════════════════════════════════════════════════════════

async function refreshMcp() {
  try {
    state.mcpServers = await api.listMcp();
  } catch (e) { /* keep stale data */ }

  var list = document.getElementById('mcp-list');
  var empty = document.getElementById('mcp-empty');
  var ids = Object.keys(state.mcpServers);

  if (ids.length === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  list.innerHTML = ids.map(function (id) {
    var srv = state.mcpServers[id];
    return renderMcpCard(id, srv);
  }).join('');
}

function renderMcpCard(id, srv) {
  var transport = srv.transport || 'stdio';
  var transportDetail = transport === 'stdio'
    ? esc(srv.command || '?') + ' ' + esc((srv.args || []).join(' '))
    : esc(srv.url || '?');

  var statusClass = srv.status || 'disconnected';
  var toolCount = srv.tools_count || 0;

  // Collect tools belonging to this MCP server
  var toolRows = '';
  var prefix = 'mcp:' + id;
  Object.keys(state.tools).forEach(function (tn) {
    var t = state.tools[tn];
    if (t.source === prefix) {
      toolRows += renderToolRow(tn, t);
    }
  });

  var toolsSection = toolRows
    ? '<div class="ts-card-tools">' + toolRows + '</div>'
    : '';

  return '<div class="ts-card">'
    + '<div class="ts-card-header">'
    + '<div>'
    + '<div class="ts-card-title">' + esc(id) + '</div>'
    + '<div class="ts-card-subtitle">' + esc(transportDetail) + '</div>'
    + '</div>'
    + '<div style="display:flex;align-items:center;gap:8px;">'
    + '<span class="ts-status-badge ' + statusClass + '">' + statusClass + '</span>'
    + '<span class="ts-muted" style="font-size:12px;">' + toolCount + ' tools</span>'
    + '</div>'
    + '</div>'
    + '<div class="ts-card-body">Transport: ' + esc(transport) + '</div>'
    + toolsSection
    + '<div style="margin-top:12px;display:flex;gap:8px;">'
    + (statusClass === 'disconnected'
      ? '<button class="ts-btn ts-btn-primary ts-btn-sm" onclick="connectMcp(\'' + escAttr(id) + '\')">Connect</button>'
      : '<button class="ts-btn ts-btn-ghost ts-btn-sm" onclick="disconnectMcp(\'' + escAttr(id) + '\')">Disconnect</button>')
    + '<button class="ts-btn ts-btn-danger ts-btn-sm" onclick="removeMcp(\'' + escAttr(id) + '\')">Remove</button>'
    + '</div>'
    + '</div>';
}

// ═══════════════════════════════════════════════════════════════════════
// Tool row renderer (shared by MCP + All Tools)
// ═══════════════════════════════════════════════════════════════════════

function renderToolRow(name, tool) {
  var exp = tool.exposure || 'secondary';
  return '<div class="ts-tool-row">'
    + '<div class="ts-tool-info">'
    + '<div class="ts-tool-name">' + esc(name) + '</div>'
    + '<div class="ts-tool-desc">' + esc(tool.description || '') + '</div>'
    + '</div>'
    + '<div class="ts-tool-controls">'
    + '<span class="ts-exposure ' + exp + '" onclick="cycleExposure(\'' + escAttr(name) + '\',event)" title="Click to cycle: primary → secondary → store → disabled">' + exp + '</span>'
    + '</div>'
    + '</div>';
}

// ═══════════════════════════════════════════════════════════════════════
// Cycle exposure
// ═══════════════════════════════════════════════════════════════════════

var EXPOSURE_ORDER = ['primary', 'secondary', 'store', 'disabled'];

async function cycleExposure(name, event) {
  var tool = state.tools[name];
  if (!tool) return;
  var current = tool.exposure || 'secondary';
  var idx = EXPOSURE_ORDER.indexOf(current);
  var next = EXPOSURE_ORDER[(idx + 1) % EXPOSURE_ORDER.length];
  try {
    await api.patchTool(name, { exposure: next });
    tool.exposure = next;
    state.tools[name] = tool;
    // Update badge inline without full re-render
    var badge = event.target;
    badge.textContent = next;
    badge.className = 'ts-exposure ' + next;
    toast(esc(name) + ' → ' + next);
  } catch (e) {
    toast('Failed to update: ' + e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════════
// MCP actions
// ═══════════════════════════════════════════════════════════════════════

async function connectMcp(id) {
  try {
    var res = await api.connectMcp(id);
    if (res.tools) {
      res.tools.forEach(function (t) {
        state.tools[t.name] = {
          source: 'mcp:' + id,
          enabled: true,
          exposure: 'secondary',
          parallel_safe: false,
          subagent_safe: false,
          description: t.description || '',
        };
      });
    }
    toast('Connected: ' + esc(id) + ' (' + (res.tools ? res.tools.length : 0) + ' tools)');
    refreshMcp();
  } catch (e) {
    toast('Connection failed: ' + e.message, 'error');
  }
}

async function disconnectMcp(id) {
  try {
    await api.disconnectMcp(id);
    state.mcpServers[id].status = 'disconnected';
    toast('Disconnected: ' + esc(id));
    refreshMcp();
  } catch (e) {
    toast('Disconnect failed: ' + e.message, 'error');
  }
}

async function removeMcp(id) {
  if (!confirm('Remove MCP server "' + id + '" and all its tools?')) return;
  try {
    await api.removeMcp(id);
    delete state.mcpServers[id];
    // Remove tools
    var prefix = 'mcp:' + id;
    Object.keys(state.tools).forEach(function (k) {
      if (state.tools[k].source === prefix) delete state.tools[k];
    });
    toast('Removed: ' + esc(id));
    refreshMcp();
  } catch (e) {
    toast('Remove failed: ' + e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Connect to MCP form
// ═══════════════════════════════════════════════════════════════════════

document.getElementById('btn-connect-mcp').addEventListener('click', function () {
  document.getElementById('form-mcp').reset();
  document.getElementById('mcp-transport').value = 'sse';
  showMcpFields('sse');
  openModal('modal-mcp');
});

document.getElementById('form-mcp').addEventListener('submit', async function (e) {
  e.preventDefault();
  var fd = new FormData(this);
  var payload = {
    server_id: fd.get('server_id').trim(),
    transport: fd.get('transport'),
    auto_connect: fd.get('auto_connect') === 'on',
    exposure_default: fd.get('exposure_default'),
  };
  if (payload.transport === 'stdio') {
    payload.command = fd.get('command').trim();
    payload.args = fd.get('args').trim().split(/\s+/).filter(Boolean);
  } else if (payload.transport === 'folder') {
    payload.folder = fd.get('folder').trim();
    payload.command = fd.get('command').trim();
    payload.args = fd.get('args').trim().split(/\s+/).filter(Boolean);
    payload.sub_transport = fd.get('sub_transport');
    payload.url = fd.get('url').trim();
  } else {
    payload.url = fd.get('url').trim();
  }
  var envRaw = fd.get('env').trim();
  if (envRaw) {
    var env = {};
    envRaw.split('\n').forEach(function (line) {
      var parts = line.split('=');
      if (parts.length >= 2) env[parts[0].trim()] = parts.slice(1).join('=').trim();
    });
    payload.env = env;
  }
  try {
    var res = await api.addMcp(payload);
    if (res.tools) {
      res.tools.forEach(function (t) {
        state.tools[t.name] = {
          source: 'mcp:' + res.server_id,
          enabled: true,
          exposure: payload.exposure_default,
          parallel_safe: false,
          subagent_safe: false,
          description: t.description || '',
        };
      });
    }
    var msg = 'Connected: ' + esc(res.server_id);
    if (res.tools_discovered) msg += ' (' + res.tools_discovered + ' tools)';
    if (res.connection_error) msg += ' [warn: ' + res.connection_error + ']';
    toast(msg, res.connection_error ? 'error' : 'success');
    closeModal('modal-mcp');
    refreshMcp();
  } catch (err) {
    toast('Failed: ' + err.message, 'error');
  }
});

// ═══════════════════════════════════════════════════════════════════════
// Refresh MCP button
// ═══════════════════════════════════════════════════════════════════════

document.getElementById('btn-refresh-mcp').addEventListener('click', function () {
  refreshMcp();
  toast('Refreshed');
});

// ═══════════════════════════════════════════════════════════════════════
// Skills tab
// ═══════════════════════════════════════════════════════════════════════

async function refreshSkills() {
  try {
    var skills = await api.listSkills();
    state.skills = skills || {};
  } catch (e) { /* keep stale */ }

  var list = document.getElementById('skill-list');
  var empty = document.getElementById('skill-empty');
  var names = Object.keys(state.skills);

  if (names.length === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  list.innerHTML = names.map(function (name) {
    var sk = state.skills[name];
    var exp = sk.exposure || 'secondary';
    return '<div class="ts-card">'
      + '<div class="ts-card-header">'
      + '<div>'
      + '<div class="ts-card-title">' + esc(name) + '</div>'
      + '<div class="ts-card-subtitle">' + esc(sk.description || '') + '</div>'
      + '</div>'
      + '<div style="display:flex;align-items:center;gap:8px;">'
      + '<span class="ts-exposure ' + exp + '" onclick="cycleExposure(\'' + escAttr(name) + '\',event)">' + exp + '</span>'
      + '<button class="ts-btn ts-btn-danger ts-btn-sm" onclick="removeSkill(\'' + escAttr(name) + '\')">Remove</button>'
      + '</div>'
      + '</div>'
      + '</div>';
  }).join('');
}

async function removeSkill(name) {
  if (!confirm('Remove skill "' + name + '"?')) return;
  try {
    await api.removeSkill(name);
    delete state.skills[name];
    delete state.tools[name];
    toast('Removed: ' + esc(name));
    refreshSkills();
  } catch (e) {
    toast('Remove failed: ' + e.message, 'error');
  }
}

document.getElementById('btn-register-skill').addEventListener('click', function () {
  document.getElementById('form-skill').reset();
  openModal('modal-skill');
});

document.getElementById('form-skill').addEventListener('submit', async function (e) {
  e.preventDefault();
  var fd = new FormData(this);
  var payload = {
    name: fd.get('name').trim(),
    description: fd.get('description').trim(),
    path: fd.get('path').trim(),
    exposure: fd.get('exposure'),
    parallel_safe: fd.get('parallel_safe') === 'on',
    subagent_safe: fd.get('subagent_safe') === 'on',
  };
  try {
    await api.registerSkill(payload);
    state.skills[payload.name] = payload;
    state.tools[payload.name] = {
      source: 'skill:' + payload.name,
      enabled: true,
      exposure: payload.exposure,
      parallel_safe: payload.parallel_safe,
      subagent_safe: payload.subagent_safe,
      description: payload.description,
    };
    toast('Registered: ' + esc(payload.name));
    closeModal('modal-skill');
    refreshSkills();
  } catch (err) {
    toast('Failed: ' + err.message, 'error');
  }
});

// ═══════════════════════════════════════════════════════════════════════
// File browser
// ═══════════════════════════════════════════════════════════════════════

var browserTarget = null;

document.getElementById('btn-browse-skill').addEventListener('click', function () {
  browserTarget = 'skill';
  document.getElementById('browser-title').textContent = 'Browse Skill File';
  navigateBrowser(document.getElementById('skill-path').value || '~');
  openModal('modal-browser');
});

document.getElementById('btn-browser-go').addEventListener('click', function () {
  navigateBrowser(document.getElementById('browser-path').value);
});

document.getElementById('browser-path').addEventListener('keydown', function (e) {
  if (e.key === 'Enter') navigateBrowser(this.value);
});

document.getElementById('btn-browser-select').addEventListener('click', function () {
  var path = document.getElementById('browser-path').value;
  if (browserTarget === 'skill') document.getElementById('skill-path').value = path;
  closeModal('modal-browser');
});

async function navigateBrowser(path) {
  var list = document.getElementById('browser-list');
  list.innerHTML = '<div class="ts-browser-entry" style="color:var(--ts-text-muted);">Loading…</div>';
  try {
    var res = await fetch('/api/files?path=' + encodeURIComponent(path));
    var data = await res.json();
    if (data.error) { list.innerHTML = '<div class="ts-browser-entry" style="color:var(--ts-danger);">' + esc(data.error) + '</div>'; return; }
    document.getElementById('browser-path').value = data.path;
    var html = '<div class="ts-browser-entry ts-browser-up" onclick="navigateBrowser(\'' + escAttr(data.parent) + '\')">📁 ..</div>';
    data.entries.forEach(function (e) {
      var icon = e.type === 'directory' ? '📁' : '📄';
      var cls = e.type === 'directory' ? ' dir' : '';
      var fp = data.path + '/' + e.name;
      if (e.type === 'directory') {
        html += '<div class="ts-browser-entry' + cls + '" onclick="navigateBrowser(\'' + escAttr(fp) + '\')">' + icon + ' ' + esc(e.name) + '</div>';
      } else {
        html += '<div class="ts-browser-entry' + cls + '" onclick="selectBrowserFile(\'' + escAttr(fp) + '\')">' + icon + ' ' + esc(e.name) + '</div>';
      }
    });
    list.innerHTML = html;
  } catch (err) {
    list.innerHTML = '<div class="ts-browser-entry" style="color:var(--ts-danger);">' + esc(String(err)) + '</div>';
  }
}

function selectBrowserFile(path) {
  document.getElementById('browser-path').value = path;
  if (browserTarget === 'skill') document.getElementById('skill-path').value = path;
  closeModal('modal-browser');
}

// ═══════════════════════════════════════════════════════════════════════
// Load Skills from Folder
// ═══════════════════════════════════════════════════════════════════════

document.getElementById('btn-load-folder').addEventListener('click', function () {
  browserTarget = 'skill-folder';
  document.getElementById('browser-title').textContent = 'Select Skills Folder';
  navigateBrowser('~');
  var btn = document.getElementById('btn-browser-select');
  btn.textContent = 'Scan This Folder';
  btn.onclick = async function () {
    var path = document.getElementById('browser-path').value;
    closeModal('modal-browser');
    try {
      var resp = await api._fetch('POST', '/api/skills/folder', { path: path, exposure: 'secondary' });
      var reg = resp.registered || [];
      var fail = resp.failed || [];
      toast('Registered: ' + (reg.join(', ') || 'none') + (fail.length ? ' | Failed: ' + fail.map(function(f){return f.name;}).join(', ') : ''));
      state.skills = await api.listSkills();
      refreshSkills();
    } catch (err) {
      toast('Failed: ' + err.message, 'error');
    }
  };
  openModal('modal-browser');
});

// ═══════════════════════════════════════════════════════════════════════
// All Tools tab
// ═══════════════════════════════════════════════════════════════════════

async function refreshTools() {
  var list = document.getElementById('tools-list');
  var empty = document.getElementById('tools-empty');
  var summary = document.getElementById('tools-summary');

  var names = Object.keys(state.tools);
  if (names.length === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    summary.textContent = '';
    return;
  }
  empty.classList.add('hidden');

  var primary = names.filter(function (n) { return state.tools[n].exposure === 'primary'; }).length;
  var secondary = names.filter(function (n) { return state.tools[n].exposure === 'secondary'; }).length;
  var store = names.filter(function (n) { return state.tools[n].exposure === 'store'; }).length;
  var disabled = names.filter(function (n) { return state.tools[n].exposure === 'disabled'; }).length;
  summary.textContent = names.length + ' tools — ' + primary + ' primary, ' + secondary + ' secondary, ' + store + ' store, ' + disabled + ' disabled';

  list.innerHTML = names.map(function (name) {
    var t = state.tools[name];
    return renderToolRow(name, t);
  }).join('');
}

// ═══════════════════════════════════════════════════════════════════════
// Escape helpers
// ═══════════════════════════════════════════════════════════════════════

function esc(s) {
  if (!s) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escAttr(s) {
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ═══════════════════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════════════════

loadAll();

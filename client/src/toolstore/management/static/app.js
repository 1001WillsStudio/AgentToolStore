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
  toolsets: {},
  tools: {},
  mcpTools: {},
  mcpToolsetTools: {},   // MCP servers in "toolset" mode (grouped)
  registryTools: {},
  toolsetTools: {},
  onlineToolsets: {},
};

// ═══════════════════════════════════════════════════════════════════════
// API helpers
// ═══════════════════════════════════════════════════════════════════════

const api = {
  async _fetch(method, path, body, isJson) {
    var opts = { method };
    if (body) {
      if (isJson === false) {
        opts.body = body;
      } else {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(body);
      }
    }
    var res = await fetch(path, opts);
    var data = await res.json();
    if (!res.ok && data.error) throw new Error(data.error);
    return data;
  },
  getConfig()           { return this._fetch('GET', '/api/config'); },
  listTools()           { return this._fetch('GET', '/api/tools'); },
  listMcp()             { return this._fetch('GET', '/api/mcp/servers'); },
  addMcp(cfg)           { return this._fetch('POST', '/api/mcp/servers', cfg); },
  connectMcp(id)        { return this._fetch('POST', `/api/mcp/servers/${id}/connect`); },
  disconnectMcp(id)     { return this._fetch('POST', `/api/mcp/servers/${id}/disconnect`); },
  removeMcp(id)         { return this._fetch('DELETE', `/api/mcp/servers/${id}`); },
  listSkills()          { return this._fetch('GET', '/api/skills'); },
  registerSkill(cfg)    { return this._fetch('POST', '/api/skills', cfg); },
  uploadSkill(payload)  { return this._fetch('POST', '/api/skills/upload', payload); },
  registerFolder(cfg)   { return this._fetch('POST', '/api/skills/folder', cfg); },
  removeSkill(name)     { return this._fetch('DELETE', `/api/skills/${name}`); },
  patchTool(name, cfg)  { return this._fetch('PATCH', `/api/tools/${name}`, cfg); },
  patchMcpServer(id, cfg){ return this._fetch('PATCH', `/api/mcp/servers/${id}`, cfg); },
  runCode(cfg)          { return this._fetch('POST', '/api/mcp/code', cfg); },
  listToolsets()        { return this._fetch('GET', '/api/toolsets'); },
  registerToolset(cfg)  { return this._fetch('POST', '/api/toolsets', cfg); },
  registerToolsetFolder(cfg) { return this._fetch('POST', '/api/toolsets/folder', cfg); },
  removeToolset(name)   { return this._fetch('DELETE', `/api/toolsets/${name}`); },
  listRegistryToolsets(refresh){ return this._fetch('GET', '/api/registry/toolsets' + (refresh ? '?refresh=true' : '')); },
  downloadToolset(cfg)  { return this._fetch('POST', '/api/registry/toolsets/download', cfg); },
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
    if (tab === 'toolsets') refreshToolsets();
    if (tab === 'online-toolsets') refreshOnlineToolsets();
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
    // Fetch categorized tools from /api/tools
    try {
      var categorized = await api.listTools();
      state.mcpTools = categorized.mcp || {};
      state.mcpToolsetTools = categorized.mcp_toolsets || {};
      state.registryTools = categorized.registry || {};
      state.toolsetTools = categorized.toolsets || {};
      state.skillTools = categorized.skills || {};
    } catch (_) {}
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
// MCP tab → tab_mcp.js
// MCP transport toggle (showMcpFields) and modal wire-up are above.
// All other MCP functions live in tab_mcp.js which loads before app.js.

// ═══════════════════════════════════════════════════════════════════════
// Tool row renderer (shared by MCP + All Tools)
// ═══════════════════════════════════════════════════════════════════════

function renderToolRow(name, tool) {
  var exp = tool.exposure || 'secondary';
  var optColors = { primary: '#a78bfa', secondary: '#fbbf24', hidden: '#9090a0' };
  var opts = ['primary', 'secondary', 'hidden'].map(function (v) {
    var sel = v === exp ? ' selected' : '';
    return '<option value="' + v + '" style="color:' + optColors[v] + '"' + sel + '>' + v + '</option>';
  }).join('');
  return '<div class="ts-tool-row">'
    + '<div class="ts-tool-info">'
    + '<div class="ts-tool-name">' + esc(name) + '</div>'
    + '<div class="ts-tool-desc">' + esc(tool.description || '') + '</div>'
    + '</div>'
    + '<div class="ts-tool-controls">'
    + '<select class="ts-exposure-select ' + exp + '" data-tool="' + escAttr(name) + '" onchange="setExposure(this)">' + opts + '</select>'
    + '</div>'
    + '</div>';
}

// ═══════════════════════════════════════════════════════════════════════
// Set exposure via dropdown
// ═══════════════════════════════════════════════════════════════════════

async function setExposure(select) {
  var name = select.dataset.tool;
  var next = select.value;
  // Check MCP toolset entries first (they use patchMcpServer, not patchTool)
  var mcpTs = state.mcpToolsetTools[name];
  if (mcpTs && mcpTs.server_id) {
    try {
      await api.patchMcpServer(mcpTs.server_id, { exposure: next });
      mcpTs.exposure = next;
      select.className = 'ts-exposure-select ' + next;
      toast(esc(name) + ' → ' + next);
    } catch (e) {
      toast('Failed: ' + e.message, 'error');
      select.value = mcpTs.exposure || 'secondary';
    }
    return;
  }
  // Look up in all tool registries (config, MCP, toolsets, skills)
  var tool = state.tools[name] || state.mcpTools[name] || state.toolsetTools[name] || state.skillTools[name];
  if (!tool) { toast('Tool not found: ' + name, 'error'); return; }
  try {
    await api.patchTool(name, { exposure: next });
    tool.exposure = next;
    // Write back to whichever registry owns this tool
    if (state.tools[name]) state.tools[name] = tool;
    if (state.mcpTools[name]) state.mcpTools[name] = tool;
    if (state.toolsetTools[name]) state.toolsetTools[name] = tool;
    if (state.skillTools[name]) state.skillTools[name] = tool;
    select.className = 'ts-exposure-select ' + next;
    toast(esc(name) + ' → ' + next);
  } catch (e) {
    toast('Failed: ' + e.message, 'error');
    select.value = tool.exposure || 'secondary';
  }
}

// ═══════════════════════════════════════════════════════════════════════
// MCP action functions → tab_mcp.js

// ═══════════════════════════════════════════════════════════════════════
// MCP quick-paste + form handlers → tab_mcp.js

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
    var desc = sk.description || '';
    return '<div class="ts-card">'
      + '<div class="ts-card-header">'
      + '<div>'
      + '<div class="ts-card-title">' + esc(name) + '</div>'
      + '<div class="ts-card-subtitle">' + esc(desc.length > 100 ? desc.slice(0,100) + '…' : desc) + '</div>'
      + '</div>'
      + '<div style="display:flex;align-items:center;gap:8px;">'
      + '<button class="ts-btn ts-btn-danger ts-btn-sm" onclick="removeSkill(\'' + escAttr(name) + '\')">Remove</button>'
      + '</div>'
      + '</div>'
      + '</div>';
  }).join('');
}

async function removeSkill(name) {
  try {
    await api.removeSkill(name);
    delete state.skills[name];
    delete state.tools['skill:' + name];
    toast('Removed: ' + esc(name));
    refreshSkills();
  } catch (e) {
    toast('Remove failed: ' + e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Toolsets tab
// ═══════════════════════════════════════════════════════════════════════

async function refreshToolsets() {
  try {
    var toolsets = await api.listToolsets();
    state.toolsets = toolsets || {};
  } catch (e) { /* keep stale */ }

  // Ensure toolsetTools exposure is synced from config
  try {
    var categorized = await api.listTools();
    state.toolsetTools = categorized.toolsets || {};
  } catch (_) {}

  var list = document.getElementById('toolset-list');
  var empty = document.getElementById('toolset-empty');
  var summary = document.getElementById('toolsets-summary');
  var names = Object.keys(state.toolsets);

  if (names.length === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    summary.textContent = '';
    return;
  }
  empty.classList.add('hidden');
  summary.textContent = names.length + ' toolset' + (names.length !== 1 ? 's' : '') + ' registered';

  list.innerHTML = names.map(function (name) {
    var ts = state.toolsets[name];
    var desc = ts.description || '';
    var fnNames = (ts.functions || []).join(', ');
    var toolMeta = state.toolsetTools[name] || {};
    var exp = toolMeta.exposure || 'secondary';
    var optColors = { primary: '#a78bfa', secondary: '#fbbf24', hidden: '#9090a0' };
    var opts = ['primary', 'secondary', 'hidden'].map(function (v) {
      var sel = v === exp ? ' selected' : '';
      return '<option value="' + v + '" style="color:' + optColors[v] + '"' + sel + '>' + v + '</option>';
    }).join('');
    return '<div class="ts-card">'
      + '<div class="ts-card-header">'
      + '<div>'
      + '<div class="ts-card-title">' + esc(name) + '</div>'
      + '<div class="ts-card-subtitle">' + esc(desc.length > 100 ? desc.slice(0,100) + '…' : desc) + '</div>'
      + '</div>'
      + '<div style="display:flex;align-items:center;gap:8px;">'
      + '<select class="ts-exposure-select ' + exp + '" data-tool="' + escAttr(name) + '" onchange="setToolsetExposure(this)">' + opts + '</select>'
      + '<button class="ts-btn ts-btn-danger ts-btn-sm" onclick="removeToolset(\'' + escAttr(name) + '\')">Remove</button>'
      + '</div>'
      + '</div>'
      + (fnNames ? '<div class="ts-card-body" style="font-family:var(--font-mono);font-size:0.75rem;">Functions: ' + esc(fnNames) + '</div>' : '')
      + '</div>';
  }).join('');
}

async function removeToolset(name) {
  try {
    await api.removeToolset(name);
    delete state.toolsets[name];
    delete state.tools['toolset:' + name];
    toast('Removed: ' + esc(name));
    refreshToolsets();
    // Also refresh All Tools tab if visible later
    refreshTools();
  } catch (e) {
    toast('Remove failed: ' + e.message, 'error');
  }
}

async function setToolsetExposure(select) {
  var name = select.dataset.tool;
  var next = select.value;
  try {
    await api.patchTool(name, { exposure: next });
    // Update local state
    if (state.toolsetTools[name]) state.toolsetTools[name].exposure = next;
    select.className = 'ts-exposure-select ' + next;
    toast(esc(name) + ' → ' + next);
  } catch (e) {
    toast('Failed: ' + e.message, 'error');
    select.value = state.toolsetTools[name] ? (state.toolsetTools[name].exposure || 'secondary') : 'secondary';
  }
}

// ── Toolset modal open/upload/submit ──

var _toolsetUploadFiles = null;

document.getElementById('btn-refresh-toolsets').addEventListener('click', function () {
  refreshToolsets();
  toast('Refreshed');
});

document.getElementById('btn-register-toolset').addEventListener('click', function () {
  document.getElementById('form-toolset').reset();
  document.getElementById('upload-toolset-local-path').style.display = 'none';
  document.getElementById('upload-toolset-local-path').textContent = '';
  _toolsetUploadFiles = null;
  openModal('modal-toolset');
});

document.getElementById('btn-upload-toolset-local').addEventListener('click', function () {
  document.getElementById('local-toolset-input').click();
});

document.getElementById('local-toolset-input').addEventListener('change', function () {
  var files = this.files;
  if (!files || files.length === 0) return;
  var firstRel = files[0].webkitRelativePath || files[0].name;
  var folderName = firstRel.split('/')[0];
  var label = document.getElementById('upload-toolset-local-path');
  label.textContent = 'Selected: ' + folderName + ' (' + files.length + ' files)';
  label.style.display = 'block';
  _toolsetUploadFiles = files;
  document.getElementById('toolset-path').value = '';
});

document.getElementById('form-toolset').addEventListener('submit', async function (e) {
  e.preventDefault();

  // --- Local upload path ---
  if (_toolsetUploadFiles && _toolsetUploadFiles.length > 0) {
    var btn = document.getElementById('btn-toolset-install');
    btn.disabled = true;
    btn.textContent = 'Uploading…';
    try {
      if (typeof JSZip === 'undefined') {
        await new Promise(function (resolve, reject) {
          var s = document.createElement('script');
          s.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
          s.onload = resolve;
          s.onerror = function () { reject(new Error('Failed to load JSZip')); };
          document.head.appendChild(s);
        });
      }
      var zip = new JSZip();
      var files = _toolsetUploadFiles;
      for (var i = 0; i < files.length; i++) {
        var f = files[i];
        var relPath = f.webkitRelativePath || f.name;
        var parts = relPath.split('/');
        var innerPath = parts.slice(1).join('/');
        if (!innerPath) continue;
        var buf = await f.arrayBuffer();
        zip.file(innerPath, buf);
      }
      var zipBlob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 1 } });
      var base64 = await new Promise(function (resolve) {
        var reader = new FileReader();
        reader.onloadend = function () {
          resolve(reader.result.split(',')[1]);
        };
        reader.readAsDataURL(zipBlob);
      });

      // Upload as a skill-zip then discover toolsets from the extracted contents
      var res = await api.uploadSkill({ archive: base64 });
      var regList = res.registered || [];
      var failList = res.failed || [];
      var msg = 'Uploaded ' + regList.length + ' item' + (regList.length !== 1 ? 's' : '');
      if (failList.length) {
        msg += ' (' + failList.length + ' failed: ' + failList.map(function (f) { return f.name; }).join(', ') + ')';
      }
      toast(msg, failList.length ? 'error' : 'success');
      closeModal('modal-toolset');
      refreshToolsets();
    } catch (err) {
      toast('Upload failed: ' + err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Register';
    }
    return;
  }

  // --- Server path ---
  var fd = new FormData(this);
  var payload = { path: fd.get('path').trim() };
  if (!payload.path) { toast('Please select a toolset directory or upload a folder', 'error'); return; }
  try {
    var res = await api.registerToolset(payload);
    state.toolsets[res.toolset] = {
      description: '',
      path: res.path || payload.path,
      functions: res.functions || [],
    };
    toast('Registered: ' + esc(res.toolset) + ' (' + (res.functions || []).length + ' functions)');
    closeModal('modal-toolset');
    refreshToolsets();
  } catch (err) {
    toast('Failed: ' + err.message, 'error');
  }
});

// Track which mode the user chose (server-path vs local-upload)
var _skillUploadFiles = null;

document.getElementById('btn-register-skill').addEventListener('click', function () {
  document.getElementById('form-skill').reset();
  document.getElementById('upload-local-path').style.display = 'none';
  document.getElementById('upload-local-path').textContent = '';
  _skillUploadFiles = null;
  openModal('modal-skill');
});

// Option 2: trigger native folder picker
document.getElementById('btn-upload-local').addEventListener('click', function () {
  document.getElementById('local-skill-input').click();
});

document.getElementById('local-skill-input').addEventListener('change', function () {
  var files = this.files;
  if (!files || files.length === 0) return;
  // Extract folder name from the first file's relative path
  var firstRel = files[0].webkitRelativePath || files[0].name;
  var folderName = firstRel.split('/')[0];
  var label = document.getElementById('upload-local-path');
  label.textContent = 'Selected: ' + folderName + ' (' + files.length + ' files)';
  label.style.display = 'block';
  _skillUploadFiles = files;
  // Clear server path so we know to use upload
  document.getElementById('skill-path').value = '';
});

document.getElementById('form-skill').addEventListener('submit', async function (e) {
  e.preventDefault();

  // --- Local upload path ---
  if (_skillUploadFiles && _skillUploadFiles.length > 0) {
    var btn = document.getElementById('btn-skill-install');
    btn.disabled = true;
    btn.textContent = 'Uploading…';
    try {
      // Load JSZip dynamically
      if (typeof JSZip === 'undefined') {
        await new Promise(function (resolve, reject) {
          var s = document.createElement('script');
          s.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
          s.onload = resolve;
          s.onerror = function () { reject(new Error('Failed to load JSZip')); };
          document.head.appendChild(s);
        });
      }
      var zip = new JSZip();
      var files = _skillUploadFiles;
      for (var i = 0; i < files.length; i++) {
        var f = files[i];
        var relPath = f.webkitRelativePath || f.name;
        // Strip the root folder name to get relative paths inside the skill
        var parts = relPath.split('/');
        var innerPath = parts.slice(1).join('/');
        if (!innerPath) continue;
        // Read file as ArrayBuffer
        var buf = await f.arrayBuffer();
        zip.file(innerPath, buf);
      }
      var zipBlob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 1 } });
      // Convert to base64 (skills are small, overhead is fine)
      var base64 = await new Promise(function (resolve) {
        var reader = new FileReader();
        reader.onloadend = function () {
          var b64 = reader.result.split(',')[1];
          resolve(b64);
        };
        reader.readAsDataURL(zipBlob);
      });

      var res = await api.uploadSkill({ archive: base64 });
      var regList = res.registered || [];
      var failList = res.failed || [];
      var exp = (document.getElementById('skill-exposure') || {}).value || 'secondary';
      regList.forEach(function (name) {
        state.skills[name] = { path: '', description: '' };
        state.tools['skill:' + name] = {
          source: 'skill:' + name,
          enabled: true,
          exposure: exp,
          description: '',
        };
      });
      var msg = 'Installed ' + regList.length + ' skill' + (regList.length !== 1 ? 's' : '');
      if (failList.length) {
        msg += ' (' + failList.length + ' failed: ' + failList.map(function (f) { return f.name; }).join(', ') + ')';
      }
      toast(msg, failList.length ? 'error' : 'success');
      closeModal('modal-skill');
      refreshSkills();
    } catch (err) {
      toast('Upload failed: ' + err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Install';
    }
    return;
  }

  // --- Server path (uses folder endpoint — works for single + multiple skills) ---
  var fd = new FormData(this);
  var payload = { path: fd.get('path').trim() };
  if (!payload.path) { toast('Please select a skill directory or upload a folder', 'error'); return; }
  try {
    var res = await api.registerFolder(payload);
    var regList = res.registered || [];
    var failList = res.failed || [];
    var exp = (document.getElementById('skill-exposure') || {}).value || 'secondary';
    regList.forEach(function (name) {
      state.skills[name] = { path: payload.path, description: '' };
      state.tools['skill:' + name] = {
        source: 'skill:' + name,
        enabled: true,
        exposure: exp,
        description: '',
      };
    });
    var msg = 'Installed ' + regList.length + ' skill' + (regList.length !== 1 ? 's' : '');
    if (failList.length) {
      msg += ' (' + failList.length + ' failed: ' + failList.map(function (f) { return f.name; }).join(', ') + ')'; }
    toast(msg, failList.length ? 'error' : 'success');
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
  document.getElementById('browser-title').textContent = 'Select Skill Directory';
  navigateBrowser(document.getElementById('skill-path').value || '~');
  var btn = document.getElementById('btn-browser-select');
  btn.textContent = 'Select Current Folder';
  btn.onclick = function () {
    var path = document.getElementById('browser-path').value;
    if (browserTarget === 'skill') document.getElementById('skill-path').value = path;
    if (browserTarget === 'toolset') document.getElementById('toolset-path').value = path;
    closeModal('modal-browser');
  };
  openModal('modal-browser');
});

document.getElementById('btn-browse-toolset').addEventListener('click', function () {
  browserTarget = 'toolset';
  document.getElementById('browser-title').textContent = 'Select Toolset Directory';
  navigateBrowser(document.getElementById('toolset-path').value || '~');
  var btn = document.getElementById('btn-browser-select');
  btn.textContent = 'Select Current Folder';
  btn.onclick = function () {
    var path = document.getElementById('browser-path').value;
    if (browserTarget === 'toolset') document.getElementById('toolset-path').value = path;
    if (browserTarget === 'skill') document.getElementById('skill-path').value = path;
    closeModal('modal-browser');
  };
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
    // Skill & Toolset browser: directories are selectable.
    var isSkill = browserTarget === 'skill' || browserTarget === 'skill-folder';
    var isToolset = browserTarget === 'toolset';
    data.entries.forEach(function (e) {
      var icon = e.type === 'directory' ? '📁' : '📄';
      var cls = e.type === 'directory' ? ' dir' : '';
      var fp = data.path + '/' + e.name;
      if (e.type === 'directory') {
        // Double-click navigates; a select button lets the user pick the dir.
        html += '<div class="ts-browser-entry' + cls + '">'
          + '<span class="ts-browser-name" onclick="navigateBrowser(\'' + escAttr(fp) + '\')">' + icon + ' ' + esc(e.name) + '</span>'
          + ((isSkill || isToolset) ? '<button class="ts-btn ts-btn-sm ts-btn-primary" style="margin-left:auto;font-size:11px;padding:2px 8px;" onclick="selectBrowserPath(\'' + escAttr(fp) + '\')">Select</button>' : '')
          + '</div>';
      } else {
        html += '<div class="ts-browser-entry' + cls + '" onclick="selectBrowserPath(\'' + escAttr(fp) + '\')">' + icon + ' ' + esc(e.name) + '</div>';
      }
    });
    list.innerHTML = html;
  } catch (err) {
    list.innerHTML = '<div class="ts-browser-entry" style="color:var(--ts-danger);">' + esc(String(err)) + '</div>';
  }
}

function selectBrowserPath(path) {
  document.getElementById('browser-path').value = path;
  if (browserTarget === 'skill') document.getElementById('skill-path').value = path;
  if (browserTarget === 'toolset') document.getElementById('toolset-path').value = path;
  closeModal('modal-browser');
}


// ═══════════════════════════════════════════════════════════════════════
// Online Toolsets tab
// ═══════════════════════════════════════════════════════════════════════

async function refreshOnlineToolsets(refresh) {
  try {
    state.onlineToolsets = await api.listRegistryToolsets(refresh);
  } catch (e) { /* keep stale */ }

  var list = document.getElementById('online-toolset-list');
  var empty = document.getElementById('online-toolset-empty');
  var summary = document.getElementById('online-toolsets-summary');
  var names = Object.keys(state.onlineToolsets);

  if (names.length === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    summary.textContent = '';
    return;
  }
  empty.classList.add('hidden');
  summary.textContent = names.length + ' online toolset' + (names.length !== 1 ? 's' : '') + ' available';

  list.innerHTML = names.map(function (name) {
    var ts = state.onlineToolsets[name];
    var desc = ts.description || '';
    var fnNames = (ts.functions || []).join(', ');
    var version = ts.version ? ' v' + esc(ts.version) : '';
    return '<div class="ts-card">'
      + '<div class="ts-card-header">'
      + '<div>'
      + '<div class="ts-card-title">' + esc(name) + '<span class="ts-muted" style="font-size:0.75rem;margin-left:6px;">' + version + '</span></div>'
      + '<div class="ts-card-subtitle">' + esc(desc.length > 120 ? desc.slice(0,120) + '\u2026' : desc) + '</div>'
      + '</div>'
      + '<div style="display:flex;align-items:center;gap:8px;">'
      + '<span class="ts-badge" style="background:var(--ts-warn);color:#000;font-size:0.7rem;padding:2px 8px;border-radius:999px;">online</span>'
      + '<button class="ts-btn ts-btn-primary ts-btn-sm" onclick="downloadToolset(\'' + escAttr(name) + '\')">\u2b07 Download</button>'
      + '</div>'
      + '</div>'
      + (fnNames ? '<div class="ts-card-body" style="font-family:var(--font-mono);font-size:0.75rem;">Functions: ' + esc(fnNames) + '</div>' : '')
      + '</div>';
  }).join('');
}

async function downloadToolset(name) {
  var btn = event && event.target;
  if (btn) { btn.disabled = true; btn.textContent = 'Downloading\u2026'; }
  try {
    var res = await api.downloadToolset({ name: name });
    // Remove from online list, it will appear in local toolsets
    delete state.onlineToolsets[name];
    toast('Downloaded: ' + esc(name) + ' \u2192 ' + res.exposure);
    refreshOnlineToolsets();
    refreshToolsets();
    refreshTools();
  } catch (e) {
    toast('Download failed: ' + e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = '\u2b07 Download'; }
  }
}

// Wire up Online Toolsets refresh button
document.getElementById('btn-refresh-online-toolsets').addEventListener('click', function () {
  refreshOnlineToolsets(true);
  toast('Refreshed from registry');
});

// ═══════════════════════════════════════════════════════════════════════
// All Tools tab
// ═══════════════════════════════════════════════════════════════════════

async function refreshTools() {
  try {
    var categorized = await api.listTools();
    state.mcpTools = categorized.mcp || {};
    state.mcpToolsetTools = categorized.mcp_toolsets || {};
    state.registryTools = categorized.registry || {};
    state.toolsetTools = categorized.toolsets || {};
    state.skillTools = categorized.skills || {};
  } catch (_) { /* keep stale */ }

  var list = document.getElementById('tools-list');
  var empty = document.getElementById('tools-empty');
  var summary = document.getElementById('tools-summary');

  var mcpNames = Object.keys(state.mcpTools);
  var mcpTsNames = Object.keys(state.mcpToolsetTools);
  var tsNames = Object.keys(state.toolsetTools);
  var skNames = Object.keys(state.skillTools || {});
  var totalCount = mcpNames.length + mcpTsNames.length + tsNames.length + skNames.length;

  if (totalCount === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    summary.textContent = '';
    return;
  }
  empty.classList.add('hidden');

  var primary = 0, secondary = 0, hidden = 0;
  function countExposure(names, source) {
    names.forEach(function (n) {
      var exp = (source[n] || {}).exposure || 'secondary';
      if (exp === 'primary') primary++;
      else if (exp === 'hidden') hidden++;
      else secondary++;
    });
  }
  countExposure(mcpNames, state.mcpTools);
  countExposure(mcpTsNames, state.mcpToolsetTools);
  countExposure(tsNames, state.toolsetTools);
  countExposure(skNames, state.skillTools);
  summary.textContent =
    totalCount + ' tool' + (totalCount !== 1 ? 's' : '')
    + ' — ' + primary + ' primary, ' + secondary + ' secondary, ' + hidden + ' hidden';

  var html = '';

  // ── MCP toolset entries (grouped servers) ──
  mcpTsNames.forEach(function (displayName) {
    var ts = state.mcpToolsetTools[displayName];
    var exp = ts.exposure || 'secondary';
    var fnNames = (ts.functions || []).join(', ');
    var optColors = { primary: '#a78bfa', secondary: '#fbbf24', hidden: '#9090a0' };
    var opts = ['primary', 'secondary', 'hidden'].map(function (v) {
      var sel = v === exp ? ' selected' : '';
      return '<option value="' + v + '" style="color:' + optColors[v] + '"' + sel + '>' + v + '</option>';
    }).join('');
    html += '<div class="ts-card">'
      + '<div class="ts-card-header">'
      + '<div>'
      + '<div class="ts-card-title">' + esc(displayName) + ' <span class="ts-badge" style="background:var(--accent-green);color:#fff;font-size:0.65rem;padding:2px 6px;border-radius:999px;">MCP toolset</span></div>'
      + '<div class="ts-card-subtitle">' + esc(ts.description || '') + '</div>'
      + '</div>'
      + '<div style="display:flex;align-items:center;gap:8px;">'
      + '<select class="ts-exposure-select ' + exp + '" data-tool="' + escAttr(displayName) + '" onchange="setExposure(this)">' + opts + '</select>'
      + '</div>'
      + '</div>'
      + (fnNames ? '<div class="ts-card-body" style="font-family:var(--font-mono);font-size:0.75rem;">Functions: ' + esc(fnNames) + '</div>' : '')
      + '</div>';
  });

  // ── Individual tools (MCP individual-mode, toolset, skill) ──
  var merged = {};
  tsNames.forEach(function (n) { merged[n] = state.toolsetTools[n]; });
  mcpNames.forEach(function (n) { merged[n] = state.mcpTools[n]; });
  skNames.forEach(function (n) { merged[n] = state.skillTools[n]; });

  html += Object.keys(merged).map(function (name) {
    return renderToolRow(name, merged[name] || {});
  }).join('');

  list.innerHTML = html;
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
// Theme toggle
// ═══════════════════════════════════════════════════════════════════════

(function () {
  var toggle = document.getElementById('themeToggle');
  var theme = localStorage.getItem('toolstore-theme') || 'light';
  document.documentElement.setAttribute('data-theme', theme);
  toggle.textContent = theme === 'dark' ? '🌙' : '☀️';
  toggle.addEventListener('click', function () {
    var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('toolstore-theme', next);
    toggle.textContent = next === 'dark' ? '🌙' : '☀️';
  });
})();

// ═══════════════════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════════════════

loadAll();

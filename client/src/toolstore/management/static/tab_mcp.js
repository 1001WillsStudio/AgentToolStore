/**
 * ToolStore Management SPA — MCP Servers tab
 * Depends on: app.js (state, api, toast, esc, escAttr, renderToolRow, setExposure)
 */

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
  var displayName = srv.display_name || id;
  var exp = srv.exposure || 'secondary';
  var mode = srv.mode || 'toolset';
  var isToolsetMode = mode === 'toolset';

  // Collect individual tool rows
  var prefix = 'mcp:' + id;
  var toolRowHTML = '';
  Object.keys(state.tools).forEach(function (tn) {
    var t = state.tools[tn];
    if (t.source === prefix) toolRowHTML += renderToolRow(tn, t);
  });

  // In toolset mode, hide individual tool exposure controls; in individual mode, show them
  var toolsSection = '';
  if (toolRowHTML) {
    if (isToolsetMode) {
      // Toolset mode: show tool rows without exposure controls (just names)
      var prefix = 'mcp:' + id;
      var toolNames = Object.keys(state.tools).filter(function (tn) {
        return state.tools[tn].source === prefix;
      });
      toolsSection = '<div class="ts-card-tools" style="opacity:0.7;">'
        + '<div style="font-family:var(--font-mono);font-size:0.75rem;padding:6px 12px;">'
        + '🔧 ' + toolNames.map(function (n) { return esc(n); }).join(', ')
        + '</div></div>';
    } else {
      // Individual mode: full tool rows with exposure controls
      toolsSection = '<div class="ts-card-tools">' + toolRowHTML + '</div>';
    }
  }

  // Exposure dropdown (server-level for toolset mode; hidden for individual mode)
  var optColors = { primary: '#a78bfa', secondary: '#fbbf24', hidden: '#9090a0' };
  var opts = ['primary', 'secondary', 'hidden'].map(function (v) {
    var sel = v === exp ? ' selected' : '';
    return '<option value="' + v + '" style="color:' + optColors[v] + '"' + sel + '>' + v + '</option>';
  }).join('');

  var exposureDropdown = isToolsetMode
    ? '<select class="ts-exposure-select ' + exp + '" data-mcp-server="' + escAttr(id) + '" onchange="setMcpServerExposure(this)">' + opts + '</select>'
    : '';

  // Mode toggle switch
  var modeToggle = '<label class="ts-switch" style="margin-right:4px;" title="' + (isToolsetMode ? 'Switch to individual tools mode' : 'Switch to toolset mode') + '">'
    + '<input type="checkbox" ' + (mode === 'individual' ? 'checked' : '') + ' onchange="toggleMcpMode(this, \'' + escAttr(id) + '\')">'
    + '<span class="ts-slider"></span>'
    + '</label>'
    + '<span class="ts-badge" style="background:' + (isToolsetMode ? 'var(--accent-green)' : 'var(--accent-violet)') + ';color:#fff;font-size:0.65rem;padding:2px 6px;border-radius:999px;">' + (isToolsetMode ? 'toolset' : 'tools') + '</span>';

  return '<div class="ts-card">'
    + '<div class="ts-card-header">'
    + '<div style="flex:1;">'
    + '<div class="ts-card-title" style="display:flex;align-items:center;gap:8px;">'
    + '<span class="ts-editable-label" data-mcp-id="' + escAttr(id) + '" onclick="editMcpDisplayName(this)">' + esc(displayName) + '</span>'
    + (displayName !== id ? '<span class="ts-muted" style="font-size:0.7rem;">(' + esc(id) + ')</span>' : '')
    + '</div>'
    + '<div class="ts-card-subtitle">' + esc(transportDetail) + '</div>'
    + '</div>'
    + '<div style="display:flex;align-items:center;gap:8px;">'
    + modeToggle
    + exposureDropdown
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

// ── MCP mode toggle (toolset ↔ individual) ───────────────────────────

async function toggleMcpMode(checkbox, serverId) {
  var newMode = checkbox.checked ? 'individual' : 'toolset';
  var oldMode = (state.mcpServers[serverId] || {}).mode;
  try {
    await api.patchMcpServer(serverId, { mode: newMode });
    if (state.mcpServers[serverId]) state.mcpServers[serverId].mode = newMode;
    // Refresh both MCP tab and All Tools tab
    refreshMcp();
    toast('Mode: ' + newMode + (newMode === 'toolset' ? ' (tools hidden, server controls exposure)' : ' (each tool controls its own exposure)'));
    loadAll(); // reload config to get updated tool exposures
  } catch (e) {
    toast('Mode switch failed: ' + e.message, 'error');
    checkbox.checked = !checkbox.checked;  // revert
  }
}

// ── MCP server exposure & display name ──────────────────────────────

async function setMcpServerExposure(select) {
  var serverId = select.dataset.mcpServer;
  var next = select.value;
  try {
    var res = await api.patchMcpServer(serverId, { exposure: next });
    if (state.mcpServers[serverId]) state.mcpServers[serverId].exposure = next;
    var prefix = 'mcp:' + serverId;
    Object.keys(state.tools).forEach(function (tn) {
      if (state.tools[tn].source === prefix) state.tools[tn].exposure = next;
    });
    select.className = 'ts-exposure-select ' + next;
    toast(esc(state.mcpServers[serverId].display_name || serverId) + ' → ' + next + ' (' + (res.tools_synced || 0) + ' tools)');
  } catch (e) {
    toast('Failed: ' + e.message, 'error');
    select.value = (state.mcpServers[serverId] || {}).exposure || 'secondary';
  }
}

function editMcpDisplayName(span) {
  var serverId = span.dataset.mcpId;
  var srv = state.mcpServers[serverId] || {};
  var current = srv.display_name || serverId;
  var input = document.createElement('input');
  input.type = 'text';
  input.value = current;
  input.className = 'ts-inline-edit';
  input.style.cssText = 'font-size:inherit;font-weight:600;color:inherit;background:transparent;border:1px solid var(--accent-violet);border-radius:4px;padding:2px 6px;width:200px;';

  function save() {
    var newName = input.value.trim();
    input.remove();
    span.style.display = '';

    if (!newName || newName === current) {
      span.textContent = current;
      return;
    }
    api.patchMcpServer(serverId, { display_name: newName }).then(function () {
      if (state.mcpServers[serverId]) state.mcpServers[serverId].display_name = newName;
      span.textContent = newName;
      var parent = span.parentElement;
      var orig = parent.querySelector('.ts-muted');
      if (newName !== serverId) {
        if (!orig) { var el = document.createElement('span'); el.className = 'ts-muted'; el.style.cssText = 'font-size:0.7rem;'; el.textContent = '(' + serverId + ')'; parent.appendChild(el); }
        else orig.textContent = '(' + serverId + ')';
      } else if (orig) orig.remove();
      toast('Renamed \u2192 ' + esc(newName));
    }).catch(function (e) { toast('Rename failed: ' + e.message, 'error'); span.textContent = current; });
  }

  input.addEventListener('blur', save);
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') save();
    if (e.key === 'Escape') { span.textContent = current; span.style.display = ''; }
  });
  span.style.display = 'none';
  span.parentElement.insertBefore(input, span.nextSibling);
  input.focus(); input.select();
}

// ═══════════════════════════════════════════════════════════════════════
// MCP actions
// ═══════════════════════════════════════════════════════════════════════

async function connectMcp(id) {
  try {
    var res = await api.connectMcp(id);
    if (res.tools) {
      res.tools.forEach(function (t) {
        state.tools[t.name] = { source: 'mcp:' + id, enabled: true, exposure: 'secondary', parallel_safe: false, subagent_safe: false, description: t.description || '' };
      });
    }
    toast('Connected: ' + esc(id) + ' (' + (res.tools ? res.tools.length : 0) + ' tools)');
    refreshMcp();
  } catch (e) { toast('Connection failed: ' + e.message, 'error'); }
}

async function disconnectMcp(id) {
  try { await api.disconnectMcp(id); state.mcpServers[id].status = 'disconnected'; toast('Disconnected: ' + esc(id)); refreshMcp(); }
  catch (e) { toast('Disconnect failed: ' + e.message, 'error'); }
}

async function removeMcp(id) {
  try {
    await api.removeMcp(id); delete state.mcpServers[id];
    var prefix = 'mcp:' + id;
    Object.keys(state.tools).forEach(function (k) { if (state.tools[k].source === prefix) delete state.tools[k]; });
    toast('Removed: ' + esc(id)); refreshMcp();
  } catch (e) { toast('Remove failed: ' + e.message, 'error'); }
}

// ═══════════════════════════════════════════════════════════════════════
// MCP mode toggle (Quick Paste / Manual)
// ═══════════════════════════════════════════════════════════════════════

function switchMcpMode(mode) {
  var quickBtn = document.getElementById('mcp-mode-quick');
  var codeBtn = document.getElementById('mcp-mode-code');
  var manualBtn = document.getElementById('mcp-mode-manual');
  var quickSection = document.getElementById('mcp-quick-section');
  var codeSection = document.getElementById('mcp-code-section');
  var manualForm = document.getElementById('form-mcp');
  [quickBtn, codeBtn, manualBtn].forEach(function (b) { b.style.borderBottomColor = 'transparent'; });
  if (mode === 'quick') { quickBtn.style.borderBottomColor = 'var(--accent-violet)'; quickSection.classList.remove('hidden'); codeSection.classList.add('hidden'); manualForm.classList.add('hidden'); }
  else if (mode === 'code') { codeBtn.style.borderBottomColor = 'var(--accent-violet)'; quickSection.classList.add('hidden'); codeSection.classList.remove('hidden'); manualForm.classList.add('hidden'); }
  else { manualBtn.style.borderBottomColor = 'var(--accent-violet)'; quickSection.classList.add('hidden'); codeSection.classList.add('hidden'); manualForm.classList.remove('hidden'); }
}

// ═══════════════════════════════════════════════════════════════════════
// Run Code — Docker MCP server
// ═══════════════════════════════════════════════════════════════════════

var PYTHON_IMAGES = ['python:3.12-slim', 'python:3.11-slim', 'python:3.10-slim'];
var NODE_IMAGES = ['node:22-slim', 'node:20-slim'];

function mcpCodeLanguageChanged() {
  var lang = document.getElementById('mcp-code-language').value;
  var sel = document.getElementById('mcp-code-image');
  var images = lang === 'python' ? PYTHON_IMAGES : NODE_IMAGES;
  sel.innerHTML = images.map(function (img) { return '<option value="' + img + '">' + img + '</option>'; }).join('');
  var ta = document.getElementById('mcp-code-text');
  if (lang === 'python') ta.placeholder = 'from mcp.server import Server\nimport asyncio\n\n...';
  else ta.placeholder = 'import { Server } from "@modelcontextprotocol/sdk/server/index.js";\n...';
}

async function runMcpCode() {
  var code = document.getElementById('mcp-code-text').value.trim();
  if (!code) { toast('Paste MCP server code first', 'error'); return; }
  var language = document.getElementById('mcp-code-language').value;
  var image = document.getElementById('mcp-code-image').value;
  var label = document.getElementById('mcp-code-label').value.trim();
  var exposure = document.getElementById('mcp-code-exposure').value || 'secondary';
  var autoConnect = document.getElementById('mcp-code-autoconnect').checked;
  try {
    var res = await api.runCode({ code: code, language: language, image: image, server_id: label || undefined, exposure_default: exposure, auto_connect: autoConnect });
    if (res.tools) { res.tools.forEach(function (t) { state.tools[t.name] = { source: 'mcp:' + res.server_id, enabled: true, exposure: exposure, parallel_safe: false, subagent_safe: false, description: t.description || '' }; }); }
    var msg = 'Server running: ' + esc(res.server_id);
    if (res.tools_discovered) msg += ' (' + res.tools_discovered + ' tools)';
    if (res.connection_error) msg += ' [warn: ' + res.connection_error + ']';
    toast(msg, res.connection_error ? 'error' : 'success');
    closeModal('modal-mcp'); refreshMcp();
  } catch (e) { toast('Build failed: ' + e.message, 'error'); }
}

// ═══════════════════════════════════════════════════════════════════════
// Quick Paste — parse standard MCP config JSON
// ═══════════════════════════════════════════════════════════════════════

function parseMcpServersJson(text) {
  try {
    var parsed = JSON.parse(text);
    if (!parsed || !parsed.mcpServers || typeof parsed.mcpServers !== 'object') {
      return [];
    }
    var out = [];
    Object.keys(parsed.mcpServers).forEach(function (key) {
      var item = parsed.mcpServers[key];
      if (item && typeof item === 'object') {
        out = out.concat(normalizeMcpServer(item));
      }
    });
    return out;
  } catch (_) { return []; }
}

function normalizeMcpServer(item) {
  // Handle GitHub-style entries: { "owner/repo": { "transport": "stdio", ... } }
  // The key becomes the server_id (replacing / with -) if no 'name' field is provided.
  if (item && typeof item === 'object' && !Array.isArray(item)) {
    var result = {};
    Object.keys(item).forEach(function (key) {
      var val = item[key];
      if (val && typeof val === 'object' && !Array.isArray(val) && (val.transport || val.command || val.url)) {
        var cfg = Object.assign({}, val);
        cfg.server_id = cfg.server_id || cfg.name || key.replace(/\//g, '-');
        result[cfg.server_id] = cfg;
      } else if (key === 'transport' || key === 'command' || key === 'url') {
        result[key] = val;
      }
    });
    // If we detected sub-objects, return them as array
    var subIds = Object.keys(result).filter(function (k) {
      return result[k] && typeof result[k] === 'object' && !Array.isArray(result[k]) && (result[k].transport || result[k].command);
    });
    if (subIds.length > 0) {
      return subIds.map(function (k) { return result[k]; });
    }
    // Single server: use item directly if it has transport fields
    if (item.transport || item.command || item.url) {
      var cfg = Object.assign({}, item);
      cfg.server_id = cfg.server_id || cfg.name || 'mcp-' + Date.now();
      return [cfg];
    }
  } else if (Array.isArray(item)) {
    return item.map(function (s) { return s; });
  }
  return [];
}

async function quickConnectMcp() {
  var textarea = document.getElementById('mcp-quick-text');
  var text = textarea.value.trim();
  if (!text) { toast('Paste MCP server JSON first', 'error'); return; }

  var servers = parseMcpServersJson(text);
  if (servers.length === 0) {
    // Try parsing as a flat list of server objects
    try {
      var parsed = JSON.parse(text);
      if (Array.isArray(parsed)) {
        servers = parsed.map(function (s) {
          var c = Object.assign({}, s);
          if (!c.server_id) c.server_id = c.name || 'mcp-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);
          return c;
        });
      }
    } catch (_) {}
  }

  if (servers.length === 0) { toast('Could not parse any MCP servers from the input', 'error'); return; }

  var added = 0, failed = 0;
  for (var i = 0; i < servers.length; i++) {
    var srv = servers[i];
    if (!srv.transport) { failed++; continue; }
    try {
      await api.addMcp(srv);
      added++;
    } catch (_) { failed++; }
  }

  toast('Added ' + added + ' server' + (added !== 1 ? 's' : '') + (failed ? ' (' + failed + ' failed)' : ''), failed ? 'error' : 'success');
  refreshMcp();
  textarea.value = '';
}

// ═══════════════════════════════════════════════════════════════════════
// MCP form handlers & event listeners
// ═══════════════════════════════════════════════════════════════════════

// Connect MCP button → opens modal
document.getElementById('btn-connect-mcp').addEventListener('click', function () {
  document.getElementById('form-mcp').reset();
  document.getElementById('mcp-quick-text').value = '';
  switchMcpMode('quick');
  showMcpFields('stdio');
  openModal('modal-mcp');
});

// MCP form submit (manual mode)
document.getElementById('form-mcp').addEventListener('submit', async function (e) {
  e.preventDefault();
  var fd = new FormData(this);
  var transport = fd.get('transport') || 'stdio';
  var cfg = { transport: transport, server_id: (fd.get('server_id') || '').trim() || undefined };
  if (transport === 'stdio') {
    cfg.command = fd.get('command') || '';
    var argsStr = fd.get('args') || '';
    cfg.args = argsStr ? argsStr.split(/\s+/) : [];
    cfg.env_vars = fd.get('env_vars') || undefined;
  } else if (transport === 'sse') {
    cfg.url = fd.get('url') || '';
    cfg.headers = fd.get('headers') || undefined;
  } else if (transport === 'folder') {
    cfg.folder_path = fd.get('folder_path') || '';
    cfg.runtime = fd.get('runtime') || 'auto';
  }

  if (!cfg.server_id) cfg.server_id = 'mcp-' + Date.now();

  try {
    var res = await api.addMcp(cfg);
    toast('Added: ' + esc(res.server_id || cfg.server_id));
    closeModal('modal-mcp');
    refreshMcp();
  } catch (err) {
    toast('Failed: ' + err.message, 'error');
  }
});

// Refresh MCP button
document.getElementById('btn-refresh-mcp').addEventListener('click', function () {
  refreshMcp();
  toast('Refreshed');
});

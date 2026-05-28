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

  var toolRows = '';
  var prefix = 'mcp:' + id;
  Object.keys(state.tools).forEach(function (tn) {
    var t = state.tools[tn];
    if (t.source === prefix) toolRows += renderToolRow(tn, t);
  });

  var toolsSection = toolRows
    ? '<div class="ts-card-tools">' + toolRows + '</div>'
    : '';

  var optColors = { primary: '#a78bfa', secondary: '#fbbf24', hidden: '#9090a0' };
  var opts = ['primary', 'secondary', 'hidden'].map(function (v) {
    var sel = v === exp ? ' selected' : '';
    return '<option value="' + v + '" style="color:' + optColors[v] + '"' + sel + '>' + v + '</option>';
  }).join('');

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
    + '<select class="ts-exposure-select ' + exp + '" data-mcp-server="' + escAttr(id) + '" onchange="setMcpServerExposure(this)">' + opts + '</select>'
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
    if (!newName || newName === current) { span.textContent = current; span.style.display = ''; return; }
    api.patchMcpServer(serverId, { display_name: newName }).then(function () {
      if (state.mcpServers[serverId]) state.mcpServers[serverId].display_name = newName;
      span.textContent = newName;
      var parent = span.parentElement;
      var orig = parent.querySelector('.ts-muted');
      if (newName !== serverId) {
        if (!orig) { var el = document.createElement('span'); el.className = 'ts-muted'; el.style.cssText = 'font-size:0.7rem;'; el.textContent = '(' + serverId + ')'; parent.appendChild(el); }
        else orig.textContent = '(' + serverId + ')';
      } else if (orig) orig.remove();
      toast('Renamed → ' + esc(newName));
    }).catch(function (e) { toast('Rename failed: ' + e.message, 'error'); span.textContent = current; });
    span.style.display = '';
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

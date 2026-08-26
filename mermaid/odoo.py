import os
import xmlrpc.client
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# ---------- Configuration ----------
# Set these environment variables or leave empty to let the frontend provide them.
ODOO_URL = os.environ.get('ODOO_URL', '')
ODOO_DB = os.environ.get('ODOO_DB', '')
ODOO_USER = os.environ.get('ODOO_USER', '')
ODOO_PASS = os.environ.get('ODOO_PASS', '')

# ---------- Embedded HTML (from your previous version) ----------
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mermaid Odoo Editor</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
    <style>
        /* Your existing styles (exactly as in your file) */
        :root {
            --bg-color: #f4f5f7;
            --panel-bg: #ffffff;
            --border-color: #e2e8f0;
            --primary: #d63384;
            --primary-hover: #b8256f;
            --text-main: #1e293b;
            --danger: #dc2626;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; height: 100vh; display: flex; flex-direction: column; background: var(--bg-color); color: var(--text-main); overflow: hidden; }
        header { background: var(--panel-bg); min-height: 50px; padding: 0 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); z-index: 5; flex-wrap: wrap; gap: 8px; }
        .logo { display: flex; align-items: center; gap: 8px; font-weight: 700; color: var(--primary); font-size: 15px; }
        .top-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .btn { background: #edf2f7; color: #4a5568; border: none; padding: 6px 12px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 12px; transition: all 0.2s; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
        .btn:hover { background: #e2e8f0; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-hover); }
        .icon-btn { background: transparent; border: 1px solid var(--border-color); padding: 5px 9px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; }
        .icon-btn:hover { background: #f1f5f9; }
        .status-badge { font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 12px; display: inline-flex; align-items: center; gap: 5px; }
        .status-disconnected { background: #fee2e2; color: #dc2626; }
        .status-connecting { background: #fef9c3; color: #a16207; }
        .status-connected { background: #dcfce7; color: #16a34a; }
        .status-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
        .status-disconnected .status-dot { background: #dc2626; }
        .status-connecting .status-dot { background: #a16207; }
        .status-connected .status-dot { background: #16a34a; }
        .workspace { display: flex; flex: 1; height: calc(100vh - 50px); position: relative; flex-direction: row; }
        .editor-panel { width: 420px; min-width: 320px; background: var(--panel-bg); border-right: 1px solid var(--border-color); display: flex; flex-direction: column; padding: 12px; gap: 10px; z-index: 2; position: relative; }
        .model-picker-box { display: flex; gap: 8px; align-items: center; background: #f8fafc; border: 1px solid var(--border-color); padding: 8px; border-radius: 6px; }
        .model-picker-box label { font-size: 11px; font-weight: 600; color: #64748b; white-space: nowrap; }
        input, select { width: 100%; padding: 6px 10px; border: 1px solid var(--border-color); border-radius: 4px; font-size: 12px; outline: none; background: white; }
        input:focus, select:focus { border-color: var(--primary); }
        .tab-header { display: flex; gap: 15px; border-bottom: 1px solid var(--border-color); padding-bottom: 4px; font-size: 13px; font-weight: 600; color: #64748b; }
        .tab-btn { cursor: pointer; padding-bottom: 4px; border-bottom: 2px solid transparent; background: none; border-left: none; border-right: none; border-top: none; font: inherit; color: inherit; }
        .tab-btn.active { color: var(--primary); border-bottom: 2px solid var(--primary); }
        .tab-content { flex: 1; display: none; flex-direction: column; }
        .tab-content.active { display: flex; }
        textarea { flex: 1; border: 1px solid var(--border-color); border-radius: 6px; padding: 10px; font-family: "Fira Code", Consolas, monospace; font-size: 13px; line-height: 1.5; resize: none; outline: none; background: #fafafa; }
        .error-banner { display: none; background: #fee2e2; color: var(--danger); border: 1px solid #fecaca; border-radius: 6px; padding: 8px 10px; font-size: 11px; font-family: "Fira Code", Consolas, monospace; max-height: 90px; overflow-y: auto; white-space: pre-wrap; }
        .error-banner.visible { display: block; }
        .bottom-controls { display: flex; gap: 8px; position: relative; margin-top: auto; align-items: center; }
        .popover { position: absolute; bottom: 45px; right: 0; background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); display: none; width: 220px; z-index: 20; }
        .popover-header { font-weight: bold; font-size: 11px; margin-bottom: 8px; color: #64748b; text-transform: uppercase; }
        .export-option-btn { width: 100%; text-align: left; background: #f8fafc; border: 1px solid var(--border-color); padding: 7px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; color: var(--text-main); cursor: pointer; margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between; }
        .export-option-btn:hover { background: #f1f5f9; border-color: #cbd5e1; }
        .canvas-panel { flex: 1; position: relative; background-color: #f8fafc; background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 16px 16px; overflow: hidden; min-height: 300px; }
        #svg-wrapper { width: 100%; height: 100%; position: absolute; top: 0; left: 0; }
        #svg-wrapper svg { width: 100% !important; height: 100% !important; max-width: none !important; }
        .zoom-toolbar { position: absolute; top: 15px; right: 15px; background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 8px; display: flex; gap: 2px; padding: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); z-index: 5; }
        .zoom-btn { background: transparent; border: none; width: 30px; height: 30px; border-radius: 4px; cursor: pointer; font-weight: bold; color: #475569; display: flex; align-items: center; justify-content: center; }
        .zoom-btn:hover { background: #f1f5f9; }
        .modal-backdrop { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.4); display: none; justify-content: center; align-items: center; z-index: 100; }
        .modal { background: var(--panel-bg); border-radius: 8px; width: 400px; max-width: 90vw; padding: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); display: flex; flex-direction: column; gap: 12px; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; font-weight: bold; font-size: 15px; border-bottom: 1px solid var(--border-color); padding-bottom: 8px; }
        .modal-header span[role="button"] { cursor: pointer; }
        .form-group { display: flex; flex-direction: column; gap: 4px; }
        .form-group label { font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; }
        .form-hint { font-size: 11px; color: #94a3b8; line-height: 1.4; }
        @media (max-width: 850px) {
            body { overflow: auto; }
            .workspace { flex-direction: column; height: auto; }
            .editor-panel { width: 100%; min-width: 100%; height: 50vh; }
            .canvas-panel { width: 100%; height: 50vh; }
        }
    </style>
</head>
<body>
<header>
    <div class="logo">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
        Mermaid Odoo Editor
    </div>
    <div class="top-actions">
        <span id="odoo-status-badge" class="status-badge status-disconnected">
            <span class="status-dot"></span> <span id="status-text">Disconnected</span>
        </span>
        <button class="icon-btn" onclick="openOdooSettings()">⚙️ Odoo Config</button>
        <button class="btn btn-primary" id="sync-btn" onclick="fetchOdooMetadata()">Sync Odoo Model</button>
    </div>
</header>
<div class="workspace">
    <div class="editor-panel">
        <div class="model-picker-box">
            <label>Model Tech Name:</label>
            <input type="text" id="odoo_model" value="hr.employee" placeholder="e.g. hr.employee">
        </div>
        <div class="tab-header">
            <button id="tab-code-btn" class="tab-btn active" onclick="switchTab('code')" type="button">Code</button>
            <button id="tab-config-btn" class="tab-btn" onclick="switchTab('config')" type="button">Config</button>
        </div>
        <div id="code-tab" class="tab-content active">
            <textarea id="mermaid-code" spellcheck="false">
flowchart TD
    A[HR Employee] -->|Department| B[HR Department]
    A -->|Job Position| C[HR Job]
    A -->|Manager| A
            </textarea>
        </div>
        <div id="config-tab" class="tab-content">
            <textarea id="mermaid-config" spellcheck="false">{
  "theme": "default",
  "securityLevel": "strict"
}</textarea>
        </div>
        <div id="error-banner" class="error-banner"></div>
        <div class="bottom-controls">
            <select id="diagram-type-select" style="flex: 1;" onchange="handleDiagramSelect(this.value)">
                <option value="" disabled selected>📐 Select Diagram Template...</option>
                <option value="flowchart">Flowchart</option>
                <option value="er">Entity Relationship (ER)</option>
                <option value="class">Class Diagram</option>
                <option value="state">State Diagram</option>
                <option value="sequence">Sequence Diagram</option>
                <option value="gantt">Gantt Chart</option>
                <option value="mindmap">Mindmap</option>
                <option value="pie">Pie Chart</option>
            </select>
            <button class="btn" style="min-width: 90px;" onclick="toggleActionsMenu(event)">↑ Actions</button>
            <div id="actions-popover" class="popover">
                <div class="popover-header">Export Diagram As</div>
                <button class="export-option-btn" onclick="exportMMD()"><span>.mmd (Source)</span> 📄</button>
                <button class="export-option-btn" onclick="exportHTML()"><span>.html (Standalone)</span> 🌐</button>
                <button class="export-option-btn" onclick="exportSVG()"><span>.svg (Vector)</span> 🎨</button>
                <button class="export-option-btn" onclick="exportPNG()"><span>.png (Image)</span> 🖼️</button>
            </div>
        </div>
    </div>
    <div class="canvas-panel">
        <div class="zoom-toolbar">
            <button class="zoom-btn" title="Reset View" onclick="resetZoom()">⟲</button>
            <button class="zoom-btn" title="Zoom In" onclick="zoomIn()">+</button>
            <button class="zoom-btn" title="Zoom Out" onclick="zoomOut()">-</button>
        </div>
        <div id="svg-wrapper"></div>
    </div>
</div>
<!-- Odoo Connection Modal -->
<div id="odoo-modal" class="modal-backdrop">
    <div class="modal">
        <div class="modal-header">
            <span>Odoo Connection Credentials</span>
            <span role="button" onclick="closeOdooSettings()">✕</span>
        </div>
        <div class="form-group">
            <label>Server URL</label>
            <input type="text" id="odoo_url" placeholder="https://your-instance.odoo.com">
        </div>
        <div class="form-group">
            <label>Database</label>
            <input type="text" id="odoo_db" placeholder="your-database-name">
        </div>
        <div class="form-group">
            <label>Username / Email</label>
            <input type="text" id="odoo_user" placeholder="you@example.com">
        </div>
        <div class="form-group">
            <label>API Key / Password</label>
            <input type="password" id="odoo_pass" placeholder="••••••••••••" autocomplete="new-password">
        </div>
        <p class="form-hint">Credentials are sent to the backend (same origin) – not exposed to the client.</p>
        <button class="btn btn-primary" style="justify-content: center;" onclick="testAndCloseOdooSettings()">Save &amp; Test</button>
    </div>
</div>
<script>
    // --- Use relative paths for API (same origin) ---
    const BACKEND_URL = '';  // empty = same origin

    let panZoomInstance = null;
    let renderCounter = 0;

    const DEFAULT_MERMAID_CONFIG = { startOnLoad: false, theme: 'default', securityLevel: 'strict' };
    mermaid.initialize(DEFAULT_MERMAID_CONFIG);

    const codeArea = document.getElementById('mermaid-code');
    const configArea = document.getElementById('mermaid-config');
    const wrapper = document.getElementById('svg-wrapper');
    const errorBanner = document.getElementById('error-banner');

    function showError(message) {
        errorBanner.textContent = message;
        errorBanner.classList.add('visible');
    }
    function clearError() {
        errorBanner.textContent = '';
        errorBanner.classList.remove('visible');
    }
    function applyConfigFromTab() {
        try {
            const parsed = JSON.parse(configArea.value || '{}');
            mermaid.initialize({ ...DEFAULT_MERMAID_CONFIG, ...parsed, startOnLoad: false });
            return true;
        } catch (e) {
            showError('Config tab: invalid JSON — ' + e.message);
            return false;
        }
    }
    async function renderDiagram() {
        const code = codeArea.value.trim();
        if (!code) { wrapper.innerHTML = ''; return; }
        if (!applyConfigFromTab()) return;
        try {
            if (panZoomInstance) {
                panZoomInstance.destroy();
                panZoomInstance = null;
            }
            renderCounter += 1;
            const renderId = `interactive-svg-${renderCounter}`;
            const { svg } = await mermaid.render(renderId, code);
            wrapper.innerHTML = svg;
            clearError();
            const svgElement = wrapper.querySelector('svg');
            if (svgElement) {
                svgElement.removeAttribute('height');
                panZoomInstance = svgPanZoom(svgElement, {
                    zoomEnabled: true,
                    controlIconsEnabled: false,
                    fit: true,
                    center: true,
                    minZoom: 0.1,
                    maxZoom: 10
                });
            }
        } catch (err) {
            showError('Diagram error: ' + (err && err.message ? err.message : String(err)));
        }
    }
    function zoomIn() { if (panZoomInstance) panZoomInstance.zoomIn(); }
    function zoomOut() { if (panZoomInstance) panZoomInstance.zoomOut(); }
    function resetZoom() { if (panZoomInstance) { panZoomInstance.resetZoom(); panZoomInstance.center(); } }
    function switchTab(tab) {
        document.getElementById('tab-code-btn').classList.toggle('active', tab === 'code');
        document.getElementById('tab-config-btn').classList.toggle('active', tab === 'config');
        document.getElementById('code-tab').classList.toggle('active', tab === 'code');
        document.getElementById('config-tab').classList.toggle('active', tab === 'config');
        if (tab === 'code') renderDiagram();
    }
    function toggleActionsMenu(evt) {
        if (evt) evt.stopPropagation();
        const pop = document.getElementById('actions-popover');
        pop.style.display = pop.style.display === 'block' ? 'none' : 'block';
    }
    document.addEventListener('click', (evt) => {
        const pop = document.getElementById('actions-popover');
        if (pop.style.display === 'block' && !pop.contains(evt.target)) {
            pop.style.display = 'none';
        }
    });
    function openOdooSettings() { document.getElementById('odoo-modal').style.display = 'flex'; }
    function closeOdooSettings() { document.getElementById('odoo-modal').style.display = 'none'; }
    function testAndCloseOdooSettings() {
        closeOdooSettings();
        fetchOdooMetadata();
    }
    function toMermaidId(raw) {
        const cleaned = String(raw || '').replace(/[^a-zA-Z0-9_]/g, '_').replace(/^_+|_+$/g, '');
        return cleaned || 'MODEL';
    }
    function handleDiagramSelect(type) {
        const rawModel = document.getElementById('odoo_model').value;
        const model = toMermaidId(rawModel).toUpperCase();
        if (type === 'er') {
            codeArea.value = `erDiagram\n    ${model} {\n        string name\n        many2one department_id\n    }\n    ${model} }|--|| HR_DEPARTMENT : "department_id"`;
        } else if (type === 'class') {
            codeArea.value = `classDiagram\n    class ${model} {\n        +String name\n        +get_department()\n    }`;
        } else if (type === 'sequence') {
            codeArea.value = `sequenceDiagram\n    autonumber\n    User->>${model}: Create Record\n    ${model}-->>User: Return ID`;
        } else if (type === 'state') {
            codeArea.value = `stateDiagram-v2\n    [*] --> Draft\n    Draft --> Confirmed\n    Confirmed --> Done\n    Done --> [*]`;
        } else if (type === 'gantt') {
            codeArea.value = `gantt\n    title ${model} Implementation\n    section Setup\n    Fetch Schema :a1, 2026-08-01, 3d\n    Render Mermaid :after a1, 2d`;
        } else if (type === 'mindmap') {
            codeArea.value = `mindmap\n  root((${model}))\n    Fields\n      Name\n      ID\n    Relations\n      Department\n      Job`;
        } else if (type === 'pie') {
            codeArea.value = `pie title ${model} Record Types\n    "Active" : 85\n    "Archived" : 15`;
        } else if (type === 'flowchart') {
            codeArea.value = `flowchart TD\n    A[${model}] --> B[Related Model]`;
        }
        document.getElementById('diagram-type-select').selectedIndex = 0;
        renderDiagram();
    }
    function downloadBlob(content, filename, type) {
        const blob = new Blob([content], { type: type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        document.getElementById('actions-popover').style.display = 'none';
    }
    function currentModelSlug() {
        return toMermaidId(document.getElementById('odoo_model').value).toLowerCase() || 'diagram';
    }
    function exportMMD() {
        downloadBlob(codeArea.value, `${currentModelSlug()}_diagram.mmd`, 'text/plain;charset=utf-8');
    }
    function exportHTML() {
        const html = `<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"><\/script>
</head>
<body>
  <pre class="mermaid">
${codeArea.value}
  </pre>
  <script>mermaid.initialize({ startOnLoad: true, securityLevel: 'strict' });<\/script>
</body>
</html>`;
        downloadBlob(html, `${currentModelSlug()}_diagram.html`, 'text/html;charset=utf-8');
    }
    function exportSVG() {
        const svgElement = wrapper.querySelector('svg');
        if (!svgElement) { showError('Nothing to export yet — render a diagram first.'); return; }
        const svgData = new XMLSerializer().serializeToString(svgElement);
        downloadBlob(svgData, `${currentModelSlug()}_diagram.svg`, 'image/svg+xml;charset=utf-8');
    }
    function exportPNG() {
        const svgElement = wrapper.querySelector('svg');
        if (!svgElement) { showError('Nothing to export yet — render a diagram first.'); return; }
        const clone = svgElement.cloneNode(true);
        let w = svgElement.viewBox && svgElement.viewBox.baseVal && svgElement.viewBox.baseVal.width;
        let h = svgElement.viewBox && svgElement.viewBox.baseVal && svgElement.viewBox.baseVal.height;
        if (!w || !h) {
            const bbox = svgElement.getBBox();
            w = bbox.width;
            h = bbox.height;
        }
        w = Math.max(Math.ceil(w) || 1200, 1);
        h = Math.max(Math.ceil(h) || 800, 1);
        clone.setAttribute('width', w);
        clone.setAttribute('height', h);
        const svgData = new XMLSerializer().serializeToString(clone);
        const canvas = document.createElement('canvas');
        const scale = 2;
        canvas.width = w * scale;
        canvas.height = h * scale;
        const ctx = canvas.getContext('2d');
        const img = new Image();
        img.onload = () => {
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            const a = document.createElement('a');
            a.download = `${currentModelSlug()}_diagram.png`;
            a.href = canvas.toDataURL('image/png');
            a.click();
            document.getElementById('actions-popover').style.display = 'none';
        };
        img.onerror = () => showError('PNG export failed while rasterizing the diagram.');
        img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
    }
    function setStatus(state, label) {
        const badge = document.getElementById('odoo-status-badge');
        const statusText = document.getElementById('status-text');
        badge.className = `status-badge status-${state}`;
        statusText.innerText = label;
    }

    // ----- Fetch via local API (same origin) -----
    async function fetchOdooMetadata() {
        const url = document.getElementById('odoo_url').value.trim();
        const db = document.getElementById('odoo_db').value.trim();
        const user = document.getElementById('odoo_user').value.trim();
        const password = document.getElementById('odoo_pass').value.trim();
        const model = document.getElementById('odoo_model').value.toLowerCase().trim().replace(/_/g, '.');

        if (!url || !db || !user || !password) {
            showError('Please fill in all Odoo credentials in the config modal.');
            openOdooSettings();
            return;
        }

        const syncBtn = document.getElementById('sync-btn');
        syncBtn.disabled = true;
        setStatus('connecting', 'Connecting…');

        try {
            // 1. Authenticate via backend
            const authRes = await fetch('/api/auth', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, db, user, password })
            });
            const authData = await authRes.json();
            if (!authRes.ok || authData.error) {
                throw new Error(authData.error || 'Authentication failed');
            }
            const uid = authData.uid;

            // 2. Fetch fields via backend
            const fieldsRes = await fetch('/api/fields', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, db, user, password, model, uid })
            });
            const fieldsData = await fieldsRes.json();
            if (!fieldsRes.ok || fieldsData.error) {
                throw new Error(fieldsData.error || 'Could not fetch fields');
            }
            const fields = fieldsData.fields || {};

            setStatus('connected', 'Connected');

            // Build ER diagram
            const cleanModel = toMermaidId(model).toUpperCase();
            let code = `erDiagram\n    ${cleanModel} {\n`;
            let rels = [];
            for (const [f_name, f_info] of Object.entries(fields)) {
                const safeName = toMermaidId(f_name).toLowerCase();
                const safeType = toMermaidId(f_info.type).toLowerCase() || 'string';
                code += `        ${safeType} ${safeName}\n`;
                if (f_info.relation) {
                    const target = toMermaidId(f_info.relation).toUpperCase();
                    if (f_info.type === 'many2one') {
                        rels.push(`    ${cleanModel} }|--|| ${target} : "${safeName}"`);
                    }
                }
            }
            code += `    }\n` + rels.join('\n');
            codeArea.value = code;
            clearError();
            renderDiagram();

        } catch (e) {
            setStatus('disconnected', 'Disconnected');
            showError('Error: ' + e.message);
        } finally {
            syncBtn.disabled = false;
        }
    }

    let timer;
    codeArea.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(renderDiagram, 400);
    });
    configArea.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(renderDiagram, 400);
    });
    renderDiagram();
</script>
</body>
</html>
"""

# ---------- Routes ----------
@app.route('/')
@app.route('/odoo')
def index():
    """Serve the main HTML page."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/auth', methods=['POST'])
def auth():
    data = request.json or {}
    url = data.get('url', ODOO_URL).rstrip('/')
    db = data.get('db', ODOO_DB)
    user = data.get('user', ODOO_USER)
    password = data.get('password', ODOO_PASS)

    if not all([url, db, user, password]):
        return jsonify({'error': 'Missing credentials'}), 400

    try:
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        uid = common.authenticate(db, user, password, {})
        if not uid:
            return jsonify({'error': 'Authentication failed'}), 401
        return jsonify({'uid': uid})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fields', methods=['POST'])
def fields():
    data = request.json or {}
    url = data.get('url', ODOO_URL).rstrip('/')
    db = data.get('db', ODOO_DB)
    user = data.get('user', ODOO_USER)
    password = data.get('password', ODOO_PASS)
    model = data.get('model', '').strip().lower().replace('_', '.')
    uid = data.get('uid')

    if not all([url, db, user, password, model]):
        return jsonify({'error': 'Missing parameters'}), 400

    try:
        # Re‑authenticate if uid not provided or invalid
        if not uid:
            common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
            uid = common.authenticate(db, user, password, {})
            if not uid:
                return jsonify({'error': 'Re‑authentication failed'}), 401

        models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
        fields_data = models.execute_kw(
            db, uid, password,
            model, 'fields_get',
            [],
            {'attributes': ['string', 'type', 'relation', 'help', 'selection']}
        )
        return jsonify({'fields': fields_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------- Run ----------
if __name__ == '__main__':
    # Use PORT env for hosting (e.g. Heroku) or default 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

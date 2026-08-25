import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';

mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: {
    darkMode: true,
    background: '#030712',
    primaryColor: '#1e1e1e',
    primaryTextColor: '#ffffff',
    primaryBorderColor: '#4b5563',
    lineColor: '#9ca3af',
    secondaryColor: '#111827',
    tertiaryColor: '#1f2937',
    attributeBackgroundColorOdd: '#18181b',
    attributeBackgroundColorEven: '#09090b',
    labelTextColor: '#ffffff',
    textColor: '#ffffff',
    nodeTextColor: '#ffffff'
  }
});

const DEFAULT_CODE = `erDiagram
    HR_EMPLOYEE }o--|| HR_DEPARTMENT        : "belongs to (department_id)"
    HR_EMPLOYEE }o--|| HR_JOB               : "holds position (job_id)"
    HR_EMPLOYEE }o--o{ HR_EMPLOYEE_CATEGORY : "tagged with (category_ids)"
    HR_EMPLOYEE }o--|| RES_COMPANY          : "belongs to (company_id)"
    HR_EMPLOYEE }o--o| HR_EMPLOYEE          : "reports to (parent_id / Manager)"
    HR_EMPLOYEE }o--o| HR_EMPLOYEE          : "coached by (coach_id)"
    HR_EMPLOYEE }o--|| HR_WORK_LOCATION     : "works at (work_location_id)"
    HR_EMPLOYEE |o--o| RES_USERS            : "linked to (user_id)"
    HR_EMPLOYEE }o--o| RES_USERS            : "expense approver (expense_manager_id)"
    HR_EMPLOYEE }o--o| RES_USERS            : "leave approver (leave_manager_id)"
    HR_EMPLOYEE |o--|| RESOURCE_RESOURCE    : "materialized as (resource_id)"
    HR_EMPLOYEE }o--|| RESOURCE_CALENDAR    : "follows schedule (resource_calendar_id)"
    HR_EMPLOYEE }o--o| RES_PARTNER_BANK     : "paid via (bank_account_id)"
    HR_EMPLOYEE }o--o| RES_PARTNER          : "work address (address_id)"
    HR_EMPLOYEE }o--o| RES_PARTNER          : "home address (address_home_id)"

    HR_DEPARTMENT }o--o| HR_EMPLOYEE   : "managed by (manager_id)"
    HR_DEPARTMENT }o--o| HR_DEPARTMENT : "sub-department of (parent_id)"
    HR_DEPARTMENT }o--|| RES_COMPANY   : "belongs to (company_id)"

    HR_JOB }o--|| HR_DEPARTMENT : "opened for (department_id)"
    HR_JOB }o--|| RES_COMPANY   : "belongs to (company_id)"

    RESOURCE_RESOURCE }o--|| RESOURCE_CALENDAR : "scheduled by (calendar_id)"
    RESOURCE_RESOURCE }o--|| RES_COMPANY       : "belongs to (company_id)"

    RESOURCE_CALENDAR }o--|| RES_COMPANY : "belongs to (company_id)"

    RES_USERS }o--|| RES_PARTNER : "represented by (partner_id)"
    RES_USERS }o--|| RES_COMPANY : "default company (company_id)"

    RES_PARTNER_BANK }o--|| RES_PARTNER : "owned by (partner_id)"

    HR_EMPLOYEE {
        int id PK
        char name
        char work_email
        char work_phone
        char job_title
        char active
        int department_id FK
        int job_id FK
        int company_id FK
        int work_location_id FK
        int parent_id FK "Manager"
        int coach_id FK
        int user_id FK
        int expense_manager_id FK
        int leave_manager_id FK
        int resource_id FK
        int resource_calendar_id FK
        int bank_account_id FK
        int address_id FK "Work address"
        int address_home_id FK "Private address"
    }

    HR_DEPARTMENT {
        int id PK
        char name
        int manager_id FK
        int parent_id FK
        int company_id FK
    }

    HR_JOB {
        int id PK
        char name
        int department_id FK
        int company_id FK
        char state
    }

    HR_EMPLOYEE_CATEGORY {
        int id PK
        char name
    }

    RES_COMPANY {
        int id PK
        char name
        int partner_id FK
    }

    HR_WORK_LOCATION {
        int id PK
        char name
        int company_id FK
        char location_type "home / office / other"
    }

    RES_USERS {
        int id PK
        int partner_id FK
        int company_id FK
        boolean active
    }

    RESOURCE_RESOURCE {
        int id PK
        char name
        int calendar_id FK
        int company_id FK
    }

    RESOURCE_CALENDAR {
        int id PK
        char name
    }

    RES_PARTNER_BANK {
        int id PK
        char acc_number
        int partner_id FK
        int bank_id FK
    }

    RES_PARTNER {
        int id PK
        char name
        int company_id FK
    }`;

// --- Elements ---
const codeEl = document.getElementById('code');
const lineNumbersEl = document.getElementById('lineNumbers');
const statusEl = document.getElementById('status');
const statusDot = document.getElementById('statusDot');
const fileNameEl = document.getElementById('fileName');
const errorBox = document.getElementById('errorBox');
const diagramEl = document.getElementById('diagram');
const stage = document.getElementById('stage');
const canvas = document.getElementById('canvas');
const fileInput = document.getElementById('fileInput');

const supportsFSAccess = 'showOpenFilePicker' in window;

// --- File state ---
let currentFileHandle = null; // File System Access API handle, when available
let currentFileName = 'untitled.mmd';
let isDirty = false;

function setDirty(dirty) {
  isDirty = dirty;
  statusDot.classList.toggle('dirty', dirty);
}

function setFileName(name) {
  currentFileName = name;
  fileNameEl.textContent = name + (isDirty ? ' •' : '');
}

codeEl.value = DEFAULT_CODE;
setFileName(currentFileName);

// --- Line numbers ---
function updateLineNumbers() {
  const lines = codeEl.value.split('\n').length;
  let out = '';
  for (let i = 1; i <= lines; i++) out += i + '\n';
  lineNumbersEl.textContent = out;
}
codeEl.addEventListener('scroll', () => {
  lineNumbersEl.scrollTop = codeEl.scrollTop;
});

// --- Rendering ---
let renderCounter = 0;
async function renderDiagram() {
  updateLineNumbers();
  const id = 'mmd-' + (++renderCounter);
  const src = codeEl.value.trim();
  if (!src) return;
  try {
    const { svg } = await mermaid.render(id, src);
    diagramEl.innerHTML = svg;
    errorBox.style.display = 'none';
    statusEl.textContent = 'rendered';
    statusEl.classList.remove('error');
  } catch (err) {
    errorBox.style.display = 'block';
    errorBox.textContent = (err && err.message) ? err.message : String(err);
    statusEl.textContent = 'syntax error';
    statusEl.classList.add('error');
    const stray = document.getElementById(id);
    if (stray) stray.remove();
  }
}

let debounceTimer;
codeEl.addEventListener('input', () => {
  updateLineNumbers();
  setDirty(true);
  setFileName(currentFileName);
  clearTimeout(debounceTimer);
  statusEl.textContent = 'rendering…';
  statusEl.classList.remove('error');
  debounceTimer = setTimeout(renderDiagram, 350);
});

codeEl.addEventListener('keydown', (e) => {
  if (e.key === 'Tab') {
    e.preventDefault();
    const start = codeEl.selectionStart;
    const end = codeEl.selectionEnd;
    codeEl.value = codeEl.value.slice(0, start) + '    ' + codeEl.value.slice(end);
    codeEl.selectionStart = codeEl.selectionEnd = start + 4;
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault();
    saveFile();
  }
});
window.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault();
    saveFile();
  }
});

// --- Resizable split (Supports Mouse and Touch) ---
const resizer = document.getElementById('resizer');
const editorPane = document.getElementById('editor-pane');
let resizing = false;

function startResize() {
  resizing = true;
  resizer.classList.add('active');
  document.body.style.userSelect = 'none';
}

function stopResize() {
  if (!resizing) return;
  resizing = false;
  resizer.classList.remove('active');
  document.body.style.userSelect = '';
}

function handlePointerMove(clientX, clientY) {
  if (!resizing) return;
  const mainRect = document.getElementById('main').getBoundingClientRect();
  const isMobile = window.innerWidth <= 768;

  if (isMobile) {
    let newHeight = clientY - mainRect.top;
    const min = 100, max = mainRect.height * 0.8;
    newHeight = Math.max(min, Math.min(max, newHeight));
    editorPane.style.height = newHeight + 'px';
  } else {
    let newWidth = clientX - mainRect.left;
    const min = 260, max = mainRect.width * 0.75;
    newWidth = Math.max(min, Math.min(max, newWidth));
    editorPane.style.width = newWidth + 'px';
  }
}

resizer.addEventListener('mousedown', startResize);
window.addEventListener('mouseup', stopResize);
window.addEventListener('mousemove', (e) => handlePointerMove(e.clientX, e.clientY));

resizer.addEventListener('touchstart', (e) => {
  startResize();
}, { passive: true });
window.addEventListener('touchend', stopResize);
window.addEventListener('touchmove', (e) => {
  if (resizing && e.touches.length > 0) {
    handlePointerMove(e.touches[0].clientX, e.touches[0].clientY);
  }
}, { passive: true });

// --- Pan & zoom on preview (Supports Touch Panning) ---
let scale = 1, originX = 0, originY = 0;
let isPanning = false, startX = 0, startY = 0;

function applyTransform() {
  stage.style.transform = `translate(${originX}px, ${originY}px) scale(${scale})`;
}

function startPan(clientX, clientY) {
  isPanning = true;
  canvas.classList.add('grabbing');
  startX = clientX - originX;
  startY = clientY - originY;
}

function movePan(clientX, clientY) {
  if (!isPanning) return;
  originX = clientX - startX;
  originY = clientY - startY;
  applyTransform();
}

function stopPan() {
  isPanning = false;
  canvas.classList.remove('grabbing');
}

canvas.addEventListener('mousedown', (e) => {
  if (e.target.closest('#zoomControls')) return;
  startPan(e.clientX, e.clientY);
});
window.addEventListener('mousemove', (e) => movePan(e.clientX, e.clientY));
window.addEventListener('mouseup', stopPan);

canvas.addEventListener('touchstart', (e) => {
  if (e.target.closest('#zoomControls') || e.touches.length > 1) return;
  startPan(e.touches[0].clientX, e.touches[0].clientY);
}, { passive: true });

window.addEventListener('touchmove', (e) => {
  if (isPanning && e.touches.length === 1) {
    movePan(e.touches[0].clientX, e.touches[0].clientY);
  }
}, { passive: true });

window.addEventListener('touchend', stopPan);

canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const delta = e.deltaY > 0 ? -0.08 : 0.08;
  scale = Math.max(0.01, scale + delta);
  applyTransform();
}, { passive: false });

document.getElementById('zoomIn').onclick = () => { scale += 0.15; applyTransform(); };
document.getElementById('zoomOut').onclick = () => { scale = Math.max(0.01, scale - 0.15); applyTransform(); };
document.getElementById('zoomReset').onclick = () => { scale = 1; originX = 0; originY = 0; applyTransform(); };

// --- Copy code ---
document.getElementById('copyBtn').addEventListener('click', async () => {
  await navigator.clipboard.writeText(codeEl.value);
  const btn = document.getElementById('copyBtn');
  const original = btn.textContent;
  btn.textContent = 'Copied';
  setTimeout(() => { btn.textContent = original; }, 1200);
});

// --- Export rendered SVG ---
document.getElementById('downloadSvgBtn').addEventListener('click', () => {
  const svgEl = diagramEl.querySelector('svg');
  if (!svgEl) return;
  const serializer = new XMLSerializer();
  let source = serializer.serializeToString(svgEl);
  if (!source.match(/^<svg[^>]+xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)) {
    source = source.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
  }
  const blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = currentFileName.replace(/\.mmd$|\.mermaid$/i, '') + '.svg';
  a.click();
  URL.revokeObjectURL(url);
});

// --- New ---
document.getElementById('newBtn').addEventListener('click', () => {
  if (isDirty && !confirm('Discard unsaved changes and start a new diagram?')) return;
  currentFileHandle = null;
  codeEl.value = 'erDiagram\n    ENTITY_ONE ||--o{ ENTITY_TWO : relates\n';
  setDirty(false);
  setFileName('untitled.mmd');
  renderDiagram();
  codeEl.focus();
});

// --- Open ---
document.getElementById('openBtn').addEventListener('click', async () => {
  if (isDirty && !confirm('Discard unsaved changes and open a different file?')) return;

  if (supportsFSAccess) {
    try {
      const [handle] = await window.showOpenFilePicker({
        types: [{
          description: 'Mermaid diagram',
          accept: { 'text/plain': ['.mmd', '.mermaid', '.txt'] }
        }],
        multiple: false
      });
      const file = await handle.getFile();
      const text = await file.text();
      currentFileHandle = handle;
      codeEl.value = text;
      setDirty(false);
      setFileName(file.name);
      updateLineNumbers();
      renderDiagram();
    } catch (err) {
      // user cancelled the picker — no-op
      if (err && err.name !== 'AbortError') console.error(err);
    }
  } else {
    fileInput.click();
  }
});

// Fallback open via <input type="file">
fileInput.addEventListener('change', async () => {
  const file = fileInput.files[0];
  if (!file) return;
  const text = await file.text();
  currentFileHandle = null; // no direct-write handle in fallback mode
  codeEl.value = text;
  setDirty(false);
  setFileName(file.name);
  updateLineNumbers();
  renderDiagram();
  fileInput.value = '';
});

// --- Save ---
async function saveFile() {
  if (supportsFSAccess) {
    try {
      if (!currentFileHandle) {
        currentFileHandle = await window.showSaveFilePicker({
          suggestedName: currentFileName || 'diagram.mmd',
          types: [{
            description: 'Mermaid diagram',
            accept: { 'text/plain': ['.mmd'] }
          }]
        });
      }
      const writable = await currentFileHandle.createWritable();
      await writable.write(codeEl.value);
      await writable.close();
      const file = await currentFileHandle.getFile();
      setDirty(false);
      setFileName(file.name);
    } catch (err) {
      if (err && err.name !== 'AbortError') console.error(err);
    }
  } else {
    // Fallback: trigger a download since direct filesystem writes aren't available
    const blob = new Blob([codeEl.value], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = currentFileName.endsWith('.mmd') ? currentFileName : currentFileName + '.mmd';
    a.click();
    URL.revokeObjectURL(url);
    setDirty(false);
    setFileName(currentFileName);
  }
}
document.getElementById('saveBtn').addEventListener('click', saveFile);

// --- Warn on unload with unsaved changes ---
window.addEventListener('beforeunload', (e) => {
  if (isDirty) {
    e.preventDefault();
    e.returnValue = '';
  }
});

// --- Init ---
updateLineNumbers();
renderDiagram();

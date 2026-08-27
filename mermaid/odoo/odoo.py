import sys
import subprocess
import importlib
import datetime

# ---------- Dependency Check & Auto-install ----------
# Maps the pip package name to the actual importable module name.
required_packages = {
    "PyQt6": "PyQt6.QtWidgets",
    "PyQt6-WebEngine": "PyQt6.QtWebEngineWidgets",
}
for pip_name, import_name in required_packages.items():
    try:
        importlib.import_module(import_name)
    except ImportError:
        print(f"Package '{pip_name}' not found. Attempting to install...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            print(f"Successfully installed '{pip_name}'.")
        except Exception as e:
            print(f"Failed to install '{pip_name}': {e}")
            sys.exit(1)

import json
import re
import xmlrpc.client
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QSplitter,
    QMessageBox, QTabWidget, QCheckBox, QProgressBar, QFileDialog,
    QStatusBar, QFrame, QWidgetAction, QToolBar, QCompleter, QToolButton,
    QMenu, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QSize, QTimer
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence, QPixmap, QPainter, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView


APP_ORG = "MermaidStudio"
APP_NAME = "OdooArchitectureVisualizer"
MAX_RECENT = 8

DIAGRAM_ICONS = {
    "ER Diagram": "🗂",
    "Class Diagram": "🧩",
    "Flowchart / Tree": "🌳",
    "State / Workflow Diagram": "🔁",
    "Sequence Diagram": "↔",
}


# ---------- Worker thread for Odoo calls ----------
class OdooWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, url, db, user, pwd, model=None, mode=None,
                 include_basic=True, include_relations=True):
        super().__init__()
        self.url = url
        self.db = db
        self.user = user
        self.pwd = pwd
        self.model = model
        self.mode = mode
        self.include_basic = include_basic
        self.include_relations = include_relations

    def run(self):
        try:
            common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            uid = common.authenticate(self.db, self.user, self.pwd, {})
            if not uid:
                self.error.emit("Authentication failed. Please check your credentials.")
                return
            models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')

            if self.model is None:
                self.progress.emit(20)
                model_list = models.execute_kw(
                    self.db, uid, self.pwd,
                    'ir.model', 'search_read',
                    [[]],
                    {'fields': ['name', 'model']}
                )
                self.progress.emit(100)
                self.finished.emit(model_list)
            else:
                self.progress.emit(30)
                fields_data = models.execute_kw(
                    self.db, uid, self.pwd,
                    self.model, 'fields_get',
                    [],
                    {'attributes': ['string', 'type', 'relation', 'selection', 'help']}
                )
                self.progress.emit(80)
                mermaid = self._build_mermaid(self.model, fields_data, self.mode)
                self.progress.emit(100)
                self.finished.emit({'code': mermaid, 'fields': fields_data})
        except Exception as e:
            self.error.emit(str(e))

    def _build_mermaid(self, model_name, fields, mode):
        clean = model_name.replace('.', '_').upper()
        lines = []

        def keep(f_info):
            """Respect the Basic Attributes / Relational checkboxes."""
            is_relation = bool(f_info.get('relation'))
            if is_relation:
                return self.include_relations
            return self.include_basic

        if mode == "ER Diagram":
            lines.append("erDiagram")
            lines.append(f"    {clean} {{")
            rels = []
            any_field = False
            for f_name, f_info in fields.items():
                if not keep(f_info):
                    continue
                any_field = True
                f_type = f_info.get('type')
                rel = f_info.get('relation')
                lines.append(f"        {f_type} {f_name}")
                if rel and self.include_relations:
                    target = rel.replace('.', '_').upper()
                    if f_type == 'many2one':
                        rels.append(f"    {clean} }}|--|| {target} : \"{f_name}\"")
                    elif f_type in ('one2many', 'many2many'):
                        brace = '{' if f_type == 'many2many' else '|'
                        rels.append(f"    {clean} }}|--|{brace} {target} : \"{f_name}\"")
            if not any_field:
                lines.append("        string _no_fields_selected")
            lines.append("    }")
            lines.extend(rels)
        elif mode == "Class Diagram":
            lines.append("classDiagram")
            lines.append(f"    class {clean} {{")
            rels = []
            any_field = False
            for f_name, f_info in fields.items():
                if not keep(f_info):
                    continue
                any_field = True
                f_type = f_info.get('type')
                rel = f_info.get('relation')
                lines.append(f"        +{f_type} {f_name}")
                if rel and self.include_relations:
                    target = rel.replace('.', '_').upper()
                    rels.append(f"    {clean} --> {target} : {f_name}")
            if not any_field:
                lines.append("        +string _no_fields_selected")
            lines.append("    }")
            lines.extend(rels)
        elif mode == "Flowchart / Tree":
            lines.append("graph TD")
            lines.append(f"    ROOT[{model_name}]")
            if self.include_relations:
                for f_name, f_info in fields.items():
                    if f_info.get('type') == 'many2one':
                        lines.append(f"    ROOT -->|{f_name}| {f_info.get('relation')}")
            if self.include_basic:
                basics = [f for f, i in fields.items() if not i.get('relation')]
                for b in basics[:12]:
                    safe = re.sub(r'\W', '_', b)
                    lines.append(f"    ROOT -.->|attr| {safe}[{b}]")
        elif mode == "State / Workflow Diagram":
            lines.append("stateDiagram-v2")
            state_field = fields.get('state') or fields.get('x_state')
            if state_field and 'selection' in state_field:
                sel = state_field['selection']
                if sel:
                    lines.append("    [*] --> " + sel[0][0])
                    for i in range(len(sel) - 1):
                        lines.append(f"    {sel[i][0]} --> {sel[i+1][0]}")
                    lines.append(f"    {sel[-1][0]} --> [*]")
            else:
                lines.append(f"    %% No state selection field found for model {model_name}")
        elif mode == "Sequence Diagram":
            lines.append("sequenceDiagram")
            lines.append("    autonumber")
            lines.append("    actor User")
            lines.append(f"    participant Model as {clean}")
            m2o = [f_info.get('relation') for f_info in fields.values() if f_info.get('type') == 'many2one']
            lines.append("    User->>Model: Create/Read Record")
            for target in m2o[:5]:
                t_clean = target.replace('.', '_').upper()
                lines.append(f"    Model->>+1_{t_clean}: Fetch Foreign Key ({target})")
                lines.append(f"    1_{t_clean}-->>-Model: Return Record ID")
        return "\n".join(lines)


# ---------- Main Window ----------
class OdooMermaidStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Odoo Architecture Studio")
        self.resize(1550, 940)

        self.settings = QSettings(APP_ORG, APP_NAME)

        self.uid = None
        self.current_mermaid = ""
        self.current_app_theme = self.settings.value("theme", "dark")
        self.all_models = []  # list of (name, model) tuples
        self.recent_models = json.loads(self.settings.value("recent_models", "[]") or "[]")

        self._create_menu_popups()
        self._create_toolbar()
        self._create_menus()
        self._create_central_widget()
        self._create_status_bar()

        self._restore_connection_fields()
        self.apply_app_theme(self.current_app_theme)
        self._show_welcome_canvas()
        self._refresh_recent_menu()

    # ------------------------------------------------------------------
    # Setup: popups (Config / Diagram Settings)
    # ------------------------------------------------------------------
    def _create_menu_popups(self):
        # Config Popup
        self.conn_popup = QWidget()
        self.conn_popup.setMinimumWidth(300)
        conn_layout = QVBoxLayout(self.conn_popup)
        conn_layout.setContentsMargins(14, 14, 14, 14)
        conn_layout.setSpacing(8)

        title = QLabel("ODOO CONNECTION")
        title.setObjectName("popupTitle")
        conn_layout.addWidget(title)

        conn_layout.addWidget(QLabel("Server URL:"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://mycompany.odoo.com")
        conn_layout.addWidget(self.url_edit)

        conn_layout.addWidget(QLabel("Database:"))
        self.db_edit = QLineEdit()
        conn_layout.addWidget(self.db_edit)

        conn_layout.addWidget(QLabel("User Email:"))
        self.user_edit = QLineEdit()
        conn_layout.addWidget(self.user_edit)

        conn_layout.addWidget(QLabel("API Password / Key:"))
        pass_row = QHBoxLayout()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        pass_row.addWidget(self.pass_edit)
        self.show_pass_btn = QToolButton()
        self.show_pass_btn.setText("👁")
        self.show_pass_btn.setCheckable(True)
        self.show_pass_btn.setFixedSize(30, 30)
        self.show_pass_btn.toggled.connect(self._toggle_password_visibility)
        pass_row.addWidget(self.show_pass_btn)
        conn_layout.addLayout(pass_row)

        self.remember_chk = QCheckBox("Remember URL / DB / Email on this device")
        self.remember_chk.setChecked(self.settings.value("remember", "true") == "true")
        conn_layout.addWidget(self.remember_chk)

        self.connect_btn = QPushButton("⚡ Connect to Odoo")
        self.connect_btn.setObjectName("connectBtn")
        self.connect_btn.clicked.connect(self.connect_odoo)
        conn_layout.addWidget(self.connect_btn)

        # Diagram Settings Popup
        self.opt_popup = QWidget()
        self.opt_popup.setMinimumWidth(300)
        opt_layout = QVBoxLayout(self.opt_popup)
        opt_layout.setContentsMargins(14, 14, 14, 14)
        opt_layout.setSpacing(8)

        opt_title = QLabel("DIAGRAM SETTINGS")
        opt_title.setObjectName("popupTitle")
        opt_layout.addWidget(opt_title)

        opt_layout.addWidget(QLabel("Target Model (type to search):"))
        model_picker = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.model_combo.setPlaceholderText("e.g. hr.employee")
        self.model_combo.setDuplicatesEnabled(False)
        model_picker.addWidget(self.model_combo, 1)

        self.refresh_models_btn = QPushButton("↻")
        self.refresh_models_btn.setToolTip("Refresh model list from Odoo")
        self.refresh_models_btn.setFixedSize(32, 32)
        self.refresh_models_btn.clicked.connect(self.fetch_models)
        model_picker.addWidget(self.refresh_models_btn)
        opt_layout.addLayout(model_picker)

        opt_layout.addWidget(QLabel("Diagram Mode:"))
        self.type_combo = QComboBox()
        for mode_name, icon in DIAGRAM_ICONS.items():
            self.type_combo.addItem(f"{icon}  {mode_name}", mode_name)
        opt_layout.addWidget(self.type_combo)

        opt_layout.addWidget(QLabel("Renderer Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["default", "dark", "forest", "neutral", "base"])
        self.theme_combo.setCurrentText(self.settings.value("mermaid_theme", "default"))
        self.theme_combo.currentTextChanged.connect(self._on_mermaid_theme_changed)
        opt_layout.addWidget(self.theme_combo)

        field_label = QLabel("Field Filters:")
        opt_layout.addWidget(field_label)
        self.chk_relations = QCheckBox("Relational fields (M2O / O2M / M2M)")
        self.chk_relations.setChecked(True)
        self.chk_basic = QCheckBox("Basic / primitive attributes")
        self.chk_basic.setChecked(True)
        opt_layout.addWidget(self.chk_relations)
        opt_layout.addWidget(self.chk_basic)

        self.generate_btn = QPushButton("✨ Generate Diagram")
        self.generate_btn.setObjectName("generateBtn")
        self.generate_btn.setToolTip("Ctrl+Enter")
        self.generate_btn.clicked.connect(self.generate_diagram)
        opt_layout.addWidget(self.generate_btn)

    def _toggle_password_visibility(self, checked):
        self.pass_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )

    def _on_mermaid_theme_changed(self, _):
        self.settings.setValue("mermaid_theme", self.theme_combo.currentText())
        if self.current_mermaid:
            self.render_diagram(self.current_mermaid)

    # ------------------------------------------------------------------
    # Setup: toolbar
    # ------------------------------------------------------------------
    def _create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        gen_action = QAction("✨ Generate", self)
        gen_action.setShortcut(QKeySequence("Ctrl+Return"))
        gen_action.setToolTip("Generate diagram from selected model (Ctrl+Enter)")
        gen_action.triggered.connect(self.generate_diagram)
        toolbar.addAction(gen_action)

        render_action = QAction("▶ Render Edited Code", self)
        render_action.setShortcut(QKeySequence("Ctrl+R"))
        render_action.setToolTip("Re-render the diagram using the current text in the code editor")
        render_action.triggered.connect(self.render_current_code)
        toolbar.addAction(render_action)

        toolbar.addSeparator()

        copy_action = QAction("📋 Copy Code", self)
        copy_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        copy_action.triggered.connect(self.copy_code)
        toolbar.addAction(copy_action)

        save_action = QAction("💾 Save .mmd", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(lambda: self.export_diagram("mmd"))
        toolbar.addAction(save_action)

        open_action = QAction("📂 Open .mmd", self)
        open_action.triggered.connect(self.open_mermaid_file)
        toolbar.addAction(open_action)

        export_menu_btn = QToolButton()
        export_menu_btn.setText("⬇ Export")
        export_menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        export_menu = QMenu(export_menu_btn)
        export_menu.addAction("Standalone HTML", lambda: self.export_diagram("html"))
        export_menu.addAction("SVG Image", lambda: self.export_diagram("svg"))
        export_menu.addAction("PNG Snapshot", lambda: self.export_diagram("png"))
        export_menu_btn.setMenu(export_menu)
        toolbar.addWidget(export_menu_btn)

        toolbar.addSeparator()

        zoom_out = QAction("🔍−", self)
        zoom_out.setToolTip("Zoom out")
        zoom_out.triggered.connect(lambda: self._run_canvas_js("window.__panZoom && window.__panZoom.zoomOut();"))
        toolbar.addAction(zoom_out)

        zoom_reset = QAction("⤢ Fit", self)
        zoom_reset.setToolTip("Fit diagram to canvas")
        zoom_reset.triggered.connect(lambda: self._run_canvas_js(
            "if(window.__panZoom){window.__panZoom.reset();window.__panZoom.fit();window.__panZoom.center();}"
        ))
        toolbar.addAction(zoom_reset)

        zoom_in = QAction("🔍+", self)
        zoom_in.setToolTip("Zoom in")
        zoom_in.triggered.connect(lambda: self._run_canvas_js("window.__panZoom && window.__panZoom.zoomIn();"))
        toolbar.addAction(zoom_in)

        toolbar.addSeparator()

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        self.theme_toggle_action = QAction("🌗 Theme", self)
        self.theme_toggle_action.setToolTip("Toggle light / dark application theme")
        self.theme_toggle_action.triggered.connect(self.toggle_app_theme)
        toolbar.addAction(self.theme_toggle_action)

    def _run_canvas_js(self, script):
        self.web_view.page().runJavaScript(script)

    # ------------------------------------------------------------------
    # Setup: menu bar
    # ------------------------------------------------------------------
    def _create_menus(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        config_menu = file_menu.addMenu("🔗 Odoo Connection")
        conn_action = QWidgetAction(self)
        conn_action.setDefaultWidget(self.conn_popup)
        config_menu.addAction(conn_action)

        file_menu.addSeparator()
        open_mmd = QAction("Open .mmd Source…", self)
        open_mmd.triggered.connect(self.open_mermaid_file)
        file_menu.addAction(open_mmd)

        save_mmd = QAction("Save .mmd Source…", self)
        save_mmd.setShortcut(QKeySequence("Ctrl+S"))
        save_mmd.triggered.connect(lambda: self.export_diagram("mmd"))
        file_menu.addAction(save_mmd)

        file_menu.addSeparator()
        export_html = QAction("Export Standalone HTML…", self)
        export_html.triggered.connect(lambda: self.export_diagram("html"))
        file_menu.addAction(export_html)

        export_svg = QAction("Export SVG Image…", self)
        export_svg.triggered.connect(lambda: self.export_diagram("svg"))
        file_menu.addAction(export_svg)

        export_png = QAction("Export PNG Snapshot…", self)
        export_png.triggered.connect(lambda: self.export_diagram("png"))
        file_menu.addAction(export_png)

        file_menu.addSeparator()
        new_action = QAction("New / Reset Workspace", self)
        new_action.triggered.connect(self.reset_workspace)
        file_menu.addAction(new_action)

        # Diagram Settings Menu
        opt_menu = menubar.addMenu("⚙ Diagram Settings")
        opt_action = QWidgetAction(self)
        opt_action.setDefaultWidget(self.opt_popup)
        opt_menu.addAction(opt_action)

        # Recent Menu
        self.recent_menu = menubar.addMenu("🕘 Recent Models")

        # View Menu
        view_menu = menubar.addMenu("&View")
        theme_action = QAction("Toggle App Theme", self)
        theme_action.triggered.connect(self.toggle_app_theme)
        view_menu.addAction(theme_action)

        zoom_in_a = QAction("Zoom In", self)
        zoom_in_a.triggered.connect(lambda: self._run_canvas_js("window.__panZoom && window.__panZoom.zoomIn();"))
        view_menu.addAction(zoom_in_a)

        zoom_out_a = QAction("Zoom Out", self)
        zoom_out_a.triggered.connect(lambda: self._run_canvas_js("window.__panZoom && window.__panZoom.zoomOut();"))
        view_menu.addAction(zoom_out_a)

        fit_a = QAction("Fit to Canvas", self)
        fit_a.triggered.connect(lambda: self._run_canvas_js(
            "if(window.__panZoom){window.__panZoom.reset();window.__panZoom.fit();window.__panZoom.center();}"
        ))
        view_menu.addAction(fit_a)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self):
        QMessageBox.information(
            self, "About Odoo Architecture Studio",
            "Odoo Architecture Studio\n\n"
            "Generates live, interactive Mermaid.js diagrams (ER, Class, Flowchart, "
            "State/Workflow, Sequence) directly from an Odoo instance's model metadata.\n\n"
            "Shortcuts:\n"
            "  Ctrl+Enter   Generate diagram\n"
            "  Ctrl+R       Render edited code\n"
            "  Ctrl+S       Save .mmd source\n"
            "  Ctrl+Shift+C Copy code to clipboard"
        )

    # ------------------------------------------------------------------
    # Setup: central widget
    # ------------------------------------------------------------------
    def _create_central_widget(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 6, 10, 10)
        main_layout.setSpacing(6)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.setTextVisible(False)
        main_layout.addWidget(self.progress)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)

        # Left: Code Editor
        code_wrapper = QWidget()
        code_wrapper.setObjectName("panelCard")
        code_layout = QVBoxLayout(code_wrapper)
        code_layout.setContentsMargins(10, 10, 10, 10)
        code_layout.setSpacing(6)

        code_header_row = QHBoxLayout()
        code_header = QLabel("MERMAID CODE EDITOR")
        code_header.setObjectName("panelHeader")
        code_header_row.addWidget(code_header)
        code_header_row.addStretch(1)
        self.render_btn = QPushButton("▶ Render")
        self.render_btn.setToolTip("Re-render diagram from the code below (Ctrl+R)")
        self.render_btn.setFixedHeight(26)
        self.render_btn.clicked.connect(self.render_current_code)
        code_header_row.addWidget(self.render_btn)
        code_layout.addLayout(code_header_row)

        self.code_edit = QTextEdit()
        self.code_edit.setObjectName("codeEditor")
        self.code_edit.setFont(QFont("Fira Code", 10))
        self.code_edit.setPlaceholderText(
            "// Mermaid diagram definition will appear here once generated.\n"
            "// You can also hand-edit this and press ▶ Render (Ctrl+R)."
        )
        self.code_edit.textChanged.connect(self.on_code_edited)
        code_layout.addWidget(self.code_edit, 1)

        # Right: Tab Canvas
        tabs = QTabWidget()
        tabs.setObjectName("mainTabs")
        tabs.setDocumentMode(True)

        self.web_view = QWebEngineView()
        tabs.addTab(self.web_view, "🖼  Interactive Canvas")

        self.field_tree = QTextEdit()
        self.field_tree.setReadOnly(True)
        self.field_tree.setFont(QFont("Fira Code", 9))
        tabs.addTab(self.field_tree, "🗒  Schema Metadata")

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Fira Code", 9))
        tabs.addTab(self.log_view, "📜  Activity Log")

        splitter.addWidget(code_wrapper)
        splitter.addWidget(tabs)
        splitter.setSizes([420, 1080])

        main_layout.addWidget(splitter, 1)

        self._log("System ready. Open File → Odoo Connection to get started.")

    def _create_status_bar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.status_badge = QFrame()
        self.status_badge.setObjectName("statusBadge")
        badge_layout = QHBoxLayout(self.status_badge)
        badge_layout.setContentsMargins(10, 2, 10, 2)
        badge_layout.setSpacing(6)

        self.status_dot = QLabel("●")
        self.status_text = QLabel("Disconnected")
        self.status_text.setObjectName("statusText")

        badge_layout.addWidget(self.status_dot)
        badge_layout.addWidget(self.status_text)

        self.model_count_label = QLabel("")
        self.last_generated_label = QLabel("")

        self.status.addWidget(self.status_badge)
        self.status.addPermanentWidget(self.model_count_label)
        self.status.addPermanentWidget(self.last_generated_label)
        self.set_connection_status("disconnected", "Disconnected")

    def set_connection_status(self, state, text):
        self.status_text.setText(text)
        if state == "connected":
            self.status_dot.setStyleSheet("color: #a6e3a1; font-size: 14px;")
            self.status_badge.setStyleSheet("background: rgba(166, 227, 161, 0.15); border-radius: 12px;")
        elif state == "pending":
            self.status_dot.setStyleSheet("color: #f9e2af; font-size: 14px;")
            self.status_badge.setStyleSheet("background: rgba(249, 226, 175, 0.15); border-radius: 12px;")
        else:
            self.status_dot.setStyleSheet("color: #f38ba8; font-size: 14px;")
            self.status_badge.setStyleSheet("background: rgba(243, 139, 168, 0.15); border-radius: 12px;")

    def _log(self, message):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{stamp}] {message}")

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------
    def apply_app_theme(self, theme):
        accent = "#89b4fa" if theme == "dark" else "#1e66f5"
        accent_hover = "#74a8f8" if theme == "dark" else "#3b7bf6"
        if theme == "dark":
            style = """
                QMainWindow, QWidget#centralWidget {
                    background-color: #1e1e2e;
                    color: #cdd6f4;
                }
                QLabel {
                    color: #bac2de;
                    font-size: 12px;
                    font-weight: 500;
                }
                QLabel#panelHeader {
                    font-weight: 700;
                    font-size: 11px;
                    color: #a6adc8;
                    letter-spacing: 0.6px;
                }
                QLabel#popupTitle {
                    font-weight: 800;
                    font-size: 11px;
                    color: #89b4fa;
                    letter-spacing: 1px;
                    padding-bottom: 4px;
                }
                QLabel#statusText {
                    font-weight: 600;
                    font-size: 12px;
                }
                QWidget#panelCard {
                    background-color: #181825;
                    border: 1px solid #313244;
                    border-radius: 10px;
                }
                QTextEdit#codeEditor {
                    background-color: #11111b;
                    border: 1px solid #313244;
                    border-radius: 8px;
                    color: #cdd6f4;
                    selection-background-color: #45475a;
                    padding: 8px;
                }
                QLineEdit, QComboBox, QTextEdit {
                    background-color: #181825;
                    color: #cdd6f4;
                    border: 1px solid #313244;
                    border-radius: 6px;
                    padding: 6px 10px;
                }
                QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                    border: 1px solid %(accent)s;
                }
                QComboBox QAbstractItemView {
                    background-color: #181825;
                    color: #cdd6f4;
                    selection-background-color: #313244;
                    selection-color: %(accent)s;
                    border: 1px solid #313244;
                    outline: none;
                }
                QComboBox QAbstractItemView::item {
                    min-height: 24px;
                    background-color: #181825;
                    color: #cdd6f4;
                }
                QComboBox QAbstractItemView::item:selected {
                    background-color: #313244;
                    color: %(accent)s;
                }
                QPushButton, QToolButton {
                    background-color: #313244;
                    color: #cdd6f4;
                    border: 1px solid #45475a;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-weight: 600;
                }
                QPushButton:hover, QToolButton:hover {
                    background-color: #45475a;
                }
                QPushButton:pressed, QToolButton:pressed {
                    background-color: #585b70;
                }
                QPushButton#connectBtn {
                    background-color: #a6e3a1;
                    color: #11111b;
                    border: none;
                }
                QPushButton#connectBtn:hover { background-color: #94e2a5; }
                QPushButton#generateBtn {
                    background-color: %(accent)s;
                    color: #11111b;
                    border: none;
                }
                QPushButton#generateBtn:hover { background-color: %(accent_hover)s; }
                QToolBar#mainToolbar {
                    background-color: #181825;
                    border: none;
                    border-bottom: 1px solid #313244;
                    padding: 4px;
                    spacing: 4px;
                }
                QToolBar#mainToolbar QToolButton {
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                    padding: 5px 8px;
                    color: #cdd6f4;
                }
                QToolBar#mainToolbar QToolButton:hover {
                    background-color: #313244;
                    border: 1px solid #45475a;
                }
                QMenuBar {
                    background-color: #181825;
                    color: #cdd6f4;
                    font-weight: 600;
                }
                QMenuBar::item:selected {
                    background-color: #313244;
                    border-radius: 4px;
                }
                QMenu {
                    background-color: #1e1e2e;
                    color: #cdd6f4;
                    border: 1px solid #313244;
                    border-radius: 6px;
                }
                QMenu::item:selected {
                    background-color: #313244;
                    color: %(accent)s;
                }
                QTabWidget::pane {
                    background-color: #181825;
                    border: 1px solid #313244;
                    border-radius: 10px;
                }
                QTabBar::tab {
                    background-color: #252538;
                    color: #a6adc8;
                    padding: 8px 16px;
                    margin-right: 4px;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    font-weight: 600;
                }
                QTabBar::tab:selected {
                    background-color: #181825;
                    color: %(accent)s;
                    border-bottom: 2px solid %(accent)s;
                }
                QSplitter::handle {
                    background-color: #313244;
                    border-radius: 2px;
                }
                QCheckBox {
                    color: #cdd6f4;
                    font-size: 11px;
                }
                QStatusBar {
                    background-color: #181825;
                    border-top: 1px solid #313244;
                }
                QStatusBar QLabel {
                    color: #9399b2;
                    font-size: 11px;
                }
            """ % {"accent": accent, "accent_hover": accent_hover}
        else:
            style = """
                QMainWindow, QWidget#centralWidget {
                    background-color: #eff1f5;
                    color: #4c4f69;
                }
                QLabel {
                    color: #5c5f77;
                    font-size: 12px;
                    font-weight: 500;
                }
                QLabel#panelHeader {
                    font-weight: 700;
                    font-size: 11px;
                    color: #6c6f85;
                    letter-spacing: 0.6px;
                }
                QLabel#popupTitle {
                    font-weight: 800;
                    font-size: 11px;
                    color: #1e66f5;
                    letter-spacing: 1px;
                    padding-bottom: 4px;
                }
                QLabel#statusText {
                    font-weight: 600;
                    font-size: 12px;
                }
                QWidget#panelCard {
                    background-color: #ffffff;
                    border: 1px solid #ccd0da;
                    border-radius: 10px;
                }
                QTextEdit#codeEditor {
                    background-color: #ffffff;
                    border: 1px solid #ccd0da;
                    border-radius: 8px;
                    color: #4c4f69;
                    selection-background-color: #acb0be;
                    padding: 8px;
                }
                QLineEdit, QComboBox, QTextEdit {
                    background-color: #ffffff;
                    color: #4c4f69;
                    border: 1px solid #bcc0cc;
                    border-radius: 6px;
                    padding: 6px 10px;
                }
                QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                    border: 1px solid %(accent)s;
                }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #4c4f69;
                    selection-background-color: #e6e9ef;
                    selection-color: %(accent)s;
                    border: 1px solid #bcc0cc;
                    outline: none;
                }
                QComboBox QAbstractItemView::item {
                    min-height: 24px;
                    background-color: #ffffff;
                    color: #4c4f69;
                }
                QComboBox QAbstractItemView::item:selected {
                    background-color: #e6e9ef;
                    color: %(accent)s;
                }
                QPushButton, QToolButton {
                    background-color: #e6e9ef;
                    color: #4c4f69;
                    border: 1px solid #bcc0cc;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-weight: 600;
                }
                QPushButton:hover, QToolButton:hover {
                    background-color: #dce0e8;
                }
                QPushButton:pressed, QToolButton:pressed {
                    background-color: #ccd0da;
                }
                QPushButton#connectBtn {
                    background-color: #40a02b;
                    color: #ffffff;
                    border: none;
                }
                QPushButton#connectBtn:hover { background-color: #379e2f; }
                QPushButton#generateBtn {
                    background-color: %(accent)s;
                    color: #ffffff;
                    border: none;
                }
                QPushButton#generateBtn:hover { background-color: %(accent_hover)s; }
                QToolBar#mainToolbar {
                    background-color: #ffffff;
                    border: none;
                    border-bottom: 1px solid #ccd0da;
                    padding: 4px;
                    spacing: 4px;
                }
                QToolBar#mainToolbar QToolButton {
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                    padding: 5px 8px;
                    color: #4c4f69;
                }
                QToolBar#mainToolbar QToolButton:hover {
                    background-color: #e6e9ef;
                    border: 1px solid #bcc0cc;
                }
                QMenuBar {
                    background-color: #ffffff;
                    color: #4c4f69;
                    font-weight: 600;
                }
                QMenuBar::item:selected {
                    background-color: #e6e9ef;
                    border-radius: 4px;
                }
                QMenu {
                    background-color: #ffffff;
                    color: #4c4f69;
                    border: 1px solid #ccd0da;
                    border-radius: 6px;
                }
                QMenu::item:selected {
                    background-color: #e6e9ef;
                    color: %(accent)s;
                }
                QTabWidget::pane {
                    background-color: #ffffff;
                    border: 1px solid #ccd0da;
                    border-radius: 10px;
                }
                QTabBar::tab {
                    background-color: #e6e9ef;
                    color: #6c6f85;
                    padding: 8px 16px;
                    margin-right: 4px;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    font-weight: 600;
                }
                QTabBar::tab:selected {
                    background-color: #ffffff;
                    color: %(accent)s;
                    border-bottom: 2px solid %(accent)s;
                }
                QSplitter::handle {
                    background-color: #ccd0da;
                    border-radius: 2px;
                }
                QCheckBox {
                    color: #4c4f69;
                    font-size: 11px;
                }
                QStatusBar {
                    background-color: #ffffff;
                    border-top: 1px solid #ccd0da;
                }
                QStatusBar QLabel {
                    color: #6c6f85;
                    font-size: 11px;
                }
            """ % {"accent": accent, "accent_hover": accent_hover}
        self.setStyleSheet(style)
        self.current_app_theme = theme
        self.settings.setValue("theme", theme)
        if self.current_mermaid:
            self.render_diagram(self.current_mermaid)
        else:
            self._show_welcome_canvas()

    def toggle_app_theme(self):
        new_theme = "light" if self.current_app_theme == "dark" else "dark"
        self.apply_app_theme(new_theme)

    # ------------------------------------------------------------------
    # Connection persistence
    # ------------------------------------------------------------------
    def _restore_connection_fields(self):
        if self.settings.value("remember", "true") == "true":
            self.url_edit.setText(self.settings.value("last_url", ""))
            self.db_edit.setText(self.settings.value("last_db", ""))
            self.user_edit.setText(self.settings.value("last_user", ""))

    def _persist_connection_fields(self):
        if self.remember_chk.isChecked():
            self.settings.setValue("remember", "true")
            self.settings.setValue("last_url", self.url_edit.text().strip())
            self.settings.setValue("last_db", self.db_edit.text().strip())
            self.settings.setValue("last_user", self.user_edit.text().strip())
        else:
            self.settings.setValue("remember", "false")
            self.settings.remove("last_url")
            self.settings.remove("last_db")
            self.settings.remove("last_user")

    # ------------------------------------------------------------------
    # Recent models
    # ------------------------------------------------------------------
    def _push_recent_model(self, model_technical_name, mode):
        entry = {"model": model_technical_name, "mode": mode}
        self.recent_models = [e for e in self.recent_models if e.get("model") != model_technical_name]
        self.recent_models.insert(0, entry)
        self.recent_models = self.recent_models[:MAX_RECENT]
        self.settings.setValue("recent_models", json.dumps(self.recent_models))
        self._refresh_recent_menu()

    def _refresh_recent_menu(self):
        self.recent_menu.clear()
        if not self.recent_models:
            empty = QAction("(No recent models yet)", self)
            empty.setEnabled(False)
            self.recent_menu.addAction(empty)
            return
        for entry in self.recent_models:
            model_name = entry.get("model", "")
            mode = entry.get("mode", "ER Diagram")
            icon = DIAGRAM_ICONS.get(mode, "•")
            act = QAction(f"{icon}  {model_name}  —  {mode}", self)
            act.triggered.connect(lambda checked=False, m=model_name, mo=mode: self._select_and_generate(m, mo))
            self.recent_menu.addAction(act)
        self.recent_menu.addSeparator()
        clear_act = QAction("Clear Recent", self)
        clear_act.triggered.connect(self._clear_recent)
        self.recent_menu.addAction(clear_act)

    def _clear_recent(self):
        self.recent_models = []
        self.settings.setValue("recent_models", "[]")
        self._refresh_recent_menu()

    def _select_and_generate(self, model_name, mode):
        idx = self.model_combo.findData(model_name)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        else:
            self.model_combo.setEditText(model_name)
        mode_idx = self.type_combo.findData(mode)
        if mode_idx >= 0:
            self.type_combo.setCurrentIndex(mode_idx)
        self.generate_diagram()

    # ------------------------------------------------------------------
    # Handlers & Logic
    # ------------------------------------------------------------------
    def connect_odoo(self):
        url = self.url_edit.text().strip().rstrip('/')
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
            self.url_edit.setText(url)
        db = self.db_edit.text().strip()
        user = self.user_edit.text().strip()
        pwd = self.pass_edit.text().strip()

        if not all([url, db, user, pwd]):
            QMessageBox.warning(self, "Missing Credentials", "Please enter all Odoo server details.")
            return

        self._persist_connection_fields()
        self.set_connection_status("pending", "Authenticating...")
        self.connect_btn.setEnabled(False)

        self.worker = OdooWorker(url, db, user, pwd)
        self.worker.finished.connect(self._on_connect_finished)
        self.worker.error.connect(self._on_connect_error)
        self.worker.progress.connect(self.progress.setValue)
        self.progress.setVisible(True)
        self.worker.start()

    def _on_connect_finished(self, result):
        self.progress.setVisible(False)
        self.connect_btn.setEnabled(True)
        self.set_connection_status("connected", "Connected")
        self.uid = True
        self._log("✓ Successfully authenticated with Odoo instance.")
        self.fetch_models()

    def _on_connect_error(self, err):
        self.progress.setVisible(False)
        self.connect_btn.setEnabled(True)
        self.set_connection_status("disconnected", "Connection Failed")
        self._log(f"✗ Connection failed: {err}")
        QMessageBox.critical(self, "Connection Error", err)

    def fetch_models(self):
        if not self.uid:
            QMessageBox.warning(self, "Not Connected", "Establish connection first.")
            return

        self.set_connection_status("pending", "Fetching Models...")
        self.progress.setVisible(True)
        self.worker = OdooWorker(
            self.url_edit.text(), self.db_edit.text(),
            self.user_edit.text(), self.pass_edit.text()
        )
        self.worker.finished.connect(self._on_models_fetched)
        self.worker.error.connect(self._on_fetch_error)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.start()

    def _on_models_fetched(self, models):
        self.progress.setVisible(False)
        self.set_connection_status("connected", "Connected")
        self.all_models = models
        self.model_combo.clear()
        for m in sorted(models, key=lambda x: x['name']):
            display = f"{m['name']} ({m['model']})"
            self.model_combo.addItem(display, m['model'])
        if self.model_combo.count() > 0:
            self.model_combo.setCurrentIndex(0)

        # Search-as-you-type filtering on the editable combo box
        completer = QCompleter([f"{m['name']} ({m['model']})" for m in models], self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.model_combo.setCompleter(completer)

        self.model_count_label.setText(f"  {len(models)} models loaded  ")
        self._log(f"✓ Loaded {len(models)} Odoo models.")

    def _on_fetch_error(self, err):
        self.progress.setVisible(False)
        self.set_connection_status("disconnected", "Error")
        self._log(f"✗ Failed to fetch models: {err}")
        QMessageBox.critical(self, "Fetch Error", err)

    def _resolve_selected_model(self):
        model_data = self.model_combo.currentData()
        if not model_data:
            model_data = self.model_combo.currentText().strip()
            match = re.search(r'\((.+)\)$', model_data)
            if match:
                model_data = match.group(1)
        return model_data

    def generate_diagram(self):
        if not self.uid:
            QMessageBox.warning(self, "Not Connected", "Connect to Odoo server first via File → Odoo Connection.")
            return

        model_data = self._resolve_selected_model()
        if not model_data:
            QMessageBox.warning(self, "Invalid Selection", "Please select a model in Diagram Settings.")
            return

        if not self.chk_basic.isChecked() and not self.chk_relations.isChecked():
            QMessageBox.warning(
                self, "No Fields Selected",
                "Enable at least one of 'Basic attributes' or 'Relational fields' in Diagram Settings."
            )
            return

        mode = self.type_combo.currentData() or self.type_combo.currentText()
        self.set_connection_status("pending", f"Generating {mode}...")
        self.progress.setVisible(True)
        self.generate_btn.setEnabled(False)

        self.worker = OdooWorker(
            self.url_edit.text(), self.db_edit.text(),
            self.user_edit.text(), self.pass_edit.text(),
            model=model_data, mode=mode,
            include_basic=self.chk_basic.isChecked(),
            include_relations=self.chk_relations.isChecked(),
        )
        self.worker.finished.connect(lambda result, m=model_data, mo=mode: self._on_diagram_generated(result, m, mo))
        self.worker.error.connect(self._on_generate_error)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.start()

    def _on_diagram_generated(self, result, model_name, mode):
        self.progress.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.set_connection_status("connected", "Diagram Ready")
        code = result['code']
        fields = result['fields']
        self.current_mermaid = code
        self.code_edit.blockSignals(True)
        self.code_edit.setPlainText(code)
        self.code_edit.blockSignals(False)
        self.render_diagram(code)

        detail_text = f"MODEL SCHEMA METADATA — {model_name}\n{'=' * 50}\n"
        detail_text += f"Total fields: {len(fields)}\n\n"
        for fname, finfo in sorted(fields.items()):
            detail_text += f"• {fname}\n"
            detail_text += f"  Type:     {finfo.get('type')}\n"
            detail_text += f"  Label:    {finfo.get('string', '')}\n"
            if finfo.get('relation'):
                detail_text += f"  Relation: {finfo.get('relation')}\n"
            detail_text += "\n"
        self.field_tree.setPlainText(detail_text)

        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.last_generated_label.setText(f"  Last generated: {stamp}  ")
        self._log(f"✓ Rendered {mode} for [{model_name}] ({len(fields)} fields).")
        self._push_recent_model(model_name, mode)

    def _on_generate_error(self, err):
        self.progress.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.set_connection_status("connected", "Error")
        self._log(f"✗ Generation failed: {err}")
        QMessageBox.critical(self, "Generation Error", err)

    def render_current_code(self):
        """Re-render whatever is currently in the code editor (manual edits included)."""
        code = self.code_edit.toPlainText().strip()
        if not code:
            QMessageBox.information(self, "Nothing to Render", "The code editor is empty.")
            return
        self.current_mermaid = code
        self.render_diagram(code)
        self._log("✓ Re-rendered diagram from editor contents.")

    # ------------------------------------------------------------------
    # Canvas rendering
    # ------------------------------------------------------------------
    def _show_welcome_canvas(self):
        bg = "#181825" if self.current_app_theme == "dark" else "#ffffff"
        fg = "#cdd6f4" if self.current_app_theme == "dark" else "#4c4f69"
        sub = "#7f849c" if self.current_app_theme == "dark" else "#8c8fa1"
        accent = "#89b4fa" if self.current_app_theme == "dark" else "#1e66f5"
        html = f"""
        <!DOCTYPE html><html><head><meta charset="utf-8"><style>
            html, body {{
                margin:0; padding:0; height:100%; width:100%;
                background: {bg};
                display:flex; align-items:center; justify-content:center;
                font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
                color:{fg};
            }}
            .wrap {{ text-align:center; max-width:520px; }}
            .glyph {{ font-size:56px; margin-bottom:10px; opacity:0.9; }}
            h1 {{ font-size:20px; margin:6px 0; font-weight:700; color:{accent}; }}
            p {{ font-size:13px; color:{sub}; line-height:1.6; margin:4px 0; }}
            .kbd {{ background: rgba(128,128,128,0.15); border-radius:4px; padding:1px 6px; font-family: monospace; }}
        </style></head><body>
            <div class="wrap">
                <div class="glyph">🧭</div>
                <h1>No Diagram Yet</h1>
                <p>Connect to an Odoo instance, pick a model and diagram mode, then hit
                <span class="kbd">Generate</span> to render an interactive, pannable, zoomable diagram here.</p>
                <p>You can also hand-write Mermaid code on the left and press
                <span class="kbd">Ctrl+R</span> to render it directly.</p>
            </div>
        </body></html>
        """
        self.web_view.setHtml(html)

    def render_diagram(self, code):
        theme = self.theme_combo.currentText()
        bg_color = "#181825" if self.current_app_theme == "dark" else "#ffffff"
        fg_color = "#cdd6f4" if self.current_app_theme == "dark" else "#4c4f69"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
            <style>
                html, body {{
                    background-color: {bg_color};
                    margin: 0;
                    padding: 0;
                    width: 100vw;
                    height: 100vh;
                    overflow: hidden;
                    font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
                }}
                #container {{
                    width: 100vw;
                    height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }}
                .mermaid {{
                    width: 100%;
                    height: 100%;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }}
                svg {{
                    width: 100% !important;
                    height: 100% !important;
                    max-width: none !important;
                    max-height: none !important;
                }}
                #err-banner {{
                    display:none;
                    position:absolute; top:12px; left:50%; transform:translateX(-50%);
                    background:#f38ba8; color:#11111b; font-size:12px; font-weight:600;
                    padding:8px 14px; border-radius:8px; max-width:80%;
                    box-shadow:0 4px 14px rgba(0,0,0,0.25);
                }}
                #hint {{
                    position:absolute; bottom:10px; right:14px;
                    font-size:11px; color:{fg_color}; opacity:0.45;
                    font-family: monospace;
                }}
            </style>
        </head>
        <body>
            <div id="err-banner"></div>
            <div id="container">
                <div class="mermaid" id="mmd">
                {code}
                </div>
            </div>
            <div id="hint">scroll to zoom · drag to pan</div>
            <script>
                try {{
                    mermaid.initialize({{ startOnLoad: false, theme: '{theme}', securityLevel: 'loose' }});
                    mermaid.run({{ querySelector: '.mermaid' }}).then(() => {{
                        setTimeout(() => {{
                            const svg = document.querySelector("svg");
                            if (svg) {{
                                const panZoom = svgPanZoom(svg, {{
                                    zoomEnabled: true,
                                    controlIconsEnabled: true,
                                    fit: true,
                                    center: true,
                                    minZoom: 0.05,
                                    maxZoom: 15
                                }});
                                panZoom.resize();
                                panZoom.fit();
                                panZoom.center();
                                window.__panZoom = panZoom;
                            }}
                        }}, 300);
                    }}).catch(e => {{
                        const b = document.getElementById('err-banner');
                        b.style.display = 'block';
                        b.innerText = 'Mermaid syntax error: ' + e.message;
                    }});
                }} catch (e) {{
                    const b = document.getElementById('err-banner');
                    b.style.display = 'block';
                    b.innerText = 'Mermaid error: ' + e.message;
                }}
            </script>
        </body>
        </html>
        """
        self.web_view.setHtml(html)

    def on_code_edited(self):
        self.current_mermaid = self.code_edit.toPlainText()

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------
    def open_mermaid_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Mermaid Source", "", "Mermaid Files (*.mmd *.mermaid *.txt);;All Files (*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Open Failed", str(e))
            return
        self.code_edit.setPlainText(content)
        self.current_mermaid = content
        self.render_diagram(content)
        self._log(f"✓ Loaded Mermaid source from {file_path}")

    def export_diagram(self, fmt):
        if not self.current_mermaid:
            QMessageBox.warning(self, "No Diagram", "Generate or write a diagram first.")
            return

        if fmt == "mmd":
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Mermaid Source", "diagram.mmd", "Mermaid Files (*.mmd)")
            if file_path:
                self._write_text_file(file_path, self.current_mermaid)

        elif fmt == "html":
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Diagram HTML", "diagram.html", "HTML Files (*.html)")
            if file_path:
                self.web_view.page().toHtml(lambda html_content: self._write_text_file(file_path, html_content))

        elif fmt == "svg":
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Diagram SVG", "diagram.svg", "SVG Files (*.svg)")
            if file_path:
                script = "document.querySelector('svg') ? document.querySelector('svg').outerHTML : ''"
                self.web_view.page().runJavaScript(
                    script, lambda svg_content: self._write_svg(file_path, svg_content)
                )

        elif fmt == "png":
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Diagram PNG", "diagram.png", "PNG Files (*.png)")
            if file_path:
                # Snapshot the current canvas widget as a pixmap.
                pixmap = self.web_view.grab()
                if pixmap.save(file_path, "PNG"):
                    QMessageBox.information(self, "Exported", f"Snapshot saved to {file_path}")
                    self._log(f"✓ Exported PNG snapshot to {file_path}")
                else:
                    QMessageBox.critical(self, "Export Failed", "Could not save PNG snapshot.")

    def _write_svg(self, path, svg_content):
        if not svg_content:
            QMessageBox.warning(self, "Export Failed", "Could not read SVG from the canvas. Generate a diagram first.")
            return
        self._write_text_file(path, svg_content)

    def _write_text_file(self, path, content):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))
            return
        QMessageBox.information(self, "Exported", f"Saved to {path}")
        self._log(f"✓ Saved file to {path}")

    def copy_code(self):
        if not self.current_mermaid:
            QMessageBox.warning(self, "No Source Code", "Generate a diagram first.")
            return
        QApplication.clipboard().setText(self.current_mermaid)
        self._log("✓ Mermaid code copied to clipboard.")

    def reset_workspace(self):
        confirm = QMessageBox.question(
            self, "Reset Workspace",
            "Clear the current diagram, code editor and logs? This does not disconnect from Odoo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.current_mermaid = ""
        self.code_edit.clear()
        self.field_tree.clear()
        self.log_view.clear()
        self._show_welcome_canvas()
        self._log("Workspace reset.")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = OdooMermaidStudio()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

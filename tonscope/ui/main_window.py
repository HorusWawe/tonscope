from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QProgressBar,
    QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget, QHeaderView,
)

from tonscope import __version__
from tonscope.core.config import AppConfig, data_dir
from tonscope.core.scanner import ScanWorker, RecheckWorker, RatesWorker
from tonscope.core.valuation import comparable_range
from tonscope.storage.database import Database

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def profile_database_path(profile: str) -> Path:
    if not re.fullmatch(r"[a-z0-9_-]{1,32}", profile):
        profile = "default"
    target = data_dir() / "profiles" / profile / "tonscope.db"
    if profile == "default" and not target.exists():
        legacy = PROJECT_ROOT / "user_data" / "profiles" / "default" / "tonscope.db"
        if legacy.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, target)
    return target

STYLE = """
QWidget { background:#111216; color:#e8e9ef; font-family:'Segoe UI'; font-size:10pt; }
QFrame#Sidebar { background:#17191f; border:1px solid #252832; border-radius:14px; }
QFrame#Panel { background:#191b22; border:1px solid #292c36; border-radius:12px; }
QLabel#Brand { font-size:20pt; font-weight:800; letter-spacing:2px; }
QLabel#Muted { color:#858b9b; }
QLabel#Metric { font-size:23pt; font-weight:700; }
QPushButton { background:#252832; border:1px solid #343846; border-radius:8px; padding:9px 14px; }
QPushButton:hover { background:#303542; }
QPushButton:disabled { color:#666b78; background:#1d2028; }
QPushButton#Primary { background:#b8f36b; color:#151810; border:0; font-weight:700; }
QPushButton#Danger { background:#49252b; color:#ffb8c0; border:1px solid #71343d; }
QLineEdit,QComboBox,QSpinBox { background:#20232b; border:1px solid #353a47; border-radius:7px; padding:8px; }
QTableWidget { background:#17191f; alternate-background-color:#1c1f27; gridline-color:#292d37; border:1px solid #292d37; border-radius:10px; }
QHeaderView::section { background:#20232b; color:#9da4b5; padding:8px; border:0; }
QTableWidget::item { padding:5px; }
QProgressBar { background:#20232b; border:1px solid #353a47; border-radius:5px; text-align:center; height:14px; }
QProgressBar::chunk { background:#b8f36b; border-radius:4px; }
"""

class MetricCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("Panel")
        box = QVBoxLayout(self)
        caption = QLabel(title)
        caption.setObjectName("Muted")
        self.value = QLabel("0")
        self.value.setObjectName("Metric")
        box.addWidget(caption)
        box.addWidget(self.value)

    def set_value(self, value: int) -> None:
        self.value.setText(str(value))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = AppConfig()
        configured_profile = str(self.config.values.get("profile", "default"))
        self.profile_name = configured_profile if re.fullmatch(r"[a-z0-9_-]{1,32}", configured_profile) else "default"
        self.db = Database(profile_database_path(self.profile_name))
        self.worker = None
        self.rates_worker = None
        self.ton_usd = None
        self.usd_rub = None
        self.setWindowTitle(f"TONSCOPE · Username Intelligence · v{__version__}")
        self.resize(1320, 820)
        self.setMinimumSize(1050, 680)
        self._build()
        self._load_settings()
        self.refresh_all()
        self.refresh_rates()

    def _build(self):
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(16)
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        side = QVBoxLayout(sidebar)
        brand = QLabel("TONSCOPE")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        sub = QLabel("USERNAME INTELLIGENCE")
        sub.setObjectName("Muted")
        side.addWidget(sub)
        side.addSpacing(24)

        self.pages = QStackedWidget()
        self.nav = []
        for label, index in (("Overview", 0), ("New available", 1), ("Saved", 2), ("Checked", 3), ("Settings", 4)):
            button = QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.pages.setCurrentIndex(i))
            side.addWidget(button)
            self.nav.append(button)
        self.nav[0].setChecked(True)
        side.addStretch()
        self.profile_label = QLabel(f"PROFILE\n{self.profile_name}")
        self.profile_label.setObjectName("Muted")
        side.addWidget(self.profile_label)

        self.pages.addWidget(self._dashboard())
        self.pages.addWidget(self._list_page("new"))
        self.pages.addWidget(self._list_page("saved"))
        self.pages.addWidget(self._list_page("checked"))
        self.pages.addWidget(self._settings())
        self.pages.currentChanged.connect(self._page_changed)
        outer.addWidget(sidebar)
        outer.addWidget(self.pages, 1)
        self.setCentralWidget(root)

    def _page_changed(self, index):
        for i, button in enumerate(self.nav):
            button.setChecked(i == index)
        if index in (1, 2, 3):
            self.refresh_table(index)

    def _table(self):
        table = QTableWidget(0, 8)
        table.setHorizontalHeaderLabels(["Username", "Status", "Length", "Score", "Readability", "Liquidity", "Fragment ask", "Comparable range"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        return table

    def _dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel("Dashboard")
        heading.setStyleSheet("font-size:22pt;font-weight:700")
        layout.addWidget(heading)
        subtitle = QLabel("Generate readable names, check Telegram and Fragment, save the useful ones.")
        subtitle.setObjectName("Muted")
        layout.addWidget(subtitle)

        metrics = QHBoxLayout()
        self.metric_total = MetricCard("IN PROFILE")
        self.metric_available = MetricCard("CONFIRMED AVAILABLE")
        self.metric_saved = MetricCard("SAVED")
        self.metric_candidates = MetricCard("WAITING TO CHECK")
        self.metric_occupied = MetricCard("OCCUPIED")
        self.metric_fragment = MetricCard("FRAGMENT COLLECTIBLES")
        for card in (self.metric_total, self.metric_available, self.metric_saved, self.metric_candidates, self.metric_occupied, self.metric_fragment):
            metrics.addWidget(card)
        layout.addLayout(metrics)

        panel = QFrame()
        panel.setObjectName("Panel")
        controls = QVBoxLayout(panel)
        title = QLabel("Live scan")
        title.setStyleSheet("font-size:14pt;font-weight:650")
        controls.addWidget(title)
        row = QHBoxLayout()
        self.length = QComboBox()
        self.length.addItems(["5 letters", "6 letters", "7 letters", "Mixed 5-7"])
        self.length.setCurrentIndex(3)
        self.mode = QComboBox()
        self.mode.addItem("Readable", "readable")
        self.mode.addItem("Word-like", "words")
        self.mode.addItem("Brandable", "brand")
        self.mode.addItem("Random", "random")
        self.target = QSpinBox()
        self.target.setRange(0, 1000000)
        self.target.setValue(25)
        self.target.setSpecialValueText("Until STOP")
        self.min_score = QSpinBox()
        self.min_score.setRange(1, 10)
        self.min_score.setValue(int(self.config.values.get("min_score", 5)))
        for label, widget in (("Length", self.length), ("Generation", self.mode), ("Free hits", self.target), ("Min score", self.min_score)):
            row.addWidget(QLabel(label))
            row.addWidget(widget, 1)
        controls.addLayout(row)

        actions = QHBoxLayout()
        self.start = QPushButton("START LIVE SCAN")
        self.start.setObjectName("Primary")
        self.start.clicked.connect(self.start_scan)
        self.stop = QPushButton("STOP")
        self.stop.setObjectName("Danger")
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self.stop_scan)
        recheck = QPushButton("Recheck saved")
        recheck.clicked.connect(self.recheck_saved)
        actions.addWidget(self.start)
        actions.addWidget(self.stop)
        actions.addWidget(recheck)
        controls.addLayout(actions)
        self.status = QLabel("Ready · candidates are checked in batches and saved automatically.")
        self.status.setObjectName("Muted")
        controls.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Checked %v")
        controls.addWidget(self.progress)
        layout.addWidget(panel)

        layout.addWidget(QLabel("Latest available usernames"))
        self.recent = self._table()
        layout.addWidget(self.recent, 1)
        return page

    def _list_page(self, view):
        page = QWidget()
        layout = QVBoxLayout(page)
        title = {"new":"New available usernames","saved":"Saved usernames","checked":"All checked usernames"}[view]
        heading = QLabel(title)
        heading.setStyleSheet("font-size:22pt;font-weight:700")
        layout.addWidget(heading)
        search = QLineEdit()
        search.setPlaceholderText("Filter usernames…")
        search.textChanged.connect(lambda value, v=view: self.refresh_table({"new":1,"saved":2,"checked":3}[v], value))
        layout.addWidget(search)
        table = self._table()
        setattr(self, f"{view}_table", table)
        layout.addWidget(table, 1)
        actions = QHBoxLayout()
        copy = QPushButton("Copy selected")
        copy.clicked.connect(lambda checked=False, t=table: self.copy_selected(t))
        save = QPushButton("Save / unsave")
        save.clicked.connect(lambda checked=False, t=table: self.toggle_selected(t))
        recheck = QPushButton("Recheck selected")
        recheck.clicked.connect(lambda checked=False, t=table: self.recheck_selected(t))
        export = QPushButton("Export")
        export.clicked.connect(lambda checked=False, v=view: self.export_view(v))
        for button in (copy, save, recheck, export):
            actions.addWidget(button)
        layout.addLayout(actions)
        return page

    def _settings(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel("Settings")
        heading.setStyleSheet("font-size:22pt;font-weight:700")
        layout.addWidget(heading)
        panel = QFrame()
        panel.setObjectName("Panel")
        form = QFormLayout(panel)
        self.profile_combo = QComboBox()
        self.api_url = QLineEdit()
        self.rpm = QSpinBox()
        self.rpm.setRange(1, 24)
        self.rpm.setSuffix(" requests/min")
        form.addRow("Active profile", self.profile_combo)
        form.addRow("Public checker API", self.api_url)
        form.addRow("API request limit", self.rpm)
        layout.addWidget(panel)
        buttons = QHBoxLayout()
        save = QPushButton("Save settings")
        save.setObjectName("Primary")
        save.clicked.connect(self.save_settings)
        rates = QPushButton("Refresh TON / USD / RUB rates")
        rates.clicked.connect(self.refresh_rates)
        create_profile = QPushButton("New profile")
        create_profile.clicked.connect(self.create_profile)
        switch_profile = QPushButton("Switch profile")
        switch_profile.clicked.connect(self.switch_profile)
        buttons.addWidget(save)
        buttons.addWidget(rates)
        buttons.addWidget(create_profile)
        buttons.addWidget(switch_profile)
        layout.addLayout(buttons)
        self.settings_info = QLabel("Public Telegram + Fragment resolver. No Telegram login required. Bulk size: up to 15 names/request. Service limit: 25 requests/minute. TON ask is shown only when Fragment returns an observed price. Comparable ranges require at least 3 active listings.")
        self.settings_info.setObjectName("Muted")
        self.settings_info.setWordWrap(True)
        layout.addWidget(self.settings_info)
        layout.addStretch()
        return page

    def _load_settings(self):
        self.api_url.setText(self.config.values.get("api_url", ""))
        self.rpm.setValue(int(self.config.values.get("requests_per_minute", 20)))
        profiles = data_dir() / "profiles"
        profiles.mkdir(parents=True, exist_ok=True)
        names = sorted(p.name for p in profiles.iterdir() if p.is_dir())
        if self.profile_name not in names:
            names.append(self.profile_name)
        self.profile_combo.addItems(names)
        self.profile_combo.setCurrentText(self.profile_name)

    def create_profile(self):
        name, accepted = QInputDialog.getText(self, "New profile", "Profile name (letters, numbers, dash, underscore):")
        if not accepted:
            return
        import re
        clean = name.strip().lower()
        if not re.fullmatch(r"[a-z0-9_-]{1,32}", clean):
            QMessageBox.warning(self, "Invalid profile", "Use 1-32 characters: a-z, 0-9, dash or underscore.")
            return
        profile_path = data_dir() / "profiles" / clean
        profile_path.mkdir(parents=True, exist_ok=True)
        if self.profile_combo.findText(clean) < 0:
            self.profile_combo.addItem(clean)
        self.profile_combo.setCurrentText(clean)
        self.status.setText(f"Profile {clean} created. Click Switch profile to activate it.")

    def switch_profile(self):
        name = self.profile_combo.currentText().strip()
        import re
        if not re.fullmatch(r"[a-z0-9_-]{1,32}", name):
            QMessageBox.warning(self, "Invalid profile", "Invalid profile name.")
            return
        if self.worker and self.worker.isRunning():
            self.status.setText("Stop the active scan before switching profiles.")
            return
        self.profile_name = name
        self.db = Database(profile_database_path(name))
        self.config.values["profile"] = name
        self.config.save()
        self.profile_label.setText(f"PROFILE\n{name}")
        self.refresh_all()
        self.status.setText(f"Switched to profile: {name}")

    def save_settings(self):
        self.config.values["api_url"] = self.api_url.text().strip().rstrip("/")
        self.config.values["requests_per_minute"] = self.rpm.value()
        self.config.values["min_score"] = self.min_score.value()
        self.config.save()
        self.status.setText("Settings saved to the local TONSCOPE profile.")

    def start_scan(self):
        if self.worker and self.worker.isRunning():
            return
        mixed = self.length.currentIndex() == 3
        self.worker = ScanWorker(
            self.db, 6 if mixed else self.length.currentIndex() + 5, self.mode.currentData(),
            self.target.value(), self.min_score.value(), self.rpm.value(), self.api_url.text().strip()
        )
        self.worker.mixed_lengths = mixed
        self.worker.message.connect(self.status.setText)
        self.worker.progress.connect(self.on_progress)
        self.worker.candidate_checked.connect(self.on_checked)
        self.worker.finished_summary.connect(self.on_finished)
        self.start.setEnabled(False)
        self.stop.setEnabled(True)
        self.worker.start()

    def stop_scan(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.status.setText("Stopping after current request… results are already saved.")

    def on_progress(self, checked, available, processed):
        self.progress.setRange(0, 0)
        self.status.setText(f"Checked {checked} · free {available} · generated {processed}")

    def on_checked(self, username, status, row):
        self.refresh_stats()
        if status == "available":
            self.refresh_table(1)
            self.refresh_recent()

    def on_finished(self, summary):
        self.start.setEnabled(True)
        self.stop.setEnabled(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if summary.get("checked") else 0)
        self.status.setText(f"Finished · checked {summary.get('checked',0)} · free {summary.get('available',0)} · generated {summary.get('generated',0)}")
        self.refresh_all()

    def _price_text(self, item):
        value = item.get("fragment_price_ton")
        if value is None:
            return "—"
        usd = value * self.ton_usd if self.ton_usd else None
        rub = usd * self.usd_rub if usd is not None and self.usd_rub else None
        parts = [f"{value:g} TON"]
        if usd is not None:
            parts.append(f"USD {usd:,.2f}")
        if rub is not None:
            parts.append(f"RUB {rub:,.0f}")
        return " · ".join(parts)

    def _range_text(self, item):
        estimate = comparable_range(self.db.comparable_prices(len(item["username"]), item.get("overall", 0)))
        if estimate is None:
            return "Not enough comps"
        low, high = estimate
        text = f"{low:g}–{high:g} TON"
        if self.ton_usd:
            text += f" · USD {low*self.ton_usd:,.0f}–{high*self.ton_usd:,.0f}"
        if self.ton_usd and self.usd_rub:
            text += f" · RUB {low*self.ton_usd*self.usd_rub:,.0f}–{high*self.ton_usd*self.usd_rub:,.0f}"
        return text

    def add_row(self, table, item):
        row = table.rowCount()
        table.insertRow(row)
        status = item.get("status", "candidate")
        frag = item.get("fragment_status")
        label = {
            "available":"AVAILABLE", "occupied":"OCCUPIED", "auction":"FRAGMENT AUCTION",
            "fragment_collectible":"FRAGMENT COLLECTIBLE", "check_error":"CHECK ERROR",
            "candidate":"NOT CHECKED", "invalid":"INVALID",
        }.get(status, status.upper())
        if frag and status not in ("auction", "fragment_collectible"):
            label += f" · {frag}"
        values = ["@" + item["username"], label, len(item["username"]), item.get("overall",0),
                  item.get("readability",0), item.get("liquidity",0), self._price_text(item), self._range_text(item)]
        for col, value in enumerate(values):
            cell = QTableWidgetItem(str(value))
            if col == 0:
                cell.setData(Qt.ItemDataRole.UserRole, item["username"])
            table.setItem(row, col, cell)

    def refresh_stats(self):
        stats = self.db.stats()
        self.metric_total.set_value(stats["total"])
        self.metric_available.set_value(stats["available"])
        self.metric_saved.set_value(stats["saved"])
        self.metric_candidates.set_value(stats["candidates"])
        self.metric_occupied.set_value(stats["occupied"])
        self.metric_fragment.set_value(stats["fragment"])

    def refresh_table(self, index, query=""):
        view = {1:"new", 2:"saved", 3:"checked"}[index]
        table = getattr(self, f"{view}_table")
        table.setRowCount(0)
        for item in self.db.list_usernames(view, min_score=self.min_score.value()):
            if query and query.lower().strip("@") not in item["username"].lower():
                continue
            self.add_row(table, item)

    def refresh_recent(self):
        self.recent.setRowCount(0)
        for item in self.db.list_usernames("new", 15):
            self.add_row(self.recent, item)

    def refresh_all(self):
        self.refresh_stats()
        for index in (1,2,3):
            attr = {1:"new_table",2:"saved_table",3:"checked_table"}[index]
            if hasattr(self, attr):
                self.refresh_table(index)
        if hasattr(self, "recent"):
            self.refresh_recent()

    def selected_usernames(self, table):
        rows = sorted({index.row() for index in table.selectionModel().selectedRows()})
        return [table.item(row, 0).data(Qt.ItemDataRole.UserRole) for row in rows if table.item(row,0)]

    def copy_selected(self, table):
        names = self.selected_usernames(table)
        if names:
            QApplication.clipboard().setText("\n".join("@" + name for name in names))

    def toggle_selected(self, table):
        names = self.selected_usernames(table)
        if not names:
            return
        all_rows = {x["username"]:x for x in self.db.list_usernames("all", 100000)}
        for name in names:
            item = all_rows.get(name)
            if item:
                self.db.toggle_saved(name, not bool(item["is_saved"]))
        self.refresh_all()

    def recheck_selected(self, table):
        self._start_recheck(self.selected_usernames(table))

    def recheck_saved(self):
        self._start_recheck([x["username"] for x in self.db.list_usernames("saved", 100000)])

    def _start_recheck(self, names):
        if not names:
            self.status.setText("No usernames selected.")
            return
        if self.worker and self.worker.isRunning():
            return
        self.worker = RecheckWorker(self.db, names, self.rpm.value(), self.api_url.text().strip())
        self.worker.message.connect(self.status.setText)
        self.worker.candidate_checked.connect(self.on_checked)
        self.worker.finished_summary.connect(self.on_finished)
        self.start.setEnabled(False)
        self.stop.setEnabled(True)
        self.worker.start()

    def export_view(self, view):
        path, _ = QFileDialog.getSaveFileName(self, "Export usernames", f"tonsсope_{view}.csv", "CSV (*.csv);;JSON (*.json);;Text (*.txt)")
        if not path:
            return
        suffix = Path(path).suffix.lower()
        fmt = "json" if suffix == ".json" else "txt" if suffix == ".txt" else "csv"
        count = self.db.export(path, fmt, view)
        QMessageBox.information(self, "Export complete", f"Exported {count} records.")

    def refresh_rates(self):
        if self.rates_worker and self.rates_worker.isRunning():
            return
        self.rates_worker = RatesWorker()
        self.rates_worker.updated.connect(self.on_rates)
        self.rates_worker.start()

    def on_rates(self, ton_usd, usd_rub):
        self.ton_usd, self.usd_rub = ton_usd, usd_rub
        self.refresh_all()
        if hasattr(self, "settings_info"):
            self.settings_info.setText(f"TON/USD: {ton_usd if ton_usd else 'unavailable'} · USD/RUB: {usd_rub if usd_rub else 'unavailable'}\nPublic Telegram + Fragment resolver. No login required. Up to 15 usernames per bulk request.")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(15000)
        event.accept()


def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()

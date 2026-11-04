from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QSpinBox, QStackedWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView,
)

from tonscope import __version__
from tonscope.core.scanner import CandidateWorker
from tonscope.storage.database import Database

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "user_data" / "profiles" / "default" / "tonscope.db"

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
        self.db = Database(DB_PATH)
        self.worker: CandidateWorker | None = None
        self.setWindowTitle(f"TONSCOPE · Username Research · v{__version__}")
        self.resize(1180, 760)
        self.setMinimumSize(920, 620)
        self._build()
        self.refresh_all()

    def _build(self) -> None:
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(16)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(205)
        side = QVBoxLayout(sidebar)
        brand = QLabel("TONSCOPE")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        caption = QLabel("USERNAME INTELLIGENCE")
        caption.setObjectName("Muted")
        side.addWidget(caption)
        side.addSpacing(24)

        self.pages = QStackedWidget()
        self.nav = []
        for label, index in (("Overview", 0), ("All candidates", 1), ("Saved", 2), ("Settings", 3)):
            button = QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.pages.setCurrentIndex(i))
            side.addWidget(button)
            self.nav.append(button)
        self.nav[0].setChecked(True)
        side.addStretch()
        profile = QLabel("PROFILE\nDefault")
        profile.setObjectName("Muted")
        side.addWidget(profile)

        self.pages.addWidget(self._dashboard())
        self.pages.addWidget(self._list_page("all"))
        self.pages.addWidget(self._list_page("saved"))
        self.pages.addWidget(self._settings())
        self.pages.currentChanged.connect(self._page_changed)
        outer.addWidget(sidebar)
        outer.addWidget(self.pages, 1)
        self.setCentralWidget(root)

    def _page_changed(self, index: int) -> None:
        for i, button in enumerate(self.nav):
            button.setChecked(i == index)
        if index in (1, 2):
            self.refresh_table(index)

    def _table(self) -> QTableWidget:
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Username", "Status", "Length", "Readability", "Brand", "Score"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        return table

    def _dashboard(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel("Dashboard")
        heading.setStyleSheet("font-size:22pt;font-weight:700")
        layout.addWidget(heading)
        subtitle = QLabel("Generate and organize clean lowercase username candidates.")
        subtitle.setObjectName("Muted")
        layout.addWidget(subtitle)

        metrics = QHBoxLayout()
        self.metric_total = MetricCard("IN DATABASE")
        self.metric_available = MetricCard("CONFIRMED AVAILABLE")
        self.metric_saved = MetricCard("SAVED")
        self.metric_candidates = MetricCard("NOT CHECKED")
        for card in (self.metric_total, self.metric_available, self.metric_saved, self.metric_candidates):
            metrics.addWidget(card)
        layout.addLayout(metrics)

        panel = QFrame()
        panel.setObjectName("Panel")
        controls = QVBoxLayout(panel)
        title = QLabel("Candidate generator")
        title.setStyleSheet("font-size:14pt;font-weight:650")
        controls.addWidget(title)
        row = QHBoxLayout()
        self.length = QComboBox()
        self.length.addItems(["5 letters", "6 letters", "7 letters"])
        self.length.setCurrentIndex(1)
        self.mode = QComboBox()
        self.mode.addItem("Readable", "readable")
        self.mode.addItem("Word-like", "words")
        self.mode.addItem("Brandable", "brand")
        self.mode.addItem("Random", "random")
        self.target = QSpinBox()
        self.target.setRange(0, 1_000_000)
        self.target.setValue(100)
        self.target.setSpecialValueText("Until stopped")
        for label, widget in (("Length", self.length), ("Style", self.mode), ("New candidates", self.target)):
            row.addWidget(QLabel(label))
            row.addWidget(widget, 1)
        controls.addLayout(row)

        actions = QHBoxLayout()
        self.start = QPushButton("Start generation")
        self.start.setObjectName("Primary")
        self.start.clicked.connect(self.start_scan)
        self.stop = QPushButton("STOP")
        self.stop.setObjectName("Danger")
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self.stop_scan)
        actions.addWidget(self.start)
        actions.addWidget(self.stop)
        controls.addLayout(actions)
        self.status = QLabel("Ready. New candidates are saved automatically.")
        self.status.setObjectName("Muted")
        controls.addWidget(self.status)
        layout.addWidget(panel)

        layout.addWidget(QLabel("Recent candidates"))
        self.recent = self._table()
        layout.addWidget(self.recent, 1)
        return page

    def _list_page(self, view: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel("All candidates" if view == "all" else "Saved usernames")
        heading.setStyleSheet("font-size:22pt;font-weight:700")
        layout.addWidget(heading)
        search = QLineEdit()
        search.setPlaceholderText("Filter usernames…")
        search.textChanged.connect(lambda value, v=view: self.refresh_table(2 if v == "saved" else 1, value))
        layout.addWidget(search)
        table = self._table()
        setattr(self, "saved_table" if view == "saved" else "all_table", table)
        layout.addWidget(table, 1)
        actions = QHBoxLayout()
        copy = QPushButton("Copy selected")
        copy.clicked.connect(lambda checked=False, t=table: self.copy_selected(t))
        save = QPushButton("Save / unsave")
        save.clicked.connect(lambda checked=False, t=table: self.toggle_selected(t))
        actions.addWidget(copy)
        actions.addWidget(save)
        layout.addLayout(actions)
        return page

    def _settings(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel("Settings")
        heading.setStyleSheet("font-size:22pt;font-weight:700")
        layout.addWidget(heading)
        info = QLabel(
            "Active profile: Default\n"
            "Local database: user_data/profiles/default/tonscope.db\n\n"
            "This foundation generates and scores candidates only. Telegram availability "
            "and Fragment market checks are not connected yet. Candidates are never marked "
            "as free without a live confirmation."
        )
        info.setObjectName("Muted")
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()
        return page

    def start_scan(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.worker = CandidateWorker(
            self.db, self.length.currentIndex() + 5, self.mode.currentData(), self.target.value()
        )
        self.worker.message.connect(self.status.setText)
        self.worker.candidate_created.connect(self.on_candidate)
        self.worker.progress.connect(lambda n: self.status.setText(f"Processed: {n}"))
        self.worker.finished_count.connect(self.on_finished)
        self.start.setEnabled(False)
        self.stop.setEnabled(True)
        self.worker.start()

    def stop_scan(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.status.setText("Stopping… current progress is already saved.")

    def on_candidate(self, username: str, scores: dict) -> None:
        self.add_row(self.recent, {
            "username": username, "status": "Candidate",
            "readability": scores["readability"], "brandability": scores["brandability"],
            "overall": scores["overall"],
        })
        self.refresh_stats()

    def on_finished(self, count: int) -> None:
        self.start.setEnabled(True)
        self.stop.setEnabled(False)
        self.refresh_all()

    def refresh_stats(self) -> None:
        stats = self.db.stats()
        self.metric_total.set_value(stats["total"])
        self.metric_available.set_value(stats["available"])
        self.metric_saved.set_value(stats["saved"])
        self.metric_candidates.set_value(stats["candidates"])

    def add_row(self, table: QTableWidget, item: dict) -> None:
        row = table.rowCount()
        table.insertRow(row)
        values = [
            "@" + item["username"], item.get("status", "Candidate"), len(item["username"]),
            item.get("readability", 0), item.get("brandability", 0), item.get("overall", 0),
        ]
        for col, value in enumerate(values):
            table.setItem(row, col, QTableWidgetItem(str(value)))

    def refresh_table(self, index: int, query: str = "") -> None:
        view = "saved" if index == 2 else "all"
        table = self.saved_table if view == "saved" else self.all_table
        table.setRowCount(0)
        for item in self.db.list_usernames(view):
            if query and query.lower().strip("@") not in item["username"].lower():
                continue
            self.add_row(table, item)

    def refresh_all(self) -> None:
        self.refresh_stats()
        if hasattr(self, "all_table"):
            self.refresh_table(1)
            self.refresh_table(2)
        if hasattr(self, "recent"):
            self.recent.setRowCount(0)
            for item in self.db.list_usernames("all", 12):
                self.add_row(self.recent, item)

    def selected_username(self, table: QTableWidget) -> str | None:
        selected = table.selectionModel().selectedRows()
        if not selected:
            return None
        return table.item(selected[0].row(), 0).text().lstrip("@")

    def copy_selected(self, table: QTableWidget) -> None:
        username = self.selected_username(table)
        if username:
            QApplication.clipboard().setText("@" + username)

    def toggle_selected(self, table: QTableWidget) -> None:
        username = self.selected_username(table)
        if not username:
            return
        item = next((x for x in self.db.list_usernames("all", 10000) if x["username"] == username), None)
        if item:
            self.db.toggle_saved(username, not bool(item["is_saved"]))
            self.refresh_all()

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(4000)
        event.accept()


def run() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()

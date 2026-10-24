# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio v5.0 — Professional Desktop GUI (PyQt6)
Giao diện desktop chuyên nghiệp với dark theme, Fast/Pro mode toggle,
đa luồng trực quan, video gallery grid preview, bảng điều khiển anti-ban,
Auto Login VIA FB → Dola, Cookie Persistence, Job Tracker v5.0.
"""

import os
import asyncio
import re
import sys
import json
import time
import threading
import subprocess
from typing import Optional

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Module path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QStackedWidget, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QTextEdit, QPlainTextEdit, QLineEdit,
    QComboBox, QSpinBox, QCheckBox, QRadioButton, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QScrollArea, QFrame, QSplitter, QFileDialog, QMessageBox,
    QStatusBar, QSizePolicy, QButtonGroup, QAbstractItemView, QDialog,
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, pyqtSlot, QSize, QThread, QObject, QEvent,
)
from PyQt6.QtGui import QFont, QPixmap, QIcon, QColor

from config import (
    APP_NAME, APP_VERSION, API_HOST, API_PORT,
    CHROME_PATH, CHROME_USER_DATA_BASE, EXTENSION_DIR,
    CHROME_FLAGS, DOLA_URL, OUTPUT_DIR, DATA_DIR,
    ASPECT_RATIOS, ASPECT_RATIO_LABELS, SEEDANCE_MODELS, SEEDANCE_MODEL_MAP,
    FAST_DURATIONS, FAST_DURATION_MAP, PRO_MAX_VIDEOS,
)
from account_manager import AccountManager, Account, parse_via_cookie_string, parse_bulk_via_text
from proxy_manager import ProxyManager, import_from_ocproxy_hub, parse_proxy_spec, find_ocproxy_db_path
from job_manager import JobManager
from session_store import SessionStore, parse_bulk_dola_cookies
from worker_pool import WorkerPool, VideoJob
from job_tracker import JobTracker, TrackedJob, generate_video_filename
from fb_login_automation import FBLoginAutomation, parse_via_fields

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

NAV_ITEMS = [
    ("📊", "Dashboard"),
    ("🎥", "Tạo Video"),
    ("📁", "Video Gallery"),
    ("👤", "Tài Khoản"),
    ("🌐", "Proxy & Anti-Ban"),
    ("⚙️", "Cài Đặt"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER WIDGETS
# ═══════════════════════════════════════════════════════════════════════════════

class StatCard(QFrame):
    """Card hiển thị 1 con số thống kê trên Dashboard."""
    def __init__(self, value: str = "0", label: str = "Label", color: str = "#00d4ff"):
        super().__init__()
        self.setObjectName("stat_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("stat_value")
        self.value_label.setStyleSheet(f"color: {color};")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.value_label)

        self.text_label = QLabel(label)
        self.text_label.setObjectName("stat_label")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.text_label)

    def set_value(self, val: str):
        self.value_label.setText(val)


class WorkerStatusRow(QFrame):
    """1 hàng hiển thị trạng thái worker trên Dashboard."""
    def __init__(self, worker_id: int):
        super().__init__()
        self.worker_id = worker_id
        self.setObjectName("worker_card")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)

        self.id_label = QLabel(f"W{worker_id}")
        self.id_label.setObjectName("worker_id_label")
        self.id_label.setFixedWidth(30)
        layout.addWidget(self.id_label)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(14)
        self.progress.setTextVisible(True)
        self.progress.setValue(0)
        self.progress.setFixedWidth(180)
        layout.addWidget(self.progress)

        self.account_label = QLabel("[idle]")
        self.account_label.setObjectName("label_dim")
        self.account_label.setFixedWidth(120)
        layout.addWidget(self.account_label)

        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setObjectName("worker_status_idle")
        layout.addWidget(self.status_label, 1)

        self.time_label = QLabel("")
        self.time_label.setObjectName("label_dim")
        self.time_label.setFixedWidth(60)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.time_label)

    def update_status(self, account: str = "", status: str = "Sẵn sàng",
                      progress: int = 0, elapsed: str = "", active: bool = False):
        self.account_label.setText(account or "[idle]")
        self.status_label.setText(status)
        self.progress.setValue(progress)
        self.time_label.setText(elapsed)
        if active:
            self.setObjectName("worker_card_active")
            self.status_label.setObjectName("worker_status_running")
        else:
            self.setObjectName("worker_card")
            self.status_label.setObjectName("worker_status_idle")
        self.style().unpolish(self)
        self.style().polish(self)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)


class VideoCard(QFrame):
    """Card hiển thị 1 video trong Gallery grid."""
    sig_play = pyqtSignal(str)
    sig_delete = pyqtSignal(str)

    def __init__(self, video_path: str, thumb_path: Optional[str] = None):
        super().__init__()
        self.video_path = video_path
        self.setObjectName("gallery_card")
        self.setFixedSize(260, 280)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Thumbnail
        self.thumb = QLabel()
        self.thumb.setObjectName("gallery_thumb")
        self.thumb.setFixedSize(260, 146)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setScaledContents(False)

        if thumb_path and os.path.isfile(thumb_path):
            pixmap = QPixmap(thumb_path).scaled(
                260, 146, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.thumb.setPixmap(pixmap)
        else:
            self.thumb.setText("🎥")
            self.thumb.setStyleSheet("font-size: 40px; background: #0a0a1a; border-radius: 10px 10px 0 0;")

        layout.addWidget(self.thumb)

        # Info section
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(10, 6, 10, 6)
        info_layout.setSpacing(2)

        fname = os.path.basename(video_path)
        self.title_label = QLabel(fname[:35] + ("…" if len(fname) > 35 else ""))
        self.title_label.setObjectName("gallery_title")
        self.title_label.setWordWrap(True)
        info_layout.addWidget(self.title_label)

        # Get video info
        size_mb = os.path.getsize(video_path) / (1024 * 1024) if os.path.isfile(video_path) else 0
        mtime = time.strftime("%d/%m %H:%M", time.localtime(os.path.getmtime(video_path))) if os.path.isfile(video_path) else ""
        self.meta_label = QLabel(f"{size_mb:.1f} MB  •  {mtime}")
        self.meta_label.setObjectName("gallery_meta")
        info_layout.addWidget(self.meta_label)

        layout.addWidget(info_widget)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(6, 0, 6, 6)
        btn_layout.setSpacing(4)

        btn_play = QPushButton("▶ Xem")
        btn_play.setFixedHeight(26)
        btn_play.clicked.connect(lambda: os.startfile(video_path))
        btn_layout.addWidget(btn_play)

        btn_folder = QPushButton("📂")
        btn_folder.setFixedHeight(26)
        btn_folder.setFixedWidth(32)
        btn_folder.setToolTip("Mở thư mục chứa")
        btn_folder.clicked.connect(lambda: subprocess.Popen(f'explorer /select,"{video_path}"'))
        btn_layout.addWidget(btn_folder)

        btn_del = QPushButton("🗑")
        btn_del.setObjectName("btn_danger")
        btn_del.setFixedHeight(26)
        btn_del.setFixedWidth(32)
        btn_del.setToolTip("Xóa video")
        btn_del.clicked.connect(lambda: self.sig_delete.emit(video_path))
        btn_layout.addWidget(btn_del)

        layout.addLayout(btn_layout)


class ConsoleLog(QPlainTextEdit):
    """Console log widget với font monospace và auto-scroll."""
    def __init__(self):
        super().__init__()
        self.setObjectName("console_log")
        self.setReadOnly(True)
        self.setMaximumBlockCount(500)
        self.setFont(QFont("Consolas", 10))

    def append_log(self, msg: str):
        timestamp = time.strftime("%H:%M:%S")
        self.appendPlainText(f"[{timestamp}] {msg}")


# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 1: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(14)

        # Title
        title = QLabel("Dashboard")
        title.setObjectName("panel_title")
        layout.addWidget(title)
        subtitle = QLabel("Tổng quan hoạt động hệ thống & tiến trình tạo video thời gian thực")
        subtitle.setObjectName("panel_subtitle")
        layout.addWidget(subtitle)

        # VIP Author Banner
        author_banner = QFrame()
        author_banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(245, 158, 11, 0.15), stop:1 rgba(37, 99, 235, 0.15));
                border: 1px solid rgba(251, 191, 36, 0.35);
                border-radius: 8px;
                padding: 4px 10px;
            }
        """)
        ab_row = QHBoxLayout(author_banner)
        ab_row.setContentsMargins(6, 4, 6, 4)
        lbl_info = QLabel("✨ <b>DOLA 30S STUDIO PRO</b> — Bản quyền & Phát triển: <b>LÊ VIỆT TÙNG</b> | Hotline / Zalo: <span style='color:#38bdf8; font-weight:bold;'>0915967790</span> | Facebook: <span style='color:#a78bfa;'>Lê Việt Tùng</span>")
        lbl_info.setStyleSheet("color: #f8fafc; font-size: 11.5px;")
        ab_row.addWidget(lbl_info)
        layout.addWidget(author_banner)

        # Stats Row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        self.card_accounts = StatCard("0", "TÀI KHOẢN", "#00d4ff")
        self.card_workers = StatCard("0/5", "WORKERS ĐANG CHẠY", "#4ade80")
        self.card_videos = StatCard("0", "VIDEO TRÊN ĐĨA", "#fbbf24")
        self.card_queue = StatCard("0", "ĐANG CHỜ / CHẠY", "#fb923c")
        self.card_success = StatCard("0", "ĐÃ HOÀN THÀNH", "#a78bfa")
        stats_layout.addWidget(self.card_accounts)
        stats_layout.addWidget(self.card_workers)
        stats_layout.addWidget(self.card_videos)
        stats_layout.addWidget(self.card_queue)
        stats_layout.addWidget(self.card_success)
        layout.addLayout(stats_layout)

        # Splitter: Left is Workers & Console, Right is Live Queue Table
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Column (Workers & Console)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # Worker Status Grid
        worker_group = QGroupBox("Trạng Thái Workers (Live)")
        worker_layout = QVBoxLayout(worker_group)
        worker_layout.setSpacing(4)

        self.worker_rows: list[WorkerStatusRow] = []
        for i in range(5):
            row = WorkerStatusRow(i)
            self.worker_rows.append(row)
            worker_layout.addWidget(row)

        left_layout.addWidget(worker_group)

        # Console Log
        log_group = QGroupBox("Console Log")
        log_layout = QVBoxLayout(log_group)
        self.console = ConsoleLog()
        self.console.setMinimumHeight(160)
        log_layout.addWidget(self.console)
        left_layout.addWidget(log_group)

        splitter.addWidget(left_widget)

        # Right Column (Live Jobs List Table)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        jobs_group = QGroupBox("📋 Danh Sách Video Đang Tạo & Hàng Đợi (Live Tracking)")
        jobs_layout = QVBoxLayout(jobs_group)
        jobs_layout.setSpacing(8)

        self.jobs_table = QTableWidget()
        self.jobs_table.setColumnCount(6)
        self.jobs_table.setHorizontalHeaderLabels([
            "#", "Prompt", "Tài Khoản", "Trạng Thái", "Thời Gian", "Kết Quả"
        ])
        self.jobs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.jobs_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.jobs_table.verticalHeader().setVisible(False)
        self.jobs_table.setAlternatingRowColors(True)
        jobs_layout.addWidget(self.jobs_table)

        right_layout.addWidget(jobs_group)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        layout.addWidget(splitter, 1)

    def set_num_workers(self, n: int):
        """Cập nhật số lượng worker hiển thị."""
        for i, row in enumerate(self.worker_rows):
            row.setVisible(i < n)
        while len(self.worker_rows) < n:
            row = WorkerStatusRow(len(self.worker_rows))
            self.worker_rows.append(row)
            group = self.findChild(QGroupBox, "Trạng Thái Workers (Live)")
            if group:
                group.layout().addWidget(row)

    def refresh_stats(self):
        """Cập nhật tất cả stat cards."""
        if not self.main_win:
            return
        accs = self.main_win.account_manager.get_all()
        self.card_accounts.set_value(str(len(accs)))
        if os.path.isdir(OUTPUT_DIR):
            vcount = len([f for f in os.listdir(OUTPUT_DIR)
                         if f.lower().endswith((".mp4", ".webm", ".mkv"))])
            self.card_videos.set_value(str(vcount))

    def update_dashboard_live(self, status: dict):
        """Cập nhật giao diện Dashboard realtime từ trạng thái WorkerPool."""
        running_workers = status.get("active_jobs", 0)
        max_w = status.get("max_workers", 5)
        self.card_workers.set_value(f"{running_workers}/{max_w}")
        self.card_queue.set_value(str(status.get("queue_size", 0) + running_workers))
        self.card_success.set_value(str(status.get("completed_jobs", 0)))

        # 1. Cập nhật từng worker row
        active_dict = status.get("jobs", {})
        for wid, row in enumerate(self.worker_rows):
            # Tìm xem worker này có đang chạy job nào không
            active_info = None
            for jid, jinfo in active_dict.items():
                if jinfo.get("worker") == wid:
                    active_info = jinfo
                    break

            if active_info:
                acc = active_info.get("account", "")
                step = active_info.get("current_step") or active_info.get("status_display", "Đang tạo video...")
                el_str = active_info.get("elapsed_str", "00:00")
                row.update_status(account=acc, status=step, progress=60, elapsed=el_str, active=True)
            else:
                row.update_status(account="[idle]", status="Sẵn sàng", progress=0, elapsed="", active=False)

        # 2. Cập nhật bảng jobs_table
        all_jobs = status.get("all_jobs", [])
        if all_jobs:
            self.jobs_table.setRowCount(len(all_jobs))
            for i, job in enumerate(all_jobs):
                # Col 0: Index
                item_idx = QTableWidgetItem(f"#{i+1:02d}")
                item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.jobs_table.setItem(i, 0, item_idx)

                # Col 1: Prompt
                prompt_txt = job.get("prompt", "")
                short_prompt = prompt_txt[:40] + "..." if len(prompt_txt) > 40 else prompt_txt
                item_prompt = QTableWidgetItem(short_prompt)
                item_prompt.setToolTip(prompt_txt)
                self.jobs_table.setItem(i, 1, item_prompt)

                # Col 2: Account
                item_acc = QTableWidgetItem(job.get("account", ""))
                self.jobs_table.setItem(i, 2, item_acc)

                # Col 3: Status & Step
                st = job.get("status", "queued")
                step_txt = job.get("status_display", "")
                item_status = QTableWidgetItem(step_txt)
                if st == "completed":
                    item_status.setForeground(QColor("#4ade80"))
                elif st in ["running", "downloading", "upscaling"]:
                    item_status.setForeground(QColor("#38bdf8"))
                elif st == "failed":
                    item_status.setForeground(QColor("#f87171"))
                else:
                    item_status.setForeground(QColor("#fbbf24"))
                self.jobs_table.setItem(i, 3, item_status)

                # Col 4: Elapsed Time
                item_time = QTableWidgetItem(job.get("elapsed_str", "00:00"))
                item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.jobs_table.setItem(i, 4, item_time)

                # Col 5: Result / Open
                out_path = job.get("output_path", "")
                if st == "completed" and out_path and os.path.exists(out_path):
                    btn_view = QPushButton("▶ Xem Video")
                    btn_view.setFixedHeight(24)
                    btn_view.clicked.connect(lambda _, p=out_path: os.startfile(p) if os.path.exists(p) else None)
                    self.jobs_table.setCellWidget(i, 5, btn_view)
                elif st == "failed":
                    err_item = QTableWidgetItem("❌ Lỗi")
                    err_item.setForeground(QColor("#f87171"))
                    err_item.setToolTip(job.get("error", ""))
                    self.jobs_table.setItem(i, 5, err_item)
                else:
                    self.jobs_table.setItem(i, 5, QTableWidgetItem("⏳ Đang xử lý..."))


# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 2: TẠO VIDEO
# ═══════════════════════════════════════════════════════════════════════════════

class CreateVideoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        self._ref_image_path = ""  # Ảnh tham chiếu (Fast mode)
        self._pro_ref_image_path = ""  # Ảnh tham chiếu (Pro mode)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        # Title
        title = QLabel("Tạo Video")
        title.setObjectName("panel_title")
        layout.addWidget(title)
        subtitle = QLabel("Tạo video đơn hoặc hàng loạt. Credit và model khả dụng theo thông báo của Dola.")
        subtitle.setObjectName("panel_subtitle")
        layout.addWidget(subtitle)

        # ─── Mode Toggle: Fast / Pro ─────────────────────────────────────
        mode_frame = QFrame()
        mode_frame.setObjectName("mode_toggle_frame")
        mode_frame.setStyleSheet("""
            #mode_toggle_frame {
                background: #1a1f2e;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(4, 4, 4, 4)
        mode_layout.setSpacing(4)

        self.btn_fast = QPushButton("⚡ Fast Mode")
        self.btn_fast.setCheckable(True)
        self.btn_fast.setChecked(True)
        self.btn_fast.setFixedHeight(36)
        self.btn_fast.setStyleSheet("""
            QPushButton { background: #2563eb; color: white; border-radius: 6px; font-weight: bold; font-size: 13px; padding: 0 20px; }
            QPushButton:!checked { background: transparent; color: #94a3b8; }
            QPushButton:hover:!checked { background: #1e293b; color: #cbd5e1; }
        """)
        mode_layout.addWidget(self.btn_fast)

        self.btn_pro = QPushButton("🧠 Pro Mode")
        self.btn_pro.setCheckable(True)
        self.btn_pro.setFixedHeight(36)
        self.btn_pro.setStyleSheet("""
            QPushButton { background: #7c3aed; color: white; border-radius: 6px; font-weight: bold; font-size: 13px; padding: 0 20px; }
            QPushButton:!checked { background: transparent; color: #94a3b8; }
            QPushButton:hover:!checked { background: #1e293b; color: #cbd5e1; }
        """)
        mode_layout.addWidget(self.btn_pro)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.btn_fast, 0)
        self.mode_group.addButton(self.btn_pro, 1)
        self.mode_group.idToggled.connect(self._on_mode_changed)

        layout.addWidget(mode_frame)

        # ─── Stacked Widget: Fast / Pro ──────────────────────────────────
        self.stack = QStackedWidget()
        self.fast_widget = self._build_fast_widget()
        self.pro_widget = self._build_pro_widget()
        self.stack.addWidget(self.fast_widget)
        self.stack.addWidget(self.pro_widget)
        layout.addWidget(self.stack, 1)

    def _on_mode_changed(self, btn_id: int, checked: bool):
        if checked:
            self.stack.setCurrentIndex(btn_id)

    # ═══════════════════════════════════════════════════════════════════════
    # FAST MODE WIDGET
    # ═══════════════════════════════════════════════════════════════════════

    def _build_fast_widget(self) -> QWidget:
        w = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        # Info banner
        info_label = QLabel("Video 15s: tạo một clip, kiểm tra lỗi Dola và xác minh thời lượng file trước khi báo hoàn thành.")
        info_label.setStyleSheet("background: #1e3a5f; color: #93c5fd; padding: 8px 12px; border-radius: 6px; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Prompt mode toggle: Đơn / Multi
        prompt_mode_layout = QHBoxLayout()
        prompt_mode_layout.addWidget(QLabel("Chế độ prompt:"))
        self.fast_single_radio = QRadioButton("📝 Đơn prompt (1 video)")
        self.fast_single_radio.setChecked(True)
        self.fast_multi_radio = QRadioButton("📋 Multi prompt (nhiều video)")
        self.fast_prompt_group = QButtonGroup(self)
        self.fast_prompt_group.addButton(self.fast_single_radio, 0)
        self.fast_prompt_group.addButton(self.fast_multi_radio, 1)
        prompt_mode_layout.addWidget(self.fast_single_radio)
        prompt_mode_layout.addWidget(self.fast_multi_radio)
        prompt_mode_layout.addStretch()
        layout.addLayout(prompt_mode_layout)

        # Prompt
        prompt_group = QGroupBox("Prompt Mô Tả Video")
        prompt_layout = QVBoxLayout(prompt_group)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText(
            "📝 Đơn prompt: Nhập 1 prompt duy nhất.\n\n"
            "📋 Multi prompt: Mỗi prompt cách nhau 1 dòng trắng.\n\n"
            "Ví dụ Multi (2 prompts):\n"
            "Con mèo đang chơi với cuộn len\n"
            "trên sàn gỗ, ánh sáng chiều\n"
            "\n"
            "Cảnh hoàng hôn trên biển,\n"
            "sóng vỗ nhẹ vào bờ cát trắng\n"
        )
        self.prompt_edit.setMaximumHeight(150)
        prompt_layout.addWidget(self.prompt_edit)

        # Prompt count + buttons
        prompt_info_layout = QHBoxLayout()
        self.prompt_count_label = QLabel("0 prompt")
        self.prompt_count_label.setObjectName("label_accent")
        prompt_info_layout.addWidget(self.prompt_count_label)
        prompt_info_layout.addStretch()

        btn_load_prompts = QPushButton("📂 Tải từ file .txt")
        btn_load_prompts.clicked.connect(self._load_prompts_from_file)
        prompt_info_layout.addWidget(btn_load_prompts)

        btn_clear = QPushButton("🗑 Xóa tất cả")
        btn_clear.clicked.connect(lambda: self.prompt_edit.clear())
        prompt_info_layout.addWidget(btn_clear)

        prompt_layout.addLayout(prompt_info_layout)
        layout.addWidget(prompt_group)

        # ─── Ảnh Tham Chiếu (REFERENCE IMAGE) ─────────────────────────
        ref_group = QGroupBox("📷 ẢNH THAM CHIẾU (REFERENCE IMAGE)")
        ref_group.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 12px; color: #f59e0b;
                        border: 1px solid #374151; border-radius: 8px; padding-top: 18px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 4px 12px; }
        """)
        ref_inner = QHBoxLayout(ref_group)
        self.ref_image_label = QLabel("Chọn hoặc kéo thả ảnh bắt đầu / tham chiếu vào đây")
        self.ref_image_label.setStyleSheet("color: #64748b; font-size: 11px; padding: 8px;")
        ref_inner.addWidget(self.ref_image_label, 1)

        btn_ref = QPushButton("📎 Chọn Ảnh")
        btn_ref.setFixedHeight(30)
        btn_ref.clicked.connect(self._select_ref_image)
        ref_inner.addWidget(btn_ref)

        btn_ref_clear = QPushButton("✕")
        btn_ref_clear.setFixedSize(28, 28)
        btn_ref_clear.clicked.connect(self._clear_ref_image)
        ref_inner.addWidget(btn_ref_clear)

        layout.addWidget(ref_group)

        # ─── Video Parameters ─────────────────────────────────────────
        params_group = QGroupBox("Tham Số Video")
        params_layout = QVBoxLayout(params_group)
        params_layout.setSpacing(8)

        # Row 1: Model + Upscale + Repeat
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Model:"))
        self.model_cb = QComboBox()
        self.model_cb.addItems(SEEDANCE_MODELS)
        self.model_cb.setCurrentText("Seedance 2.0")
        self.model_cb.setToolTip("Với video 15s, đây là model ưu tiên. Pro có thể chọn model khả dụng và không cung cấp model ID thực tế.")
        row1.addWidget(self.model_cb)

        row1.addWidget(QLabel("Upscale:"))
        self.upscale_cb = QComboBox()
        self.upscale_cb.addItems(["4K (NVENC/CPU)", "2K", "Không upscale"])
        self.upscale_cb.setCurrentText("Không upscale")
        row1.addWidget(self.upscale_cb)

        row1.addWidget(QLabel("Video/prompt:"))
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(1, 1000)
        self.repeat_spin.setValue(1)
        self.repeat_spin.setToolTip("Tạo bao nhiêu video cho mỗi prompt")
        row1.addWidget(self.repeat_spin)
        params_layout.addLayout(row1)

        # Row 2: Aspect Ratio — Pill buttons
        ratio_row = QHBoxLayout()
        ratio_row.addWidget(QLabel("TỈ LỆ KHUNG HÌNH:"))
        ratio_row.addSpacing(10)

        self.ratio_btn_group = QButtonGroup(self)
        self._ratio_buttons = []
        ratio_pill_style = """
            QPushButton {{ background: {bg}; color: {fg}; border: 1px solid #374151;
                           border-radius: 4px; padding: 4px 14px; font-weight: bold; font-size: 12px; }}
            QPushButton:hover {{ background: #374151; color: white; }}
        """
        for idx, r in enumerate(ASPECT_RATIOS):
            btn = QPushButton(r)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            if r == "9:16":
                btn.setChecked(True)
                btn.setStyleSheet(ratio_pill_style.format(bg="#2563eb", fg="white"))
            else:
                btn.setStyleSheet(ratio_pill_style.format(bg="#1e293b", fg="#94a3b8"))
            self.ratio_btn_group.addButton(btn, idx)
            self._ratio_buttons.append(btn)
            ratio_row.addWidget(btn)

        self.ratio_btn_group.idToggled.connect(self._on_ratio_changed)
        ratio_row.addStretch()
        params_layout.addLayout(ratio_row)

        # Row 3: Duration — Pill buttons
        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("THỜI LƯỢNG:"))
        dur_row.addSpacing(10)

        self.duration_btn_group = QButtonGroup(self)
        self._duration_buttons = []
        dur_pill_style = """
            QPushButton {{ background: {bg}; color: {fg}; border: 1px solid #374151;
                           border-radius: 4px; padding: 4px 12px; font-weight: bold; font-size: 12px; }}
            QPushButton:hover {{ background: #374151; color: white; }}
        """
        for idx, d in enumerate(FAST_DURATIONS):
            btn = QPushButton(d)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            if d == "15s":
                btn.setChecked(True)
                btn.setStyleSheet(dur_pill_style.format(bg="#7c3aed", fg="white"))
            else:
                btn.setStyleSheet(dur_pill_style.format(bg="#1e293b", fg="#94a3b8"))
            self.duration_btn_group.addButton(btn, idx)
            self._duration_buttons.append(btn)
            dur_row.addWidget(btn)

        self.duration_btn_group.idToggled.connect(self._on_duration_changed)
        dur_row.addStretch()
        params_layout.addLayout(dur_row)

        # Auto download toggle
        auto_dl_row = QHBoxLayout()
        self.chk_auto_download = QCheckBox("Tự động tải Master 1080P gốc — Lưu trực tiếp video không logo vào Downloads")
        self.chk_auto_download.setChecked(True)
        auto_dl_row.addWidget(self.chk_auto_download)
        auto_dl_row.addStretch()
        params_layout.addLayout(auto_dl_row)

        layout.addWidget(params_group)

        self.prompt_edit.textChanged.connect(self._update_prompt_count)
        self.fast_prompt_group.idToggled.connect(lambda *_: self._update_prompt_count())

        # Multi-thread Config
        mt_group = QGroupBox("Cấu Hình Đa Luồng")
        mt_grid = QGridLayout(mt_group)
        mt_grid.setHorizontalSpacing(16)
        mt_grid.setVerticalSpacing(8)

        mt_grid.addWidget(QLabel("Số Workers:"), 0, 0)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 10)
        self.workers_spin.setValue(5)
        mt_grid.addWidget(self.workers_spin, 0, 1)

        mt_grid.addWidget(QLabel("Delay giữa Job:"), 0, 2)
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 120)
        self.delay_spin.setValue(3)
        self.delay_spin.setSuffix("s")
        mt_grid.addWidget(self.delay_spin, 0, 3)

        mt_grid.addWidget(QLabel("Max Retry:"), 0, 4)
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 5)
        self.retry_spin.setValue(2)
        mt_grid.addWidget(self.retry_spin, 0, 5)

        mt_grid.addWidget(QLabel("Timeout/Job:"), 1, 0)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(60, 1800)
        self.timeout_spin.setValue(600)
        self.timeout_spin.setSuffix("s")
        self.timeout_spin.setSingleStep(60)
        mt_grid.addWidget(self.timeout_spin, 1, 1)

        mt_grid.addWidget(QLabel("Proxy mode:"), 1, 2)
        self.proxy_mode_cb = QComboBox()
        self.proxy_mode_cb.addItems(["Sticky per-job", "Sticky per-account", "Rotate mỗi request", "Không dùng proxy"])
        mt_grid.addWidget(self.proxy_mode_cb, 1, 3)

        self.chk_auto_rotate = QCheckBox("Tự động xoay account khi hết quota")
        self.chk_auto_rotate.setChecked(True)
        mt_grid.addWidget(self.chk_auto_rotate, 2, 0, 1, 3)

        self.chk_close_chrome = QCheckBox("Đóng Chrome sau download (tiết kiệm RAM)")
        self.chk_close_chrome.setChecked(True)
        mt_grid.addWidget(self.chk_close_chrome, 2, 3, 1, 3)

        self.chk_upscale_after = QCheckBox("Upscale 4K sau khi tải video")
        self.chk_upscale_after.setChecked(True)
        mt_grid.addWidget(self.chk_upscale_after, 3, 0, 1, 3)

        self.chk_show_chrome = QCheckBox("🌐 Hiện cửa sổ Chrome (để nhìn thấy tool thao tác trực tiếp)")
        self.chk_show_chrome.setChecked(True)
        self.chk_show_chrome.setToolTip("Chọn: Mở cửa sổ Chrome trên màn hình để bạn nhìn thấy tool thao tác trực tiếp.\nBỏ chọn: Chrome chạy ẩn ngầm (tiết kiệm màn hình và RAM).")
        mt_grid.addWidget(self.chk_show_chrome, 3, 3, 1, 3)

        layout.addWidget(mt_group)

        # Account Selector
        acc_group = QGroupBox("Chọn Tài Khoản Sử Dụng")
        acc_layout = QVBoxLayout(acc_group)

        self.acc_table = QTableWidget()
        self.acc_table.setColumnCount(4)
        self.acc_table.setHorizontalHeaderLabels(["✓", "Tài khoản", "Quota", "Session"])
        self.acc_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.acc_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.acc_table.setMaximumHeight(130)
        self.acc_table.verticalHeader().setVisible(False)
        acc_layout.addWidget(self.acc_table)

        acc_btn_layout = QHBoxLayout()
        self.chk_select_all = QCheckBox("Chọn tất cả có Session")
        self.chk_select_all.setChecked(True)
        acc_btn_layout.addWidget(self.chk_select_all)
        acc_btn_layout.addStretch()
        self.selected_count_label = QLabel("Đã chọn: 0 accounts")
        self.selected_count_label.setObjectName("label_dim")
        acc_btn_layout.addWidget(self.selected_count_label)
        acc_layout.addLayout(acc_btn_layout)
        layout.addWidget(acc_group)

        # Batch Summary
        summary_layout = QHBoxLayout()
        self.batch_summary_label = QLabel("")
        self.batch_summary_label.setObjectName("label_accent")
        summary_layout.addWidget(self.batch_summary_label)
        summary_layout.addStretch()
        layout.addLayout(summary_layout)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        self.btn_single = QPushButton("✨  TẠO VIDEO KHÔNG LOGO")
        self.btn_single.setObjectName("btn_primary")
        self.btn_single.setFixedHeight(46)
        self.btn_single.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #ef4444);
                          color: white; border-radius: 8px; font-weight: bold; font-size: 15px; padding: 0 30px; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #dc2626); }
            QPushButton:disabled { background: #374151; color: #64748b; }
        """)
        self.btn_single.clicked.connect(self.on_create_single)
        btn_layout.addWidget(self.btn_single)

        self.btn_batch = QPushButton("🚀  Chạy Hàng Loạt Đa Luồng")
        self.btn_batch.setObjectName("btn_primary")
        self.btn_batch.setFixedHeight(46)
        self.btn_batch.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb);
                          color: white; border-radius: 8px; font-weight: bold; font-size: 14px; padding: 0 24px; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6d28d9, stop:1 #1d4ed8); }
            QPushButton:disabled { background: #374151; color: #64748b; }
        """)
        self.btn_batch.clicked.connect(self.on_create_batch)
        btn_layout.addWidget(self.btn_batch)

        self.btn_stop = QPushButton("⏹  Dừng Tất Cả")
        self.btn_stop.setObjectName("btn_danger")
        self.btn_stop.setFixedHeight(46)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop_all)
        btn_layout.addWidget(self.btn_stop)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        # ─── Live Video Tracking Section (Fast Mode) ───
        tracking_group = QGroupBox("📡 Tiến Trình Tạo Video Realtime (Live Tracking)")
        tracking_layout = QVBoxLayout(tracking_group)
        tracking_layout.setSpacing(8)

        # Overview Stats Header
        summary_row = QHBoxLayout()
        self.fast_lbl_total = QLabel("📊 Tổng: <b>0</b> video")
        self.fast_lbl_running = QLabel("🚀 Đang tạo: <b>0</b>")
        self.fast_lbl_running.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.fast_lbl_queued = QLabel("⏳ Đang chờ: <b>0</b>")
        self.fast_lbl_queued.setStyleSheet("color: #fbbf24; font-weight: bold;")
        self.fast_lbl_completed = QLabel("✅ Đã xong: <b>0</b>")
        self.fast_lbl_completed.setStyleSheet("color: #4ade80; font-weight: bold;")
        self.fast_lbl_elapsed = QLabel("⏱ Thời gian chạy: <b>00:00</b>")
        self.fast_lbl_elapsed.setStyleSheet("color: #c084fc; font-weight: bold;")

        summary_row.addWidget(self.fast_lbl_total)
        summary_row.addWidget(self.fast_lbl_running)
        summary_row.addWidget(self.fast_lbl_queued)
        summary_row.addWidget(self.fast_lbl_completed)
        summary_row.addWidget(self.fast_lbl_elapsed)
        summary_row.addStretch()

        btn_open_folder = QPushButton("📂 Mở Thư Mục Video")
        btn_open_folder.setFixedHeight(28)
        btn_open_folder.clicked.connect(self._open_output_folder)
        summary_row.addWidget(btn_open_folder)
        tracking_layout.addLayout(summary_row)

        # Total Progress Bar
        self.fast_progress_bar = QProgressBar()
        self.fast_progress_bar.setFixedHeight(14)
        self.fast_progress_bar.setTextVisible(True)
        self.fast_progress_bar.setValue(0)
        tracking_layout.addWidget(self.fast_progress_bar)

        # Live Tracking Table
        self.fast_tracking_table = QTableWidget()
        self.fast_tracking_table.setColumnCount(7)
        self.fast_tracking_table.setHorizontalHeaderLabels([
            "#", "Prompt", "Tài Khoản", "Worker", "Trạng Thái & Bước Thực Hiện", "Thời Gian", "Kết Quả"
        ])
        self.fast_tracking_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.fast_tracking_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.fast_tracking_table.setMinimumHeight(240)
        self.fast_tracking_table.verticalHeader().setVisible(False)
        self.fast_tracking_table.setAlternatingRowColors(True)
        tracking_layout.addWidget(self.fast_tracking_table)

        layout.addWidget(tracking_group)

        layout.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return w

    # ═══════════════════════════════════════════════════════════════════════
    # PRO MODE WIDGET
    # ═══════════════════════════════════════════════════════════════════════

    def _build_pro_widget(self) -> QWidget:
        w = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        # Info banner
        info_label = QLabel("🧠 Pro Mode: Gửi tác vụ cho AI Agent. Credit và khả năng tạo video theo tài khoản Dola.")
        info_label.setStyleSheet("background: #2d1b69; color: #c4b5fd; padding: 8px 12px; border-radius: 6px; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Prompt mode toggle: Đơn / Multi
        pro_mode_layout = QHBoxLayout()
        pro_mode_layout.addWidget(QLabel("Chế độ prompt:"))
        self.pro_single_radio = QRadioButton("📝 Đơn prompt (1 video)")
        self.pro_multi_radio = QRadioButton("📋 Multi prompt (nhiều video)")
        self.pro_multi_radio.setChecked(True)  # Pro mặc định multi
        self.pro_prompt_mode_group = QButtonGroup(self)
        self.pro_prompt_mode_group.addButton(self.pro_single_radio, 0)
        self.pro_prompt_mode_group.addButton(self.pro_multi_radio, 1)
        pro_mode_layout.addWidget(self.pro_single_radio)
        pro_mode_layout.addWidget(self.pro_multi_radio)
        pro_mode_layout.addStretch()
        layout.addLayout(pro_mode_layout)

        # Prompt List
        prompt_group = QGroupBox("Danh Sách Prompt")
        prompt_layout = QVBoxLayout(prompt_group)
        self.pro_prompt_edit = QTextEdit()
        self.pro_prompt_edit.setPlaceholderText(
            "📝 Đơn: Nhập 1 prompt duy nhất cho AI Agent.\n\n"
            "📋 Multi: Mỗi prompt cách nhau 1 dòng trắng.\n\n"
            "Ví dụ Multi (3 prompts):\n"
            "A cute cat playing with yarn\n"
            "on a wooden floor, warm lighting\n"
            "\n"
            "Sunset over the ocean,\n"
            "waves crashing on sandy beach\n"
            "\n"
            "Golden retriever running\n"
            "through a green meadow\n"
        )
        self.pro_prompt_edit.setMaximumHeight(150)
        prompt_layout.addWidget(self.pro_prompt_edit)

        # Prompt count + load from file
        pro_info_layout = QHBoxLayout()
        self.pro_prompt_count = QLabel("0 prompt")
        self.pro_prompt_count.setObjectName("label_accent")
        pro_info_layout.addWidget(self.pro_prompt_count)
        pro_info_layout.addStretch()

        btn_pro_load = QPushButton("📂 Tải từ file .txt")
        btn_pro_load.clicked.connect(self._load_pro_prompts_from_file)
        pro_info_layout.addWidget(btn_pro_load)

        btn_pro_clear = QPushButton("🗑 Xóa")
        btn_pro_clear.clicked.connect(lambda: self.pro_prompt_edit.clear())
        pro_info_layout.addWidget(btn_pro_clear)

        prompt_layout.addLayout(pro_info_layout)
        layout.addWidget(prompt_group)

        self.pro_prompt_edit.textChanged.connect(self._update_pro_prompt_count)
        self.pro_prompt_mode_group.idToggled.connect(lambda *_: self._update_pro_prompt_count())

        # Skill / Template
        skill_group = QGroupBox("Hoặc: Skill / Template (để AI Agent tự tạo prompt)")
        skill_layout = QVBoxLayout(skill_group)

        self.skill_edit = QTextEdit()
        self.skill_edit.setPlaceholderText(
            "Nếu không có sẵn list prompt, nhập Skill instruction ở đây...\n\n"
            "Ví dụ:\n"
            "Tạo 50 video về động vật dễ thương, mỗi video có 1 con vật khác nhau,\n"
            "bối cảnh tự nhiên đẹp, chuyển động mượt mà."
        )
        self.skill_edit.setMaximumHeight(80)
        skill_layout.addWidget(self.skill_edit)
        layout.addWidget(skill_group)

        # Pro Parameters
        pro_params = QGroupBox("Tham Số Pro")
        pro_grid = QGridLayout(pro_params)
        pro_grid.setHorizontalSpacing(16)
        pro_grid.setVerticalSpacing(8)

        pro_grid.addWidget(QLabel("Số lượng video:"), 0, 0)
        self.pro_count_spin = QSpinBox()
        self.pro_count_spin.setRange(1, PRO_MAX_VIDEOS)
        self.pro_count_spin.setValue(1)
        self.pro_count_spin.setToolTip("Số video yêu cầu AI Agent tạo")
        pro_grid.addWidget(self.pro_count_spin, 0, 1)

        pro_grid.addWidget(QLabel("Định dạng:"), 0, 2)
        self.pro_ratio_cb = QComboBox()
        self.pro_ratio_cb.addItems([
            "Dọc 9:16",
            "Ngang 16:9",
            "Vuông 1:1",
        ])
        pro_grid.addWidget(self.pro_ratio_cb, 0, 3)

        pro_grid.addWidget(QLabel("Thời lượng:"), 1, 0)
        self.pro_duration_cb = QComboBox()
        self.pro_duration_cb.addItems(["30s · Skill Seedance 2.5", "15s · Pro native"])
        self.pro_duration_cb.setToolTip("30s: tự kiểm tra/cài SKILL.md và chọn skill trong chat Pro; xác minh thời lượng file.")
        pro_grid.addWidget(self.pro_duration_cb, 1, 1)

        # Ảnh tham chiếu Pro
        pro_grid.addWidget(QLabel("Ảnh tham chiếu:"), 1, 2)
        pro_ref_layout = QHBoxLayout()
        self.pro_ref_label = QLabel("Chưa chọn")
        self.pro_ref_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        pro_ref_layout.addWidget(self.pro_ref_label)
        btn_pro_ref = QPushButton("📎 Chọn ảnh")
        btn_pro_ref.setFixedHeight(28)
        btn_pro_ref.clicked.connect(self._select_pro_ref_image)
        pro_ref_layout.addWidget(btn_pro_ref)
        btn_pro_ref_clear = QPushButton("✕")
        btn_pro_ref_clear.setFixedSize(28, 28)
        btn_pro_ref_clear.clicked.connect(self._clear_pro_ref_image)
        pro_ref_layout.addWidget(btn_pro_ref_clear)
        pro_grid.addLayout(pro_ref_layout, 1, 3)

        # Tài khoản Pro: một account hoặc phân bổ theo checkbox bảng account
        pro_grid.addWidget(QLabel("Tài khoản:"), 2, 0)
        self.pro_account_cb = QComboBox()
        self.pro_account_cb.setToolTip("Dùng một tài khoản cho toàn bộ prompt; hoặc tích chọn nhiều tài khoản bên bảng account và bật phân bổ bên dưới.")
        pro_grid.addWidget(self.pro_account_cb, 2, 1)

        self.chk_pro_show_chrome = QCheckBox("🌐 Hiện cửa sổ Chrome (bỏ chọn để chạy ẩn)")
        self.chk_pro_show_chrome.setChecked(True)
        self.chk_pro_show_chrome.setToolTip("Chọn: Mở cửa sổ Chrome trên màn hình để bạn xem AI Agent Dola tương tác.\nBỏ chọn: Chạy Chrome ẩn ngầm.")
        pro_grid.addWidget(self.chk_pro_show_chrome, 2, 2, 1, 2)

        self.chk_pro_multi_accounts = QCheckBox("Chia 2 prompt liên tiếp cho mỗi tài khoản đã tích ở bảng tài khoản")
        self.chk_pro_multi_accounts.setToolTip("Ví dụ 10 prompt và 5 tài khoản đã tích: mỗi tài khoản nhận 2 prompt. Chỉ chọn tài khoản có phiên đăng nhập.")
        pro_grid.addWidget(self.chk_pro_multi_accounts, 3, 0, 1, 4)

        layout.addWidget(pro_params)

        # Action button
        pro_btn_layout = QHBoxLayout()
        pro_btn_layout.setSpacing(12)
        pro_btn_layout.addStretch()

        self.btn_pro_start = QPushButton("🧠  Gửi Lệnh Pro")
        self.btn_pro_start.setFixedHeight(42)
        self.btn_pro_start.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #a855f7);
                color: white; border-radius: 8px; font-weight: bold; font-size: 14px; padding: 0 28px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6d28d9, stop:1 #9333ea); }
            QPushButton:disabled { background: #374151; color: #6b7280; }
        """)
        self.btn_pro_start.clicked.connect(self.on_pro_start)
        pro_btn_layout.addWidget(self.btn_pro_start)

        self.btn_pro_stop = QPushButton("⏹  Dừng")
        self.btn_pro_stop.setObjectName("btn_danger")
        self.btn_pro_stop.setFixedHeight(42)
        self.btn_pro_stop.setEnabled(False)
        self.btn_pro_stop.clicked.connect(self._on_pro_stop)
        pro_btn_layout.addWidget(self.btn_pro_stop)

        pro_btn_layout.addStretch()
        layout.addLayout(pro_btn_layout)

        # Video tracking panel
        tracking_group = QGroupBox("📡 Theo Dõi Video (Live)")
        tracking_layout = QVBoxLayout(tracking_group)

        self.pro_status_label = QLabel("Chưa bắt đầu")
        self.pro_status_label.setStyleSheet("color: #94a3b8; font-size: 12px; padding: 4px 0;")
        tracking_layout.addWidget(self.pro_status_label)

        self.pro_tracking_table = QTableWidget()
        self.pro_tracking_table.setColumnCount(4)
        self.pro_tracking_table.setHorizontalHeaderLabels(["#", "Trạng thái", "URL", "Thao tác"])
        self.pro_tracking_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.pro_tracking_table.setMaximumHeight(200)
        self.pro_tracking_table.verticalHeader().setVisible(False)
        tracking_layout.addWidget(self.pro_tracking_table)

        layout.addWidget(tracking_group)

        layout.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return w

    # ═══════════════════════════════════════════════════════════════════════
    # SHARED METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _load_prompts_from_file(self):
        fp, _ = QFileDialog.getOpenFileName(self, "Chọn file prompts", "", "Text files (*.txt);;All files (*.*)")
        if fp:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                self.prompt_edit.setPlainText(f.read())

    def _load_pro_prompts_from_file(self):
        fp, _ = QFileDialog.getOpenFileName(self, "Chọn file prompts", "", "Text files (*.txt);;All files (*.*)")
        if fp:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                self.pro_prompt_edit.setPlainText(f.read())

    def _parse_prompts(self, text: str, is_multi: bool) -> list[str]:
        """Phân tích text thành danh sách prompt.
        
        - Đơn: Toàn bộ text = 1 prompt duy nhất.
        - Multi: Mỗi prompt cách nhau bởi 1 dòng trắng.
        """
        text = text.strip()
        if not text:
            return []
        if not is_multi:
            # Đơn prompt: ghép tất cả thành 1
            return [' '.join(text.split())]
        # Multi: split bằng dòng trắng (2+ newline liên tiếp)
        import re
        blocks = re.split(r'\n\s*\n', text)
        prompts = []
        for block in blocks:
            cleaned = ' '.join(block.strip().split())
            if cleaned:
                prompts.append(cleaned)
        return prompts

    def _update_prompt_count(self):
        is_multi = self.fast_multi_radio.isChecked()
        prompts = self._parse_prompts(self.prompt_edit.toPlainText(), is_multi)
        count = len(prompts)
        repeat = self.repeat_spin.value()
        total = count * repeat
        mode_str = "multi" if is_multi else "đơn"
        self.prompt_count_label.setText(f"{count} prompt{'s' if count > 1 else ''} ({mode_str})")
        if is_multi and count > 0 and repeat > 1:
            self.batch_summary_label.setText(
                f"📊 Tổng cộng: {count} prompts × {repeat} lần = {total} video sẽ được tạo")
        elif is_multi and count > 1:
            self.batch_summary_label.setText(f"📊 Tổng cộng: {total} video sẽ được tạo")
        else:
            self.batch_summary_label.setText("")

    def _update_pro_prompt_count(self):
        is_multi = self.pro_multi_radio.isChecked()
        prompts = self._parse_prompts(self.pro_prompt_edit.toPlainText(), is_multi)
        count = len(prompts)
        mode_str = "multi" if is_multi else "đơn"
        self.pro_prompt_count.setText(f"{count} prompt{'s' if count > 1 else ''} ({mode_str})")
        if is_multi and prompts:
            self.pro_count_spin.setValue(count)

    def _select_ref_image(self):
        fp, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh tham chiếu", "",
            "Images (*.png *.jpg *.jpeg *.webp);;All files (*.*)")
        if fp:
            self._ref_image_path = fp
            self.ref_image_label.setText(fp.split("/")[-1].split("\\")[-1])
            self.ref_image_label.setStyleSheet("color: #4ade80; font-size: 11px;")

    def _clear_ref_image(self):
        self._ref_image_path = ""
        self.ref_image_label.setText("Chưa chọn")
        self.ref_image_label.setStyleSheet("color: #94a3b8; font-size: 11px;")

    def get_ref_image_path(self) -> str:
        """Lấy đường dẫn ảnh tham chiếu."""
        return self._ref_image_path if hasattr(self, '_ref_image_path') else ""

    def _select_pro_ref_image(self):
        fp, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh tham chiếu", "",
            "Images (*.png *.jpg *.jpeg *.webp);;All files (*.*)")
        if fp:
            self._pro_ref_image_path = fp
            self.pro_ref_label.setText(fp.split("/")[-1].split("\\")[-1])
            self.pro_ref_label.setStyleSheet("color: #4ade80; font-size: 11px;")

    def _clear_pro_ref_image(self):
        self._pro_ref_image_path = ""
        self.pro_ref_label.setText("Chưa chọn")
        self.pro_ref_label.setStyleSheet("color: #94a3b8; font-size: 11px;")

    def refresh_accounts(self):
        """Load danh sách account vào bảng chọn (cả Fast và Pro)."""
        if not self.main_win:
            return
        accounts = self.main_win.account_manager.get_all()

        # Fast mode table
        self.acc_table.setRowCount(len(accounts))
        for i, acc in enumerate(accounts):
            name = acc["name"]
            chk = QCheckBox()
            has_session = self.main_win.session_store.has_session(name)
            chk.setChecked(has_session)
            chk.setEnabled(has_session)
            self.acc_table.setCellWidget(i, 0, chk)
            self.acc_table.setItem(i, 1, QTableWidgetItem(name))

            used = acc.get("quota_used", 0)
            mx = acc.get("quota_max", 4)
            item_q = QTableWidgetItem(f"{used}/{mx}")
            if used >= mx:
                item_q.setForeground(QColor("#f87171"))
            else:
                item_q.setForeground(QColor("#4ade80"))
            self.acc_table.setItem(i, 2, item_q)

            if has_session:
                info = self.main_win.session_store.get_session_info(name)
                item_s = QTableWidgetItem(f"✅ {info.get('cookies_count', 0)} cookies")
                item_s.setForeground(QColor("#4ade80"))
            else:
                item_s = QTableWidgetItem("❌ Chưa lưu")
                item_s.setForeground(QColor("#f87171"))
            self.acc_table.setItem(i, 3, item_s)

        self._update_selected_count()

        # Pro mode account dropdown
        self.pro_account_cb.clear()
        for acc in accounts:
            name = acc["name"]
            has_session = self.main_win.session_store.has_session(name)
            if has_session:
                self.pro_account_cb.addItem(f"✅ {name}", name)
            else:
                self.pro_account_cb.addItem(f"❌ {name} (chưa login)", name)

    def _update_selected_count(self):
        count = 0
        for i in range(self.acc_table.rowCount()):
            chk = self.acc_table.cellWidget(i, 0)
            if chk and chk.isChecked():
                count += 1
        self.selected_count_label.setText(f"Đã chọn: {count} accounts")

    def get_ratio_value(self) -> str:
        checked_id = self.ratio_btn_group.checkedId()
        if 0 <= checked_id < len(ASPECT_RATIOS):
            return ASPECT_RATIOS[checked_id]
        return "9:16"

    def get_duration_value(self) -> int:
        checked_id = self.duration_btn_group.checkedId()
        if 0 <= checked_id < len(FAST_DURATIONS):
            return FAST_DURATION_MAP.get(FAST_DURATIONS[checked_id], 30)
        return 30

    def _on_ratio_changed(self, btn_id: int, checked: bool):
        """Update pill button styles when ratio changes."""
        style_active = """
            QPushButton { background: #2563eb; color: white; border: 1px solid #374151;
                           border-radius: 4px; padding: 4px 14px; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background: #1d4ed8; color: white; }
        """
        style_inactive = """
            QPushButton { background: #1e293b; color: #94a3b8; border: 1px solid #374151;
                           border-radius: 4px; padding: 4px 14px; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background: #374151; color: white; }
        """
        for i, btn in enumerate(self._ratio_buttons):
            btn.setStyleSheet(style_active if btn.isChecked() else style_inactive)

    def _on_duration_changed(self, btn_id: int, checked: bool):
        """Update pill button styles when duration changes."""
        style_active = """
            QPushButton { background: #7c3aed; color: white; border: 1px solid #374151;
                           border-radius: 4px; padding: 4px 12px; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background: #6d28d9; color: white; }
        """
        style_inactive = """
            QPushButton { background: #1e293b; color: #94a3b8; border: 1px solid #374151;
                           border-radius: 4px; padding: 4px 12px; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background: #374151; color: white; }
        """
        for i, btn in enumerate(self._duration_buttons):
            btn.setStyleSheet(style_active if btn.isChecked() else style_inactive)


    def get_model_value(self) -> str:
        text = self.model_cb.currentText()
        return SEEDANCE_MODEL_MAP.get(text, "2.5")

    def get_all_prompts(self) -> list[str]:
        """Lấy danh sách tất cả prompts.
        
        - Đơn: Trả về 1 prompt duy nhất.
        - Multi: Tách bằng dòng trắng, mỗi block = 1 prompt.
        """
        is_multi = self.fast_multi_radio.isChecked()
        prompts = self._parse_prompts(self.prompt_edit.toPlainText(), is_multi)
        repeat = self.repeat_spin.value()
        result = []
        for prompt in prompts:
            for _ in range(repeat):
                result.append(prompt)
        return result

    def get_upscale_value(self) -> str:
        text = self.upscale_cb.currentText()
        if "4K" in text: return "4K"
        if "2K" in text: return "2K"
        return "off"

    def get_pro_ratio(self) -> str:
        text = self.pro_ratio_cb.currentText()
        if "9:16" in text: return "9:16"
        if "16:9" in text: return "16:9"
        return "1:1"

    def get_pro_prompts(self) -> list[str]:
        """Lấy danh sách prompts Pro mode."""
        is_multi = self.pro_multi_radio.isChecked()
        return self._parse_prompts(self.pro_prompt_edit.toPlainText(), is_multi)

    def get_pro_skill(self) -> str:
        return self.skill_edit.toPlainText().strip()

    def get_pro_account(self) -> str:
        return self.pro_account_cb.currentData() or ""

    def get_pro_accounts(self) -> list[str]:
        if self.chk_pro_multi_accounts.isChecked():
            selected = self.main_win._get_selected_accounts(self) if self.main_win else []
            valid = [name for name in selected
                     if self.main_win.session_store.has_session(name)]
            return valid
        account = self.get_pro_account()
        if account and self.main_win and self.main_win.session_store.has_session(account):
            return [account]
        return []

    # ─── Fast Mode Actions ────────────────────────────────────────────────

    def on_create_single(self):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Thiếu prompt", "Vui lòng nhập prompt trước!")
            return
        if self.main_win:
            self.main_win.log("⚡ [Fast Mode] Đang tạo video đơn...")
            self.main_win.run_single_video(prompt, self)

    def on_create_batch(self):
        prompts = self.get_all_prompts()
        if not prompts:
            QMessageBox.warning(self, "Thiếu prompt", "Vui lòng nhập ít nhất 1 prompt!")
            return
        reply = QMessageBox.question(
            self, "Xác nhận chạy hàng loạt (Fast Mode)",
            f"⚡ Fast Mode: Sẽ tạo {len(prompts)} video với {self.workers_spin.value()} workers.\n\n"
            f"Model: {self.model_cb.currentText()}\n"
            f"Tỉ lệ: {self.get_ratio_value()}\n"
            f"Thời lượng: {self.get_duration_value()}s\n"
            f"Upscale: {self.upscale_cb.currentText()}\n\n"
            f"⚠️ Sẽ tốn credit. Bắt đầu?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.main_win:
                self.main_win.log(f"⚡ [Fast Mode] Khởi tạo: {len(prompts)} video, {self.workers_spin.value()} workers")
                self.main_win.run_batch_video(prompts, self)
                self.btn_batch.setEnabled(False)
                self.btn_stop.setEnabled(True)

    # ─── Pro Mode Actions ─────────────────────────────────────────────────

    def on_pro_start(self):
        prompts = self.get_pro_prompts()
        skill = self.get_pro_skill()
        accounts = self.get_pro_accounts()

        if not prompts and not skill:
            QMessageBox.warning(self, "Thiếu nội dung",
                "Vui lòng nhập danh sách prompt HOẶC Skill instruction!")
            return
        if not accounts:
            QMessageBox.warning(self, "Chưa chọn tài khoản",
                "Vui lòng chọn ít nhất một tài khoản đã login. Nếu chia nhiều tài khoản, hãy tích chọn chúng ở bảng tài khoản bên trái.")
            return

        count = len(prompts) if prompts else self.pro_count_spin.value()
        ratio = self.get_pro_ratio()

        reply = QMessageBox.question(
            self, "Xác nhận gửi lệnh Pro",
            f"🧠 Pro Mode: yêu cầu {count} video ({30 if self.pro_duration_cb.currentIndex() == 0 else 15}s, {ratio}).\n\n"
            f"Tài khoản: {', '.join(accounts)}\n"
            f"Phân bổ: 2 prompt/tài khoản theo thứ tự (nếu bật chia nhiều tài khoản)\n"
            f"Prompts: {len(prompts)} dòng\n"
            f"Skill: {'Có' if skill else 'Không'}\n\n"
            f"Credit theo thông báo của Dola. Chrome sẽ duy trì suốt quá trình. Bắt đầu?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.main_win:
                self.main_win.log(f"🧠 [Pro Mode] Gửi lệnh: {count} video, accounts={', '.join(accounts)}")
                self.btn_pro_start.setEnabled(False)
                self.btn_pro_stop.setEnabled(True)
                self.pro_status_label.setText("🧠 Đang gửi lệnh cho AI Agent...")
                self.pro_status_label.setStyleSheet("color: #a78bfa; font-size: 12px; padding: 4px 0;")
                self.main_win.run_pro_video(prompts, skill, count, ratio,
                    accounts, self._pro_ref_image_path, self)

    def add_pro_tracking_row(self, index: int, status: str, url: str):
        """Thêm 1 hàng vào bảng tracking Pro."""
        row = self.pro_tracking_table.rowCount()
        self.pro_tracking_table.setRowCount(row + 1)

        self.pro_tracking_table.setItem(row, 0, QTableWidgetItem(f"#{index:03d}"))

        status_item = QTableWidgetItem(status)
        if "✅" in status:
            status_item.setForeground(QColor("#4ade80"))
        elif "⏳" in status:
            status_item.setForeground(QColor("#fbbf24"))
        self.pro_tracking_table.setItem(row, 1, status_item)

        url_item = QTableWidgetItem(url[:60] + "..." if len(url) > 60 else url)
        url_item.setToolTip(url)
        self.pro_tracking_table.setItem(row, 2, url_item)

        btn_dl = QPushButton("📂 Mở" if os.path.isfile(url) else "📥 Tải")
        btn_dl.setFixedHeight(26)
        btn_dl.clicked.connect(lambda checked=False, target=url: os.startfile(target))
        self.pro_tracking_table.setCellWidget(row, 3, btn_dl)

    def update_pro_status(self, message: str):
        """Cập nhật trạng thái Pro mode."""
        self.pro_status_label.setText(message)

    def _on_stop_all(self):
        """Dừng tất cả workers trong Fast mode."""
        if self.main_win:
            self.main_win.stop_all_workers()
        self.btn_single.setEnabled(True)
        self.btn_batch.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _on_pro_stop(self):
        """Dừng Pro mode."""
        if self.main_win:
            self.main_win.log("⚠️ Đang yêu cầu dừng Pro mode...")
            runner = getattr(self.main_win, '_pro_skill_runner', None)
            if runner:
                runner.cancel()
            self.btn_pro_stop.setEnabled(False)
    def _open_output_folder(self):
        """Mở thư mục video trên Windows Explorer."""
        if os.path.isdir(OUTPUT_DIR):
            os.startfile(OUTPUT_DIR)
        else:
            QMessageBox.information(self, "Thông báo", f"Thư mục chưa tồn tại: {OUTPUT_DIR}")

    def update_fast_tracking(self, status: dict):
        """Cập nhật giao diện live tracking cho Fast mode."""
        total = status.get("total_jobs", 0)
        completed = status.get("completed_jobs", 0)
        failed = status.get("failed_jobs", 0)
        running = status.get("active_jobs", 0)
        queued = status.get("queue_size", 0)

        # Total elapsed time of the pool
        start_time = status.get("stats", {}).get("start_time", 0)
        if start_time > 0 and status.get("running"):
            total_el = max(0, int(time.time() - start_time))
            mins = total_el // 60
            secs = total_el % 60
            el_str = f"{mins:02d}:{secs:02d}"
        else:
            el_str = "00:00"

        self.fast_lbl_total.setText(f"📊 Tổng: <b>{total}</b> video")
        self.fast_lbl_running.setText(f"🚀 Đang tạo: <b>{running}</b>")
        self.fast_lbl_queued.setText(f"⏳ Đang chờ: <b>{queued}</b>")
        self.fast_lbl_completed.setText(f"✅ Đã xong: <b>{completed}</b>")
        self.fast_lbl_elapsed.setText(f"⏱ Thời gian chạy: <b>{el_str}</b>")

        # Progress bar
        if total > 0:
            pct = int((completed / total) * 100)
            self.fast_progress_bar.setValue(min(pct, 100))
        else:
            self.fast_progress_bar.setValue(0)

        # Table rows
        all_jobs = status.get("all_jobs", [])
        if all_jobs:
            self.fast_tracking_table.setRowCount(len(all_jobs))
            for i, job in enumerate(all_jobs):
                # 0. Index
                item_idx = QTableWidgetItem(f"#{i+1:02d}")
                item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.fast_tracking_table.setItem(i, 0, item_idx)

                # 1. Prompt
                prompt_txt = job.get("prompt", "")
                short_prompt = prompt_txt[:45] + "..." if len(prompt_txt) > 45 else prompt_txt
                item_prompt = QTableWidgetItem(short_prompt)
                item_prompt.setToolTip(prompt_txt)
                self.fast_tracking_table.setItem(i, 1, item_prompt)

                # 2. Account
                self.fast_tracking_table.setItem(i, 2, QTableWidgetItem(job.get("account", "")))

                # 3. Worker
                wid = job.get("worker", -1)
                w_str = f"Worker #{wid}" if wid >= 0 else "—"
                item_w = QTableWidgetItem(w_str)
                item_w.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.fast_tracking_table.setItem(i, 3, item_w)

                # 4. Status & Step
                st = job.get("status", "queued")
                step_txt = job.get("status_display", "")
                item_status = QTableWidgetItem(step_txt)
                if st == "completed":
                    item_status.setForeground(QColor("#4ade80"))
                elif st in ["running", "downloading", "upscaling"]:
                    item_status.setForeground(QColor("#38bdf8"))
                elif st == "failed":
                    item_status.setForeground(QColor("#f87171"))
                else:
                    item_status.setForeground(QColor("#fbbf24"))
                self.fast_tracking_table.setItem(i, 4, item_status)

                # 5. Elapsed
                item_time = QTableWidgetItem(job.get("elapsed_str", "00:00"))
                item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.fast_tracking_table.setItem(i, 5, item_time)

                # 6. Action / Result
                out_path = job.get("output_path", "")
                if st == "completed" and out_path and os.path.exists(out_path):
                    btn_view = QPushButton("▶ Xem Video")
                    btn_view.setFixedHeight(24)
                    btn_view.setStyleSheet("background: #059669; color: white; font-weight: bold;")
                    btn_view.clicked.connect(lambda _, p=out_path: os.startfile(p) if os.path.exists(p) else None)
                    self.fast_tracking_table.setCellWidget(i, 6, btn_view)
                elif st == "failed":
                    err_item = QTableWidgetItem("❌ Thất bại")
                    err_item.setForeground(QColor("#f87171"))
                    err_item.setToolTip(job.get("error", ""))
                    self.fast_tracking_table.setItem(i, 6, err_item)
                else:
                    self.fast_tracking_table.setItem(i, 6, QTableWidgetItem("⏳ Đang xử lý..."))


# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 3: VIDEO GALLERY
# ═══════════════════════════════════════════════════════════════════════════════

class VideoGalleryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        # Title Row
        title_row = QHBoxLayout()
        title = QLabel("Video Gallery")
        title.setObjectName("panel_title")
        title_row.addWidget(title)
        title_row.addStretch()

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self.refresh_gallery)
        title_row.addWidget(btn_refresh)

        btn_folder = QPushButton("📂 Mở thư mục Output")
        btn_folder.clicked.connect(lambda: os.startfile(OUTPUT_DIR) if os.path.isdir(OUTPUT_DIR) else None)
        title_row.addWidget(btn_folder)

        layout.addLayout(title_row)

        # Filter Row
        filter_row = QHBoxLayout()
        self.count_label = QLabel("0 video")
        self.count_label.setObjectName("panel_subtitle")
        filter_row.addWidget(self.count_label)
        filter_row.addStretch()

        filter_row.addWidget(QLabel("Sắp xếp:"))
        self.sort_cb = QComboBox()
        self.sort_cb.addItems(["Mới nhất", "Cũ nhất", "Lớn nhất", "Nhỏ nhất"])
        self.sort_cb.currentIndexChanged.connect(self.refresh_gallery)
        filter_row.addWidget(self.sort_cb)

        layout.addLayout(filter_row)

        # Scroll Area for Grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.grid_widget)
        layout.addWidget(self.scroll)

    def refresh_gallery(self):
        """Tải lại danh sách video vào grid."""
        # Clear existing cards
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not os.path.isdir(OUTPUT_DIR):
            self.count_label.setText("0 video")
            return

        files = [f for f in os.listdir(OUTPUT_DIR)
                 if f.lower().endswith((".mp4", ".webm", ".mkv"))]

        # Sort
        sort_idx = self.sort_cb.currentIndex()
        if sort_idx == 0:  # Mới nhất
            files.sort(key=lambda f: os.path.getmtime(os.path.join(OUTPUT_DIR, f)), reverse=True)
        elif sort_idx == 1:  # Cũ nhất
            files.sort(key=lambda f: os.path.getmtime(os.path.join(OUTPUT_DIR, f)))
        elif sort_idx == 2:  # Lớn nhất
            files.sort(key=lambda f: os.path.getsize(os.path.join(OUTPUT_DIR, f)), reverse=True)
        elif sort_idx == 3:  # Nhỏ nhất
            files.sort(key=lambda f: os.path.getsize(os.path.join(OUTPUT_DIR, f)))

        self.count_label.setText(f"{len(files)} video")

        # Tính số cột dựa trên width
        cols = max(1, (self.scroll.width() - 40) // 272)
        if cols < 1:
            cols = 4

        # Tạo thumbnail & cards
        from thumbnail_cache import extract_thumbnail
        for idx, fname in enumerate(files):
            vpath = os.path.join(OUTPUT_DIR, fname)
            thumb = extract_thumbnail(vpath)
            card = VideoCard(vpath, thumb)
            card.sig_delete.connect(self._on_delete_video)
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

    def _on_delete_video(self, path: str):
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc muốn xóa video?\n{os.path.basename(path)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(path)
                self.refresh_gallery()
                if self.main_win:
                    self.main_win.log(f"Đã xóa: {os.path.basename(path)}")
            except Exception as e:
                QMessageBox.warning(self, "Lỗi", f"Không xóa được: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 4: TÀI KHOẢN
# ═══════════════════════════════════════════════════════════════════════════════

class ManualLoginDialog(QDialog):
    """Mở 1 Chrome SẠCH (profile tạm) để người dùng tự đăng nhập Dola thủ công,
    xong thì lưu toàn bộ cookies + localStorage thành 1 tài khoản."""
    sig_status = pyqtSignal(str, str)    # text, color
    sig_detected = pyqtSignal(dict)      # thông tin user Dola (passport API)
    sig_commit = pyqtSignal(object)      # (cookies, local_storage, user) -> lưu trên UI thread
    sig_done = pyqtSignal(bool, str)     # ok, message

    def __init__(self, main_win, parent=None, google=False):
        super().__init__(parent)
        self.google_mode = google
        self._google_credentials = ("", "")
        self.main_win = main_win
        self.setWindowTitle("Chrome Sạch — Đăng nhập thủ công")
        self.setMinimumWidth(500)
        self.setModal(False)
        self._save_evt = threading.Event()
        self._stop_evt = threading.Event()
        self._proc = None
        self._profile_dir = None
        self._port = None
        self._user = None
        self._finished = False
        self._saved_name = ""
        self._worker_done = False

        self.setStyleSheet("""
            QDialog { background: #0f1524; }
            QLabel { color: #cbd5e1; background: transparent; }
            QLineEdit { background: #1a2035; color: #f1f5f9; border: 1px solid #2a3350;
                        border-radius: 8px; padding: 8px 10px; font-size: 12px; }
            QLineEdit:focus { border-color: #38bdf8; }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        header = QLabel("🧼 Chrome Sạch — Đăng Nhập Thủ Công")
        header.setStyleSheet("color: #f1f5f9; font-size: 16px; font-weight: 800;")
        lay.addWidget(header)

        guide = QLabel(
            "<div style='line-height:150%'>"
            "<b style='color:#38bdf8'>1.</b> Một cửa sổ Chrome hoàn toàn mới (không cookie) sẽ mở trang Dola.<br>"
            "<b style='color:#38bdf8'>2.</b> Tự đăng nhập Dola bằng bất kỳ cách nào (Facebook / Google / Email...).<br>"
            "<b style='color:#38bdf8'>3.</b> Đăng nhập xong bấm <b style='color:#4ade80'>Lưu Cookies &amp; Đóng</b> "
            "(hoặc cứ đóng Chrome — tool sẽ tự lưu nếu đã đăng nhập).</div>"
        )
        guide.setWordWrap(True)
        guide.setStyleSheet("color: #94a3b8; font-size: 12px; background: #141b2d;"
                            " border: 1px solid #222b42; border-radius: 10px; padding: 10px 12px;")
        lay.addWidget(guide)

        if self.google_mode:
            self.setWindowTitle("Đăng nhập Google → Dola")
            header.setText("Google → Dola")
            guide.setText("Nhập tài khoản Google của bạn, rồi bấm Mở Chrome. "
                          "Tool hỗ trợ điền email/mật khẩu; bạn tự hoàn tất 2FA hoặc xác minh trên Chrome. "
                          "Chỉ lưu phiên khi Dola xác nhận đăng nhập. Mật khẩu không ghi ra file.")
            self.google_email = QLineEdit()
            self.google_email.setPlaceholderText("Email Google")
            self.google_password = QLineEdit()
            self.google_password.setPlaceholderText("Mật khẩu (có thể để trống và nhập trên Chrome)")
            self.google_password.setEchoMode(QLineEdit.EchoMode.Password)
            lay.addWidget(self.google_email)
            lay.addWidget(self.google_password)
            self.google_start = QPushButton("Mở Chrome · Đăng nhập Google")
            self.google_start.clicked.connect(self._start_google)
            lay.addWidget(self.google_start)

        name_lbl = QLabel("Tên tài khoản")
        name_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        lay.addWidget(name_lbl)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Để trống = tự đặt theo tên tài khoản Dola")
        lay.addWidget(self.name_edit)

        self.status_lbl = QLabel("⏳ Đang khởi động Chrome sạch...")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("color: #fbbf24; font-size: 12px; font-weight: bold;"
                                      " background: #1a2035; border-radius: 8px; padding: 10px 12px;")
        lay.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_cancel = QPushButton("Huỷ & Đóng Chrome")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet(
            "QPushButton { background: #252e45; color: #fca5a5; border: 1px solid #3a2a35;"
            " border-radius: 8px; padding: 9px 16px; font-weight: bold; }"
            " QPushButton:hover { background: #3b1d24; border-color: #f87171; }")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addStretch()
        self.btn_save = QPushButton("💾 Lưu Cookies & Đóng")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #059669, stop:1 #10b981);"
            " color: white; border: none; border-radius: 8px; padding: 9px 20px; font-weight: bold; font-size: 13px; }"
            " QPushButton:hover { background: #10b981; }"
            " QPushButton:disabled { background: #374151; color: #6b7280; }")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._on_save_clicked)
        btn_row.addWidget(self.btn_save)
        lay.addLayout(btn_row)

        self.sig_status.connect(self._on_status)
        self.sig_detected.connect(self._on_detected)
        self.sig_commit.connect(self._on_commit)
        self.sig_done.connect(self._on_done)

    # ─── Khởi chạy ───────────────────────────────────────────────
    def _start_google(self):
        self._google_credentials = (self.google_email.text().strip(), self.google_password.text())
        self.google_password.clear()
        self.google_email.setEnabled(False)
        self.google_password.setEnabled(False)
        self.google_start.setEnabled(False)
        self.start()

    def start(self):
        if not self._launch_chrome():
            self._worker_done = True
            return
        threading.Thread(target=self._worker, daemon=True).start()

    def _launch_chrome(self) -> bool:
        import tempfile, socket
        if not CHROME_PATH or not os.path.isfile(CHROME_PATH):
            self._on_done(False, "Không tìm thấy Chrome trên máy!")
            return False
        try:
            self._profile_dir = tempfile.mkdtemp(prefix="seedance_clean_")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", 0))
            self._port = s.getsockname()[1]
            s.close()
            cmd = [
                CHROME_PATH,
                f"--remote-debugging-port={self._port}",
                "--remote-debugging-address=127.0.0.1",
                f"--user-data-dir={self._profile_dir}",
                "--lang=vi",
                "--window-position=120,60", "--window-size=1280,900",
            ]
            cmd.extend(CHROME_FLAGS)
            cmd.append("https://console.cloud.google.com/" if self.google_mode else DOLA_URL)
            self._proc = subprocess.Popen(cmd)
            self.main_win.log(f"🧼 Đã mở Chrome sạch (port={self._port}) — hãy đăng nhập Dola thủ công.")
            return True
        except Exception as e:
            self._on_done(False, f"Không mở được Chrome: {e}")
            return False

    # ─── Luồng nền: giám sát cookies qua CDP ─────────────────────
    def _worker(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._watch())
        except Exception as e:
            self.sig_done.emit(False, f"Lỗi giám sát Chrome: {e}")
        finally:
            try:
                loop.close()
            except Exception:
                pass
            self._kill_chrome()
            self._worker_done = True

    async def _watch(self):
        import asyncio
        from playwright.async_api import async_playwright
        helper = FBLoginAutomation()
        pw = await async_playwright().start()
        browser = None
        try:
            for _ in range(40):
                if self._stop_evt.is_set():
                    return
                try:
                    browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{self._port}")
                    break
                except Exception:
                    await asyncio.sleep(1.0)
            if not browser:
                self.sig_done.emit(False, "Không kết nối được Chrome qua CDP.")
                return
            self.sig_status.emit("👀 Chrome đã sẵn sàng — hãy đăng nhập Dola trong cửa sổ Chrome...", "#38bdf8")

            google_flow = None
            if self.google_mode:
                from google_login_automation import GoogleLoginFlow
                google_flow = GoogleLoginFlow(*self._google_credentials)
                self._google_credentials = ("", "")
                self.sig_status.emit("Hoàn tất xác minh Google trên Chrome nếu được yêu cầu; sau đó chọn Google trên Dola.", "#38bdf8")
            snapshot = None
            last_check = 0.0
            while True:
                if self._stop_evt.is_set():
                    await self._close_browser(browser)
                    return
                if not browser.is_connected():
                    if snapshot:
                        self.sig_commit.emit(snapshot)
                        self.sig_done.emit(True, "Chrome đã đóng — đã tự lưu cookies của phiên đăng nhập.")
                    else:
                        self.sig_done.emit(False, "Chrome đã bị đóng trước khi đăng nhập Dola xong.")
                    return

                if google_flow:
                    try:
                        await google_flow.step(browser.contexts[0])
                    except Exception:
                        # Người dùng vẫn có thể hoàn tất đăng nhập thủ công.
                        pass
                save_now = self._save_evt.is_set()
                if save_now or time.time() - last_check >= 3.0:
                    last_check = time.time()
                    try:
                        ctx = browser.contexts[0] if browser.contexts else None
                        if ctx:
                            cookies = await ctx.cookies()
                            has_sid = any(
                                "dola" in (c.get("domain") or "").lower()
                                and c.get("name") in ("sessionid", "sessionid_ss") and c.get("value")
                                for c in cookies
                            )
                            user = await helper.fetch_dola_account_info(ctx) if has_sid else None
                            if user:
                                ls = await self._grab_local_storage(ctx)
                                snapshot = (cookies, ls, user)
                                uid_new = str(user.get("user_id_str") or user.get("user_id") or "")
                                uid_old = str((self._user or {}).get("user_id_str") or (self._user or {}).get("user_id") or "")
                                if uid_new != uid_old:
                                    self._user = user
                                    self.sig_detected.emit(user)
                    except Exception:
                        pass

                    if save_now:
                        self._save_evt.clear()
                        if snapshot:
                            self.sig_commit.emit(snapshot)
                            self.sig_done.emit(True, "Đã lưu cookies thành công!")
                            await self._close_browser(browser)
                            return
                        self.sig_status.emit("⚠️ Chưa phát hiện đăng nhập Dola hợp lệ — đăng nhập xong rồi bấm Lưu lại.", "#fbbf24")
                await asyncio.sleep(0.5)
        finally:
            self._google_credentials = ("", "")
            if self.google_mode and "google_flow" in locals() and google_flow:
                google_flow.password = ""
            try:
                await pw.stop()
            except Exception:
                pass

    async def _grab_local_storage(self, ctx) -> dict:
        for p in ctx.pages:
            if "dola.com" in (p.url or ""):
                try:
                    return await p.evaluate("() => ({ ...localStorage })") or {}
                except Exception:
                    pass
        return {}

    async def _close_browser(self, browser):
        try:
            cdp = await browser.new_browser_cdp_session()
            await cdp.send("Browser.close")
        except Exception:
            pass

    def _kill_chrome(self):
        try:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except Exception:
                    pass
        except Exception:
            pass
        if self._profile_dir:
            import shutil
            for _ in range(5):
                shutil.rmtree(self._profile_dir, ignore_errors=True)
                if not os.path.exists(self._profile_dir):
                    break
                time.sleep(1.0)

    # ─── UI slots ────────────────────────────────────────────────
    def _on_status(self, text: str, color: str):
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;"
                                      " background: #1a2035; border-radius: 8px; padding: 10px 12px;")
        if not self._finished:
            self.btn_save.setEnabled(True)

    def _on_detected(self, user: dict):
        uname = user.get("screen_name") or user.get("name") or "?"
        uid = user.get("user_id_str") or user.get("user_id") or ""
        self._on_status(f"✅ Đã đăng nhập Dola: {uname}  (UID {uid}) — bấm 'Lưu Cookies & Đóng' để lưu.", "#4ade80")
        if not self.name_edit.text().strip():
            self.name_edit.setPlaceholderText(f"Để trống = {self._suggest_name(user)}")

    def _suggest_name(self, user: dict) -> str:
        am = self.main_win.account_manager
        dola_uid = str(user.get("user_id_str") or user.get("user_id") or "")
        for a in am.accounts:
            if dola_uid and a.dola_uid == dola_uid:
                return a.name
        base = (user.get("screen_name") or user.get("name") or "").strip()
        base = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", base).strip(" ._")[:40] or ("Dola_" + dola_uid[-6:])
        name, n = base, 1
        while am.get_account(name):
            n += 1
            name = f"{base}_{n}"
        return name

    def _on_commit(self, payload):
        cookies, ls, user = payload
        main = self.main_win
        am, ss = main.account_manager, main.session_store
        am.load()
        ss.load()
        typed = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", self.name_edit.text().strip())
        name = typed or self._suggest_name(user)
        acc = am.get_account(name)
        if not acc:
            acc = Account(name=name, login_type="manual", created_date=time.strftime("%Y-%m-%d %H:%M"))
            am.accounts.append(acc)
        dola_c = [c for c in cookies if "dola" in (c.get("domain") or "").lower()]
        acc.session_count = len(dola_c)
        acc.dola_session_saved = True
        acc.login_status = "logged_in"
        if acc.status == "error":
            acc.status = "active"
        acc.dola_uid = str(user.get("user_id_str") or user.get("user_id") or acc.dola_uid or "")
        acc.last_check_time = time.time()
        if self.google_mode:
            acc.login_type = "google"
        # Chỉ lưu cookie Dola, không sao chép phiên Google vào kho tài khoản.
        ss.save_session(name, dola_c, ls)
        am.save()
        self._saved_name = name
        QTimer.singleShot(3000, lambda: main.install_video_skill_accounts([name]))
        main.log(f"🎉 [CHROME SẠCH] Đã lưu tài khoản '{name}' ({len(dola_c)} cookies Dola).")
        try:
            main.accounts_panel.refresh_table()
            main.create_panel.refresh_accounts()
        except Exception:
            pass

    def _on_done(self, ok: bool, msg: str):
        self._finished = True
        self.btn_save.setEnabled(False)
        self.btn_cancel.setText("Đóng")
        if ok and self._saved_name:
            msg = f"{msg}  →  Tài khoản: {self._saved_name}"
        self._on_status(("🎉 " if ok else "⚠️ ") + msg, "#4ade80" if ok else "#f87171")
        if not ok:
            self.main_win.log(f"[CHROME SẠCH] {msg}")
        if ok:
            QTimer.singleShot(2500, self.accept)

    def _on_save_clicked(self):
        self._on_status("⏳ Đang kiểm tra đăng nhập & lưu cookies...", "#38bdf8")
        self.btn_save.setEnabled(False)
        self._save_evt.set()

    def reject(self):
        if not self._finished and self._user:
            ans = QMessageBox.question(
                self, "Chưa lưu",
                "Đã phát hiện đăng nhập Dola nhưng chưa lưu cookies.\nLưu trước khi đóng?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if ans == QMessageBox.StandardButton.Cancel:
                return
            if ans == QMessageBox.StandardButton.Yes:
                self._on_save_clicked()
                return
        self._stop_evt.set()
        super().reject()


class AccountCard(QFrame):
    """Thẻ 1 tài khoản: chấm trạng thái + tên đậm + dòng phụ (cookies) + 3 nút icon (Lưu / Mở Chrome / Xoá)."""
    sig_clicked = pyqtSignal(str)
    sig_save = pyqtSignal(str)
    sig_open = pyqtSignal(str)
    sig_delete = pyqtSignal(str)

    def __init__(self, name: str, subtitle: str, dot_color: str, crown: bool = False,
                 tooltip: str = "", parent=None):
        super().__init__(parent)
        self.name = name
        self._selected = False
        self.setObjectName("acc_card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(64)
        self.setMinimumWidth(280)
        if tooltip:
            self.setToolTip(tooltip)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 10, 10)
        lay.setSpacing(12)

        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background: {dot_color}; border-radius: 5px; border: none;")
        lay.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        title = QLabel(name + ("  👑" if crown else ""))
        title.setStyleSheet("color: #f1f5f9; font-size: 13px; font-weight: 700; background: transparent; border: none;")
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        sub = QLabel(subtitle)
        sub.setStyleSheet("color: #7c8799; font-size: 11px; background: transparent; border: none;")
        sub.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_col.addWidget(title)
        text_col.addWidget(sub)
        lay.addLayout(text_col, 1)

        for icon, tip, color, sig in (
            ("💾", f"Lưu Session Dola cho '{name}'", "#facc15", self.sig_save),
            ("🌐", f"Mở Chrome cho '{name}'", "#60a5fa", self.sig_open),
            ("✕", f"Xoá '{name}'", "#f87171", self.sig_delete),
        ):
            b = QPushButton(icon)
            b.setFixedSize(34, 30)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(tip)
            b.setStyleSheet(
                f"QPushButton {{ background: #252e45; color: {color}; border: 1px solid #323c58;"
                f" border-radius: 7px; font-size: 13px; font-weight: bold; padding: 0; }}"
                f" QPushButton:hover {{ background: #2f3a57; border-color: {color}; }}"
                f" QPushButton:pressed {{ background: #1b2236; }}"
            )
            b.clicked.connect(lambda _=False, s=sig: s.emit(self.name))
            lay.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)

        self.set_selected(False)

    def set_selected(self, selected: bool):
        self._selected = selected
        border = "#38bdf8" if selected else "#2a3350"
        hover = "#38bdf8" if selected else "#3d4b6e"
        bg = "#1d2944" if selected else "#1a2035"
        self.setStyleSheet(
            f"QFrame#acc_card {{ background: {bg}; border: 1px solid {border}; border-radius: 10px; }}"
            f" QFrame#acc_card:hover {{ border-color: {hover}; background: #1e2740; }}"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.sig_clicked.emit(self.name)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Nhấp đúp = mở Chrome cho tài khoản
        self.sig_open.emit(self.name)
        super().mouseDoubleClickEvent(event)


class AccountsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 8)
        layout.setSpacing(8)

        # Scroll wrapper
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(10)

        # ─── Title Row ────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel("VIA & Tài Khoản")
        title.setObjectName("panel_title")
        title_row.addWidget(title)
        title_row.addStretch()

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_table)
        title_row.addWidget(btn_refresh)
        inner_layout.addLayout(title_row)

        # ═══ SECTION 1: AUTO LOG VIA FACEBOOK ═══════════════════════════
        self._bulk_stop_requested = False
        via_group = QGroupBox("AUTO LOG VIA FACEBOOK (HỖ TRỢ HÀNG LOẠT / 1 HOẶC NHIỀU VIA)")
        via_group.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 13px; color: #f59e0b;
                        border: 1px solid #374151; border-radius: 8px; padding-top: 18px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 4px 12px; }
        """)
        via_layout = QVBoxLayout(via_group)

        # Top row: Counter badge + Nạp file .txt + Xóa
        via_top_row = QHBoxLayout()
        self.via_count_label = QLabel("📋 Danh sách VIA (Đã phát hiện: 0 tài khoản)")
        self.via_count_label.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")
        via_top_row.addWidget(self.via_count_label)
        via_top_row.addStretch()

        btn_load_via_file = QPushButton("📂 Nạp File VIA (.txt)")
        btn_load_via_file.setFixedHeight(28)
        btn_load_via_file.setStyleSheet("""
            QPushButton { background: #1e3a5f; color: #38bdf8; border: 1px solid #2563eb; border-radius: 5px; font-weight: bold; padding: 0 12px; font-size: 11px; }
            QPushButton:hover { background: #2563eb; color: white; }
        """)
        btn_load_via_file.clicked.connect(self._on_load_via_file)
        via_top_row.addWidget(btn_load_via_file)

        btn_clear_via = QPushButton("🗑️ Xóa")
        btn_clear_via.setFixedHeight(28)
        btn_clear_via.setStyleSheet("""
            QPushButton { background: #374151; color: #f87171; border: 1px solid #4b5563; border-radius: 5px; font-weight: bold; padding: 0 10px; font-size: 11px; }
            QPushButton:hover { background: #ef4444; color: white; }
        """)
        btn_clear_via.clicked.connect(lambda: self.via_cookie_edit.clear())
        via_top_row.addWidget(btn_clear_via)
        via_layout.addLayout(via_top_row)

        via_hint = QLabel("💡 Dán 1 hoặc NHIỀU chuỗi VIA (mỗi VIA một dòng hoặc cách nhau 1 khoảng trắng). Tool sẽ tự động bóc tách và login tuần tự từng acc!")
        via_hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        via_layout.addWidget(via_hint)

        self.via_cookie_edit = QTextEdit()
        self.via_cookie_edit.setPlaceholderText(
            "Dán 1 hoặc NHIỀU chuỗi VIA vào đây (UID|Pass|2FA|Cookie... hoặc c_user=...; xs=...)\n"
            "Mỗi VIA có thể xuống dòng hoặc cách nhau 1 khoảng trắng.\n"
            "Ví dụ:\n"
            "61594339886440|Pass1|2FA1|c_user=61594339886440; xs=...\n"
            "61594339886441|Pass2|2FA2|c_user=61594339886441; xs=..."
        )
        self.via_cookie_edit.setMinimumHeight(85)
        self.via_cookie_edit.textChanged.connect(self._on_via_text_changed)
        via_layout.addWidget(self.via_cookie_edit)

        # Progress bar cho quá trình bulk login
        self.via_progress_bar = QProgressBar()
        self.via_progress_bar.setFixedHeight(18)
        self.via_progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #374151; border-radius: 4px; text-align: center; color: white; font-weight: bold; font-size: 11px; background: #1f2937; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #10b981); border-radius: 3px; }
        """)
        self.via_progress_bar.setVisible(False)
        via_layout.addWidget(self.via_progress_bar)

        self.via_progress_status = QLabel("")
        self.via_progress_status.setStyleSheet("color: #a7f3d0; font-size: 11px; font-weight: bold;")
        self.via_progress_status.setVisible(False)
        via_layout.addWidget(self.via_progress_status)

        via_opt_row = QHBoxLayout()
        lbl_threads = QLabel("Số luồng song song:")
        lbl_threads.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        via_opt_row.addWidget(lbl_threads)
        self.via_threads_spin = QSpinBox()
        self.via_threads_spin.setRange(1, 5)
        self.via_threads_spin.setValue(1)
        self.via_threads_spin.setFixedWidth(60)
        self.via_threads_spin.setToolTip("Số Chrome đăng nhập cùng lúc (1 = tuần tự, an toàn nhất cho VIA)")
        via_opt_row.addWidget(self.via_threads_spin)
        self.via_show_browser_chk = QCheckBox("Hiện cửa sổ Chrome")
        self.via_show_browser_chk.setChecked(True)
        via_opt_row.addWidget(self.via_show_browser_chk)
        via_opt_row.addStretch()
        via_layout.addLayout(via_opt_row)

        via_btn_row = QHBoxLayout()
        self.btn_auto_login = QPushButton("🚀 BẮT ĐẦU ĐĂNG NHẬP HÀNG LOẠT VIA FB")
        self.btn_auto_login.setFixedHeight(38)
        self.btn_auto_login.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #ef4444);
                          color: white; border-radius: 6px; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #dc2626); }
            QPushButton:disabled { background: #4b5563; color: #9ca3af; }
        """)
        self.btn_auto_login.clicked.connect(self.on_auto_login_via)
        via_btn_row.addWidget(self.btn_auto_login)

        self.btn_stop_bulk = QPushButton("⏹ Dừng")
        self.btn_stop_bulk.setFixedSize(80, 38)
        self.btn_stop_bulk.setEnabled(False)
        self.btn_stop_bulk.setStyleSheet("""
            QPushButton { background: #7f1d1d; color: #fca5a5; border: 1px solid #991b1b; border-radius: 6px; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background: #991b1b; color: white; }
            QPushButton:disabled { background: #374151; color: #6b7280; border-color: #4b5563; }
        """)
        self.btn_stop_bulk.clicked.connect(self.on_stop_bulk_login)
        via_btn_row.addWidget(self.btn_stop_bulk)

        via_layout.addLayout(via_btn_row)

        inner_layout.addWidget(via_group)

        # ═══ SECTION 2: MỞ NHIỀU TAB TÀI KHOẢN ════════════════════════
        tab_group = QGroupBox("MỞ NHIỀU TAB TÀI KHOẢN ĐỘC LẬP")
        tab_group.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 12px; color: #38bdf8;
                        border: 1px solid #374151; border-radius: 8px; padding-top: 18px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 4px 12px; }
        """)
        tab_layout = QHBoxLayout(tab_group)

        self.tab_count_spin = QSpinBox()
        self.tab_count_spin.setRange(1, 10)
        self.tab_count_spin.setValue(5)
        self.tab_count_spin.setFixedWidth(60)
        tab_layout.addWidget(self.tab_count_spin)

        btn_open_tabs = QPushButton("Mở Các Tab Tài Khoản")
        btn_open_tabs.setFixedHeight(34)
        btn_open_tabs.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #ef4444);
                          color: white; border-radius: 6px; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #dc2626); }
        """)
        btn_open_tabs.clicked.connect(self.on_open_multi_tabs)
        tab_layout.addWidget(btn_open_tabs)

        tab_layout.addStretch()

        btn_catch_tabs = QPushButton("+ Bắt Tab Hiện Tại")
        btn_catch_tabs.setFixedHeight(30)
        btn_catch_tabs.clicked.connect(lambda: self.main_win.log("Đang kiểm tra tabs đang mở...") if self.main_win else None)
        tab_layout.addWidget(btn_catch_tabs)

        inner_layout.addWidget(tab_group)

        # ═══ SECTION 3: NHẬP COOKIES / PROFILE MỚI ═════════════════════
        cookie_group = QGroupBox("+ NHẬP COOKIES / PROFILE MỚI")
        cookie_group.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 12px; color: #4ade80;
                        border: 1px solid #374151; border-radius: 8px; padding-top: 18px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 4px 12px; }
        """)
        cookie_layout = QVBoxLayout(cookie_group)

        # Tên tài khoản
        name_row = QHBoxLayout()
        self.cookie_name_edit = QLineEdit()
        self.cookie_name_edit.setPlaceholderText("Tên tài khoản (để trống để tự sinh #01, #02...)")
        name_row.addWidget(self.cookie_name_edit)

        btn_load_file = QPushButton("Nạp File")
        btn_load_file.clicked.connect(self._on_load_cookie_file)
        name_row.addWidget(btn_load_file)

        btn_clear_cookie = QPushButton("Xóa hết")
        btn_clear_cookie.clicked.connect(lambda: self.cookie_paste_edit.clear())
        name_row.addWidget(btn_clear_cookie)

        cookie_layout.addLayout(name_row)

        # Cookie textarea
        self.cookie_paste_edit = QTextEdit()
        self.cookie_paste_edit.setPlaceholderText(
            "Dán mảng JSON cookies, định dạng Netscape hoặc chuỗi\n"
            "c_user=...; xs=..."
        )
        self.cookie_paste_edit.setMaximumHeight(80)
        cookie_layout.addWidget(self.cookie_paste_edit)

        btn_save_cookie = QPushButton("+ Lưu Tài Khoản Vào Bộ Nhớ")
        btn_save_cookie.setFixedHeight(34)
        btn_save_cookie.setStyleSheet("""
            QPushButton { background: #374151; color: white; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #4b5563; }
        """)
        btn_save_cookie.clicked.connect(self.on_save_cookie_profile)
        cookie_layout.addWidget(btn_save_cookie)

        inner_layout.addWidget(cookie_group)

        # ═══ SECTION 4: DANH SÁCH TÀI KHOẢN ═══════════════════════════
        self.acc_group = QGroupBox("📋 DANH SÁCH TÀI KHOẢN ĐÃ LƯU ( 0 )")
        self.acc_group.setStyleSheet("""
            QGroupBox { font-weight: 800; font-size: 13px; color: #f1f5f9; background: #111827;
                        border: 1px solid #263048; border-radius: 12px; padding-top: 22px; margin-top: 4px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 6px 14px; }
        """)
        acc_layout = QVBoxLayout(self.acc_group)
        acc_layout.setContentsMargins(12, 8, 12, 12)
        acc_layout.setSpacing(10)

        # Thanh tìm kiếm + chú thích + nút Chrome sạch
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        self.acc_search = QLineEdit()
        self.acc_search.setPlaceholderText("🔎  Tìm tài khoản...")
        self.acc_search.setClearButtonEnabled(True)
        self.acc_search.setFixedWidth(240)
        self.acc_search.setStyleSheet(
            "QLineEdit { background: #1a2035; color: #e2e8f0; border: 1px solid #2a3350;"
            " border-radius: 8px; padding: 6px 10px; font-size: 12px; }"
            " QLineEdit:focus { border-color: #38bdf8; }")
        self.acc_search.textChanged.connect(self._relayout_cards)
        top_row.addWidget(self.acc_search)

        legend = QLabel(
            "<span style='color:#3b82f6'>●</span> Có session &nbsp;&nbsp;"
            "<span style='color:#f5b014'>●</span> Chính chủ 👑 &nbsp;&nbsp;"
            "<span style='color:#64748b'>●</span> Cooldown/Lỗi &nbsp;&nbsp;"
            "<span style='color:#ef4444'>●</span> Chưa lưu session"
        )
        legend.setStyleSheet("color: #7c8799; font-size: 11px; background: transparent;")
        top_row.addWidget(legend)
        top_row.addStretch()

        self.btn_clean_chrome = QPushButton("🧼 Mở Chrome Sạch · Login Thủ Công")
        self.btn_clean_chrome.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clean_chrome.setToolTip(
            "Mở 1 Chrome hoàn toàn mới (không cookie). Bạn tự đăng nhập Dola,\n"
            "xong bấm 'Lưu Cookies & Đóng' để lưu thành tài khoản mới.")
        self.btn_clean_chrome.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0891b2, stop:1 #6366f1);"
            " color: white; border: none; border-radius: 8px; padding: 8px 16px; font-weight: bold; font-size: 12px; }"
            " QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #06b6d4, stop:1 #818cf8); }"
            " QPushButton:pressed { background: #0e7490; }")
        self.btn_clean_chrome.clicked.connect(self.on_open_clean_chrome)
        top_row.addWidget(self.btn_clean_chrome)
        self.btn_google_login = QPushButton("Google · Đăng nhập")
        self.btn_google_login.clicked.connect(lambda: self.main_win.open_clean_chrome_manual_login(google=True))
        top_row.addWidget(self.btn_google_login)
        self.btn_install_video_skill = QPushButton("Skill 30s · Cài cho các tài khoản")
        self.btn_install_video_skill.clicked.connect(lambda: self.main_win.install_video_skill_accounts())
        top_row.addWidget(self.btn_install_video_skill)
        acc_layout.addLayout(top_row)

        # Danh sách dạng thẻ (grid tự co giãn 1-3 cột)
        self._acc_cards = []
        self._selected_name = None
        self._card_cols = 0
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards_scroll.setMinimumHeight(260)
        self.cards_scroll.setMaximumHeight(460)
        self.cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.cards_container = QWidget()
        self.cards_container.setObjectName("cards_container")
        self.cards_container.setStyleSheet("QWidget#cards_container { background: transparent; }")
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setContentsMargins(0, 0, 6, 0)
        self.cards_grid.setHorizontalSpacing(10)
        self.cards_grid.setVerticalSpacing(8)
        self.cards_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._cards_empty = QLabel("Chưa có tài khoản nào — bấm 🧼 Mở Chrome Sạch để đăng nhập thủ công.")
        self._cards_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cards_empty.setStyleSheet("color: #64748b; font-size: 12px; padding: 30px; background: transparent;")
        self.cards_scroll.setWidget(self.cards_container)
        self.cards_scroll.viewport().installEventFilter(self)
        acc_layout.addWidget(self.cards_scroll)

        # Action bar below table
        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        btn_chrome = QPushButton("Mở Chrome")
        btn_chrome.setObjectName("btn_primary")
        btn_chrome.clicked.connect(self.on_open_chrome)
        action_row.addWidget(btn_chrome)

        btn_session = QPushButton("Lưu Session")
        btn_session.setObjectName("btn_success")
        btn_session.clicked.connect(self.on_save_session)
        action_row.addWidget(btn_session)

        btn_delete = QPushButton("Xóa")
        btn_delete.setObjectName("btn_danger")
        btn_delete.clicked.connect(self.on_delete)
        action_row.addWidget(btn_delete)

        action_row.addStretch()

        btn_scan = QPushButton("🔍 Quét Session")
        btn_scan.setObjectName("btn_secondary")
        btn_scan.setToolTip("Quét các trình duyệt Chrome đang mở và tự động lưu Session Dola")
        btn_scan.clicked.connect(self.on_scan_all_sessions)
        action_row.addWidget(btn_scan)

        self.btn_scan_dead = QPushButton("🩺 Quét & Xoá Acc Die Cookie")
        self.btn_scan_dead.setStyleSheet("""
            QPushButton { background: #7f1d1d; color: #fecaca; border: 1px solid #b91c1c; border-radius: 6px; font-weight: bold; padding: 6px 12px; }
            QPushButton:hover { background: #b91c1c; color: white; }
            QPushButton:disabled { background: #374151; color: #6b7280; border-color: #4b5563; }
        """)
        self.btn_scan_dead.setToolTip("Kiểm tra cookie Dola của TẤT CẢ tài khoản qua API passport, sau đó xoá các tài khoản đã die")
        self.btn_scan_dead.clicked.connect(self.on_scan_dead_accounts)
        action_row.addWidget(self.btn_scan_dead)

        btn_import_sll = QPushButton("📥 Import / Cập Nhật Cookies")
        btn_import_sll.setObjectName("btn_secondary")
        btn_import_sll.setToolTip("Import hoặc cập nhật danh sách cookies cho 1 hoặc nhiều tài khoản")
        btn_import_sll.clicked.connect(self.on_import_dola_cookies)
        action_row.addWidget(btn_import_sll)

        btn_export_cookies = QPushButton("📤 Xuất Cookies Cho Extension")
        btn_export_cookies.setStyleSheet("background: #ff7e00; color: #000000; font-weight: bold; padding: 6px 12px; border-radius: 6px;")
        btn_export_cookies.setToolTip("Xuất toàn bộ cookies tài khoản ra file JSON và copy vào clipboard để đồng bộ vào Extension")
        btn_export_cookies.clicked.connect(self.on_export_cookies)
        action_row.addWidget(btn_export_cookies)

        acc_layout.addLayout(action_row)

        inner_layout.addWidget(self.acc_group)
        inner_layout.addStretch()

        scroll.setWidget(inner)
        layout.addWidget(scroll)

    # ─── Event Handlers ──────────────────────────────────────────────

    def get_selected_name(self) -> Optional[str]:
        names = {c.name for c in self._acc_cards}
        if not self._selected_name or self._selected_name not in names:
            QMessageBox.warning(self, "Chưa chọn", "Vui lòng nhấp chọn 1 tài khoản trong danh sách!")
            return None
        return self._selected_name

    def _select_card(self, name: str):
        self._selected_name = name
        for c in self._acc_cards:
            c.set_selected(c.name == name)

    def _card_action(self, action: str, name: str):
        self._select_card(name)
        if not self.main_win:
            return
        if action == "save":
            self.main_win.save_session_for_account(name)
        elif action == "open":
            self.main_win.open_chrome_for_account(name)
        elif action == "delete":
            self.main_win.delete_account(name)

    def eventFilter(self, obj, event):
        # Tự co giãn số cột thẻ khi đổi kích thước
        if obj is self.cards_scroll.viewport() and event.type() == QEvent.Type.Resize:
            cols = self._calc_card_cols()
            if cols != self._card_cols:
                self._relayout_cards()
        return super().eventFilter(obj, event)

    def _calc_card_cols(self) -> int:
        w = self.cards_scroll.viewport().width()
        return max(1, min(3, w // 340))

    def _relayout_cards(self, *_):
        grid = self.cards_grid
        while grid.count():
            grid.takeAt(0)
        cols = self._calc_card_cols()
        self._card_cols = cols
        kw = self.acc_search.text().strip().lower()
        visible = [c for c in self._acc_cards if not kw or kw in c.name.lower()]
        for c in self._acc_cards:
            if c not in visible:
                c.hide()
        if not visible:
            self._cards_empty.setText(
                "Không tìm thấy tài khoản phù hợp." if self._acc_cards
                else "Chưa có tài khoản nào — bấm 🧼 Mở Chrome Sạch để đăng nhập thủ công.")
            grid.addWidget(self._cards_empty, 0, 0, 1, cols)
            self._cards_empty.show()
        else:
            self._cards_empty.hide()
            for idx, c in enumerate(visible):
                grid.addWidget(c, idx // cols, idx % cols)
                c.show()
        for col in range(4):
            grid.setColumnStretch(col, 1 if col < cols else 0)

    def refresh_table(self):
        """Tải lại danh sách tài khoản (dạng thẻ)."""
        if not self.main_win:
            return
        # Đảm bảo đọc dữ liệu mới nhất từ file
        self.main_win.session_store.load()
        self.main_win.account_manager.load()
        accounts = self.main_win.account_manager.get_all()
        self.acc_group.setTitle(f"📋 DANH SÁCH TÀI KHOẢN ĐÃ LƯU ( {len(accounts)} )")

        for c in self._acc_cards:
            c.hide()
            c.deleteLater()
        self._acc_cards = []

        for acc in accounts:
            name = acc["name"]
            login_type = acc.get("login_type", "") or ""
            uid = acc.get("fb_uid", "") or acc.get("dola_uid", "")
            status = acc.get("status", "active")
            used = acc.get("quota_used", 0)
            mx = acc.get("quota_max", 4)
            health = acc.get("session_health", 0.0) or 0.0

            has_session = (self.main_win.session_store.has_session(name)
                           and acc.get('login_status') != 'login_required')
            n_cookies = 0
            if has_session:
                info = self.main_win.session_store.get_session_info(name)
                n_cookies = info.get("cookies_count", 0)

            crown = has_session and login_type.lower() in ("manual", "dola_direct", "google")
            if not has_session:
                dot = "#ef4444"
            elif status != "active":
                dot = "#64748b"
            elif crown:
                dot = "#f5b014"
            else:
                dot = "#3b82f6"

            proxy_str = acc.get("proxy", "") or acc.get("proxy_direct", "")
            parts = [f"{n_cookies} cookies" if has_session else "Chưa lưu session"]
            if login_type:
                parts.append(login_type.replace("_", " ").capitalize())
            parts.append(f"Quota {used}/{mx}")
            if proxy_str:
                short_p = proxy_str.split('@')[-1] if '@' in proxy_str else proxy_str
                parts.append(f"🌐 {short_p}")
            if status != "active":
                parts.append(status.capitalize())
            subtitle = "  ·  ".join(parts)

            tooltip = (
                f"Tên: {name}\nUID: {uid or '—'}\nLoại: {login_type or '—'}\n"
                f"Proxy: {proxy_str or 'Tự cấp từ pool VPN'}\n"
                f"Session Dola: {str(n_cookies) + ' cookies' if has_session else 'Chưa lưu'}\n"
                f"Cookie FB: {'Có' if acc.get('fb_cookies') else 'Không'}\n"
                f"Trạng thái: {status}\nQuota: {used}/{mx}\n"
                f"Health: {f'{health:.0f}%' if health > 0 else '—'}\n\n"
                f"Nhấp để chọn · Nhấp đúp để mở Chrome"
            )

            card = AccountCard(name, subtitle, dot, crown=crown, tooltip=tooltip, parent=self.cards_container)
            card.sig_clicked.connect(self._select_card)
            card.sig_save.connect(lambda n: self._card_action("save", n))
            card.sig_open.connect(lambda n: self._card_action("open", n))
            card.sig_delete.connect(lambda n: self._card_action("delete", n))
            if name == self._selected_name:
                card.set_selected(True)
            self._acc_cards.append(card)

        if self._selected_name not in {c.name for c in self._acc_cards}:
            self._selected_name = None
        self._relayout_cards()

    def on_open_clean_chrome(self):
        if self.main_win:
            self.main_win.open_clean_chrome_manual_login()

    def on_scan_all_sessions(self):
        """Kích hoạt quét toàn bộ Chrome đang chạy để lưu session."""
        if self.main_win:
            self.main_win.scan_and_auto_save_all_running(force_scan=True)

    def _on_via_text_changed(self):
        """Cập nhật số lượng VIA phát hiện được theo thời gian thực."""
        raw = self.via_cookie_edit.toPlainText().strip()
        vias = parse_bulk_via_text(raw)
        self.via_count_label.setText(f"📋 Danh sách VIA (Đã phát hiện: {len(vias)} tài khoản)")

    def _on_load_via_file(self):
        """Nạp danh sách VIA từ file .txt."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Chọn file danh sách VIA (.txt)", "", "Text Files (*.txt);;All Files (*)"
        )
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.via_cookie_edit.setPlainText(content)
            vias = parse_bulk_via_text(content)
            if self.main_win:
                self.main_win.log(f"📂 Đã nạp file VIA '{os.path.basename(filepath)}' — Phát hiện {len(vias)} tài khoản!")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi nạp file", f"Không đọc được file: {e}")

    def on_stop_bulk_login(self):
        """Dừng tiến trình đăng nhập hàng loạt."""
        self._bulk_stop_requested = True
        if self.main_win:
            self.main_win.log("⏹ Đã gửi yêu cầu dừng đăng nhập hàng loạt...")
        self.btn_stop_bulk.setEnabled(False)
        self.via_progress_status.setText("⏹ Đang dừng... Sẽ đóng Chrome an toàn sau account hiện tại.")

    def on_auto_login_via(self):
        # Auto login hang loat VIA FB -> Dola (1-5 luong song song)
        raw = self.via_cookie_edit.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "Thieu du lieu", "Vui long dan chuoi VIA hoac bam Nap File VIA (.txt)!")
            return
        if not self.main_win:
            return
        via_list = parse_bulk_via_text(raw)
        if not via_list:
            QMessageBox.warning(self, "Khong tim thay VIA", "Khong phat hien chuoi VIA hop le nao!")
            return

        total = len(via_list)
        threads = max(1, min(self.via_threads_spin.value(), total))
        show_browser = self.via_show_browser_chk.isChecked()
        self._bulk_stop_requested = False
        main = self.main_win

        self.btn_auto_login.setEnabled(False)
        self.btn_stop_bulk.setEnabled(True)
        self.via_progress_bar.setVisible(True)
        self.via_progress_bar.setRange(0, total)
        self.via_progress_bar.setValue(0)
        self.via_progress_status.setVisible(True)
        self.via_progress_status.setText(f"Bat dau dang nhap 0/{total} tai khoan ({threads} luong)...")
        main.log(f"BAT DAU AUTO LOGIN HANG LOAT: {total} VIA, {threads} luong song song...")

        # Port rieng 9290+ de khong dung Chrome cua Worker Pool tao video (9250-9269)
        BASE_WORKER_ID = 40

        def _run_bulk():
            import asyncio
            stats = {"ok": 0, "fail": 0, "done": 0}
            failed_lines = []

            def _update_progress():
                msg = f"[{stats['done']}/{total}] Thanh cong: {stats['ok']} | Loi: {stats['fail']}"
                main.run_on_ui(lambda d=stats["done"], m=msg: (
                    self.via_progress_bar.setValue(d), self.via_progress_status.setText(m)))

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                from browser_manager import BrowserManager
                bm = BrowserManager()

                async def _login_one(idx, via_item, wid):
                    fields = parse_via_fields(via_item)
                    uid = fields.get("uid", "")
                    name = self._resolve_via_account_name(uid, idx)
                    main.sig_log.emit("=" * 60)
                    main.sig_log.emit(f"[{idx}/{total}] Dang xu ly '{name}' (UID={uid or '?'})...")
                    fb_auto = FBLoginAutomation()
                    try:
                        await bm.launch_temp_chrome(wid, show_browser=show_browser, load_extension=False)
                        browser = await bm.connect_worker(wid, setup_extension=False)
                        if not browser:
                            raise Exception("Khong ket noi duoc Chrome (CDP)")
                        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
                        await ctx.clear_cookies()
                        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

                        def on_progress(msg, n=name):
                            main.sig_log.emit(f"  [{n}] {msg}")

                        ok = await fb_auto.full_auto_login(ctx, page, via_item, on_progress=on_progress)
                        if not ok:
                            return False, fb_auto.last_error or "Khong dang nhap duoc Dola"

                        cookies = await ctx.cookies()
                        dola_c = [c for c in cookies if "dola" in (c.get("domain") or "").lower()]
                        dola_page = next((p for p in ctx.pages if "dola.com" in (p.url or "")), page)
                        ls = {}
                        try:
                            await dola_page.evaluate(
                                "() => { localStorage.setItem('__dolaDurBypass','1'); "
                                "localStorage.setItem('__dolaTargetDur','31'); "
                                "localStorage.setItem('__dolaDur31','1'); "
                                "localStorage.setItem('__dolaDur15','1'); }")
                            ls = await dola_page.evaluate(
                                "() => { const d = {}; for (let i = 0; i < localStorage.length; i++) "
                                "{ const k = localStorage.key(i); d[k] = localStorage.getItem(k); } return d; }")
                        except Exception:
                            pass

                        user = fb_auto.dola_user or {}
                        main.run_on_ui(lambda: self._commit_via_login(
                            name, uid, fields, via_item, cookies, ls, user))
                        sid = next((c["value"] for c in dola_c if c.get("name") == "sessionid"), "")
                        main.sig_log.emit(
                            f"OK '{name}' - Dola user: {user.get('screen_name') or user.get('name') or '?'} "
                            f"(id={user.get('user_id_str') or user.get('user_id') or '?'}), "
                            f"{len(dola_c)} cookies, sessionid={sid[:8]}...")
                        return True, ""
                    except Exception as e:
                        return False, str(e)
                    finally:
                        try:
                            await bm.cleanup_worker(wid)
                        except Exception:
                            pass

                async def _do_bulk():
                    wid_pool = asyncio.Queue()
                    for w in range(threads):
                        wid_pool.put_nowait(BASE_WORKER_ID + w)

                    async def runner(idx, via_item):
                        wid = await wid_pool.get()
                        try:
                            if self._bulk_stop_requested:
                                return
                            ok, reason = await _login_one(idx, via_item, wid)
                            stats["done"] += 1
                            if ok:
                                stats["ok"] += 1
                            else:
                                stats["fail"] += 1
                                failed_lines.append(via_item)
                                main.sig_log.emit(f"[{idx}/{total}] THAT BAI: {reason}")
                            _update_progress()
                            main.run_on_ui(self.refresh_table)
                            if not self._bulk_stop_requested:
                                await asyncio.sleep(2.0)
                        finally:
                            wid_pool.put_nowait(wid)

                    await asyncio.gather(*(runner(i, v) for i, v in enumerate(via_list, 1)),
                                         return_exceptions=True)

                loop.run_until_complete(_do_bulk())
                try:
                    loop.run_until_complete(bm.cleanup_all_workers())
                    if bm._playwright:
                        loop.run_until_complete(bm._playwright.stop())
                except Exception:
                    pass
                loop.close()

            except Exception as e:
                main.sig_log.emit(f"Loi quy trinh Auto Login Hang Loat: {e}")

            finally:
                failed_file = ""
                if failed_lines:
                    try:
                        stamp = time.strftime("%Y%m%d_%H%M%S")
                        failed_file = os.path.join(DATA_DIR, "via_login_failed_" + stamp + ".txt")
                        with open(failed_file, "w", encoding="utf-8") as f:
                            f.write("\n".join(failed_lines) + "\n")
                    except Exception:
                        failed_file = ""
                skipped = total - stats["done"]
                final_msg = "HOAN TAT: %d/%d thanh cong, %d that bai" % (stats["ok"], total, stats["fail"])
                if skipped:
                    final_msg += ", %d bo qua (da dung)" % skipped
                main.sig_log.emit("=" * 60)
                main.sig_log.emit(final_msg)
                if failed_file:
                    main.sig_log.emit("Danh sach VIA loi da luu: " + failed_file)

                def _finish_ui():
                    self.btn_auto_login.setEnabled(True)
                    self.btn_stop_bulk.setEnabled(False)
                    self.via_progress_bar.setValue(stats["done"])
                    self.via_progress_status.setText(final_msg)
                    self.refresh_table()
                    if self.main_win:
                        self.main_win.create_panel.refresh_accounts()

                main.run_on_ui(_finish_ui)

        threading.Thread(target=_run_bulk, daemon=True).start()

    def _resolve_via_account_name(self, uid: str, idx: int) -> str:
        # Dung lai account cu cung UID (tranh tao trung FB_xxx_2, FB_xxx_3...)
        am = self.main_win.account_manager
        if uid:
            preferred = "FB_" + uid
            matches = [a for a in am.accounts if a.fb_uid == uid or a.name == preferred]
            for a in matches:
                if a.name == preferred:
                    return a.name
            if matches:
                return matches[0].name
            name = preferred
        else:
            name = "VIA_" + time.strftime("%m%d%H%M") + "_" + str(idx)
        base, n = name, 1
        while am.get_account(name) and am.get_account(name).fb_uid not in ("", uid):
            n += 1
            name = base + "_" + str(n)
        return name

    def _commit_via_login(self, name, uid, fields, via_item, cookies, ls, user):
        # Chay tren UI thread: luu account + session Dola vao file
        main = self.main_win
        am = main.account_manager
        ss = main.session_store
        am.load()
        ss.load()
        acc = am.get_account(name)
        if not acc:
            acc = Account(name=name, login_type="facebook",
                          created_date=time.strftime("%Y-%m-%d %H:%M"))
            am.accounts.append(acc)
        if uid:
            acc.fb_uid = uid
        if fields.get("password"):
            acc.fb_password = fields["password"]
        if fields.get("twofa"):
            acc.fb_2fa = fields["twofa"]
        if fields.get("token"):
            acc.fb_token = fields["token"]
        acc.fb_cookies = fields.get("cookie") or via_item
        acc.cookie_count = len(parse_via_cookie_string(fields.get("cookie") or via_item))
        dola_c = [c for c in cookies if "dola" in (c.get("domain") or "").lower()]
        acc.session_count = len(dola_c)
        acc.dola_session_saved = True
        acc.login_status = "logged_in"
        if acc.status == "error":
            acc.status = "active"
        if user:
            acc.dola_uid = str(user.get("user_id_str") or user.get("user_id") or "")
        acc.last_check_time = time.time()
        ss.save_session(name, cookies, ls)
        am.save()
        self.refresh_table()
        if hasattr(main, "create_panel"):
            main.create_panel.refresh_accounts()
        main.install_video_skill_accounts([name])

    def on_scan_dead_accounts(self):
        # Quet cookie Dola cua tat ca tai khoan (passport API) -> xoa tai khoan die
        main = self.main_win
        if not main:
            return
        main.account_manager.load()
        main.session_store.load()
        names = [a.name for a in main.account_manager.accounts]
        for n in main.session_store._sessions.keys():
            if n not in names:
                names.append(n)
        if not names:
            QMessageBox.information(self, "Trong", "Chua co tai khoan nao de quet.")
            return

        self.btn_scan_dead.setEnabled(False)
        self.btn_scan_dead.setText("Dang quet 0/%d..." % len(names))
        main.log("BAT DAU QUET COOKIE DOLA cho %d tai khoan..." % len(names))

        def _worker():
            from dola_session_checker import scan_accounts

            def on_progress(res, done, total):
                main.sig_log.emit("  [%d/%d] %s: %s %s" % (
                    done, total, res.name, res.status.upper(), res.screen_name or res.detail))
                main.run_on_ui(lambda d=done, t=total: self.btn_scan_dead.setText("Dang quet %d/%d..." % (d, t)))

            try:
                results = scan_accounts(names, main.session_store, max_workers=8, on_progress=on_progress)
            except Exception as e:
                main.sig_log.emit("Loi quet cookie Dola: %s" % e)
                results = []
            main.run_on_ui(lambda: self._on_scan_dead_finished(results))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_scan_dead_finished(self, results):
        from dola_session_checker import delete_accounts, STATUS_LIVE, STATUS_DEAD, STATUS_NO_SESSION
        main = self.main_win
        self.btn_scan_dead.setEnabled(True)
        self.btn_scan_dead.setText("\U0001FA7A Qu\u00e9t & Xo\u00e1 Acc Die Cookie")
        if not results:
            return

        live = [r for r in results if r.status == STATUS_LIVE]
        dead = [r for r in results if r.status == STATUS_DEAD]
        nosess = [r for r in results if r.status == STATUS_NO_SESSION]
        errs = [r for r in results if r.status not in (STATUS_LIVE, STATUS_DEAD, STATUS_NO_SESSION)]

        # Cap nhat trang thai cho account con song
        am = main.account_manager
        am.load()
        for r in results:
            a = am.get_account(r.name)
            if not a:
                continue
            a.last_check_time = time.time()
            if r.status == STATUS_LIVE:
                a.login_status = "logged_in"
                if r.user_id:
                    a.dola_uid = r.user_id
            elif r.status in (STATUS_DEAD, STATUS_NO_SESSION):
                a.login_status = "expired"
        am.save()

        summary = "Song: %d | Die cookie: %d | Chua co session: %d | Loi mang (giu lai): %d" % (
            len(live), len(dead), len(nosess), len(errs))
        main.log("KET QUA QUET: " + summary)
        if not dead and not nosess:
            QMessageBox.information(self, "Ket qua quet", summary + "\n\nKhong co tai khoan die nao.")
            self.refresh_table()
            return

        lines = ["- %s  (%s)" % (r.name, r.detail[:60]) for r in dead + nosess]
        box = QMessageBox(self)
        box.setWindowTitle("Xoa tai khoan die cookie?")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(summary + "\n\nCac tai khoan se bi XOA (ca account + session):")
        box.setDetailedText("\n".join(lines))
        chk = QCheckBox("Xoa ca tai khoan CHUA CO session (%d)" % len(nosess))
        chk.setChecked(True)
        box.setCheckBox(chk)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            self.refresh_table()
            return

        to_delete = [r.name for r in dead]
        if chk.isChecked():
            to_delete += [r.name for r in nosess]
        deleted = delete_accounts(to_delete, main.account_manager, main.session_store)
        main.log("Da xoa %d tai khoan die: %s" % (len(deleted), ", ".join(deleted)))
        self.refresh_table()
        if hasattr(main, "create_panel"):
            main.create_panel.refresh_accounts()

    def on_open_multi_tabs(self):
        """Mở nhiều tab Chrome cho nhiều account."""
        if not self.main_win:
            return
        count = self.tab_count_spin.value()
        accounts = self.main_win.account_manager.get_all()
        if not accounts:
            QMessageBox.warning(self, "Chưa có account", "Vui lòng thêm ít nhất 1 account trước!")
            return

        accounts = [a for a in accounts
                    if self.main_win.session_store.has_session(a['name'])
                    and a.get('login_status') != 'login_required']
        accounts.sort(key=lambda a: (
            a.get('session_health', 0), a.get('last_check_time', 0),
            self.main_win.session_store.get_session_info(a['name']).get('saved_at', 0)
        ), reverse=True)
        chosen = accounts[:count]
        if not chosen:
            QMessageBox.warning(self, 'Cần đăng nhập', 'Chưa có phiên lưu để mở. Dùng Mở Chrome Sạch để đăng nhập.')
            return
        for account in chosen:
            self.main_win.open_chrome_for_account(account['name'])
        self.main_win.log('Mở profile riêng và xác thực Dola: ' + ', '.join(a['name'] for a in chosen))

    def on_save_cookie_profile(self):
        """Lưu cookies/profile mới từ textarea."""
        if not self.main_win:
            return
        raw = self.cookie_paste_edit.toPlainText().strip()
        name = self.cookie_name_edit.text().strip()

        if not raw:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Vui lòng paste cookies vào ô!")
            return

        parsed_accounts = parse_bulk_dola_cookies(raw, default_name=name)
        saved_skill_accounts = []
        if not parsed_accounts:
            # Fallback: try as VIA cookie
            acc = self.main_win.account_manager.add_account_from_via(raw, display_name=name)
            self.main_win.log(f"✅ Đã tạo account từ VIA: {acc.name}")
        else:
            for acc_name, cookies_list in parsed_accounts:
                if not acc_name:
                    acc_name = name or f"dola_{len(self.main_win.account_manager.accounts) + 1:02d}"
                if not cookies_list:
                    continue
                # Tạo account nếu chưa có
                existing = self.main_win.account_manager.get_account(acc_name)
                if not existing:
                    try:
                        self.main_win.account_manager.add_account(name=acc_name, login_type="dola_direct")
                    except ValueError:
                        pass
                self.main_win.session_store.save_session(acc_name, cookies_list, {})
                acc_obj = self.main_win.account_manager.get_account(acc_name)
                if acc_obj:
                    acc_obj.dola_session_saved = True
                saved_skill_accounts.append(acc_name)
                self.main_win.log(f"✅ Đã lưu session cho '{acc_name}' ({len(cookies_list)} cookies)")

            self.main_win.account_manager.save()

        self.refresh_table()
        if hasattr(self.main_win, 'create_panel'):
            self.main_win.create_panel.refresh_accounts()
        self.cookie_paste_edit.clear()
        self.cookie_name_edit.clear()
        if saved_skill_accounts:
            self.main_win.install_video_skill_accounts(saved_skill_accounts)

    def _on_load_cookie_file(self):
        fp, _ = QFileDialog.getOpenFileName(self, "Chọn file Cookies", "",
            "Text/JSON (*.txt *.json);;All files (*.*)")
        if fp:
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    self.cookie_paste_edit.setPlainText(f.read())
            except Exception as e:
                QMessageBox.warning(self, "Lỗi", f"Không đọc được file: {e}")

    def on_open_chrome(self):
        name = self.get_selected_name()
        if name and self.main_win:
            self.main_win.open_chrome_for_account(name)

    def on_save_session(self):
        name = self.get_selected_name()
        if name and self.main_win:
            self.main_win.save_session_for_account(name)

    def on_delete(self):
        name = self.get_selected_name()
        if name and self.main_win:
            self.main_win.delete_account(name)

    def on_import_dola_cookies(self):
        if self.main_win:
            self.main_win.import_dola_cookies_dialog()

    def on_export_cookies(self):
        if self.main_win:
            self.main_win.export_all_cookies_for_extension()







# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 5: PROXY & ANTI-BAN
# ═══════════════════════════════════════════════════════════════════════════════

class ProxyPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_win = parent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        title = QLabel("Proxy & Anti-Ban")
        title.setObjectName("panel_title")
        layout.addWidget(title)
        subtitle = QLabel("Quản lý bật/tắt Proxy, chọn nguồn từ Tool VPN2proxy hoặc Proxy ngoài riêng, và cấu hình chống ban")
        subtitle.setObjectName("panel_subtitle")
        layout.addWidget(subtitle)

        # ─── MASTER PROXY ON/OFF TOGGLE BAR ───────────────────────────────
        master_bar = QFrame()
        master_bar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(30, 41, 59, 0.95), stop:1 rgba(15, 23, 42, 0.95));
                border: 2px solid rgba(16, 185, 129, 0.5);
                border-radius: 10px;
                padding: 8px 14px;
            }
        """)
        mb_layout = QHBoxLayout(master_bar)
        mb_layout.setContentsMargins(8, 6, 8, 6)

        self.chk_proxy_enabled = QCheckBox("BẬT CHẾ ĐỘ PROXY (ANTI-BAN & ĐỔI IP CHO DOLA & CHROME)")
        self.chk_proxy_enabled.setStyleSheet("""
            QCheckBox {
                color: #f8fafc; font-size: 13px; font-weight: 800; letter-spacing: 0.3px;
            }
            QCheckBox::indicator {
                width: 22px; height: 22px; border-radius: 5px; border: 2px solid #10b981;
            }
            QCheckBox::indicator:checked {
                background: #10b981;
            }
        """)
        self.chk_proxy_enabled.setChecked(True)
        self.chk_proxy_enabled.toggled.connect(self._on_proxy_toggle_changed)
        mb_layout.addWidget(self.chk_proxy_enabled)
        mb_layout.addStretch()

        self.proxy_status_badge = QLabel("🟢 ĐANG BẬT PROXY")
        self.proxy_status_badge.setStyleSheet("""
            QLabel {
                background: rgba(16, 185, 129, 0.2);
                color: #34d399;
                border: 1px solid #10b981;
                border-radius: 6px;
                font-weight: 800;
                font-size: 11.5px;
                padding: 4px 12px;
            }
        """)
        mb_layout.addWidget(self.proxy_status_badge)
        layout.addWidget(master_bar)

        # ─── NGUỒN PROXY (TOOL VPN2PROXY vs PROXY NGOÀI RIÊNG) ────────────
        self.source_group = QGroupBox("CHỌN NGUỒN PROXY SỬ DỤNG")
        self.source_group.setStyleSheet("QGroupBox { font-weight: 800; color: #fbbf24; }")
        source_layout = QVBoxLayout(self.source_group)

        source_btn_row = QHBoxLayout()
        self.rb_source_vpn = QRadioButton("⚡ Nguồn: Tool VPN2proxy (WireGuard / PIA / HMA - Cổng 10000-10019)")
        self.rb_source_vpn.setStyleSheet("QRadioButton { font-weight: 700; color: #38bdf8; font-size: 12px; }")
        self.rb_source_vpn.setChecked(True)
        self.rb_source_vpn.toggled.connect(self._on_source_changed)
        source_btn_row.addWidget(self.rb_source_vpn)

        self.rb_source_custom = QRadioButton("🌐 Nguồn: Proxy Ngoài Riêng (Tự nhập HTTP / SOCKS5 / IP:Port / 5Stars)")
        self.rb_source_custom.setStyleSheet("QRadioButton { font-weight: 700; color: #a78bfa; font-size: 12px; }")
        self.rb_source_custom.toggled.connect(self._on_source_changed)
        source_btn_row.addWidget(self.rb_source_custom)
        source_btn_row.addStretch()
        source_layout.addLayout(source_btn_row)

        self.source_desc_label = QLabel("⚡ Đang dùng Proxy từ Tool VPN2proxy (KHOI_DONG_TOOL_PROXY.bat). Tự động xoay vòng cho tài khoản.")
        self.source_desc_label.setStyleSheet("color: #94a3b8; font-size: 11px; margin-top: 2px;")
        source_layout.addWidget(self.source_desc_label)
        self.chk_vpn_auto_rotate = QCheckBox('Tự động xoay IP mỗi 5 phút khi dùng VPN2Proxy')
        self.chk_vpn_auto_rotate.setChecked(True)
        self.chk_vpn_auto_rotate.setToolTip('Lưu cấu hình để áp dụng. Hub dùng chung một lịch cho mỗi cổng; chỉ báo đổi IP sau khi đo lại. Xoay tunnel có thể ngắt kết nối đang truyền dữ liệu.')
        source_layout.addWidget(self.chk_vpn_auto_rotate)
        layout.addWidget(self.source_group)

        # ─── PANEL NGUỒN 1: TOOL VPN2PROXY ───────────────────────────────
        self.vpn_panel = QFrame()
        vpn_panel_layout = QVBoxLayout(self.vpn_panel)
        vpn_panel_layout.setContentsMargins(0, 0, 0, 0)
        vpn_panel_layout.setSpacing(8)

        vpn_banner = QFrame()
        vpn_banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(16, 185, 129, 0.15), stop:1 rgba(37, 99, 235, 0.15));
                border: 1px solid rgba(16, 185, 129, 0.35);
                border-radius: 8px;
                padding: 6px 12px;
            }
        """)
        vb_layout = QHBoxLayout(vpn_banner)
        vb_layout.setContentsMargins(6, 4, 6, 4)

        self.ocproxy_status_label = QLabel("🔍 Đang kiểm tra Tool Proxy VPN (KHOI_DONG_TOOL_PROXY.bat)...")
        self.ocproxy_status_label.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")
        vb_layout.addWidget(self.ocproxy_status_label)
        vb_layout.addStretch()

        btn_sync_vpn = QPushButton("⚡ Tự Động Đồng Bộ 20 Proxy Từ Tool VPN")
        btn_sync_vpn.setFixedHeight(30)
        btn_sync_vpn.setStyleSheet("""
            QPushButton {
                background: #059669; color: white; border: 1px solid #10b981;
                border-radius: 6px; font-weight: bold; padding: 0 14px; font-size: 11.5px;
            }
            QPushButton:hover { background: #10b981; }
        """)
        btn_sync_vpn.clicked.connect(self.on_sync_from_vpn_tool)
        vb_layout.addWidget(btn_sync_vpn)

        btn_clear_vpn = QPushButton("🗑️ Xóa")
        btn_clear_vpn.setFixedHeight(30)
        btn_clear_vpn.setStyleSheet("""
            QPushButton {
                background: #374151; color: #f87171; border: 1px solid #4b5563;
                border-radius: 6px; font-weight: bold; padding: 0 10px; font-size: 11px;
            }
            QPushButton:hover { background: #ef4444; color: white; }
        """)
        btn_clear_vpn.clicked.connect(lambda: self.vpn_proxy_edit.clear())
        vb_layout.addWidget(btn_clear_vpn)
        vpn_panel_layout.addWidget(vpn_banner)

        vpn_group = QGroupBox("Danh Sách Cổng Proxy Từ Tool VPN2proxy (Cổng 10000 - 10019)")
        vpn_group_layout = QVBoxLayout(vpn_group)
        self.vpn_proxy_edit = QTextEdit()
        self.vpn_proxy_edit.setPlaceholderText(
            "# Bấm '⚡ Tự Động Đồng Bộ 20 Proxy Từ Tool VPN' ở trên hoặc dán danh sách cổng:\n"
            "127.0.0.1:10000:admin:admin123\n"
            "127.0.0.1:10001:admin:admin123\n"
            "...\n"
        )
        self.vpn_proxy_edit.setMinimumHeight(110)
        vpn_group_layout.addWidget(self.vpn_proxy_edit)
        vpn_panel_layout.addWidget(vpn_group)
        layout.addWidget(self.vpn_panel)

        # ─── PANEL NGUỒN 2: PROXY NGOÀI RIÊNG CỦA NGƯỜI DÙNG ──────────────
        self.custom_panel = QFrame()
        custom_panel_layout = QVBoxLayout(self.custom_panel)
        custom_panel_layout.setContentsMargins(0, 0, 0, 0)
        custom_panel_layout.setSpacing(8)

        custom_group = QGroupBox("Danh Sách Proxy Ngoài Riêng Của Bạn (Mỗi Dòng 1 Proxy Hoặc API Key)")
        custom_group_layout = QVBoxLayout(custom_group)
        self.custom_proxy_edit = QTextEdit()
        self.custom_proxy_edit.setPlaceholderText(
            "# HỖ TRỢ TẤT CẢ ĐỊNH DẠNG PROXY NGOÀI RIÊNG:\n"
            "# 1. Định dạng IP:Port: 123.45.67.89:8080\n"
            "# 2. Định dạng IP:Port:User:Pass: 123.45.67.89:8080:username:password\n"
            "# 3. Định dạng URL HTTP/HTTPS: http://user:pass@123.45.67.89:8080\n"
            "# 4. Định dạng SOCKS5: socks5://user:pass@123.45.67.89:1080\n"
            "# 5. API Key xoay IP: 5Stars / TM Proxy (mã 32 ký tự)\n"
        )
        self.custom_proxy_edit.setMinimumHeight(110)
        custom_group_layout.addWidget(self.custom_proxy_edit)

        custom_opts = QHBoxLayout()
        custom_opts.addWidget(QLabel("Nhà mạng (5Stars fallback):"))
        self.carrier_cb = QComboBox()
        self.carrier_cb.addItems(["random", "viettel", "vinaphone", "mobifone"])
        custom_opts.addWidget(self.carrier_cb)
        custom_opts.addSpacing(16)
        custom_opts.addWidget(QLabel("Tỉnh thành:"))
        self.province_cb = QComboBox()
        self.province_cb.addItems(["0 (Tự động)", "1", "2", "3"])
        custom_opts.addWidget(self.province_cb)
        custom_opts.addStretch()

        btn_clear_custom = QPushButton("🗑️ Xóa Proxy Ngoài")
        btn_clear_custom.setFixedHeight(28)
        btn_clear_custom.setStyleSheet("background: #374151; color: #f87171; border-radius: 4px; padding: 0 10px; font-size: 11px;")
        btn_clear_custom.clicked.connect(lambda: self.custom_proxy_edit.clear())
        custom_opts.addWidget(btn_clear_custom)
        custom_group_layout.addLayout(custom_opts)
        custom_panel_layout.addWidget(custom_group)
        layout.addWidget(self.custom_panel)

        # Mặc định ẩn custom panel nếu đang chọn vpn
        self.custom_panel.hide()

        # Anti-Ban Parameters
        ab_group = QGroupBox("Tham Số Anti-Ban")
        ab_grid = QGridLayout(ab_group)
        ab_grid.setHorizontalSpacing(16)
        ab_grid.setVerticalSpacing(10)

        ab_grid.addWidget(QLabel("Delay giữa 2 video cùng account:"), 0, 0)
        self.delay_account_spin = QSpinBox()
        self.delay_account_spin.setRange(0, 600)
        self.delay_account_spin.setValue(30)
        self.delay_account_spin.setSuffix("s")
        ab_grid.addWidget(self.delay_account_spin, 0, 1)

        ab_grid.addWidget(QLabel("Delay giữa 2 request cùng IP:"), 0, 2)
        self.delay_ip_spin = QSpinBox()
        self.delay_ip_spin.setRange(0, 120)
        self.delay_ip_spin.setValue(5)
        self.delay_ip_spin.setSuffix("s")
        ab_grid.addWidget(self.delay_ip_spin, 0, 3)

        ab_grid.addWidget(QLabel("Max video/account/ngày:"), 1, 0)
        self.max_daily_spin = QSpinBox()
        self.max_daily_spin.setRange(1, 100)
        self.max_daily_spin.setValue(4)
        ab_grid.addWidget(self.max_daily_spin, 1, 1)

        ab_grid.addWidget(QLabel("Proxy rotate mode:"), 1, 2)
        self.rotate_mode_cb = QComboBox()
        self.rotate_mode_cb.addItems([
            "Sticky per-job (giữ IP suốt 1 video)",
            "Sticky per-account (1 IP = 1 account)",
            "Rotate mỗi request",
        ])
        ab_grid.addWidget(self.rotate_mode_cb, 1, 3)

        self.chk_ua_rotate = QCheckBox("Xoay User-Agent ngẫu nhiên (Desktop UA)")
        self.chk_ua_rotate.setChecked(False)
        ab_grid.addWidget(self.chk_ua_rotate, 2, 0, 1, 2)

        self.chk_fingerprint = QCheckBox("Randomize browser fingerprint (Canvas/WebGL)")
        self.chk_fingerprint.setChecked(False)
        ab_grid.addWidget(self.chk_fingerprint, 2, 2, 1, 2)

        self.chk_auto_rotate_acc = QCheckBox("Tự động xoay account khi hết quota hàng ngày")
        self.chk_auto_rotate_acc.setChecked(True)
        ab_grid.addWidget(self.chk_auto_rotate_acc, 3, 0, 1, 2)

        layout.addWidget(ab_group)

        # Save button & Test button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_save = QPushButton("💾 Lưu Cấu Hình Proxy & Anti-Ban")
        btn_save.setObjectName("btn_primary")
        btn_save.setFixedHeight(40)
        btn_save.clicked.connect(self.on_save)
        btn_layout.addWidget(btn_save)

        self.btn_test = QPushButton("🧪 Kiểm Tra Kết Nối Proxy (Live Check)")
        self.btn_test.setFixedHeight(40)
        self.btn_test.clicked.connect(self.on_test_proxy)
        btn_layout.addWidget(self.btn_test)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

    def _on_proxy_toggle_changed(self, checked: bool):
        if getattr(self, '_config_loaded', False) and self.main_win:
            self.main_win.proxy_manager.pool.enabled = bool(checked)
            self.main_win.proxy_manager.save()
        if checked:
            self.proxy_status_badge.setText("🟢 ĐANG BẬT PROXY")
            self.proxy_status_badge.setStyleSheet("""
                QLabel {
                    background: rgba(16, 185, 129, 0.2);
                    color: #34d399;
                    border: 1px solid #10b981;
                    border-radius: 6px;
                    font-weight: 800;
                    font-size: 11.5px;
                    padding: 4px 12px;
                }
            """)
            self.source_group.setEnabled(True)
            self.vpn_panel.setEnabled(True)
            self.custom_panel.setEnabled(True)
        else:
            self.proxy_status_badge.setText("⚪ ĐANG TẮT PROXY (DÙNG MẠNG TRỰC TIẾP)")
            self.proxy_status_badge.setStyleSheet("""
                QLabel {
                    background: rgba(100, 116, 139, 0.2);
                    color: #94a3b8;
                    border: 1px solid #64748b;
                    border-radius: 6px;
                    font-weight: 800;
                    font-size: 11.5px;
                    padding: 4px 12px;
                }
            """)
            self.source_group.setEnabled(False)
            self.vpn_panel.setEnabled(False)
            self.custom_panel.setEnabled(False)

    def _on_source_changed(self):
        if self.rb_source_vpn.isChecked():
            self.vpn_panel.show()
            self.custom_panel.hide()
            self.source_desc_label.setText("⚡ Đang dùng Proxy từ Tool VPN2proxy (KHOI_DONG_TOOL_PROXY.bat). Tự động xoay vòng cho tài khoản.")
        else:
            self.vpn_panel.hide()
            self.custom_panel.show()
            self.source_desc_label.setText("🌐 Đang dùng danh sách Proxy Ngoài Riêng của bạn. Tự động chuyển tiếp qua Transparent Auth Bridge.")

    def load_config(self):
        if not self.main_win:
            return
        info = self.main_win.proxy_manager.get_pool_info()
        self.chk_vpn_auto_rotate.setChecked(bool(info.get('vpn_auto_rotate', True)))
        is_en = bool(info.get("enabled", True))
        self.chk_proxy_enabled.setChecked(is_en)
        self._on_proxy_toggle_changed(is_en)

        source = str(info.get("source", "vpn_tool"))
        if source == "custom":
            self.rb_source_custom.setChecked(True)
        else:
            self.rb_source_vpn.setChecked(True)
        self._on_source_changed()

        vpn_keys = info.get("proxies", [])
        if vpn_keys:
            self.vpn_proxy_edit.setPlainText("\n".join(vpn_keys))

        custom_keys = info.get("custom_proxies", [])
        if custom_keys:
            self.custom_proxy_edit.setPlainText("\n".join(custom_keys))

        carrier = info.get("5stars_carrier", "random")
        idx = self.carrier_cb.findText(carrier)
        if idx >= 0:
            self.carrier_cb.setCurrentIndex(idx)

        self._config_loaded = True
        self.ocproxy_status_label.setText("Đang kiểm tra VPN2Proxy…")
        def inspect_hub():
            try:
                proxies = import_from_ocproxy_hub()
                running = sum(p.get("status") == "running" for p in proxies)
                message = f"VPN2Proxy: {len(proxies)} proxy, {running} đang chạy."
            except Exception:
                message = "VPN2Proxy chưa sẵn sàng."
            self.main_win.run_on_ui(lambda: self.ocproxy_status_label.setText(message))
        threading.Thread(target=inspect_hub, name='studio-vpn-status', daemon=True).start()

    def on_sync_from_vpn_tool(self):
        proxies = import_from_ocproxy_hub()
        if not proxies:
            QMessageBox.warning(
                self,
                "Không tìm thấy Proxy",
                "Chưa tìm thấy danh sách proxy từ Tool Proxy VPN!\n"
                "Hãy đảm bảo bạn đã khởi động file:\n"
                "d:\\Proxy\\KHOI_DONG_HMA_DOC_LAP.bat\n"
                "Chỉ đồng bộ tunnel đã kết nối thành công; Docker mở chưa có nghĩa proxy đã chạy."
            )
            return

        lines = []
        details = []
        for p in proxies:
            port = p.get("port")
            user = p.get("auth_user", "")
            pass_ = p.get("auth_pass", "")
            country = p.get("country_name", "Unknown")
            flag = p.get("flag", "🌐")
            ip = p.get("real_wan_ip", "")

            if user and pass_:
                proxy_str = f"127.0.0.1:{port}:{user}:{pass_}"
            else:
                proxy_str = f"127.0.0.1:{port}"
            lines.append(proxy_str)
            details.append(f"• Cổng {port}: {flag} {country} (IP: {ip or 'đang kết nối'})")

        self.vpn_proxy_edit.setPlainText("\n".join(lines))
        self.rb_source_vpn.setChecked(True)
        self.on_save(quiet=True)
        self.ocproxy_status_label.setText(f"✅ Đã đồng bộ {len(lines)} proxy từ Tool Proxy VPN (HMA / PIA / WireGuard)!")

        detail_text = "\n".join(details[:10])
        if len(details) > 10:
            detail_text += f"\n... và {len(details) - 10} proxy khác."

        QMessageBox.information(
            self,
            "Đồng Bộ Thành Công",
            f"✅ Đã đồng bộ thành công {len(lines)} proxy từ Tool Proxy VPN vào Seedance Studio!\n\n"
            f"Danh sách vị trí quốc gia:\n{detail_text}\n\n"
            "Tất cả Chrome instances sẽ tự động đi qua các proxy này kèm cơ chế chống ban Transparent Auth Bridge!"
        )

    def on_save(self, quiet=False):
        enabled = self.chk_proxy_enabled.isChecked()
        source = "custom" if self.rb_source_custom.isChecked() else "vpn_tool"
        vpn_keys = [k.strip() for k in self.vpn_proxy_edit.toPlainText().strip().split("\n") if k.strip() and not k.startswith("#")]
        custom_keys = [k.strip() for k in self.custom_proxy_edit.toPlainText().strip().split("\n") if k.strip() and not k.startswith("#")]

        if self.main_win:
            self.main_win.proxy_manager.update_pool(
                proxies=vpn_keys,
                carrier=self.carrier_cb.currentText(),
                province="0",
                enabled=enabled,
                source=source,
                custom_proxies=custom_keys,
                vpn_auto_rotate=self.chk_vpn_auto_rotate.isChecked()
            )
            if not quiet:
                status_str = "BẬT" if enabled else "TẮT"
                source_str = "Tool VPN2proxy" if source == "vpn_tool" else "Proxy Ngoài Riêng"
                msg = f"Đã lưu thành công cấu hình Proxy!\n\n• Trạng thái: {status_str}\n• Nguồn hoạt động: {source_str}\n• Proxy VPN: {len(vpn_keys)} cổng\n• Proxy Ngoài: {len(custom_keys)} proxy"
                self.main_win.log(f"Đã lưu Proxy: [{status_str}] - Nguồn: {source_str}")
                QMessageBox.information(self, "Lưu Thành Công", msg)

    def on_test_proxy(self):
        source = "custom" if self.rb_source_custom.isChecked() else "vpn_tool"
        if source == "custom":
            raw_text = self.custom_proxy_edit.toPlainText().strip()
            source_label = "Proxy Ngoài Riêng"
        else:
            raw_text = self.vpn_proxy_edit.toPlainText().strip()
            source_label = "Tool VPN2proxy"

        lines = [k.strip() for k in raw_text.split("\n") if k.strip() and not k.startswith("#")]
        if not lines:
            QMessageBox.warning(self, "Chưa có Proxy", f"Vui lòng nhập hoặc đồng bộ ít nhất 1 proxy trong mục '{source_label}' để kiểm tra.")
            return

        self.btn_test.setEnabled(False)
        self.btn_test.setText("⏳ Đang kiểm tra kết nối...")

        def _run_test():
            import asyncio
            async def _check_all():
                results = []
                pm = self.main_win.proxy_manager if self.main_win else ProxyManager()
                for proxy_str in lines[:10]:
                    res = await pm.test_proxy(proxy_str)
                    results.append((proxy_str, res))
                return results

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(_check_all())
            finally:
                loop.close()

            def _show_result():
                self.btn_test.setEnabled(True)
                self.btn_test.setText("🧪 Kiểm Tra Kết Nối Proxy (Live Check)")
                
                success_count = sum(1 for _, r in results if r.get("success"))
                lines_msg = []
                for proxy_str, r in results:
                    if r.get("success"):
                        lines_msg.append(f"✅ {proxy_str} -> IP: {r.get('ip')} ({r.get('latency_ms')}ms)")
                    else:
                        lines_msg.append(f"❌ {proxy_str} -> Lỗi: {r.get('error', 'Timeout')}")

                proxy_state = "ĐANG BẬT" if self.chk_proxy_enabled.isChecked() else "ĐANG TẮT (Chỉ kiểm tra thử)"
                msg = f"Kết quả kiểm tra [{source_label}] ({success_count}/{len(results)} proxy hoạt động):\n(Trạng thái hệ thống: {proxy_state})\n\n" + "\n".join(lines_msg)
                if len(lines) > 10:
                    msg += f"\n\n(Chỉ hiển thị mẫu 10/{len(lines)} proxy)"
                QMessageBox.information(self, f"Kết Quả Kiểm Tra Proxy - {source_label}", msg)

            QTimer.singleShot(0, _show_result)

        threading.Thread(target=_run_test, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 6: CÀI ĐẶT
# ═══════════════════════════════════════════════════════════════════════════════

class SettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        title = QLabel("Cài Đặt Hệ Thống")
        title.setObjectName("panel_title")
        layout.addWidget(title)

        info_group = QGroupBox("Thông Tin Hệ Thống")
        info_grid = QGridLayout(info_group)
        info_grid.setHorizontalSpacing(16)
        info_grid.setVerticalSpacing(8)

        items = [
            ("Chrome:", CHROME_PATH or "Không tìm thấy!", bool(CHROME_PATH)),
            ("Extension:", EXTENSION_DIR if os.path.isdir(EXTENSION_DIR) else "Không tìm thấy!", os.path.isdir(EXTENSION_DIR)),
            ("Output dir:", OUTPUT_DIR, True),
            ("Data dir:", DATA_DIR, True),
            ("API Server:", f"http://{API_HOST}:{API_PORT}", True),
            ("PyQt6:", "✅ Đã cài đặt", True),
        ]

        for row, (label, value, ok) in enumerate(items):
            info_grid.addWidget(QLabel(label), row, 0)
            val_label = QLabel(value)
            val_label.setObjectName("label_success" if ok else "label_error")
            val_label.setWordWrap(True)
            info_grid.addWidget(val_label, row, 1)

        layout.addWidget(info_group)

        # Open folders
        btn_layout = QHBoxLayout()
        btn_output = QPushButton("📂 Mở thư mục Output")
        btn_output.clicked.connect(lambda: os.startfile(OUTPUT_DIR) if os.path.isdir(OUTPUT_DIR) else None)
        btn_layout.addWidget(btn_output)
        btn_data = QPushButton("📂 Mở thư mục Data")
        btn_data.clicked.connect(lambda: os.startfile(DATA_DIR) if os.path.isdir(DATA_DIR) else None)
        btn_layout.addWidget(btn_data)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class SeedanceMainWindow(QMainWindow):
    """Cửa sổ chính của ứng dụng Seedance AI Video Studio."""

    sig_log = pyqtSignal(str)
    sig_call = pyqtSignal(object)   # Chạy callable trên UI thread (an toàn từ thread nền)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Seedance AI Video Studio PRO v{APP_VERSION} - Dola 30s Bypass Pro | Tác giả: LÊ VIỆT TÙNG (Zalo: 0915967790)")
        self.setMinimumSize(1100, 750)
        self.resize(1280, 850)

        # ─── Backend Managers ─────────────────────────────────────
        self.account_manager = AccountManager()
        self.proxy_manager = ProxyManager()
        self.job_manager = JobManager()
        self.session_store = SessionStore()
        self.chrome_processes: dict = {}

        # WorkerPool for video generation
        from worker_pool import WorkerPool, VideoJob
        self._worker_pool: Optional[WorkerPool] = None
        self._pool_thread: Optional[threading.Thread] = None
        self._pool_loop: Optional[object] = None  # asyncio event loop

        # ─── Load QSS ────────────────────────────────────────────
        qss_path = os.path.join(os.path.dirname(__file__), "style.qss")
        if os.path.isfile(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

        # ─── Central Widget ──────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ─── Sidebar ─────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        logo = QLabel("🎬 SEEDANCE DOLA")
        logo.setObjectName("sidebar_logo")
        sidebar_layout.addWidget(logo)

        version = QLabel(f"PRO v{APP_VERSION} • Bypass 30s")
        version.setObjectName("sidebar_version")
        sidebar_layout.addWidget(version)

        tag_author = QLabel("BẢN QUYỀN: LÊ VIỆT TÙNG")
        tag_author.setStyleSheet("color: #fbbf24; font-size: 10px; font-weight: 750; padding: 2px 14px; margin-bottom: 4px;")
        sidebar_layout.addWidget(tag_author)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("nav_list")
        for icon, text in NAV_ITEMS:
            item = QListWidgetItem(f"{icon}  {text}")
            item.setSizeHint(QSize(180, 40))
            self.nav_list.addItem(item)
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        sidebar_layout.addWidget(self.nav_list)

        sidebar_layout.addStretch()

        # Author contact card in sidebar footer
        author_card = QFrame()
        author_card.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.85);
                border-top: 1px solid rgba(251, 191, 36, 0.25);
                padding: 10px 12px;
            }
        """)
        ac_layout = QVBoxLayout(author_card)
        ac_layout.setContentsMargins(4, 6, 4, 6)
        ac_layout.setSpacing(3)
        
        lbl_dev_title = QLabel("👨‍💻 <b>LÊ VIỆT TÙNG</b>")
        lbl_dev_title.setStyleSheet("color: #f8fafc; font-size: 11px;")
        lbl_dev_zalo = QLabel("💬 Zalo: <span style='color:#38bdf8; font-weight:bold;'>0915967790</span>")
        lbl_dev_zalo.setStyleSheet("color: #cbd5e1; font-size: 10px;")
        lbl_dev_fb = QLabel("🌐 FB: Lê Việt Tùng")
        lbl_dev_fb.setStyleSheet("color: #94a3b8; font-size: 9.5px;")
        
        ac_layout.addWidget(lbl_dev_title)
        ac_layout.addWidget(lbl_dev_zalo)
        ac_layout.addWidget(lbl_dev_fb)
        sidebar_layout.addWidget(author_card)

        main_layout.addWidget(sidebar)

        # ─── Content Stack ───────────────────────────────────────
        content_wrapper = QWidget()
        content_wrapper.setObjectName("content_area")
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.dashboard_panel = DashboardPanel(self)
        self.create_panel = CreateVideoPanel(self)
        self.gallery_panel = VideoGalleryPanel(self)
        self.accounts_panel = AccountsPanel(self)
        self.proxy_panel = ProxyPanel(self)
        self.settings_panel = SettingsPanel(self)

        self.stack.addWidget(self.dashboard_panel)
        self.stack.addWidget(self.create_panel)
        self.stack.addWidget(self.gallery_panel)
        self.stack.addWidget(self.accounts_panel)
        self.stack.addWidget(self.proxy_panel)
        self.stack.addWidget(self.settings_panel)

        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_wrapper)

        # ─── Status Bar ──────────────────────────────────────────
        status = self.statusBar()
        chrome_ok = bool(CHROME_PATH)
        ext_ok = os.path.isdir(EXTENSION_DIR)
        accs = self.account_manager.get_all()

        status.addWidget(QLabel(f"  Chrome: {'✅ OK' if chrome_ok else '❌'}  "))
        status.addWidget(QLabel(f"  Extension: {'✅ OK' if ext_ok else '❌'}  "))
        self.status_api_label = QLabel(f"  API: :{API_PORT} ⏳  ")
        status.addWidget(self.status_api_label)
        self.status_accounts_label = QLabel(f"  Accounts: {len(accs)}  ")
        status.addWidget(self.status_accounts_label)

        # ─── Signals ─────────────────────────────────────────────
        self.sig_log.connect(self._on_log)
        self.sig_call.connect(self._on_call)

        # ─── Init data ──────────────────────────────────────────
        self.dashboard_panel.refresh_stats()
        self.accounts_panel.refresh_table()
        self.create_panel.refresh_accounts()
        self.proxy_panel.load_config()

        # ─── API Server ──────────────────────────────────────────
        self._start_api_server()

        # ─── Refresh timer (1s cho live ticker tiến trình video) ─────
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._periodic_refresh)
        self.refresh_timer.start(1000)

    # ─── Navigation ───────────────────────────────────────────────

    def _on_nav_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.dashboard_panel.refresh_stats()
        elif index == 1:
            self.create_panel.refresh_accounts()
        elif index == 2:
            self.gallery_panel.refresh_gallery()
        elif index == 3:
            self.accounts_panel.refresh_table()

    def _periodic_refresh(self):
        accs = self.account_manager.get_all()
        self.status_accounts_label.setText(f"  Accounts: {len(accs)}  ")

        # Cập nhật live tracking thời gian thực nếu WorkerPool đang tồn tại
        if self._worker_pool:
            try:
                status = self._worker_pool.get_status()
                self.create_panel.update_fast_tracking(status)
                self.dashboard_panel.update_dashboard_live(status)
            except Exception:
                pass

        # Tự động quét và lưu session cho các Chrome đang mở mỗi 3 giây
        self._auto_scan_ticker = getattr(self, "_auto_scan_ticker", 0) + 1
        if self._auto_scan_ticker >= 15:
            self._auto_scan_ticker = 0
            self.scan_and_auto_save_all_running()

    # ─── Logging ──────────────────────────────────────────────────

    def log(self, msg: str):
        self.sig_log.emit(msg)

    @pyqtSlot(str)
    def _on_log(self, msg: str):
        self.dashboard_panel.console.append_log(msg)

    def run_on_ui(self, fn):
        """Đưa 1 callable về chạy trên UI thread (gọi được từ thread nền)."""
        self.sig_call.emit(fn)

    @pyqtSlot(object)
    def _on_call(self, fn):
        try:
            fn()
        except Exception as e:
            self.dashboard_panel.console.append_log(f"[UI] Lỗi cập nhật giao diện: {e}")

    # ─── Account Actions ─────────────────────────────────────────

    def add_account_dialog(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Thêm Account Mới")
        dlg.setFixedSize(400, 200)
        form = QFormLayout(dlg)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("vd: fb01, gg01, via_xxx...")
        form.addRow("Tên Account:", name_edit)

        type_cb = QComboBox()
        type_cb.addItems(["facebook", "google", "tiktok"])
        form.addRow("Loại đăng nhập:", type_cb)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            name = name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên account!")
                return
            try:
                self.account_manager.add_account(name=name, login_type=type_cb.currentText())
                self.accounts_panel.refresh_table()
                self.create_panel.refresh_accounts()
                self.log(f"Đã thêm account: {name}")
            except ValueError as e:
                QMessageBox.warning(self, "Lỗi", str(e))

    def open_clean_chrome_manual_login(self, google=False):
        """Mở 1 Chrome sạch (profile tạm) để người dùng tự đăng nhập Dola, xong lưu cookies thành tài khoản."""
        dialogs = getattr(self, "_manual_login_dialogs", [])
        # Giữ tham chiếu tới khi luồng nền kết thúc (tránh bị GC khi còn emit signal)
        dialogs = [d for d in dialogs if not (d._worker_done and not d.isVisible())]
        dlg = ManualLoginDialog(self, self, google=google)
        dialogs.append(dlg)
        self._manual_login_dialogs = dialogs
        dlg.show()
        if not google:
            dlg.start()

    def open_chrome_for_account(self, name: str):
        """Keep process discovery and proxy setup off the Qt event loop."""
        opening = getattr(self, '_opening_accounts', None)
        if opening is None:
            self._opening_accounts = opening = set()
        if name in opening:
            return
        opening.add(name)
        def work():
            try:
                self._open_chrome_for_account_background(name)
            except Exception as exc:
                self.sig_log.emit(f"Không mở được Chrome '{name}': {exc}")
            finally:
                self.run_on_ui(lambda: opening.discard(name))
        threading.Thread(target=work, name='studio-open-account', daemon=True).start()

    def _open_chrome_for_account_background(self, name: str):
        chrome_path = CHROME_PATH
        if not chrome_path or not os.path.isfile(chrome_path):
            self.run_on_ui(lambda: QMessageBox.critical(self, "Lỗi", "Không tìm thấy Chrome!"))
            return

        profile_dir = os.path.join(CHROME_USER_DATA_BASE, name)
        os.makedirs(profile_dir, exist_ok=True)

        from browser_manager import BrowserManager
        bm = BrowserManager()
        port = bm._get_port(name)

        # 1. Cấu hình sẵn Preferences: ghim icon Extension lên toolbar, bật Developer Mode
        bm.ensure_profile_preferences(profile_dir)

        # 2. Kiểm tra xem Chrome cho account này đã đang chạy chưa
        already_running = False
        acc = self.account_manager.get_account(name)
        saved_proxy = (acc.proxy or acc.proxy_direct) if acc else ''
        account_proxy = self.proxy_manager.select_profile_proxy(name, saved_proxy)
        if account_proxy and self.proxy_manager.pool.source == 'vpn_tool':
            from vpn_bootstrap import ensure_vpn_hub
            ensure_vpn_hub()
        if self.proxy_manager.is_enabled and not account_proxy:
            raise RuntimeError('Chế độ VPN2Proxy đang bật nhưng chưa có proxy được cấu hình; không mở bằng mạng trực tiếp.')
        if acc and account_proxy and acc.proxy != account_proxy:
            acc.proxy = account_proxy
            self.account_manager.save()
        import psutil
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if "chrome" in (p.info["name"] or "").lower():
                    cmdline = " ".join(p.info["cmdline"] or [])
                    if f"--remote-debugging-port={port}" in cmdline:
                        already_running = True
                        break
            except Exception:
                pass

        if not already_running:
            cmd = [
                chrome_path,
                f"--remote-debugging-port={port}",
                f"--remote-debugging-address=127.0.0.1",
                f"--user-data-dir={profile_dir}",
                "--profile-directory=Default",
                "--lang=vi",
                "--window-position=100,80", "--window-size=1280,900",
            ]
            cmd.extend(CHROME_FLAGS)
            if os.path.isdir(EXTENSION_DIR):
                ext_path = EXTENSION_DIR.replace(chr(92), '/')
                cmd.append(f"--load-extension={ext_path}")
            acc = self.account_manager.get_account(name)
            if self.proxy_manager.is_enabled:
                if account_proxy:
                    chrome_proxy, _ = self.proxy_manager.bridge_mgr.prepare_chrome_proxy_sync(
                        account_proxy, session_key=f"gui_acc_{name}"
                    )
                    if chrome_proxy:
                        cmd.append(f"--proxy-server={chrome_proxy}")
            else:
                cmd.append("--no-proxy-server")
                self.log(f"🌐 Chế độ Proxy đang TẮT — Mở Chrome '{name}' bằng MẠNG TRỰC TIẾP (Direct IP).")
            cmd.extend([DOLA_URL])

            from browser_capacity import reserve_browser, browser_started, release_reservation
            reserve_browser(profile_dir)
            try:
                proc = subprocess.Popen(cmd)
                browser_started(profile_dir, proc.pid)
                self.chrome_processes[name] = proc
                self.log(f"Chrome đã mở cho '{name}' (port={port})")
            except Exception as e:
                release_reservation(profile_dir)
                self.run_on_ui(lambda message=str(e): QMessageBox.critical(self, "Lỗi", message))
                return
        else:
            self.log(f"Chrome cho '{name}' đang hoạt động sẵn trên port={port} — Đang kiểm tra tab Extension...")

        # Khởi chạy background watcher: Nạp Extension qua CDP, mở tab popup.html, nạp cookies & tự động lưu khi login Dola
        acc = self.account_manager.get_account(name)
        def _watch_and_auto_save():
            import asyncio, urllib.request
            time.sleep(2.0)

            # 1. Nạp Extension qua CDP, mở tab Extension UI, nạp FB/Dola session
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                async def _inject():
                    from playwright.async_api import async_playwright
                    pw_instance = await async_playwright().start()
                    try:
                        browser = None
                        for attempt in range(8):
                            try:
                                browser = await pw_instance.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                                break
                            except Exception:
                                await asyncio.sleep(1.0)
                        if not browser:
                            return
                        ctx = browser.contexts[0] if browser.contexts else None
                        if not ctx:
                            return

                        # A. Nạp Unpacked Extension qua CDP & mở tab Extension UI popup.html
                        ext_id = None
                        if os.path.isdir(EXTENSION_DIR):
                            try:
                                cdp = await browser.new_browser_cdp_session()
                                ext_abs = os.path.abspath(EXTENSION_DIR)
                                res = await cdp.send("Extensions.loadUnpacked", {"path": ext_abs})
                                ext_id = res.get("id") or "mikgdpblejoompnjdbmdpgicgikmblcn"
                                self.sig_log.emit(f"✅ Đã nạp Extension Studio Pro cho '{name}' qua CDP (ID: {ext_id})")
                            except Exception as ex:
                                self.sig_log.emit(f"⚠️ CDP load extension note: {ex}")

                        if ext_id:
                            popup_url = f"chrome-extension://{ext_id}/popup.html"
                            already_popup = any(popup_url in p.url for p in ctx.pages)
                            ext_p = None
                            if not already_popup:
                                try:
                                    ext_p = await ctx.new_page()
                                    await ext_p.goto(popup_url)
                                    self.sig_log.emit(f"🚀 Đã mở tab Extension Studio Pro sẵn sàng điều khiển!")
                                except Exception as ex:
                                    self.sig_log.emit(f"Mở tab extension note: {ex}")
                            else:
                                for p in ctx.pages:
                                    if popup_url in p.url:
                                        ext_p = p
                                        break

                            # Đồng bộ cấu hình proxy vào extension storage của profile này
                            if self.proxy_manager.is_enabled and account_proxy and ext_p:
                                from proxy_manager import parse_proxy_spec
                                spec = parse_proxy_spec(account_proxy)
                                if spec:
                                    try:
                                        u = spec.get('user', '')
                                        p = spec.get('pass', '')
                                        h = spec.get('host', '127.0.0.1')
                                        port_num = int(spec.get('port', 10000))
                                        sch = spec.get('scheme', 'http')
                                        await ext_p.evaluate('''async ({config, rotate}) => {
                                            await chrome.storage.local.set({dola_vpn_auto_rotate: rotate});
                                            const reply = await new Promise(resolve => chrome.runtime.sendMessage(
                                                {action: 'SET_EXTENSION_PROXY', config}, resolve));
                                            if (!reply || !reply.ok) throw new Error('Extension không áp dụng được proxy.');
                                        }''', {'config': {'enabled': True, 'host': h, 'port': port_num,
                                            'username': u, 'password': p, 'scheme': sch,
                                            'account_name': name, 'raw_proxy': account_proxy,
                                            'source': self.proxy_manager.pool.source},
                                            'rotate': self.proxy_manager.pool.vpn_auto_rotate})
                                    except Exception as error:
                                        self.sig_log.emit(f'Không đồng bộ được proxy extension: {error}')
                            elif not self.proxy_manager.is_enabled and ext_p:
                                try:
                                    clear_js = """
                                    await chrome.storage.local.set({
                                        dola_proxy_enabled: false,
                                        dola_proxy_config: { enabled: false }
                                    });
                                    if (chrome.proxy && chrome.proxy.settings) {
                                        await chrome.proxy.settings.set({
                                            value: {mode: 'direct'}, scope: 'regular'
                                        });
                                    }
                                    """
                                    await ext_p.evaluate('async () => {' + clear_js + '}')
                                except Exception:
                                    pass

                        # B. Đảm bảo tab Dola mở
                        dola_page = None
                        for p in ctx.pages:
                            if "dola.com" in p.url or "doubao.com" in p.url:
                                dola_page = p
                                break
                        if not dola_page:
                            dola_page = ctx.pages[0] if ctx.pages else await ctx.new_page()

                        # C. Nạp FB cookies nếu có
                        if acc and acc.fb_cookies:
                            from account_manager import parse_via_cookie_string
                            fb_parsed = parse_via_cookie_string(acc.fb_cookies)
                            if fb_parsed:
                                try:
                                    await ctx.add_cookies(fb_parsed)
                                    self.sig_log.emit(f"[OK] Đã nạp FB cookies cho '{name}' vào Chrome!")
                                except Exception:
                                    pass

                        # Preserve a newer live login; never overwrite it with stale cookies.
                        from dola_session_health import restore_account_session
                        valid = await restore_account_session(
                            dola_page, self.session_store, name, self.sig_log.emit)
                        if acc:
                            acc.login_status = 'logged_in' if valid else 'login_required'
                            acc.session_health = 100.0 if valid else 0.0
                            acc.last_check_time = time.time()
                            self.account_manager.save()
                        self.run_on_ui(self.accounts_panel.refresh_table)
                    finally:
                        await pw_instance.stop()

                loop.run_until_complete(_inject())
                loop.close()
            except Exception as e:
                self.sig_log.emit(f"[!] Setup tương tác Chrome: {e}")

            # 2. Vòng lặp giám sát: Tự động phát hiện khi login Dola và lưu session ngay
            self.sig_log.emit(f"👀 Đang giám sát Chrome '{name}' — Sẽ tự động lưu Cookies Dola ngay khi đăng nhập!")
            max_cycles = 180  # 180 x 2.5s = ~7.5 phút
            for _ in range(max_cycles):
                time.sleep(2.5)
                try:
                    req = urllib.request.Request(f"http://127.0.0.1:{port}/json/version", headers={"User-Agent": "Mozilla/5.0"})
                    urllib.request.urlopen(req, timeout=1.0)
                except Exception:
                    break

                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    async def _check_and_save():
                        from playwright.async_api import async_playwright
                        pw_instance = await async_playwright().start()
                        try:
                            browser = await pw_instance.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                            ctx = browser.contexts[0] if browser.contexts else None
                            if not ctx:
                                return False
                            cookies = await ctx.cookies()
                            dola_cookies = [c for c in cookies if "dola" in c.get("domain", "").lower()]
                            auth_cookies = [c for c in dola_cookies if c.get("name") in ("sessionid", "sessionid_ss", "uid_tt", "uid_tt_ss", "sid_tt")]

                            if auth_cookies or len(dola_cookies) >= 8:
                                dola_page = None
                                for p in ctx.pages:
                                    if "dola.com" in p.url:
                                        dola_page = p
                                        break
                                ls = {}
                                if dola_page:
                                    try:
                                        ls = await dola_page.evaluate("() => ({ ...localStorage })")
                                    except Exception:
                                        pass

                                from fb_login_automation import FBLoginAutomation
                                if not dola_page or not await FBLoginAutomation()._check_dola_logged_in(dola_page):
                                    return False
                                self.session_store.save_session(name, cookies, ls)
                                acc_obj = self.account_manager.get_account(name)
                                if acc_obj:
                                    acc_obj.dola_session_saved = True
                                    acc_obj.login_status = "logged_in"
                                    acc_obj.session_count = len(dola_cookies)
                                    self.account_manager.save()

                                self.sig_log.emit(f"🎉 [TỰ ĐỘNG] Đã nhận diện & lưu thành công Session Dola cho '{name}' ({len(dola_cookies)} cookies)!")
                                self.run_on_ui(self.accounts_panel.refresh_table)
                                self.run_on_ui(self.create_panel.refresh_accounts)
                                return True
                            return False
                        finally:
                            await pw_instance.stop()

                    saved = loop.run_until_complete(_check_and_save())
                    loop.close()
                    if saved:
                        break
                except Exception:
                    pass

        threading.Thread(target=_watch_and_auto_save, daemon=True).start()

    def save_session_for_account(self, name: str):
        def do_extract():
            try:
                import asyncio
                from browser_manager import BrowserManager
                bm = BrowserManager()
                ss = self.session_store
                port = bm._get_port(name)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def _extract():
                    from playwright.async_api import async_playwright
                    pw_instance = await async_playwright().start()
                    try:
                        browser = await pw_instance.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                        ctx = browser.contexts[0] if browser.contexts else None
                        if not ctx:
                            self.sig_log.emit(f"⚠️ Không tìm thấy context trình duyệt trên port {port}")
                            return

                        cookies = await ctx.cookies()
                        dola_page = None
                        for p in ctx.pages:
                            if "dola.com" in p.url:
                                dola_page = p
                                break
                        ls = {}
                        if dola_page:
                            try:
                                ls = await dola_page.evaluate("() => ({ ...localStorage })")
                            except Exception:
                                pass

                        ss.save_session(name, cookies, ls)
                        acc = self.account_manager.get_account(name)
                        if acc:
                            acc.dola_session_saved = True
                            acc.login_status = "logged_in"
                            dola_c = [c for c in cookies if 'dola' in c.get('domain', '')]
                            acc.session_count = len(dola_c)
                            self.account_manager.save()

                        self.sig_log.emit(f"🎉 Đã lưu Session Dola cho '{name}' ({len(cookies)} cookies)")
                    finally:
                        # Tuyệt đối KHÔNG đóng browser!
                        await pw_instance.stop()

                loop.run_until_complete(_extract())
                loop.close()

                # Refresh UI on main thread
                QTimer.singleShot(0, self.accounts_panel.refresh_table)
                QTimer.singleShot(0, self.create_panel.refresh_accounts)
            except Exception as e:
                self.sig_log.emit(f"⚠️ Lỗi lưu session '{name}': {e}")

        threading.Thread(target=do_extract, daemon=True).start()
        self.log(f"Đang trích xuất session cho '{name}'...")

    def scan_and_auto_save_all_running(self, force_scan: bool = False):
        """Tự động quét các Chrome đang mở trên máy, nhận diện login Dola và lưu session."""
        if getattr(self, "_is_scanning_sessions", False):
            return
        self._is_scanning_sessions = True

        def _do_scan():
            try:
                import psutil, re, urllib.request, asyncio
                from playwright.async_api import async_playwright

                active_ports = {}
                for p in psutil.process_iter(["pid", "name", "cmdline"]):
                    try:
                        if "chrome" in (p.info["name"] or "").lower():
                            cmd = " ".join(p.info["cmdline"] or [])
                            if "--remote-debugging-port=" in cmd and "--user-data-dir=" in cmd:
                                m_port = re.search(r'--remote-debugging-port=(\d+)', cmd)
                                m_user = re.search(r'--user-data-dir=([^\s]+)', cmd)
                                if m_port and m_user:
                                    port = int(m_port.group(1))
                                    udir = m_user.group(1).rstrip('/\\')
                                    acc_name = udir.split('\\')[-1].split('/')[-1]
                                    if acc_name and acc_name not in active_ports:
                                        active_ports[acc_name] = port
                    except Exception:
                        pass

                if not active_ports:
                    if force_scan:
                        self.sig_log.emit("ℹ️ Không tìm thấy cửa sổ Chrome nào đang mở có debug port.")
                    return

                for name, port in active_ports.items():
                    acc = self.account_manager.get_account(name)
                    if not acc:
                        continue

                    # Nếu không ép buộc quét, bỏ qua các acc đã lưu session hợp lệ
                    if not force_scan:
                        if self.session_store.has_session(name) and acc.dola_session_saved:
                            continue

                    try:
                        req = urllib.request.Request(f"http://127.0.0.1:{port}/json/version", headers={"User-Agent": "Mozilla/5.0"})
                        urllib.request.urlopen(req, timeout=1.0)
                    except Exception:
                        continue

                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        async def _scan_one(acc_name, p):
                            pw_instance = await async_playwright().start()
                            try:
                                browser = await pw_instance.chromium.connect_over_cdp(f"http://127.0.0.1:{p}")
                                ctx = browser.contexts[0] if browser.contexts else None
                                if not ctx:
                                    return
                                cookies = await ctx.cookies()
                                dola_cookies = [c for c in cookies if "dola" in c.get("domain", "").lower()]
                                auth_cookies = [c for c in dola_cookies if c.get("name") in ("sessionid", "sessionid_ss", "uid_tt", "uid_tt_ss", "sid_tt")]
                                if auth_cookies or len(dola_cookies) >= 8:
                                    dola_page = None
                                    for pg in ctx.pages:
                                        if "dola.com" in pg.url:
                                            dola_page = pg
                                            break
                                    ls = {}
                                    if dola_page:
                                        try:
                                            ls = await dola_page.evaluate("() => ({ ...localStorage })")
                                        except Exception:
                                            pass
                                    from fb_login_automation import FBLoginAutomation
                                    if not dola_page or not await FBLoginAutomation()._check_dola_logged_in(dola_page):
                                        return
                                    self.session_store.save_session(acc_name, cookies, ls)
                                    a = self.account_manager.get_account(acc_name)
                                    if a:
                                        a.dola_session_saved = True
                                        a.login_status = "logged_in"
                                        a.session_count = len(dola_cookies)
                                        self.account_manager.save()
                                    self.sig_log.emit(f"🎉 [QUÉT TỰ ĐỘNG] Đã lưu Session Dola cho '{acc_name}' ({len(dola_cookies)} cookies)!")
                                    self.run_on_ui(self.accounts_panel.refresh_table)
                                    self.run_on_ui(self.create_panel.refresh_accounts)
                            finally:
                                await pw_instance.stop()

                        loop.run_until_complete(_scan_one(name, port))
                        loop.close()
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                self._is_scanning_sessions = False

        threading.Thread(target=_do_scan, daemon=True).start()

    def inject_cookie_dialog(self, name: str):
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Nạp Cookie FB VIA cho '{name}'")
        dlg.setFixedSize(500, 300)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("Dán chuỗi Cookie FB VIA:"))
        cookie_edit = QTextEdit()
        cookie_edit.setPlaceholderText("c_user=xxx; xs=xxx; fr=xxx; datr=xxx; sb=xxx")
        layout.addWidget(cookie_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            raw = cookie_edit.toPlainText().strip()
            if raw:
                acc = self.account_manager.get_account(name)
                if acc:
                    acc.fb_cookies = raw[:500]
                    self.account_manager.save()
                self.accounts_panel.refresh_table()
                self.log(f"Đã nạp Cookie FB cho '{name}'")

    def delete_account(self, name: str):
        reply = QMessageBox.question(
            self, "Xác nhận", f"Xóa account '{name}'?\nProfile Chrome sẽ được giữ lại.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if name in self.chrome_processes:
                proc = self.chrome_processes[name]
                if proc and proc.poll() is None:
                    proc.terminate()
                del self.chrome_processes[name]
            self.account_manager.delete_account(name)
            self.accounts_panel.refresh_table()
            self.create_panel.refresh_accounts()
            self.log(f"Đã xóa account: {name}")

    def bulk_import_dialog(self):
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Import Hàng Loạt VIA Cookies → Auto Login Dola")
        dlg.setMinimumSize(600, 400)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("Dán danh sách VIA cookies (mỗi dòng 1 account) hoặc chọn file .txt:"))
        via_edit = QTextEdit()
        via_edit.setPlaceholderText(
            "# Format: uid|password|2fa|cookie_string\n"
            "# Hoặc: cookie_string (c_user=...; xs=...)\n"
        )
        layout.addWidget(via_edit)

        btn_file = QPushButton("📂 Chọn File .txt")
        def load_file():
            fp, _ = QFileDialog.getOpenFileName(dlg, "Chọn file VIA", "", "Text files (*.txt);;All files (*.*)")
            if fp:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    via_edit.setPlainText(f.read())
        btn_file.clicked.connect(load_file)
        layout.addWidget(btn_file)

        progress = QProgressBar()
        layout.addWidget(progress)

        status = QLabel("Sẵn sàng")
        status.setObjectName("label_dim")
        layout.addWidget(status)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("🚀 Bắt Đầu Import")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            raw = via_edit.toPlainText().strip()
            lines = [l for l in raw.split("\n") if l.strip() and not l.startswith("#")]
            if lines:
                self.log(f"Import {len(lines)} tài khoản VIA...")
                # TODO: Wire up BulkImporter async
                QMessageBox.information(self, "Import", f"Đã nhận {len(lines)} dòng VIA.\nĐang xử lý...")

    def import_dola_cookies_dialog(self):
        """Dialog paste cookies Dola từ Extension vào Tool (Hỗ trợ ĐƠN và SLL HÀNG LOẠT)."""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox

        dlg = QDialog(self)
        dlg.setWindowTitle("Import Cookies Dola / SLL Hàng Loạt")
        dlg.setMinimumSize(680, 560)
        layout = QVBoxLayout(dlg)

        # Instructions
        instructions = QLabel(
            "📋 <b>Hướng dẫn Import Cookies Dola (Hỗ trợ 1 hoặc SLL nhiều tài khoản):</b><br/>"
            "• <b>1 Tài khoản đơn:</b> Nhập Tên Account bên dưới và paste JSON cookies / chuỗi cookie.<br/>"
            "• <b>SLL Nhiều tài khoản cùng lúc:</b> Để trống ô Tên Account và paste theo định dạng:<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<code>tentaikhoan1:</code><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<code>[ { \"name\": \"...\", \"value\": \"...\" }, ... ]</code><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<code>tentaikhoan2:</code><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<code>[ { \"name\": \"...\", \"value\": \"...\" }, ... ]</code><br/>"
            "💡 <i>Hoặc bấm '📂 Tải từ File .txt / .json' để nạp danh sách lớn.</i>"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 10px; background: #1a2745; border-radius: 8px; font-size: 12px; line-height: 1.4;")
        layout.addWidget(instructions)

        # Account name (optional if pasting multiple accounts)
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Tên Account (nếu tạo 1 acc đơn):"))
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("vd: dola_01 (để trống nếu dán nhiều acc dạng ten_acc: [...])")
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)

        # Cookie textarea
        layout.addWidget(QLabel("Dán Cookies Dola (1 tài khoản hoặc nhiều tài khoản SLL):"))
        cookie_edit = QTextEdit()
        cookie_edit.setPlaceholderText(
            "Ví dụ 1 account:\n"
            "[\n"
            "  {\"name\": \"passport_csrf_token\", \"value\": \"abc123\", ...},\n"
            "  {\"name\": \"sessionid\", \"value\": \"xyz456\", ...}\n"
            "]\n\n"
            "Ví dụ nhiều account SLL:\n"
            "leviettung04:\n"
            "[\n"
            "  {\"name\": \"sessionid\", \"value\": \"...\", ...}\n"
            "]\n\n"
            "tungkyluatbanthan:\n"
            "[\n"
            "  {\"name\": \"sessionid\", \"value\": \"...\", ...}\n"
            "]"
        )
        layout.addWidget(cookie_edit)

        # File load button
        file_btn_layout = QHBoxLayout()
        btn_load_file = QPushButton("📂 Tải từ File .txt / .json")
        def _on_load_cookie_file():
            fp, _ = QFileDialog.getOpenFileName(dlg, "Chọn file Cookies", "", "Text/JSON (*.txt *.json);;All files (*.*)")
            if fp:
                try:
                    with open(fp, "r", encoding="utf-8", errors="replace") as f:
                        cookie_edit.setPlainText(f.read())
                except Exception as e:
                    QMessageBox.warning(dlg, "Lỗi", f"Không đọc được file: {e}")
        btn_load_file.clicked.connect(_on_load_cookie_file)
        file_btn_layout.addWidget(btn_load_file)
        file_btn_layout.addStretch()
        layout.addLayout(file_btn_layout)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("🚀 Import & Lưu Session")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            raw = cookie_edit.toPlainText().strip()
            default_name = name_edit.text().strip()

            if not raw:
                QMessageBox.warning(self, "Lỗi", "Vui lòng paste nội dung cookies hoặc tải từ file!")
                return

            parsed_accounts = parse_bulk_dola_cookies(raw, default_name=default_name)
            if not parsed_accounts:
                QMessageBox.warning(self, "Lỗi", "Không parse được cookies hoặc tài khoản hợp lệ!\n"
                    "Đảm bảo paste đúng JSON hoặc định dạng ten_acc:\n[...] ")
                return

            imported_count = 0
            summary_details = []

            for acc_name, cookies_list in parsed_accounts:
                if not acc_name:
                    acc_name = default_name or f"dola_{len(self.account_manager.accounts) + 1:02d}"

                if not cookies_list:
                    continue

                # Tạo account trong account_manager nếu chưa có
                acc = self.account_manager.get_account(acc_name)
                if not acc:
                    try:
                        acc = self.account_manager.add_account(name=acc_name, login_type="dola_direct")
                    except ValueError:
                        acc = self.account_manager.get_account(acc_name)

                # Lưu session
                self.session_store.save_session(acc_name, cookies_list, {})

                if acc:
                    acc.dola_session_saved = True

                imported_count += 1
                summary_details.append(f"• <b>{acc_name}</b>: {len(cookies_list)} cookies")
                self.log(f"🎉 Đã nạp session cho '{acc_name}' ({len(cookies_list)} cookies)")

            self.account_manager.save()
            self.accounts_panel.refresh_table()
            self.create_panel.refresh_accounts()

            summary_msg = f"✅ Đã import thành công <b>{imported_count}</b> tài khoản:<br/><br/>" + "<br/>".join(summary_details[:20])
            if len(summary_details) > 20:
                summary_msg += f"<br/><i>...và {len(summary_details) - 20} tài khoản khác.</i>"

            QMessageBox.information(self, "Import Thành Công", summary_msg)

    def export_all_cookies_for_extension(self):
        """Xuất toàn bộ cookies tài khoản ra file JSON và copy vào clipboard để đồng bộ vào Extension."""
        self.session_store.load()
        self.account_manager.load()

        if not self.session_store._sessions:
            QMessageBox.warning(self, "Chưa có dữ liệu", "Chưa có session tài khoản nào được lưu để xuất!")
            return

        target_dir = "F:/Seedance"
        indiv_dir = os.path.join(target_dir, "Dola_Account_Cookies_Individual")
        os.makedirs(indiv_dir, exist_ok=True)

        multi_accounts = {}
        array_accounts = []
        extension_multi_profiles = {}
        via_lines = []

        colors = ['#ff7e00', '#2563eb', '#10b981', '#fbbf24', '#ec4899', '#8b5cf6', '#06b6d4', '#f97316']

        for idx, (acc_name, sdata) in enumerate(self.session_store._sessions.items()):
            raw_cookies = sdata.get("cookies", [])
            clean_cookies = []
            cookie_kv_pairs = []
            for c in raw_cookies:
                c_dict = {
                    "name": str(c.get("name", "")).strip(),
                    "value": str(c.get("value", "")).strip(),
                    "domain": str(c.get("domain", ".dola.com")),
                    "path": str(c.get("path", "/")),
                    "secure": bool(c.get("secure", True)),
                    "httpOnly": bool(c.get("httpOnly", False)),
                    "sameSite": str(c.get("sameSite", "Lax"))
                }
                if "expirationDate" in c:
                    c_dict["expirationDate"] = c["expirationDate"]
                elif "expires" in c:
                    c_dict["expirationDate"] = c["expires"]
                clean_cookies.append(c_dict)
                cookie_kv_pairs.append(f"{c_dict['name']}={c_dict['value']}")

            acc = self.account_manager.get_account(acc_name)
            fb_uid = (acc.fb_uid if acc else "") or sdata.get("fb_uid", "")
            dola_uid = (acc.dola_uid if acc else "") or sdata.get("dola_uid", "")
            ls = sdata.get("local_storage", {})

            multi_accounts[acc_name] = clean_cookies
            array_accounts.append({
                "name": acc_name,
                "cookies": clean_cookies,
                "local_storage": ls,
                "fb_uid": fb_uid,
                "dola_uid": dola_uid
            })

            # Định dạng multi_profiles tương thích 100% với Chrome Extension:
            extension_multi_profiles[acc_name] = {
                "name": acc_name,
                "cookies": clean_cookies,
                "local_storage": ls,
                "cookie_string": "; ".join(cookie_kv_pairs),
                "fb_uid": fb_uid,
                "dola_uid": dola_uid,
                "color": colors[idx % len(colors)],
                "updated_at": int(time.time() * 1000)
            }

            # File riêng cho từng account
            safe_fname = acc_name.replace(" ", "_").replace("/", "_").replace("\\", "_") + ".json"
            with open(os.path.join(indiv_dir, safe_fname), "w", encoding="utf-8") as f:
                json.dump(clean_cookies, f, ensure_ascii=False, indent=2)

            via_lines.append(f"Account [{acc_name}]: " + "; ".join(cookie_kv_pairs[:8]))

        # Ghi các file tổng hợp
        p_all = os.path.join(target_dir, "DOLA_ALL_ACCOUNTS_COOKIES.json")
        with open(p_all, "w", encoding="utf-8") as f:
            json.dump(extension_multi_profiles, f, ensure_ascii=False, indent=2)

        p_arr = os.path.join(target_dir, "DOLA_ACCOUNTS_ARRAY.json")
        with open(p_arr, "w", encoding="utf-8") as f:
            json.dump(array_accounts, f, ensure_ascii=False, indent=2)

        p_txt = os.path.join(target_dir, "DOLA_COOKIE_STRINGS.txt")
        with open(p_txt, "w", encoding="utf-8") as f:
            f.write("\n\n".join(via_lines))

        # Tự động copy JSON vào clipboard
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(json.dumps(extension_multi_profiles, ensure_ascii=False, indent=2))
        except Exception:
            pass

        count = len(multi_accounts)
        self.log(f"📤 Đã xuất {count} tài khoản cookies cho Extension ra {target_dir}")

        msg = (
            f"✅ <b>Đã xuất thành công {count} tài khoản cookies!</b><br/><br/>"
            f"📁 <b>Các file đã tạo:</b><br/>"
            f"• File tổng hợp Extension: <code>{p_all}</code><br/>"
            f"• File danh sách tài khoản: <code>{p_arr}</code><br/>"
            f"• Thư mục từng account riêng: <code>{indiv_dir}</code><br/><br/>"
            f"📋 <b>ĐÃ TỰ ĐỘNG COPY TOÀN BỘ JSON VÀO CLIPBOARD!</b><br/>"
            f"<i>Bạn có thể:</i><br/>"
            f"1. Mở Extension &rarr; Bấm <b>'⚡ LẤY TOÀN BỘ TỪ TOOL (PORT 8899)'</b> để đồng bộ tự động 1-click.<br/>"
            f"2. Hoặc mở Extension &rarr; Chọn <b>'📁 Nạp File'</b> &rarr; Chọn file <code>DOLA_ALL_ACCOUNTS_COOKIES.json</code>.<br/>"
            f"3. Hoặc Paste trực tiếp Clipboard vào ô Cookies của Extension."
        )
        QMessageBox.information(self, "Xuất Cookies Thành Công", msg)

    # ─── Video Creation ───────────────────────────────────────────

    def _get_selected_accounts(self, panel) -> list[str]:
        """Lấy danh sách tài khoản được chọn trong bảng Fast Mode."""
        selected = []
        for i in range(panel.acc_table.rowCount()):
            chk = panel.acc_table.cellWidget(i, 0)
            if chk and chk.isChecked():
                item = panel.acc_table.item(i, 1)
                if item:
                    selected.append(item.text())
        return selected

    def _run_pool_thread(self, pool, num_workers: int):
        """Chạy WorkerPool trong background thread với event loop riêng."""
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._pool_loop = loop

            async def _run():
                await pool.start(num_workers)
                # Chờ cho đến khi queue rỗng và không còn job chạy
                while pool._running:
                    status = pool.get_status()
                    if status['queue_size'] == 0 and status['active_jobs'] == 0:
                        await asyncio.sleep(3)
                        status2 = pool.get_status()
                        if status2['queue_size'] == 0 and status2['active_jobs'] == 0:
                            break
                    await asyncio.sleep(2)
                await pool.stop()

            loop.run_until_complete(_run())
        except Exception as e:
            self.sig_log.emit(f"❌ [Pool] Lỗi: {e}")
        finally:
            self.sig_log.emit("✅ [Pool] Tất cả workers đã dừng.")
            self._pool_loop = None
            # Re-enable buttons on GUI thread
            def enable_buttons():
                self.create_panel.btn_batch.setEnabled(True)
                self.create_panel.btn_single.setEnabled(True)
                self.create_panel.btn_stop.setEnabled(False)
            self.run_on_ui(enable_buttons)

    def run_single_video(self, prompt: str, panel: CreateVideoPanel):
        """Tạo 1 video đơn (Fast Mode)."""
        from worker_pool import WorkerPool

        model = panel.get_model_value()
        ratio = panel.get_ratio_value()
        duration = panel.get_duration_value()
        upscale = panel.get_upscale_value()
        image_path = panel.get_ref_image_path() if hasattr(panel, 'get_ref_image_path') else (panel._ref_image_path if hasattr(panel, '_ref_image_path') else "")

        # Lấy account được chọn
        accounts = self._get_selected_accounts(panel)
        if not accounts:
            QMessageBox.warning(self, "Chưa chọn tài khoản",
                "Vui lòng chọn ít nhất 1 tài khoản có session để tạo video!")
            return

        # Lấy tùy chọn hiện/ẩn Chrome
        show_browser = panel.chk_show_chrome.isChecked() if hasattr(panel, 'chk_show_chrome') else False

        img_info = f", Ảnh={image_path.split('/')[-1].split(chr(92))[-1]}" if image_path else ""
        vis_info = " (Hiện Chrome)" if show_browser else " (Ẩn Chrome)"
        self.log(f"⚡ [Fast] Tạo video đơn: Model={model}, Ratio={ratio}, {duration}s{img_info}{vis_info}")
        self.log(f"   Prompt: '{prompt[:80]}...'")

        # Disable buttons
        panel.btn_single.setEnabled(False)
        panel.btn_batch.setEnabled(False)
        panel.btn_stop.setEnabled(True)

        # Tạo pool và submit 1 job
        pool = WorkerPool(max_workers=1)
        pool.set_callbacks(
            on_progress=lambda wid, jid, msg: self.sig_log.emit(f"[W#{wid}] {msg}"),
            on_job_done=lambda job: self._on_job_completed(job, panel)
        )
        pool.submit_job(
            account_name=accounts[0],
            prompt=prompt,
            aspect_ratio=ratio,
            model_version=model,
            mode="standard",
            duration_target=duration,
            upscale=upscale,
            image_path=image_path,
            show_browser=show_browser,
            max_retries=panel.retry_spin.value(),
        )
        self._worker_pool = pool

        # Chạy pool trong background thread
        self._pool_thread = threading.Thread(
            target=self._run_pool_thread, args=(pool, 1), daemon=True)
        self._pool_thread.start()

    def run_batch_video(self, prompts: list[str], panel: CreateVideoPanel):
        """Chạy tạo video hàng loạt đa luồng (Fast Mode)."""
        from worker_pool import WorkerPool

        num_workers = panel.workers_spin.value()
        model = panel.get_model_value()
        ratio = panel.get_ratio_value()
        duration = panel.get_duration_value()
        upscale = panel.get_upscale_value()
        image_path = panel.get_ref_image_path() if hasattr(panel, 'get_ref_image_path') else (panel._ref_image_path if hasattr(panel, '_ref_image_path') else "")
        show_browser = panel.chk_show_chrome.isChecked() if hasattr(panel, 'chk_show_chrome') else False

        # Lấy accounts được chọn
        accounts = self._get_selected_accounts(panel)
        if not accounts:
            QMessageBox.warning(self, "Chưa chọn tài khoản",
                "Vui lòng chọn ít nhất 1 tài khoản có session để tạo video!")
            panel.btn_batch.setEnabled(True)
            panel.btn_stop.setEnabled(False)
            return

        img_info = f", Ảnh tham chiếu: {image_path.split('/')[-1].split(chr(92))[-1]}" if image_path else ""
        vis_info = " (Hiện Chrome)" if show_browser else " (Ẩn Chrome)"
        self.log(f"⚡ [Fast] Hàng loạt: {len(prompts)} video, {num_workers} workers{img_info}{vis_info}")
        self.dashboard_panel.set_num_workers(num_workers)
        self.dashboard_panel.card_workers.set_value(f"0/{num_workers}")
        self.dashboard_panel.card_queue.set_value(str(len(prompts)))

        # Tạo pool và submit tất cả jobs
        pool = WorkerPool(max_workers=num_workers)
        pool.set_callbacks(
            on_progress=lambda wid, jid, msg: self.sig_log.emit(f"[W#{wid}] {msg}"),
            on_job_done=lambda job: self._on_job_completed(job, panel)
        )

        # Phân bổ prompts cho accounts xoay vòng
        for i, prompt in enumerate(prompts):
            acc = accounts[i % len(accounts)]
            pool.submit_job(
                account_name=acc,
                prompt=prompt,
                aspect_ratio=ratio,
                model_version=model,
                mode="standard",
                duration_target=duration,
                upscale=upscale,
                image_path=image_path,
                show_browser=show_browser,
                max_retries=panel.retry_spin.value(),
            )

        self._worker_pool = pool
        self.log(f"🚀 Đã submit {len(prompts)} jobs cho {len(accounts)} accounts. Bắt đầu...")

        # Chạy pool trong background thread
        self._pool_thread = threading.Thread(
            target=self._run_pool_thread, args=(pool, num_workers), daemon=True)
        self._pool_thread.start()

    def _on_job_completed(self, job, panel: CreateVideoPanel):
        """Callback khi 1 job hoàn thành hoặc lỗi."""
        if job.status == 'completed':
            self.sig_log.emit(f"✅ [{job.id}] Video hoàn thành: {job.output_path}")
        else:
            self.sig_log.emit(f"❌ [{job.id}] Lỗi: {job.error}")
        if self._worker_pool:
            try:
                status = self._worker_pool.get_status()
                self.run_on_ui(lambda: (
                    self.create_panel.update_fast_tracking(status),
                    self.dashboard_panel.update_dashboard_live(status)))
            except Exception:
                pass

    def _on_stop_all(self):
        """Xử lý nút Dừng Tất Cả."""
        self.stop_all_workers()

    def stop_all_workers(self):
        """Đặt cờ dừng cho WorkerPool."""
        if self._worker_pool:
            self._worker_pool._running = False
            self.log("⚠️ Đang dừng tất cả workers...")
            if self._pool_loop and self._pool_loop.is_running():
                import asyncio
                asyncio.run_coroutine_threadsafe(self._worker_pool.stop(), self._pool_loop)
        self.create_panel.btn_stop.setEnabled(False)

    def install_video_skill_accounts(self, names=None):
        """Cài tuần tự cho mỗi phiên đã lưu; một tài khoản lỗi không chặn phần còn lại."""
        names = list(names) if names else [a['name'] for a in self.account_manager.get_all()
                                          if self.session_store.has_session(a['name'])]
        if not names:
            self.log("Chưa có phiên Dola để cài Skill.")
            return
        if not hasattr(self, '_skill_install_lock'):
            self._skill_install_lock = threading.Lock()
            self._skill_install_pending = []
        with self._skill_install_lock:
            self._skill_install_pending.extend(n for n in names if n not in self._skill_install_pending)
            if getattr(self, '_skill_install_busy', False):
                self.log("Đã thêm tài khoản vào hàng đợi cài Skill.")
                return
            self._skill_install_busy = True
        self.accounts_panel.btn_install_video_skill.setEnabled(False)

        def work():
            from browser_manager import BrowserManager
            from dola_skill_automation import DolaSkillAutomation, record_skill_status
            async def execute():
                bm = BrowserManager()
                try:
                    while True:
                        with self._skill_install_lock:
                            if not self._skill_install_pending:
                                self._skill_install_busy = False
                                break
                            name = self._skill_install_pending.pop(0)
                        try:
                            await bm.launch_temp_chrome(41, show_browser=True, load_extension=False)
                            await bm.connect_worker(41, setup_extension=False)
                            if not await bm.inject_session_to_worker(41, name):
                                raise RuntimeError("Không có session hợp lệ")
                            page = await bm.get_worker_page(41)
                            result = await DolaSkillAutomation().ensure_installed(page, name,
                                lambda msg: self.sig_log.emit(f"[Skill · {name}] {msg}"))
                            record_skill_status(name, result)
                            self.sig_log.emit(f"[Skill · {name}] {result['status']}")
                        except Exception as exc:
                            record_skill_status(name, {'status': 'error', 'error': str(exc)[:300]})
                            self.sig_log.emit(f"[Skill · {name}] Lỗi: {exc}")
                        finally:
                            await bm.cleanup_worker(41)
                finally:
                    await bm.cleanup_all()
            try:
                asyncio.run(execute())
            finally:
                self.run_on_ui(lambda: self.accounts_panel.btn_install_video_skill.setEnabled(
                    not getattr(self, '_skill_install_busy', False)))
        threading.Thread(target=work, daemon=True).start()

    def run_pro_video(self, prompts: list[str], skill: str, count: int,
                      ratio: str, account: str | list[str], image_path: str,
                      panel: CreateVideoPanel):
        from pro_skill_batch import ProSkillBatch
        self._pro_skill_runner = ProSkillBatch()
        runner = self._pro_skill_runner
        duration = 30 if panel.pro_duration_cb.currentIndex() == 0 else 15
        show_browser = panel.chk_pro_show_chrome.isChecked()
        def status(message):
            self.sig_log.emit(f"[Pro] {message}")
            self.run_on_ui(lambda m=message: panel.update_pro_status(m))
        def found(info):
            self.run_on_ui(lambda v=info: panel.add_pro_tracking_row(
                v['index'], f"✅ {v['duration']:.2f}s · Đã tải", v['path']))
        def work():
            async def execute():
                await runner.run(account, prompts, skill, count, ratio, image_path,
                    duration=duration, show_browser=show_browser, progress=status, on_video=found)
            try:
                asyncio.run(execute())
                status(f"Hoàn tất: {count} file video đã tải và kiểm tra thời lượng.")
            except asyncio.CancelledError:
                status("Đã dừng theo yêu cầu. Tác vụ Dola đã gửi có thể vẫn tiếp tục trên máy chủ.")
            except Exception as exc:
                status(f"Lỗi: {exc}")
            finally:
                self.run_on_ui(lambda: panel.btn_pro_start.setEnabled(True))
                self.run_on_ui(lambda: panel.btn_pro_stop.setEnabled(False))
                if self._pro_skill_runner is runner:
                    self._pro_skill_runner = None
        threading.Thread(target=work, daemon=True).start()

    # ─── API Server ───────────────────────────────────────────────

    def _start_api_server(self):
        def run_server():
            try:
                import uvicorn
                import api_server
                def open_accounts(names):
                    # The opener itself only schedules backend work. Keep this
                    # usable even while Qt is refreshing the account cards.
                    for index, name in enumerate(names[:10]):
                        timer = threading.Timer(index * 2.0, self.open_chrome_for_account, args=(name,))
                        timer.daemon = True
                        timer.start()
                    self.run_on_ui(lambda: self.nav_list.setCurrentRow(3))
                api_server.gui_open_accounts_handler = open_accounts
                uvicorn.run("api_server:app", host=API_HOST, port=API_PORT,
                            reload=False, log_level="warning", access_log=False)
            except Exception as e:
                self.sig_log.emit(f"API Server error: {e}")

        threading.Thread(target=run_server, daemon=True).start()

        def check_server():
            def work():
                try:
                    import urllib.request
                    with urllib.request.urlopen(f"http://{API_HOST}:{API_PORT}/api/health", timeout=2):
                        pass
                    self.run_on_ui(lambda: self.status_api_label.setText(f"  API: :{API_PORT} ✅  "))
                except Exception:
                    self.run_on_ui(lambda: QTimer.singleShot(5000, check_server))
            threading.Thread(target=work, name='studio-api-health', daemon=True).start()

        QTimer.singleShot(2000, check_server)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print(f"  {APP_NAME} PRO v{APP_VERSION} — PyQt6 Professional GUI")
    print("=" * 60)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = SeedanceMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()


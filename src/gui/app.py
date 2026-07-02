"""大麦 ATX 抢票 GUI 主界面

PyQt6 实现，提供配置编辑、设备管理、流程控制、日志查看一体化界面。
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox,
    QTabWidget, QGroupBox, QFormLayout, QTextEdit, QProgressBar,
    QRadioButton, QButtonGroup, QFrame, QSplitter, QMessageBox,
    QCheckBox,
)

from src.config_loader import AppConfig, load_config
from src.gui.worker import GrabWorker


# 配置文件路径
CONFIG_PATH = "config.jsonc"


def _make_section(title: str) -> QGroupBox:
    """创建带标题的分组框"""
    gb = QGroupBox(title)
    gb.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            border: 1px solid #cccccc;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
        }
    """)
    return gb


class ConfigPanel(QWidget):
    """配置编辑面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fields: dict[str, QWidget] = {}
        self._countdown_target = None  # 倒计时目标时间 (datetime)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._update_countdown)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Tab: 演出
        show_tab = QWidget()
        show_layout = QFormLayout(show_tab)
        show_layout.setSpacing(6)

        # 从手机自动检测
        detect_row = QHBoxLayout()
        self._detect_btn = QPushButton("从手机获取")
        self._detect_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0; color: white;
                padding: 4px 14px; border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7B1FA2; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        detect_row.addWidget(self._detect_btn)
        detect_row.addStretch()
        self._detect_status_label = QLabel("")
        self._detect_status_label.setStyleSheet("color: #888; font-size: 11px;")
        detect_row.addWidget(self._detect_status_label)
        show_layout.addRow("手机检测", detect_row)

        self._add_field(show_layout, "item_url", "商品链接", "https://m.damai.cn/...")
        self._add_field(show_layout, "keyword", "演出", "演唱会")
        self._add_field(show_layout, "city", "城市", "深圳")
        self._add_field(show_layout, "date", "日期", "12.06")
        self._add_field(show_layout, "price", "票价", "内场1199元")
        self._add_field(show_layout, "price_index", "票价索引", "0", is_int=True)
        self._add_field(show_layout, "users", "观演人", "姓名1,姓名2")

        # 开票倒计时显示
        self._countdown_label = QLabel("")
        self._countdown_label.setStyleSheet("""
            QLabel {
                font-size: 18px; font-weight: bold;
                color: #FF5722; padding: 8px;
                background-color: #FFF3E0;
                border: 2px solid #FF5722;
                border-radius: 6px;
            }
        """)
        self._countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_label.hide()  # 默认隐藏
        show_layout.addRow("开票倒计时", self._countdown_label)

        tabs.addTab(show_tab, "演出")

        # Tab: 定时
        time_tab = QWidget()
        time_layout = QFormLayout(time_tab)
        time_layout.setSpacing(6)
        self._add_field(time_layout, "start_at", "开售时间", "2026-07-01 20:00:00")
        self._add_field(time_layout, "warmup_sec", "预热秒数", "120", is_int=True)

        # NTP 服务器 + 测试按钮
        ntp_row = QHBoxLayout()
        self._ntp_input = QLineEdit()
        self._ntp_input.setPlaceholderText("ntp.aliyun.com")
        self._ntp_input.setText("ntp.aliyun.com")
        self._fields["ntp_server"] = self._ntp_input
        ntp_row.addWidget(self._ntp_input, 1)

        self._ntp_test_btn = QPushButton("测试")
        self._ntp_test_btn.setStyleSheet("""
            QPushButton {
                background-color: #607D8B; color: white;
                padding: 4px 12px; border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #455A64; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        ntp_row.addWidget(self._ntp_test_btn)

        self._ntp_status_label = QLabel("")
        self._ntp_status_label.setStyleSheet("color: #888; font-size: 11px;")
        ntp_row.addWidget(self._ntp_status_label)
        time_layout.addRow("NTP 服务器", ntp_row)

        tabs.addTab(time_tab, "定时")

        # Tab: 冲刺
        sprint_tab = QWidget()
        sprint_layout = QFormLayout(sprint_tab)
        sprint_layout.setSpacing(6)
        self._add_field(sprint_layout, "sprint_interval_ms", "循环间隔(ms)", "50", is_int=True)
        self._add_field(sprint_layout, "sprint_max_retries", "最大重试", "60", is_int=True)
        tabs.addTab(sprint_tab, "冲刺")

        # Tab: 设备
        dev_tab = QWidget()
        dev_layout = QFormLayout(dev_tab)
        dev_layout.setSpacing(6)

        # UDID + 获取序列号按钮
        udid_row = QHBoxLayout()
        self._udid_input = QLineEdit()
        self._udid_input.setPlaceholderText("留空自动选择")
        self._fields["udid"] = self._udid_input
        udid_row.addWidget(self._udid_input, 1)

        self._detect_serial_btn = QPushButton("获取序列号")
        self._detect_serial_btn.setStyleSheet("""
            QPushButton {
                background-color: #009688; color: white;
                padding: 4px 12px; border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #00796B; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        udid_row.addWidget(self._detect_serial_btn)
        self._serial_status_label = QLabel("")
        self._serial_status_label.setStyleSheet("color: #888; font-size: 11px;")
        udid_row.addWidget(self._serial_status_label)
        dev_layout.addRow("设备序列号", udid_row)

        self._add_field(dev_layout, "app_package", "App 包名", "cn.damai")
        self._add_field(dev_layout, "app_activity", "启动 Activity", ".launcher.splash.SplashMainActivity")

        self._auto_nav_cb = QCheckBox("自动导航到目标演出")
        self._auto_nav_cb.setChecked(True)
        dev_layout.addRow("导航", self._auto_nav_cb)
        self._fields["auto_navigate"] = self._auto_nav_cb

        tabs.addTab(dev_tab, "设备")

        # 保存按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("保存配置")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; color: white;
                padding: 6px 20px; border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        save_btn.clicked.connect(self._save_config)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def set_detect_busy(self, busy: bool):
        """设置手机检测按钮的忙碌状态"""
        self._detect_btn.setEnabled(not busy)
        if busy:
            self._detect_status_label.setText("检测中...")
        else:
            self._detect_status_label.setText("")

    def start_countdown(self, target_dt):
        """启动倒计时显示

        Args:
            target_dt: 目标时间 datetime 对象
        """
        from datetime import datetime
        self._countdown_target = target_dt
        self._countdown_label.show()
        self._update_countdown()
        self._countdown_timer.start(1000)  # 每秒更新

    def _update_countdown(self):
        """更新倒计时显示"""
        from datetime import datetime
        if not self._countdown_target:
            return

        now = datetime.now()
        diff = self._countdown_target - now

        if diff.total_seconds() <= 0:
            self._countdown_label.setText("已开票！")
            self._countdown_label.setStyleSheet("""
                QLabel {
                    font-size: 18px; font-weight: bold;
                    color: #4CAF50; padding: 8px;
                    background-color: #E8F5E9;
                    border: 2px solid #4CAF50;
                    border-radius: 6px;
                }
            """)
            self._countdown_timer.stop()
            return

        days = diff.days
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if days > 0:
            text = f"仅剩 {days}天 {hours:02d}时 {minutes:02d}分 {seconds:02d}秒"
        elif hours > 0:
            text = f"仅剩 {hours:02d}时 {minutes:02d}分 {seconds:02d}秒"
        else:
            text = f"仅剩 {minutes:02d}分 {seconds:02d}秒"

        self._countdown_label.setText(text)

    def stop_countdown(self):
        """停止倒计时"""
        self._countdown_timer.stop()
        self._countdown_label.hide()
        self._countdown_target = None

    def has_countdown(self) -> bool:
        """是否有倒计时"""
        return self._countdown_target is not None

    def is_countdown_finished(self) -> bool:
        """倒计时是否已结束"""
        if not self._countdown_target:
            return True
        from datetime import datetime
        return datetime.now() >= self._countdown_target

    def apply_detect_result(self, data: dict):
        """将手机检测结果填入表单"""
        if data.get("error"):
            return
        if data.get("city"):
            self._fields["city"].setText(data["city"])
        if data.get("date"):
            self._fields["date"].setText(data["date"])
        if data.get("price"):
            self._fields["price"].setText(data["price"])
        if "price_index" in data and data["price_index"]:
            self._fields["price_index"].setValue(data["price_index"])
        if data.get("item_url"):
            self._fields["item_url"].setText(data["item_url"])
        if data.get("venue"):
            pass  # 场馆信息仅供查看，不映射到表单字段
        # show_name 填入 keyword 字段
        if data.get("show_name"):
            self._fields["keyword"].setText(data["show_name"])

    def _add_field(self, layout, name: str, label: str, placeholder: str = "", is_int: bool = False):
        """添加配置字段"""
        if is_int:
            widget = QSpinBox()
            widget.setRange(0, 99999)
            widget.setValue(int(placeholder))
        else:
            widget = QLineEdit()
            widget.setPlaceholderText(placeholder)
        self._fields[name] = widget
        layout.addRow(label, widget)

    def load_from_config(self, config: AppConfig):
        """从 AppConfig 加载数据到表单"""
        for name, field in self._fields.items():
            val = getattr(config, name, "")
            if isinstance(field, QSpinBox):
                field.setValue(int(val) if val else 0)
            elif isinstance(field, QCheckBox):
                field.setChecked(bool(val))
            elif isinstance(field, QLineEdit):
                if isinstance(val, list):
                    field.setText(", ".join(val))
                else:
                    field.setText(str(val) if val else "")

    def to_config(self) -> AppConfig:
        """从表单读取数据生成 AppConfig"""
        data = {}
        for name, field in self._fields.items():
            if isinstance(field, QSpinBox):
                data[name] = field.value()
            elif isinstance(field, QCheckBox):
                data[name] = field.isChecked()
            elif isinstance(field, QLineEdit):
                text = field.text().strip()
                if name == "users":
                    data[name] = [u.strip() for u in text.split(",") if u.strip()]
                elif name in ("udid", "item_url", "keyword") and not text:
                    data[name] = "" if name in ("udid", "item_url") else None
                else:
                    data[name] = text
        return AppConfig(**data)

    def _save_config(self):
        """保存配置到文件"""
        try:
            config = self.to_config()
            raw = {
                "udid": config.udid,
                "app_package": config.app_package,
                "app_activity": config.app_activity,
                "item_url": config.item_url,
                "keyword": config.keyword,
                "users": config.users,
                "city": config.city,
                "date": config.date,
                "price": config.price,
                "price_index": config.price_index,
                "if_commit_order": config.if_commit_order,
                "probe_only": config.probe_only,
                "auto_navigate": config.auto_navigate,
                "start_at": config.start_at,
                "warmup_sec": config.warmup_sec,
                "ntp_server": config.ntp_server,
                "sprint_interval_ms": config.sprint_interval_ms,
                "sprint_max_retries": config.sprint_max_retries,
                "log_level": config.log_level,
                "log_dir": config.log_dir,
            }
            lines = json.dumps(raw, ensure_ascii=False, indent=2).split("\n")
            # 在字段后添加注释
            comments = {
                "udid": "adb devices 序列号，留空自动选择",
                "item_url": "商品链接（优先级高于 keyword）",
                "keyword": "搜索关键词",
                "users": "观演人列表",
                "if_commit_order": "true=正式提交订单",
                "probe_only": "true=仅探测不点购票",
                "auto_navigate": "自动导航到目标演出",
                "warmup_sec": "开售前预热秒数",
                "sprint_interval_ms": "冲刺循环间隔(ms)",
                "sprint_max_retries": "最大重试次数",
            }
            result = []
            for line in lines:
                stripped = line.strip()
                for key, comment in comments.items():
                    if stripped.startswith(f'"{key}"'):
                        line = line.rstrip() + f"  // {comment}"
                        break
                result.append(line)
            content = "{\n" + "\n".join(result[1:-1]) + "\n}\n"
            Path(CONFIG_PATH).write_text(content, encoding="utf-8")
            QMessageBox.information(self, "保存成功", f"配置已保存到 {CONFIG_PATH}")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))


class LogPanel(QWidget):
    """日志显示面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("运行日志")
        header.setStyleSheet("font-weight: bold; font-size: 13px; padding: 2px 0;")
        layout.addWidget(header)

        self._log_area = QTextEdit()
        self._log_area.setReadOnly(True)
        self._log_area.setFont(QFont("Consolas", 9))
        self._log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        self._log_area.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._log_area)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._log_area.clear)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def append_log(self, message: str):
        """追加日志"""
        self._log_area.append(message)
        # 自动滚动到底部
        scrollbar = self._log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def append_html(self, html: str):
        """追加 HTML 格式日志"""
        cursor = self._log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_area.setTextCursor(cursor)
        scrollbar = self._log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self._worker: Optional[GrabWorker] = None
        self._device_connected = False
        self._setup_ui()
        self._load_initial_config()
        self._check_device_status()

        # 连接按钮
        self._config_panel._detect_btn.clicked.connect(self._start_phone_detect)
        self._config_panel._ntp_test_btn.clicked.connect(self._start_ntp_test)
        self._config_panel._detect_serial_btn.clicked.connect(self._detect_serial)

    def _setup_ui(self):
        self.setWindowTitle("大麦 ATX 抢票 v2.0")
        self.setMinimumSize(1000, 720)

        # 创建工作线程（仅一次）
        self._worker = GrabWorker(CONFIG_PATH)
        self._worker.log_message.connect(self._on_log_message)
        self._worker.phase_changed.connect(self._on_phase_changed)
        self._worker.progress_update.connect(self._on_progress_update)
        self._worker.device_info.connect(self._on_device_info)
        self._worker.device_error.connect(self._on_device_error)
        self._worker.connect_finished.connect(self._on_connect_finished)
        self._worker.detect_result.connect(self._on_detect_result)
        self._worker.ntp_test_result.connect(self._on_ntp_test_result)
        self._worker.finished.connect(self._on_workflow_finished)
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QToolTip { background-color: #333; color: #fff; border: 1px solid #555; padding: 4px; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ========================================
        # 顶部: 设备状态栏
        # ========================================
        dev_frame = _make_section("设备状态")
        dev_layout = QHBoxLayout(dev_frame)

        self._dev_label = QLabel("📱 未连接")
        self._dev_label.setStyleSheet("font-size: 14px; padding: 4px;")
        dev_layout.addWidget(self._dev_label)

        dev_layout.addStretch()

        self._dev_connect_btn = QPushButton("连接设备")
        self._dev_connect_btn.setStyleSheet("""
            QPushButton { padding: 6px 16px; border-radius: 4px; font-weight: bold; }
            QPushButton { background-color: #4CAF50; color: white; }
            QPushButton:hover { background-color: #388E3C; }
        """)
        self._dev_connect_btn.clicked.connect(self._toggle_device)
        dev_layout.addWidget(self._dev_connect_btn)

        main_layout.addWidget(dev_frame)

        # ========================================
        # 控制栏
        # ========================================
        ctrl_frame = _make_section("运行控制")
        ctrl_layout = QVBoxLayout(ctrl_frame)

        # 模式选择
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("运行模式:"))
        self._mode_group = QButtonGroup(self)
        self._rb_probe = QRadioButton("探测模式")
        self._rb_probe.setChecked(True)
        self._rb_dryrun = QRadioButton("演练模式")
        self._rb_live = QRadioButton("实战模式")
        self._mode_group.addButton(self._rb_probe, 1)
        self._mode_group.addButton(self._rb_dryrun, 2)
        self._mode_group.addButton(self._rb_live, 3)
        mode_row.addWidget(self._rb_probe)
        mode_row.addWidget(self._rb_dryrun)
        mode_row.addWidget(self._rb_live)
        mode_row.addStretch()
        ctrl_layout.addLayout(mode_row)

        # 进度 + 按钮
        action_row = QHBoxLayout()

        self._phase_label = QLabel("就绪")
        self._phase_label.setStyleSheet("font-size: 13px; padding: 4px; color: #555;")
        action_row.addWidget(self._phase_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setValue(0)
        action_row.addWidget(self._progress_bar)

        action_row.addStretch()

        self._start_btn = QPushButton("▶ 开始运行")
        self._start_btn.setStyleSheet("""
            QPushButton { padding: 8px 24px; border-radius: 4px; font-weight: bold; font-size: 13px; }
            QPushButton { background-color: #FF5722; color: white; }
            QPushButton:hover { background-color: #E64A19; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self._start_btn.clicked.connect(self._start_workflow)
        action_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("■ 停止")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet("""
            QPushButton { padding: 8px 24px; border-radius: 4px; font-weight: bold; font-size: 13px; }
            QPushButton { background-color: #9E9E9E; color: white; }
            QPushButton:enabled { background-color: #F44336; color: white; }
            QPushButton:enabled:hover { background-color: #D32F2F; }
        """)
        self._stop_btn.clicked.connect(self._stop_workflow)
        action_row.addWidget(self._stop_btn)

        ctrl_layout.addLayout(action_row)
        main_layout.addWidget(ctrl_frame)

        # ========================================
        # 中部分割: 配置 + 日志
        # ========================================
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 配置面板
        self._config_panel = ConfigPanel()
        splitter.addWidget(self._config_panel)

        # 日志面板
        self._log_panel = LogPanel()
        splitter.addWidget(self._log_panel)

        splitter.setSizes([350, 300])
        main_layout.addWidget(splitter, 1)

        # 状态栏
        self.statusBar().showMessage("就绪")

    # ---------- 设备管理 ----------

    def _load_initial_config(self):
        """加载初始配置"""
        try:
            config = load_config(CONFIG_PATH)
            self._config_panel.load_from_config(config)
        except Exception:
            # 默认配置
            self._config_panel.load_from_config(AppConfig())

    def _check_device_status(self):
        """定时检查设备状态"""
        import subprocess
        try:
            result = subprocess.run(
                ["adb", "devices", "-l"],
                capture_output=True, text=True, timeout=3
            )
            lines = result.stdout.strip().split("\n")
            device_lines = [l for l in lines if "device" in l and "List" not in l]
            if device_lines:
                self._dev_label.setText(f"📱 {device_lines[0].strip()}")
            else:
                self._dev_label.setText("📱 未检测到设备")
        except Exception:
            self._dev_label.setText("📱 adb 不可用")

    def _toggle_device(self):
        """连接/断开设备"""
        if self._device_connected:
            self._disconnect_device()
        else:
            self._connect_device()

    def _connect_device(self):
        """异步连接设备（在后台线程执行）"""
        self._dev_connect_btn.setEnabled(False)
        self._dev_connect_btn.setText("连接中...")
        self._log_panel.append_log("正在连接设备...")
        QApplication.processEvents()

        udid = ""
        udid_field = self._config_panel._fields.get("udid")
        if udid_field:
            udid = udid_field.text().strip()
        self._worker.connect_device(udid)

    def _on_connect_finished(self, ok: bool):
        """设备连接完成回调"""
        if ok:
            self._device_connected = True
            self._dev_connect_btn.setText("断开设备")
            self._dev_connect_btn.setStyleSheet("""
                QPushButton { padding: 6px 16px; border-radius: 4px; font-weight: bold; }
                QPushButton { background-color: #FF5722; color: white; }
                QPushButton:hover { background-color: #E64A19; }
            """)
        else:
            self._device_connected = False
            self._dev_connect_btn.setText("连接设备")
            self._dev_connect_btn.setStyleSheet("""
                QPushButton { padding: 6px 16px; border-radius: 4px; font-weight: bold; }
                QPushButton { background-color: #4CAF50; color: white; }
                QPushButton:hover { background-color: #388E3C; }
            """)
        self._dev_connect_btn.setEnabled(True)

    def _disconnect_device(self):
        """断开设备"""
        if self._worker:
            self._worker.disconnect_device()
        self._device_connected = False
        self._dev_connect_btn.setText("连接设备")
        self._log_panel.append_log("设备已断开")

    def _on_device_info(self, name: str, size: str, status: str):
        self._dev_label.setText(f"📱 {name}  {size}")
        self.statusBar().showMessage(f"设备: {name} | {size}")

    def _on_device_error(self, msg: str):
        self._log_panel.append_log(f"[错误] {msg}")
        QMessageBox.warning(self, "设备错误", msg)

    # ---------- 手机页面检测 ----------

    def _start_phone_detect(self):
        """开始从手机检测当前页面信息"""
        if not self._device_connected:
            QMessageBox.warning(self, "设备未连接", "请先连接手机设备")
            return

        self._config_panel.set_detect_busy(True)
        self._log_panel.append_log("正在检测手机当前页面信息...")
        self._worker.request_detect()

    def _on_detect_result(self, data: dict):
        """手机检测结果回调"""
        self._config_panel.set_detect_busy(False)

        if data.get("error"):
            self._log_panel.append_log(f"[错误] {data['error']}")
            QMessageBox.warning(self, "检测失败", data["error"])
            return

        self._config_panel.apply_detect_result(data)

        # 构建结果摘要
        summary_parts = []
        if data.get("show_name"):
            summary_parts.append(f"演出: {data['show_name']}")
        if data.get("city"):
            summary_parts.append(f"城市: {data['city']}")
        if data.get("date"):
            summary_parts.append(f"日期: {data['date']}")
        if data.get("price"):
            summary_parts.append(f"票价: {data['price']}")
        if data.get("venue"):
            summary_parts.append(f"场馆: {data['venue']}")
        if data.get("sale_time"):
            summary_parts.append(f"开票: {data['sale_time']}")

        summary = " | ".join(summary_parts) if summary_parts else "未检测到有效信息"
        self._log_panel.append_log(f"手机检测完成: {summary}")

        if data.get("warning"):
            self._log_panel.append_log(f"[警告] {data['warning']}")

        # 每次检测结果都先清除旧倒计时
        self._config_panel.stop_countdown()
        # 如果新页面有开票时间则启动新倒计时
        if data.get("sale_time"):
            self._start_countdown_from_str(data["sale_time"])

        QMessageBox.information(
            self, "检测成功",
            f"已从手机当前页面提取以下信息:\n\n"
            + "\n".join(summary_parts)
            + "\n\n请核对后点击保存配置。"

        )

    def _start_countdown_from_str(self, sale_time_str: str):
        """从开票时间字符串解析并启动倒计时

        支持格式:
          - "07月08日 19:00开抢"
          - "2026-07-08 19:00:00"
          - "07.08 19:00"
        """
        import re
        from datetime import datetime

        # 模式1: "07月08日 19:00开抢"
        m = re.match(r"(\d{1,2})月(\d{1,2})日?\s*(\d{1,2}):(\d{2})", sale_time_str)
        if m:
            month, day, hour, minute = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            now = datetime.now()
            target = now.replace(month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            if target < now:
                target = target.replace(year=now.year + 1)
            self._log_panel.append_log(f"开票倒计时: {target.strftime('%Y-%m-%d %H:%M:%S')}")
            self._config_panel.start_countdown(target)
            return

        # 模式2: "2026-07-08 19:00:00"
        m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})\s*(\d{1,2}):(\d{2})", sale_time_str)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            hour, minute = int(m.group(4)), int(m.group(5))
            target = datetime(year, month, day, hour, minute, 0)
            self._log_panel.append_log(f"开票倒计时: {target.strftime('%Y-%m-%d %H:%M:%S')}")
            self._config_panel.start_countdown(target)
            return

        # 模式3: "07.08 19:00"
        m = re.match(r"(\d{1,2})\.(\d{1,2})\s*(\d{1,2}):(\d{2})", sale_time_str)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            hour, minute = int(m.group(3)), int(m.group(4))
            now = datetime.now()
            target = now.replace(month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            if target < now:
                target = target.replace(year=now.year + 1)
            self._log_panel.append_log(f"开票倒计时: {target.strftime('%Y-%m-%d %H:%M:%S')}")
            self._config_panel.start_countdown(target)
            return

        self._log_panel.append_log(f"[警告] 无法解析开票时间: {sale_time_str}")

    # ---------- NTP 测试 ----------

    def _start_ntp_test(self):
        """测试 NTP 服务器连通性"""
        server = self._config_panel._ntp_input.text().strip()
        if not server:
            QMessageBox.warning(self, "输入错误", "请输入 NTP 服务器地址")
            return

        self._config_panel._ntp_test_btn.setEnabled(False)
        self._config_panel._ntp_status_label.setText("测试中...")
        self._log_panel.append_log(f"正在测试 NTP 服务器: {server}...")
        self._worker.test_ntp(server)

    def _on_ntp_test_result(self, server: str, offset_ms: float):
        """NTP 测试结果回调"""
        self._config_panel._ntp_test_btn.setEnabled(True)
        if offset_ms < 0:
            self._config_panel._ntp_status_label.setText("连接失败")
            self._config_panel._ntp_status_label.setStyleSheet("color: #F44336; font-size: 11px;")
            self._log_panel.append_log(f"NTP 测试失败: {server}")
        else:
            sign = "+" if offset_ms >= 0 else ""
            self._config_panel._ntp_status_label.setText(f"偏移 {sign}{offset_ms:.0f}ms")
            self._config_panel._ntp_status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
            self._log_panel.append_log(f"NTP 测试成功: {server}, 偏移 {sign}{offset_ms:.0f}ms")

    # ---------- 设备序列号检测 ----------

    def _detect_serial(self):
        """检测已连接手机的序列号"""
        import subprocess
        self._config_panel._detect_serial_btn.setEnabled(False)
        self._config_panel._serial_status_label.setText("检测中...")
        self._log_panel.append_log("正在检测设备序列号...")

        try:
            result = subprocess.run(
                ["adb", "devices", "-l"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split("\n")
            device_found = None
            for line in lines:
                if "device" in line and "List" not in line:
                    parts = line.split()
                    if parts:
                        udid = parts[0]
                        if udid and udid != "unknown":
                            device_found = udid
                            break

            if device_found:
                self._config_panel._udid_input.setText(device_found)
                self._config_panel._serial_status_label.setText("已检测")
                self._config_panel._serial_status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
                self._log_panel.append_log(f"检测到设备序列号: {device_found}")
            else:
                self._config_panel._serial_status_label.setText("未发现设备")
                self._config_panel._serial_status_label.setStyleSheet("color: #FF9800; font-size: 11px;")
                self._log_panel.append_log("未检测到已连接的 Android 设备")

        except FileNotFoundError:
            self._config_panel._serial_status_label.setText("adb 不可用")
            self._config_panel._serial_status_label.setStyleSheet("color: #F44336; font-size: 11px;")
            self._log_panel.append_log("错误: adb 未安装或不在 PATH 中")
        except Exception as e:
            self._config_panel._serial_status_label.setText("检测失败")
            self._config_panel._serial_status_label.setStyleSheet("color: #F44336; font-size: 11px;")
            self._log_panel.append_log(f"检测序列号失败: {e}")
        finally:
            self._config_panel._detect_serial_btn.setEnabled(True)

    # ---------- 工作流控制 ----------

    def _start_workflow(self):
        """开始运行抢票流程"""
        config = self._config_panel.to_config()

        # 设置运行模式
        selected = self._mode_group.checkedId()
        if selected == 1:  # 探测
            config.probe_only = True
            config.if_commit_order = False
        elif selected == 2:  # 演练
            config.probe_only = False
            config.if_commit_order = False
        else:  # 实战
            config.probe_only = False
            config.if_commit_order = True

        # 验证必要字段
        errors = []
        if not config.city:
            errors.append("城市不能为空")
        if not config.date:
            errors.append("日期不能为空")
        if not config.users:
            errors.append("请至少添加一个观演人")
        if errors:
            QMessageBox.warning(self, "配置不完整", "\n".join(errors))
            return

        # 如果有倒计时且未结束，等待归零
        if self._config_panel.has_countdown() and not self._config_panel.is_countdown_finished():
            reply = QMessageBox.question(
                self, "倒计时未结束",
                "开票倒计时还未结束，是否等到开票后再自动启动？\n\n"
                "选择「是」将自动等待，选择「否」立即启动。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._log_panel.append_log("等待倒计时结束后自动启动...")
                # 使用 QTimer 等待
                self._wait_countdown_timer = QTimer(self)
                self._wait_countdown_timer.timeout.connect(self._check_countdown_and_start)
                self._wait_countdown_timer.start(1000)
                self._start_btn.setEnabled(False)
                self._stop_btn.setEnabled(True)
                return

        # 直接启动
        self._do_start_workflow(config)

    def _check_countdown_and_start(self):
        """检查倒计时是否结束，结束则启动流程"""
        if self._config_panel.is_countdown_finished():
            self._wait_countdown_timer.stop()
            self._log_panel.append_log("倒计时结束，启动抢票流程！")
            config = self._config_panel.to_config()
            self._do_start_workflow(config)

    def _do_start_workflow(self, config):
        """实际启动抢票流程"""
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._phase_label.setText("启动中...")
        self._progress_bar.setValue(0)
        self._config_panel.setEnabled(False)

        self._worker.run_workflow(config)

    def _stop_workflow(self):
        """停止运行"""
        # 停止倒计时等待
        if hasattr(self, '_wait_countdown_timer') and self._wait_countdown_timer.isActive():
            self._wait_countdown_timer.stop()
            self._start_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
            self._config_panel.setEnabled(True)
            self._phase_label.setText("已停止")
            self._log_panel.append_log("[用户] 已停止等待倒计时")
            return

        # 停止运行中的工作流
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._log_panel.append_log("[用户] 正在停止...")
            self._stop_btn.setEnabled(False)

    def _on_log_message(self, message: str):
        """收到日志消息"""
        self._log_panel.append_log(message)

    def _on_phase_changed(self, phase_name: str):
        """阶段变化"""
        self._phase_label.setText(f"阶段: {phase_name}")

    def _on_progress_update(self, value: int, description: str):
        """进度更新"""
        self._progress_bar.setValue(value)
        self._phase_label.setText(f"阶段: {description}")

    def _on_workflow_finished(self, success: int):
        """流程结束"""
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._config_panel.setEnabled(True)

        if success == 1:
            self._progress_bar.setStyleSheet("")
            self._progress_bar.setValue(100)
            self.statusBar().showMessage("流程完成")
            self._log_panel.append_log("[结束] 流程完成")
        else:
            self._progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #F44336; }")
            self.statusBar().showMessage("流程异常终止")
            self._log_panel.append_log("[结束] 流程异常终止")

    def closeEvent(self, event):
        """关闭窗口时的清理"""
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(2000)
        event.accept()

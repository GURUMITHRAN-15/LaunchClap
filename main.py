"""
ClapLaunch — local double-clap app launcher for Windows.
Audio is processed in memory; no audio is saved or uploaded.
"""
import json
import os
import sys
import time
import threading
import subprocess
import queue
from collections import deque

import numpy as np
import sounddevice as sd
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QLineEdit,
    QFileDialog, QCheckBox, QSlider, QProgressBar, QFrame, QVBoxLayout,
    QHBoxLayout, QGridLayout, QMessageBox, QScrollArea
)

APP_NAME = "ClapLaunch"
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
DOUBLE_CLAP_MIN_GAP = 0.12
DOUBLE_CLAP_MAX_GAP = 0.70
CLAP_REFRACTORY = 0.10
COOLDOWN_SECONDS = 4.0

DEFAULT_APPS = {
    "VS Code": r"C:\Users\YOUR_USERNAME\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "Browser": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "Terminal": "wt.exe",
    "Spotify": os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
}

BG = "#090d0b"
PANEL = "#111915"
PANEL_2 = "#151f19"
GREEN = "#39ff88"
GREEN_DIM = "#1eaa5b"
TEXT = "#e6f5eb"
MUTED = "#8ba394"
RED = "#ff647c"


def load_config():
    defaults = {"apps": DEFAULT_APPS.copy(), "threshold": 0.04, "startup": True}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        defaults.update(saved)
        defaults["apps"] = {**DEFAULT_APPS, **saved.get("apps", {})}
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return defaults


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def set_windows_startup(enabled):
    if sys.platform != "win32":
        raise RuntimeError("Windows startup integration is available only on Windows.")
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            python_exe = sys.executable
            if python_exe.lower().endswith("python.exe"):
                python_exe = python_exe[:-10] + "pythonw.exe"
            command = f'"{python_exe}" "{os.path.abspath(__file__)}" --minimized'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def launch_app(name, app_path):
    app_path = (app_path or "").strip().strip('"')
    if not app_path:
        raise ValueError(f"No application path configured for {name}.")
    if os.path.isabs(app_path) and not os.path.exists(app_path):
        raise FileNotFoundError(f"Path not found for {name}:\n{app_path}")
    subprocess.Popen([app_path], shell=False)


class ClapDetector:
    """RMS-based transient detector, retaining the original calibration and timing rules."""
    def __init__(self, threshold=0.04, status_callback=None, trigger_callback=None, visual_callback=None):
        self.threshold = float(threshold)
        self.status_callback = status_callback or (lambda _s: None)
        self.trigger_callback = trigger_callback or (lambda: None)
        self.visual_callback = visual_callback or (lambda _rms, _wave: None)
        self.stream = None
        self.running = False
        self.calibrating = False
        self.noise_samples = []
        self.last_peak_time = 0.0
        self.first_clap_time = None
        self.last_trigger_time = 0.0
        self.calibrated = False
        self._rms_history = []

    def status(self, text):
        self.status_callback(text)

    def start(self):
        if self.running:
            return
        self.running = True
        self.calibrated = False
        self.noise_samples = []
        self._rms_history = []
        self.calibrating = True
        self.first_clap_time = None
        self.status("Calibrating for 3 seconds — stay quiet, then clap twice.")
        try:
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, channels=1,
                dtype="float32", callback=self._audio_callback
            )
            self.stream.start()
            threading.Thread(target=self._finish_calibration, daemon=True).start()
        except Exception as exc:
            self.running = False
            self.calibrating = False
            self.status(f"Microphone error: {exc}")

    def _finish_calibration(self):
        time.sleep(3.0)
        if not self.running:
            return
        values = self.noise_samples[:]
        if len(values) < 10:
            self.calibrating = False
            self.status("Calibration failed: no microphone data. Check Windows microphone permissions.")
            return
        ambient = float(np.percentile(values, 90))
        self.threshold = max(0.018, min(0.30, ambient * 4.0 + 0.012))
        self.calibrating = False
        self.calibrated = True
        self.status(f"Listening for double claps. Ambient RMS {ambient:.4f}; threshold {self.threshold:.4f}. Clap twice to test.")

    def _audio_callback(self, indata, frames, time_info, status):
        if not self.running:
            return
        samples = indata[:, 0]
        rms = float(np.sqrt(np.mean(np.square(samples))))
        # Only send a small copy for a visual waveform; never write audio to disk.
        wave = samples[::8].copy()
        self.visual_callback(rms, wave)
        now = time.monotonic()
        if self.calibrating:
            self.noise_samples.append(rms)
            return
        if not self.calibrated:
            return
        self._rms_history.append(rms)
        if len(self._rms_history) > 25:
            self._rms_history.pop(0)
        baseline_values = self._rms_history[:-1] or [0.0]
        baseline = float(np.percentile(baseline_values, 40))
        threshold = max(self.threshold, baseline * 3.0 + 0.008)
        if rms >= threshold and (now - self.last_peak_time) >= CLAP_REFRACTORY:
            self.last_peak_time = now
            if self.first_clap_time is None:
                self.first_clap_time = now
                self.status("First clap detected — clap once more!")
            else:
                gap = now - self.first_clap_time
                if DOUBLE_CLAP_MIN_GAP <= gap <= DOUBLE_CLAP_MAX_GAP:
                    if now - self.last_trigger_time >= COOLDOWN_SECONDS:
                        self.last_trigger_time = now
                        self.first_clap_time = None
                        self.status("Double clap detected! Opening configured apps…")
                        threading.Thread(target=self.trigger_callback, daemon=True).start()
                    else:
                        self.first_clap_time = None
                        self.status("Cooldown active — wait a few seconds before the next double clap.")
                elif gap < DOUBLE_CLAP_MIN_GAP:
                    self.first_clap_time = now
                else:
                    self.first_clap_time = now
                    self.status("Clap window expired — clap again to start a new pair.")

    def stop(self):
        self.running = False
        self.calibrating = False
        self.calibrated = False
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        self.stream = None
        self.status("Stopped. Microphone is not being read.")


class WaveformWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(112)
        self.samples = deque([0.0] * 180, maxlen=180)

    def add_samples(self, wave):
        self.samples.extend(float(x) for x in wave)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(PANEL))
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor("#23372b"), 1, Qt.PenStyle.DotLine))
        p.drawLine(0, h // 2, w, h // 2)
        values = list(self.samples)
        if len(values) > 1:
            pen = QPen(QColor(GREEN), 2)
            p.setPen(pen)
            points = []
            for i, value in enumerate(values):
                x = i * (w - 1) / (len(values) - 1)
                y = h / 2 - max(-1.0, min(1.0, value)) * (h * 0.42)
                points.append((int(x), int(y)))
            for a, b in zip(points, points[1:]):
                p.drawLine(a[0], a[1], b[0], b[1])
        p.end()


class ClapLaunchWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.path_fields = {}
        self.ui_queue = queue.Queue()
        self.detector = ClapDetector(
            threshold=self.config.get("threshold", 0.04),
            status_callback=lambda message: self.ui_queue.put(("status", message)),
            trigger_callback=self.open_configured_apps,
            visual_callback=lambda rms, wave: self.ui_queue.put(("audio", rms, wave)),
        )
        self.setWindowTitle("ClapLaunch")
        self.resize(900, 790)
        self.setMinimumSize(760, 700)
        self._build_ui()
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._drain_queue)
        self.poll_timer.start(35)
        self._set_status("Ready. Configure your apps, then start listening.")
        if "--minimized" in sys.argv:
            QTimer.singleShot(250, self.hide)

    def _build_ui(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {BG}; color: {TEXT}; font-family: 'Segoe UI'; font-size: 10pt; }}
            QFrame#panel {{ background: {PANEL}; border: 1px solid #24372b; border-radius: 12px; }}
            QLabel#muted {{ color: {MUTED}; }}
            QLabel#green {{ color: {GREEN}; font-weight: 700; }}
            QLineEdit {{ background: #0b110d; border: 1px solid #2b4233; border-radius: 6px; padding: 8px; color: {TEXT}; }}
            QLineEdit:focus {{ border: 1px solid {GREEN}; }}
            QPushButton {{ background: {PANEL_2}; border: 1px solid #31513c; border-radius: 7px; padding: 9px 12px; color: {TEXT}; }}
            QPushButton:hover {{ border: 1px solid {GREEN}; color: {GREEN}; }}
            QPushButton#primary {{ background: {GREEN_DIM}; border: 1px solid {GREEN}; color: #031108; font-weight: 700; }}
            QPushButton#primary:hover {{ background: {GREEN}; }}
            QCheckBox {{ spacing: 8px; }}
            QSlider::groove:horizontal {{ background: #25372b; height: 6px; border-radius: 3px; }}
            QSlider::handle:horizontal {{ background: {GREEN}; width: 16px; margin: -5px 0; border-radius: 8px; }}
            QProgressBar {{ background: #0b110d; border: 1px solid #263c2d; border-radius: 5px; height: 10px; text-align: center; }}
            QProgressBar::chunk {{ background: {GREEN}; border-radius: 4px; }}
        """)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("CLAP<span>LAUNCH</span>")
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setStyleSheet(f"font-size: 27pt; font-weight: 800; color: {TEXT}; letter-spacing: 1px;")
        title.setText(f'CLAP<span style="color:{GREEN}">LAUNCH</span>')
        subtitle = QLabel("DOUBLE-CLAP WORKSPACE ACTIVATOR  /  LOCAL AUDIO ONLY")
        subtitle.setObjectName("muted")
        subtitle.setStyleSheet("font-size: 9pt; letter-spacing: 1px;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch()
        self.live_label = QLabel("● OFFLINE")
        self.live_label.setStyleSheet(f"color: {MUTED}; font-weight: 700; border: 1px solid #2a4031; border-radius: 10px; padding: 8px 12px;")
        header.addWidget(self.live_label, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        monitor = self._panel()
        ml = QVBoxLayout(monitor)
        top = QHBoxLayout()
        top.addWidget(self._section_title("LIVE AUDIO MONITOR"))
        top.addStretch()
        self.level_label = QLabel("INPUT  0%")
        self.level_label.setObjectName("green")
        top.addWidget(self.level_label)
        ml.addLayout(top)
        self.waveform = WaveformWidget()
        ml.addWidget(self.waveform)
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setValue(0)
        self.level_bar.setTextVisible(False)
        ml.addWidget(self.level_bar)
        note = QLabel("Waveform is visualized in memory only. Clap twice within 0.12–0.70 seconds.")
        note.setObjectName("muted")
        ml.addWidget(note)
        layout.addWidget(monitor)

        apps = self._panel()
        al = QVBoxLayout(apps)
        al.addWidget(self._section_title("WORKSPACE APPLICATIONS"))
        al.addWidget(QLabel("Choose which applications should open after a recognized double clap."))
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for row, name in enumerate(["VS Code", "Browser", "Terminal", "Spotify"]):
            lab = QLabel(name.upper())
            lab.setStyleSheet(f"color: {MUTED}; font-size: 9pt; font-weight: 700;")
            field = QLineEdit(self.config["apps"].get(name, ""))
            field.setPlaceholderText("Paste an app path or use Browse…")
            browse = QPushButton("Browse")
            browse.clicked.connect(lambda checked=False, n=name: self._browse(n))
            grid.addWidget(lab, row, 0)
            grid.addWidget(field, row, 1)
            grid.addWidget(browse, row, 2)
            self.path_fields[name] = field
        grid.setColumnStretch(1, 1)
        al.addLayout(grid)
        layout.addWidget(apps)

        controls = self._panel()
        cl = QVBoxLayout(controls)
        cl.addWidget(self._section_title("DETECTION CONTROLS"))
        sensitivity_row = QHBoxLayout()
        sensitivity_row.addWidget(QLabel("Sensitivity"))
        self.sensitivity = QSlider(Qt.Orientation.Horizontal)
        self.sensitivity.setRange(18, 30)
        current = float(self.config.get("threshold", 0.04))
        self.sensitivity.setValue(max(18, min(30, int(current * 100))))
        self.sensitivity_value = QLabel(f"{self.sensitivity.value() / 100:.2f}")
        self.sensitivity_value.setObjectName("green")
        self.sensitivity.valueChanged.connect(lambda value: self.sensitivity_value.setText(f"{value / 100:.2f}"))
        sensitivity_row.addWidget(self.sensitivity, 1)
        sensitivity_row.addWidget(self.sensitivity_value)
        cl.addLayout(sensitivity_row)
        sensitivity_note = QLabel("Higher value = less sensitive; calibration recalculates the threshold when listening starts.")
        sensitivity_note.setObjectName("muted")
        cl.addWidget(sensitivity_note)
        self.startup_check = QCheckBox("Run automatically when I sign in to Windows")
        self.startup_check.setChecked(bool(self.config.get("startup", True)))
        cl.addWidget(self.startup_check)
        buttons = QHBoxLayout()
        self.listen_button = QPushButton("▶  START LISTENING + CALIBRATE")
        self.listen_button.setObjectName("primary")
        self.listen_button.clicked.connect(self._toggle_listening)
        buttons.addWidget(self.listen_button, 2)
        save_btn = QPushButton("SAVE SETTINGS")
        save_btn.clicked.connect(self._save_settings)
        buttons.addWidget(save_btn)
        test_btn = QPushButton("TEST LAUNCH")
        test_btn.clicked.connect(self._test_launch)
        buttons.addWidget(test_btn)
        cl.addLayout(buttons)
        layout.addWidget(controls)

        status_panel = self._panel()
        sl = QVBoxLayout(status_panel)
        sl.addWidget(self._section_title("ACTIVITY"))
        self.status_label = QLabel("Ready.")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(42)
        sl.addWidget(self.status_label)
        path_label = QLabel(f"Settings: {CONFIG_PATH}")
        path_label.setObjectName("muted")
        path_label.setWordWrap(True)
        path_label.setStyleSheet("font-size: 8pt;")
        sl.addWidget(path_label)
        layout.addWidget(status_panel)
        footer = QLabel("CLAPLAUNCH  •  NO RECORDING  •  NO UPLOADS  •  WINDOWS")
        footer.setObjectName("muted")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("font-size: 8pt; letter-spacing: 1px;")
        layout.addWidget(footer)
        scroll.setWidget(root)
        self.setCentralWidget(scroll)

    def _panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        return panel

    def _section_title(self, text):
        label = QLabel(text)
        label.setObjectName("green")
        label.setStyleSheet(f"color: {GREEN}; font-size: 9pt; font-weight: 800; letter-spacing: 1px;")
        return label

    def _set_status(self, message):
        self.status_label.setText(message)

    def _drain_queue(self):
        try:
            while True:
                item = self.ui_queue.get_nowait()
                if item[0] == "status":
                    self._set_status(item[1])
                    if self.detector.running:
                        self.live_label.setText("● LISTENING")
                        self.live_label.setStyleSheet(f"color: {GREEN}; font-weight: 700; border: 1px solid {GREEN_DIM}; border-radius: 10px; padding: 8px 12px;")
                    else:
                        self.live_label.setText("● OFFLINE")
                        self.live_label.setStyleSheet(f"color: {MUTED}; font-weight: 700; border: 1px solid #2a4031; border-radius: 10px; padding: 8px 12px;")
                    if not self.detector.running:
                        self.listen_button.setText("▶  START LISTENING + CALIBRATE")
                elif item[0] == "audio":
                    rms, wave = item[1], item[2]
                    self.waveform.add_samples(wave)
                    percent = max(0, min(100, int(rms * 500)))
                    self.level_bar.setValue(percent)
                    self.level_label.setText(f"INPUT  {percent}%")
        except queue.Empty:
            pass

    def _browse(self, name):
        path, _ = QFileDialog.getOpenFileName(self, f"Choose {name} executable", "", "Applications (*.exe);;All files (*.*)")
        if path:
            self.path_fields[name].setText(path)

    def _save_settings(self, quiet=False):
        self.config["apps"] = {name: field.text().strip() for name, field in self.path_fields.items()}
        self.config["startup"] = self.startup_check.isChecked()
        self.config["threshold"] = self.sensitivity.value() / 100.0
        try:
            save_config(self.config)
            set_windows_startup(self.startup_check.isChecked())
            if not quiet:
                QMessageBox.information(self, APP_NAME, "Settings saved.")
        except Exception as exc:
            if not quiet:
                QMessageBox.warning(self, APP_NAME, f"Could not save settings/startup option:\n{exc}")

    def _test_launch(self):
        self._save_settings(quiet=True)
        self.open_configured_apps()

    def open_configured_apps(self):
        opened, errors = [], []
        for name, field in list(self.path_fields.items()):
            path = field.text().strip()
            if not path:
                continue
            try:
                launch_app(name, path)
                opened.append(name)
                time.sleep(0.25)
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        result = "Opened: " + (", ".join(opened) if opened else "no apps configured")
        if errors:
            result += "\nIssues:\n" + "\n".join(errors)
        self.ui_queue.put(("status", result))

    def _toggle_listening(self):
        if self.detector.running:
            self.detector.stop()
            self.listen_button.setText("▶  START LISTENING + CALIBRATE")
        else:
            self._save_settings(quiet=True)
            # Use the saved slider value as the baseline before calibration.
            self.detector.threshold = self.sensitivity.value() / 100.0
            self.detector.start()
            self.listen_button.setText("■  STOP LISTENING")

    def closeEvent(self, event):
        self.detector.stop()
        try:
            self._save_settings(quiet=True)
        except Exception:
            pass
        event.accept()


def main():
    if sys.platform != "win32":
        print("ClapLaunch is designed for Windows 10/11.")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = ClapLaunchWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

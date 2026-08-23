# -------------------------------------------------------------
# CRRC Puzhen Alstom Transportation Systems Limited
# PATSMET Yang Bohang
# -------------------------------------------------------------
import time
import sys
import json
import os
import math
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

# ---------- Console output encoding (Windows) ----------
# Ensure UTF-8 output even when stdout is redirected to a file/pipe,
# so Chinese text and special symbols (✓/×/²) never trigger encode errors.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ------------------ Embedded default configuration ------------------
DEFAULT_CONFIG = {
    "language": "zh",
    "speed_signal": "FCT.UIOUHMSPDD.CarSpeed",
    "brake_signal": "'MWT.MIINMIOC3.MIINMX3_MD_DI3_1",
    "min_decel": 1.48,
    "max_decel": 2.21,
    "enable_min_limit": True,
    "enable_max_limit": True,
    "decel_metric": "v2_2s",
}


def get_config_path():
    """Return the persistent configuration storage path.

    A onefile executable extracts its embedded files to a temporary ``_MEI``
    directory, so writing ``_MEI/config.json`` cannot persist. To keep the
    application as a single visible file, store the edited JSON in an NTFS
    alternate data stream attached to the exe. The stream moves with the exe
    on the same NTFS volume and does not create a separate visible file.
    """
    if getattr(sys, "frozen", False):
        internal_dir = getattr(sys, "_MEIPASS", None)
        # Preserve onedir behavior; only onefile uses the exe's data stream.
        if internal_dir and os.path.basename(os.path.normpath(internal_dir)).lower() == "_internal":
            return os.path.join(internal_dir, "config.json")
        return sys.executable + ":brake_calc_config"
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def get_embedded_config_path():
    """Return the bundled initial config used when no saved stream exists."""
    if getattr(sys, "frozen", False):
        internal_dir = getattr(sys, "_MEIPASS", None)
        if internal_dir:
            return os.path.join(internal_dir, "config.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def has_saved_config(path):
    """Check whether persistent configuration already exists."""
    try:
        with open(path, "rb"):
            return True
    except OSError:
        return False

# ------------------ Bilingual message table ------------------
MSGS = {
    "en": {
        "title": "     E M E R G E N C Y  B R A K E  C A L C U L A T O R  ",
        "version": "SW Version : 1.0 2026.08 ",
        "lang_name": "English (en)",
        "lang_warn": "         × Unknown language '{value}', using English (en).",
        "step1": "\n[Step 1] Program directory: {path}",
        "step2": "\n[Step 2] Looking for config file: {path}",
        "cfg_not_found": "         × Error: config.json not found",
        "press_exit": "\nPress Enter to exit...",
        "cfg_lang": "         ✓ Language: {name}",
        "cfg_ok_speed": "         ✓ Speed signal name: {name}",
        "cfg_ok_brake": "         ✓ Brake signal name: {name}",
        "cfg_parse_fail": "         × Config file parsing failed: {err}",
        "no_file_arg": "         × No data file received. Please drag a .txt file onto this program icon.",
        "step3": "\n[Step 3] Data file to process: {path}",
        "file_not_exist": "         × File does not exist!",
        "read_fail": "         × Unable to read file: {err}",
        "read_fail_text": "Unable to read file with any encoding: {path}",
        "need_two_rows": "         × Data file must contain at least a header row and one data row.",
        "step4": "\n[Step 4] File header (total {count} columns)",
        "time_col": "         Time column index: {idx} (first column)",
        "speed_col": "         Speed column index: {idx} (corresponding to '{name}')",
        "brake_col": "         Brake column index: {idx} (corresponding to '{name}')",
        "col_not_found": "         × Required signal column not found in header: {err}",
        "valid_rows": "         Valid data rows read: {count} rows, skipped invalid: {skipped}",
        "time_range": "         Time range: {start} ~ {end}",
        "speed_range": "         Speed range: {lo:.2f} ~ {hi:.2f} km/h",
        "no_valid_data": "         × No valid data!",
        "eb_found": "[Step 5] Found valid EB point -> index:{idx}, time:{time}, speed:{speed:.2f} km/h ",
        "eb_skipped": "\n         EB point index:{idx} speed {speed:.2f} km/h <=5, skipped, continue searching...\n",
        "eb_fallback": "\n         No EB point found, but data starts in braking state (0) with speed>5, using start as brake onset.\n",
        "eb_none": "\n         × No valid EB start found (EB point with initial speed > 5 km/h).\n",
        "step6_start": "\n[Step 6] Braking start point -> index:{idx}, time:{time}, speed:{speed:.2f} km/h",
        "end_fallback": "         Speed never dropped below 0.2 km/h, using last data point as brake end.",
        "step6_end": "         Braking end point -> index:{idx}, time:{time}, speed:{speed:.2f} km/h",
        "press_calc": "         Press Enter to start calculation...",
        "result_title": "          C A L C U L A T I O N   R E S U L T S        ",
        "data_points": "  Data points: {count}",
        "time_interval": "  Time interval: {start} ~ {end}",
        "v0": "  Initial speed: {value:.2f} km/h",
        "v_end": "  Final speed: {value:.2f} km/h",
        "brake_time": "  Braking time: {value:.4f} sec",
        "distance": "  Braking distance: {value:.3f} m",
        "rate_decel": "  Rate deceleration (dv/dt): {value}",
        "avg_decel": "  Average deceleration (V²/2S): {value}",
        "infinite_dist": "Infinite (distance zero)",
        "infinite_time": "Infinite (time zero)",
        "done": "\nProcessing complete. Press Enter to exit...",
        "press_continue": "\nPress Enter to continue...",
        # ----- Result GUI -----
        "gui_title": "Brake Test Result",
        "gui_panel_title": "Test Result Summary",
        "gui_btn_screenshot": "SAVE PICTURE",
        "gui_saved": "Screenshot saved to:\n{path}",
        "gui_save_fail": "Screenshot failed: {err}",
        "gui_no_pillow": "Pillow is not installed, cannot take a screenshot.\nPlease run:  pip install pillow",
        "plot_title": "Speed - Time Curve",
        "axis_x": "Time (HH:MM:SS.mmm)",
        "axis_y": "Speed (km/h)",
        "legend_speed": "Speed curve",
        "legend_eb": "EB signal",
        "legend_start": "Brake start",
        "legend_end": "Brake end",
        "legend_area": "Braking distance",
        "lbl_v0": "Initial speed v0",
        "lbl_vend": "Final speed v_end",
        "lbl_dt": "Interval Δt",
        "lbl_dist": "Distance S",
        "gui_file": "Data file",
        "gui_label_points": "Data points",
        "gui_label_interval": "Time interval",
        "gui_label_v0": "Initial speed",
        "gui_label_vend": "Final speed",
        "gui_label_time": "Braking time",
        "gui_label_dist": "Braking distance",
        "gui_label_rate": "Rate deceleration (dv/dt)",
        "gui_label_avg": "Average deceleration (V²/2S)",
        "gui_pass": "PASS",
        "gui_fail": "FAIL",
        "gui_req": "Requirement: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "(no limit)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        # ----- Config GUI -----
        "config_title": "Configuration Setup",
        "config_prompt": "Please select an option:",
        "config_saved": "Configuration saved successfully.",
        "config_cancelled": "Configuration cancelled.",
        "config_overlimit": "Configuration out of range",
        "config_lbl_language": "Language:",
        "config_lbl_speed": "Speed Signal:",
        "config_lbl_brake": "Brake Signal:",
        "config_lbl_min": "Min Decel (m/s\²):",
        "config_lbl_max": "Max Decel (m/s\²):",
        "config_lbl_enable_min": "Enable Min Limit:",
        "config_lbl_enable_max": "Enable Max Limit:",
        "config_lbl_metric": "Evaluation Metric:",
        "config_btn_save": "Save",
        "config_btn_cancel": "Cancel",
        "config_opt_yes": "Yes",
        "config_opt_no": "No",
        "config_overlimit_msg": "Configuration out of range: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "Please select an option:",
        "menu_opt1": "1. Open data file",
        "menu_opt2": "2. Configure settings",
        "menu_opt3": "3. Exit",
        "menu_prompt": "Enter your choice (1-3): ",
        "menu_invalid": "Invalid choice, please try again.",
        "file_dialog_title": "Select data file",
        "file_filter": "Text files (*.txt)|*.txt|All files (*.*)|*.*",
        "no_file_selected": "No file selected.",
    },
    "zh": {
        "title": "            紧 急 制 动 计 算 器  ",
        "version": "软件版本 : 1.0 2026.08 ",
        "lang_name": "中文 (zh)",
        "lang_warn": "         × 未知语言“{value}”，已使用英文（en）。",
        "step1": "\n[步骤 1] 程序目录：{path}",
        "step2": "\n[步骤 2] 正在查找配置文件：{path}",
        "cfg_not_found": "         × 错误：未找到 config.json",
        "press_exit": "\n按回车键退出...",
        "cfg_lang": "         ✓ 语言：{name}",
        "cfg_ok_speed": "         ✓ 速度信号名称：{name}",
        "cfg_ok_brake": "         ✓ 制动信号名称：{name}",
        "cfg_parse_fail": "         × 配置文件解析失败：{err}",
        "no_file_arg": "         × 未收到数据文件，请将 .txt 文件拖放到本程序图标上。",
        "step3": "\n[步骤 3] 待处理的数据文件：{path}",
        "file_not_exist": "         × 文件不存在！",
        "read_fail": "         × 无法读取文件：{err}",
        "read_fail_text": "无法用任何编码读取文件：{path}",
        "need_two_rows": "         × 数据文件必须至少包含一行表头和一行数据。",
        "step4": "\n[步骤 4] 文件表头（共 {count} 列）",
        "time_col": "         时间列索引：{idx}（第一列）",
        "speed_col": "         速度列索引：{idx}（对应 '{name}'）",
        "brake_col": "         制动列索引：{idx}（对应 '{name}'）",
        "col_not_found": "         × 表头中未找到所需信号列：{err}",
        "valid_rows": "         读取的有效数据行：{count} 行，跳过无效：{skipped}",
        "time_range": "         时间范围：{start} ~ {end}",
        "speed_range": "         速度范围：{lo:.2f} ~ {hi:.2f} km/h",
        "no_valid_data": "         × 没有有效数据！",
        "eb_found": "[步骤 5] 找到有效的 EB 点 -> 索引:{idx}, 时间:{time}, 速度:{speed:.2f} km/h ",
        "eb_skipped": "\n         EB 点索引:{idx} 速度 {speed:.2f} km/h <=5，已跳过，继续搜索...\n",
        "eb_fallback": "\n         未找到 EB 点，但数据从制动状态（0）开始且速度>5，使用起点作为制动开始点。\n",
        "eb_none": "\n         × 未找到有效的 EB 起点（初始速度 > 5 km/h 的 EB 点）。\n",
        "step6_start": "\n[步骤 6] 制动起始点 -> 索引:{idx}, 时间:{time}, 速度:{speed:.2f} km/h",
        "end_fallback": "         速度未降至 0.2 km/h 以下，使用最后一个数据点作为制动结束点。",
        "step6_end": "         制动结束点 -> 索引:{idx}, 时间:{time}, 速度:{speed:.2f} km/h",
        "press_calc": "         按回车键开始计算...",
        "result_title": "            计 算 结 果        ",
        "data_points": "  数据点数量：{count}",
        "time_interval": "  时间区间：{start} ~ {end}",
        "v0": "  初始速度：{value:.2f} km/h",
        "v_end": "  末速度：{value:.2f} km/h",
        "brake_time": "  制动时间：{value:.4f} 秒",
        "distance": "  制动距离：{value:.3f} 米",
        "rate_decel": "  减速速率（dv/dt）：{value}",
        "avg_decel": "  平均减速度（V²/2S）：{value}",
        "infinite_dist": "无穷大（距离为零）",
        "infinite_time": "无穷大（时间为零）",
        "done": "\n处理完成，按回车键退出...",
        "press_continue": "\n按回车键继续...",
        # ----- 结果 GUI -----
        "gui_title": "制动测试结果",
        "gui_panel_title": "测试结果总结",
        "gui_btn_screenshot": "保存截图",
        "gui_saved": "截图已保存至：\n{path}",
        "gui_save_fail": "截图失败：{err}",
        "gui_no_pillow": "未安装 Pillow，无法截图。\n请在命令行执行：pip install pillow",
        "plot_title": "速度 - 时间曲线",
        "axis_x": "时间 (HH:MM:SS.mmm)",
        "axis_y": "速度 (km/h)",
        "legend_speed": "速度曲线",
        "legend_eb": "EB 信号",
        "legend_start": "制动开始点",
        "legend_end": "制动结束点",
        "legend_area": "制动距离",
        "lbl_v0": "初始速度 v0",
        "lbl_vend": "结束速度 v_end",
        "lbl_dt": "间隔时间 Δt",
        "lbl_dist": "距离 S",
        "gui_file": "数据文件",
        "gui_label_points": "数据点数量",
        "gui_label_interval": "时间区间",
        "gui_label_v0": "初始速度",
        "gui_label_vend": "结束速度",
        "gui_label_time": "制动时间",
        "gui_label_dist": "制动距离",
        "gui_label_rate": "减速速率 (dv/dt)",
        "gui_label_avg": "平均减速度 (V²/2S)",
        "gui_pass": "通过",
        "gui_fail": "不通过",
        "gui_req": "测试要求：{cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "（无限制）",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        # ----- 配置 GUI -----
        "config_title": "配置设置",
        "config_prompt": "请选择操作：",
        "config_saved": "配置已成功保存。",
        "config_cancelled": "配置已取消。",
        "config_overlimit": "配置超限",
        "config_lbl_language": "语言：",
        "config_lbl_speed": "速度信号：",
        "config_lbl_brake": "制动信号：",
        "config_lbl_min": "最小减速度 (m/s²)：",
        "config_lbl_max": "最大减速度 (m/s²)：",
        "config_lbl_enable_min": "启用最小值限制：",
        "config_lbl_enable_max": "启用最大值限制：",
        "config_lbl_metric": "考核指标：",
        "config_btn_save": "保存",
        "config_btn_cancel": "取消",
        "config_opt_yes": "是",
        "config_opt_no": "否",
        "config_overlimit_msg": "配置超限：最小减速度 >= 0，最大减速度 > 0，且最小减速度 <= 最大减速度。",
        "menu_title": "请选择操作：",
        "menu_opt1": "1. 打开数据文件",
        "menu_opt2": "2. 配置信息",
        "menu_opt3": "3. 退出",
        "menu_prompt": "请输入选择 (1-3): ",
        "menu_invalid": "无效选择，请重新输入。",
        "file_dialog_title": "选择数据文件",
        "file_filter": "文本文件 (*.txt)|*.txt|所有文件 (*.*)|*.*",
        "no_file_selected": "未选择文件。",
    },
}

# ------------------ Language resolution ------------------
def resolve_language(cfg_lang):
    """Return 'zh' or 'en' from a config language value (case-insensitive)."""
    if not cfg_lang:
        return "en"
    lang = str(cfg_lang).strip().lower()
    if lang in ("zh", "cn", "chinese", "zh-cn", "中文"):
        return "zh"
    return "en"

# ------------------ Message helper ------------------
def msg(lang, key, **kwargs):
    """Fetch a localized string and format placeholders if any."""
    table = MSGS.get(lang, MSGS["en"])
    text = table.get(key, MSGS["en"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text

# ------------------ Safe file reading ------------------
def safe_read_file(file_path, err_text, encodings=('utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'latin-1')):
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(err_text)



# ------------------ Format total seconds as HH:MM:SS.mmm ------------------
def format_time(seconds):
    """Format seconds as HH:MM:SS.mmm string"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

# -------------------------------------------------------------
# Result GUI window (pure tkinter, no external dependencies).
# -------------------------------------------------------------
try:
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import messagebox, filedialog
    _TK_AVAILABLE = True
except Exception:
    _TK_AVAILABLE = False


def _ui_font(lang, size=10, bold=False):
    """Pick a font family that renders well on Windows for the active language."""
    family = "Microsoft YaHei UI" if lang == "zh" else "Segoe UI"
    return (family, size, "bold" if bold else "normal")


def _nice_step(span, n):
    """Return a 'nice' tick step so the axis gets about n ticks."""
    if span <= 0:
        return 1.0
    raw = span / max(n, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def _ticks(lo, hi, n=6):
    """Return tick values between lo and hi with a nice step."""
    step = _nice_step(hi - lo, n)
    start = math.ceil(lo / step) * step
    out = []
    val = start
    while val <= hi + 1e-9:
        out.append(val)
        val += step
    return out


def _smooth_curve(pts, samples=8):
    """Return a smoothed point list (Catmull-Rom spline) passing through pts.

    pts: list of (x, y) pixel coordinates, ordered left to right.
    """
    n = len(pts)
    if n < 3:
        return pts
    out = []
    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else p2
        for s in range(samples):
            u = s / samples
            u2 = u * u
            u3 = u2 * u
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * u
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * u2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * u3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * u
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * u2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * u3)
            out.append((x, y))
    out.append(pts[-1])
    return out


def _decimate_8(pts):
    """Take every 8th point (first of each group of 8 identical speed values).

    pts: list of (x, y) pixel coordinates, ordered left to right.
    Returns decimated point list.
    """
    if len(pts) < 8:
        return pts
    return pts[::8]


def get_desktop_path():
    """Resolve the real Desktop folder (handles OneDrive redirection / localized names)."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders") as key:
                p = winreg.QueryValueEx(key, "Desktop")[0]
                if p and os.path.isdir(p):
                    return p
        except Exception:
            pass
    home = Path.home()
    for cand in (home / "Desktop", home / "OneDrive" / "Desktop", home / "桌面"):
        if cand.is_dir():
            return str(cand)
    return str(home)


def hide_console():
    """Hide the console window on Windows so only the GUI stays visible."""
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
        except Exception:
            pass


class PlotWidget(tk.Canvas):
    """Canvas that draws the speed curve + EB signal with pure tkinter primitives."""

    PAD_L, PAD_R, PAD_T, PAD_B = 66, 16, 46, 50

    def __init__(self, master, lang, ctx, **kw):
        kw.setdefault("bg", "white")
        kw.setdefault("highlightthickness", 0)
        super().__init__(master, **kw)
        self.lang = lang
        self.ctx = ctx
        self.bind("<Configure>", lambda e: self.redraw())

    @staticmethod
    def _text_w(text, font):
        try:
            return tkfont.Font(font=font).measure(text)
        except Exception:
            return len(text) * 8.0

    def _tag(self, x, y, text, color, font, anchor="nw", pad=5):
        """Draw a white box + colored text (annotation helper)."""
        w = self._text_w(text, font) + pad * 2
        fh = 18
        if anchor == "nw":
            box, tx, ty, ta = (x, y, x + w, y + fh), x + pad, y + fh / 2, "w"
        elif anchor == "ne":
            box, tx, ty, ta = (x - w, y, x, y + fh), x - pad, y + fh / 2, "e"
        else:
            box, tx, ty, ta = (x - w / 2, y - fh / 2, x + w / 2, y + fh / 2), x, y, "center"
        self.create_rectangle(box, fill="#FFFFFF", outline="#BFBFBF", width=1)
        self.create_text(tx, ty, text=text, anchor=ta, fill=color, font=font)

    # ------------------------------------------------------------------
    def redraw(self):
        self.delete("all")
        c = self.ctx
        w, h = self.winfo_width(), self.winfo_height()
        if w < 80 or h < 80:
            return
        lang = self.lang
        T = MSGS.get(lang, MSGS["en"])

        pl, pr, pt, pb = self.PAD_L, self.PAD_R, self.PAD_T, self.PAD_B
        ax_l, ax_r = pl, w - pr
        ax_t, ax_b = pt, h - pb
        pw, ph = ax_r - ax_l, ax_b - ax_t

        t, v, br = c["times"], c["speeds"], c["brakes"]
        si, ei = c["start_idx"], c["end_idx"]
        t_s, t_e = t[si], t[ei]

        # Visible window: 2 s before the trigger to 2 s after the
        # first point below 5 km/h (clamped to the data range).
        speed_below_5_idx = next(
            (i for i in range(si, len(v)) if v[i] < 5.0),
            len(v) - 1,
        )
        t_lo = max(t[0], t_s - 1.0)
        t_hi = min(t[-1], t[speed_below_5_idx] + 1.0)
        if t_hi <= t_lo:
            t_hi = min(t[-1], t_lo + 1.0)
        vis = [i for i in range(len(t)) if t_lo - 1e-9 <= t[i] <= t_hi + 1e-9]
        if not vis:
            return
        v_vis = [v[i] for i in vis]
        v_min = min(0.0, min(v_vis)) - 3.0
        v_max = max(v_vis) + 8.0

        def X(ts):
            return ax_l + (ts - t_lo) / (t_hi - t_lo) * pw

        def Y(vs):
            return ax_b - (vs - v_min) / (v_max - v_min) * ph

        small = ("Segoe UI", 8)

        # ---------- grid ----------
        for tkx in _ticks(t_lo, t_hi, 7):
            self.create_line(X(tkx), ax_t, X(tkx), ax_b, fill="#EBEBEB")
        for tkv in _ticks(v_min, v_max, 6):
            self.create_line(ax_l, Y(tkv), ax_r, Y(tkv), fill="#EBEBEB")

        # ---------- EB signal band (top strip) ----------
        band_h = max(16.0, ph * 0.09)
        band_b = ax_t + band_h
        self.create_rectangle(ax_l, ax_t, ax_r, band_b, fill="#F7F7F7", outline="#CCCCCC")
        eb0 = ax_t + band_h * 0.72   # EB = 0 -> braking applied (top)
        eb1 = ax_t + band_h * 0.30   # EB = 1 -> no brake (bottom)
        px_, py_ = None, None
        for i in vis:
            yv = eb1 if br[i] >= 0.5 else eb0
            xv = X(t[i])
            if px_ is not None:
                self.create_line(px_, py_, xv, py_, fill="#D35400", width=2)
                if abs(py_ - yv) > 1e-6:
                    self.create_line(xv, py_, xv, yv, fill="#D35400", width=2)
            px_, py_ = xv, yv
        self.create_text(ax_l + 6, (ax_t + band_b) / 2, text="EB", anchor="w",
                         fill="#8A5A00", font=("Segoe UI", 8, "bold"))

        # ---------- compute smoothed speed curve (once, shared) ----------
        raw_pts = [(X(t[i]), Y(v[i])) for i in vis]
        dec_pts = _decimate_8(raw_pts)
        smooth_pts = _smooth_curve(dec_pts, samples=8)

        # pre-compute dashed-line positions (used by areas below)
        col_s, col_e = "#C0392B", "#27AE60"
        x_s, x_e = X(t_s), X(t_e)

        # ---------- green area: from curve start to braking start ----------
        green_color = "#A8E6CF"
        green_poly = []
        for p in smooth_pts:
            if p[0] <= x_s + 1e-6:
                green_poly.append(p)
            else:
                break
        if green_poly:
            green_poly.append((x_s, Y(0.0)))
            green_poly.append((green_poly[0][0], Y(0.0)))
            flat_g = [crd for p in green_poly for crd in p]
            self.create_polygon(flat_g, fill=green_color, outline="")

        # ---------- yellow area: from braking start to braking end ----------
        yellow_color = "#FFE66D"
        yellow_poly = []
        started = False
        for p in smooth_pts:
            if not started and p[0] >= x_s - 1e-6:
                started = True
            if started:
                if p[0] <= x_e + 1e-6:
                    yellow_poly.append(p)
                else:
                    break
        if yellow_poly:
            yellow_poly.append((x_e, Y(0.0)))
            yellow_poly.append((x_s, Y(0.0)))
            flat_y = [crd for p in yellow_poly for crd in p]
            self.create_polygon(flat_y, fill=yellow_color, outline="")

        # ---------- speed curve (decimated + smoothed) ----------
        pts = [crd for p in smooth_pts for crd in p]
        self.create_line(pts, fill="#1F77B4", width=2)

        # ---------- dashed start / end lines ----------
        self.create_line(x_s, ax_t, x_s, ax_b, fill=col_s, dash=(5, 3), width=1.6)
        self.create_line(x_e, ax_t, x_e, ax_b, fill=col_e, dash=(5, 3), width=1.6)

        # ---------- annotations ----------
        bold = _ui_font(lang, 10, True)

        # bottom arrow Y position (used by final speed and interval labels)
        ay = ax_b - 22

        # initial speed (left edge aligned with start line, above curve)
        txt = T["lbl_v0"] + " = " + f"{c['v0_kmh']:.2f} km/h"
        y0t = Y(c["speeds"][si]) - 38
        if y0t < ax_t + band_h + 4:
            y0t = ax_t + band_h + 4
        self._tag(x_s, y0t, txt, col_s, bold, "nw")

        # final speed (right edge aligned with end line, below arrow)
        txt = T["lbl_vend"] + " = " + f"{c['v_end_kmh']:.2f} km/h"
        self._tag(x_e, ay + 3, txt, col_e, bold, "ne")

        # interval time (double arrow between the two dashed lines)
        self.create_line(x_s, ay, x_e, ay, fill="#37474F", width=1.4,
                         arrow="both", arrowshape=(8, 10, 4))
        txt = T["lbl_dt"] + " = " + f"{c['brake_time']:.2f} s"
        self._tag((x_s + x_e) / 2, ay - 28, txt, "#37474F", bold, "center")

        # distance value inside the yellow area
        t_mid = (t_s + t_e) / 2.0
        v_mid = v[ei]
        for i in range(si, ei):
            if t[i] <= t_mid <= t[i + 1]:
                f_ = (t_mid - t[i]) / (t[i + 1] - t[i])
                v_mid = v[i] + f_ * (v[i + 1] - v[i])
                break
        txt = T["lbl_dist"] + " = " + f"{c['distance']:.3f} m"
        self._tag(X(t_mid), (Y(v_mid) + Y(0.0)) / 2.0, txt, "#7A5C00", bold, "center")

        # ---------- legend (top-right) ----------
        legend = [
            ("#1F77B4", "line", T["legend_speed"]),
            ("#D35400", "line", T["legend_eb"]),
            (col_s, "dash", T["legend_start"]),
            (col_e, "dash", T["legend_end"]),
            (yellow_color, "rect", T["legend_area"]),
        ]
        lf = ("Segoe UI", 9)
        rx = ax_r - 10
        maxw = max(24 + self._text_w(lbl, lf) for _, _, lbl in legend)
        lx0 = rx - maxw
        ly = ax_t + band_h + 10
        for (color, kind, lbl) in legend:
            if kind == "line":
                self.create_line(lx0 + 2, ly + 9, lx0 + 20, ly + 9, fill=color, width=2.4)
            elif kind == "dash":
                self.create_line(lx0 + 2, ly + 9, lx0 + 20, ly + 9, fill=color, width=1.8, dash=(4, 3))
            else:
                self.create_rectangle(lx0 + 2, ly + 3, lx0 + 20, ly + 15,
                                      fill=color, outline="#B8A84A", width=1)
            self.create_text(lx0 + 26, ly + 9, text=lbl, anchor="w", fill="#333333", font=lf)
            ly += 19

        # ---------- axes, ticks, labels ----------
        self.create_rectangle(ax_l, ax_t, ax_r, ax_b, outline="#555555", width=1.1)
        for tkx in _ticks(t_lo, t_hi, 5):
            self.create_text(X(tkx), ax_b + 14, text=format_time(tkx), font=small, fill="#444444")
        step_y = _nice_step(v_max - v_min, 6)
        for tkv in _ticks(v_min, v_max, 6):
            fmt = f"{tkv:.0f}" if step_y >= 1 else f"{tkv:.1f}"
            self.create_text(ax_l - 7, Y(tkv), text=fmt, font=small, fill="#444444", anchor="e")
        self.create_text((ax_l + ax_r) / 2, 18, text=T["plot_title"],
                         font=_ui_font(lang, 12, True), fill="#222222")
        self.create_text((ax_l + ax_r) / 2, h - 9, text=T["axis_x"],
                         font=_ui_font(lang, 9), fill="#333333")
        self.create_text(13, (ax_t + ax_b) / 2, text=T["axis_y"], angle=90,
                         font=_ui_font(lang, 9), fill="#333333")


def take_screenshot(root, lang, btn=None):
    """Capture the whole result window and save it to the Desktop.
    If btn is provided, it is hidden during capture so it does not appear in the screenshot."""
    T = MSGS.get(lang, MSGS["en"])
    try:
        from PIL import ImageGrab
    except Exception:
        messagebox.showwarning(T["gui_title"], T["gui_no_pillow"])
        return
    try:
        if btn:
            btn.pack_forget()
            root.update()
            root.update_idletasks()
        x0 = root.winfo_rootx(); y0 = root.winfo_rooty()
        x1 = x0 + root.winfo_width(); y1 = y0 + root.winfo_height()
        img = ImageGrab.grab(bbox=(x0, y0, x1, y1))
        if btn:
            btn.pack(side="right")
            root.update_idletasks()
        desk = get_desktop_path()
        fname = os.path.join(desk, "brake_result_" + time.strftime("%Y%m%d_%H%M%S") + ".png")
        img.save(fname)
        messagebox.showinfo(T["gui_title"], msg(lang, "gui_saved", path=fname))
    except Exception as e:
        if btn:
            btn.pack(side="right")
        messagebox.showerror(T["gui_title"], msg(lang, "gui_save_fail", err=e))


def show_result_gui(lang, ctx):
    """Open the result window: left = summary, right = plot, top-right = screenshot.

    Returns True if the GUI was shown (the console is hidden in that case),
    False if tkinter is unavailable (console flow keeps running).
    """
    if not _TK_AVAILABLE:
        print("         [GUI] tkinter not available, skipping result window.")
        return False
    T = MSGS.get(lang, MSGS["en"])

    # Window title: "Emergency Brake Test Result + filename" (no .txt)
    file_name = ctx.get("file_name") or ""
    if file_name.lower().endswith(".txt"):
        file_name = file_name[:-4]
    win_title = T["gui_title"] + ("  " + file_name if file_name else "")
    console_title = T["title"].strip() + ("  " + file_name if file_name else "")

    root = tk.Tk()
    root.title(console_title)
    root.geometry("960x600")
    root.minsize(960, 600)
    root.configure(bg="#F0F2F5")

    # ----- header: title + save-picture button (top-right, default Windows style) -----
    header = tk.Frame(root, bg="#F0F2F5")
    header.pack(side="top", fill="x", padx=12, pady=(10, 6))
    tk.Label(header, text=win_title, font=_ui_font(lang, 14, True),
             bg="#F0F2F5", fg="#1F2937").pack(side="left")
    btn_screenshot = tk.Button(header, text=T["gui_btn_screenshot"], font=_ui_font(lang, 11),
                              width=14, height=1, command=lambda: take_screenshot(root, lang, btn_screenshot))
    btn_screenshot.pack(side="right")

    # ----- content: left summary, right plot -----
    content = tk.Frame(root, bg="#F0F2F5")
    content.pack(side="top", fill="both", expand=True, padx=12, pady=(0, 12))
    content.rowconfigure(0, weight=1)
    content.columnconfigure(1, weight=1)

    # left: summary panel
    left = tk.Frame(content, bg="#FFFFFF", highlightbackground="#D8DCE2", highlightthickness=1)
    left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
    left.configure(width=340)
    left.grid_propagate(False)
    tk.Label(left, text=T["gui_panel_title"], font=_ui_font(lang, 12, True),
             bg="#FFFFFF", fg="#1F2937", anchor="w").pack(fill="x", padx=16, pady=(14, 10))
    rows = [
        (T["gui_file"], ctx.get("file_name", "")),
        (T["gui_label_points"], f"{ctx['count']}"),
        (T["gui_label_interval"], ctx.get("interval_str", "")),
        (T["gui_label_v0"], f"{ctx['v0_kmh']:.2f} km/h"),
        (T["gui_label_vend"], f"{ctx['v_end_kmh']:.2f} km/h"),
        (T["gui_label_time"], f"{ctx['brake_time']:.4f} s"),
        (T["gui_label_dist"], f"{ctx['distance']:.3f} m"),
        (T["gui_label_rate"], ctx.get("rate_decel_str", "")),
        (T["gui_label_avg"], ctx.get("avg_decel_str", "")),
    ]
    body = tk.Frame(left, bg="#FFFFFF")
    body.pack(fill="both", expand=True, padx=16, pady=(0, 12))
    for i, (lab, val) in enumerate(rows):
        tk.Label(body, text=lab, font=_ui_font(lang, 10), bg="#FFFFFF", fg="#6B7280",
                 anchor="w").grid(row=i, column=0, sticky="w", pady=5, padx=(0, 10))
        tk.Label(body, text=val, font=_ui_font(lang, 10, True), bg="#FFFFFF", fg="#111827",
                 anchor="w", justify="left", wraplength=180).grid(row=i, column=1, sticky="ew", pady=5)
    body.columnconfigure(1, weight=1)

    # ----- PASS / FAIL result -----
    passed = ctx.get("passed", False)
    minv = ctx.get("min_decel", 1.48)
    maxv = ctx.get("max_decel", 2.21)
    en_min = ctx.get("enable_min_limit", True)
    en_max = ctx.get("enable_max_limit", True)
    metric_key = "metric_v2_2s" if ctx.get("decel_metric", "v2_2s") == "v2_2s" else "metric_dv_dt"
    metric_name = T[metric_key]
    result_text = T["gui_pass"] if passed else T["gui_fail"]
    result_color = "#27AE60" if passed else "#C0392B"

    if en_min and en_max:
        cond = msg(lang, "gui_req_both", metric=metric_name, minv=minv, maxv=maxv)
    elif en_min:
        cond = msg(lang, "gui_req_min_only", metric=metric_name, minv=minv)
    elif en_max:
        cond = msg(lang, "gui_req_max_only", metric=metric_name, maxv=maxv)
    else:
        cond = T["gui_req_none"]
    req_text = msg(lang, "gui_req", cond=cond)

    result_frame = tk.Frame(left, bg="#FFFFFF")
    result_frame.pack(fill="x", padx=16, pady=(0, 16), side="bottom")
    tk.Label(result_frame, text=result_text, font=_ui_font(lang, 20, True),
             bg="#FFFFFF", fg=result_color).pack(anchor="w")
    tk.Label(result_frame, text=req_text, font=_ui_font(lang, 9),
             bg="#FFFFFF", fg="#6B7280").pack(anchor="w", pady=(2, 0))

    # right: plot panel
    plot_frame = tk.Frame(content, bg="#FFFFFF", highlightbackground="#D8DCE2", highlightthickness=1)
    plot_frame.grid(row=0, column=1, sticky="nsew")
    plot_frame.rowconfigure(0, weight=1)
    plot_frame.columnconfigure(0, weight=1)
    plot = PlotWidget(plot_frame, lang, ctx)
    plot.grid(row=0, column=0, sticky="nsew")

    root.bind("<Control-s>", lambda e: take_screenshot(root, lang, btn_screenshot))
    root.bind("<F12>", lambda e: take_screenshot(root, lang, btn_screenshot))
    # Console auto-closes as soon as the GUI appears; only the GUI stays visible.
    hide_console()
    root.mainloop()
    return True



def show_config_gui(lang, current_config):
    """Open a configuration GUI window.
    Returns the new config dict if saved, None if cancelled.
    """
    if not _TK_AVAILABLE:
        print("         [GUI] tkinter not available, cannot open config window.")
        return None
    T = MSGS.get(lang, MSGS["en"])

    result = {"config": None}

    def on_save():
        new_lang = lang_var.get()
        speed = speed_var.get().strip()
        brake = brake_var.get().strip()
        min_str = min_var.get().strip()
        max_str = max_var.get().strip()
        en_min = enable_min_var.get()
        en_max = enable_max_var.get()
        metric = metric_var.get()

        if not speed or not brake:
            messagebox.showwarning(T["config_title"], T.get("config_overlimit_msg", "Configuration out of range"))
            return

        try:
            min_val = float(min_str)
            max_val = float(max_str)
        except ValueError:
            messagebox.showwarning(T["config_title"], T["config_overlimit"])
            return

        if min_val < 0 or max_val <= 0 or min_val > max_val:
            messagebox.showwarning(T["config_title"], T["config_overlimit"])
            return

        result["config"] = {
            "language": new_lang,
            "speed_signal": speed,
            "brake_signal": brake,
            "min_decel": min_val,
            "max_decel": max_val,
            "enable_min_limit": en_min,
            "enable_max_limit": en_max,
            "decel_metric": metric,
        }
        root.destroy()

    def on_cancel():
        result["config"] = None
        root.destroy()

    root = tk.Tk()
    root.title(T["config_title"])
    # The form has eight rows; leave a dedicated area for the buttons.
    root.geometry("560x620")
    root.resizable(False, False)
    root.configure(bg="#F0F2F5")

    header = tk.Frame(root, bg="#F0F2F5")
    header.pack(side="top", fill="x", padx=12, pady=(10, 6))
    tk.Label(header, text=T["config_title"], font=_ui_font(lang, 14, True),
             bg="#F0F2F5", fg="#1F2937").pack(side="left")

    content = tk.Frame(root, bg="#FFFFFF", highlightbackground="#D8DCE2", highlightthickness=1)
    # Do not let the expanding form consume the button bar's height.
    content.pack(side="top", fill="both", expand=True, padx=12, pady=(0, 6))

    cfg = current_config if current_config else DEFAULT_CONFIG

    lang_var = tk.StringVar(value=cfg.get("language", "zh"))
    speed_var = tk.StringVar(value=cfg.get("speed_signal", ""))
    brake_var = tk.StringVar(value=cfg.get("brake_signal", ""))
    min_var = tk.StringVar(value=str(cfg.get("min_decel", 1.48)))
    max_var = tk.StringVar(value=str(cfg.get("max_decel", 2.21)))
    enable_min_var = tk.BooleanVar(value=bool(cfg.get("enable_min_limit", True)))
    enable_max_var = tk.BooleanVar(value=bool(cfg.get("enable_max_limit", True)))
    metric_var = tk.StringVar(value=str(cfg.get("decel_metric", "v2_2s")))

    font_label = _ui_font(lang, 10)
    font_input = _ui_font(lang, 10)

    row = 0
    pad_y = 14

    # Language - option (dropdown)
    tk.Label(content, text=T["config_lbl_language"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="w").grid(row=row, column=0, sticky="w", padx=(20, 10), pady=pad_y)
    lang_combo = tk.OptionMenu(content, lang_var, "zh", "en")
    lang_combo.config(font=font_input, width=18)
    lang_combo.grid(row=row, column=1, sticky="w", padx=(0, 20), pady=pad_y)
    row += 1

    # Speed signal - input
    tk.Label(content, text=T["config_lbl_speed"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="w").grid(row=row, column=0, sticky="w", padx=(20, 10), pady=pad_y)
    tk.Entry(content, textvariable=speed_var, font=font_input, width=30).grid(row=row, column=1, sticky="ew", padx=(0, 20), pady=pad_y)
    row += 1

    # Brake signal - input
    tk.Label(content, text=T["config_lbl_brake"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="w").grid(row=row, column=0, sticky="w", padx=(20, 10), pady=pad_y)
    tk.Entry(content, textvariable=brake_var, font=font_input, width=30).grid(row=row, column=1, sticky="ew", padx=(0, 20), pady=pad_y)
    row += 1

    # Min decel - input
    tk.Label(content, text=T["config_lbl_min"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="w").grid(row=row, column=0, sticky="w", padx=(20, 10), pady=pad_y)
    tk.Entry(content, textvariable=min_var, font=font_input, width=20).grid(row=row, column=1, sticky="w", padx=(0, 20), pady=pad_y)
    row += 1

    # Max decel - input
    tk.Label(content, text=T["config_lbl_max"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="w").grid(row=row, column=0, sticky="w", padx=(20, 10), pady=pad_y)
    tk.Entry(content, textvariable=max_var, font=font_input, width=20).grid(row=row, column=1, sticky="w", padx=(0, 20), pady=pad_y)
    row += 1

    # Enable min limit - option (radio)
    tk.Label(content, text=T["config_lbl_enable_min"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="w").grid(row=row, column=0, sticky="w", padx=(20, 10), pady=pad_y)
    min_frame = tk.Frame(content, bg="#FFFFFF")
    min_frame.grid(row=row, column=1, sticky="w", padx=(0, 20), pady=pad_y)
    tk.Radiobutton(min_frame, text=T["config_opt_yes"], variable=enable_min_var, value=True,
                   font=font_input, bg="#FFFFFF").pack(side="left", padx=(0, 15))
    tk.Radiobutton(min_frame, text=T["config_opt_no"], variable=enable_min_var, value=False,
                   font=font_input, bg="#FFFFFF").pack(side="left")
    row += 1

    # Enable max limit - option (radio)
    tk.Label(content, text=T["config_lbl_enable_max"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="w").grid(row=row, column=0, sticky="w", padx=(20, 10), pady=pad_y)
    max_frame = tk.Frame(content, bg="#FFFFFF")
    max_frame.grid(row=row, column=1, sticky="w", padx=(0, 20), pady=pad_y)
    tk.Radiobutton(max_frame, text=T["config_opt_yes"], variable=enable_max_var, value=True,
                   font=font_input, bg="#FFFFFF").pack(side="left", padx=(0, 15))
    tk.Radiobutton(max_frame, text=T["config_opt_no"], variable=enable_max_var, value=False,
                   font=font_input, bg="#FFFFFF").pack(side="left")
    row += 1

    # Evaluation metric - option (dropdown)
    tk.Label(content, text=T["config_lbl_metric"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="w").grid(row=row, column=0, sticky="w", padx=(20, 10), pady=pad_y)
    metric_combo = tk.OptionMenu(content, metric_var, "v2_2s", "dv_dt")
    metric_combo.config(font=font_input, width=18)
    metric_combo.grid(row=row, column=1, sticky="w", padx=(0, 20), pady=pad_y)
    row += 1

    content.columnconfigure(1, weight=1)

    # Button bar: pack it explicitly at the bottom so it cannot be pushed
    # outside the window by the expanding form above.
    btn_frame = tk.Frame(root, bg="#F0F2F5", height=58)
    btn_frame.pack(side="bottom", fill="x", padx=12, pady=(0, 12))
    btn_frame.pack_propagate(False)

    btn_save = tk.Button(btn_frame, text=T["config_btn_save"], font=_ui_font(lang, 11),
                         width=12, height=1, command=on_save)
    btn_save.pack(side="right", padx=(6, 0))

    btn_cancel = tk.Button(btn_frame, text=T["config_btn_cancel"], font=_ui_font(lang, 11),
                           width=12, height=1, command=on_cancel)
    btn_cancel.pack(side="right", padx=(0, 6))

    root.protocol("WM_DELETE_WINDOW", on_cancel)

    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    root.geometry(f"+{x}+{y}")

    root.mainloop()
    return result["config"]

def main():
    # ---------- 0. Determine script directory ----------
    if getattr(sys, 'frozen', False):
        script_dir = Path(sys.executable).parent
    else:
        script_dir = Path(__file__).parent
    config_path = get_config_path()

    # ---------- 1. Pre-read config to determine language ----------
    config = None
    config_error = None
    try:
        # In onefile mode, load the saved NTFS stream first. If it does not
        # exist yet, fall back to the config.json bundled inside the exe.
        read_path = config_path
        if getattr(sys, "frozen", False) and not has_saved_config(config_path):
            read_path = get_embedded_config_path()
        config_text = safe_read_file(read_path, msg("en", "read_fail_text", path=read_path))
        # Strip // comments from JSON before parsing
        config_text = re.sub(r'//.*', '', config_text)
        config = json.loads(config_text)
    except Exception as e:
        config_error = e

    if config is None:
        # Config file not found or parse error - use defaults
        config = dict(DEFAULT_CONFIG)
        if config_path and os.path.exists(config_path):
            lang = resolve_language(config.get("language"))
            T = MSGS[lang]
            print(T["title"])

    lang = resolve_language(config.get("language"))
    T = MSGS[lang]

    # Banner
    print("=" * 60)
    print(T["title"])
    print("=" * 60)
    print()
    print(T["version"])

    # Warn only when a non-empty, unsupported language was configured
    raw_lang = config.get("language")
    if (raw_lang is not None and str(raw_lang).strip()
            and lang == "en" and str(raw_lang).strip().lower() not in ("en", "english", "英文")):
        print(msg(lang, "lang_warn", value=raw_lang))

    # ---------- 2. Program directory ----------
    print(msg(lang, "step1", path=script_dir))

    # ---------- 3. Configuration (loaded above) ----------
    print(msg(lang, "step2", path=config_path))
    try:
        speed_signal = config["speed_signal"]
        brake_signal = config["brake_signal"]
        min_decel = float(config.get("min_decel", 1.48))
        max_decel = float(config.get("max_decel", 2.21))
        enable_min_limit = bool(config.get("enable_min_limit", True))
        enable_max_limit = bool(config.get("enable_max_limit", True))
        decel_metric = str(config.get("decel_metric", "v2_2s")).strip().lower()
    except Exception as e:
        print(msg(lang, "cfg_parse_fail", err=e))
        input(msg(lang, "press_exit"))
        return
    print(msg(lang, "cfg_lang", name=T["lang_name"]))
    print(msg(lang, "cfg_ok_speed", name=speed_signal))
    print(msg(lang, "cfg_ok_brake", name=brake_signal))
    time.sleep(0.5)  # pause 0.5 seconds

    # ---------- 4. Get the data file ----------
    if len(sys.argv) < 2:
        print(msg(lang, "no_file_arg"))
        print()
        print(msg(lang, "menu_title"))
        print(msg(lang, "menu_opt1"))
        print(msg(lang, "menu_opt2"))
        print(msg(lang, "menu_opt3"))
        print()
        while True:
            try:
                choice = input(msg(lang, "menu_prompt")).strip()
            except (EOFError, KeyboardInterrupt):
                choice = "3"
            if choice == "1":
                # Open file dialog to select data file
                if _TK_AVAILABLE:
                    temp_root = tk.Tk()
                    temp_root.withdraw()
                    file_path = filedialog.askopenfilename(
                        title=msg(lang, "file_dialog_title"),
                        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
                    )
                    temp_root.destroy()
                    if file_path:
                        # Process the selected file (reuse existing logic)
                        sys.argv.append(file_path)
                        break  # exit while loop, continue to process file
                    else:
                        print(msg(lang, "no_file_selected"))
                        continue
                else:
                    print("         [GUI] tkinter not available, cannot open file dialog.")
                    input(msg(lang, "press_exit"))
                    return
            elif choice == "2":
                new_cfg = show_config_gui(lang, config)
                if new_cfg is not None:
                    cfg_path = get_config_path()
                    config_text = json.dumps(new_cfg, indent=4, ensure_ascii=False)
                    # The stream is attached to the exe, so no sidecar file
                    # is created. On non-frozen script runs, keep config.json.
                    with open(cfg_path, "w", encoding="utf-8") as f:
                        f.write(config_text)
                    config = new_cfg
                    lang = resolve_language(config.get("language"))
                    T = MSGS[lang]
                    speed_signal = config["speed_signal"]
                    brake_signal = config["brake_signal"]
                    min_decel = float(config.get("min_decel", 1.48))
                    max_decel = float(config.get("max_decel", 2.21))
                    enable_min_limit = bool(config.get("enable_min_limit", True))
                    enable_max_limit = bool(config.get("enable_max_limit", True))
                    decel_metric = str(config.get("decel_metric", "v2_2s")).strip().lower()
                    print(msg(lang, "config_saved"))
                else:
                    print(msg(lang, "config_cancelled"))
                # After config, continue showing menu
                print()
                print(msg(lang, "menu_title"))
                print(msg(lang, "menu_opt1"))
                print(msg(lang, "menu_opt2"))
                print(msg(lang, "menu_opt3"))
                print()
            elif choice == "3":
                return
            else:
                print(msg(lang, "menu_invalid"))
        # If we break out of while loop with choice 1, file_path is in sys.argv
        file_path = sys.argv[-1]



    file_path = sys.argv[1]
    print(msg(lang, "step3", path=file_path))
    if not os.path.exists(file_path):
        print(msg(lang, "file_not_exist"))
        input(msg(lang, "press_exit"))
        return

    # ---------- 5. Read and parse data file (split by whitespace) ----------
    try:
        file_text = safe_read_file(file_path, msg(lang, "read_fail_text", path=file_path))
        lines = file_text.splitlines(keepends=True)
    except Exception as e:
        print(msg(lang, "read_fail", err=e))
        input(msg(lang, "press_exit"))
        return

    if len(lines) < 2:
        print(msg(lang, "need_two_rows"))
        input(msg(lang, "press_exit"))
        return

    headers = lines[0].rstrip('\n').split()
    print(msg(lang, "step4", count=len(headers)))

    # Locate column indices
    try:
        time_idx = 0                     # First column is time (hour value)
        speed_idx = headers.index(speed_signal)
        brake_idx = headers.index(brake_signal)
        print(msg(lang, "time_col", idx=time_idx))
        print(msg(lang, "speed_col", idx=speed_idx, name=speed_signal))
        print(msg(lang, "brake_col", idx=brake_idx, name=brake_signal))
    except ValueError as e:
        print(msg(lang, "col_not_found", err=e))
        input(msg(lang, "press_exit"))
        return

    # Read data row by row
    raw_times_sec, raw_speeds, brakes = [], [], []
    skipped = 0
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) <= max(time_idx, speed_idx, brake_idx):
            skipped += 1
            continue
        try:
            t_hour = float(parts[time_idx])      # Hour value
            v_kmh = float(parts[speed_idx])
            b = float(parts[brake_idx])
        except ValueError:
            skipped += 1
            continue
        # Convert to seconds
        t_sec = t_hour * 3600.0
        raw_times_sec.append(t_sec)
        raw_speeds.append(v_kmh)
        brakes.append(b)

    print(msg(lang, "valid_rows", count=len(raw_times_sec), skipped=skipped))
    if raw_times_sec:
        print(msg(lang, "time_range", start=format_time(raw_times_sec[0]), end=format_time(raw_times_sec[-1])))
        print(msg(lang, "speed_range", lo=min(raw_speeds), hi=max(raw_speeds)))
        print()
    else:
        print(msg(lang, "no_valid_data"))
        input(msg(lang, "press_exit"))
        return
    time.sleep(0.5)  # pause 0.5 seconds

    # ---------- 6. Unit conversion (km/h → m/s) ----------
    speeds_ms = [v / 3.6 for v in raw_speeds]

    # ---------- 7. Find braking interval (1→0 falling edge, initial speed > 5 km/h) ----------
    start_idx = None
    search_from = 1
    while search_from < len(brakes):
        if brakes[search_from] == 0 and brakes[search_from - 1] == 1:
            if raw_speeds[search_from] > 5.0:
                start_idx = search_from
                print(msg(lang, "eb_found", idx=start_idx, time=format_time(raw_times_sec[start_idx]), speed=raw_speeds[start_idx]))
                break
            else:
                print(msg(lang, "eb_skipped", idx=search_from, speed=raw_speeds[search_from]))
                search_from += 1
                continue
        search_from += 1

    if start_idx is None:
        if brakes[0] == 0 and raw_speeds[0] > 5.0:
            start_idx = 0
            print(msg(lang, "eb_fallback"))
        else:
            print(msg(lang, "eb_none"))
            input(msg(lang, "press_exit"))
            return

    print(msg(lang, "step6_start", idx=start_idx, time=format_time(raw_times_sec[start_idx]), speed=raw_speeds[start_idx]))

    # Braking end: speed first < 0.2 km/h
    end_idx = None
    for i in range(start_idx, len(raw_speeds)):
        if raw_speeds[i] < 0.2:
            end_idx = i
            break
    if end_idx is None:
        end_idx = len(raw_speeds) - 1
        print(msg(lang, "end_fallback"))
    print(msg(lang, "step6_end", idx=end_idx, time=format_time(raw_times_sec[end_idx]), speed=raw_speeds[end_idx]))
    print()

    # ---------- 8. Extract interval and calculate ----------
    t_seg = raw_times_sec[start_idx:end_idx + 1]
    v_seg = speeds_ms[start_idx:end_idx + 1]
    v_kmh_seg = raw_speeds[start_idx:end_idx + 1]
    print()
    print("=" * 58)
    print(msg(lang, "result_title"))
    print("=" * 58)
    print()
    print(msg(lang, "data_points", count=len(t_seg)))
    if len(t_seg) > 0:
        print()
        print(msg(lang, "time_interval", start=format_time(t_seg[0]), end=format_time(t_seg[-1])))

    # Braking time (seconds)
    brake_time = t_seg[-1] - t_seg[0]

    # Distance via trapezoidal integration
    distance = 0.0
    for i in range(len(t_seg) - 1):
        dt = t_seg[i + 1] - t_seg[i]
        v_avg = (v_seg[i] + v_seg[i + 1]) / 2.0
        distance += v_avg * dt

    # Initial speed, final speed (km/h and m/s)
    v0_kmh = v_kmh_seg[0]
    v_end_kmh = v_kmh_seg[-1]
    v0_ms = v_seg[0]
    v_end_ms = v_seg[-1]

    # Average deceleration v0²/(2S)
    if distance > 0:
        avg_decel = (v0_ms ** 2) / (2.0 * distance)
        avg_decel_str = f"{avg_decel:.3f} m/s²"
    else:
        avg_decel_str = msg(lang, "infinite_dist")

    # Rate deceleration = speed difference / brake time
    if brake_time > 0:
        rate_decel = (v0_ms - v_end_ms) / brake_time
        rate_decel_str = f"{rate_decel:.3f} m/s²"
    else:
        rate_decel_str = msg(lang, "infinite_time")

    # ---------- 9. Output results ----------
    print()
    print(msg(lang, "v0", value=v0_kmh))
    print()
    print(msg(lang, "v_end", value=v_end_kmh))
    print()
    print(msg(lang, "brake_time", value=brake_time))
    print()
    print(msg(lang, "distance", value=distance))
    print()
    print(msg(lang, "rate_decel", value=rate_decel_str))
    print()
    print(msg(lang, "avg_decel", value=avg_decel_str))
    print()
    print("=" * 58)

    # ---------- 10. Result GUI window (summary + plot + one-click screenshot) ----------
    # Determine PASS/FAIL based on selected deceleration metric
    if decel_metric == "dv_dt":
        if brake_time > 0:
            decel_val = (v0_ms - v_end_ms) / brake_time
        else:
            decel_val = None
    else:
        if distance > 0:
            decel_val = (v0_ms ** 2) / (2.0 * distance)
        else:
            decel_val = None
    if decel_val is None:
        passed = False
    else:
        passed = True
        if enable_min_limit and decel_val < min_decel:
            passed = False
        if enable_max_limit and decel_val > max_decel:
            passed = False
    gui_ctx = {
        "times": raw_times_sec,
        "speeds": raw_speeds,
        "brakes": brakes,
        "start_idx": start_idx,
        "end_idx": end_idx,
        "v0_kmh": v0_kmh,
        "v_end_kmh": v_end_kmh,
        "brake_time": brake_time,
        "distance": distance,
        "rate_decel_str": rate_decel_str,
        "avg_decel_str": avg_decel_str,
        "count": len(t_seg),
        "interval_str": format_time(t_seg[0]) + " ~ " + format_time(t_seg[-1]),
        "file_name": os.path.basename(file_path),
        "passed": passed,
        "min_decel": min_decel,
        "max_decel": max_decel,
        "enable_min_limit": enable_min_limit,
        "enable_max_limit": enable_max_limit,
        "decel_metric": decel_metric,
    }
    try:
        if show_result_gui(lang, gui_ctx):
            return                      # GUI shown (console hidden) -> program exits
    except Exception as e:
        print()
        print("         [GUI] Failed to open the result window: {}".format(e))
        print("         [GUI] The console result above is still valid.")
    print()
    print("=" * 58)

if __name__ == "__main__":
    main()

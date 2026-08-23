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
import webbrowser
from pathlib import Path

# ---------- Console output encoding (Windows) ----------
# Ensure UTF-8 output even when stdout is redirected to a file/pipe,
# so Chinese text and special symbols (✓/×/²) never trigger encode errors.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
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

# ------------------ Multilingual message table ------------------
MSGS = {
    "en": {
        "title": "     E M E R G E N C Y  B R A K E  C A L C U L A T O R  ",
        "version": "SW Version : 1.0 2026.08 ",
        "lang_name": "English",
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
        "config_lbl_min": "Min Decel (m/s²):",
        "config_lbl_max": "Max Decel (m/s²):",
        "config_lbl_enable_min": "Enable Min Limit:",
        "config_lbl_enable_max": "Enable Max Limit:",
        "config_lbl_metric": "Evaluation Metric:",
        "config_btn_save": "Save",
        "config_btn_cancel": "Cancel",
        "config_opt_yes": "Yes",
        "config_opt_no": "No",
        "config_overlimit_msg": "Configuration out of range: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "Please select an option:",
        "menu_opt1": "Open data file",
        "menu_opt2": "Configure settings",
        "menu_opt3": "About",
        "menu_prompt": "Enter your choice (1-3): ",
        "menu_invalid": "Invalid choice, please try again.",
        "file_dialog_title": "Select data file",
        "file_filter": "Text files (*.txt)|*.txt|All files (*.*)|*.*",
        "menu_about": "Version Info: v1.0 Multilingual",
        "no_file_selected": "No file selected.",    },
    "zh": {
        "title": "            紧 急 制 动 计 算 器  ",
        "version": "软件版本 : 1.0 2026.08 ",
        "lang_name": "简体中文",
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
        "menu_opt1": "打开数据文件",
        "menu_opt2": "配置信息",
        "menu_opt3": "关于",
        "menu_prompt": "请输入选择 (1-3): ",
        "menu_invalid": "无效选择，请重新输入。",
        "file_dialog_title": "选择数据文件",
        "file_filter": "文本文件 (*.txt)|*.txt|所有文件 (*.*)|*.*",
        "menu_about": "版本信息：v1.0 多语言版",
        "no_file_selected": "No file selected.",    },
    "ms": {
        "title": "     K A L K U L A T O R  B R E K  K E C E M A S A N  ",
        "version": "Versi Perisian : 1.0 2026.08 ",
        "lang_name": "Bahasa Melayu",
        "lang_warn": "         × Bahasa tidak diketahui '{value}', menggunakan English (en).",
        "step1": "\n[Langkah 1] Direktori program: {path}",
        "step2": "\n[Langkah 2] Mencari fail konfigurasi: {path}",
        "cfg_not_found": "         × Ralat: config.json tidak dijumpai",
        "press_exit": "\nTekan Enter untuk keluar...",
        "cfg_lang": "         ✓ Bahasa: {name}",
        "cfg_ok_speed": "         ✓ Nama isyarat kelajuan: {name}",
        "cfg_ok_brake": "         ✓ Nama isyarat brek: {name}",
        "cfg_parse_fail": "         × Penghuraian fail konfigurasi gagal: {err}",
        "no_file_arg": "         × Tiada fail data diterima. Sila seret fail .txt ke ikon program ini.",
        "step3": "\n[Langkah 3] Fail data untuk diproses: {path}",
        "file_not_exist": "         × Fail tidak wujud!",
        "read_fail": "         × Tidak dapat membaca fail: {err}",
        "read_fail_text": "Tidak dapat membaca fail dengan sebarang pengekodan: {path}",
        "need_two_rows": "         × Fail data mesti mengandungi sekurang-kurangnya baris pengepala dan satu baris data.",
        "step4": "\n[Langkah 4] Pengepala fail (jumlah {count} lajur)",
        "time_col": "         Indeks lajur masa: {idx} (lajur pertama)",
        "speed_col": "         Indeks lajur kelajuan: {idx} (berkaitan dengan '{name}')",
        "brake_col": "         Indeks lajur brek: {idx} (berkaitan dengan '{name}')",
        "col_not_found": "         × Lajur isyarat yang diperlukan tidak dijumpai dalam pengepala: {err}",
        "valid_rows": "         Baris data sah dibaca: {count} baris, dilangkau tidak sah: {skipped}",
        "time_range": "         Julat masa: {start} ~ {end}",
        "speed_range": "         Julat kelajuan: {lo:.2f} ~ {hi:.2f} km/j",
        "no_valid_data": "         × Tiada data sah!",
        "eb_found": "[Langkah 5] Titik EB sah dijumpai -> indeks:{idx}, masa:{time}, kelajuan:{speed:.2f} km/j ",
        "eb_skipped": "\n         Titik EB indeks:{idx} kelajuan {speed:.2f} km/j <=5, dilangkau, terus mencari...\n",
        "eb_fallback": "\n         Tiada titik EB dijumpai, tetapi data bermula dalam keadaan membrek (0) dengan kelajuan>5, menggunakan permulaan sebagai permulaan brek.\n",
        "eb_none": "\n         × Tiada permulaan EB sah dijumpai (titik EB dengan kelajuan awal > 5 km/j).\n",
        "step6_start": "\n[Langkah 6] Titik mula membrek -> indeks:{idx}, masa:{time}, kelajuan:{speed:.2f} km/j",
        "end_fallback": "         Kelajuan tidak pernah turun di bawah 0.2 km/j, menggunakan titik data terakhir sebagai akhir brek.",
        "step6_end": "         Titik akhir membrek -> indeks:{idx}, masa:{time}, kelajuan:{speed:.2f} km/j",
        "press_calc": "         Tekan Enter untuk memulakan pengiraan...",
        "result_title": "          K E P U T U S A N   P E N G I R A A N        ",
        "data_points": "  Titik data: {count}",
        "time_interval": "  Selang masa: {start} ~ {end}",
        "v0": "  Kelajuan awal: {value:.2f} km/j",
        "v_end": "  Kelajuan akhir: {value:.2f} km/j",
        "brake_time": "  Masa membrek: {value:.4f} saat",
        "distance": "  Jarak membrek: {value:.3f} m",
        "rate_decel": "  Penyahpecutan kadar (dv/dt): {value}",
        "avg_decel": "  Penyahpecutan purata (V²/2S): {value}",
        "infinite_dist": "Infiniti (jarak sifar)",
        "infinite_time": "Infiniti (masa sifar)",
        "done": "\nPemprosesan selesai. Tekan Enter untuk keluar...",
        "press_continue": "\nTekan Enter untuk teruskan...",
        "gui_title": "Keputusan Ujian Brek",
        "gui_panel_title": "Ringkasan Keputusan Ujian",
        "gui_btn_screenshot": "SIMPAN GAMBAR",
        "gui_saved": "Tangkapan skrin disimpan ke:\n{path}",
        "gui_save_fail": "Tangkapan skrin gagal: {err}",
        "gui_no_pillow": "Pillow tidak dipasang, tidak dapat mengambil tangkapan skrin.\nSila jalankan:  pip install pillow",
        "plot_title": "Lengkung Kelajuan - Masa",
        "axis_x": "Masa (HH:MM:SS.mmm)",
        "axis_y": "Kelajuan (km/j)",
        "legend_speed": "Lengkung kelajuan",
        "legend_eb": "Isyarat EB",
        "legend_start": "Mula brek",
        "legend_end": "Akhir brek",
        "legend_area": "Jarak membrek",
        "lbl_v0": "Kelajuan awal v0",
        "lbl_vend": "Kelajuan akhir v_end",
        "lbl_dt": "Selang Δt",
        "lbl_dist": "Jarak S",
        "gui_file": "Fail data",
        "gui_label_points": "Titik data",
        "gui_label_interval": "Selang masa",
        "gui_label_v0": "Kelajuan awal",
        "gui_label_vend": "Kelajuan akhir",
        "gui_label_time": "Masa membrek",
        "gui_label_dist": "Jarak membrek",
        "gui_label_rate": "Penyahpecutan kadar (dv/dt)",
        "gui_label_avg": "Penyahpecutan purata (V²/2S)",
        "gui_pass": "LULUS",
        "gui_fail": "GAGAL",
        "gui_req": "Keperluan: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "(tiada had)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "Persediaan Konfigurasi",
        "config_prompt": "Sila pilih pilihan:",
        "config_saved": "Konfigurasi berjaya disimpan.",
        "config_cancelled": "Konfigurasi dibatalkan.",
        "config_overlimit": "Konfigurasi di luar julat",
        "config_lbl_language": "Bahasa:",
        "config_lbl_speed": "Isyarat Kelajuan:",
        "config_lbl_brake": "Isyarat Brek:",
        "config_lbl_min": "Min Penyahpecutan (m/s²):",
        "config_lbl_max": "Maks Penyahpecutan (m/s²):",
        "config_lbl_enable_min": "Dayakan Had Min:",
        "config_lbl_enable_max": "Dayakan Had Maks:",
        "config_lbl_metric": "Metrik Penilaian:",
        "config_btn_save": "Simpan",
        "config_btn_cancel": "Batal",
        "config_opt_yes": "Ya",
        "config_opt_no": "Tidak",
        "config_overlimit_msg": "Konfigurasi di luar julat: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "Sila pilih pilihan:",
        "menu_opt1": "Buka fail data",
        "menu_opt2": "Konfigurasi tetapan",
        "menu_opt3": "Perihal",
        "menu_prompt": "Masukkan pilihan anda (1-3): ",
        "menu_invalid": "Pilihan tidak sah, sila cuba lagi.",
        "file_dialog_title": "Pilih fail data",
        "file_filter": "Fail teks (*.txt)|*.txt|Semua fail (*.*)|*.*",
        "menu_about": "Maklumat Versi: v1.0 Berbilang Bahasa",
        "no_file_selected": "未选择文件。",    },
    "ja": {
        "title": "     緊 急 ブ レ ー キ 計 算 機  ",
        "version": "ソフトウェアバージョン : 1.0 2026.08 ",
        "lang_name": "日本語",
        "lang_warn": "         × 不明な言語'{value}'、英語（en）を使用します。",
        "step1": "\n[ステップ 1] プログラムディレクトリ: {path}",
        "step2": "\n[ステップ 2] 設定ファイルを検索中: {path}",
        "cfg_not_found": "         × エラー：config.jsonが見つかりません",
        "press_exit": "\nEnterキーを押して終了...",
        "cfg_lang": "         ✓ 言語: {name}",
        "cfg_ok_speed": "         ✓ 速度信号名: {name}",
        "cfg_ok_brake": "         ✓ ブレーキ信号名: {name}",
        "cfg_parse_fail": "         × 設定ファイルの解析に失敗しました: {err}",
        "no_file_arg": "         × データファイルを受信していません。.txtファイルをこのプログラムアイコンにドラッグしてください。",
        "step3": "\n[ステップ 3] 処理するデータファイル: {path}",
        "file_not_exist": "         × ファイルが存在しません！",
        "read_fail": "         × ファイルを読み取れません: {err}",
        "read_fail_text": "どのエンコーディングでもファイルを読み取れません: {path}",
        "need_two_rows": "         × データファイルには、少なくともヘッダー行と1つのデータ行が含まれている必要があります。",
        "step4": "\n[ステップ 4] ファイルヘッダー（合計{count}列）",
        "time_col": "         時間列インデックス: {idx}（最初の列）",
        "speed_col": "         速度列インデックス: {idx}（'{name}'に対応）",
        "brake_col": "         ブレーキ列インデックス: {idx}（'{name}'に対応）",
        "col_not_found": "         × 必要な信号列がヘッダーに見つかりません: {err}",
        "valid_rows": "         有効なデータ行を読み取りました: {count}行、無効をスキップ: {skipped}",
        "time_range": "         時間範囲: {start} ~ {end}",
        "speed_range": "         速度範囲: {lo:.2f} ~ {hi:.2f} km/h",
        "no_valid_data": "         × 有効なデータがありません！",
        "eb_found": "[ステップ 5] 有効なEBポイントが見つかりました -> インデックス:{idx}、時間:{time}、速度:{speed:.2f} km/h ",
        "eb_skipped": "\n         EBポイントインデックス:{idx} 速度{speed:.2f} km/h <=5、スキップ、検索を続行...\n",
        "eb_fallback": "\n         EBポイントが見つかりませんが、データはブレーキ状態（0）で速度>5で始まり、開始をブレーキ開始として使用します。\n",
        "eb_none": "\n         × 有効なEB開始が見つかりません（初速度> 5 km/hのEBポイント）。\n",
        "step6_start": "\n[ステップ 6] ブレーキ開始点 -> インデックス:{idx}、時間:{time}、速度:{speed:.2f} km/h",
        "end_fallback": "         速度は0.2 km/h未満に下がらず、最後のデータポイントをブレーキ終了として使用します。",
        "step6_end": "         ブレーキ終了点 -> インデックス:{idx}、時間:{time}、速度:{speed:.2f} km/h",
        "press_calc": "         Enterキーを押して計算を開始...",
        "result_title": "          計 算 結 果        ",
        "data_points": "  データポイント: {count}",
        "time_interval": "  時間間隔: {start} ~ {end}",
        "v0": "  初速度: {value:.2f} km/h",
        "v_end": "  終速度: {value:.2f} km/h",
        "brake_time": "  ブレーキ時間: {value:.4f} 秒",
        "distance": "  ブレーキ距離: {value:.3f} m",
        "rate_decel": "  レート減速度（dv/dt）: {value}",
        "avg_decel": "  平均減速度（V²/2S）: {value}",
        "infinite_dist": "無限（距離ゼロ）",
        "infinite_time": "無限（時間ゼロ）",
        "done": "\n処理が完了しました。Enterキーを押して終了...",
        "press_continue": "\nEnterキーを押して続行...",
        "gui_title": "ブレーキテスト結果",
        "gui_panel_title": "テスト結果の概要",
        "gui_btn_screenshot": "画像を保存",
        "gui_saved": "スクリーンショットを保存しました:\n{path}",
        "gui_save_fail": "スクリーンショット失敗: {err}",
        "gui_no_pillow": "Pillowがインストールされていません。スクリーンショットを撮ることができません。\n実行してください:  pip install pillow",
        "plot_title": "速度 - 時間曲線",
        "axis_x": "時間（HH:MM:SS.mmm）",
        "axis_y": "速度（km/h）",
        "legend_speed": "速度曲線",
        "legend_eb": "EB信号",
        "legend_start": "ブレーキ開始",
        "legend_end": "ブレーキ終了",
        "legend_area": "ブレーキ距離",
        "lbl_v0": "初速度 v0",
        "lbl_vend": "終速度 v_end",
        "lbl_dt": "間隔 Δt",
        "lbl_dist": "距離 S",
        "gui_file": "データファイル",
        "gui_label_points": "データポイント",
        "gui_label_interval": "時間間隔",
        "gui_label_v0": "初速度",
        "gui_label_vend": "終速度",
        "gui_label_time": "ブレーキ時間",
        "gui_label_dist": "ブレーキ距離",
        "gui_label_rate": "レート減速度（dv/dt）",
        "gui_label_avg": "平均減速度（V²/2S）",
        "gui_pass": "合格",
        "gui_fail": "不合格",
        "gui_req": "要件: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "（制限なし）",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "設定セットアップ",
        "config_prompt": "オプションを選択してください:",
        "config_saved": "設定が正常に保存されました。",
        "config_cancelled": "設定がキャンセルされました。",
        "config_overlimit": "設定が範囲外です",
        "config_lbl_language": "言語:",
        "config_lbl_speed": "速度信号:",
        "config_lbl_brake": "ブレーキ信号:",
        "config_lbl_min": "最小減速度（m/s²）:",
        "config_lbl_max": "最大減速度（m/s²）:",
        "config_lbl_enable_min": "最小制限を有効にする:",
        "config_lbl_enable_max": "最大制限を有効にする:",
        "config_lbl_metric": "評価指標:",
        "config_btn_save": "保存",
        "config_btn_cancel": "キャンセル",
        "config_opt_yes": "はい",
        "config_opt_no": "いいえ",
        "config_overlimit_msg": "設定が範囲外: min_decel >= 0、max_decel > 0、min_decel <= max_decel。",
        "menu_title": "オプションを選択してください:",
        "menu_opt1": "データファイルを開く",
        "menu_opt2": "設定を構成",
        "menu_opt3": "バージョン情報",
        "menu_prompt": "選択を入力してください（1-3）: ",
        "menu_invalid": "無効な選択です。もう一度お試しください。",
        "file_dialog_title": "データファイルを選択",
        "file_filter": "テキストファイル (*.txt)|*.txt|すべてのファイル (*.*)|*.*",
        "menu_about": "バージョン情報：v1.0 多言語版",
        "no_file_selected": "Tiada fail dipilih.",    },
    "fr": {
        "title": "     C A L C U L A T E U R  D E  F R E I N  D ' U R G E N C E  ",
        "version": "Version du logiciel : 1.0 2026.08 ",
        "lang_name": "Français",
        "lang_warn": "         × Langue inconnue '{value}', utilisation de l'anglais (en).",
        "step1": "\n[Étape 1] Répertoire du programme: {path}",
        "step2": "\n[Étape 2] Recherche du fichier de configuration: {path}",
        "cfg_not_found": "         × Erreur: config.json introuvable",
        "press_exit": "\nAppuyez sur Entrée pour quitter...",
        "cfg_lang": "         ✓ Langue: {name}",
        "cfg_ok_speed": "         ✓ Nom du signal de vitesse: {name}",
        "cfg_ok_brake": "         ✓ Nom du signal de frein: {name}",
        "cfg_parse_fail": "         × Échec de l'analyse du fichier de configuration: {err}",
        "no_file_arg": "         × Aucun fichier de données reçu. Veuillez glisser un fichier .txt sur l'icône de ce programme.",
        "step3": "\n[Étape 3] Fichier de données à traiter: {path}",
        "file_not_exist": "         × Le fichier n'existe pas!",
        "read_fail": "         × Impossible de lire le fichier: {err}",
        "read_fail_text": "Impossible de lire le fichier avec n'importe quel encodage: {path}",
        "need_two_rows": "         × Le fichier de données doit contenir au moins une ligne d'en-tête et une ligne de données.",
        "step4": "\n[Étape 4] En-tête du fichier (total {count} colonnes)",
        "time_col": "         Index de colonne de temps: {idx} (première colonne)",
        "speed_col": "         Index de colonne de vitesse: {idx} (correspondant à '{name}')",
        "brake_col": "         Index de colonne de frein: {idx} (correspondant à '{name}')",
        "col_not_found": "         × Colonne de signal requise introuvable dans l'en-tête: {err}",
        "valid_rows": "         Lignes de données valides lues: {count} lignes, invalides ignorées: {skipped}",
        "time_range": "         Plage de temps: {start} ~ {end}",
        "speed_range": "         Plage de vitesse: {lo:.2f} ~ {hi:.2f} km/h",
        "no_valid_data": "         × Aucune donnée valide!",
        "eb_found": "[Étape 5] Point EB valide trouvé -> index:{idx}, temps:{time}, vitesse:{speed:.2f} km/h ",
        "eb_skipped": "\n         Point EB index:{idx} vitesse {speed:.2f} km/h <=5, ignoré, continuer la recherche...\n",
        "eb_fallback": "\n         Aucun point EB trouvé, mais les données commencent en état de freinage (0) avec vitesse>5, utilisation du début comme début de freinage.\n",
        "eb_none": "\n         × Aucun début EB valide trouvé (point EB avec vitesse initiale > 5 km/h).\n",
        "step6_start": "\n[Étape 6] Point de début de freinage -> index:{idx}, temps:{time}, vitesse:{speed:.2f} km/h",
        "end_fallback": "         La vitesse n'est jamais tombée en dessous de 0.2 km/h, utilisation du dernier point de données comme fin de freinage.",
        "step6_end": "         Point de fin de freinage -> index:{idx}, temps:{time}, vitesse:{speed:.2f} km/h",
        "press_calc": "         Appuyez sur Entrée pour démarrer le calcul...",
        "result_title": "          R É S U L T A T S   D E   C A L C U L        ",
        "data_points": "  Points de données: {count}",
        "time_interval": "  Intervalle de temps: {start} ~ {end}",
        "v0": "  Vitesse initiale: {value:.2f} km/h",
        "v_end": "  Vitesse finale: {value:.2f} km/h",
        "brake_time": "  Temps de freinage: {value:.4f} sec",
        "distance": "  Distance de freinage: {value:.3f} m",
        "rate_decel": "  Décélération de taux (dv/dt): {value}",
        "avg_decel": "  Décélération moyenne (V²/2S): {value}",
        "infinite_dist": "Infini (distance zéro)",
        "infinite_time": "Infini (temps zéro)",
        "done": "\nTraitement terminé. Appuyez sur Entrée pour quitter...",
        "press_continue": "\nAppuyez sur Entrée pour continuer...",
        "gui_title": "Résultat du test de frein",
        "gui_panel_title": "Résumé des résultats de test",
        "gui_btn_screenshot": "ENREGISTRER L'IMAGE",
        "gui_saved": "Capture d'écran enregistrée à:\n{path}",
        "gui_save_fail": "Échec de la capture d'écran: {err}",
        "gui_no_pillow": "Pillow n'est pas installé, impossible de prendre une capture d'écran.\nVeuillez exécuter:  pip install pillow",
        "plot_title": "Courbe Vitesse - Temps",
        "axis_x": "Temps (HH:MM:SS.mmm)",
        "axis_y": "Vitesse (km/h)",
        "legend_speed": "Courbe de vitesse",
        "legend_eb": "Signal EB",
        "legend_start": "Début de freinage",
        "legend_end": "Fin de freinage",
        "legend_area": "Distance de freinage",
        "lbl_v0": "Vitesse initiale v0",
        "lbl_vend": "Vitesse finale v_end",
        "lbl_dt": "Intervalle Δt",
        "lbl_dist": "Distance S",
        "gui_file": "Fichier de données",
        "gui_label_points": "Points de données",
        "gui_label_interval": "Intervalle de temps",
        "gui_label_v0": "Vitesse initiale",
        "gui_label_vend": "Vitesse finale",
        "gui_label_time": "Temps de freinage",
        "gui_label_dist": "Distance de freinage",
        "gui_label_rate": "Décélération de taux (dv/dt)",
        "gui_label_avg": "Décélération moyenne (V²/2S)",
        "gui_pass": "RÉUSSI",
        "gui_fail": "ÉCHOUÉ",
        "gui_req": "Exigence: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "(pas de limite)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "Configuration",
        "config_prompt": "Veuillez sélectionner une option:",
        "config_saved": "Configuration enregistrée avec succès.",
        "config_cancelled": "Configuration annulée.",
        "config_overlimit": "Configuration hors limites",
        "config_lbl_language": "Langue:",
        "config_lbl_speed": "Signal de vitesse:",
        "config_lbl_brake": "Signal de frein:",
        "config_lbl_min": "Décélération min (m/s²):",
        "config_lbl_max": "Décélération max (m/s²):",
        "config_lbl_enable_min": "Activer la limite min:",
        "config_lbl_enable_max": "Activer la limite max:",
        "config_lbl_metric": "Métrique d'évaluation:",
        "config_btn_save": "Enregistrer",
        "config_btn_cancel": "Annuler",
        "config_opt_yes": "Oui",
        "config_opt_no": "Non",
        "config_overlimit_msg": "Configuration hors limites: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "Veuillez sélectionner une option:",
        "menu_opt1": "Ouvrir le fichier de données",
        "menu_opt2": "Configurer les paramètres",
        "menu_opt3": "À propos",
        "menu_prompt": "Entrez votre choix (1-3): ",
        "menu_invalid": "Choix invalide, veuillez réessayer.",
        "file_dialog_title": "Sélectionner le fichier de données",
        "file_filter": "Fichiers texte (*.txt)|*.txt|Tous les fichiers (*.*)|*.*",
        "menu_about": "Info version : v1.0 Multilingue",
        "no_file_selected": "ファイルが選択されていません。",    },
    "de": {
        "title": "     N O T B R E M S E N R E C H N E R  ",
        "version": "Software-Version : 1.0 2026.08 ",
        "lang_name": "Deutsch",
        "lang_warn": "         × Unbekannte Sprache '{value}', verwende Englisch (en).",
        "step1": "\n[Schritt 1] Programmverzeichnis: {path}",
        "step2": "\n[Schritt 2] Suche nach Konfigurationsdatei: {path}",
        "cfg_not_found": "         × Fehler: config.json nicht gefunden",
        "press_exit": "\nDrücken Sie die Eingabetaste zum Beenden...",
        "cfg_lang": "         ✓ Sprache: {name}",
        "cfg_ok_speed": "         ✓ Geschwindigkeitssignalname: {name}",
        "cfg_ok_brake": "         ✓ Bremssignalname: {name}",
        "cfg_parse_fail": "         × Fehler beim Parsen der Konfigurationsdatei: {err}",
        "no_file_arg": "         × Keine Datendatei empfangen. Bitte ziehen Sie eine .txt-Datei auf dieses Programmsymbol.",
        "step3": "\n[Schritt 3] Zu verarbeitende Datendatei: {path}",
        "file_not_exist": "         × Datei existiert nicht!",
        "read_fail": "         × Datei kann nicht gelesen werden: {err}",
        "read_fail_text": "Datei kann mit keiner Kodierung gelesen werden: {path}",
        "need_two_rows": "         × Datendatei muss mindestens eine Kopfzeile und eine Datenzeile enthalten.",
        "step4": "\n[Schritt 4] Dateikopf (insgesamt {count} Spalten)",
        "time_col": "         Zeitspaltenindex: {idx} (erste Spalte)",
        "speed_col": "         Geschwindigkeitsspaltenindex: {idx} (entspricht '{name}')",
        "brake_col": "         Bremsspaltenindex: {idx} (entspricht '{name}')",
        "col_not_found": "         × Erforderliche Signalspalte nicht im Kopf gefunden: {err}",
        "valid_rows": "         Gültige Datenzeilen gelesen: {count} Zeilen, übersprungen ungültig: {skipped}",
        "time_range": "         Zeitbereich: {start} ~ {end}",
        "speed_range": "         Geschwindigkeitsbereich: {lo:.2f} ~ {hi:.2f} km/h",
        "no_valid_data": "         × Keine gültigen Daten!",
        "eb_found": "[Schritt 5] Gültiger EB-Punkt gefunden -> Index:{idx}, Zeit:{time}, Geschwindigkeit:{speed:.2f} km/h ",
        "eb_skipped": "\n         EB-Punkt Index:{idx} Geschwindigkeit {speed:.2f} km/h <=5, übersprungen, Suche fortsetzen...\n",
        "eb_fallback": "\n         Kein EB-Punkt gefunden, aber Daten beginnen im Bremszustand (0) mit Geschwindigkeit>5, verwende Start als Bremsbeginn.\n",
        "eb_none": "\n         × Kein gültiger EB-Start gefunden (EB-Punkt mit Anfangsgeschwindigkeit > 5 km/h).\n",
        "step6_start": "\n[Schritt 6] Bremsstartpunkt -> Index:{idx}, Zeit:{time}, Geschwindigkeit:{speed:.2f} km/h",
        "end_fallback": "         Geschwindigkeit fiel nie unter 0,2 km/h, verwende letzten Datenpunkt als Bremsende.",
        "step6_end": "         Bremsendpunkt -> Index:{idx}, Zeit:{time}, Geschwindigkeit:{speed:.2f} km/h",
        "press_calc": "         Drücken Sie die Eingabetaste, um die Berechnung zu starten...",
        "result_title": "          B E R E C H N U N G S E R G E B N I S S E        ",
        "data_points": "  Datenpunkte: {count}",
        "time_interval": "  Zeitintervall: {start} ~ {end}",
        "v0": "  Anfangsgeschwindigkeit: {value:.2f} km/h",
        "v_end": "  Endgeschwindigkeit: {value:.2f} km/h",
        "brake_time": "  Bremszeit: {value:.4f} Sek",
        "distance": "  Bremsweg: {value:.3f} m",
        "rate_decel": "  Ratenverzögerung (dv/dt): {value}",
        "avg_decel": "  Durchschnittliche Verzögerung (V²/2S): {value}",
        "infinite_dist": "Unendlich (Entfernung Null)",
        "infinite_time": "Unendlich (Zeit Null)",
        "done": "\nVerarbeitung abgeschlossen. Drücken Sie die Eingabetaste zum Beenden...",
        "press_continue": "\nDrücken Sie die Eingabetaste, um fortzufahren...",
        "gui_title": "Bremstestergebnis",
        "gui_panel_title": "Testergebnis-Zusammenfassung",
        "gui_btn_screenshot": "BILD SPEICHERN",
        "gui_saved": "Screenshot gespeichert unter:\n{path}",
        "gui_save_fail": "Screenshot fehlgeschlagen: {err}",
        "gui_no_pillow": "Pillow ist nicht installiert, Screenshot nicht möglich.\nBitte ausführen:  pip install pillow",
        "plot_title": "Geschwindigkeit - Zeit Kurve",
        "axis_x": "Zeit (HH:MM:SS.mmm)",
        "axis_y": "Geschwindigkeit (km/h)",
        "legend_speed": "Geschwindigkeitskurve",
        "legend_eb": "EB-Signal",
        "legend_start": "Bremsstart",
        "legend_end": "Bremsende",
        "legend_area": "Bremsweg",
        "lbl_v0": "Anfangsgeschwindigkeit v0",
        "lbl_vend": "Endgeschwindigkeit v_end",
        "lbl_dt": "Intervall Δt",
        "lbl_dist": "Entfernung S",
        "gui_file": "Datendatei",
        "gui_label_points": "Datenpunkte",
        "gui_label_interval": "Zeitintervall",
        "gui_label_v0": "Anfangsgeschwindigkeit",
        "gui_label_vend": "Endgeschwindigkeit",
        "gui_label_time": "Bremszeit",
        "gui_label_dist": "Bremsweg",
        "gui_label_rate": "Ratenverzögerung (dv/dt)",
        "gui_label_avg": "Durchschnittliche Verzögerung (V²/2S)",
        "gui_pass": "BESTANDEN",
        "gui_fail": "DURCHGEFALLEN",
        "gui_req": "Anforderung: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "(keine Begrenzung)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "Konfigurationseinrichtung",
        "config_prompt": "Bitte wählen Sie eine Option:",
        "config_saved": "Konfiguration erfolgreich gespeichert.",
        "config_cancelled": "Konfiguration abgebrochen.",
        "config_overlimit": "Konfiguration außerhalb des Bereichs",
        "config_lbl_language": "Sprache:",
        "config_lbl_speed": "Geschwindigkeitssignal:",
        "config_lbl_brake": "Bremssignal:",
        "config_lbl_min": "Min Verzögerung (m/s²):",
        "config_lbl_max": "Max Verzögerung (m/s²):",
        "config_lbl_enable_min": "Min-Grenze aktivieren:",
        "config_lbl_enable_max": "Max-Grenze aktivieren:",
        "config_lbl_metric": "Bewertungsmetrik:",
        "config_btn_save": "Speichern",
        "config_btn_cancel": "Abbrechen",
        "config_opt_yes": "Ja",
        "config_opt_no": "Nein",
        "config_overlimit_msg": "Konfiguration außerhalb des Bereichs: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "Bitte wählen Sie eine Option:",
        "menu_opt1": "Datendatei öffnen",
        "menu_opt2": "Einstellungen konfigurieren",
        "menu_opt3": "Über",
        "menu_prompt": "Geben Sie Ihre Wahl ein (1-3): ",
        "menu_invalid": "Ungültige Wahl, bitte versuchen Sie es erneut.",
        "file_dialog_title": "Datendatei auswählen",
        "file_filter": "Textdateien (*.txt)|*.txt|Alle Dateien (*.*)|*.*",
        "menu_about": "Versionsinfo: v1.0 Mehrsprachig",
        "no_file_selected": "Aucun fichier sélectionné.",    },
    "es": {
        "title": "     C A L C U L A D O R A  D E  F R E N O  D E  E M E R G E N C I A  ",
        "version": "Versión de software : 1.0 2026.08 ",
        "lang_name": "Español",
        "lang_warn": "         × Idioma desconocido '{value}', usando inglés (en).",
        "step1": "\n[Paso 1] Directorio del programa: {path}",
        "step2": "\n[Paso 2] Buscando archivo de configuración: {path}",
        "cfg_not_found": "         × Error: config.json no encontrado",
        "press_exit": "\nPresione Enter para salir...",
        "cfg_lang": "         ✓ Idioma: {name}",
        "cfg_ok_speed": "         ✓ Nombre de señal de velocidad: {name}",
        "cfg_ok_brake": "         ✓ Nombre de señal de freno: {name}",
        "cfg_parse_fail": "         × Falló el análisis del archivo de configuración: {err}",
        "no_file_arg": "         × No se recibió archivo de datos. Arrastre un archivo .txt al icono de este programa.",
        "step3": "\n[Paso 3] Archivo de datos a procesar: {path}",
        "file_not_exist": "         × ¡El archivo no existe!",
        "read_fail": "         × No se puede leer el archivo: {err}",
        "read_fail_text": "No se puede leer el archivo con ninguna codificación: {path}",
        "need_two_rows": "         × El archivo de datos debe contener al menos una fila de encabezado y una fila de datos.",
        "step4": "\n[Paso 4] Encabezado del archivo (total {count} columnas)",
        "time_col": "         Índice de columna de tiempo: {idx} (primera columna)",
        "speed_col": "         Índice de columna de velocidad: {idx} (correspondiente a '{name}')",
        "brake_col": "         Índice de columna de freno: {idx} (correspondiente a '{name}')",
        "col_not_found": "         × Columna de señal requerida no encontrada en el encabezado: {err}",
        "valid_rows": "         Filas de datos válidas leídas: {count} filas, omitidas no válidas: {skipped}",
        "time_range": "         Rango de tiempo: {start} ~ {end}",
        "speed_range": "         Rango de velocidad: {lo:.2f} ~ {hi:.2f} km/h",
        "no_valid_data": "         × ¡No hay datos válidos!",
        "eb_found": "[Paso 5] Punto EB válido encontrado -> índice:{idx}, tiempo:{time}, velocidad:{speed:.2f} km/h ",
        "eb_skipped": "\n         Punto EB índice:{idx} velocidad {speed:.2f} km/h <=5, omitido, continuar búsqueda...\n",
        "eb_fallback": "\n         No se encontró punto EB, pero los datos comienzan en estado de frenado (0) con velocidad>5, usando inicio como inicio de frenado.\n",
        "eb_none": "\n         × No se encontró inicio EB válido (punto EB con velocidad inicial > 5 km/h).\n",
        "step6_start": "\n[Paso 6] Punto de inicio de frenado -> índice:{idx}, tiempo:{time}, velocidad:{speed:.2f} km/h",
        "end_fallback": "         La velocidad nunca cayó por debajo de 0.2 km/h, usando el último punto de datos como fin de frenado.",
        "step6_end": "         Punto de fin de frenado -> índice:{idx}, tiempo:{time}, velocidad:{speed:.2f} km/h",
        "press_calc": "         Presione Enter para iniciar el cálculo...",
        "result_title": "          R E S U L T A D O S   D E   C Á L C U L O        ",
        "data_points": "  Puntos de datos: {count}",
        "time_interval": "  Intervalo de tiempo: {start} ~ {end}",
        "v0": "  Velocidad inicial: {value:.2f} km/h",
        "v_end": "  Velocidad final: {value:.2f} km/h",
        "brake_time": "  Tiempo de frenado: {value:.4f} seg",
        "distance": "  Distancia de frenado: {value:.3f} m",
        "rate_decel": "  Desaceleración de tasa (dv/dt): {value}",
        "avg_decel": "  Desaceleración promedio (V²/2S): {value}",
        "infinite_dist": "Infinito (distancia cero)",
        "infinite_time": "Infinito (tiempo cero)",
        "done": "\nProcesamiento completo. Presione Enter para salir...",
        "press_continue": "\nPresione Enter para continuar...",
        "gui_title": "Resultado de prueba de freno",
        "gui_panel_title": "Resumen de resultados de prueba",
        "gui_btn_screenshot": "GUARDAR IMAGEN",
        "gui_saved": "Captura de pantalla guardada en:\n{path}",
        "gui_save_fail": "Captura de pantalla falló: {err}",
        "gui_no_pillow": "Pillow no está instalado, no se puede tomar una captura de pantalla.\nEjecute:  pip install pillow",
        "plot_title": "Curva Velocidad - Tiempo",
        "axis_x": "Tiempo (HH:MM:SS.mmm)",
        "axis_y": "Velocidad (km/h)",
        "legend_speed": "Curva de velocidad",
        "legend_eb": "Señal EB",
        "legend_start": "Inicio de frenado",
        "legend_end": "Fin de frenado",
        "legend_area": "Distancia de frenado",
        "lbl_v0": "Velocidad inicial v0",
        "lbl_vend": "Velocidad final v_end",
        "lbl_dt": "Intervalo Δt",
        "lbl_dist": "Distancia S",
        "gui_file": "Archivo de datos",
        "gui_label_points": "Puntos de datos",
        "gui_label_interval": "Intervalo de tiempo",
        "gui_label_v0": "Velocidad inicial",
        "gui_label_vend": "Velocidad final",
        "gui_label_time": "Tiempo de frenado",
        "gui_label_dist": "Distancia de frenado",
        "gui_label_rate": "Desaceleración de tasa (dv/dt)",
        "gui_label_avg": "Desaceleración promedio (V²/2S)",
        "gui_pass": "APROBADO",
        "gui_fail": "REPROBADO",
        "gui_req": "Requisito: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "(sin límite)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "Configuración",
        "config_prompt": "Por favor seleccione una opción:",
        "config_saved": "Configuración guardada exitosamente.",
        "config_cancelled": "Configuración cancelada.",
        "config_overlimit": "Configuración fuera de rango",
        "config_lbl_language": "Idioma:",
        "config_lbl_speed": "Señal de velocidad:",
        "config_lbl_brake": "Señal de freno:",
        "config_lbl_min": "Desaceleración mín (m/s²):",
        "config_lbl_max": "Desaceleración máx (m/s²):",
        "config_lbl_enable_min": "Habilitar límite mín:",
        "config_lbl_enable_max": "Habilitar límite máx:",
        "config_lbl_metric": "Métrica de evaluación:",
        "config_btn_save": "Guardar",
        "config_btn_cancel": "Cancelar",
        "config_opt_yes": "Sí",
        "config_opt_no": "No",
        "config_overlimit_msg": "Configuración fuera de rango: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "Por favor seleccione una opción:",
        "menu_opt1": "Abrir archivo de datos",
        "menu_opt2": "Configurar ajustes",
        "menu_opt3": "Acerca de",
        "menu_prompt": "Ingrese su elección (1-3): ",
        "menu_invalid": "Elección no válida, por favor intente de nuevo.",
        "file_dialog_title": "Seleccionar archivo de datos",
        "file_filter": "Archivos de texto (*.txt)|*.txt|Todos los archivos (*.*)|*.*",
        "menu_about": "Info de versión: v1.0 Multilingüe",
        "no_file_selected": "Keine Datei ausgewählt.",    },
    "ru": {
        "title": "     К А Л Ь К У Л Я Т О Р  А В А Р И Й Н О Г О  Т О Р М О Ж Е Н И Я  ",
        "version": "Версия ПО : 1.0 2026.08 ",
        "lang_name": "Русский",
        "lang_warn": "         × Неизвестный язык '{value}', используется английский (en).",
        "step1": "\n[Шаг 1] Каталог программы: {path}",
        "step2": "\n[Шаг 2] Поиск файла конфигурации: {path}",
        "cfg_not_found": "         × Ошибка: config.json не найден",
        "press_exit": "\nНажмите Enter для выхода...",
        "cfg_lang": "         ✓ Язык: {name}",
        "cfg_ok_speed": "         ✓ Название сигнала скорости: {name}",
        "cfg_ok_brake": "         ✓ Название сигнала тормоза: {name}",
        "cfg_parse_fail": "         × Ошибка анализа файла конфигурации: {err}",
        "no_file_arg": "         × Файл данных не получен. Перетащите файл .txt на значок этой программы.",
        "step3": "\n[Шаг 3] Файл данных для обработки: {path}",
        "file_not_exist": "         × Файл не существует!",
        "read_fail": "         × Невозможно прочитать файл: {err}",
        "read_fail_text": "Невозможно прочитать файл с любой кодировкой: {path}",
        "need_two_rows": "         × Файл данных должен содержать как минимум строку заголовка и одну строку данных.",
        "step4": "\n[Шаг 4] Заголовок файла (всего {count} столбцов)",
        "time_col": "         Индекс столбца времени: {idx} (первый столбец)",
        "speed_col": "         Индекс столбца скорости: {idx} (соответствует '{name}')",
        "brake_col": "         Индекс столбца тормоза: {idx} (соответствует '{name}')",
        "col_not_found": "         × Требуемый столбец сигнала не найден в заголовке: {err}",
        "valid_rows": "         Прочитано допустимых строк данных: {count} строк, пропущено недопустимых: {skipped}",
        "time_range": "         Диапазон времени: {start} ~ {end}",
        "speed_range": "         Диапазон скорости: {lo:.2f} ~ {hi:.2f} км/ч",
        "no_valid_data": "         × Нет допустимых данных!",
        "eb_found": "[Шаг 5] Найдена допустимая точка EB -> индекс:{idx}, время:{time}, скорость:{speed:.2f} км/ч ",
        "eb_skipped": "\n         Точка EB индекс:{idx} скорость {speed:.2f} км/ч <=5, пропущена, продолжить поиск...\n",
        "eb_fallback": "\n         Точка EB не найдена, но данные начинаются в состоянии торможения (0) со скоростью>5, используется начало как начало торможения.\n",
        "eb_none": "\n         × Не найдено допустимого начала EB (точка EB с начальной скоростью > 5 км/ч).\n",
        "step6_start": "\n[Шаг 6] Точка начала торможения -> индекс:{idx}, время:{time}, скорость:{speed:.2f} км/ч",
        "end_fallback": "         Скорость никогда не опускалась ниже 0.2 км/ч, используется последняя точка данных как конец торможения.",
        "step6_end": "         Точка конца торможения -> индекс:{idx}, время:{time}, скорость:{speed:.2f} км/ч",
        "press_calc": "         Нажмите Enter для начала расчета...",
        "result_title": "          Р Е З У Л Ь Т А Т Ы   Р А С Ч Е Т А        ",
        "data_points": "  Точки данных: {count}",
        "time_interval": "  Временной интервал: {start} ~ {end}",
        "v0": "  Начальная скорость: {value:.2f} км/ч",
        "v_end": "  Конечная скорость: {value:.2f} км/ч",
        "brake_time": "  Время торможения: {value:.4f} сек",
        "distance": "  Тормозной путь: {value:.3f} м",
        "rate_decel": "  Темп замедления (dv/dt): {value}",
        "avg_decel": "  Среднее замедление (V²/2S): {value}",
        "infinite_dist": "Бесконечность (расстояние ноль)",
        "infinite_time": "Бесконечность (время ноль)",
        "done": "\nОбработка завершена. Нажмите Enter для выхода...",
        "press_continue": "\nНажмите Enter для продолжения...",
        "gui_title": "Результат теста тормоза",
        "gui_panel_title": "Сводка результатов теста",
        "gui_btn_screenshot": "СОХРАНИТЬ ИЗОБРАЖЕНИЕ",
        "gui_saved": "Скриншот сохранен в:\n{path}",
        "gui_save_fail": "Ошибка скриншота: {err}",
        "gui_no_pillow": "Pillow не установлен, невозможно сделать скриншот.\nВыполните:  pip install pillow",
        "plot_title": "Кривая Скорость - Время",
        "axis_x": "Время (ЧЧ:ММ:СС.ммм)",
        "axis_y": "Скорость (км/ч)",
        "legend_speed": "Кривая скорости",
        "legend_eb": "Сигнал EB",
        "legend_start": "Начало торможения",
        "legend_end": "Конец торможения",
        "legend_area": "Тормозной путь",
        "lbl_v0": "Начальная скорость v0",
        "lbl_vend": "Конечная скорость v_end",
        "lbl_dt": "Интервал Δt",
        "lbl_dist": "Расстояние S",
        "gui_file": "Файл данных",
        "gui_label_points": "Точки данных",
        "gui_label_interval": "Временной интервал",
        "gui_label_v0": "Начальная скорость",
        "gui_label_vend": "Конечная скорость",
        "gui_label_time": "Время торможения",
        "gui_label_dist": "Тормозной путь",
        "gui_label_rate": "Темп замедления (dv/dt)",
        "gui_label_avg": "Среднее замедление (V²/2S)",
        "gui_pass": "ПРОЙДЕНО",
        "gui_fail": "НЕ ПРОЙДЕНО",
        "gui_req": "Требование: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} м/с²",
        "gui_req_max_only": "{metric} ≤ {maxv} м/с²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} м/с²",
        "gui_req_none": "(без ограничения)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "Настройка конфигурации",
        "config_prompt": "Пожалуйста, выберите опцию:",
        "config_saved": "Конфигурация успешно сохранена.",
        "config_cancelled": "Конфигурация отменена.",
        "config_overlimit": "Конфигурация вне диапазона",
        "config_lbl_language": "Язык:",
        "config_lbl_speed": "Сигнал скорости:",
        "config_lbl_brake": "Сигнал тормоза:",
        "config_lbl_min": "Мин замедление (м/с²):",
        "config_lbl_max": "Макс замедление (м/с²):",
        "config_lbl_enable_min": "Включить мин ограничение:",
        "config_lbl_enable_max": "Включить макс ограничение:",
        "config_lbl_metric": "Метрика оценки:",
        "config_btn_save": "Сохранить",
        "config_btn_cancel": "Отмена",
        "config_opt_yes": "Да",
        "config_opt_no": "Нет",
        "config_overlimit_msg": "Конфигурация вне диапазона: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "Пожалуйста, выберите опцию:",
        "menu_opt1": "Открыть файл данных",
        "menu_opt2": "Настроить параметры",
        "menu_opt3": "О программе",
        "menu_prompt": "Введите ваш выбор (1-3): ",
        "menu_invalid": "Неверный выбор, пожалуйста, попробуйте снова.",
        "file_dialog_title": "Выбрать файл данных",
        "file_filter": "Текстовые файлы (*.txt)|*.txt|Все файлы (*.*)|*.*",
        "menu_about": "Информация о версии: v1.0 Многоязычная",
        "no_file_selected": "Ningún archivo seleccionado.",    },
    "pt": {
        "title": "     C A L C U L A D O R A  D E  F R E I O  D E  E M E R G Ê N C I A  ",
        "version": "Versão do software : 1.0 2026.08 ",
        "lang_name": "Português",
        "lang_warn": "         × Idioma desconhecido '{value}', usando inglês (en).",
        "step1": "\n[Passo 1] Diretório do programa: {path}",
        "step2": "\n[Passo 2] Procurando arquivo de configuração: {path}",
        "cfg_not_found": "         × Erro: config.json não encontrado",
        "press_exit": "\nPressione Enter para sair...",
        "cfg_lang": "         ✓ Idioma: {name}",
        "cfg_ok_speed": "         ✓ Nome do sinal de velocidade: {name}",
        "cfg_ok_brake": "         ✓ Nome do sinal de freio: {name}",
        "cfg_parse_fail": "         × Falha na análise do arquivo de configuração: {err}",
        "no_file_arg": "         × Nenhum arquivo de dados recebido. Arraste um arquivo .txt para o ícone deste programa.",
        "step3": "\n[Passo 3] Arquivo de dados a processar: {path}",
        "file_not_exist": "         × O arquivo não existe!",
        "read_fail": "         × Não foi possível ler o arquivo: {err}",
        "read_fail_text": "Não foi possível ler o arquivo com nenhuma codificação: {path}",
        "need_two_rows": "         × O arquivo de dados deve conter pelo menos uma linha de cabeçalho e uma linha de dados.",
        "step4": "\n[Passo 4] Cabeçalho do arquivo (total {count} colunas)",
        "time_col": "         Índice da coluna de tempo: {idx} (primeira coluna)",
        "speed_col": "         Índice da coluna de velocidade: {idx} (correspondente a '{name}')",
        "brake_col": "         Índice da coluna de freio: {idx} (correspondente a '{name}')",
        "col_not_found": "         × Coluna de sinal necessária não encontrada no cabeçalho: {err}",
        "valid_rows": "         Linhas de dados válidas lidas: {count} linhas, ignoradas inválidas: {skipped}",
        "time_range": "         Faixa de tempo: {start} ~ {end}",
        "speed_range": "         Faixa de velocidade: {lo:.2f} ~ {hi:.2f} km/h",
        "no_valid_data": "         × Não há dados válidos!",
        "eb_found": "[Passo 5] Ponto EB válido encontrado -> índice:{idx}, tempo:{time}, velocidade:{speed:.2f} km/h ",
        "eb_skipped": "\n         Ponto EB índice:{idx} velocidade {speed:.2f} km/h <=5, ignorado, continuar procurando...\n",
        "eb_fallback": "\n         Nenhum ponto EB encontrado, mas os dados começam em estado de frenagem (0) com velocidade>5, usando início como início de frenagem.\n",
        "eb_none": "\n         × Nenhum início EB válido encontrado (ponto EB com velocidade inicial > 5 km/h).\n",
        "step6_start": "\n[Passo 6] Ponto de início de frenagem -> índice:{idx}, tempo:{time}, velocidade:{speed:.2f} km/h",
        "end_fallback": "         A velocidade nunca caiu abaixo de 0.2 km/h, usando o último ponto de dados como fim de frenagem.",
        "step6_end": "         Ponto de fim de frenagem -> índice:{idx}, tempo:{time}, velocidade:{speed:.2f} km/h",
        "press_calc": "         Pressione Enter para iniciar o cálculo...",
        "result_title": "          R E S U L T A D O S   D E   C Á L C U L O        ",
        "data_points": "  Pontos de dados: {count}",
        "time_interval": "  Intervalo de tempo: {start} ~ {end}",
        "v0": "  Velocidade inicial: {value:.2f} km/h",
        "v_end": "  Velocidade final: {value:.2f} km/h",
        "brake_time": "  Tempo de frenagem: {value:.4f} seg",
        "distance": "  Distância de frenagem: {value:.3f} m",
        "rate_decel": "  Desaceleração de taxa (dv/dt): {value}",
        "avg_decel": "  Desaceleração média (V²/2S): {value}",
        "infinite_dist": "Infinito (distância zero)",
        "infinite_time": "Infinito (tempo zero)",
        "done": "\nProcessamento concluído. Pressione Enter para sair...",
        "press_continue": "\nPressione Enter para continuar...",
        "gui_title": "Resultado do teste de freio",
        "gui_panel_title": "Resumo dos resultados do teste",
        "gui_btn_screenshot": "SALVAR IMAGEM",
        "gui_saved": "Captura de tela salva em:\n{path}",
        "gui_save_fail": "Falha na captura de tela: {err}",
        "gui_no_pillow": "Pillow não está instalado, não é possível tirar uma captura de tela.\nExecute:  pip install pillow",
        "plot_title": "Curva Velocidade - Tempo",
        "axis_x": "Tempo (HH:MM:SS.mmm)",
        "axis_y": "Velocidade (km/h)",
        "legend_speed": "Curva de velocidade",
        "legend_eb": "Sinal EB",
        "legend_start": "Início de frenagem",
        "legend_end": "Fim de frenagem",
        "legend_area": "Distância de frenagem",
        "lbl_v0": "Velocidade inicial v0",
        "lbl_vend": "Velocidade final v_end",
        "lbl_dt": "Intervalo Δt",
        "lbl_dist": "Distância S",
        "gui_file": "Arquivo de dados",
        "gui_label_points": "Pontos de dados",
        "gui_label_interval": "Intervalo de tempo",
        "gui_label_v0": "Velocidade inicial",
        "gui_label_vend": "Velocidade final",
        "gui_label_time": "Tempo de frenagem",
        "gui_label_dist": "Distância de frenagem",
        "gui_label_rate": "Desaceleração de taxa (dv/dt)",
        "gui_label_avg": "Desaceleração média (V²/2S)",
        "gui_pass": "APROVADO",
        "gui_fail": "REPROVADO",
        "gui_req": "Requisito: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "(sem limite)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "Configuração",
        "config_prompt": "Por favor, selecione uma opção:",
        "config_saved": "Configuração salva com sucesso.",
        "config_cancelled": "Configuração cancelada.",
        "config_overlimit": "Configuração fora do alcance",
        "config_lbl_language": "Idioma:",
        "config_lbl_speed": "Sinal de velocidade:",
        "config_lbl_brake": "Sinal de freio:",
        "config_lbl_min": "Desaceleração mín (m/s²):",
        "config_lbl_max": "Desaceleração máx (m/s²):",
        "config_lbl_enable_min": "Ativar limite mín:",
        "config_lbl_enable_max": "Ativar limite máx:",
        "config_lbl_metric": "Métrica de avaliação:",
        "config_btn_save": "Salvar",
        "config_btn_cancel": "Cancelar",
        "config_opt_yes": "Sim",
        "config_opt_no": "Não",
        "config_overlimit_msg": "Configuração fora do alcance: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "Por favor, selecione uma opção:",
        "menu_opt1": "Abrir arquivo de dados",
        "menu_opt2": "Configurar definições",
        "menu_opt3": "Sobre",
        "menu_prompt": "Digite sua escolha (1-3): ",
        "menu_invalid": "Escolha inválida, por favor tente novamente.",
        "file_dialog_title": "Selecionar arquivo de dados",
        "file_filter": "Arquivos de texto (*.txt)|*.txt|Todos os arquivos (*.*)|*.*",
        "menu_about": "Info da versão: v1.0 Multilíngue",
        "no_file_selected": "Файл не выбран.",    },
    "ar": {
        "title": "     ح ا س ب ة  ا l ف ر ا م ل  ا ل ط ا ر ئ ة  ",
        "version": "إصدار البرنامج : 1.0 2026.08 ",
        "lang_name": "العربية",
        "lang_warn": "         × لغة غير معروفة '{value}'، استخدام الإنجليزية (en).",
        "step1": "\n[الخطوة 1] دليل البرنامج: {path}",
        "step2": "\n[الخطوة 2] البحث عن ملف التكوين: {path}",
        "cfg_not_found": "         × خطأ: لم يتم العثور على config.json",
        "press_exit": "\nاضغط Enter للخروج...",
        "cfg_lang": "         ✓ اللغة: {name}",
        "cfg_ok_speed": "         ✓ اسم إشارة السرعة: {name}",
        "cfg_ok_brake": "         ✓ اسم إشارة الفرامل: {name}",
        "cfg_parse_fail": "         × فشل تحليل ملف التكوين: {err}",
        "no_file_arg": "         × لم يتم استلام ملف بيانات. يرجى سحب ملف .txt إلى أيقونة هذا البرنامج.",
        "step3": "\n[الخطوة 3] ملف البيانات المراد معالجته: {path}",
        "file_not_exist": "         × الملف غير موجود!",
        "read_fail": "         × غير قادر على قراءة الملف: {err}",
        "read_fail_text": "غير قادر على قراءة الملف بأي ترميز: {path}",
        "need_two_rows": "         × يجب أن يحتوي ملف البيانات على صف رأس واحد على الأقل وصف بيانات واحد.",
        "step4": "\n[الخطوة 4] رأس الملف (إجمالي {count} أعمدة)",
        "time_col": "         فهرس عمود الوقت: {idx} (العمود الأول)",
        "speed_col": "         فهرس عمود السرعة: {idx} (يتوافق مع '{name}')",
        "brake_col": "         فهرس عمود الفرامل: {idx} (يتوافق مع '{name}')",
        "col_not_found": "         × لم يتم العثور على عمود الإشارة المطلوب في الرأس: {err}",
        "valid_rows": "         قراءة صفوف البيانات الصالحة: {count} صفوف، تم تخطي غير صالحة: {skipped}",
        "time_range": "         نطاق الوقت: {start} ~ {end}",
        "speed_range": "         نطاق السرعة: {lo:.2f} ~ {hi:.2f} كم/ساعة",
        "no_valid_data": "         × لا توجد بيانات صالحة!",
        "eb_found": "[الخطوة 5] تم العثور على نقطة EB صالحة -> الفهرس:{idx}، الوقت:{time}، السرعة:{speed:.2f} كم/ساعة ",
        "eb_skipped": "\n         نقطة EB الفهرس:{idx} السرعة {speed:.2f} كم/ساعة <=5، تم التخطي، متابعة البحث...\n",
        "eb_fallback": "\n         لم يتم العثور على نقطة EB، لكن البيانات تبدأ في حالة الكبح (0) بسرعة>5، استخدام البداية كبداية الكبح.\n",
        "eb_none": "\n         × لم يتم العثور على بداية EB صالحة (نقطة EB بسرعة أولية > 5 كم/ساعة).\n",
        "step6_start": "\n[الخطوة 6] نقطة بداية الكبح -> الفهرس:{idx}، الوقت:{time}، السرعة:{speed:.2f} كم/ساعة",
        "end_fallback": "         لم تنخفض السرعة أبدًا إلى أقل من 0.2 كم/ساعة، استخدام آخر نقطة بيانات كنهاية الكبح.",
        "step6_end": "         نقطة نهاية الكبح -> الفهرس:{idx}، الوقت:{time}، السرعة:{speed:.2f} كم/ساعة",
        "press_calc": "         اضغط Enter لبدء الحساب...",
        "result_title": "          ن ت ا ئ ج  ا l ح س ا ب        ",
        "data_points": "  نقاط البيانات: {count}",
        "time_interval": "  الفترة الزمنية: {start} ~ {end}",
        "v0": "  السرعة الأولية: {value:.2f} كم/ساعة",
        "v_end": "  السرعة النهائية: {value:.2f} كم/ساعة",
        "brake_time": "  وقت الكبح: {value:.4f} ثانية",
        "distance": "  مسافة الكبح: {value:.3f} م",
        "rate_decel": "  تباطؤ المعدل (dv/dt): {value}",
        "avg_decel": "  التباطؤ المتوسط (V²/2S): {value}",
        "infinite_dist": "لانهائي (مسافة صفر)",
        "infinite_time": "لانهائي (وقت صفر)",
        "done": "\nاكتملت المعالجة. اضغط Enter للخروج...",
        "press_continue": "\nاضغط Enter للمتابعة...",
        "gui_title": "نتيجة اختبار الفرامل",
        "gui_panel_title": "ملخص نتائج الاختبار",
        "gui_btn_screenshot": "حفظ الصورة",
        "gui_saved": "تم حفظ لقطة الشاشة في:\n{path}",
        "gui_save_fail": "فشلت لقطة الشاشة: {err}",
        "gui_no_pillow": "Pillow غير مثبت، لا يمكن التقاط لقطة شاشة.\nيرجى التشغيل:  pip install pillow",
        "plot_title": "منحنى السرعة - الوقت",
        "axis_x": "الوقت (HH:MM:SS.mmm)",
        "axis_y": "السرعة (كم/ساعة)",
        "legend_speed": "منحنى السرعة",
        "legend_eb": "إشارة EB",
        "legend_start": "بداية الكبح",
        "legend_end": "نهاية الكبح",
        "legend_area": "مسافة الكبح",
        "lbl_v0": "السرعة الأولية v0",
        "lbl_vend": "السرعة النهائية v_end",
        "lbl_dt": "الفترة Δt",
        "lbl_dist": "المسافة S",
        "gui_file": "ملف البيانات",
        "gui_label_points": "نقاط البيانات",
        "gui_label_interval": "الفترة الزمنية",
        "gui_label_v0": "السرعة الأولية",
        "gui_label_vend": "السرعة النهائية",
        "gui_label_time": "وقت الكبح",
        "gui_label_dist": "مسافة الكبح",
        "gui_label_rate": "تباطؤ المعدل (dv/dt)",
        "gui_label_avg": "التباطؤ المتوسط (V²/2S)",
        "gui_pass": "نجح",
        "gui_fail": "فشل",
        "gui_req": "المتطلبات: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} م/ث²",
        "gui_req_max_only": "{metric} ≤ {maxv} م/ث²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} م/ث²",
        "gui_req_none": "(لا حد)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "إعداد التكوين",
        "config_prompt": "يرجى تحديد خيار:",
        "config_saved": "تم حفظ التكوين بنجاح.",
        "config_cancelled": "تم إلغاء التكوين.",
        "config_overlimit": "التكوين خارج النطاق",
        "config_lbl_language": "اللغة:",
        "config_lbl_speed": "إشارة السرعة:",
        "config_lbl_brake": "إشارة الفرامل:",
        "config_lbl_min": "الحد الأدنى للتباطؤ (م/ث²):",
        "config_lbl_max": "الحد الأقصى للتباطؤ (م/ث²):",
        "config_lbl_enable_min": "تمكين الحد الأدنى:",
        "config_lbl_enable_max": "تمكين الحد الأقصى:",
        "config_lbl_metric": "مقياس التقييم:",
        "config_btn_save": "حفظ",
        "config_btn_cancel": "إلغاء",
        "config_opt_yes": "نعم",
        "config_opt_no": "لا",
        "config_overlimit_msg": "التكوين خارج النطاق: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "يرجى تحديد خيار:",
        "menu_opt1": "فتح ملف البيانات",
        "menu_opt2": "تكوين الإعدادات",
        "menu_opt3": "حول",
        "menu_prompt": "أدخل اختيارك (1-3): ",
        "menu_invalid": "اختيار غير صالح، يرجى المحاولة مرة أخرى.",
        "file_dialog_title": "اختر ملف البيانات",
        "file_filter": "ملفات نصية (*.txt)|*.txt|جميع الملفات (*.*)|*.*",
        "menu_about": "معلومات الإصدار: v1.0 متعدد اللغات",
        "no_file_selected": "Nenhum arquivo selecionado.",    },
    "zh_tw": {
        "title": "            緊 急 制 動 計 算 器  ",
        "version": "軟件版本 : 1.0 2026.08 ",
        "lang_name": "繁體中文",
        "lang_warn": "         × 未知語言「{value}」，已使用英文（en）。",
        "step1": "\n[步驟 1] 程序目錄：{path}",
        "step2": "\n[步驟 2] 正在查找配置文件：{path}",
        "cfg_not_found": "         × 錯誤：未找到 config.json",
        "press_exit": "\n按回車鍵退出...",
        "cfg_lang": "         ✓ 語言：{name}",
        "cfg_ok_speed": "         ✓ 速度信號名稱：{name}",
        "cfg_ok_brake": "         ✓ 制動信號名稱：{name}",
        "cfg_parse_fail": "         × 配置文件解析失敗：{err}",
        "no_file_arg": "         × 未收到數據文件，請將 .txt 文件拖放到本程序圖標上。",
        "step3": "\n[步驟 3] 待處理的數據文件：{path}",
        "file_not_exist": "         × 文件不存在！",
        "read_fail": "         × 無法讀取文件：{err}",
        "read_fail_text": "無法用任何編碼讀取文件：{path}",
        "need_two_rows": "         × 數據文件必須至少包含一行表頭和一行數據。",
        "step4": "\n[步驟 4] 文件表頭（共 {count} 列）",
        "time_col": "         時間列索引：{idx}（第一列）",
        "speed_col": "         速度列索引：{idx}（對應「{name}」）",
        "brake_col": "         制動列索引：{idx}（對應「{name}」）",
        "col_not_found": "         × 表頭中未找到所需的信號列：{err}",
        "valid_rows": "         已讀取有效數據行：{count} 行，跳過無效：{skipped}",
        "time_range": "         時間範圍：{start} ~ {end}",
        "speed_range": "         速度範圍：{lo:.2f} ~ {hi:.2f} 公里/小時",
        "no_valid_data": "         × 沒有有效數據！",
        "eb_found": "[步驟 5] 找到有效 EB 點 -> 索引:{idx}，時間:{time}，速度:{speed:.2f} 公里/小時 ",
        "eb_skipped": "\n         EB 點索引:{idx} 速度 {speed:.2f} 公里/小時 <=5，跳過，繼續搜索...\n",
        "eb_fallback": "\n         未找到 EB 點，但數據以制動狀態（0）開始且速度>5，使用開始作為制動開始。\n",
        "eb_none": "\n         × 未找到有效的 EB 開始（初始速度 > 5 公里/小時的 EB 點）。\n",
        "step6_start": "\n[步驟 6] 制動開始點 -> 索引:{idx}，時間:{time}，速度:{speed:.2f} 公里/小時",
        "end_fallback": "         速度從未降到 0.2 公里/小時以下，使用最後一個數據點作為制動結束。",
        "step6_end": "         制動結束點 -> 索引:{idx}，時間:{time}，速度:{speed:.2f} 公里/小時",
        "press_calc": "         按回車鍵開始計算...",
        "result_title": "          計 算 結 果        ",
        "data_points": "  數據點：{count}",
        "time_interval": "  時間間隔：{start} ~ {end}",
        "v0": "  初始速度：{value:.2f} 公里/小時",
        "v_end": "  最終速度：{value:.2f} 公里/小時",
        "brake_time": "  制動時間：{value:.4f} 秒",
        "distance": "  制動距離：{value:.3f} 米",
        "rate_decel": "  速率減速度（dv/dt）：{value}",
        "avg_decel": "  平均減速度（V²/2S）：{value}",
        "infinite_dist": "無窮大（距離為零）",
        "infinite_time": "無窮大（時間為零）",
        "done": "\n處理完成。按回車鍵退出...",
        "press_continue": "\n按回車鍵繼續...",
        "gui_title": "制動測試結果",
        "gui_panel_title": "測試結果摘要",
        "gui_btn_screenshot": "保存圖片",
        "gui_saved": "截圖已保存到：\n{path}",
        "gui_save_fail": "截圖失敗：{err}",
        "gui_no_pillow": "Pillow 未安裝，無法截圖。\n請運行：  pip install pillow",
        "plot_title": "速度 - 時間曲線",
        "axis_x": "時間（HH:MM:SS.mmm）",
        "axis_y": "速度（公里/小時）",
        "legend_speed": "速度曲線",
        "legend_eb": "EB 信號",
        "legend_start": "制動開始",
        "legend_end": "制動結束",
        "legend_area": "制動距離",
        "lbl_v0": "初始速度 v0",
        "lbl_vend": "最終速度 v_end",
        "lbl_dt": "間隔 Δt",
        "lbl_dist": "距離 S",
        "gui_file": "數據文件",
        "gui_label_points": "數據點",
        "gui_label_interval": "時間間隔",
        "gui_label_v0": "初始速度",
        "gui_label_vend": "最終速度",
        "gui_label_time": "制動時間",
        "gui_label_dist": "制動距離",
        "gui_label_rate": "速率減速度（dv/dt）",
        "gui_label_avg": "平均減速度（V²/2S）",
        "gui_pass": "通過",
        "gui_fail": "未通過",
        "gui_req": "要求：{cond}",
        "gui_req_min_only": "{metric} ≥ {minv} 米/秒²",
        "gui_req_max_only": "{metric} ≤ {maxv} 米/秒²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} 米/秒²",
        "gui_req_none": "（無限制）",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "配置設置",
        "config_prompt": "請選擇一個選項：",
        "config_saved": "配置已成功保存。",
        "config_cancelled": "配置已取消。",
        "config_overlimit": "配置超出範圍",
        "config_lbl_language": "語言：",
        "config_lbl_speed": "速度信號：",
        "config_lbl_brake": "制動信號：",
        "config_lbl_min": "最小減速度（米/秒²）：",
        "config_lbl_max": "最大減速度（米/秒²）：",
        "config_lbl_enable_min": "啟用最小限制：",
        "config_lbl_enable_max": "啟用最大限制：",
        "config_lbl_metric": "評估指標：",
        "config_btn_save": "保存",
        "config_btn_cancel": "取消",
        "config_opt_yes": "是",
        "config_opt_no": "否",
        "config_overlimit_msg": "配置超出範圍：最小減速度 >= 0，最大減速度 > 0，且最小減速度 <= 最大減速度。",
        "menu_title": "請選擇操作：",
        "menu_opt1": "打開數據文件",
        "menu_opt2": "配置信息",
        "menu_opt3": "關於",
        "menu_prompt": "請輸入選擇（1-3）：",
        "menu_invalid": "無效選擇，請重新輸入。",
        "file_dialog_title": "選擇數據文件",
        "file_filter": "文本文件 (*.txt)|*.txt|所有文件 (*.*)|*.*",
        "menu_about": "版本資訊：v1.0 多語言版",
        "no_file_selected": "لم يتم اختيار ملف.",    },
    "ko": {
        "title": "     비 상 제 동 계 산 기  ",
        "version": "소프트웨어 버전 : 1.0 2026.08 ",
        "lang_name": "한국어",
        "lang_warn": "         × 알 수 없는 언어 '{value}', 영어(en) 사용.",
        "step1": "\n[단계 1] 프로그램 디렉터리: {path}",
        "step2": "\n[단계 2] 구성 파일 찾기: {path}",
        "cfg_not_found": "         × 오류: config.json을 찾을 수 없습니다",
        "press_exit": "\n종료하려면 Enter 키를 누르세요...",
        "cfg_lang": "         ✓ 언어: {name}",
        "cfg_ok_speed": "         ✓ 속도 신호 이름: {name}",
        "cfg_ok_brake": "         ✓ 브레이크 신호 이름: {name}",
        "cfg_parse_fail": "         × 구성 파일 구문 분석 실패: {err}",
        "no_file_arg": "         × 데이터 파일을 받지 못했습니다. .txt 파일을 이 프로그램 아이콘에 드래그하세요.",
        "step3": "\n[단계 3] 처리할 데이터 파일: {path}",
        "file_not_exist": "         × 파일이 존재하지 않습니다!",
        "read_fail": "         × 파일을 읽을 수 없습니다: {err}",
        "read_fail_text": "어떤 인코딩으로도 파일을 읽을 수 없습니다: {path}",
        "need_two_rows": "         × 데이터 파일에는 헤더 행과 데이터 행이 하나 이상 포함되어야 합니다.",
        "step4": "\n[단계 4] 파일 헤더 (총 {count}개 열)",
        "time_col": "         시간 열 인덱스: {idx} (첫 번째 열)",
        "speed_col": "         속도 열 인덱스: {idx} ('{name}'에 해당)",
        "brake_col": "         브레이크 열 인덱스: {idx} ('{name}'에 해당)",
        "col_not_found": "         × 헤더에서 필요한 신호 열을 찾을 수 없습니다: {err}",
        "valid_rows": "         유효한 데이터 행 읽기: {count}행, 건너뛴 무효: {skipped}",
        "time_range": "         시간 범위: {start} ~ {end}",
        "speed_range": "         속도 범위: {lo:.2f} ~ {hi:.2f} km/h",
        "no_valid_data": "         × 유효한 데이터가 없습니다!",
        "eb_found": "[단계 5] 유효한 EB 지점 발견 -> 인덱스:{idx}, 시간:{time}, 속도:{speed:.2f} km/h ",
        "eb_skipped": "\n         EB 지점 인덱스:{idx} 속도 {speed:.2f} km/h <=5, 건너뛰기, 계속 검색...\n",
        "eb_fallback": "\n         EB 지점을 찾을 수 없지만 데이터가 제동 상태(0)에서 속도>5로 시작하므로 시작을 제동 시작으로 사용합니다.\n",
        "eb_none": "\n         × 유효한 EB 시작을 찾을 수 없습니다(초기 속도 > 5 km/h인 EB 지점).\n",
        "step6_start": "\n[단계 6] 제동 시작점 -> 인덱스:{idx}, 시간:{time}, 속도:{speed:.2f} km/h",
        "end_fallback": "         속도가 0.2 km/h 아래로 떨어지지 않았으므로 마지막 데이터 지점을 제동 종료로 사용합니다.",
        "step6_end": "         제동 종료점 -> 인덱스:{idx}, 시간:{time}, 속도:{speed:.2f} km/h",
        "press_calc": "         계산을 시작하려면 Enter 키를 누르세요...",
        "result_title": "          계 산 결 과        ",
        "data_points": "  데이터 포인트: {count}",
        "time_interval": "  시간 간격: {start} ~ {end}",
        "v0": "  초기 속도: {value:.2f} km/h",
        "v_end": "  최종 속도: {value:.2f} km/h",
        "brake_time": "  제동 시간: {value:.4f} 초",
        "distance": "  제동 거리: {value:.3f} m",
        "rate_decel": "  속도 감속도(dv/dt): {value}",
        "avg_decel": "  평균 감속도(V²/2S): {value}",
        "infinite_dist": "무한대(거리 0)",
        "infinite_time": "무한대(시간 0)",
        "done": "\n처리가 완료되었습니다. 종료하려면 Enter 키를 누르세요...",
        "press_continue": "\n계속하려면 Enter 키를 누르세요...",
        "gui_title": "브레이크 테스트 결과",
        "gui_panel_title": "테스트 결과 요약",
        "gui_btn_screenshot": "사진 저장",
        "gui_saved": "스크린샷이 저장되었습니다:\n{path}",
        "gui_save_fail": "스크린샷 실패: {err}",
        "gui_no_pillow": "Pillow가 설치되지 않아 스크린샷을 찍을 수 없습니다.\n실행하세요:  pip install pillow",
        "plot_title": "속도 - 시간 곡선",
        "axis_x": "시간 (HH:MM:SS.mmm)",
        "axis_y": "속도 (km/h)",
        "legend_speed": "속도 곡선",
        "legend_eb": "EB 신호",
        "legend_start": "제동 시작",
        "legend_end": "제동 종료",
        "legend_area": "제동 거리",
        "lbl_v0": "초기 속도 v0",
        "lbl_vend": "최종 속도 v_end",
        "lbl_dt": "간격 Δt",
        "lbl_dist": "거리 S",
        "gui_file": "데이터 파일",
        "gui_label_points": "데이터 포인트",
        "gui_label_interval": "시간 간격",
        "gui_label_v0": "초기 속도",
        "gui_label_vend": "최종 속도",
        "gui_label_time": "제동 시간",
        "gui_label_dist": "제동 거리",
        "gui_label_rate": "속도 감속도(dv/dt)",
        "gui_label_avg": "평균 감속도(V²/2S)",
        "gui_pass": "합격",
        "gui_fail": "불합격",
        "gui_req": "요구사항: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "(제한 없음)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "구성 설정",
        "config_prompt": "옵션을 선택하세요:",
        "config_saved": "구성이 성공적으로 저장되었습니다.",
        "config_cancelled": "구성이 취소되었습니다.",
        "config_overlimit": "구성이 범위를 벗어났습니다",
        "config_lbl_language": "언어:",
        "config_lbl_speed": "속도 신호:",
        "config_lbl_brake": "브레이크 신호:",
        "config_lbl_min": "최소 감속도 (m/s²):",
        "config_lbl_max": "최대 감속도 (m/s²):",
        "config_lbl_enable_min": "최소 제한 활성화:",
        "config_lbl_enable_max": "최대 제한 활성화:",
        "config_lbl_metric": "평가 지표:",
        "config_btn_save": "저장",
        "config_btn_cancel": "취소",
        "config_opt_yes": "예",
        "config_opt_no": "아니오",
        "config_overlimit_msg": "구성이 범위를 벗어났습니다: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "옵션을 선택하세요:",
        "menu_opt1": "데이터 파일 열기",
        "menu_opt2": "설정 구성",
        "menu_opt3": "정보",
        "menu_prompt": "선택을 입력하세요 (1-3): ",
        "menu_invalid": "잘못된 선택입니다. 다시 시도하세요.",
        "file_dialog_title": "데이터 파일 선택",
        "file_filter": "텍스트 파일 (*.txt)|*.txt|모든 파일 (*.*)|*.*",
        "menu_about": "버전 정보: v1.0 다국어판",
        "no_file_selected": "未選擇文件。",    },
    "th": {
        "title": "     เ ค รื่ อ ง คิ ด เ ล ข เ บ ร ก ฉุ ก เ ฉิ น  ",
        "version": "เวอร์ชันซอฟต์แวร์ : 1.0 2026.08 ",
        "lang_name": "ไทย",
        "lang_warn": "         × ภาษาที่ไม่รู้จัก '{value}' ใช้ภาษาอังกฤษ (en)",
        "step1": "\n[ขั้นตอน 1] ไดเรกทอรีโปรแกรม: {path}",
        "step2": "\n[ขั้นตอน 2] กำลังค้นหาไฟล์กำหนดค่า: {path}",
        "cfg_not_found": "         × ข้อผิดพลาด: ไม่พบ config.json",
        "press_exit": "\nกด Enter เพื่อออก...",
        "cfg_lang": "         ✓ ภาษา: {name}",
        "cfg_ok_speed": "         ✓ ชื่อสัญญาณความเร็ว: {name}",
        "cfg_ok_brake": "         ✓ ชื่อสัญญาณเบรก: {name}",
        "cfg_parse_fail": "         × การแยกวิเคราะห์ไฟล์กำหนดค่าล้มเหลว: {err}",
        "no_file_arg": "         × ไม่ได้รับไฟล์ข้อมูล โปรดลากไฟล์ .txt ไปยังไอคอนโปรแกรมนี้",
        "step3": "\n[ขั้นตอน 3] ไฟล์ข้อมูลที่จะประมวลผล: {path}",
        "file_not_exist": "         × ไฟล์ไม่มีอยู่!",
        "read_fail": "         × ไม่สามารถอ่านไฟล์: {err}",
        "read_fail_text": "ไม่สามารถอ่านไฟล์ด้วยการเข้ารหัสใดๆ: {path}",
        "need_two_rows": "         × ไฟล์ข้อมูลต้องมีแถวส่วนหัวอย่างน้อยหนึ่งแถวและแถวข้อมูลหนึ่งแถว",
        "step4": "\n[ขั้นตอน 4] ส่วนหัวไฟล์ (ทั้งหมด {count} คอลัมน์)",
        "time_col": "         ดัชนีคอลัมน์เวลา: {idx} (คอลัมน์แรก)",
        "speed_col": "         ดัชนีคอลัมน์ความเร็ว: {idx} (ตรงกับ '{name}')",
        "brake_col": "         ดัชนีคอลัมน์เบรก: {idx} (ตรงกับ '{name}')",
        "col_not_found": "         × ไม่พบคอลัมน์สัญญาณที่ต้องการในส่วนหัว: {err}",
        "valid_rows": "         อ่านแถวข้อมูลที่ถูกต้อง: {count} แถว, ข้ามไม่ถูกต้อง: {skipped}",
        "time_range": "         ช่วงเวลา: {start} ~ {end}",
        "speed_range": "         ช่วงความเร็ว: {lo:.2f} ~ {hi:.2f} กม./ชม.",
        "no_valid_data": "         × ไม่มีข้อมูลที่ถูกต้อง!",
        "eb_found": "[ขั้นตอน 5] พบจุด EB ที่ถูกต้อง -> ดัชนี:{idx}, เวลา:{time}, ความเร็ว:{speed:.2f} กม./ชม. ",
        "eb_skipped": "\n         จุด EB ดัชนี:{idx} ความเร็ว {speed:.2f} กม./ชม. <=5, ข้าม, ค้นหาต่อ...\n",
        "eb_fallback": "\n         ไม่พบจุด EB แต่ข้อมูลเริ่มในสถานะเบรก (0) ที่ความเร็ว>5, ใช้จุดเริ่มต้นเป็นจุดเริ่มเบรก\n",
        "eb_none": "\n         × ไม่พบจุดเริ่ม EB ที่ถูกต้อง (จุด EB ที่มีความเร็วเริ่มต้น > 5 กม./ชม.)\n",
        "step6_start": "\n[ขั้นตอน 6] จุดเริ่มเบรก -> ดัชนี:{idx}, เวลา:{time}, ความเร็ว:{speed:.2f} กม./ชม.",
        "end_fallback": "         ความเร็วไม่เคยลดลงต่ำกว่า 0.2 กม./ชม., ใช้จุดข้อมูลสุดท้ายเป็นจุดสิ้นสุดเบรก",
        "step6_end": "         จุดสิ้นสุดเบรก -> ดัชนี:{idx}, เวลา:{time}, ความเร็ว:{speed:.2f} กม./ชม.",
        "press_calc": "         กด Enter เพื่อเริ่มการคำนวณ...",
        "result_title": "          ผ ล ล ั พ ธ์ ก า ร คำ น ว ณ        ",
        "data_points": "  จุดข้อมูล: {count}",
        "time_interval": "  ช่วงเวลา: {start} ~ {end}",
        "v0": "  ความเร็วเริ่มต้น: {value:.2f} กม./ชม.",
        "v_end": "  ความเร็วสุดท้าย: {value:.2f} กม./ชม.",
        "brake_time": "  เวลาเบรก: {value:.4f} วินาที",
        "distance": "  ระยะเบรก: {value:.3f} ม.",
        "rate_decel": "  อัตราชะลอ (dv/dt): {value}",
        "avg_decel": "  ค่าเฉลี่ยชะลอ (V²/2S): {value}",
        "infinite_dist": "ไม่สิ้นสุด (ระยะทางศูนย์)",
        "infinite_time": "ไม่สิ้นสุด (เวลาศูนย์)",
        "done": "\nประมวลผลเสร็จสิ้น กด Enter เพื่อออก...",
        "press_continue": "\nกด Enter เพื่อดำเนินการต่อ...",
        "gui_title": "ผลการทดสอบเบรก",
        "gui_panel_title": "สรุปผลการทดสอบ",
        "gui_btn_screenshot": "บันทึกรูปภาพ",
        "gui_saved": "บันทึกภาพหน้าจอไปที่:\n{path}",
        "gui_save_fail": "จับภาพหน้าจอล้มเหลว: {err}",
        "gui_no_pillow": "ไม่ได้ติดตั้ง Pillow ไม่สามารถจับภาพหน้าจอได้\nโปรดรัน:  pip install pillow",
        "plot_title": "เส้นโค้งความเร็ว - เวลา",
        "axis_x": "เวลา (HH:MM:SS.mmm)",
        "axis_y": "ความเร็ว (กม./ชม.)",
        "legend_speed": "เส้นโค้งความเร็ว",
        "legend_eb": "สัญญาณ EB",
        "legend_start": "เริ่มเบรก",
        "legend_end": "สิ้นสุดเบรก",
        "legend_area": "ระยะเบรก",
        "lbl_v0": "ความเร็วเริ่มต้น v0",
        "lbl_vend": "ความเร็วสุดท้าย v_end",
        "lbl_dt": "ช่วง Δt",
        "lbl_dist": "ระยะ S",
        "gui_file": "ไฟล์ข้อมูล",
        "gui_label_points": "จุดข้อมูล",
        "gui_label_interval": "ช่วงเวลา",
        "gui_label_v0": "ความเร็วเริ่มต้น",
        "gui_label_vend": "ความเร็วสุดท้าย",
        "gui_label_time": "เวลาเบรก",
        "gui_label_dist": "ระยะเบรก",
        "gui_label_rate": "อัตราชะลอ (dv/dt)",
        "gui_label_avg": "ค่าเฉลี่ยชะลอ (V²/2S)",
        "gui_pass": "ผ่าน",
        "gui_fail": "ไม่ผ่าน",
        "gui_req": "ข้อกำหนด: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "(ไม่มีขีดจำกัด)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "ตั้งค่าคอนฟิก",
        "config_prompt": "โปรดเลือกตัวเลือก:",
        "config_saved": "บันทึกการกำหนดค่าสำเร็จแล้ว",
        "config_cancelled": "ยกเลิกการกำหนดค่าแล้ว",
        "config_overlimit": "การกำหนดค่าเกินขอบเขต",
        "config_lbl_language": "ภาษา:",
        "config_lbl_speed": "สัญญาณความเร็ว:",
        "config_lbl_brake": "สัญญาณเบรก:",
        "config_lbl_min": "ชะลอขั้นต่ำ (m/s²):",
        "config_lbl_max": "ชะลอสูงสุด (m/s²):",
        "config_lbl_enable_min": "เปิดใช้ขีดจำกัดขั้นต่ำ:",
        "config_lbl_enable_max": "เปิดใช้ขีดจำกัดสูงสุด:",
        "config_lbl_metric": "เมตริกการประเมิน:",
        "config_btn_save": "บันทึก",
        "config_btn_cancel": "ยกเลิก",
        "config_opt_yes": "ใช่",
        "config_opt_no": "ไม่ใช่",
        "config_overlimit_msg": "การกำหนดค่าเกินขอบเขต: min_decel >= 0, max_decel > 0, min_decel <= max_decel",
        "menu_title": "โปรดเลือกตัวเลือก:",
        "menu_opt1": "เปิดไฟล์ข้อมูล",
        "menu_opt2": "กำหนดค่าการตั้งค่า",
        "menu_opt3": "เกี่ยวกับ",
        "menu_prompt": "ป้อนตัวเลือกของคุณ (1-3): ",
        "menu_invalid": "ตัวเลือกไม่ถูกต้อง โปรดลองอีกครั้ง",
        "file_dialog_title": "เลือกไฟล์ข้อมูล",
        "file_filter": "ไฟล์ข้อความ (*.txt)|*.txt|ไฟล์ทั้งหมด (*.*)|*.*",
        "menu_about": "ข้อมูลเวอร์ชัน: v1.0 หลายภาษา",
        "no_file_selected": "파일이 선택되지 않았습니다.",    },
    "it": {
        "title": "     C A L C O L A T O R E  F R E N O  D ' E M E R G E N Z A  ",
        "version": "Versione software : 1.0 2026.08 ",
        "lang_name": "Italiano",
        "lang_warn": "         × Lingua sconosciuta '{value}', usando inglese (en).",
        "step1": "\n[Passo 1] Directory del programma: {path}",
        "step2": "\n[Passo 2] Ricerca del file di configurazione: {path}",
        "cfg_not_found": "         × Errore: config.json non trovato",
        "press_exit": "\nPremi Invio per uscire...",
        "cfg_lang": "         ✓ Lingua: {name}",
        "cfg_ok_speed": "         ✓ Nome segnale velocità: {name}",
        "cfg_ok_brake": "         ✓ Nome segnale freno: {name}",
        "cfg_parse_fail": "         × Analisi del file di configurazione non riuscita: {err}",
        "no_file_arg": "         × Nessun file di dati ricevuto. Trascina un file .txt sull'icona di questo programma.",
        "step3": "\n[Passo 3] File di dati da elaborare: {path}",
        "file_not_exist": "         × Il file non esiste!",
        "read_fail": "         × Impossibile leggere il file: {err}",
        "read_fail_text": "Impossibile leggere il file con qualsiasi codifica: {path}",
        "need_two_rows": "         × Il file di dati deve contenere almeno una riga di intestazione e una riga di dati.",
        "step4": "\n[Passo 4] Intestazione del file (totale {count} colonne)",
        "time_col": "         Indice colonna tempo: {idx} (prima colonna)",
        "speed_col": "         Indice colonna velocità: {idx} (corrispondente a '{name}')",
        "brake_col": "         Indice colonna freno: {idx} (corrispondente a '{name}')",
        "col_not_found": "         × Colonna segnale richiesta non trovata nell'intestazione: {err}",
        "valid_rows": "         Righe di dati valide lette: {count} righe, saltate non valide: {skipped}",
        "time_range": "         Intervallo di tempo: {start} ~ {end}",
        "speed_range": "         Intervallo di velocità: {lo:.2f} ~ {hi:.2f} km/h",
        "no_valid_data": "         × Nessun dato valido!",
        "eb_found": "[Passo 5] Punto EB valido trovato -> indice:{idx}, tempo:{time}, velocità:{speed:.2f} km/h ",
        "eb_skipped": "\n         Punto EB indice:{idx} velocità {speed:.2f} km/h <=5, saltato, continua la ricerca...\n",
        "eb_fallback": "\n         Nessun punto EB trovato, ma i dati iniziano in stato di frenata (0) con velocità>5, usando l'inizio come inizio frenata.\n",
        "eb_none": "\n         × Nessun inizio EB valido trovato (punto EB con velocità iniziale > 5 km/h).\n",
        "step6_start": "\n[Passo 6] Punto di inizio frenata -> indice:{idx}, tempo:{time}, velocità:{speed:.2f} km/h",
        "end_fallback": "         La velocità non è mai scesa sotto 0,2 km/h, usando l'ultimo punto dati come fine frenata.",
        "step6_end": "         Punto di fine frenata -> indice:{idx}, tempo:{time}, velocità:{speed:.2f} km/h",
        "press_calc": "         Premi Invio per avviare il calcolo...",
        "result_title": "          R I S U L T A T I   D E L   C A L C O L O        ",
        "data_points": "  Punti dati: {count}",
        "time_interval": "  Intervallo di tempo: {start} ~ {end}",
        "v0": "  Velocità iniziale: {value:.2f} km/h",
        "v_end": "  Velocità finale: {value:.2f} km/h",
        "brake_time": "  Tempo di frenata: {value:.4f} sec",
        "distance": "  Distanza di frenata: {value:.3f} m",
        "rate_decel": "  Decelerazione di tasso (dv/dt): {value}",
        "avg_decel": "  Decelerazione media (V²/2S): {value}",
        "infinite_dist": "Infinito (distanza zero)",
        "infinite_time": "Infinito (tempo zero)",
        "done": "\nElaborazione completata. Premi Invio per uscire...",
        "press_continue": "\nPremi Invio per continuare...",
        "gui_title": "Risultato test freno",
        "gui_panel_title": "Riepilogo risultati test",
        "gui_btn_screenshot": "SALVA IMMAGINE",
        "gui_saved": "Screenshot salvato in:\n{path}",
        "gui_save_fail": "Screenshot fallito: {err}",
        "gui_no_pillow": "Pillow non è installato, impossibile fare uno screenshot.\nEsegui:  pip install pillow",
        "plot_title": "Curva Velocità - Tempo",
        "axis_x": "Tempo (HH:MM:SS.mmm)",
        "axis_y": "Velocità (km/h)",
        "legend_speed": "Curva di velocità",
        "legend_eb": "Segnale EB",
        "legend_start": "Inizio frenata",
        "legend_end": "Fine frenata",
        "legend_area": "Distanza di frenata",
        "lbl_v0": "Velocità iniziale v0",
        "lbl_vend": "Velocità finale v_end",
        "lbl_dt": "Intervallo Δt",
        "lbl_dist": "Distanza S",
        "gui_file": "File di dati",
        "gui_label_points": "Punti dati",
        "gui_label_interval": "Intervallo di tempo",
        "gui_label_v0": "Velocità iniziale",
        "gui_label_vend": "Velocità finale",
        "gui_label_time": "Tempo di frenata",
        "gui_label_dist": "Distanza di frenata",
        "gui_label_rate": "Decelerazione di tasso (dv/dt)",
        "gui_label_avg": "Decelerazione media (V²/2S)",
        "gui_pass": "SUPERATO",
        "gui_fail": "FALLITO",
        "gui_req": "Requisito: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "(nessun limite)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "Impostazione configurazione",
        "config_prompt": "Si prega di selezionare un'opzione:",
        "config_saved": "Configurazione salvata con successo.",
        "config_cancelled": "Configurazione annullata.",
        "config_overlimit": "Configurazione fuori intervallo",
        "config_lbl_language": "Lingua:",
        "config_lbl_speed": "Segnale velocità:",
        "config_lbl_brake": "Segnale freno:",
        "config_lbl_min": "Decel min (m/s²):",
        "config_lbl_max": "Decel max (m/s²):",
        "config_lbl_enable_min": "Abilita limite min:",
        "config_lbl_enable_max": "Abilita limite max:",
        "config_lbl_metric": "Metrica di valutazione:",
        "config_btn_save": "Salva",
        "config_btn_cancel": "Annulla",
        "config_opt_yes": "Sì",
        "config_opt_no": "No",
        "config_overlimit_msg": "Configurazione fuori intervallo: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "Si prega di selezionare un'opzione:",
        "menu_opt1": "Apri file di dati",
        "menu_opt2": "Configura impostazioni",
        "menu_opt3": "Informazioni",
        "menu_prompt": "Inserisci la tua scelta (1-3): ",
        "menu_invalid": "Scelta non valida, riprova.",
        "file_dialog_title": "Seleziona file di dati",
        "file_filter": "File di testo (*.txt)|*.txt|Tutti i file (*.*)|*.*",
        "menu_about": "Info versione: v1.0 Multilingue",
        "no_file_selected": "ไม่ได้เลือกไฟล์",    },
    "vi": {
        "title": "     M Á Y  T Í N H  P H A N H  K H Ẩ N  C Ấ P  ",
        "version": "Phiên bản phần mềm : 1.0 2026.08 ",
        "lang_name": "Tiếng Việt",
        "lang_warn": "         × Ngôn ngữ không xác định '{value}', sử dụng tiếng Anh (en).",
        "step1": "\n[Bước 1] Thư mục chương trình: {path}",
        "step2": "\n[Bước 2] Tìm kiếm tệp cấu hình: {path}",
        "cfg_not_found": "         × Lỗi: không tìm thấy config.json",
        "press_exit": "\nNhấn Enter để thoát...",
        "cfg_lang": "         ✓ Ngôn ngữ: {name}",
        "cfg_ok_speed": "         ✓ Tên tín hiệu tốc độ: {name}",
        "cfg_ok_brake": "         ✓ Tên tín hiệu phanh: {name}",
        "cfg_parse_fail": "         × Phân tích tệp cấu hình thất bại: {err}",
        "no_file_arg": "         × Không nhận được tệp dữ liệu. Vui lòng kéo tệp .txt vào biểu tượng chương trình này.",
        "step3": "\n[Bước 3] Tệp dữ liệu để xử lý: {path}",
        "file_not_exist": "         × Tệp không tồn tại!",
        "read_fail": "         × Không thể đọc tệp: {err}",
        "read_fail_text": "Không thể đọc tệp với bất kỳ mã hóa nào: {path}",
        "need_two_rows": "         × Tệp dữ liệu phải chứa ít nhất một hàng tiêu đề và một hàng dữ liệu.",
        "step4": "\n[Bước 4] Tiêu đề tệp (tổng {count} cột)",
        "time_col": "         Chỉ số cột thời gian: {idx} (cột đầu tiên)",
        "speed_col": "         Chỉ số cột tốc độ: {idx} (tương ứng với '{name}')",
        "brake_col": "         Chỉ số cột phanh: {idx} (tương ứng với '{name}')",
        "col_not_found": "         × Không tìm thấy cột tín hiệu bắt buộc trong tiêu đề: {err}",
        "valid_rows": "         Đọc các hàng dữ liệu hợp lệ: {count} hàng, bỏ qua không hợp lệ: {skipped}",
        "time_range": "         Phạm vi thời gian: {start} ~ {end}",
        "speed_range": "         Phạm vi tốc độ: {lo:.2f} ~ {hi:.2f} km/h",
        "no_valid_data": "         × Không có dữ liệu hợp lệ!",
        "eb_found": "[Bước 5] Tìm thấy điểm EB hợp lệ -> chỉ số:{idx}, thời gian:{time}, tốc độ:{speed:.2f} km/h ",
        "eb_skipped": "\n         Điểm EB chỉ số:{idx} tốc độ {speed:.2f} km/h <=5, bỏ qua, tiếp tục tìm kiếm...\n",
        "eb_fallback": "\n         Không tìm thấy điểm EB, nhưng dữ liệu bắt đầu ở trạng thái phanh (0) với tốc độ>5, sử dụng đầu làm điểm bắt đầu phanh.\n",
        "eb_none": "\n         × Không tìm thấy điểm bắt đầu EB hợp lệ (điểm EB với tốc độ ban đầu > 5 km/h).\n",
        "step6_start": "\n[Bước 6] Điểm bắt đầu phanh -> chỉ số:{idx}, thời gian:{time}, tốc độ:{speed:.2f} km/h",
        "end_fallback": "         Tốc độ không bao giờ giảm xuống dưới 0,2 km/h, sử dụng điểm dữ liệu cuối cùng làm điểm kết thúc phanh.",
        "step6_end": "         Điểm kết thúc phanh -> chỉ số:{idx}, thời gian:{time}, tốc độ:{speed:.2f} km/h",
        "press_calc": "         Nhấn Enter để bắt đầu tính toán...",
        "result_title": "          K Ế T  Q U Ả  T Í N H  T O Á N        ",
        "data_points": "  Điểm dữ liệu: {count}",
        "time_interval": "  Khoảng thời gian: {start} ~ {end}",
        "v0": "  Tốc độ ban đầu: {value:.2f} km/h",
        "v_end": "  Tốc độ cuối cùng: {value:.2f} km/h",
        "brake_time": "  Thời gian phanh: {value:.4f} giây",
        "distance": "  Quãng đường phanh: {value:.3f} m",
        "rate_decel": "  Giảm tốc tỷ lệ (dv/dt): {value}",
        "avg_decel": "  Giảm tốc trung bình (V²/2S): {value}",
        "infinite_dist": "Vô cùng (khoảng cách zero)",
        "infinite_time": "Vô cùng (thời gian zero)",
        "done": "\nXử lý hoàn tất. Nhấn Enter để thoát...",
        "press_continue": "\nNhấn Enter để tiếp tục...",
        "gui_title": "Kết quả kiểm tra phanh",
        "gui_panel_title": "Tóm tắt kết quả kiểm tra",
        "gui_btn_screenshot": "LƯU HÌNH ẢNH",
        "gui_saved": "Ảnh chụp màn hình đã lưu vào:\n{path}",
        "gui_save_fail": "Ảnh chụp màn hình thất bại: {err}",
        "gui_no_pillow": "Pillow chưa được cài đặt, không thể chụp màn hình.\nVui lòng chạy:  pip install pillow",
        "plot_title": "Đường cong Tốc độ - Thời gian",
        "axis_x": "Thời gian (HH:MM:SS.mmm)",
        "axis_y": "Tốc độ (km/h)",
        "legend_speed": "Đường cong tốc độ",
        "legend_eb": "Tín hiệu EB",
        "legend_start": "Bắt đầu phanh",
        "legend_end": "Kết thúc phanh",
        "legend_area": "Quãng đường phanh",
        "lbl_v0": "Tốc độ ban đầu v0",
        "lbl_vend": "Tốc độ cuối cùng v_end",
        "lbl_dt": "Khoảng Δt",
        "lbl_dist": "Khoảng cách S",
        "gui_file": "Tệp dữ liệu",
        "gui_label_points": "Điểm dữ liệu",
        "gui_label_interval": "Khoảng thời gian",
        "gui_label_v0": "Tốc độ ban đầu",
        "gui_label_vend": "Tốc độ cuối cùng",
        "gui_label_time": "Thời gian phanh",
        "gui_label_dist": "Quãng đường phanh",
        "gui_label_rate": "Giảm tốc tỷ lệ (dv/dt)",
        "gui_label_avg": "Giảm tốc trung bình (V²/2S)",
        "gui_pass": "ĐẠT",
        "gui_fail": "KHÔNG ĐẠT",
        "gui_req": "Yêu cầu: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "(không giới hạn)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "Thiết lập cấu hình",
        "config_prompt": "Vui lòng chọn một tùy chọn:",
        "config_saved": "Cấu hình đã được lưu thành công.",
        "config_cancelled": "Cấu hình đã bị hủy.",
        "config_overlimit": "Cấu hình vượt quá giới hạn",
        "config_lbl_language": "Ngôn ngữ:",
        "config_lbl_speed": "Tín hiệu tốc độ:",
        "config_lbl_brake": "Tín hiệu phanh:",
        "config_lbl_min": "Giảm tốc tối thiểu (m/s²):",
        "config_lbl_max": "Giảm tốc tối đa (m/s²):",
        "config_lbl_enable_min": "Bật giới hạn tối thiểu:",
        "config_lbl_enable_max": "Bật giới hạn tối đa:",
        "config_lbl_metric": "Chỉ số đánh giá:",
        "config_btn_save": "Lưu",
        "config_btn_cancel": "Hủy",
        "config_opt_yes": "Có",
        "config_opt_no": "Không",
        "config_overlimit_msg": "Cấu hình vượt quá giới hạn: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "Vui lòng chọn một tùy chọn:",
        "menu_opt1": "Mở tệp dữ liệu",
        "menu_opt2": "Cấu hình cài đặt",
        "menu_opt3": "Giới thiệu",
        "menu_prompt": "Nhập lựa chọn của bạn (1-3): ",
        "menu_invalid": "Lựa chọn không hợp lệ, vui lòng thử lại.",
        "file_dialog_title": "Chọn tệp dữ liệu",
        "file_filter": "Tệp văn bản (*.txt)|*.txt|Tất cả tệp (*.*)|*.*",
        "menu_about": "Thông tin phiên bản: v1.0 Đa ngôn ngữ",
        "no_file_selected": "Nessun file selezionato.",    },
    "id": {
        "title": "     K A L K U L A T O R  R E M  D A R U R A T  ",
        "version": "Versi Perangkat Lunak : 1.0 2026.08 ",
        "lang_name": "Bahasa Indonesia",
        "lang_warn": "         × Bahasa tidak dikenal '{value}', menggunakan bahasa Inggris (en).",
        "step1": "\n[Langkah 1] Direktori program: {path}",
        "step2": "\n[Langkah 2] Mencari file konfigurasi: {path}",
        "cfg_not_found": "         × Kesalahan: config.json tidak ditemukan",
        "press_exit": "\nTekan Enter untuk keluar...",
        "cfg_lang": "         ✓ Bahasa: {name}",
        "cfg_ok_speed": "         ✓ Nama sinyal kecepatan: {name}",
        "cfg_ok_brake": "         ✓ Nama sinyal rem: {name}",
        "cfg_parse_fail": "         × Gagal mengurai file konfigurasi: {err}",
        "no_file_arg": "         × Tidak ada file data yang diterima. Silakan seret file .txt ke ikon program ini.",
        "step3": "\n[Langkah 3] File data yang akan diproses: {path}",
        "file_not_exist": "         × File tidak ada!",
        "read_fail": "         × Tidak dapat membaca file: {err}",
        "read_fail_text": "Tidak dapat membaca file dengan encoding apa pun: {path}",
        "need_two_rows": "         × File data harus berisi setidaknya satu baris header dan satu baris data.",
        "step4": "\n[Langkah 4] Header file (total {count} kolom)",
        "time_col": "         Indeks kolom waktu: {idx} (kolom pertama)",
        "speed_col": "         Indeks kolom kecepatan: {idx} (sesuai dengan '{name}')",
        "brake_col": "         Indeks kolom rem: {idx} (sesuai dengan '{name}')",
        "col_not_found": "         × Kolom sinyal yang diperlukan tidak ditemukan di header: {err}",
        "valid_rows": "         Baris data valid yang dibaca: {count} baris, dilewati tidak valid: {skipped}",
        "time_range": "         Rentang waktu: {start} ~ {end}",
        "speed_range": "         Rentang kecepatan: {lo:.2f} ~ {hi:.2f} km/jam",
        "no_valid_data": "         × Tidak ada data yang valid!",
        "eb_found": "[Langkah 5] Titik EB valid ditemukan -> indeks:{idx}, waktu:{time}, kecepatan:{speed:.2f} km/jam ",
        "eb_skipped": "\n         Titik EB indeks:{idx} kecepatan {speed:.2f} km/jam <=5, dilewati, lanjutkan pencarian...\n",
        "eb_fallback": "\n         Tidak ada titik EB yang ditemukan, tetapi data dimulai dalam keadaan pengereman (0) dengan kecepatan>5, menggunakan awal sebagai awal pengereman.\n",
        "eb_none": "\n         × Tidak ada awal EB yang valid ditemukan (titik EB dengan kecepatan awal > 5 km/jam).\n",
        "step6_start": "\n[Langkah 6] Titik awal pengereman -> indeks:{idx}, waktu:{time}, kecepatan:{speed:.2f} km/jam",
        "end_fallback": "         Kecepatan tidak pernah turun di bawah 0,2 km/jam, menggunakan titik data terakhir sebagai akhir pengereman.",
        "step6_end": "         Titik akhir pengereman -> indeks:{idx}, waktu:{time}, kecepatan:{speed:.2f} km/jam",
        "press_calc": "         Tekan Enter untuk memulai perhitungan...",
        "result_title": "          H A S I L  P E R H I T U N G A N        ",
        "data_points": "  Titik data: {count}",
        "time_interval": "  Interval waktu: {start} ~ {end}",
        "v0": "  Kecepatan awal: {value:.2f} km/jam",
        "v_end": "  Kecepatan akhir: {value:.2f} km/jam",
        "brake_time": "  Waktu pengereman: {value:.4f} detik",
        "distance": "  Jarak pengereman: {value:.3f} m",
        "rate_decel": "  Perlambatan laju (dv/dt): {value}",
        "avg_decel": "  Perlambatan rata-rata (V²/2S): {value}",
        "infinite_dist": "Tak terhingga (jarak nol)",
        "infinite_time": "Tak terhingga (waktu nol)",
        "done": "\nPemrosesan selesai. Tekan Enter untuk keluar...",
        "press_continue": "\nTekan Enter untuk melanjutkan...",
        "gui_title": "Hasil Tes Rem",
        "gui_panel_title": "Ringkasan Hasil Tes",
        "gui_btn_screenshot": "SIMPAN GAMBAR",
        "gui_saved": "Screenshot disimpan ke:\n{path}",
        "gui_save_fail": "Screenshot gagal: {err}",
        "gui_no_pillow": "Pillow tidak terinstal, tidak dapat mengambil screenshot.\nSilakan jalankan:  pip install pillow",
        "plot_title": "Kurva Kecepatan - Waktu",
        "axis_x": "Waktu (HH:MM:SS.mmm)",
        "axis_y": "Kecepatan (km/jam)",
        "legend_speed": "Kurva kecepatan",
        "legend_eb": "Sinyal EB",
        "legend_start": "Awal pengereman",
        "legend_end": "Akhir pengereman",
        "legend_area": "Jarak pengereman",
        "lbl_v0": "Kecepatan awal v0",
        "lbl_vend": "Kecepatan akhir v_end",
        "lbl_dt": "Interval Δt",
        "lbl_dist": "Jarak S",
        "gui_file": "File data",
        "gui_label_points": "Titik data",
        "gui_label_interval": "Interval waktu",
        "gui_label_v0": "Kecepatan awal",
        "gui_label_vend": "Kecepatan akhir",
        "gui_label_time": "Waktu pengereman",
        "gui_label_dist": "Jarak pengereman",
        "gui_label_rate": "Perlambatan laju (dv/dt)",
        "gui_label_avg": "Perlambatan rata-rata (V²/2S)",
        "gui_pass": "LULUS",
        "gui_fail": "GAGAL",
        "gui_req": "Persyaratan: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "(tanpa batas)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "Pengaturan Konfigurasi",
        "config_prompt": "Silakan pilih opsi:",
        "config_saved": "Konfigurasi berhasil disimpan.",
        "config_cancelled": "Konfigurasi dibatalkan.",
        "config_overlimit": "Konfigurasi di luar jangkauan",
        "config_lbl_language": "Bahasa:",
        "config_lbl_speed": "Sinyal Kecepatan:",
        "config_lbl_brake": "Sinyal Rem:",
        "config_lbl_min": "Perlambatan Min (m/s²):",
        "config_lbl_max": "Perlambatan Maks (m/s²):",
        "config_lbl_enable_min": "Aktifkan Batas Min:",
        "config_lbl_enable_max": "Aktifkan Batas Maks:",
        "config_lbl_metric": "Metrik Evaluasi:",
        "config_btn_save": "Simpan",
        "config_btn_cancel": "Batal",
        "config_opt_yes": "Ya",
        "config_opt_no": "Tidak",
        "config_overlimit_msg": "Konfigurasi di luar jangkauan: min_decel >= 0, max_decel > 0, min_decel <= max_decel.",
        "menu_title": "Silakan pilih opsi:",
        "menu_opt1": "Buka file data",
        "menu_opt2": "Konfigurasi pengaturan",
        "menu_opt3": "Tentang",
        "menu_prompt": "Masukkan pilihan Anda (1-3): ",
        "menu_invalid": "Pilihan tidak valid, silakan coba lagi.",
        "file_dialog_title": "Pilih file data",
        "file_filter": "File teks (*.txt)|*.txt|Semua file (*.*)|*.*",
        "menu_about": "Info Versi: v1.0 Multi Bahasa",
        "no_file_selected": "Không có tệp nào được chọn.",    },
    "hi": {
        "title": "     आ प ा त क ा ल ी न  ब्रे क  क ै ल कु ले ट र  ",
        "version": "सॉफ़्टवेयर संस्करण : 1.0 2026.08 ",
        "lang_name": "हिन्दी",
        "lang_warn": "         × अज्ञात भाषा '{value}', अंग्रेज़ी (en) का उपयोग कर रहे हैं।",
        "step1": "\n[चरण 1] प्रोग्राम निर्देशिका: {path}",
        "step2": "\n[चरण 2] कॉन्फ़िगरेशन फ़ाइल खोज रहे हैं: {path}",
        "cfg_not_found": "         × त्रुटि: config.json नहीं मिला",
        "press_exit": "\nबाहर निकलने के लिए Enter दबाएं...",
        "cfg_lang": "         ✓ भाषा: {name}",
        "cfg_ok_speed": "         ✓ गति सिग्नल का नाम: {name}",
        "cfg_ok_brake": "         ✓ ब्रेक सिग्नल का नाम: {name}",
        "cfg_parse_fail": "         × कॉन्फ़िगरेशन फ़ाइल पार्सिंग विफल: {err}",
        "no_file_arg": "         × कोई डेटा फ़ाइल प्राप्त नहीं हुई। कृपया .txt फ़ाइल को इस प्रोग्राम आइकन पर खींचें।",
        "step3": "\n[चरण 3] प्रोसेस करने के लिए डेटा फ़ाइल: {path}",
        "file_not_exist": "         × फ़ाइल मौजूद नहीं है!",
        "read_fail": "         × फ़ाइल पढ़ने में असमर्थ: {err}",
        "read_fail_text": "किसी भी एन्कोडिंग के साथ फ़ाइल पढ़ने में असमर्थ: {path}",
        "need_two_rows": "         × डेटा फ़ाइल में कम से कम एक हेडर पंक्ति और एक डेटा पंक्ति होनी चाहिए।",
        "step4": "\n[चरण 4] फ़ाइल हेडर (कुल {count} कॉलम)",
        "time_col": "         समय कॉलम सूचकांक: {idx} (पहला कॉलम)",
        "speed_col": "         गति कॉलम सूचकांक: {idx} ('{name}' से संबंधित)",
        "brake_col": "         ब्रेक कॉलम सूचकांक: {idx} ('{name}' से संबंधित)",
        "col_not_found": "         × आवश्यक सिग्नल कॉलम हेडर में नहीं मिला: {err}",
        "valid_rows": "         वैध डेटा पंक्तियाँ पढ़ीं: {count} पंक्तियाँ, अमान्य छोड़ी गईं: {skipped}",
        "time_range": "         समय सीमा: {start} ~ {end}",
        "speed_range": "         गति सीमा: {lo:.2f} ~ {hi:.2f} किमी/घंटा",
        "no_valid_data": "         × कोई वैध डेटा नहीं!",
        "eb_found": "[चरण 5] वैध EB बिंदु मिला -> सूचकांक:{idx}, समय:{time}, गति:{speed:.2f} किमी/घंटा ",
        "eb_skipped": "\n         EB बिंदु सूचकांक:{idx} गति {speed:.2f} किमी/घंटा <=5, छोड़ा गया, खोज जारी...\n",
        "eb_fallback": "\n         कोई EB बिंदु नहीं मिला, लेकिन डेटा ब्रेकिंग स्थिति (0) में गति>5 के साथ शुरू होता है, आरंभ को ब्रेक आरंभ के रूप में उपयोग कर रहे हैं।\n",
        "eb_none": "\n         × कोई वैध EB आरंभ नहीं मिला (प्रारंभिक गति > 5 किमी/घंटा वाला EB बिंदु)।\n",
        "step6_start": "\n[चरण 6] ब्रेकिंग आरंभ बिंदु -> सूचकांक:{idx}, समय:{time}, गति:{speed:.2f} किमी/घंटा",
        "end_fallback": "         गति कभी 0.2 किमी/घंटा से नीचे नहीं गिरी, अंतिम डेटा बिंदु को ब्रेक अंत के रूप में उपयोग कर रहे हैं।",
        "step6_end": "         ब्रेकिंग अंत बिंदु -> सूचकांक:{idx}, समय:{time}, गति:{speed:.2f} किमी/घंटा",
        "press_calc": "         गणना शुरू करने के लिए Enter दबाएं...",
        "result_title": "          ग ण न ा  प रि णा म        ",
        "data_points": "  डेटा बिंदु: {count}",
        "time_interval": "  समय अंतराल: {start} ~ {end}",
        "v0": "  प्रारंभिक गति: {value:.2f} किमी/घंटा",
        "v_end": "  अंतिम गति: {value:.2f} किमी/घंटा",
        "brake_time": "  ब्रेकिंग समय: {value:.4f} सेकंड",
        "distance": "  ब्रेकिंग दूरी: {value:.3f} मी",
        "rate_decel": "  दर मंदी (dv/dt): {value}",
        "avg_decel": "  औसत मंदी (V²/2S): {value}",
        "infinite_dist": "अनंत (दूरी शून्य)",
        "infinite_time": "अनंत (समय शून्य)",
        "done": "\nप्रसंस्करण पूर्ण। बाहर निकलने के लिए Enter दबाएं...",
        "press_continue": "\nजारी रखने के लिए Enter दबाएं...",
        "gui_title": "ब्रेक परीक्षण परिणाम",
        "gui_panel_title": "परीक्षण परिणाम सारांश",
        "gui_btn_screenshot": "चित्र सहेजें",
        "gui_saved": "स्क्रीनशॉट यहाँ सहेजा गया:\n{path}",
        "gui_save_fail": "स्क्रीनशॉट विफल: {err}",
        "gui_no_pillow": "Pillow स्थापित नहीं है, स्क्रीनशॉट नहीं ले सकते।\nकृपया चलाएं:  pip install pillow",
        "plot_title": "गति - समय वक्र",
        "axis_x": "समय (HH:MM:SS.mmm)",
        "axis_y": "गति (किमी/घंटा)",
        "legend_speed": "गति वक्र",
        "legend_eb": "EB सिग्नल",
        "legend_start": "ब्रेक आरंभ",
        "legend_end": "ब्रेक अंत",
        "legend_area": "ब्रेकिंग दूरी",
        "lbl_v0": "प्रारंभिक गति v0",
        "lbl_vend": "अंतिम गति v_end",
        "lbl_dt": "अंतराल Δt",
        "lbl_dist": "दूरी S",
        "gui_file": "डेटा फ़ाइल",
        "gui_label_points": "डेटा बिंदु",
        "gui_label_interval": "समय अंतराल",
        "gui_label_v0": "प्रारंभिक गति",
        "gui_label_vend": "अंतिम गति",
        "gui_label_time": "ब्रेकिंग समय",
        "gui_label_dist": "ब्रेकिंग दूरी",
        "gui_label_rate": "दर मंदी (dv/dt)",
        "gui_label_avg": "औसत मंदी (V²/2S)",
        "gui_pass": "उत्तीर्ण",
        "gui_fail": "अनुत्तीर्ण",
        "gui_req": "आवश्यकता: {cond}",
        "gui_req_min_only": "{metric} ≥ {minv} m/s²",
        "gui_req_max_only": "{metric} ≤ {maxv} m/s²",
        "gui_req_both": "{minv} ≤ {metric} ≤ {maxv} m/s²",
        "gui_req_none": "(कोई सीमा नहीं)",
        "metric_v2_2s": "V²/2S",
        "metric_dv_dt": "dv/dt",
        "config_title": "कॉन्फ़िगरेशन सेटअप",
        "config_prompt": "कृपया एक विकल्प चुनें:",
        "config_saved": "कॉन्फ़िगरेशन सफलतापूर्वक सहेजा गया।",
        "config_cancelled": "कॉन्फ़िगरेशन रद्द किया गया।",
        "config_overlimit": "कॉन्फ़िगरेशन सीमा से बाहर",
        "config_lbl_language": "भाषा:",
        "config_lbl_speed": "गति सिग्नल:",
        "config_lbl_brake": "ब्रेक सिग्नल:",
        "config_lbl_min": "न्यूनतम मंदी (m/s²):",
        "config_lbl_max": "अधिकतम मंदी (m/s²):",
        "config_lbl_enable_min": "न्यूनतम सीमा सक्षम करें:",
        "config_lbl_enable_max": "अधिकतम सीमा सक्षम करें:",
        "config_lbl_metric": "मूल्यांकन मीट्रिक:",
        "config_btn_save": "सहेजें",
        "config_btn_cancel": "रद्द करें",
        "config_opt_yes": "हाँ",
        "config_opt_no": "नहीं",
        "config_overlimit_msg": "कॉन्फ़िगरेशन सीमा से बाहर: min_decel >= 0, max_decel > 0, min_decel <= max_decel।",
        "menu_title": "कृपया एक विकल्प चुनें:",
        "menu_opt1": "डेटा फ़ाइल खोलें",
        "menu_opt2": "सेटिंग्स कॉन्फ़िगर करें",
        "menu_opt3": "परिचय",
        "menu_prompt": "अपनी पसंद दर्ज करें (1-3): ",
        "menu_invalid": "अमान्य पसंद, कृपया पुनः प्रयास करें।",
        "file_dialog_title": "डेटा फ़ाइल चुनें",
        "file_filter": "टेक्स्ट फ़ाइलें (*.txt)|*.txt|सभी फ़ाइलें (*.*)|*.*",
        "menu_about": "संस्करण जानकारी: v1.0 बहुभाषी",
        "no_file_selected": "Tidak ada file yang dipilih.",    },
}

# About dialog content is kept separate from the general message table so the
# release-page label can be rendered as a clickable link in every language.
ABOUT_TEXTS = {
    "en": ("Version: v1.0 Official Release", "Author: bohangyang", "Update:", "Software Release Page", "Please save the project configuration before updating the software to prevent data loss."),
    "zh": ("版本：v1.0 正式版", "作者：bohangyang", "更新：", "软件发布页", "更新软件前请留存项目配置信息以防丢失。"),
    "ms": ("Versi: v1.0 Edisi Rasmi", "Pengarang: bohangyang", "Kemas kini:", "Halaman Pelancaran Perisian", "Sila simpan konfigurasi projek sebelum mengemas kini perisian untuk mengelakkan kehilangan data."),
    "ja": ("バージョン：v1.0 正式版", "作者：bohangyang", "更新：", "ソフトウェア公開ページ", "ソフトウェアを更新する前に、紛失を防ぐためプロジェクト設定を保存してください。"),
    "fr": ("Version : v1.0 Edition officielle", "Auteur : bohangyang", "Mise à jour :", "Page de publication du logiciel", "Avant de mettre à jour le logiciel, sauvegardez la configuration du projet pour éviter toute perte."),
    "de": ("Version: v1.0 Offizielle Version", "Autor: bohangyang", "Update:", "Software-Veröffentlichungsseite", "Bitte sichern Sie vor dem Update die Projektkonfiguration, um Datenverlust zu vermeiden."),
    "es": ("Versión: v1.0 Edición oficial", "Autor: bohangyang", "Actualización:", "Página de publicación del software", "Guarde la configuración del proyecto antes de actualizar el software para evitar pérdidas."),
    "ru": ("Версия: v1.0 Официальный выпуск", "Автор: bohangyang", "Обновление:", "Страница публикации программы", "Перед обновлением сохраните конфигурацию проекта, чтобы избежать потери данных."),
    "pt": ("Versão: v1.0 Edição oficial", "Autor: bohangyang", "Atualização:", "Página de lançamento do software", "Antes de atualizar o software, guarde a configuração do projeto para evitar perdas."),
    "ar": ("الإصدار: v1.0 الإصدار الرسمي", "المؤلف: bohangyang", "التحديث:", "صفحة إصدار البرنامج", "يرجى حفظ إعدادات المشروع قبل تحديث البرنامج لتجنب فقدان البيانات."),
    "zh_tw": ("版本：v1.0 正式版", "作者：bohangyang", "更新：", "軟體發布頁", "更新軟體前請留存專案設定資訊以防遺失。"),
    "ko": ("버전: v1.0 정식 버전", "작성자: bohangyang", "업데이트:", "소프트웨어 배포 페이지", "소프트웨어를 업데이트하기 전에 손실을 방지하기 위해 프로젝트 설정을 저장하세요."),
    "th": ("เวอร์ชัน: v1.0 รุ่นอย่างเป็นทางการ", "ผู้เขียน: bohangyang", "อัปเดต:", "หน้าดาวน์โหลดซอฟต์แวร์", "โปรดบันทึกการกำหนดค่าโครงการก่อนอัปเดตซอฟต์แวร์เพื่อป้องกันข้อมูลสูญหาย"),
    "it": ("Versione: v1.0 Edizione ufficiale", "Autore: bohangyang", "Aggiornamento:", "Pagina di pubblicazione del software", "Salvare la configurazione del progetto prima di aggiornare il software per evitare perdite."),
    "vi": ("Phiên bản: v1.0 Bản chính thức", "Tác giả: bohangyang", "Cập nhật:", "Trang phát hành phần mềm", "Vui lòng lưu cấu hình dự án trước khi cập nhật phần mềm để tránh mất dữ liệu."),
    "id": ("Versi: v1.0 Edisi Resmi", "Penulis: bohangyang", "Pembaruan:", "Halaman Rilis Perangkat Lunak", "Simpan konfigurasi proyek sebelum memperbarui perangkat lunak untuk mencegah kehilangan data."),
    "hi": ("संस्करण: v1.0 आधिकारिक संस्करण", "लेखक: bohangyang", "अपडेट:", "सॉफ्टवेयर रिलीज़ पृष्ठ", "डेटा खोने से बचने के लिए सॉफ्टवेयर अपडेट करने से पहले प्रोजेक्ट कॉन्फ़िगरेशन सहेजें।"),
}

RELEASE_URL = "https://github.com/cnybh/brake_calc_tool"

START_TITLES = {
    "en": "Direct Start",
    "zh": "直接启动",
    "ms": "Mula Terus",
    "ja": "直接起動",
    "fr": "Démarrage direct",
    "de": "Direktstart",
    "es": "Inicio directo",
    "ru": "Прямой запуск",
    "pt": "Início direto",
    "ar": "بدء التشغيل المباشر",
    "zh_tw": "直接啟動",
    "ko": "바로 시작",
    "th": "เริ่มต้นโดยตรง",
    "it": "Avvio diretto",
    "vi": "Khởi động trực tiếp",
    "id": "Mulai Langsung",
    "hi": "सीधा प्रारंभ",
}

# ------------------ Language resolution ------------------
def resolve_language(cfg_lang):
    """Return language code from a config language value (case-insensitive)."""
    if not cfg_lang:
        return "en"
    lang = str(cfg_lang).strip().lower()
    if lang in ("zh", "cn", "chinese", "zh-cn", "中文", "简体中文"):
        return "zh"
    if lang in ("zh_tw", "zh-tw", "tw", "traditional chinese", "繁體中文", "繁体中文"):
        return "zh_tw"
    if lang in ("ms", "malay", "bahasa melayu", "马来语"):
        return "ms"
    if lang in ("ja", "japanese", "日本語", "日语"):
        return "ja"
    if lang in ("fr", "french", "français", "法语"):
        return "fr"
    if lang in ("de", "german", "deutsch", "德语"):
        return "de"
    if lang in ("es", "spanish", "español", "西班牙语"):
        return "es"
    if lang in ("ru", "russian", "русский", "俄语"):
        return "ru"
    if lang in ("pt", "portuguese", "português", "葡萄牙语"):
        return "pt"
    if lang in ("ar", "arabic", "العربية", "阿拉伯语"):
        return "ar"
    if lang in ("ko", "korean", "한국어", "韩语"):
        return "ko"
    if lang in ("th", "thai", "ไทย", "泰语"):
        return "th"
    if lang in ("it", "italian", "italiano", "意大利语"):
        return "it"
    if lang in ("vi", "vietnamese", "tiếng việt", "越南语"):
        return "vi"
    if lang in ("id", "indonesian", "bahasa indonesia", "印尼语"):
        return "id"
    if lang in ("hi", "hindi", "हिन्दी", "印地语"):
        return "hi"
    return "en"


def is_rtl(lang):
    """Return True for right-to-left languages (currently Arabic)."""
    return lang == "ar"

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
    # Use appropriate fonts for different language scripts
    if lang in ("zh", "zh_tw", "ja", "ko"):
        # CJK languages (Chinese, Japanese, Korean)
        family = "Microsoft YaHei UI"
    elif lang in ("ar"):
        # Arabic
        family = "Segoe UI"
    elif lang in ("hi"):
        # Hindi (Devanagari script)
        family = "Nirmala UI"
    elif lang in ("th"):
        # Thai
        family = "Leelawadee UI"
    else:
        # Latin scripts and others
        family = "Segoe UI"
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


def setup_console():
    """Configure the Windows console for UTF-8 and Unicode-capable fonts.

    On Windows the legacy console renders Thai/Arabic/CJK as empty boxes
    ("tofu") when the active code page is not UTF-8 or when the console
    font is a raster font without glyph fallback. Setting the code page to
    65001 and switching to a TrueType face lets the modern conhost fall
    back to system fonts for scripts such as Thai and Arabic.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        # UTF-8 input/output code page.
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)

        class CONSOLE_FONT_INFOEX(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.ULONG),
                ("nFont", wintypes.DWORD),
                ("dwFontSize", wintypes.COORD),
                ("FontFamily", wintypes.UINT),
                ("FontWeight", wintypes.UINT),
                ("FaceName", wintypes.WCHAR * 32),
            ]

        h_out = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        if not h_out or h_out == ctypes.c_void_p(-1).value:
            return
        info = CONSOLE_FONT_INFOEX()
        info.cbSize = ctypes.sizeof(CONSOLE_FONT_INFOEX)
        if not kernel32.GetCurrentConsoleFontEx(h_out, False, ctypes.byref(info)):
            return
        # TMPF_TRUETYPE = 4; raster fonts have no Unicode fallback.
        if info.FontFamily & 4:
            return
        for face in ("Cascadia Mono", "Cascadia Code", "Consolas", "Lucida Console"):
            trial = CONSOLE_FONT_INFOEX()
            trial.cbSize = ctypes.sizeof(CONSOLE_FONT_INFOEX)
            kernel32.GetCurrentConsoleFontEx(h_out, False, ctypes.byref(trial))
            trial.FaceName = face
            trial.FontFamily = (trial.FontFamily & 0xF0) | 4
            if kernel32.SetCurrentConsoleFontEx(h_out, False, ctypes.byref(trial)):
                break
    except Exception:
        pass


def _get_icon_path():
    """Return the absolute path to logo.ico (works in PyInstaller onefile too)."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "logo.ico")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")


def _set_app_icon(window):
    """Set the window icon to logo.ico; silently ignore on failure."""
    try:
        window.iconbitmap(_get_icon_path())
    except Exception:
        pass


# ---- single hidden root Tk so that multiple Toplevel windows never flash ----
_root_tk = None


def _get_root():
    """Return a hidden singleton Tk root; all visible windows are Toplevel children."""
    global _root_tk
    if _root_tk is None:
        _root_tk = tk.Tk()
        _root_tk.withdraw()
        _set_app_icon(_root_tk)
    return _root_tk


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




def _bring_to_front(window):
    """Force a tkinter window to the foreground and give it focus."""
    try:
        window.lift()
        window.attributes("-topmost", True)
        window.update_idletasks()
        window.attributes("-topmost", False)
        window.focus_force()
        if sys.platform == "win32":
            import ctypes
            hwnd = window.winfo_id()
            if hwnd:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
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

    def _tag_fit(self, x, y, text, color, font, prefer="nw", pad=5):
        """Annotation box that flips/clamps so it never leaves the plot area."""
        w = self._text_w(text, font) + pad * 2
        fh = 18
        lo = self.PAD_L
        hi = max(lo + w, self.winfo_width() - self.PAD_R)
        if prefer == "center":
            anchor = "center"
        elif prefer == "ne":
            anchor = "nw" if x - w < lo else "ne"
        else:  # nw
            anchor = "ne" if x + w > hi else "nw"
        if anchor == "center":
            x0 = max(lo, min(x - w / 2, hi - w))
            box = (x0, y - fh / 2, x0 + w, y + fh / 2)
            tx, ty, ta = x0 + w / 2, y, "center"
        elif anchor == "ne":
            x1 = min(hi, max(x, lo + w))
            box = (x1 - w, y, x1, y + fh)
            tx, ty, ta = x1 - pad, y + fh / 2, "e"
        else:
            x0 = max(lo, min(x, hi - w))
            box = (x0, y, x0 + w, y + fh)
            tx, ty, ta = x0 + pad, y + fh / 2, "w"
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
        rtl = is_rtl(lang)

        # bottom arrow Y position (used by final speed and interval labels)
        ay = ax_b - 22

        # initial speed (aligned with start line, above curve)
        txt = T["lbl_v0"] + " = " + f"{c['v0_kmh']:.2f} km/h"
        y0t = Y(c["speeds"][si]) - 38
        if y0t < ax_t + band_h + 4:
            y0t = ax_t + band_h + 4
        self._tag_fit(x_s, y0t, txt, col_s, bold, "ne" if rtl else "nw")

        # final speed (aligned with end line, below arrow)
        txt = T["lbl_vend"] + " = " + f"{c['v_end_kmh']:.2f} km/h"
        self._tag_fit(x_e, ay + 3, txt, col_e, bold, "nw" if rtl else "ne")

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

        # ---------- legend (top-right; top-left for RTL) ----------
        legend = [
            ("#1F77B4", "line", T["legend_speed"]),
            ("#D35400", "line", T["legend_eb"]),
            (col_s, "dash", T["legend_start"]),
            (col_e, "dash", T["legend_end"]),
            (yellow_color, "rect", T["legend_area"]),
        ]
        lf = ("Segoe UI", 9)
        maxw = max(24 + self._text_w(lbl, lf) for _, _, lbl in legend)
        if rtl:
            lx0 = ax_l + 10
        else:
            lx0 = ax_r - 10 - maxw
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
        self.create_text(13, (ax_t + ax_b) / 2, text=T["axis_y"], angle=-90 if rtl else 90,
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
    rtl = is_rtl(lang)

    # Window title: "Emergency Brake Test Result + filename" (no .txt)
    file_name = ctx.get("file_name") or ""
    if file_name.lower().endswith(".txt"):
        file_name = file_name[:-4]
    win_title = T["gui_title"] + ("  " + file_name if file_name else "")
    console_title = T["title"].strip() + ("  " + file_name if file_name else "")

    root = tk.Toplevel(_get_root())
    _set_app_icon(root)
    root.title(console_title)
    root.geometry("960x600")
    root.minsize(960, 600)
    root.configure(bg="#F0F2F5")

    # ----- header: title + save-picture button (top-right, default Windows style) -----
    header = tk.Frame(root, bg="#F0F2F5")
    header.pack(side="top", fill="x", padx=12, pady=(10, 6))
    tk.Label(header, text=win_title, font=_ui_font(lang, 14, True),
             bg="#F0F2F5", fg="#1F2937", anchor="e" if rtl else "w").pack(side="right" if rtl else "left")
    btn_screenshot = tk.Button(header, text=T["gui_btn_screenshot"], font=_ui_font(lang, 11),
                              width=14, height=1, command=lambda: take_screenshot(root, lang, btn_screenshot))
    btn_screenshot.pack(side="left" if rtl else "right")

    # ----- content: left summary, right plot -----
    content = tk.Frame(root, bg="#F0F2F5")
    content.pack(side="top", fill="both", expand=True, padx=12, pady=(0, 12))
    content.rowconfigure(0, weight=1)
    content.columnconfigure(0 if rtl else 1, weight=1)

    # summary panel (right side for RTL layouts)
    left = tk.Frame(content, bg="#FFFFFF", highlightbackground="#D8DCE2", highlightthickness=1)
    left_col = 1 if rtl else 0
    left.grid(row=0, column=left_col, sticky="ns", padx=((12, 0) if rtl else (0, 12)))
    left.configure(width=340)
    left.grid_propagate(False)
    tk.Label(left, text=T["gui_panel_title"], font=_ui_font(lang, 12, True),
             bg="#FFFFFF", fg="#1F2937", anchor="e" if rtl else "w").pack(fill="x", padx=16, pady=(14, 10))
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
                 anchor="e" if rtl else "w").grid(row=i, column=1 if rtl else 0, sticky="e" if rtl else "w",
                                                  pady=5, padx=(10, 0) if rtl else (0, 10))
        tk.Label(body, text=val, font=_ui_font(lang, 10, True), bg="#FFFFFF", fg="#111827",
                 anchor="e" if rtl else "w", justify="right" if rtl else "left",
                 wraplength=180).grid(row=i, column=0 if rtl else 1, sticky="ew", pady=5)
    body.columnconfigure(0 if rtl else 1, weight=1)

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
             bg="#FFFFFF", fg=result_color).pack(anchor="e" if rtl else "w")
    tk.Label(result_frame, text=req_text, font=_ui_font(lang, 9),
             bg="#FFFFFF", fg="#6B7280").pack(anchor="e" if rtl else "w", pady=(2, 0))

    # plot panel (left side for RTL layouts)
    plot_frame = tk.Frame(content, bg="#FFFFFF", highlightbackground="#D8DCE2", highlightthickness=1)
    plot_frame.grid(row=0, column=0 if rtl else 1, sticky="nsew")
    plot_frame.rowconfigure(0, weight=1)
    plot_frame.columnconfigure(0, weight=1)
    plot = PlotWidget(plot_frame, lang, ctx)
    plot.grid(row=0, column=0, sticky="nsew")

    root.bind("<Control-s>", lambda e: take_screenshot(root, lang, btn_screenshot))
    root.bind("<F12>", lambda e: take_screenshot(root, lang, btn_screenshot))
    # Console auto-closes as soon as the GUI appears; only the GUI stays visible.
    hide_console()
    _bring_to_front(root)
    root.wait_window()
    return True



def show_config_gui(lang, current_config):
    """Open a configuration GUI window.
    Returns the new config dict if saved, None if cancelled.
    """
    if not _TK_AVAILABLE:
        print("         [GUI] tkinter not available, cannot open config window.")
        return None
    T = MSGS.get(lang, MSGS["en"])
    rtl = is_rtl(lang)

    result = {"config": None}

    # Create a mapping of language codes to display names
    lang_display_map = {
        "en": MSGS["en"]["lang_name"],
        "zh": MSGS["zh"]["lang_name"],
        "ms": MSGS["ms"]["lang_name"],
        "ja": MSGS["ja"]["lang_name"],
        "fr": MSGS["fr"]["lang_name"],
        "de": MSGS["de"]["lang_name"],
        "es": MSGS["es"]["lang_name"],
        "ru": MSGS["ru"]["lang_name"],
        "pt": MSGS["pt"]["lang_name"],
        "ar": MSGS["ar"]["lang_name"],
        "zh_tw": MSGS["zh_tw"]["lang_name"],
        "ko": MSGS["ko"]["lang_name"],
        "th": MSGS["th"]["lang_name"],
        "it": MSGS["it"]["lang_name"],
        "vi": MSGS["vi"]["lang_name"],
        "id": MSGS["id"]["lang_name"],
        "hi": MSGS["hi"]["lang_name"],
    }
    
    # Create reverse mapping for saving
    lang_code_map = {v: k for k, v in lang_display_map.items()}

    def on_save():
        new_lang_display = lang_display_var.get()
        # Convert display name back to language code
        new_lang = lang_code_map.get(new_lang_display, "en")
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

    root = tk.Toplevel(_get_root())
    _set_app_icon(root)
    root.title(T["config_title"])
    # The form has eight rows; leave a dedicated area for the buttons.
    root.geometry("560x620")
    root.resizable(False, False)
    root.configure(bg="#F0F2F5")

    header = tk.Frame(root, bg="#F0F2F5")
    header.pack(side="top", fill="x", padx=12, pady=(10, 6))
    tk.Label(header, text=T["config_title"], font=_ui_font(lang, 14, True),
             bg="#F0F2F5", fg="#1F2937", anchor="e" if rtl else "w").pack(side="right" if rtl else "left")

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
             bg="#FFFFFF", fg="#374151", anchor="e" if rtl else "w").grid(row=row, column=1 if rtl else 0, sticky="e" if rtl else "w", padx=(10, 20) if rtl else (20, 10), pady=pad_y)
    
    # Get current language display name
    current_lang_code = lang_var.get()
    current_lang_display = lang_display_map.get(current_lang_code, lang_display_map["en"])
    
    # Create StringVar for display name
    lang_display_var = tk.StringVar(value=current_lang_display)
    
    # Create dropdown with display names
    lang_combo = tk.OptionMenu(content, lang_display_var, 
                                *[lang_display_map[code] for code in [
                                    "en", "zh", "zh_tw", "ja", "ko",
                                    "ms", "th", "vi", "id", "hi",
                                    "fr", "de", "es", "it", "pt", "ru", "ar"
                                ]])
    lang_combo.config(font=font_input, width=18)
    lang_combo.grid(row=row, column=0 if rtl else 1, sticky="e" if rtl else "w", padx=(20, 0) if rtl else (0, 20), pady=pad_y)
    row += 1

    # Speed signal - input
    tk.Label(content, text=T["config_lbl_speed"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="e" if rtl else "w").grid(row=row, column=1 if rtl else 0, sticky="e" if rtl else "w", padx=(10, 20) if rtl else (20, 10), pady=pad_y)
    tk.Entry(content, textvariable=speed_var, font=font_input, width=30, justify="right" if rtl else "left").grid(row=row, column=0 if rtl else 1, sticky="ew", padx=(20, 0) if rtl else (0, 20), pady=pad_y)
    row += 1

    # Brake signal - input
    tk.Label(content, text=T["config_lbl_brake"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="e" if rtl else "w").grid(row=row, column=1 if rtl else 0, sticky="e" if rtl else "w", padx=(10, 20) if rtl else (20, 10), pady=pad_y)
    tk.Entry(content, textvariable=brake_var, font=font_input, width=30, justify="right" if rtl else "left").grid(row=row, column=0 if rtl else 1, sticky="ew", padx=(20, 0) if rtl else (0, 20), pady=pad_y)
    row += 1

    # Min decel - input
    tk.Label(content, text=T["config_lbl_min"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="e" if rtl else "w").grid(row=row, column=1 if rtl else 0, sticky="e" if rtl else "w", padx=(10, 20) if rtl else (20, 10), pady=pad_y)
    tk.Entry(content, textvariable=min_var, font=font_input, width=20, justify="right" if rtl else "left").grid(row=row, column=0 if rtl else 1, sticky="e" if rtl else "w", padx=(20, 0) if rtl else (0, 20), pady=pad_y)
    row += 1

    # Max decel - input
    tk.Label(content, text=T["config_lbl_max"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="e" if rtl else "w").grid(row=row, column=1 if rtl else 0, sticky="e" if rtl else "w", padx=(10, 20) if rtl else (20, 10), pady=pad_y)
    tk.Entry(content, textvariable=max_var, font=font_input, width=20, justify="right" if rtl else "left").grid(row=row, column=0 if rtl else 1, sticky="e" if rtl else "w", padx=(20, 0) if rtl else (0, 20), pady=pad_y)
    row += 1

    # Enable min limit - option (radio)
    tk.Label(content, text=T["config_lbl_enable_min"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="e" if rtl else "w").grid(row=row, column=1 if rtl else 0, sticky="e" if rtl else "w", padx=(10, 20) if rtl else (20, 10), pady=pad_y)
    min_frame = tk.Frame(content, bg="#FFFFFF")
    min_frame.grid(row=row, column=0 if rtl else 1, sticky="e" if rtl else "w", padx=(20, 0) if rtl else (0, 20), pady=pad_y)
    tk.Radiobutton(min_frame, text=T["config_opt_yes"], variable=enable_min_var, value=True,
                   font=font_input, bg="#FFFFFF").pack(side="right" if rtl else "left", padx=(15, 0) if rtl else (0, 15))
    tk.Radiobutton(min_frame, text=T["config_opt_no"], variable=enable_min_var, value=False,
                   font=font_input, bg="#FFFFFF").pack(side="right" if rtl else "left")
    row += 1

    # Enable max limit - option (radio)
    tk.Label(content, text=T["config_lbl_enable_max"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="e" if rtl else "w").grid(row=row, column=1 if rtl else 0, sticky="e" if rtl else "w", padx=(10, 20) if rtl else (20, 10), pady=pad_y)
    max_frame = tk.Frame(content, bg="#FFFFFF")
    max_frame.grid(row=row, column=0 if rtl else 1, sticky="e" if rtl else "w", padx=(20, 0) if rtl else (0, 20), pady=pad_y)
    tk.Radiobutton(max_frame, text=T["config_opt_yes"], variable=enable_max_var, value=True,
                   font=font_input, bg="#FFFFFF").pack(side="right" if rtl else "left", padx=(15, 0) if rtl else (0, 15))
    tk.Radiobutton(max_frame, text=T["config_opt_no"], variable=enable_max_var, value=False,
                   font=font_input, bg="#FFFFFF").pack(side="right" if rtl else "left")
    row += 1

    # Evaluation metric - option (dropdown)
    tk.Label(content, text=T["config_lbl_metric"], font=font_label,
             bg="#FFFFFF", fg="#374151", anchor="e" if rtl else "w").grid(row=row, column=1 if rtl else 0, sticky="e" if rtl else "w", padx=(10, 20) if rtl else (20, 10), pady=pad_y)
    metric_combo = tk.OptionMenu(content, metric_var, "v2_2s", "dv_dt")
    metric_combo.config(font=font_input, width=18)
    metric_combo.grid(row=row, column=0 if rtl else 1, sticky="e" if rtl else "w", padx=(20, 0) if rtl else (0, 20), pady=pad_y)
    row += 1

    content.columnconfigure(0 if rtl else 1, weight=1)

    # Button bar: pack it explicitly at the bottom so it cannot be pushed
    # outside the window by the expanding form above.
    btn_frame = tk.Frame(root, bg="#F0F2F5", height=58)
    btn_frame.pack(side="bottom", fill="x", padx=12, pady=(0, 12))
    btn_frame.pack_propagate(False)

    btn_save = tk.Button(btn_frame, text=T["config_btn_save"], font=_ui_font(lang, 11),
                         width=12, height=1, command=on_save)
    btn_save.pack(side="left" if rtl else "right", padx=(0, 6) if rtl else (6, 0))

    btn_cancel = tk.Button(btn_frame, text=T["config_btn_cancel"], font=_ui_font(lang, 11),
                           width=12, height=1, command=on_cancel)
    btn_cancel.pack(side="left" if rtl else "right", padx=(6, 0) if rtl else (0, 6))

    root.protocol("WM_DELETE_WINDOW", on_cancel)

    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    root.geometry(f"+{x}+{y}")

    _bring_to_front(root)
    root.wait_window()
    return result["config"]

def _pause_exit(lang, title=None, message=None):
    """Wait for the user to acknowledge before the program exits.

    In windowed (no-console) builds there is no stdin/stdout, so errors and
    "press Enter to exit" prompts are shown as a GUI message box instead.
    """
    if _TK_AVAILABLE:
        try:
            if title is None:
                title = MSGS.get(lang, MSGS["en"]).get("title", "Brake Calculator").strip()
            if message is None:
                message = MSGS.get(lang, MSGS["en"]).get("press_exit", "").strip()
            messagebox.showinfo(title, message, parent=_get_root())
            return
        except Exception:
            pass
    try:
        input(msg(lang, "press_exit"))
    except Exception:
        pass


def show_about(lang):
    """Show localized release information with a clickable release-page link."""
    if not _TK_AVAILABLE:
        return

    T = MSGS.get(lang, MSGS["en"])
    version_text, author_text, update_text, release_text, update_note = ABOUT_TEXTS.get(
        lang, ABOUT_TEXTS["en"]
    )
    rtl = is_rtl(lang)
    dialog = tk.Toplevel(_get_root())
    _set_app_icon(dialog)
    dialog.title(T["menu_opt3"])
    dialog.resizable(False, False)
    if sys.platform == "win32":
        try:
            dialog.attributes("-toolwindow", True)
        except tk.TclError:
            # Some bundled Tk builds do not expose the Windows toolwindow flag.
            pass
    dialog.configure(bg="#FFFFFF")

    content = tk.Frame(dialog, bg="#FFFFFF", padx=24, pady=18)
    content.pack(fill="both", expand=True)
    anchor = "e" if rtl else "w"
    label_style = {
        "font": _ui_font(lang, 11),
        "bg": "#FFFFFF",
        "fg": "#1F2937",
        "anchor": anchor,
    }
    tk.Label(content, text=version_text, **label_style).pack(fill="x", pady=2)
    tk.Label(content, text=author_text, **label_style).pack(fill="x", pady=2)

    update_row = tk.Frame(content, bg="#FFFFFF")
    update_row.pack(fill="x", pady=2)
    tk.Label(update_row, text=update_text, **label_style).pack(side="right" if rtl else "left")
    try:
        link_font = tkfont.Font(root=dialog, font=_ui_font(lang, 11, True))
        link_font.configure(underline=True)
    except tk.TclError:
        # Keep the link usable if the bundled Tk font implementation differs.
        link_font = _ui_font(lang, 11, True)
    link = tk.Label(
        update_row,
        text=release_text,
        font=link_font,
        bg="#FFFFFF",
        fg="#1565C0",
        cursor="hand2",
        underline=True,
    )
    link.pack(side="right" if rtl else "left", padx=(6, 0) if not rtl else (0, 6))
    link.bind("<Button-1>", lambda _event: webbrowser.open(RELEASE_URL))

    tk.Label(content, text=update_note, font=_ui_font(lang, 9),
             bg="#FFFFFF", fg="#6B7280", anchor=anchor,
             justify="left" if not rtl else "right", wraplength=560).pack(
                 fill="x", pady=(8, 0))

    tk.Button(content, text=T.get("config_btn_cancel", "Close"),
              command=dialog.destroy, cursor="hand2",
              font=_ui_font(lang, 10)).pack(pady=(14, 0))
    dialog.transient(_get_root())
    # Explicit geometry and deferred focus avoid a Windows Tk focus deadlock
    # when this dialog is opened from the menu's wait_window loop.
    dialog.update_idletasks()
    width = dialog.winfo_reqwidth()
    height = dialog.winfo_reqheight()
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    width = max(width, 560)
    dialog.geometry(
        f"{width}x{height}+{max(0, (screen_width - width) // 2)}+"
        f"{max(0, (screen_height - height) // 2)}"
    )
    dialog.deiconify()
    dialog.after(50, lambda: _bring_to_front(dialog))


def show_start_menu(lang):
    """Show the main menu as a GUI window with three buttons.

    Returns one of:
      "open"   - user wants to pick a data file
      "config" - user wants to configure settings
      "exit"   - user wants to quit
    """
    if not _TK_AVAILABLE:
        return None
    T = MSGS.get(lang, MSGS["en"])
    rtl = is_rtl(lang)

    result = {"action": "exit"}

    root = tk.Toplevel(_get_root())
    _set_app_icon(root)
    root.title(START_TITLES.get(lang, START_TITLES["en"]))
    root.resizable(False, False)
    if sys.platform == "win32":
        try:
            root.attributes("-toolwindow", True)
        except tk.TclError:
            pass
    root.configure(bg="#F0F2F5")

    header = tk.Frame(root, bg="#F0F2F5")
    header.pack(side="top", fill="x", padx=16, pady=(14, 6))
    tk.Label(header, text=T["title"].strip() or T["menu_title"],
             font=_ui_font(lang, 14, True),
             bg="#F0F2F5", fg="#1F2937", anchor="e" if rtl else "w").pack(fill="x")

    content = tk.Frame(root, bg="#FFFFFF", highlightbackground="#D8DCE2", highlightthickness=1)
    content.pack(side="top", fill="both", expand=True, padx=16, pady=(0, 12))

    btn_style = {"font": _ui_font(lang, 12), "width": 30, "height": 2, "cursor": "hand2"}

    btn_open = tk.Button(content, text=T["menu_opt1"], **btn_style,
                         command=lambda: set_action("open"))
    btn_open.pack(pady=(22, 10), padx=20)

    btn_config = tk.Button(content, text=T["menu_opt2"], **btn_style,
                           command=lambda: set_action("config"))
    btn_config.pack(pady=10, padx=20)

    btn_about = tk.Button(content, text=T["menu_opt3"], **btn_style,
                          command=lambda: show_about(lang))
    btn_about.pack(pady=(10, 22), padx=20)

    def set_action(action):
        result["action"] = action
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", lambda: set_action("exit"))

    root.update_idletasks()
    w = root.winfo_reqwidth()
    h = root.winfo_reqheight()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    _bring_to_front(root)
    root.wait_window()
    return result["action"]


def main():
    # ---------- 0. Prepare console for Unicode (UTF-8 code page + TrueType font) ----------
    setup_console()

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
        _pause_exit(lang, message=msg(lang, "cfg_parse_fail", err=e))
        return
    print(msg(lang, "cfg_lang", name=T["lang_name"]))
    print(msg(lang, "cfg_ok_speed", name=speed_signal))
    print(msg(lang, "cfg_ok_brake", name=brake_signal))
    time.sleep(0.5)  # pause 0.5 seconds

    # ---------- 4. Get the data file ----------
    if len(sys.argv) < 2:
        if _TK_AVAILABLE:
            # GUI main menu: three buttons drive the next step.
            while True:
                action = show_start_menu(lang)
                if action == "exit":
                    return
                if action == "config":
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
                    continue
                # action == "open": pick a data file
                file_path = filedialog.askopenfilename(
                    parent=_get_root(),
                    title=msg(lang, "file_dialog_title"),
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
                )
                if file_path:
                    sys.argv.append(file_path)
                    break  # exit while loop, continue to process file
                else:
                    print(msg(lang, "no_file_selected"))
                    continue
        else:
            # tkinter unavailable: fall back to the console menu.
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
                    print("         [GUI] tkinter not available, cannot open file dialog.")
                    input(msg(lang, "press_exit"))
                    return
                elif choice == "2":
                    new_cfg = show_config_gui(lang, config)
                    if new_cfg is not None:
                        cfg_path = get_config_path()
                        config_text = json.dumps(new_cfg, indent=4, ensure_ascii=False)
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
        # If we break out of while loop with a selected file, it is in sys.argv
        file_path = sys.argv[-1]



    file_path = sys.argv[1]
    print(msg(lang, "step3", path=file_path))
    if not os.path.exists(file_path):
        print(msg(lang, "file_not_exist"))
        _pause_exit(lang, message=msg(lang, "file_not_exist"))
        return

    # ---------- 5. Read and parse data file (split by whitespace) ----------
    try:
        file_text = safe_read_file(file_path, msg(lang, "read_fail_text", path=file_path))
        lines = file_text.splitlines(keepends=True)
    except Exception as e:
        print(msg(lang, "read_fail", err=e))
        _pause_exit(lang, message=msg(lang, "read_fail", err=e))
        return

    if len(lines) < 2:
        print(msg(lang, "need_two_rows"))
        _pause_exit(lang, message=msg(lang, "need_two_rows"))
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
        _pause_exit(lang, message=msg(lang, "col_not_found", err=e))
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
        _pause_exit(lang, message=msg(lang, "no_valid_data"))
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
            _pause_exit(lang, message=msg(lang, "eb_none"))
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
        _pause_exit(lang, message=msg(lang, "gui_save_fail", err=e))
    print()
    print("=" * 58)

if __name__ == "__main__":
    main()

# -------------------------------------------------------------
# CRRC Puzhen Alstom Transportation Systems Limited
# PATSMET Yang Bohang 2026.07 pre-release
# -------------------------------------------------------------
import time
import sys
import json
import os
from pathlib import Path

# ------------------ Safe file reading ------------------
def safe_read_file(file_path, encodings=('utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'latin-1')):
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise UnicodeDecodeError(f"无法用任何编码读取文件：{file_path}")

# ------------------ Debug pause ------------------
def debug_pause(prompt="\n按回车键继续..."):
    input(prompt)

# ------------------ Format total seconds as HH:MM:SS.mmm ------------------
def format_time(seconds):
    """Format seconds as HH:MM:SS.mmm string"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

def main():
    print("=" * 60)
    print("            紧 急 制 动 计 算 器  ")
    print("=" * 60)
    print()
    print("软件版本 : 0.9（预发布） 2026.07 ")

    # ---------- 1. Determine script directory ----------
    if getattr(sys, 'frozen', False):
        script_dir = Path(sys.executable).parent
    else:
        script_dir = Path(__file__).parent
    print(f"\n[步骤 1] 程序目录：{script_dir}")

    # ---------- 2. Read configuration file ----------
    config_path = script_dir / "config.json"
    print(f"\n[步骤 2] 正在查找配置文件：{config_path}")
    if not config_path.exists():
        print("         × 错误：未找到 config.json")
        input("\n按回车键退出...")
        return

    try:
        config_text = safe_read_file(config_path)
        config = json.loads(config_text)
        speed_signal = config["speed_signal"]
        brake_signal = config["brake_signal"]
        # Time interval parameters no longer needed; time column itself is hour value
        print(f"         ✓ 速度信号名称：{speed_signal}")
        print(f"         ✓ 制动信号名称：{brake_signal}")
    except Exception as e:
        print(f"         × 配置文件解析失败：{e}")
        input("\n按回车键退出...")
        return
    #debug_pause("Press Enter to continue getting data file...")
    time.sleep(0.5)  # pause 0.5 seconds

    # ---------- 3. Get the dragged file ----------
    if len(sys.argv) < 2:
        print("         × 未收到数据文件，请将 .txt 文件拖放到本程序图标上。")
        input("\n按回车键退出...")
        return

    file_path = sys.argv[1]
    print(f"\n[步骤 3] 待处理的数据文件：{file_path}")
    if not os.path.exists(file_path):
        print("         × 文件不存在！")
        input("\n按回车键退出...")
        return
    #debug_pause("Press Enter to start parsing data...")

    # ---------- 4. Read and parse data file (split by whitespace) ----------
    try:
        file_text = safe_read_file(file_path)
        lines = file_text.splitlines(keepends=True)
    except Exception as e:
        print(f"         × 无法读取文件：{e}")
        input("\n按回车键退出...")
        return

    if len(lines) < 2:
        print("         × 数据文件必须至少包含一行表头和一行数据。")
        input("\n按回车键退出...")
        return

    headers = lines[0].rstrip('\n').split()
    print(f"\n[步骤 4] 文件表头（共 {len(headers)} 列）")

    # Locate column indices
    try:
        time_idx = 0                     # First column is time (hour value)
        speed_idx = headers.index(speed_signal)
        brake_idx = headers.index(brake_signal)
        print(f"         时间列索引：{time_idx}（第一列）")
        print(f"         速度列索引：{speed_idx}（对应 '{speed_signal}'）")
        print(f"         制动列索引：{brake_idx}（对应 '{brake_signal}'）")
    except ValueError as e:
        print(f"         × 表头中未找到所需信号列：{e}")
        input("\n按回车键退出...")
        return

    # Read data row by row
    raw_times_sec, raw_speeds, brakes = [], [], []
    skipped = 0
    for line_num, line in enumerate(lines[1:], start=2):
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

    print(f"         读取的有效数据行：{len(raw_times_sec)} 行，跳过无效：{skipped}")
    if raw_times_sec:
        print(f"         时间范围：{format_time(raw_times_sec[0])} ~ {format_time(raw_times_sec[-1])}")
        print(f"         速度范围：{min(raw_speeds):.2f} ~ {max(raw_speeds):.2f} km/h")
        print()
    else:
        print("         × 没有有效数据！")
        input("\n按回车键退出...")
        return
    #debug_pause("Press Enter to search for braking interval...")
    time.sleep(0.5)  # pause 0.5 seconds

    # ---------- 5. Unit conversion (km/h → m/s) ----------
    speeds_ms = [v / 3.6 for v in raw_speeds]

    # ---------- 6. Find braking interval (1→0 falling edge, initial speed > 5 km/h) ----------
    start_idx = None
    search_from = 1
    while search_from < len(brakes):
        if brakes[search_from] == 0 and brakes[search_from-1] == 1:
            if raw_speeds[search_from] > 5.0:
                start_idx = search_from
                print(f"[步骤 5] 找到有效的 EB 点 -> 索引:{start_idx}, 时间:{format_time(raw_times_sec[start_idx])}, 速度:{raw_speeds[start_idx]:.2f} km/h ")
                break
            else:
                print(f"\n         EB 点索引:{search_from} 速度 {raw_speeds[search_from]:.2f} km/h <=5，已跳过，继续搜索...\n")
                search_from += 1
                continue
        search_from += 1

    if start_idx is None:
        if brakes[0] == 0 and raw_speeds[0] > 5.0:
            start_idx = 0
            print("\n         未找到 EB 点，但数据从制动状态（0）开始且速度>5，使用起点作为制动开始点。\n")
        else:
            print("\n         × 未找到有效的 EB 起点（初始速度 > 5 km/h 的 EB 点）。\n")
            input("\n按回车键退出...")
            return

    print(f"\n[步骤 6] 制动起始点 -> 索引:{start_idx}, 时间:{format_time(raw_times_sec[start_idx])}, 速度:{raw_speeds[start_idx]:.2f} km/h")

    # Braking end: speed first < 0.5 km/h
    end_idx = None
    for i in range(start_idx, len(raw_speeds)):
        if raw_speeds[i] < 0.5:
            end_idx = i
            break
    if end_idx is None:
        end_idx = len(raw_speeds) - 1
        print("         速度未降至 0.5 km/h 以下，使用最后一个数据点作为制动结束点。")
    print(f"         制动结束点 -> 索引:{end_idx}, 时间:{format_time(raw_times_sec[end_idx])}, 速度:{raw_speeds[end_idx]:.2f} km/h")
    print()
    debug_pause("         按回车键开始计算...")
    # ---------- 7. Extract interval and calculate ----------
    t_seg = raw_times_sec[start_idx:end_idx+1]
    v_seg = speeds_ms[start_idx:end_idx+1]
    v_kmh_seg = raw_speeds[start_idx:end_idx+1]
    print()
    print("=" * 58)
    print("            计 算 结 果        ")
    print("=" * 58)
    print()
    print(f"  数据点数量：{len(t_seg)}")
    if len(t_seg) > 0:
        print()
        print(f"  时间区间：{format_time(t_seg[0])} ~ {format_time(t_seg[-1])}")
        #print(f"  Speed interval: {v_kmh_seg[0]:.2f} km/h ~ {v_kmh_seg[-1]:.2f} km/h")
    # Braking time (seconds)
    brake_time = t_seg[-1] - t_seg[0]

    # Distance via trapezoidal integration
    distance = 0.0
    for i in range(len(t_seg)-1):
        dt = t_seg[i+1] - t_seg[i]
        v_avg = (v_seg[i] + v_seg[i+1]) / 2.0
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
        avg_decel_str = "无穷大（距离为零）"

    # Rate deceleration = speed difference / brake time
    if brake_time > 0:
        rate_decel = (v0_ms - v_end_ms) / brake_time
        rate_decel_str = f"{rate_decel:.3f} m/s²"
    else:
        rate_decel_str = "无穷大（时间为零）"

    # ---------- 8. Output results ----------
    print()
    print(f"  初始速度：{v0_kmh:.2f} km/h")
    print()
    print(f"  末速度：{v_end_kmh:.2f} km/h")
    print()
    print(f"  制动时间：{brake_time:.4f} 秒")
    print()
    print(f"  制动距离：{distance:.3f} 米")
    print()
    print(f"  减速速率（dv/dt）：{rate_decel_str}")
    print()
    print(f"  平均减速度（V²/2S）：{avg_decel_str}")
    print()
    print("=" * 58)
    input("\n处理完成，按回车键退出...")

if __name__ == "__main__":
    main()

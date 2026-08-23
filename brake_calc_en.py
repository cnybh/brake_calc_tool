# -------------------------------------------------------------
# CRRC Puzhen Alstom Transportation Systems Limited
# PATSMET Yang Bohang 2026.07 pre-release 0.9a
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
    raise UnicodeDecodeError(f"Unable to read file with any encoding: {file_path}")

# ------------------ Debug pause ------------------
def debug_pause(prompt="\nPress Enter to continue..."):
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
    print("     E M E R G E N C Y  B R A K E  C A L C U L A T O R  ")
    print("=" * 60)
    print()
    print("SW Version : 0.9 (pre-release) 2026.07 ")

    # ---------- 1. Determine script directory ----------
    if getattr(sys, 'frozen', False):
        script_dir = Path(sys.executable).parent
    else:
        script_dir = Path(__file__).parent
    print(f"\n[Step 1] Program directory: {script_dir}")

    # ---------- 2. Read configuration file ----------
    config_path = script_dir / "config.json"
    print(f"\n[Step 2] Looking for config file: {config_path}")
    if not config_path.exists():
        print("         × Error: config.json not found")
        input("\nPress Enter to exit...")
        return

    try:
        config_text = safe_read_file(config_path)
        config = json.loads(config_text)
        speed_signal = config["speed_signal"]
        brake_signal = config["brake_signal"]
        # Time interval parameters no longer needed; time column itself is hour value
        print(f"         ✓ Speed signal name: {speed_signal}")
        print(f"         ✓ Brake signal name: {brake_signal}")
    except Exception as e:
        print(f"         × Config file parsing failed: {e}")
        input("\nPress Enter to exit...")
        return
    #debug_pause("Press Enter to continue getting data file...")
    time.sleep(0.5)  # pause 0.5 seconds

    # ---------- 3. Get the dragged file ----------
    if len(sys.argv) < 2:
        print("         × No data file received. Please drag a .txt file onto this program icon.")
        input("\nPress Enter to exit...")
        return

    file_path = sys.argv[1]
    print(f"\n[Step 3] Data file to process: {file_path}")
    if not os.path.exists(file_path):
        print("         × File does not exist!")
        input("\nPress Enter to exit...")
        return
    #debug_pause("Press Enter to start parsing data...")

    # ---------- 4. Read and parse data file (split by whitespace) ----------
    try:
        file_text = safe_read_file(file_path)
        lines = file_text.splitlines(keepends=True)
    except Exception as e:
        print(f"         × Unable to read file: {e}")
        input("\nPress Enter to exit...")
        return

    if len(lines) < 2:
        print("         × Data file must contain at least a header row and one data row.")
        input("\nPress Enter to exit...")
        return

    headers = lines[0].rstrip('\n').split()
    print(f"\n[Step 4] File header (total {len(headers)} columns)")

    # Locate column indices
    try:
        time_idx = 0                     # First column is time (hour value)
        speed_idx = headers.index(speed_signal)
        brake_idx = headers.index(brake_signal)
        print(f"         Time column index: {time_idx} (first column)")
        print(f"         Speed column index: {speed_idx} (corresponding to '{speed_signal}')")
        print(f"         Brake column index: {brake_idx} (corresponding to '{brake_signal}')")
    except ValueError as e:
        print(f"         × Required signal column not found in header: {e}")
        input("\nPress Enter to exit...")
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

    print(f"         Valid data rows read: {len(raw_times_sec)} rows, skipped invalid: {skipped}")
    if raw_times_sec:
        print(f"         Time range: {format_time(raw_times_sec[0])} ~ {format_time(raw_times_sec[-1])}")
        print(f"         Speed range: {min(raw_speeds):.2f} ~ {max(raw_speeds):.2f} km/h")
        print()
    else:
        print("         × No valid data!")
        input("\nPress Enter to exit...")
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
                print(f"[Step 5] Found valid EB point -> index:{start_idx}, time:{format_time(raw_times_sec[start_idx])}, speed:{raw_speeds[start_idx]:.2f} km/h ")
                break
            else:
                print(f"\n         EB point index:{search_from} speed {raw_speeds[search_from]:.2f} km/h <=5, skipped, continue searching...\n")
                search_from += 1
                continue
        search_from += 1

    if start_idx is None:
        if brakes[0] == 0 and raw_speeds[0] > 5.0:
            start_idx = 0
            print("\n         No EB point found, but data starts in braking state (0) with speed>5, using start as brake onset.\n")
        else:
            print("\n         × No valid EB start found (EB point with initial speed > 5 km/h).\n")
            input("\nPress Enter to exit...")
            return

    print(f"\n[Step 6] Braking start point -> index:{start_idx}, time:{format_time(raw_times_sec[start_idx])}, speed:{raw_speeds[start_idx]:.2f} km/h")

    # Braking end: speed first < 0.5 km/h
    end_idx = None
    for i in range(start_idx, len(raw_speeds)):
        if raw_speeds[i] < 0.5:
            end_idx = i
            break
    if end_idx is None:
        end_idx = len(raw_speeds) - 1
        print("         Speed never dropped below 0.5 km/h, using last data point as brake end.")
    print(f"         Braking end point -> index:{end_idx}, time:{format_time(raw_times_sec[end_idx])}, speed:{raw_speeds[end_idx]:.2f} km/h")
    print()
    debug_pause("         Press Enter to start calculation...")
    # ---------- 7. Extract interval and calculate ----------
    t_seg = raw_times_sec[start_idx:end_idx+1]
    v_seg = speeds_ms[start_idx:end_idx+1]
    v_kmh_seg = raw_speeds[start_idx:end_idx+1]
    print()
    print("=" * 58)
    print("          C A L C U L A T I O N   R E S U L T S        ")
    print("=" * 58)
    print()
    print(f"  Data points: {len(t_seg)}")
    if len(t_seg) > 0:
        print()
        print(f"  Time interval: {format_time(t_seg[0])} ~ {format_time(t_seg[-1])}")
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
        avg_decel_str = "Infinite (distance zero)"

    # Rate deceleration = speed difference / brake time
    if brake_time > 0:
        rate_decel = (v0_ms - v_end_ms) / brake_time
        rate_decel_str = f"{rate_decel:.3f} m/s²"
    else:
        rate_decel_str = "Infinite (time zero)"

    # ---------- 8. Output results ----------
    print()
    print(f"  Initial speed: {v0_kmh:.2f} km/h")
    print()
    print(f"  Final speed: {v_end_kmh:.2f} km/h")
    print()
    print(f"  Braking time: {brake_time:.4f} sec")
    print()
    print(f"  Braking distance: {distance:.3f} m")
    print()
    print(f"  Rate deceleration (dv/dt): {rate_decel_str}")
    print()
    print(f"  Average deceleration (V²/2S): {avg_decel_str}")
    print()
    print("=" * 58)
    input("\nProcessing complete. Press Enter to exit...")

if __name__ == "__main__":
    main()

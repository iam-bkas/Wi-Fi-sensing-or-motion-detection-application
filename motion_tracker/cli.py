import argparse
import time
from datetime import datetime
from typing import Optional
import threading
import queue
import csv

from .datasource import WindowsWlanSignalSource
from .detector import MotionDetector

try:
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def run(source_interface: Optional[str], interval: float, window: int, threshold: float, min_duration: float, csv_path: Optional[str], visualize: bool, events_csv: Optional[str]):
    src = WindowsWlanSignalSource(interface=source_interface)
    det = MotionDetector(window_size=window, threshold=threshold)
    min_samples = max(1, int(min_duration / interval))
    
    data_queue = queue.Queue() if visualize else None
    events_queue = queue.Queue() if visualize else None
    
    def worker():
        active_count = 0
        f = None
        fe = None
        if csv_path:
            f = open(csv_path, "a", encoding="utf-8")
            if f.tell() == 0:
                f.write("timestamp,signal,avg,std,motion\n")
        if events_csv:
            fe = open(events_csv, "a", encoding="utf-8", newline="")
            w = csv.writer(fe)
            if fe.tell() == 0:
                w.writerow(["start", "end", "duration_s", "max_std", "mean_signal"])
        
        last_event = False
        ev_start_ts = None
        ev_start_time = None
        ev_max_std = 0.0
        ev_sig_sum = 0.0
        ev_count = 0
        
        while True:
            ts = datetime.utcnow().isoformat()
            try:
                val = src.read()
            except Exception as e:
                s = f"{ts} source_error {str(e)}"
                print(s)
                if f:
                    f.write(f"{ts},,,,{0}\n")
                    f.flush()
                time.sleep(interval)
                continue
            
            moving, avg, std, level = det.update(val)
            if moving:
                active_count += 1
            else:
                active_count = 0
            
            event = active_count >= min_samples
            state = "MOTION" if event else "IDLE"
            
            print(f"{ts} signal={val}% avg={avg:.2f}% std={std:.2f} state={state} level={level}")
            
            if f:
                f.write(f"{ts},{val},{avg:.4f},{std:.4f},{1 if event else 0}\n")
                f.flush()
            
            if data_queue:
                data_queue.put((ts, val, avg, std, event))
            
            if not last_event and event:
                ev_start_ts = ts
                ev_start_time = time.time()
                ev_max_std = std
                ev_sig_sum = val
                ev_count = 1
            elif last_event and event:
                if std > ev_max_std:
                    ev_max_std = std
                ev_sig_sum += val
                ev_count += 1
            elif last_event and not event:
                end_ts = ts
                duration = time.time() - (ev_start_time or time.time())
                mean_sig = (ev_sig_sum / ev_count) if ev_count else 0.0
                if events_queue:
                    events_queue.put((ev_start_ts, end_ts))
                if events_csv and fe:
                    w.writerow([ev_start_ts, end_ts, round(duration, 3), round(ev_max_std, 3), round(mean_sig, 3)])
                    fe.flush()
                ev_start_ts = None
                ev_start_time = None
                ev_max_std = 0.0
                ev_sig_sum = 0.0
                ev_count = 0
            last_event = event
                
            time.sleep(interval)

    # Start collection thread
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    
    if visualize:
        if not HAS_MATPLOTLIB:
            print("Error: matplotlib not installed. Cannot visualize.")
            return

        # Setup Plot
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
        fig.suptitle('WiFi Motion Tracker')
        
        # Signal Plot
        xs = []
        ys_signal = []
        ys_avg = []
        
        # Stats Plot
        ys_std = []
        ys_thresh = []
        events = []
        
        MAX_POINTS = 100
        spans = []
        
        last_event = [False]
        last_start = [None]
        def animate(i):
            while not data_queue.empty():
                ts, val, avg, std, event = data_queue.get()
                now = datetime.now()
                xs.append(now)
                ys_signal.append(val)
                ys_avg.append(avg)
                ys_std.append(std)
                ys_thresh.append(threshold)
                if event:
                    events.append(now)
                
                # Trim
                if len(xs) > MAX_POINTS:
                    xs.pop(0)
                    ys_signal.pop(0)
                    ys_avg.pop(0)
                    ys_std.pop(0)
                    ys_thresh.pop(0)
                if len(events) > MAX_POINTS:
                    events = events[-MAX_POINTS:]
            while events_queue and not events_queue.empty():
                s_ts, e_ts = events_queue.get()
                # approximate datetime for spans using current wall clock timestamps; used only for display
                spans.append((s_ts, e_ts))
                if len(spans) > 100:
                    spans = spans[-100:]
            if not xs:
                return
            
            ax1.clear()
            ax1.plot(xs, ys_signal, label='Signal %', color='blue', alpha=0.5)
            ax1.plot(xs, ys_avg, label='Average', color='green', linewidth=2)
            ax1.set_ylabel('Signal Strength (%)')
            ax1.set_ylim(0, 100)
            ax1.legend(loc='upper right')
            ax1.grid(True)
            for e in events:
                ax1.axvline(e, color='red', alpha=0.25)
            for s_ts, e_ts in spans:
                ax1.axvspan(datetime.fromisoformat(s_ts), datetime.fromisoformat(e_ts), color='red', alpha=0.1)
            
            ax2.clear()
            ax2.plot(xs, ys_std, label='Deviation', color='red')
            ax2.plot(xs, ys_thresh, label='Threshold', color='orange', linestyle='--')
            for e in events:
                ax2.axvline(e, color='red', alpha=0.25)
            for s_ts, e_ts in spans:
                ax2.axvspan(datetime.fromisoformat(s_ts), datetime.fromisoformat(e_ts), color='red', alpha=0.1)
            
            if last_event[0]:
                ax2.text(xs[-1], ys_std[-1], "MOTION", color='red', fontweight='bold')
                fig.patch.set_facecolor('#ffebee')
            else:
                fig.patch.set_facecolor('white')

            ax2.set_ylabel('Standard Deviation')
            ax2.legend(loc='upper right')
            ax2.grid(True)

        ani = animation.FuncAnimation(fig, animate, interval=100)
        plt.show()
    else:
        # Keep main thread alive if not visualizing
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

def main():
    p = argparse.ArgumentParser(prog="wifi-motion-tracker")
    p.add_argument("--interface", default=None)
    p.add_argument("--interval", type=float, default=0.5)
    p.add_argument("--window", type=int, default=30)
    p.add_argument("--threshold", type=float, default=8.0)
    p.add_argument("--min-duration", type=float, default=1.0)
    p.add_argument("--csv", default=None)
    p.add_argument("--visualize", action="store_true", help="Show real-time plot")
    p.add_argument("--events-csv", default=None)
    a = p.parse_args()
    run(a.interface, a.interval, a.window, a.threshold, a.min_duration, a.csv, a.visualize, a.events_csv)


if __name__ == "__main__":
    main()

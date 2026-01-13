import threading
import queue
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk
import csv

from .datasource import WindowsWlanSignalSource
from .detector import MotionDetector

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("WiFi Motion Tracker")
        self.interval = tk.DoubleVar(value=0.5)
        self.threshold = tk.DoubleVar(value=8.0)
        self.window = tk.IntVar(value=30)
        self.state_str = tk.StringVar(value="IDLE")
        self.crowd_str = tk.StringVar(value="Empty")
        self.running = False
        self.queue = queue.Queue()
        self.source = WindowsWlanSignalSource()
        self.detector = MotionDetector(window_size=self.window.get(), threshold=self.threshold.get())

        # Setup Tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_monitor = ttk.Frame(self.notebook)
        self.tab_train = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_monitor, text="Live Monitor")
        self.notebook.add(self.tab_train, text="Train AI")

        self._setup_monitor_tab()
        self._setup_train_tab()

        self.xs = []
        self.sig = []
        self.avg = []
        self.std = []
        self.thr = []
        self.events = []
        self.max_points = 200
        self.events_queue = queue.Queue()
        self.log_events = tk.BooleanVar(value=True)
        self.events_csv = 'motion_events.csv'

        # Move Checkbutton to Monitor Tab
        side = ttk.Frame(self.tab_monitor)
        side.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)
        ttk.Checkbutton(side, text="Log Events", variable=self.log_events).pack(side=tk.LEFT)
        ttk.Label(side, text=self.events_csv).pack(side=tk.LEFT, padx=(10, 0))

        # Move Treeview to Monitor Tab
        self.tree = ttk.Treeview(self.tab_monitor, columns=("start", "end", "duration", "maxstd", "meansig"), show="headings", height=6)
        for col, text in [("start", "Start"), ("end", "End"), ("duration", "Duration s"), ("maxstd", "Max Std"), ("meansig", "Mean Sig")]:
            self.tree.heading(col, text=text)
            self.tree.column(col, anchor=tk.CENTER, width=120)
        self.tree.pack(fill=tk.X, padx=10)

        self.root.after(100, self.update_ui)

    def _setup_monitor_tab(self):
        top = ttk.Frame(self.tab_monitor)
        top.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(top, text="Interval (s)").pack(side=tk.LEFT)
        ttk.Scale(top, from_=0.1, to=2.0, variable=self.interval, orient=tk.HORIZONTAL).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Label(top, text="Threshold").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Scale(top, from_=2.0, to=20.0, variable=self.threshold, orient=tk.HORIZONTAL).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Label(top, text="Window").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Scale(top, from_=10, to=120, variable=self.window, orient=tk.HORIZONTAL).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        ctl = ttk.Frame(self.tab_monitor)
        ctl.pack(fill=tk.X, padx=10)
        self.btn = ttk.Button(ctl, text="Start", command=self.start)
        self.btn.pack(side=tk.LEFT)
        ttk.Label(ctl, text="State:").pack(side=tk.LEFT, padx=(10, 0))
        self.state_label = ttk.Label(ctl, textvariable=self.state_str, width=8)
        self.state_label.pack(side=tk.LEFT)
        
        ttk.Label(ctl, text="Crowd:").pack(side=tk.LEFT, padx=(10, 0))
        self.crowd_label = ttk.Label(ctl, textvariable=self.crowd_str, font=("Helvetica", 10, "bold"))
        self.crowd_label.pack(side=tk.LEFT)

        fig = Figure(figsize=(9, 5))
        self.ax1 = fig.add_subplot(211)
        self.ax2 = fig.add_subplot(212)
        self.canvas = FigureCanvasTkAgg(fig, master=self.tab_monitor)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _setup_train_tab(self):
        # Variables for training
        self.train_people = tk.IntVar(value=0)
        self.is_recording = False
        self.train_file = None
        self.train_status = tk.StringVar(value="Ready to record")
        
        frame = ttk.Frame(self.tab_train)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(frame, text="AI Data Collection", font=("Helvetica", 14, "bold")).pack(pady=10)
        ttk.Label(frame, text="1. Select number of people currently in the room.").pack(anchor=tk.W)
        ttk.Label(frame, text="2. Click 'Start Recording'.").pack(anchor=tk.W)
        ttk.Label(frame, text="3. Move naturally (or sit still) for 1-2 minutes.").pack(anchor=tk.W)
        
        ctl = ttk.Frame(frame)
        ctl.pack(fill=tk.X, pady=20)
        
        ttk.Label(ctl, text="People Count:").pack(side=tk.LEFT)
        ttk.Spinbox(ctl, from_=0, to=10, textvariable=self.train_people, width=5).pack(side=tk.LEFT, padx=10)
        
        self.btn_rec = ttk.Button(ctl, text="Start Recording", command=self.toggle_record)
        self.btn_rec.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(frame, textvariable=self.train_status, foreground="blue").pack(pady=10)
        
        self.train_log = tk.Text(frame, height=15)
        self.train_log.pack(fill=tk.BOTH, expand=True)

    def toggle_record(self):
        if self.is_recording:
            self.is_recording = False
            self.btn_rec.config(text="Start Recording")
            self.train_status.set("Recording stopped.")
            if self.train_file:
                self.train_file.close()
                self.train_file = None
        else:
            count = self.train_people.get()
            fname = f"train_data_{count}people_{int(time.time())}.csv"
            self.train_file = open(fname, "w", encoding="utf-8", newline="")
            self.train_writer = csv.writer(self.train_file)
            self.train_writer.writerow(["timestamp", "signal"])
            
            self.is_recording = True
            self.btn_rec.config(text="Stop Recording")
            self.train_status.set(f"Recording to {fname}...")
            
            # Ensure background thread is running
            if not self.running:
                self.start()


    def start(self):
        if self.running:
            self.running = False
            self.btn.config(text="Start")
            return
        self.running = True
        self.btn.config(text="Stop")
        self.detector = MotionDetector(window_size=int(self.window.get()), threshold=float(self.threshold.get()))
        t = threading.Thread(target=self.worker, daemon=True)
        t.start()

    def worker(self):
        active_count = 0
        last_event = False
        ev_start_ts = None
        ev_start_time = None
        ev_max_std = 0.0
        ev_sig_sum = 0.0
        ev_count = 0
        min_samples = max(1, int(1.0 / max(self.interval.get(), 0.1)))
        while self.running:
            try:
                val = self.source.read()
            except Exception as e:
                self.queue.put((datetime.utcnow().isoformat(), None, 0.0, 0.0, False, 0, str(e)))
                time.sleep(self.interval.get())
                continue
            moving, avg, std, level = self.detector.update(val)
            if moving:
                active_count += 1
            else:
                active_count = 0
            event = active_count >= min_samples
            if not last_event and event:
                ev_start_ts = datetime.utcnow().isoformat()
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
                end_ts = datetime.utcnow().isoformat()
                duration = time.time() - (ev_start_time or time.time())
                mean_sig = (ev_sig_sum / ev_count) if ev_count else 0.0
                self.events_queue.put((ev_start_ts, end_ts, duration, ev_max_std, mean_sig))
                if self.log_events.get():
                    with open(self.events_csv, 'a', encoding='utf-8', newline='') as fe:
                        w = csv.writer(fe)
                        if fe.tell() == 0:
                            w.writerow(["start", "end", "duration_s", "max_std", "mean_signal"])
                        w.writerow([ev_start_ts, end_ts, round(duration, 3), round(ev_max_std, 3), round(mean_sig, 3)])
                ev_start_ts = None
                ev_start_time = None
                ev_max_std = 0.0
                ev_sig_sum = 0.0
                ev_count = 0
            last_event = event
            self.queue.put((datetime.utcnow().isoformat(), val, avg, std, event, level, None))
            
            # Training Data Log
            if self.is_recording and self.train_file:
                try:
                    self.train_writer.writerow([datetime.utcnow().isoformat(), val])
                except:
                    pass
            
            time.sleep(self.interval.get())

    def update_ui(self):
        changed = False
        error = None
        event = False
        level = 0
        while not self.queue.empty():
            ts, val, avg, std, ev, lvl, err = self.queue.get()
            if err:
                error = err
                continue
            now = datetime.now()
            self.xs.append(now)
            self.sig.append(val)
            self.avg.append(avg)
            self.std.append(std)
            self.thr.append(self.threshold.get())
            if ev:
                self.events.append(now)
            if len(self.xs) > self.max_points:
                self.xs.pop(0)
                self.sig.pop(0)
                self.avg.pop(0)
                self.std.pop(0)
                self.thr.pop(0)
            if len(self.events) > self.max_points:
                self.events = self.events[-self.max_points:]
            changed = True
            event = ev
            level = lvl
        if changed:
            self.ax1.clear()
            self.ax1.plot(self.xs, self.sig, label="Signal %", color="blue")
            self.ax1.plot(self.xs, self.avg, label="Average", color="green")
            self.ax1.set_ylim(0, 100)
            self.ax1.legend(loc="upper right")
            self.ax1.grid(True)
            for e in self.events:
                self.ax1.axvline(e, color="red", alpha=0.25)
            self.ax2.clear()
            self.ax2.plot(self.xs, self.std, label="Deviation", color="red")
            self.ax2.plot(self.xs, self.thr, label="Threshold", color="orange", linestyle="--")
            self.ax2.legend(loc="upper right")
            self.ax2.grid(True)
            for e in self.events:
                self.ax2.axvline(e, color="red", alpha=0.25)
            self.state_str.set("MOTION" if event else "IDLE")
            
            # Update Crowd Estimate
            if level == 0:
                self.crowd_str.set("Empty")
            elif level == 1:
                self.crowd_str.set("Low")
            elif level == 2:
                self.crowd_str.set("Medium")
            elif level == 3:
                self.crowd_str.set("High")
                
            self.canvas.draw()
            
            # Update Training Log (Sample)
            if self.is_recording and len(self.sig) > 0:
                self.train_log.insert(tk.END, f"Recorded: {self.sig[-1]}%\n")
                self.train_log.see(tk.END)
                
        while not self.events_queue.empty():
            s_ts, e_ts, duration, max_std, mean_sig = self.events_queue.get()
            self.tree.insert('', tk.END, values=(s_ts, e_ts, f"{duration:.2f}", f"{max_std:.2f}", f"{mean_sig:.2f}"))
        if error:
            self.state_str.set(error)
        self.root.after(100, self.update_ui)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

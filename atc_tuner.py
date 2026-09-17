"""
ATC Tuner — Live ATC audio streaming from LiveATC.net
Streams real ATC communications from online airport feeds.
No hardware required — just an internet connection.
"""
import tkinter as tk
from tkinter import ttk
import threading
import time
import numpy as np
import sounddevice as sd
import av

AUDIO_RATE = 24_000  # Playback sample rate

# (display_label, stream_url, freq_hint)
# Find more feed names at liveatc.net/search
# URL format: http://d.liveatc.net/<feed_name>
PRESETS = [
    # Sydney
    ("YSSY  Approach",   "http://d.liveatc.net/yssy_app",   "124.4 MHz"),
    ("YSSY  Departure",  "http://d.liveatc.net/yssy_dep",   "123.0 MHz"),
    ("YSSY  Tower",      "http://d.liveatc.net/yssy_twr",   "120.5 MHz"),
    ("YSSY  Ground",     "http://d.liveatc.net/yssy_gnd",   "121.7 MHz"),
    # Melbourne
    ("YMML  Approach",   "http://d.liveatc.net/ymml_app",   "132.0 MHz"),
    ("YMML  Tower",      "http://d.liveatc.net/ymml_twr",   "120.5 MHz"),
    # Brisbane
    ("YBBN  Approach",   "http://d.liveatc.net/ybbn_app",   "124.7 MHz"),
    ("YBBN  Tower",      "http://d.liveatc.net/ybbn_twr",   "118.45 MHz"),
    # Perth
    ("YPPH  Tower/Dep",  "http://d.liveatc.net/ypph",        "127.4 MHz"),
    # Adelaide
    ("YPAD  Tower",      "http://d.liveatc.net/ypad",        "120.9 MHz"),
    # Gold Coast
    ("YBCG  Tower",      "http://d.liveatc.net/ybcg",        "118.7 MHz"),
    # Canberra
    ("YSCB  Tower",      "http://d.liveatc.net/yscb",        "118.7 MHz"),
    # Auckland
    ("NZAA  Approach",   "http://d.liveatc.net/nzaa_app",   "124.3 MHz"),
    ("NZAA  Tower",      "http://d.liveatc.net/nzaa_twr",   "118.7 MHz"),
    # Christchurch
    ("NZCH  Tower",      "http://d.liveatc.net/nzch",        "118.75 MHz"),
    # Wellington
    ("NZWN  Approach",   "http://d.liveatc.net/nzwn_app",   "119.3 MHz"),
]


class ATCTuner:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ATC Tuner — Live Streaming")
        self.root.resizable(False, False)

        self.running = False
        self.scan_active = False
        self._container = None
        self._next_url = None   # set to trigger mid-stream URL switch
        self._stream_thread: threading.Thread | None = None

        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # ── Stream URL row ──
        url_frame = ttk.LabelFrame(self.root,
                                   text="Stream URL  (paste a LiveATC URL or click a preset)")
        url_frame.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)
        url_frame.columnconfigure(0, weight=1)

        self.url_var = tk.StringVar(value="http://d.liveatc.net/yssy_app")
        url_entry = ttk.Entry(url_frame, textvariable=self.url_var,
                              width=52, font=("Courier", 10))
        url_entry.grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        url_entry.bind("<Return>", lambda _: self._reconnect())

        ttk.Button(url_frame, text="Connect", command=self._reconnect).grid(
            row=0, column=1, padx=6)

        # ── Signal meter ──
        meter_frame = ttk.Frame(self.root)
        meter_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8)
        ttk.Label(meter_frame, text="Level:").pack(side="left")
        self.signal_bar = ttk.Progressbar(meter_frame, length=260, maximum=100)
        self.signal_bar.pack(side="left", padx=6)
        self.signal_label = ttk.Label(meter_frame, text="-- dBFS", width=10)
        self.signal_label.pack(side="left")

        # ── Controls ──
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)

        ttk.Label(ctrl_frame, text="Volume:").grid(row=0, column=0, sticky="e")
        self.vol_var = tk.DoubleVar(value=0.8)
        ttk.Scale(ctrl_frame, from_=0, to=1, variable=self.vol_var,
                  orient="horizontal", length=120).grid(row=0, column=1, padx=4)

        ttk.Label(ctrl_frame, text="Squelch:").grid(
            row=0, column=2, sticky="e", padx=(12, 0))
        self.sql_var = tk.DoubleVar(value=0.0)
        ttk.Scale(ctrl_frame, from_=0, to=0.15, variable=self.sql_var,
                  orient="horizontal", length=120).grid(row=0, column=3, padx=4)
        self.sql_label = ttk.Label(ctrl_frame, text="off", width=6)
        self.sql_label.grid(row=0, column=4, sticky="w")
        self.sql_var.trace_add("write", self._on_sql_change)

        # ── Presets ──
        preset_frame = ttk.LabelFrame(
            self.root, text="Airport Feeds  (find more at liveatc.net/search)")
        preset_frame.grid(row=3, column=0, sticky="nsew", **pad)

        for name, url, freq in PRESETS:
            btn = tk.Button(
                preset_frame,
                text=f"{name}  {freq}",
                width=30, anchor="w", relief="flat",
                bg="#f0f0f0", activebackground="#d0e8ff",
                command=lambda u=url, n=name: self._select_preset(u, n),
            )
            btn.pack(fill="x", padx=4, pady=1)

        # ── Right panel ──
        right = ttk.Frame(self.root)
        right.grid(row=3, column=1, sticky="nsew", **pad)

        self.start_btn = ttk.Button(right, text="▶  Start Listening",
                                    command=self._toggle_rx, width=22)
        self.start_btn.grid(row=0, column=0, pady=6)

        # Cycler
        cycle_lf = ttk.LabelFrame(right, text="Cycle Streams")
        cycle_lf.grid(row=1, column=0, sticky="ew", pady=4)

        ttk.Label(cycle_lf, text="Dwell (s):").grid(
            row=0, column=0, sticky="e", padx=4)
        self.dwell_var = tk.StringVar(value="8")
        ttk.Entry(cycle_lf, textvariable=self.dwell_var, width=5).grid(
            row=0, column=1, padx=4, pady=4)

        self.scan_btn = ttk.Button(cycle_lf, text="▶ Cycle All Presets",
                                   command=self._toggle_scan, width=18)
        self.scan_btn.grid(row=1, column=0, columnspan=2, pady=4)

        self.scan_label = ttk.Label(cycle_lf, text="", wraplength=160)
        self.scan_label.grid(row=2, column=0, columnspan=2)

        # Status
        self.status_var = tk.StringVar(value="Ready — press Start to connect")
        ttk.Label(right, textvariable=self.status_var,
                  wraplength=200, justify="left").grid(
            row=2, column=0, pady=8, sticky="w")

        ttk.Label(right,
                  text="Tip: liveatc.net/search — find\nfeeds by airport ICAO code",
                  foreground="gray",
                  font=("TkDefaultFont", 8)).grid(row=3, column=0, sticky="sw")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Control callbacks ──────────────────────────────────────────────────────
    def _on_sql_change(self, *_):
        v = self.sql_var.get()
        self.sql_label.config(text="off" if v < 0.001 else f"{v:.3f}")

    def _select_preset(self, url: str, name: str):
        self.url_var.set(url)
        if self.running:
            self._next_url = url
            self.status_var.set(f"Switching → {name}…")

    def _reconnect(self):
        if self.running:
            self._next_url = self.url_var.get()
            self.status_var.set("Reconnecting…")

    # ── Start / Stop ──────────────────────────────────────────────────────────
    def _toggle_rx(self):
        if self.running:
            self._stop_rx()
        else:
            self._start_rx()

    def _start_rx(self):
        self.running = True
        self.start_btn.config(text="■  Stop")
        self.status_var.set("Connecting…")
        self._stream_thread = threading.Thread(
            target=self._stream_loop, daemon=True)
        self._stream_thread.start()

    def _stop_rx(self):
        self.running = False
        self.scan_active = False
        self.scan_btn.config(text="▶ Cycle All Presets")
        self.scan_label.config(text="")
        self.start_btn.config(text="▶  Start Listening")
        self.status_var.set("Stopped")
        self._update_meter(0.0)

    # ── Streaming backend ─────────────────────────────────────────────────────
    def _stream_loop(self):
        """Background thread: connects to URL, decodes audio, feeds sounddevice."""
        while self.running:
            url = self._next_url or self.url_var.get()
            self._next_url = None

            if not url:
                time.sleep(0.5)
                continue

            try:
                container = av.open(
                    url,
                    options={"user_agent": "ATC-Tuner/1.0"},
                    timeout=(10, 30),   # (connect_s, read_s)
                )
                self._container = container

                resampler = av.AudioResampler("fltp", "mono", AUDIO_RATE)
                feed = url.rstrip("/").split("/")[-1]
                self.root.after(0, self.status_var.set, f"Streaming: {feed}")

                with sd.OutputStream(samplerate=AUDIO_RATE, channels=1,
                                     dtype="float32", latency="high") as out:
                    for frame in container.decode(audio=0):
                        if not self.running:
                            return
                        if self._next_url:
                            break   # caller wants a different URL

                        for rf in resampler.resample(frame):
                            raw = rf.to_ndarray()[0].astype(np.float32)
                            if not len(raw):
                                continue

                            rms = float(np.sqrt(np.mean(raw ** 2)))
                            self.root.after(0, self._update_meter, rms)

                            squelch = self.sql_var.get()
                            if squelch > 0.001 and rms < squelch:
                                raw = np.zeros_like(raw)

                            vol = self.vol_var.get() * 2.0
                            raw = np.clip(raw * vol, -1.0, 1.0)
                            out.write(raw.reshape(-1, 1))

                container.close()
                self._container = None

            except Exception as exc:
                self._container = None
                if not self.running:
                    return
                if self._next_url:
                    continue    # switching URLs; suppress error display

                msg = str(exc)
                if any(k in msg for k in ("404", "403", "Connection refused")):
                    feed = url.rstrip("/").split("/")[-1]
                    msg = (f"Feed '{feed}' not found — "
                           "check liveatc.net/search for the correct name")
                elif any(k in msg.lower() for k in ("timeout", "timed out")):
                    msg = "Connection timed out — check your internet connection"
                self.root.after(0, self.status_var.set, msg[:80])

                # Back off 5 s then auto-retry
                for _ in range(50):
                    if not self.running or self._next_url:
                        break
                    time.sleep(0.1)

    def _update_meter(self, rms: float):
        db = 20.0 * np.log10(rms + 1e-9)
        pct = max(0.0, min(100.0, (db + 60.0) * 2.0))
        self.signal_bar["value"] = pct
        self.signal_label.config(text=f"{db:5.1f} dBFS")

    # ── Stream cycler ─────────────────────────────────────────────────────────
    def _toggle_scan(self):
        if self.scan_active:
            self.scan_active = False
            self.scan_btn.config(text="▶ Cycle All Presets")
            self.scan_label.config(text="")
            return
        if not self.running:
            self._start_rx()
        self.scan_active = True
        self.scan_btn.config(text="■ Stop Cycling")
        threading.Thread(target=self._cycle_loop, daemon=True).start()

    def _cycle_loop(self):
        try:
            dwell = float(self.dwell_var.get())
        except ValueError:
            dwell = 8.0

        idx = 0
        while self.scan_active and self.running:
            name, url, freq = PRESETS[idx % len(PRESETS)]
            self._next_url = url
            self.root.after(0, self.url_var.set, url)
            self.root.after(0, self.scan_label.config,
                            {"text": f"{name}\n{freq}"})

            deadline = time.monotonic() + dwell
            while time.monotonic() < deadline:
                if not self.scan_active or not self.running:
                    break
                time.sleep(0.1)

            idx += 1

        self.root.after(0, self.scan_label.config, {"text": ""})
        if self.scan_active:
            self.scan_active = False
            self.root.after(0, self.scan_btn.config,
                            {"text": "▶ Cycle All Presets"})

    # ── Cleanup ───────────────────────────────────────────────────────────────
    def _on_close(self):
        self._stop_rx()
        self.root.destroy()


def main():
    root = tk.Tk()
    ATCTuner(root)
    root.mainloop()


if __name__ == "__main__":
    main()

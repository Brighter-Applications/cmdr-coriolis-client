"""Main tkinter GUI for cmdr-coriolis-client.

Provides a simple window where the user can:
  - enter / save their API key
  - see their CMDR name (read from the journal)
  - set a custom journal directory
  - start / stop monitoring and sending events to the Journal API
  - view a live activity log
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext

import requests

from client import api, config, journal

WINDOW_TITLE = "CMDR Coriolis Client"
WINDOW_WIDTH = 620
WINDOW_HEIGHT = 480
PAD = 8
ENTRY_WIDTH = 40
LOG_MAX_LINES = 500

STATUS_IDLE = "Idle"
STATUS_MONITORING = "Monitoring…"


class App(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title(WINDOW_TITLE)
        self.resizable(True, True)
        self.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self._monitor_thread: threading.Thread | None = None
        self._tailer: journal.JournalTailer | None = None
        self._msg_queue: queue.Queue = queue.Queue()
        self._cmdr_name: str = ""

        self._build_ui()
        self._load_saved_settings()
        self._auto_detect_journal()

        self.after(200, self._process_queue)

    # ---- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        row = 0

        # API key
        api_frame = tk.LabelFrame(self, text="API Key", padx=PAD, pady=PAD)
        api_frame.grid(row=row, column=0, sticky="ew", padx=PAD, pady=(PAD, 0))
        api_frame.columnconfigure(1, weight=1)

        tk.Label(api_frame, text="Key:").grid(row=0, column=0, sticky="w")
        self._api_key_var = tk.StringVar()
        self._api_key_entry = tk.Entry(api_frame, textvariable=self._api_key_var, show="*", width=ENTRY_WIDTH)
        self._api_key_entry.grid(row=0, column=1, sticky="ew", padx=(PAD, 0))

        self._show_key_var = tk.BooleanVar(value=False)
        tk.Checkbutton(api_frame, text="Show", variable=self._show_key_var, command=self._toggle_key_visibility).grid(row=0, column=2, padx=(4, 0))
        tk.Button(api_frame, text="Save Key", command=self._save_api_key).grid(row=0, column=3, padx=(PAD, 0))

        row += 1

        # Journal path
        path_frame = tk.LabelFrame(self, text="Journal Directory", padx=PAD, pady=PAD)
        path_frame.grid(row=row, column=0, sticky="ew", padx=PAD, pady=(PAD, 0))
        path_frame.columnconfigure(1, weight=1)

        tk.Label(path_frame, text="Path:").grid(row=0, column=0, sticky="w")
        self._journal_path_var = tk.StringVar()
        tk.Entry(path_frame, textvariable=self._journal_path_var, width=ENTRY_WIDTH).grid(row=0, column=1, sticky="ew", padx=(PAD, 0))
        tk.Button(path_frame, text="Browse…", command=self._browse_journal_dir).grid(row=0, column=2, padx=(PAD, 0))
        tk.Button(path_frame, text="Apply", command=self._apply_journal_path).grid(row=0, column=3, padx=(4, 0))

        row += 1

        # Commander info
        cmdr_frame = tk.LabelFrame(self, text="Commander", padx=PAD, pady=PAD)
        cmdr_frame.grid(row=row, column=0, sticky="ew", padx=PAD, pady=(PAD, 0))
        cmdr_frame.columnconfigure(1, weight=1)

        tk.Label(cmdr_frame, text="CMDR:").grid(row=0, column=0, sticky="w")
        self._cmdr_name_var = tk.StringVar(value="(not yet read)")
        tk.Label(cmdr_frame, textvariable=self._cmdr_name_var, font=("TkDefaultFont", 10, "bold"), anchor="w").grid(row=0, column=1, sticky="ew", padx=(PAD, 0))

        row += 1

        # Controls
        ctrl_frame = tk.Frame(self)
        ctrl_frame.grid(row=row, column=0, sticky="ew", padx=PAD, pady=(PAD, 0))

        self._monitor_btn = tk.Button(ctrl_frame, text="Start Monitoring", command=self._toggle_monitoring, width=18)
        self._monitor_btn.pack(side="left")

        self._status_var = tk.StringVar(value=STATUS_IDLE)
        tk.Label(ctrl_frame, textvariable=self._status_var, anchor="w").pack(side="left", padx=(PAD, 0))

        row += 1

        # Log area
        log_frame = tk.LabelFrame(self, text="Activity Log", padx=PAD, pady=PAD)
        log_frame.grid(row=row, column=0, sticky="nsew", padx=PAD, pady=PAD)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self._log_text = scrolledtext.ScrolledText(log_frame, state="disabled", wrap="word", height=12)
        self._log_text.grid(row=0, column=0, sticky="nsew")

    # ---- Settings -----------------------------------------------------------

    def _load_saved_settings(self) -> None:
        key = config.get_api_key()
        if key:
            self._api_key_var.set(key)
        path = config.get_journal_path()
        if path:
            self._journal_path_var.set(path)

    def _auto_detect_journal(self) -> None:
        if not self._journal_path_var.get():
            detected = journal.default_journal_dir()
            if detected:
                self._journal_path_var.set(detected)
                self._log(f"Auto-detected journal directory: {detected}")
            else:
                self._log("Could not auto-detect journal directory. Please set it manually.")
        self._refresh_cmdr_name()

    def _toggle_key_visibility(self) -> None:
        self._api_key_entry.config(show="" if self._show_key_var.get() else "*")

    def _save_api_key(self) -> None:
        key = self._api_key_var.get().strip()
        config.set_api_key(key)
        self._log("API key saved." if key else "API key cleared.")

    def _browse_journal_dir(self) -> None:
        initial = self._journal_path_var.get() or os.path.expanduser("~")
        chosen = filedialog.askdirectory(title="Select Elite Dangerous journal directory", initialdir=initial, mustexist=True)
        if chosen:
            self._journal_path_var.set(chosen)
            self._apply_journal_path()

    def _apply_journal_path(self) -> None:
        path = self._journal_path_var.get().strip()
        if not path:
            self._log("No journal path entered.")
            return
        if not os.path.isdir(path):
            self._log(f"Directory not found: {path}")
            return
        config.set_journal_path(path)
        self._log(f"Journal directory set to: {path}")
        self._refresh_cmdr_name()

    def _refresh_cmdr_name(self) -> None:
        path = self._journal_path_var.get().strip()
        latest = journal.find_latest_journal(path)
        if not latest:
            self._cmdr_name_var.set("(no journal file found)")
            return
        name = journal.extract_cmdr_name(latest)
        if name:
            self._cmdr_name = name
            self._cmdr_name_var.set(name)
            self._log(f"CMDR name: {name}")
        else:
            self._cmdr_name_var.set("(name not found in journal)")

    # ---- Monitoring ---------------------------------------------------------

    def _toggle_monitoring(self) -> None:
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._stop_monitoring()
        else:
            self._start_monitoring()

    def _start_monitoring(self) -> None:
        path = self._journal_path_var.get().strip()
        latest = journal.find_latest_journal(path)
        if not latest:
            self._log("No journal file found. Check the journal directory.")
            return

        api_key = self._api_key_var.get().strip()
        if not api_key:
            self._log("No API key configured. Please enter and save your API key first.")
            return

        self._log(f"Starting monitoring: {os.path.basename(latest)}")
        self._tailer = journal.JournalTailer(latest)
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(self._tailer, api_key),
            daemon=True,
        )
        self._monitor_thread.start()
        self._monitor_btn.config(text="Stop Monitoring")
        self._status_var.set(STATUS_MONITORING)

    def _stop_monitoring(self) -> None:
        if self._tailer:
            self._tailer.stop()
            self._tailer = None
        self._monitor_btn.config(text="Start Monitoring")
        self._status_var.set(STATUS_IDLE)
        self._log("Monitoring stopped.")

    def _monitor_loop(self, tailer: journal.JournalTailer, api_key: str) -> None:
        """Background thread: tail journal, filter to tracked events, send to API."""
        for event in tailer.read_new_events():
            event_type = event.get("event", "")

            # Update CMDR name from journal events
            if event_type == "Commander":
                name = event.get("Name", "")
                if name:
                    self._cmdr_name = name
                    self._msg_queue.put(("cmdr", name))
            elif event_type == "LoadGame":
                name = event.get("Commander", "")
                if name:
                    self._cmdr_name = name
                    self._msg_queue.put(("cmdr", name))

            # Only send events the API cares about
            if not api.is_tracked_event(event):
                continue

            cmdr = self._cmdr_name or "Unknown"
            self._msg_queue.put(("log", f"Sending: {event_type}"))

            try:
                result = api.send_journal_entry(event, cmdr, api_key)
                processed = result.get('processed', '?')
                self._msg_queue.put(("log", f"  → OK (processed: {processed})"))
            except api.ApiError as exc:
                self._msg_queue.put(("log", f"  → API error: {exc}"))
            except requests.RequestException as exc:
                msg = str(exc)
                if 'PermissionError' in msg or 'Permission denied' in msg:
                    self._msg_queue.put(("log", f"  → Connection blocked (firewall/antivirus). Allow this app through Windows Firewall."))
                else:
                    self._msg_queue.put(("log", f"  → Network error: {exc}"))
            except Exception as exc:
                self._msg_queue.put(("log", f"  → Unexpected error: {type(exc).__name__}: {exc}"))

        self._msg_queue.put(("status", STATUS_IDLE))

    # ---- Queue processing ---------------------------------------------------

    def _process_queue(self) -> None:
        try:
            while True:
                kind, value = self._msg_queue.get_nowait()
                if kind == "log":
                    self._log(value)
                elif kind == "status":
                    self._status_var.set(value)
                elif kind == "cmdr":
                    self._cmdr_name_var.set(value)
        except queue.Empty:
            pass
        finally:
            self.after(200, self._process_queue)

    # ---- Log ----------------------------------------------------------------

    def _log(self, message: str) -> None:
        self._log_text.config(state="normal")
        self._log_text.insert("end", message + "\n")
        lines = int(self._log_text.index("end-1c").split(".")[0])
        if lines > LOG_MAX_LINES:
            self._log_text.delete("1.0", f"{lines - LOG_MAX_LINES}.0")
        self._log_text.see("end")
        self._log_text.config(state="disabled")


def run() -> None:
    app = App()
    app.mainloop()

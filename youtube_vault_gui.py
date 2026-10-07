"""Interfaz gráfica local para ejecutar flujos autorizados de YouTube Vault.

No sustituye las obligaciones de derechos de autor, privacidad ni los Términos
de Servicio de las plataformas. Procesa únicamente contenido autorizado.
"""
from __future__ import annotations

import copy
import queue
import sys
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

import youtube_vault as vault


class QueueWriter:
    """Envía la salida del worker al hilo de interfaz sin bloquearlo."""

    def __init__(self, events: queue.Queue[tuple[str, str]]) -> None:
        self.events = events

    def write(self, text: str) -> int:
        if text:
            self.events.put(("log", text))
        return len(text)

    def flush(self) -> None:
        return None


class VaultApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("YouTube Vault · Archivo autorizado")
        self.geometry("940x700")
        self.minsize(760, 560)
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.running = False

        base_cfg = vault.load_config()
        self.url = tk.StringVar()
        self.mode = tk.StringVar(value=str(base_cfg["download"].get("mode", "video")))
        self.model = tk.StringVar(value=str(base_cfg["transcription"].get("model", "medium")))
        self.language = tk.StringVar(value=str(base_cfg["transcription"].get("language", "auto")))
        self.download = tk.BooleanVar(value=True)
        self.transcript = tk.BooleanVar(value=True)
        self.comments = tk.BooleanVar(value=bool(base_cfg["comments"].get("enabled", True)))
        self.analytics = tk.BooleanVar(value=bool(base_cfg["analytics"].get("sentiment", True)))

        self._build()
        self.after(100, self._drain_events)

    def _build(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Hint.TLabel", foreground="#536471")

        outer = ttk.Frame(self, padding=18)
        outer.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        ttk.Label(outer, text="YouTube Vault", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(outer, text="Procesamiento local de contenido autorizado", style="Hint.TLabel").grid(
            row=1, column=0, sticky="w", pady=(0, 14))

        form = ttk.LabelFrame(outer, text="Nueva ejecución", padding=14)
        form.grid(row=2, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="URL o ID del vídeo").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.url_entry = ttk.Entry(form, textvariable=self.url)
        self.url_entry.grid(row=0, column=1, columnspan=5, sticky="ew")

        ttk.Label(form, text="Descarga").grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Combobox(form, textvariable=self.mode, state="readonly", width=14,
                     values=("video", "video_hq", "audio", "audio_mp3", "subs_only")).grid(
                         row=1, column=1, sticky="w", pady=(12, 0))
        ttk.Label(form, text="Modelo Whisper").grid(row=1, column=2, sticky="w", padx=(18, 8), pady=(12, 0))
        ttk.Combobox(form, textvariable=self.model, state="readonly", width=12,
                     values=("base", "small", "medium", "large-v3")).grid(row=1, column=3, sticky="w", pady=(12, 0))
        ttk.Label(form, text="Idioma").grid(row=1, column=4, sticky="w", padx=(18, 8), pady=(12, 0))
        ttk.Combobox(form, textvariable=self.language, state="readonly", width=8,
                     values=("auto", "es", "en", "pt", "fr")).grid(row=1, column=5, sticky="w", pady=(12, 0))

        opts = ttk.Frame(form)
        opts.grid(row=2, column=0, columnspan=6, sticky="w", pady=(14, 0))
        for text, variable in (("Descargar medio", self.download), ("Transcribir", self.transcript),
                               ("Comentarios", self.comments), ("Analytics", self.analytics)):
            ttk.Checkbutton(opts, text=text, variable=variable).pack(side="left", padx=(0, 18))
        self.run_button = ttk.Button(form, text="Procesar", command=self.start)
        self.run_button.grid(row=3, column=5, sticky="e", pady=(14, 0))

        log_frame = ttk.LabelFrame(outer, text="Actividad", padding=8)
        log_frame.grid(row=3, column=0, sticky="nsew", pady=(16, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log = tk.Text(log_frame, wrap="word", state="disabled", background="#101820", foreground="#e7eef5",
                           insertbackground="#ffffff", font=("Cascadia Mono", 10))
        bar = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=bar.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        bar.grid(row=0, column=1, sticky="ns")
        self._append("Listo. Selecciona contenido que tengas derecho a procesar.\n")

    def _append(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drain_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self._append(value)
                elif kind == "done":
                    self.running = False
                    self.run_button.configure(state="normal")
                    self._append(f"\n✓ Terminado. Bundle: {value}\n")
                    messagebox.showinfo("YouTube Vault", f"Proceso terminado.\n\nSalida:\n{value}")
                elif kind == "error":
                    self.running = False
                    self.run_button.configure(state="normal")
                    self._append(f"\n✗ Error:\n{value}\n")
                    messagebox.showerror("YouTube Vault", "La ejecución terminó con un error. Revisa el registro.")
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def start(self) -> None:
        if self.running:
            return
        target = self.url.get().strip()
        if not vault.extract_video_id(target):
            messagebox.showwarning("URL inválida", "Introduce una URL de YouTube o un ID de vídeo válido.")
            return
        if not any((self.download.get(), self.transcript.get(), self.comments.get())):
            messagebox.showwarning("Sin tareas", "Selecciona al menos una tarea para procesar.")
            return
        self.running = True
        self.run_button.configure(state="disabled")
        self._append("\n— Iniciando ejecución —\n")
        threading.Thread(target=self._run, args=(target,), daemon=True).start()

    def _run(self, target: str) -> None:
        cfg: dict[str, Any] = copy.deepcopy(vault.load_config())
        cfg["download"]["mode"] = self.mode.get()
        cfg["transcription"].update({"model": self.model.get(), "language": self.language.get(),
                                      "prefer_whisper": True})
        cfg["comments"]["enabled"] = self.comments.get()
        previous_out, previous_err = sys.stdout, sys.stderr
        writer = QueueWriter(self.events)
        try:
            sys.stdout = writer
            sys.stderr = writer
            session = vault.create_session(use_tor=bool(cfg["youtube"].get("use_tor")))
            result = vault.process_video(target, cfg, session, do_download=self.download.get(),
                                         do_transcript=self.transcript.get(), do_comments=self.comments.get(),
                                         do_analytics=self.analytics.get())
            self.events.put(("done", str(result.get("dir", ""))))
        except Exception:
            self.events.put(("error", traceback.format_exc()))
        finally:
            sys.stdout, sys.stderr = previous_out, previous_err


if __name__ == "__main__":
    VaultApp().mainloop()

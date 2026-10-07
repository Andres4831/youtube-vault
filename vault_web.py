"""Panel web local para YouTube Vault.

La aplicación escucha exclusivamente en 127.0.0.1. Úsala únicamente para
contenido que tengas derecho a procesar y respetando los términos aplicables.
"""
from __future__ import annotations

import copy
import threading
import uuid
import webbrowser
from datetime import datetime, timezone
from typing import Any

from flask import Flask, jsonify, render_template, request

import youtube_vault as vault

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def update_job(job_id: str, **values: Any) -> None:
    with JOBS_LOCK:
        JOBS.setdefault(job_id, {}).update(values)


def public_job(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = dict(JOBS.get(job_id) or {"state": "unknown", "message": "Trabajo no encontrado."})
    job.pop("result", None)
    return job


def run_job(job_id: str, payload: dict[str, Any]) -> None:
    cfg = copy.deepcopy(vault.load_config())
    cfg["download"]["mode"] = payload.get("mode", "video")
    cfg["transcription"].update({
        "model": payload.get("model", "medium"),
        "language": payload.get("language", "auto"),
        "prefer_whisper": payload.get("transcript_engine", "whisper") == "whisper",
    })
    cfg["comments"]["enabled"] = bool(payload.get("comments", True))

    def report(event: dict[str, Any]) -> None:
        update_job(job_id, state="running", updated_at=datetime.now(timezone.utc).isoformat(), **event)

    try:
        update_job(job_id, state="running", stage="metadata", progress=2, message="Preparando proceso…")
        session = vault.create_session(use_tor=bool(cfg["youtube"].get("use_tor")))
        result = vault.process_video(
            payload["url"], cfg, session,
            do_download=bool(payload.get("download", True)),
            do_transcript=bool(payload.get("transcript", True)),
            do_comments=bool(payload.get("comments", True)),
            do_analytics=bool(payload.get("analytics", True)),
            on_status=report,
        )
        update_job(job_id, state="done", stage="complete", progress=100,
                   message="Proceso terminado y verificado.", output_dir=result.get("dir"),
                   title=(result.get("meta") or {}).get("title"), completed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        update_job(job_id, state="error", progress=0, message=str(exc), stage="error",
                   completed_at=datetime.now(timezone.utc).isoformat())


@app.get("/")
def index() -> str:
    return render_template("vault_web.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "ffmpeg": vault.ffmpeg_ok(), "version": vault.VERSION})


@app.post("/api/analyze")
def analyze():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url") or "").strip()
    if not vault.extract_video_id(url):
        return jsonify(ok=False, error="Introduce una URL o ID de vídeo válido."), 400
    try:
        cfg = copy.deepcopy(vault.load_config())
        session = vault.create_session(use_tor=bool(cfg["youtube"].get("use_tor")))
        meta = vault.extract_metadata(url, cfg, session)
        formats = []
        for item in meta.get("formats") or []:
            if not item.get("format_id") or not item.get("height"):
                continue
            formats.append({"id": str(item["format_id"]), "height": item.get("height"),
                            "fps": item.get("fps"), "ext": item.get("ext"),
                            "has_audio": item.get("acodec") not in (None, "none")})
        formats.sort(key=lambda value: (value["height"] or 0, bool(value["has_audio"])), reverse=True)
        return jsonify(ok=True, title=meta.get("title"), channel=meta.get("channel"),
                       duration=meta.get("duration"), thumbnail=meta.get("thumbnail"), formats=formats[:20])
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 400


@app.post("/api/jobs")
def start_job():
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url") or "").strip()
    if not vault.extract_video_id(url):
        return jsonify(ok=False, error="Introduce una URL o ID de vídeo válido."), 400
    if not any(bool(payload.get(key, True)) for key in ("download", "transcript", "comments")):
        return jsonify(ok=False, error="Selecciona al menos una tarea."), 400
    job_id = uuid.uuid4().hex
    update_job(job_id, state="queued", stage="queued", progress=0, message="En cola…",
               created_at=datetime.now(timezone.utc).isoformat())
    threading.Thread(target=run_job, args=(job_id, {**payload, "url": url}), daemon=True).start()
    return jsonify(ok=True, job_id=job_id)


@app.get("/api/jobs/<job_id>")
def job_status(job_id: str):
    return jsonify(public_job(job_id))


if __name__ == "__main__":
    threading.Timer(0.5, lambda: webbrowser.open("http://127.0.0.1:8765")).start()
    app.run(host="127.0.0.1", port=8765, debug=False, use_reloader=False)

#!/usr/bin/env python3
"""
YOUTUBE VAULT v3.3 — MODULAR (consolidado + estructura organizada)
==================================================================
Script modular para descarga + transcripción + comentarios + analytics de YouTube.
Cada sección está aislada para editar sin romper el resto.

AVISO DE USO RESPONSABLE:
  Usa esta herramienta únicamente con contenido propio, contenido con autorización
  expresa o material que pueda descargarse y procesarse legalmente. El usuario es
  responsable de cumplir los Términos de Servicio de YouTube, la legislación
  aplicable, los derechos de autor y la privacidad. No uses cookies, proxies, Tor
  ni automatización para evadir controles de acceso, CAPTCHA u otras medidas.

ESTRUCTURA:
  [S0]   Imports y configuración global
  [S1]   Consola (colores, prints)
  [S2]   Tor Manager (rotación de IP)
  [S3]   Fingerprint / User-Agent rotativo
  [S4]   Humanizer (curva circadiana, fatiga, pausas)
  [S5]   Anti-captcha (Chromium + cookies + JS off + reload)
  [S6]   Metadata (yt-dlp + InnerTube fallback + análisis de formatos)
  [S7]   Descarga de video (4K/Full HD, reusa client que funcionó)
  [S8]   Transcripción (Whisper + subs YouTube)
  [S9]   Comentarios (multi-pasada con rotación)
  [S10]  Analytics (sentiment, topics, grafo, heatmap)
  [S11]  Empaquetado (TXT/JSON/CSV/HTML/ZIP)
  [S12a] Utilidades (config, output dir, power, tor panel)
  [S13]  Auto-Repair System (autoreparación universal)
  [S14]  Menús avanzados (presets, paneles)
  [S12b] Pipeline principal + main()

ESTRUCTURA DE SALIDA:
  salidas/{id}_{slug}/
  ├── LEEME.txt
  ├── metadata/metadata.json
  ├── video/{id}.mkv + audio.m4a + audio.mp3
  ├── subtitles/transcription.{srt,vtt,txt,json,md}
  ├── comments/comments.{json,csv,md,html}
  ├── analytics/analytics.json + sentiment_report.json + analytics_report.html
  └── images/thumbnail.jpg + waveform.png + storyboard.jpg + author_graph.svg + heatmap

CAMBIOS v3.3:
  * Salida organizada en subcarpetas (metadata/, video/, subtitles/, comments/, analytics/, images/)
  * Helper _subdir() centraliza la creación de subcarpetas
  * Menús 4 y 7 buscan archivos en las nuevas rutas (con fallback a la raíz)
  * LEEME.txt describe la estructura completa

REQUISITOS:
    pip install yt-dlp requests urllib3 tenacity pyyaml stem pysocks
    pip install faster-whisper youtube-transcript-api pytubefix
    pip install playwright && playwright install chromium
    # Opcionales:
    pip install pysentimiento detoxify bertopic networkx python-louvain
    pip install matplotlib mutagen browser-cookie3
    # ffmpeg en PATH

TOR EXPERT BUNDLE:
    SocksPort 9050 IsolateSOCKSAuth
    ControlPort 9051
    tor.exe -f torrc

USO: python youtube_vault.py
"""
from __future__ import annotations

# ============================================================
# [S0] IMPORTS Y CONFIGURACIÓN GLOBAL
# ============================================================
import base64, csv, hashlib, html as html_lib, json, logging, os
import random, re, shutil, socket, subprocess, sys, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional
from urllib.parse import parse_qs, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Dependencias opcionales
try:
    import yaml; YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    from stem import Signal
    from stem.control import Controller
    from stem.connection import AuthenticationFailure, MissingPasswordError
    STEM_AVAILABLE = True
except ImportError:
    STEM_AVAILABLE = False
    Signal = None; Controller = None

try:
    import socks; SOCKS_AVAILABLE = True
except ImportError:
    SOCKS_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None; PWTimeout = Exception

try:
    import yt_dlp; YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

try:
    from pytubefix import YouTube as PytubeYouTube; PYTUBEFIX_AVAILABLE = True
except ImportError:
    PYTUBEFIX_AVAILABLE = False; PytubeYouTube = None

try:
    from youtube_transcript_api import YouTubeTranscriptApi; TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    TRANSCRIPT_API_AVAILABLE = False; YouTubeTranscriptApi = None

try:
    from youtube_comment_downloader import YoutubeCommentDownloader, SORT_BY_POPULAR, SORT_BY_RECENT
    COMMENT_DL_AVAILABLE = True
except ImportError:
    COMMENT_DL_AVAILABLE = False; YoutubeCommentDownloader = None
    SORT_BY_POPULAR = 0; SORT_BY_RECENT = 1

try:
    from faster_whisper import WhisperModel; WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False; WhisperModel = None

try:
    from bs4 import BeautifulSoup; BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False; BeautifulSoup = None

try:
    import mutagen
    from mutagen.id3 import ID3, APIC, TIT2, TPE1
    from mutagen.mp4 import MP4, MP4Cover
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

try:
    import browser_cookie3; COOKIES_AVAILABLE = True
except ImportError:
    COOKIES_AVAILABLE = False; browser_cookie3 = None

try:
    import networkx as nx; NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False; nx = None

try:
    import community as community_louvain; LOUVAIN_AVAILABLE = True
except ImportError:
    LOUVAIN_AVAILABLE = False; community_louvain = None

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MPL_AVAILABLE = True
except ImportError:
    MPL_AVAILABLE = False; plt = None

try:
    from pysentimiento import create_analyzer as create_sent_analyzer
    PYSENT_AVAILABLE = True
except ImportError:
    PYSENT_AVAILABLE = False; create_sent_analyzer = None


# --- Constantes globales ---
VERSION = "3.3-MODULAR"
LOG_FILE = "youtube_vault.log"
CONFIG_PATH = Path("config.yaml")
CACHE_DIR = Path("cache")
POT_CACHE = CACHE_DIR / "po_tokens.json"
DEFAULT_OUTPUT = Path("salidas")

INNERTUBE_API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
INNERTUBE_WEB_VERSION = "2.20240620.00.00"
INNERTUBE_ANDROID_VERSION = "19.29.37"
INNERTUBE_IOS_VERSION = "19.29.1"
POT_PROVIDER_URL = "http://127.0.0.1:4416"
POT_TTL_SECONDS = 6 * 3600
MAX_COMMENT_PAGES = 500
VOLUME_THRESHOLD = 30

PLAYER_CLIENTS_4K = ["web_safari", "tv_embedded", "web", "mweb"]
PLAYER_CLIENTS_MOBILE = ["android", "ios"]
PLAYER_CLIENTS = PLAYER_CLIENTS_4K + PLAYER_CLIENTS_MOBILE

METADATA_FIELDS = [
    "id", "title", "description", "upload_date", "duration", "view_count",
    "like_count", "comment_count", "channel", "channel_id", "uploader_id",
    "categories", "tags", "chapters", "heatmap", "language", "age_limit",
    "is_live", "was_live", "availability", "thumbnail", "thumbnails",
    "subtitles", "automatic_captions", "webpage_url", "formats",
]

YOUTUBE_BOT_MARKERS = [
    "sign in to confirm you're not a bot", "sign in to confirm you",
    "this video is not available in your country", "video unavailable",
    "http error 403", "premieres in", "po_token", "sabr", "confirm your age",
    "captcha", "recaptcha", "cf-challenge", "verify you are human", "unusual traffic",
]

# --- Estado global editable ---
TOR_SOCKS_HOST = "127.0.0.1"
TOR_SOCKS_PORT = 9050
TOR_CONTROL_PORT = 9051
TOR_CONTROL_PASSWORD: Optional[str] = None

HUMANIZATION_MODE = "equilibrado"   # rapida | equilibrado | pausada | nocturna
HUMANIZATION_LEVEL = "medio"        # bajo | medio | alto | paranoico

VOLUME_PROFILE: dict[str, float] = {
    "total_ops": 0, "volume_factor": 0.0, "duration_boost": 1.0,
    "pause_boost": 1.0, "density_factor": 1.0, "rotate_boost": 1.0,
    "extra_hit_chance": 0.30,
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

ACCEPT_LANGUAGES = [
    "es-ES,es;q=0.9,en;q=0.8", "es-MX,es;q=0.9,en;q=0.8",
    "es-AR,es;q=0.9,en;q=0.7", "en-US,en;q=0.9,es;q=0.7",
]

BROWSER_FINGERPRINT_PROFILES: list[dict] = [
    {
        "ua": USER_AGENTS[0], "locale": "es-ES",
        "languages": ["es-ES", "es", "en-US", "en"],
        "platform": "Win32", "viewport": {"width": 1366, "height": 768},
        "timezone_id": "Europe/Madrid",
        "sec_ch_ua": '"Chromium";v="124", "Not(A:Brand";v="24", "Google Chrome";v="124"',
        "sec_ch_ua_mobile": "?0", "sec_ch_ua_platform": '"Windows"',
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "hardware_concurrency": 8, "device_memory": 8,
    },
    {
        "ua": USER_AGENTS[1], "locale": "es-MX",
        "languages": ["es-MX", "es", "en-US", "en"],
        "platform": "Win32", "viewport": {"width": 1536, "height": 864},
        "timezone_id": "America/Mexico_City",
        "sec_ch_ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "sec_ch_ua_mobile": "?0", "sec_ch_ua_platform": '"Windows"',
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "hardware_concurrency": 4, "device_memory": 8,
    },
    {
        "ua": USER_AGENTS[2], "locale": "es-ES",
        "languages": ["es-ES", "es", "en"],
        "platform": "MacIntel", "viewport": {"width": 1440, "height": 900},
        "timezone_id": "Europe/Madrid",
        "sec_ch_ua": '"Chromium";v="124", "Not(A:Brand";v="24", "Google Chrome";v="124"',
        "sec_ch_ua_mobile": "?0", "sec_ch_ua_platform": '"macOS"',
        "webgl_vendor": "Google Inc. (Apple)",
        "webgl_renderer": "ANGLE (Apple, Apple M1, OpenGL 4.1)",
        "hardware_concurrency": 8, "device_memory": 8,
    },
    {
        "ua": USER_AGENTS[3], "locale": "en-US",
        "languages": ["en-US", "en"],
        "platform": "Linux x86_64", "viewport": {"width": 1280, "height": 800},
        "timezone_id": "UTC",
        "sec_ch_ua": '"Chromium";v="124", "Not(A:Brand";v="24", "Google Chrome";v="124"',
        "sec_ch_ua_mobile": "?0", "sec_ch_ua_platform": '"Linux"',
        "webgl_vendor": "Google Inc. (Mesa)",
        "webgl_renderer": "Mesa Intel(R) UHD Graphics 620 (CML GT2)",
        "hardware_concurrency": 4, "device_memory": 4,
    },
]

DEFAULT_CONFIG: dict[str, Any] = {
    "youtube": {
        "use_tor": False, "paranoid_mode": False,
        "rotate_every_pages": 10, "rotate_ua_every_pages": 3,
        "player_clients": list(PLAYER_CLIENTS[:4]),
        "use_cookies": False, "cookies_browser": "firefox",
    },
    "download": {
        "mode": "video", "quality": 2160, "prefer_max_quality": True,
        "container_preference": "mkv", "limit_rate": "0",
        "sleep_requests": 3, "sleep_interval": 5, "concurrent_fragments": 5,
    },
    "transcription": {
        "engine": "faster-whisper", "model": "medium", "language": "auto",
        "vad": True, "word_timestamps": True, "prefer_whisper": False,
    },
    "comments": {
        "enabled": True, "sort": "top", "max_comments": 5000,
        "max_replies_per_thread": 50, "include_replies": True,
        "passes": 1, "delay_between_passes_sec": [60, 180],
        "rotate_on_pass": True, "shadow_throttle_detection": True,
    },
    "analytics": {
        "sentiment": True, "topics": False, "toxicity": False,
        "social_graph": True, "heatmap": True,
    },
    "humanization": {
        "mode": "equilibrado", "level": "medio",
        "circadian": True, "fatigue": True,
        "micro_breaks": True, "macro_breaks": True,
        "sleep_schedule": False,
    },
    "anonymous_browser": {
        "enabled": True, "headless": True, "use_tor": True,
        "canvas_noise": True, "webgl_spoof": True, "webrtc_block": True,
    },
    "tor": {
        "socks_host": "127.0.0.1", "socks_port": 9050, "control_port": 9051,
        "control_password": None, "stream_isolation": True,
        "verify_new_identity": True, "circuit_max_age_seconds": 600,
    },
    "output": {"dir": "salidas"},
}

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")


# ============================================================
# [S1] CONSOLA — colores y helpers de impresión
# ============================================================

def _supports_color() -> bool:
    if sys.platform == "win32" and "idlelib" in sys.modules:
        return False
    try:
        if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
            return False
    except Exception:
        return False
    return not os.environ.get("NO_COLOR")


class Color:
    _on = False
    GREEN = RED = YELLOW = CYAN = MAGENTA = BLUE = BOLD = DIM = RESET = ""


def _init_color() -> None:
    on = _supports_color()
    Color._on = on
    Color.GREEN = "\033[92m" if on else ""
    Color.RED = "\033[91m" if on else ""
    Color.YELLOW = "\033[93m" if on else ""
    Color.CYAN = "\033[96m" if on else ""
    Color.MAGENTA = "\033[95m" if on else ""
    Color.BLUE = "\033[94m" if on else ""
    Color.BOLD = "\033[1m" if on else ""
    Color.DIM = "\033[2m" if on else ""
    Color.RESET = "\033[0m" if on else ""

_init_color()


def banner() -> None:
    line = "=" * 62
    print(f"\n{line}\n  YOUTUBE VAULT  v{VERSION}\n"
          f"  Tor · Chromium stealth · Humanización · 4K\n{line}\n")


def console_section(t: str) -> None:
    print(f"\n{'-'*62}\n  {t}\n{'-'*62}")


def console_kv(k: str, v: Any, color: str = "") -> None:
    c = color or Color.GREEN
    print(f"  {c}{str(k):<24}{Color.RESET} {v}")


def console_ok(m: str) -> None: print(f"  {Color.GREEN}[OK]{Color.RESET} {m}")
def console_fail(m: str) -> None: print(f"  {Color.RED}[ERROR]{Color.RESET} {m}")
def console_info(m: str) -> None: print(f"  {Color.CYAN}[i]{Color.RESET} {m}")
def console_warn(m: str) -> None: print(f"  {Color.YELLOW}[!]{Color.RESET} {m}")
def console_tor(m: str) -> None: print(f"  {Color.MAGENTA}[TOR]{Color.RESET} {m}")
def console_human(m: str) -> None: print(f"  {Color.BLUE}[HUM]{Color.RESET} {m}")
def live_status(m: str) -> None: print(f"  {Color.CYAN}→ {m}{Color.RESET}", flush=True)


def live_wait(seconds: float, label: str = "espera") -> None:
    end = time.monotonic() + max(0.0, seconds)
    last = 0.0
    while time.monotonic() < end:
        left = end - time.monotonic()
        if time.monotonic() - last >= 10 and left > 8:
            live_status(f"{label}: ~{left:.0f}s restantes")
            last = time.monotonic()
        time.sleep(min(2.0, max(0.2, left)))


def progress(current: int, total: int, label: str = "") -> None:
    total = max(1, int(total))
    pct = min(100, int(100 * current / total))
    bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
    print(f"  [{bar}] {pct:3d}%  {current}/{total} {label}", flush=True)


# ============================================================
# [S2] TOR MANAGER — rotación de IP (editable aislado)
# ============================================================

class TorManager:
    """Rotación verificada de IP con stream isolation y cierre de circuitos."""

    def __init__(self, socks_host: str = TOR_SOCKS_HOST, socks_port: int = TOR_SOCKS_PORT,
                 control_port: int = TOR_CONTROL_PORT, password: Optional[str] = TOR_CONTROL_PASSWORD):
        self.socks_host = socks_host
        self.socks_port = socks_port
        self.control_port = control_port
        self.password = password
        self._controller: Optional[Any] = None
        self._last_ip: Optional[str] = None
        self._last_rotate: float = 0.0
        self._circuit_stream_id: Optional[str] = None

    def is_socks_alive(self, timeout: float = 1.5) -> bool:
        try:
            with socket.create_connection((self.socks_host, self.socks_port), timeout=timeout):
                return True
        except OSError:
            return False

    def is_control_alive(self, timeout: float = 1.5) -> bool:
        try:
            with socket.create_connection((self.socks_host, self.control_port), timeout=timeout):
                return True
        except OSError:
            return False

    def available(self) -> bool:
        return self.is_socks_alive() and STEM_AVAILABLE

    def _connect(self) -> Optional[Any]:
        if not STEM_AVAILABLE:
            return None
        if self._controller is not None:
            return self._controller
        try:
            ctrl = Controller.from_port(port=self.control_port)
            try:
                if self.password:
                    ctrl.authenticate(password=self.password)
                else:
                    ctrl.authenticate()
            except (AuthenticationFailure, MissingPasswordError):
                ctrl.authenticate()
            self._controller = ctrl
            return ctrl
        except Exception as exc:
            logging.debug("Tor controller: %s", exc)
            self._controller = None
            return None

    def close(self) -> None:
        try:
            if self._controller is not None:
                self._controller.close()
        except Exception:
            pass
        self._controller = None

    def list_circuits(self) -> list:
        ctrl = self._connect()
        if not ctrl:
            return []
        try:
            return list(ctrl.get_circuits())
        except Exception:
            return []

    def close_old_circuits(self) -> int:
        ctrl = self._connect()
        if not ctrl:
            return 0
        closed = 0
        try:
            for c in list(ctrl.get_circuits()):
                if c.status in {"BUILT", "EXTENDED", "GUARD_WAIT", "FAILED", "CLOSED"}:
                    try:
                        ctrl.close_circuit(c.id)
                        closed += 1
                    except Exception:
                        pass
        except Exception:
            pass
        return closed

    def new_identity(self, session: Optional[requests.Session] = None,
                     aggressive: bool = False, max_attempts: int = 3) -> bool:
        """NEWNYM verificada: comprueba que la IP de salida realmente cambió."""
        ctrl = self._connect()
        if not ctrl:
            console_tor("ControlPort no disponible")
            return False
        console_tor(f"Nueva identidad (máx {max_attempts} intentos)…")
        for attempt in range(1, max_attempts + 1):
            try:
                self.close_old_circuits()
                ctrl.signal(Signal.NEWNYM)
                if aggressive:
                    time.sleep(random.uniform(2.0, 4.0))
                    ctrl.signal(Signal.NEWNYM)
                self._wait_for_built_circuit(min_circuits=1, timeout=25.0)
                if session is not None:
                    new_ip = self._probe_ip(session)
                    if new_ip and new_ip != self._last_ip:
                        self._last_ip = new_ip
                        self._last_rotate = time.time()
                        console_tor(f"IP nueva: {new_ip} (intento {attempt})")
                        return True
                    elif new_ip:
                        console_tor(f"IP no cambió ({new_ip}); reintento…")
                        time.sleep(random.uniform(3.0, 6.0))
                        continue
                    else:
                        self._last_rotate = time.time()
                        return True
                else:
                    self._last_rotate = time.time()
                    return True
            except Exception as exc:
                logging.warning("new_identity intento %s: %s", attempt, exc)
                time.sleep(random.uniform(2.0, 5.0))
        return False

    def _wait_for_built_circuit(self, min_circuits: int = 1, timeout: float = 25.0) -> None:
        ctrl = self._connect()
        if not ctrl:
            time.sleep(random.uniform(8.0, 14.0))
            return
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                built = sum(1 for c in ctrl.get_circuits()
                            if c.status in {"BUILT", "EXTENDED"})
                if built >= min_circuits:
                    time.sleep(random.uniform(1.2, 2.8))
                    return
            except Exception:
                pass
            time.sleep(1.5)

    def _probe_ip(self, session: requests.Session) -> Optional[str]:
        for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
            try:
                r = session.get(url, timeout=18)
                if r.status_code == 200 and r.text.strip():
                    return r.text.strip()
            except Exception:
                continue
        return None

    def stream_isolation_proxy(self) -> str:
        """Proxy SOCKS con credenciales ficticias → Tor aísla streams (IsolateSOCKSAuth)."""
        sid = self._circuit_stream_id or hashlib.sha1(os.urandom(16)).hexdigest()[:16]
        self._circuit_stream_id = sid
        return f"socks5h://{sid}:{sid}@{self.socks_host}:{self.socks_port}"

    def reset_stream_isolation(self) -> None:
        self._circuit_stream_id = None

    def should_rotate(self, max_age_seconds: float = 600.0) -> bool:
        if self._last_rotate <= 0:
            return True
        return (time.time() - self._last_rotate) >= max_age_seconds


TOR = TorManager()


# ============================================================
# [S3] FINGERPRINT / USER-AGENT ROTATIVO
# ============================================================

def pick_fingerprint_profile() -> dict:
    """Devuelve un perfil COHERENTE (UA + TZ + WebGL + hardware)."""
    try:
        return dict(random.choice(BROWSER_FINGERPRINT_PROFILES))
    except Exception:
        return dict(BROWSER_FINGERPRINT_PROFILES[0])


def build_accept_language(langs: list[str]) -> str:
    if not langs:
        return "es-ES,es;q=0.9,en;q=0.8"
    return ",".join(langs[0] if i == 0 else f"{c};q=0.{max(1, 9 - i)}"
                   for i, c in enumerate(langs[:4]))


def rotate_user_agent(session: requests.Session) -> None:
    """Rota UA + Accept-Language + Client-Hints coherentes."""
    fp = pick_fingerprint_profile()
    session.headers["User-Agent"] = fp["ua"]
    session.headers["Accept-Language"] = build_accept_language(fp["languages"])
    session.headers["Sec-Ch-Ua"] = fp.get("sec_ch_ua", "")
    session.headers["Sec-Ch-Ua-Mobile"] = fp.get("sec_ch_ua_mobile", "?0")
    session.headers["Sec-Ch-Ua-Platform"] = fp.get("sec_ch_ua_platform", '"Windows"')
    logging.info("UA rotado: %s", fp["ua"][:60])


def create_session(use_tor: bool = False, profile: Optional[dict] = None,
                   stream_isolation: bool = True) -> requests.Session:
    """Crea sesión con headers coherentes y proxy Tor opcional."""
    session = requests.Session()
    session.headers.pop("User-Agent", None)
    retry_policy = Retry(total=2, connect=2, read=2, status=2, backoff_factor=1.0,
                         status_forcelist=(500, 502, 503, 504),
                         allowed_methods=frozenset({"GET", "POST"}),
                         respect_retry_after_header=True)
    adapter = HTTPAdapter(max_retries=retry_policy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    fp = profile or pick_fingerprint_profile()
    session.headers.update({
        "User-Agent": fp["ua"],
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": build_accept_language(fp["languages"]),
        "Accept-Encoding": "gzip, deflate, br",
        "Origin": "https://www.youtube.com",
        "Referer": "https://www.youtube.com/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin",
        "Sec-Ch-Ua": fp.get("sec_ch_ua", ""),
        "Sec-Ch-Ua-Mobile": fp.get("sec_ch_ua_mobile", "?0"),
        "Sec-Ch-Ua-Platform": fp.get("sec_ch_ua_platform", '"Windows"'),
        "X-Youtube-Client-Name": "1",
        "X-Youtube-Client-Version": INNERTUBE_WEB_VERSION,
    })
    if use_tor:
        if not TOR.available():
            console_warn(f"Tor SOCKS no responde en {TOR.socks_host}:{TOR.socks_port}")
        proxy = TOR.stream_isolation_proxy() if stream_isolation else \
                f"socks5h://{TOR.socks_host}:{TOR.socks_port}"
        session.proxies = {"http": proxy, "https": proxy}
    return session


def get_exit_ip(session: requests.Session) -> Optional[str]:
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            r = session.get(url, timeout=18)
            if r.status_code == 200 and r.text.strip():
                return r.text.strip()
        except Exception:
            continue
    return None


# ============================================================
# [S4] HUMANIZER — ritmo humano realista
# ============================================================

_HUMANIZATION_MODIFIERS: dict[str, dict[str, float]] = {
    "rapida":      {"duration_scale": 0.60, "density_scale": 1.30, "pause_scale": 0.60},
    "equilibrado": {"duration_scale": 1.00, "density_scale": 1.00, "pause_scale": 1.00},
    "pausada":     {"duration_scale": 1.60, "density_scale": 0.70, "pause_scale": 1.50},
    "nocturna":    {"duration_scale": 2.10, "density_scale": 0.55, "pause_scale": 1.90},
}


class Humanizer:
    """Curva circadiana + fatiga + micro/macro pausas + sueño simulado."""

    def __init__(self, level: str = "medio"):
        self.level = level
        self.fatigue = 0.0
        self.ops_count = 0
        self.session_start = time.time()
        self.last_micro = time.time()
        self.last_macro = time.time()
        self.last_sleep = time.time()

    def circadian_factor(self) -> float:
        """Hora local → factor 0.55–1.25 (madrugada lento, tarde rápido)."""
        h = datetime.now().hour
        if 2 <= h < 6:  return 0.55
        if 6 <= h < 9:  return 0.80
        if 9 <= h < 13: return 1.10
        if 13 <= h < 15: return 0.85
        if 15 <= h < 22: return 1.25
        if 22 <= h < 24: return 0.95
        return 0.70

    def update_fatigue(self, delta: int = 1) -> None:
        self.ops_count += delta
        self.fatigue = min(1.0, self.fatigue + 0.012 * delta)

    def recover_fatigue(self, amount: float) -> None:
        self.fatigue = max(0.0, self.fatigue - amount)

    def fatigue_factor(self) -> float:
        return 1.0 + self.fatigue * 0.8

    def maybe_micro_break(self) -> float:
        if self.level == "bajo":
            return 0.0
        elapsed = time.time() - self.last_micro
        p = min(0.30, 0.02 + 0.003 * self.ops_count)
        if elapsed > 180 and random.random() < p:
            secs = random.uniform(5.0, 30.0) * self.fatigue_factor()
            self.last_micro = time.time()
            self.recover_fatigue(0.05)
            console_human(f"Micro-pausa: {secs:.0f}s")
            time.sleep(secs)
            return secs
        return 0.0

    def maybe_macro_break(self) -> float:
        if self.level == "bajo":
            return 0.0
        elapsed = time.time() - self.last_macro
        threshold = random.uniform(1800, 5400) if self.level == "medio" else random.uniform(900, 2700)
        if elapsed > threshold and random.random() < 0.6:
            secs = random.uniform(120.0, 900.0)
            self.last_macro = time.time()
            self.recover_fatigue(0.5)
            console_human(f"Macro-pausa: {secs/60:.1f} min")
            time.sleep(secs)
            return secs
        return 0.0

    def maybe_sleep(self) -> float:
        if self.level != "paranoico":
            return 0.0
        elapsed = time.time() - self.last_sleep
        if elapsed > random.uniform(16 * 3600, 20 * 3600):
            secs = random.uniform(4 * 3600, 8 * 3600)
            self.last_sleep = time.time()
            console_human(f"Sueño simulado: {secs/3600:.1f} h")
            try:
                time.sleep(secs)
            except KeyboardInterrupt:
                console_human("Sueño cancelado")
            return secs
        return 0.0

    def think_pause(self, base: float = 2.0) -> float:
        secs = random.uniform(base * 0.4, base * 2.5)
        secs *= self.circadian_factor() * self.fatigue_factor()
        time.sleep(secs)
        return secs

    def between_ops(self) -> None:
        self.update_fatigue(1)
        self.maybe_micro_break()
        self.maybe_macro_break()
        self.maybe_sleep()
        time.sleep(random.uniform(0.4, 1.8) * self.fatigue_factor())


HUMAN = Humanizer(level="medio")


def compute_volume_profile(total_ops: int, use_tor: bool = False) -> dict:
    """Más ops → pausas más largas (anti-ráfaga, patrón Wattpad)."""
    n = max(0, int(total_ops or 0))
    if n < VOLUME_THRESHOLD:
        factor = 0.0
    else:
        factor = min(1.15, ((n - VOLUME_THRESHOLD) / 70.0) ** 0.85)
    exposure = 1.0 + (0.12 if use_tor else 0.0)
    factor = min(1.25, factor * exposure)
    return {
        "total_ops": n, "volume_factor": round(factor, 3),
        "duration_boost": round(1.0 + factor * 0.85, 3),
        "pause_boost": round(1.0 + factor * 1.10, 3),
        "density_factor": round(max(0.55, 1.0 - factor * 0.40), 3),
        "rotate_boost": round(1.0 + factor * 0.70, 3),
        "extra_hit_chance": round(max(0.12, 0.30 - factor * 0.15), 3),
    }


def apply_volume_profile(profile: dict) -> None:
    global VOLUME_PROFILE
    VOLUME_PROFILE = dict(profile)


def inter_operation_delay(tor_active: bool = False) -> float:
    mod = _HUMANIZATION_MODIFIERS.get(HUMANIZATION_MODE, _HUMANIZATION_MODIFIERS["equilibrado"])
    boost = float(VOLUME_PROFILE.get("pause_boost") or 1.0)
    lo, hi = (5.5, 13.0) if tor_active else (3.0, 8.5)
    lo *= mod["pause_scale"] * boost
    hi *= mod["pause_scale"] * boost
    span = max(0.5, hi - lo)
    raw = lo + span * random.lognormvariate(0.0, 0.35) / (1.0 + random.lognormvariate(0.0, 0.35))
    return round(max(lo, min(hi, raw)), 3)


def inter_read_delay(tor_active: bool = False) -> float:
    mod = _HUMANIZATION_MODIFIERS.get(HUMANIZATION_MODE, _HUMANIZATION_MODIFIERS["equilibrado"])
    boost = float(VOLUME_PROFILE.get("pause_boost") or 1.0)
    lo, hi = (7.0, 16.0) if tor_active else (4.5, 11.0)
    lo *= mod["pause_scale"] * boost
    hi *= mod["pause_scale"] * boost
    span = max(0.5, hi - lo)
    raw = lo + span * random.betavariate(2.0, 2.5)
    return round(max(lo, min(hi, raw)), 3)


# ============================================================
# [S5] ANTI-CAPTCHA — Chromium stealth + cookie clear + JS off + reload
# ============================================================

def progressive_error_penalty(strikes: int, base: float = 8.0) -> float:
    """Penalización exponencial + jitter + factor circadiano/fatiga."""
    n = max(1, int(strikes))
    factor = min(12.0, 1.6 ** (n - 1))
    wait = base * factor + random.uniform(2.0, 8.0) * n
    wait *= HUMAN.fatigue_factor() * (1.0 / max(0.5, HUMAN.circadian_factor()))
    return round(min(300.0, wait), 2)


def apply_error_slowdown(strikes: int) -> None:
    """Degrada el modo de humanización si hay muchos strikes."""
    global HUMANIZATION_MODE, VOLUME_PROFILE
    if strikes <= 1:
        return
    prof = dict(VOLUME_PROFILE)
    prof["pause_boost"] = round(min(2.8, float(prof.get("pause_boost") or 1.0) * (1.0 + 0.25 * strikes)), 3)
    prof["duration_boost"] = round(min(2.4, float(prof.get("duration_boost") or 1.0) * (1.0 + 0.18 * strikes)), 3)
    prof["density_factor"] = round(max(0.45, float(prof.get("density_factor") or 1.0) * 0.85), 3)
    apply_volume_profile(prof)
    if strikes >= 3 and HUMANIZATION_MODE == "rapida":
        HUMANIZATION_MODE = "equilibrado"
        console_warn("Muchos errores → humanización pasa a 'equilibrado'.")
    elif strikes >= 4 and HUMANIZATION_MODE in {"rapida", "equilibrado"}:
        HUMANIZATION_MODE = "pausada"
        console_warn("Errores persistentes → humanización 'pausada'.")


def is_captcha_response(response: Any = None, html: str = "", status: Optional[int] = None) -> bool:
    st = status
    body = html or ""
    if response is not None:
        try:
            st = st or getattr(response, "status_code", None)
            body = body or (getattr(response, "text", "") or "")
        except Exception:
            pass
    blob = (body or "").lower()
    if st in {403, 429}:
        if any(m in blob for m in YOUTUBE_BOT_MARKERS) or st == 429:
            return True
    return any(m in blob for m in YOUTUBE_BOT_MARKERS)


def is_youtube_blocked(text: str) -> tuple[bool, str]:
    low = (text or "").lower()
    for m in YOUTUBE_BOT_MARKERS:
        if m in low:
            return True, m
    return False, ""


def evade_captcha_with_signal(session: requests.Session, strikes: int = 1) -> requests.Session:
    """Recuperación completa: penalización + NEWNYM + nueva sesión + UA rotado."""
    penalty = progressive_error_penalty(strikes, base=12.0)
    console_warn(f"Bloqueo strike {strikes} → enfriamiento {penalty:.0f}s + NEWNYM")
    live_wait(penalty, "penalización")
    ok = TOR.new_identity(session=session, aggressive=True)
    if not ok:
        console_warn("NEWNYM falló; espera extra")
        live_wait(progressive_error_penalty(strikes, base=8.0), "sin Signal")
    if strikes >= 2:
        time.sleep(random.uniform(4.0, 9.0))
        TOR.reset_stream_isolation()
        TOR.new_identity(session=session, aggressive=True)
    new_session = create_session(use_tor=True)
    ip = get_exit_ip(new_session)
    if ip:
        console_ok(f"Nueva IP Tor: {ip}")
    return new_session


# --- Stealth script para Chromium ---
def _stealth_init_script(profile: dict, canvas_noise: bool = True, webgl_spoof: bool = True) -> str:
    langs = json.dumps(profile.get("languages") or ["es-ES", "es"])
    platform = json.dumps(profile.get("platform") or "Win32")
    vendor = json.dumps(profile.get("webgl_vendor") or "Google Inc.")
    renderer = json.dumps(profile.get("webgl_renderer") or "ANGLE")
    hw = int(profile.get("hardware_concurrency") or 4)
    mem = int(profile.get("device_memory") or 8)
    canvas_block = """
      try {
        const orig = CanvasRenderingContext2D.prototype.getImageData;
        CanvasRenderingContext2D.prototype.getImageData = function() {
          const d = orig.apply(this, arguments);
          const n = (Math.random() * 2 - 1) * 0.4;
          for (let i = 0; i < d.data.length; i += 97) d.data[i] = Math.max(0, Math.min(255, d.data[i] + n));
          return d;
        };
      } catch (e) {}
    """ if canvas_noise else ""
    webgl_block = f"""
      try {{
        const patch = (proto) => {{
          const gp = proto.getParameter;
          proto.getParameter = function(p) {{
            if (p === 37445) return {vendor};
            if (p === 37446) return {renderer};
            return gp.apply(this, arguments);
          }};
        }};
        patch(WebGLRenderingContext.prototype);
        if (window.WebGL2RenderingContext) patch(WebGL2RenderingContext.prototype);
      }} catch (e) {{}}
    """ if webgl_spoof else ""
    return f"""
    (() => {{
      try {{ Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }}); }} catch (e) {{}}
      try {{
        Object.defineProperty(navigator, 'languages', {{ get: () => {langs} }});
        Object.defineProperty(navigator, 'language', {{ get: () => {langs}[0] }});
      }} catch (e) {{}}
      try {{ Object.defineProperty(navigator, 'platform', {{ get: () => {platform} }}); }} catch (e) {{}}
      try {{ Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {hw} }}); }} catch (e) {{}}
      try {{ Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {mem} }}); }} catch (e) {{}}
      try {{
        if (!navigator.plugins || navigator.plugins.length === 0) {{
          Object.defineProperty(navigator, 'plugins', {{ get: () => [
            {{ name: 'PDF Viewer' }}, {{ name: 'Chrome PDF Viewer' }}, {{ name: 'Chromium PDF Viewer' }},
          ]}});
        }}
      }} catch (e) {{}}
      try {{ window.chrome = window.chrome || {{ runtime: {{}} }}; }} catch (e) {{}}
      {canvas_block}
      {webgl_block}
      try {{
        Object.defineProperty(window, 'RTCPeerConnection', {{ get: () => undefined }});
        Object.defineProperty(window, 'webkitRTCPeerConnection', {{ get: () => undefined }});
      }} catch (e) {{}}
    }})();
    """


def create_browser_context(playwright, use_tor: bool = False, headless: bool = True,
                           js_enabled: bool = True):
    """Chromium con perfil coherente + stealth. Devuelve (browser, context)."""
    fp = pick_fingerprint_profile()
    launch_args = [
        "--disable-blink-features=AutomationControlled", "--no-sandbox",
        "--disable-dev-shm-usage", "--disable-infobars",
        "--disable-background-networking", "--disable-default-apps", "--no-first-run",
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    ]
    proxy = None
    if use_tor and TOR.available():
        proxy = {"server": f"socks5://{TOR.socks_host}:{TOR.socks_port}"}
    browser = playwright.chromium.launch(headless=headless, proxy=proxy, args=launch_args)
    context = browser.new_context(
        user_agent=fp["ua"],
        locale=fp["locale"],
        viewport=fp["viewport"],
        timezone_id=fp.get("timezone_id") or "Europe/Madrid",
        java_script_enabled=js_enabled,
        accept_downloads=False,
        color_scheme=random.choice(["light", "dark", "no-preference"]),
        extra_http_headers={
            "Accept-Language": build_accept_language(fp["languages"]),
            "Sec-Ch-Ua": fp.get("sec_ch_ua", ""),
            "Sec-Ch-Ua-Mobile": fp.get("sec_ch_ua_mobile", "?0"),
            "Sec-Ch-Ua-Platform": fp.get("sec_ch_ua_platform", '"Windows"'),
        },
    )
    context.clear_cookies()
    context.add_init_script(
        _stealth_init_script(fp) if js_enabled else
        "try { localStorage.clear(); sessionStorage.clear(); } catch (e) {}"
    )
    return browser, context


def human_mouse_move(page, x1: int, y1: int, x2: int, y2: int, steps: int = 0) -> None:
    if steps <= 0:
        steps = random.randint(12, 30)
    cx1 = x1 + (x2 - x1) * random.uniform(0.2, 0.4) + random.randint(-80, 80)
    cy1 = y1 + (y2 - y1) * random.uniform(0.2, 0.4) + random.randint(-80, 80)
    cx2 = x1 + (x2 - x1) * random.uniform(0.6, 0.8) + random.randint(-80, 80)
    cy2 = y1 + (y2 - y1) * random.uniform(0.6, 0.8) + random.randint(-80, 80)
    for i in range(1, steps + 1):
        t = i / steps
        bx = (1-t)**3*x1 + 3*(1-t)**2*t*cx1 + 3*(1-t)*t**2*cx2 + t**3*x2
        by = (1-t)**3*y1 + 3*(1-t)**2*t*cy1 + 3*(1-t)*t**2*cy2 + t**3*y2
        try:
            page.mouse.move(int(bx), int(by))
        except Exception:
            return
        time.sleep(random.uniform(0.004, 0.022))


def human_scroll(page, total_steps: int = 8, mode: str = "leer") -> None:
    lo_p, hi_p = (0.3, 0.9) if mode == "explorar" else (0.8, 2.4)
    lo_s, hi_s = (0.7, 1.2) if mode == "explorar" else (0.4, 0.85)
    for _ in range(total_steps):
        frac = random.uniform(lo_s, hi_s)
        overshoot = -random.randint(30, 120) if random.random() < 0.15 else 0
        try:
            page.evaluate(
                "({f, o}) => window.scrollBy(0, Math.floor(window.innerHeight * f) + o)",
                {"f": frac, "o": overshoot})
        except Exception:
            pass
        time.sleep(random.uniform(lo_p, hi_p) * HUMAN.circadian_factor())


def perform_browser_read(url: str, use_tor: bool = False, headless: bool = True,
                         scroll_steps: int = 12) -> dict:
    """
    Lectura realista en Chromium con fallback anti-captcha (patrón Wattpad):
      1) Carga con JS + stealth
      2) Si captcha: borrar cookies + localStorage + JS OFF + recargar
      3) Si aún bloqueado: abortar con blocked=True
    Devuelve dict con éxito, status, html, blocked, method.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {"success": False, "error": "Playwright no instalado", "blocked": False}

    def _one_pass(js_enabled: bool) -> dict:
        with sync_playwright() as p:
            browser, context = create_browser_context(p, use_tor=use_tor,
                                                     headless=headless, js_enabled=js_enabled)
            page = context.new_page()
            page.set_default_timeout(35000)
            page.set_default_navigation_timeout(45000)
            live_status(f"Cargando (JS={js_enabled})…")
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception as exc:
                try:
                    browser.close()
                except Exception:
                    pass
                return {"success": False, "error": f"goto: {exc}", "blocked": False,
                        "soft_error": True, "html": None}
            status = response.status if response else None
            time.sleep(random.uniform(0.6, 1.4))

            html = page.content()
            if is_captcha_response(html=html, status=status):
                try:
                    context.clear_cookies()
                    page.evaluate("try{localStorage.clear();sessionStorage.clear();}catch(e){}")
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass
                return {"success": False, "error": "Captcha en pasada", "blocked": True,
                        "status": status, "html": html, "method": "captcha-detected"}

            # Interacción humana: mouse + scroll
            try:
                human_mouse_move(page, 200, 200, 900, 500)
                HUMAN.think_pause(1.0)
                human_scroll(page, total_steps=scroll_steps, mode="leer")
            except Exception:
                pass

            html = page.content()
            final_url = page.url
            title = ""
            try:
                title = page.title()
            except Exception:
                pass
            browser.close()
            return {"success": True, "status": status, "html": html,
                    "title": title, "final_url": final_url, "blocked": False,
                    "method": f"chromium-js-{'on' if js_enabled else 'off'}"}

    # ----- Pasada 1: JS ON -----
    result = _one_pass(js_enabled=True)
    if result.get("success") or not result.get("blocked"):
        return result

    # ----- Pasada 2: JS OFF + cookies limpias (recuperación) -----
    console_warn("Captcha → limpiando cookies + JS off + recarga…")
    live_wait(random.uniform(3.0, 7.0), "pre-recuperación")
    result2 = _one_pass(js_enabled=False)
    if result2.get("success"):
        result2["method"] = "chromium-js-off-recovery"
        return result2

    # ----- Fallback: rotar Tor y reintentar una vez más -----
    if use_tor:
        console_warn("Aún bloqueado → NEWNYM + último intento")
        TOR.new_identity(session=None, aggressive=True)
        TOR.reset_stream_isolation()
        result3 = _one_pass(js_enabled=True)
        if result3.get("success"):
            result3["method"] = "chromium-post-newnym"
            return result3
        return result3

    return result2


# ============================================================
# [S6] METADATA — yt-dlp + InnerTube fallback + análisis de formatos
# ============================================================

def extract_video_id(url_or_id: str) -> Optional[str]:
    raw = (url_or_id or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", raw):
        return raw
    try:
        p = urlparse(raw)
        host = (p.hostname or "").lower()
        if host == "youtu.be":
            vid = p.path.strip("/").split("/")[0]
            return vid if re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) else None
        if "youtube.com" in host or "youtube-nocookie.com" in host:
            qs = parse_qs(p.query)
            if qs.get("v"):
                vid = qs["v"][0]
                return vid if re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) else None
            parts = [x for x in p.path.split("/") if x]
            if parts and parts[0] in {"shorts", "embed", "live", "v"} and len(parts) > 1:
                return parts[1] if re.fullmatch(r"[A-Za-z0-9_-]{11}", parts[1]) else None
    except Exception:
        return None
    return None


def innertube_context(client: str = "WEB", visitor: Optional[str] = None) -> dict:
    client = client.upper()
    if client == "ANDROID":
        c = {"clientName": "ANDROID", "clientVersion": INNERTUBE_ANDROID_VERSION,
             "androidSdkVersion": 33, "hl": "es", "gl": "ES"}
    elif client == "IOS":
        c = {"clientName": "IOS", "clientVersion": INNERTUBE_IOS_VERSION,
             "hl": "es", "gl": "ES", "deviceMake": "Apple",
             "deviceModel": "iPhone14,5", "osName": "iOS", "osVersion": "17.0"}
    else:
        c = {"clientName": "WEB", "clientVersion": INNERTUBE_WEB_VERSION, "hl": "es", "gl": "ES"}
    if visitor:
        c["visitorData"] = visitor
    return {"client": c}


def innertube_post(session: requests.Session, endpoint: str, payload: dict,
                   timeout: float = 25.0) -> dict:
    url = f"https://www.youtube.com/youtubei/v1/{endpoint}"
    params = {"key": INNERTUBE_API_KEY, "prettyPrint": "false"}
    r = session.post(url, params=params, json=payload, timeout=timeout)
    if r.status_code == 429:
        raise RuntimeError(f"429 InnerTube")
    if r.status_code in {401, 403} or is_captcha_response(r, r.text, r.status_code):
        raise RuntimeError(f"InnerTube HTTP {r.status_code}")
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("InnerTube no devolvió JSON")
    return data


def get_visitor_data(session: Optional[requests.Session] = None) -> str:
    sess = session or create_session(use_tor=False)
    try:
        r = sess.get("https://www.youtube.com/", timeout=20)
        m = re.search(r'"VISITOR_DATA":"([^"]+)"', r.text or "")
        if not m:
            m = re.search(r"VISITOR_INFO1_LIVE=([^;\"']+)", r.text or "")
        if m:
            val = m.group(1)
            sess.headers["X-Goog-Visitor-Id"] = val
            return val
    except Exception:
        pass
    raw = bytes([1]) + int(time.time()).to_bytes(4, "big") + os.urandom(6)
    token = "Cgt" + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sess.headers["X-Goog-Visitor-Id"] = token
    return token


def get_po_token(video_id: str) -> Optional[str]:
    """Intenta poToken vía bgutil-ytdlp-pot-provider (opcional)."""
    cache = {}
    try:
        if POT_CACHE.exists():
            cache = json.loads(POT_CACHE.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    ent = cache.get(video_id) or {}
    if ent.get("token") and (time.time() - float(ent.get("ts") or 0)) < POT_TTL_SECONDS:
        return str(ent["token"])
    if not is_port_open("127.0.0.1", 4416):
        return None
    for url in (f"{POT_PROVIDER_URL}/get_pot?content_binding={video_id}",
                f"{POT_PROVIDER_URL}/get_pot?video_id={video_id}"):
        try:
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                continue
            try:
                data = r.json()
                token = data.get("poToken") or data.get("pot") or data.get("token")
            except Exception:
                token = r.text.strip() or None
            if token:
                cache[video_id] = {"token": token, "ts": time.time()}
                ensure_dir(POT_CACHE.parent)
                POT_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
                console_ok("po_token obtenido")
                return str(token)
        except Exception:
            continue
    return None


def is_port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ytdlp_base_opts(cfg: dict, for_video: bool) -> dict:
    dl = cfg.get("download") or {}
    yt = cfg.get("youtube") or {}
    paranoid = bool(yt.get("paranoid_mode"))
    opts: dict[str, Any] = {
        "quiet": True, "no_warnings": True, "noprogress": True,
        "retries": 10, "fragment_retries": 10, "extractor_retries": 3,
        "sleep_interval": int(dl.get("sleep_interval") or 5),
        "max_sleep_interval": int(dl.get("sleep_interval") or 5) + 4,
        "sleep_interval_requests": int(dl.get("sleep_requests") or 3),
        "concurrent_fragment_downloads": int(dl.get("concurrent_fragments") or 5),
        "cachedir": str(CACHE_DIR / "ytdlp"),
        "nocheckcertificate": True,
        "format_sort": ["res", "fps", "hdr:12", "vcodec:h264"],
    }
    if for_video and not paranoid:
        rate = _parse_rate(str(dl.get("limit_rate") or "0"))
        if rate > 0:
            opts["ratelimit"] = rate
    if for_video and paranoid:
        opts["ratelimit"] = _parse_rate("300K")
    cookies = yt.get("cookies_file")
    if yt.get("use_cookies") and cookies:
        opts["cookiefile"] = cookies
    return opts


def _parse_rate(s: str) -> int:
    s = str(s or "0").strip().upper()
    if s in {"0", "", "NONE", "UNLIMITED"}:
        return 0
    m = re.match(r"^(\d+(?:\.\d+)?)([KMG])?$", s)
    if not m:
        return 0
    n = float(m.group(1))
    mul = {None: 1, "K": 1000, "M": 1_000_000, "G": 1_000_000_000}[m.group(2)]
    return int(n * mul)


def extract_metadata(url: str, cfg: dict, session: requests.Session, use_tor: bool) -> dict:
    """Extrae metadatos Y guarda qué client funcionó + lista de formatos disponibles."""
    if not YTDLP_AVAILABLE:
        raise RuntimeError("yt-dlp requerido")
    vid = extract_video_id(url) or url
    watch = f"https://www.youtube.com/watch?v={vid}"
    clients = list((cfg.get("youtube") or {}).get("player_clients") or PLAYER_CLIENTS)
    last_exc = None
    working_client = None
    best_info = None

    for client in clients:
        HUMAN.think_pause(1.0)
        live_status(f"Metadata · probando client={client}")
        try:
            opts = ytdlp_base_opts(cfg, for_video=False)
            opts["skip_download"] = True
            opts["extract_flat"] = False
            opts["extractor_args"] = {"youtube": {"player_client": [client]}}
            if use_tor:
                opts["proxy"] = TOR.stream_isolation_proxy()
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(watch, download=False) or {}
            if info.get("id"):
                working_client = client
                best_info = info
                break
        except Exception as exc:
            last_exc = exc
            console_warn(f"  metadata {client}: {str(exc)[:100]}")

    if not best_info:
        # Fallback InnerTube
        try:
            visitor = get_visitor_data(session)
            payload = {"context": innertube_context("ANDROID", visitor),
                       "videoId": vid, "contentCheckOk": True, "racyCheckOk": True}
            data = innertube_post(session, "player", payload)
            vd = data.get("videoDetails") or {}
            meta = {"id": vd.get("videoId") or vid, "title": vd.get("title"),
                    "description": vd.get("shortDescription"), "channel": vd.get("author"),
                    "channel_id": vd.get("channelId"),
                    "view_count": _parse_compact_number(vd.get("viewCount")),
                    "duration": _parse_compact_number(vd.get("lengthSeconds")),
                    "webpage_url": watch,
                    "_working_client": "android",
                    "_available_heights": [],
                    "_available_vcodecs": []}
            if meta.get("title"):
                return meta
        except Exception as exc:
            last_exc = exc
        raise RuntimeError(f"No metadata: {last_exc}")

    meta = {k: best_info.get(k) for k in METADATA_FIELDS}
    meta["id"] = best_info.get("id")
    meta["title"] = best_info.get("title")
    meta["_working_client"] = working_client

    # --- Analizar formatos REALES disponibles ---
    formats = best_info.get("formats") or []
    heights = sorted({f.get("height") for f in formats if f.get("height")}, reverse=True)
    vcodecs = sorted({(f.get("vcodec") or "").split(".")[0]
                     for f in formats if f.get("vcodec") and f.get("vcodec") != "none"})
    meta["_available_heights"] = heights
    meta["_available_vcodecs"] = vcodecs
    max_h = heights[0] if heights else 0

    console_ok(f"Metadata OK · client={working_client} · máx resolución real={max_h}p")
    if heights:
        top = heights[:8]
        console_info(f"Resoluciones disponibles: {', '.join(str(h)+'p' for h in top)}")
    if vcodecs:
        console_info(f"Códecs disponibles: {', '.join(vcodecs)}")

    return meta


def _parse_compact_number(s: Any) -> int:
    if s is None: return 0
    if isinstance(s, (int, float)): return int(s)
    t = str(s).strip().upper().replace(",", "").replace("\xa0", "")
    mult = 1.0
    if t.endswith("K") or t.endswith("MIL"):
        t = t.replace("MIL", "").rstrip("K"); mult = 1_000
    elif t.endswith("M"):
        t = t[:-1]; mult = 1_000_000
    elif t.endswith("B") or t.endswith("MM"):
        t = t.replace("MM", "").rstrip("B"); mult = 1_000_000_000
    t = re.sub(r"[^\d.]", "", t)
    try:
        return int(float(t) * mult) if t else 0
    except ValueError:
        return 0


# ============================================================
# [S7] DESCARGA DE VIDEO — 4K/Full HD, reusa client que funcionó
# ============================================================

def format_for_mode(mode: str, quality: int, prefer_max: bool = True,
                    available_heights: Optional[list] = None,
                    available_vcodecs: Optional[list] = None) -> tuple[str, dict]:
    """
    Selector de formato que respeta los formatos REALES del video.
    Si el video solo tiene 1080p, no intenta 8K.
    """
    extra: dict[str, Any] = {
        "writesubtitles": True, "writeautomaticsub": True,
        "subtitleslangs": ["es", "en", "es-ES"],
        "concurrent_fragment_downloads": 5, "retries": 10, "fragment_retries": 10,
    }

    # Ajustar calidad al máximo REAL disponible
    real_max = max(available_heights) if available_heights else int(quality or 2160)
    effective_q = min(int(quality or 2160), real_max) if real_max else int(quality or 2160)
    if effective_q < int(quality or 2160):
        console_info(
            f"Calidad ajustada: pediste {quality}p, el video llega a {real_max}p → usando {effective_q}p"
        )
    q = effective_q

    if mode in {"video", "video_4k", "video_hq"}:
        if prefer_max or mode == "video_hq":
            spec = (
                f"bestvideo[height<={q}][vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={q}][vcodec^=av01]+bestaudio/"
                f"bestvideo[height<={q}][vcodec^=vp9]+bestaudio/"
                f"bestvideo[height<={q}][vcodec^=vp09]+bestaudio/"
                f"bestvideo[height<={q}]+bestaudio/"
                f"bestvideo+bestaudio/best"
            )
        else:
            spec = f"bestvideo[height<={q}]+bestaudio/best[height<={q}]/best"
        extra["merge_output_format"] = "mkv"
        return spec, extra

    if mode == "audio":
        return "bestaudio[ext=m4a]/bestaudio/best", {
            "postprocessors": [{"key": "FFmpegExtractAudio",
                                "preferredcodec": "m4a", "preferredquality": "320"}],
            "concurrent_fragment_downloads": 5}
    if mode == "audio_mp3":
        return "bestaudio/best", {
            "postprocessors": [{"key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3", "preferredquality": "320"}],
            "concurrent_fragment_downloads": 5}
    if mode == "subs_only":
        extra.update({"skip_download": True})
        return "best", extra
    return "bestvideo+bestaudio/best", extra


def download_with_fallback(video_id: str, dest: Path, cfg: dict,
                           session: requests.Session,
                           meta: Optional[dict] = None) -> dict:
    """Descarga reusando el client y formatos que metadata ya descubrió."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    yt_cfg = cfg.get("youtube") or {}
    dl = cfg.get("download") or {}
    mode = str(dl.get("mode") or "video")
    quality = int(dl.get("quality") or 2160)
    prefer_max = bool(dl.get("prefer_max_quality", True))
    paranoid = bool(yt_cfg.get("paranoid_mode"))

    # --- Reusar info de metadata ---
    working_client = (meta or {}).get("_working_client")
    avail_h = (meta or {}).get("_available_heights") or []
    avail_vc = (meta or {}).get("_available_vcodecs") or []

    # Orden de clients: el que funcionó en metadata primero
    if quality >= 2160 and mode in {"video", "video_4k", "video_hq"}:
        base_clients = list(PLAYER_CLIENTS_4K) + list(PLAYER_CLIENTS_MOBILE)
    else:
        base_clients = list(yt_cfg.get("player_clients") or PLAYER_CLIENTS)

    if working_client and working_client in base_clients:
        base_clients.remove(working_client)
        clients = [working_client] + base_clients
        console_info(f"Reusando client que funcionó en metadata: {working_client}")
    else:
        clients = base_clients

    spec, extra = format_for_mode(mode, quality, prefer_max,
                                  available_heights=avail_h,
                                  available_vcodecs=avail_vc)
    video_dir = _subdir(dest, "video")
    tmpl = str(video_dir / "%(id)s.%(ext)s")
    errors: list[str] = []
    tried_clients: set[str] = set()

    for i, client in enumerate(clients):
        if client in tried_clients:
            continue
        tried_clients.add(client)

        HUMAN.think_pause(1.5)
        use_tor_dl = paranoid
        live_status(f"Descarga · client={client} · objetivo={quality}p ({i+1}/{len(clients)})")
        try:
            opts = ytdlp_base_opts(cfg, for_video=True)
            opts["skip_download"] = False
            opts["extract_flat"] = False
            opts["extractor_args"] = {"youtube": {"player_client": [client]}}
            pot = get_po_token(video_id)
            if pot:
                opts["extractor_args"]["youtube"]["po_token"] = [f"{client}.gvs+{pot}"]
            if use_tor_dl:
                opts["proxy"] = TOR.stream_isolation_proxy()
            opts["outtmpl"] = tmpl
            opts["format"] = spec
            opts.update(extra)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True) or {}
            fmts = info.get("requested_formats") or info.get("requested_downloads") or []
            height = None
            for f in fmts:
                if isinstance(f, dict) and f.get("height"):
                    height = max(height or 0, int(f["height"]))
            if height:
                if height >= quality:
                    console_ok(f"Descargado a {height}p (client={client}) ✓")
                elif height >= 2160:
                    console_ok(f"Descargado a {height}p · 4K OK (client={client})")
                elif height >= 1440:
                    console_ok(f"Descargado a {height}p · 2K (client={client})")
                elif height >= 1080:
                    console_ok(f"Descargado a {height}p · Full HD (client={client})")
                else:
                    console_warn(f"Descargado a {height}p (client={client}) — menor que lo pedido")
            return {"success": True, "info": info, "client": client,
                    "source": "yt-dlp", "height": height}
        except Exception as exc:
            blocked, marker = is_youtube_blocked(str(exc))
            errors.append(f"{client}: {str(exc)[:120]}")
            if blocked:
                console_warn(f"  Bloqueo ({marker}) en {client} → rotar identidad")
                if TOR.available():
                    TOR.new_identity(session=session, aggressive=(i >= 1))
                    session = create_session(use_tor=paranoid)
                rotate_user_agent(session)
            else:
                console_warn(f"  Fallo {client}: {str(exc)[:100]}")
            HUMAN.maybe_micro_break()
            time.sleep(inter_operation_delay(TOR.available()))

    # Fallback: cookies
    if yt_cfg.get("use_cookies"):
        console_info("Reintento con cookies del navegador…")
        cfile = _load_cookies_from_browser(str(yt_cfg.get("cookies_browser") or "firefox"))
        if cfile:
            cfg2 = dict(cfg)
            cfg2["youtube"] = {**yt_cfg, "cookies_file": cfile}
            try:
                return download_with_fallback(video_id, dest, cfg2, session, meta=meta)
            except Exception as exc:
                errors.append(f"cookies: {exc}")

    # Fallback: pytubefix
    if PYTUBEFIX_AVAILABLE:
        try:
            console_info("Fallback pytubefix…")
            yt = PytubeYouTube(url)
            stream = yt.streams.filter(progressive=True, file_extension="mp4")\
                .order_by("resolution").last() or \
                yt.streams.filter(file_extension="mp4").order_by("resolution").last()
            if stream:
                path = Path(stream.download(output_path=str(video_dir), filename="video.mp4"))
                return {"success": True, "info": {"id": video_id},
                        "client": "pytubefix", "source": "pytubefix"}
        except Exception as exc:
            errors.append(f"pytubefix: {exc}")

    raise RuntimeError(" | ".join(errors[-6:]))


def postprocess_media(dest: Path, mode: str, meta: dict) -> dict:
    """Extrae audio, waveform, storyboard. Guarda todo en subcarpetas."""
    out: dict[str, str] = {}
    video_dir = _subdir(dest, "video")
    images_dir = _subdir(dest, "images")

    videos = (list(video_dir.glob("*.mp4")) + list(video_dir.glob("*.mkv")) +
              list(video_dir.glob("*.webm")))
    audios = (list(video_dir.glob("*.m4a")) + list(video_dir.glob("*.opus")) +
              list(video_dir.glob("*.mp3")) + list(video_dir.glob("*.ogg")) +
              list(video_dir.glob("*.wav")))

    if videos:
        out["video"] = str(videos[0])
        if ffmpeg_ok():
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height,codec_name",
                     "-of", "json", str(videos[0])],
                    capture_output=True, timeout=30, text=True)
                if probe.returncode == 0:
                    data = json.loads(probe.stdout or "{}")
                    streams = data.get("streams") or []
                    if streams:
                        w = streams[0].get("width"); h = streams[0].get("height")
                        vcodec = streams[0].get("codec_name")
                        out["resolution"] = f"{w}x{h}"
                        out["vcodec"] = str(vcodec)
                        console_ok(f"Video final: {w}x{h} ({vcodec})")
                        if h and h >= 2160:
                            console_ok(f"✅ 4K confirmado ({h}p)")
                        elif h and h >= 1440:
                            console_ok(f"✅ 2K confirmado ({h}p)")
                        elif h and h >= 1080:
                            console_warn(f"⚠ Full HD ({h}p) — el video no tiene 4K o el client lo capó")
            except Exception:
                pass

    audio_path = audios[0] if audios else None
    if not audio_path and videos and ffmpeg_ok():
        target = video_dir / "audio.m4a"
        subprocess.run(["ffmpeg", "-y", "-i", str(videos[0]), "-vn",
                        "-acodec", "copy", str(target)],
                       capture_output=True, timeout=600)
        if not (target.exists() and target.stat().st_size > 1000):
            subprocess.run(["ffmpeg", "-y", "-i", str(videos[0]), "-vn",
                            "-acodec", "aac", "-b:a", "192k", str(target)],
                           capture_output=True, timeout=600)
        if target.exists():
            audio_path = target

    if audio_path:
        out["audio"] = str(audio_path)
        if mode == "audio_mp3" and ffmpeg_ok() and audio_path.suffix.lower() != ".mp3":
            mp3 = video_dir / "audio.mp3"
            subprocess.run(["ffmpeg", "-y", "-i", str(audio_path), "-codec:a",
                            "libmp3lame", "-b:a", "320k", str(mp3)],
                           capture_output=True, timeout=600)
            if mp3.exists():
                out["audio_mp3"] = str(mp3); audio_path = mp3

        # Waveform → images/
        if ffmpeg_ok():
            try:
                wavp = images_dir / "waveform.png"
                subprocess.run(["ffmpeg", "-y", "-i", str(audio_path), "-filter_complex",
                                "showwavespic=s=1280x240:colors=#33aaff", str(wavp)],
                               capture_output=True, timeout=180)
                if wavp.exists():
                    out["waveform"] = str(wavp)
            except Exception:
                pass

        thumb = images_dir / "thumbnail.jpg"
        _embed_cover(audio_path, thumb, meta)

    if videos and ffmpeg_ok():
        try:
            sb = images_dir / "storyboard.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", str(videos[0]), "-vf",
                            "fps=1/10,scale=160:-1,tile=6x6", "-frames:v", "1", str(sb)],
                           capture_output=True, timeout=180)
            if sb.exists():
                out["storyboard"] = str(sb)
        except Exception:
            pass
    return out


def _embed_cover(audio: Path, thumb: Path, meta: dict) -> None:
    if not MUTAGEN_AVAILABLE or not thumb.exists():
        return
    try:
        data = thumb.read_bytes()
        if audio.suffix.lower() == ".mp3":
            try:
                tags = ID3(str(audio))
            except Exception:
                tags = ID3()
            tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=data))
            if meta.get("title"):
                tags.add(TIT2(encoding=3, text=str(meta["title"])))
            if meta.get("channel"):
                tags.add(TPE1(encoding=3, text=str(meta["channel"])))
            tags.save(str(audio))
        elif audio.suffix.lower() in {".m4a", ".mp4"}:
            mp4 = MP4(str(audio))
            mp4["covr"] = [MP4Cover(data, imageformat=MP4Cover.FORMAT_JPEG)]
            if meta.get("title"):
                mp4["\xa9nam"] = [str(meta["title"])]
            if meta.get("channel"):
                mp4["\xa9ART"] = [str(meta["channel"])]
            mp4.save()
    except Exception:
        pass


def _load_cookies_from_browser(browser: str = "firefox") -> Optional[str]:
    if not COOKIES_AVAILABLE:
        console_warn("browser_cookie3 no instalado")
        return None
    console_warn("Usar cookies puede BANEAR tu cuenta.")
    try:
        fn = getattr(browser_cookie3, browser, None)
        if fn is None:
            return None
        jar = fn(domain_name="youtube.com")
        path = ensure_dir(CACHE_DIR) / f"cookies_{browser}.txt"
        lines = ["# Netscape HTTP Cookie File"]
        for c in jar:
            secure = "TRUE" if c.secure else "FALSE"
            exp = int(c.expires or 0)
            lines.append(f"{c.domain}\tTRUE\t{c.path}\t{secure}\t{exp}\t{c.name}\t{c.value}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        console_info(f"Cookies exportadas a {path}")
        return str(path)
    except Exception as exc:
        console_fail(f"Cookies: {exc}")
        return None


def download_thumbnail(session: requests.Session, meta: dict, dest: Path) -> Optional[Path]:
    """Descarga el thumbnail en images/."""
    url = meta.get("thumbnail")
    if not url and meta.get("thumbnails"):
        thumbs = meta["thumbnails"]
        if isinstance(thumbs, list) and thumbs:
            url = thumbs[-1].get("url")
    if not url:
        vid = meta.get("id")
        url = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg" if vid else None
    if not url:
        return None
    try:
        r = session.get(url, timeout=25)
        if r.status_code == 200 and r.content:
            path = _subdir(dest, "images") / "thumbnail.jpg"
            path.write_bytes(r.content)
            return path
    except Exception:
        pass
    return None


# ============================================================
# [S8] TRANSCRIPCIÓN — Whisper + fallback a subs YouTube
# ============================================================

def fetch_youtube_subs(video_id: str) -> Optional[list[dict]]:
    if not TRANSCRIPT_API_AVAILABLE:
        return None
    try:
        try:
            tr = YouTubeTranscriptApi().fetch(video_id)
            return [{"text": x.text, "start": x.start, "duration": x.duration} for x in tr]
        except Exception:
            pass
        lst = YouTubeTranscriptApi.list_transcripts(video_id)
        for pref in ("es", "es-ES", "en"):
            try:
                return lst.find_transcript([pref]).fetch()
            except Exception:
                continue
        t = next(iter(lst), None)
        return t.fetch() if t else None
    except Exception as exc:
        logging.info("subs: %s", exc)
        return None


def srt_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_transcript_files(dest: Path, segs: list[dict], source: str, video_id: str) -> None:
    """Guarda la transcripción en subtitles/."""
    subs_dir = _subdir(dest, "subtitles")
    srt_lines = []
    for i, s in enumerate(segs, 1):
        start = float(s.get("start") or 0)
        dur = float(s.get("duration") or s.get("end") or 0)
        end = float(s.get("end") or (start + (dur if dur else 2)))
        text = (s.get("text") or "").strip()
        srt_lines.append(f"{i}\n{srt_ts(start)} --> {srt_ts(end)}\n{text}\n")
    srt = "\n".join(srt_lines)
    (subs_dir / "transcription.srt").write_text(srt, encoding="utf-8")
    (subs_dir / "transcription.vtt").write_text("WEBVTT\n\n" + srt.replace(",", "."), encoding="utf-8")
    (subs_dir / "transcription.txt").write_text(
        "\n\n".join(s["text"] for s in segs if s.get("text")), encoding="utf-8")
    save_json(subs_dir / "transcription.json", {"source": source, "segments": segs})
    md = [f"# Transcripción `{video_id}`", "", f"_Fuente: {source}_", ""]
    for s in segs:
        md.append(f"[{srt_ts(float(s['start']))}] {s.get('text','')}")
    (subs_dir / "transcription.md").write_text("\n".join(md), encoding="utf-8")


def transcribe_audio(audio_path: Optional[Path], dest: Path, cfg: dict, video_id: str) -> dict:
    tcfg = cfg.get("transcription") or {}
    model_name = str(tcfg.get("model") or "base")
    language = tcfg.get("language") or "auto"
    want_words = bool(tcfg.get("word_timestamps", True))
    segs: list[dict] = []
    source = "none"

    yt_subs = fetch_youtube_subs(video_id)
    if yt_subs:
        segs = [{"start": float(x.get("start") or 0),
                 "duration": float(x.get("duration") or 0),
                 "end": float(x.get("start") or 0) + float(x.get("duration") or 0),
                 "text": x.get("text") or ""} for x in yt_subs]
        source = "youtube-transcript-api"
        console_ok(f"Subtítulos YouTube: {len(segs)} cues")

    if (not segs) and WHISPER_AVAILABLE and audio_path and audio_path.exists():
        live_status(f"faster-whisper modelo={model_name}…")
        try:
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            lang = None if language in {None, "", "auto"} else language
            segments, info = model.transcribe(str(audio_path), language=lang,
                                              vad_filter=bool(tcfg.get("vad", True)),
                                              word_timestamps=want_words)
            segs = []
            for s in segments:
                item = {"start": float(s.start), "end": float(s.end),
                        "duration": float(s.end - s.start), "text": (s.text or "").strip()}
                if want_words and getattr(s, "words", None):
                    item["words"] = [{"word": w.word, "start": float(w.start),
                                      "end": float(w.end)} for w in s.words if w.start is not None]
                segs.append(item)
            source = f"faster-whisper:{model_name}"
            console_ok(f"Whisper: {len(segs)} segmentos, idioma={getattr(info, 'language', '?')}")
        except Exception as exc:
            if not segs:
                raise RuntimeError(f"Whisper falló: {exc}")

    if not segs:
        raise RuntimeError("Ni subtítulos ni Whisper disponibles")

    write_transcript_files(dest, segs, source, video_id)
    return {"source": source, "segments": len(segs)}


# ============================================================
# [S9] COMENTARIOS — multi-pasada con rotación IP/UA
# ============================================================

def iter_renderers(obj: Any) -> Iterator[dict]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from iter_renderers(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from iter_renderers(it)


def runs_text(node: Any) -> str:
    if node is None: return ""
    if isinstance(node, str): return node
    if isinstance(node, dict):
        if "simpleText" in node:
            return str(node.get("simpleText") or "")
        if "runs" in node:
            return "".join(str(r.get("text") or "") for r in node.get("runs") or [])
    return ""


def parse_comment_renderer(c: dict) -> dict:
    cr = c.get("commentRenderer") or c
    author_id = ""
    handle = ""
    try:
        be = cr.get("authorEndpoint", {}).get("browseEndpoint", {})
        author_id = be.get("browseId") or ""
        handle = be.get("canonicalBaseUrl") or ""
    except Exception:
        pass
    avatar = ""
    thumbs = (cr.get("authorThumbnail") or {}).get("thumbnails") or []
    if thumbs:
        avatar = thumbs[-1].get("url") or ""
    return {
        "id": cr.get("commentId") or cr.get("id") or "",
        "author": runs_text(cr.get("authorText")),
        "author_id": author_id, "author_handle": handle, "author_avatar": avatar,
        "text": runs_text(cr.get("contentText")),
        "likes": _parse_compact_number(runs_text(cr.get("voteCount")) or cr.get("likeCount") or 0),
        "published_relative": runs_text(cr.get("publishedTimeText")),
        "published_absolute": None,
        "is_pinned": bool(cr.get("pinnedCommentBadge")),
        "has_creator_heart": bool(cr.get("creatorHeart")),
        "is_member": bool(cr.get("authorCommentBadge") or cr.get("sponsorCommentBadge")),
        "reply_count": _parse_compact_number(cr.get("replyCount") or 0),
        "replies_continuation": None, "replies": [],
        "parent_id": None, "depth": 0,
    }


def parse_comment_thread(thread: dict) -> dict:
    ctr = thread.get("commentThreadRenderer") or thread
    comment = parse_comment_renderer(ctr.get("comment") or {})
    cont = None
    for node in iter_renderers(ctr.get("replies") or {}):
        cir = node.get("continuationItemRenderer") if isinstance(node, dict) else None
        if not cir:
            continue
        tok = (cir.get("continuationEndpoint", {})
                  .get("continuationCommand", {}).get("token"))
        if tok:
            cont = tok
            break
    comment["replies_continuation"] = cont
    return comment


def get_comments_continuation(session: requests.Session, video_id: str,
                              sort: str = "top", visitor: Optional[str] = None) -> Optional[str]:
    payload = {"context": innertube_context("WEB", visitor or get_visitor_data(session)),
               "videoId": video_id}
    data = innertube_post(session, "next", payload)
    tokens: list[str] = []
    for node in iter_renderers(data):
        if not isinstance(node, dict):
            continue
        cir = node.get("continuationItemRenderer")
        if not cir:
            continue
        te = cir.get("continuationEndpoint") or cir.get("button") or {}
        cmd = (te.get("continuationEndpoint") or te).get("continuationCommand") \
              or te.get("continuationCommand") or {}
        tok = cmd.get("token")
        if tok:
            tokens.append(tok)
    return tokens[0] if tokens else None


def fetch_comments_page(session: requests.Session, continuation: str,
                        visitor: Optional[str] = None) -> dict:
    payload = {"context": innertube_context("WEB", visitor), "continuation": continuation}
    return innertube_post(session, "next", payload)


def is_shadow_throttled(data: dict) -> bool:
    items = [i for i in iter_renderers(data) if isinstance(i, dict) and
             ("commentThreadRenderer" in i or "commentRenderer" in i)]
    if ("continuationContents" in data or "onResponseReceivedEndpoints" in data) \
       and len(items) == 0:
        return True
    blob = json.dumps(data)[:5000].lower()
    return "rate limit" in blob


def next_continuations(data: dict) -> list[str]:
    found: list[str] = []
    for node in iter_renderers(data):
        if not isinstance(node, dict):
            continue
        cir = node.get("continuationItemRenderer")
        if not cir:
            continue
        for key in ("continuationEndpoint", "button"):
            block = cir.get(key) or {}
            if "continuationCommand" in block and block["continuationCommand"].get("token"):
                found.append(block["continuationCommand"]["token"])
            inner = block.get("continuationEndpoint") or {}
            tok = (inner.get("continuationCommand") or {}).get("token")
            if tok:
                found.append(tok)
    out, seen = [], set()
    for t in found:
        if t not in seen:
            seen.add(t); out.append(t)
    return out


def fetch_replies_recursive(session: requests.Session, continuation: str,
                            depth: int = 1, max_depth: int = 3, max_replies: int = 50,
                            visitor: Optional[str] = None, parent_id: str = "") -> list[dict]:
    if depth > max_depth or not continuation:
        return []
    collected: list[dict] = []
    token: Optional[str] = continuation
    pages = 0
    while token and len(collected) < max_replies and pages < 20:
        pages += 1
        mod = _HUMANIZATION_MODIFIERS.get(HUMANIZATION_MODE,
                                          _HUMANIZATION_MODIFIERS["equilibrado"])
        time.sleep(random.uniform(1.2, 3.0) * mod["pause_scale"] * HUMAN.circadian_factor())
        try:
            data = fetch_comments_page(session, token, visitor)
        except Exception:
            break
        if is_shadow_throttled(data):
            time.sleep(20)
            break
        for node in iter_renderers(data):
            if not isinstance(node, dict):
                continue
            if "commentRenderer" in node:
                item = parse_comment_renderer(node)
                item["parent_id"] = parent_id
                item["depth"] = depth
                collected.append(item)
            elif "commentThreadRenderer" in node:
                item = parse_comment_thread(node)
                item["parent_id"] = parent_id
                item["depth"] = depth
                collected.append(item)
        conts = next_continuations(data)
        token = conts[0] if conts else None
    return collected[:max_replies]


def download_comments_single_pass(session: requests.Session, video_id: str, cfg: dict,
                                   sort: str = "top", max_comments: int = 5000,
                                   max_replies_per_thread: int = 50,
                                   include_replies: bool = True,
                                   use_tor: bool = False,
                                   tag: str = "") -> dict:
    """Una pasada de comentarios con rotación IP/UA cada N páginas."""
    yt_cfg = cfg.get("youtube") or {}
    rotate_ip_every = int(yt_cfg.get("rotate_every_pages") or 10)
    rotate_ua_every = int(yt_cfg.get("rotate_ua_every_pages") or 3)

    cache_dir = ensure_dir(CACHE_DIR / "comments")
    state_path = cache_dir / f"{video_id}{tag}_state.json"
    state = load_json(state_path, {})
    comments: list[dict] = state.get("comments") or []
    token = state.get("continuation")
    page = int(state.get("page") or 0)
    visitor = get_visitor_data(session)
    session.headers["X-Goog-Visitor-Id"] = visitor
    shadow_hits = 0
    strikes = 0

    apply_volume_profile(compute_volume_profile(max_comments, use_tor=use_tor))

    if not token:
        live_status("Obteniendo continuation inicial…")
        try:
            token = get_comments_continuation(session, video_id, sort=sort, visitor=visitor)
        except Exception as exc:
            console_warn(f"Continuation inicial: {exc}")
            if use_tor:
                session = evade_captcha_with_signal(session, strikes=1)
                visitor = get_visitor_data(session)
                try:
                    token = get_comments_continuation(session, video_id, sort=sort, visitor=visitor)
                except Exception:
                    token = None

    if not token and not comments:
        return {"video_id": video_id, "sort": sort, "count": 0,
                "source": "no-continuation", "comments": [], "incomplete": True}

    while token and len(comments) < max_comments and page < MAX_COMMENT_PAGES:
        page += 1

        # --- Rotación IP cada N páginas ---
        if use_tor and TOR.available() and page > 1 and (page - 1) % rotate_ip_every == 0:
            console_tor(f"Rotando IP (pág {page})…")
            if TOR.new_identity(session=session, aggressive=(page >= 20)):
                session = create_session(use_tor=True)
                visitor = get_visitor_data(session)
                session.headers["X-Goog-Visitor-Id"] = visitor

        # --- Rotación UA cada N páginas ---
        if page > 1 and (page - 1) % rotate_ua_every == 0:
            rotate_user_agent(session)
            console_info(f"UA rotado en pág {page}")

        # --- Delays humanizados ---
        mod = _HUMANIZATION_MODIFIERS.get(HUMANIZATION_MODE,
                                          _HUMANIZATION_MODIFIERS["equilibrado"])
        delay = random.uniform(2.5, 6.0) * mod["pause_scale"]
        if use_tor:
            delay *= 1.8
        delay *= float(VOLUME_PROFILE.get("pause_boost") or 1.0) * HUMAN.circadian_factor()
        if page % 10 == 0:
            extra = random.uniform(15.0, 45.0) * mod["pause_scale"]
            live_wait(extra, "pausa larga cada 10 pág")
        else:
            time.sleep(delay)
        HUMAN.maybe_micro_break()
        HUMAN.maybe_macro_break()

        live_status(f"Pág {page} · {len(comments)} comentarios")

        try:
            data = fetch_comments_page(session, token, visitor)
        except Exception as exc:
            err_str = str(exc)
            if "429" in err_str or "RateLimited" in err_str:
                console_warn("429 → esperar 90s")
                live_wait(90, "429")
                continue
            if is_captcha_response(html=err_str):
                strikes += 1
                apply_error_slowdown(strikes)
                if use_tor:
                    session = evade_captcha_with_signal(session, strikes=strikes)
                else:
                    rotate_user_agent(session)
                    live_wait(progressive_error_penalty(strikes, 20), "bloqueo")
                visitor = get_visitor_data(session)
                continue
            console_warn(f"Error: {exc}")
            time.sleep(inter_operation_delay(use_tor))
            continue

        if is_shadow_throttled(data):
            shadow_hits += 1
            console_warn(f"Shadow-throttle ({shadow_hits}/3)")
            live_wait(60, "shadow-throttle")
            rotate_user_agent(session)
            visitor = get_visitor_data(session)
            if shadow_hits >= 3:
                console_fail("Shadow-throttle persistente")
                break
            continue
        shadow_hits = 0

        batch = 0
        for node in iter_renderers(data):
            if not isinstance(node, dict) or "commentThreadRenderer" not in node:
                continue
            item = parse_comment_thread(node)
            if include_replies and item.get("replies_continuation"):
                try:
                    item["replies"] = fetch_replies_recursive(
                        session, item["replies_continuation"], depth=1, max_depth=3,
                        max_replies=max_replies_per_thread, visitor=visitor, parent_id=item["id"])
                except Exception:
                    pass
            comments.append(item)
            batch += 1
            if len(comments) >= max_comments:
                break
        conts = next_continuations(data)
        token = conts[-1] if conts else None
        save_json(state_path, {"video_id": video_id, "continuation": token, "page": page,
                               "comments": comments,
                               "updated": datetime.now(timezone.utc).isoformat()})
        progress(len(comments), max_comments, "comentarios")
        if batch == 0 and not token:
            break

    return {"video_id": video_id, "sort": sort, "count": len(comments), "pages": page,
            "source": "innertube", "comments": comments,
            "incomplete": bool(token) and len(comments) < max_comments}


def download_all_comments(session: requests.Session, video_id: str, cfg: dict,
                          sort: str = "top", max_comments: int = 5000,
                          max_replies_per_thread: int = 50, include_replies: bool = True,
                          use_tor: bool = False) -> dict:
    """Multi-pasada configurable con rotación entre pasadas."""
    ccfg = cfg.get("comments") or {}
    passes = max(1, int(ccfg.get("passes") or 1))
    delay_range = ccfg.get("delay_between_passes_sec") or [60, 180]
    rotate_on_pass = bool(ccfg.get("rotate_on_pass", True))

    console_section(f"COMENTARIOS · {passes} pasada(s)")
    all_comments: list[dict] = []
    seen_ids: set[str] = set()
    passes_info: list[dict] = []

    for p in range(1, passes + 1):
        if p > 1:
            wait = random.uniform(float(delay_range[0]), float(delay_range[1]))
            console_info(f"Esperando {wait:.0f}s antes de pasada {p}/{passes}…")
            live_wait(wait, f"entre pasadas")
            if rotate_on_pass:
                if use_tor:
                    TOR.new_identity(session=session, aggressive=True)
                    session = create_session(use_tor=True)
                rotate_user_agent(session)
                HUMAN.think_pause(3.0)

        console_section(f"PASADA {p}/{passes}")
        tag = f"_pass{p}" if passes > 1 else ""
        try:
            payload = download_comments_single_pass(
                session, video_id, cfg, sort=sort, max_comments=max_comments,
                max_replies_per_thread=max_replies_per_thread,
                include_replies=include_replies, use_tor=use_tor, tag=tag)
        except Exception as exc:
            console_fail(f"Pasada {p} falló: {exc}")
            passes_info.append({"pass": p, "count": 0, "error": str(exc)})
            continue

        new = 0
        for c in payload.get("comments") or []:
            cid = c.get("id") or ""
            if cid and cid not in seen_ids:
                seen_ids.add(cid); all_comments.append(c); new += 1
        console_ok(f"Pasada {p}: {len(payload.get('comments') or [])} recuperados, {new} nuevos")
        passes_info.append({"pass": p, "count": len(payload.get("comments") or []), "new": new})
        if new == 0 and p > 1:
            console_warn("Sin nuevos en esta pasada.")
        HUMAN.between_ops()

    total_replies = sum(1 + len(c.get("replies") or []) for c in all_comments)
    console_ok(f"TOTAL: {len(all_comments)} top-level · {total_replies} con replies")
    return {
        "video_id": video_id, "sort": sort,
        "total_top_level": len(all_comments), "total_with_replies": total_replies,
        "comments": all_comments, "passes": passes_info,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def flatten_comments(tree: list[dict], parent: Optional[str] = None, depth: int = 0) -> list[dict]:
    rows = []
    for c in tree or []:
        row = dict(c)
        row["parent_id"] = c.get("parent_id") or parent
        row["depth"] = c.get("depth") if c.get("depth") is not None else depth
        replies = row.pop("replies", []) or []
        rows.append(row)
        rows.extend(flatten_comments(replies, row.get("id"), depth + 1))
    return rows


def export_comments(dest: Path, payload: dict) -> None:
    """Escribe JSON/CSV/MD/HTML dentro de comments/."""
    comments_dir = _subdir(dest, "comments")
    comments = payload.get("comments") or []
    flat = flatten_comments(comments)
    save_json(comments_dir / "comments.json", payload)

    with (comments_dir / "comments.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "parent_id", "depth", "author", "author_id", "author_handle",
            "text", "likes", "published_relative", "reply_count",
            "is_pinned", "has_creator_heart", "is_member"], extrasaction="ignore")
        w.writeheader()
        for row in flat:
            w.writerow(row)

    md = [f"# Comentarios `{payload.get('video_id')}`", "",
          f"Total nodos: {len(flat)}", f"Pasadas: {len(payload.get('passes') or [])}", ""]
    for row in flat:
        pad = "  " * int(row.get("depth") or 0)
        md.append(f"{pad}- **{row.get('author')}** ({row.get('likes', 0)}): {row.get('text')}")
    (comments_dir / "comments.md").write_text("\n".join(md), encoding="utf-8")
    (comments_dir / "comments.html").write_text(
        _render_comments_html(payload.get("video_id"), comments), encoding="utf-8")


def _render_comments_html(video_id: str, comments: list[dict]) -> str:
    def node_html(c: dict) -> str:
        kids = "".join(node_html(r) for r in (c.get("replies") or []))
        text = html_lib.escape(str(c.get("text") or ""))
        author = html_lib.escape(str(c.get("author") or "?"))
        likes = int(c.get("likes") or 0)
        pin = " PIN" if c.get("is_pinned") else ""
        heart = " ❤" if c.get("has_creator_heart") else ""
        return (f'<details class="c" open><summary><b>{author}</b> · {likes} ·'
                f'{pin}{heart}</summary><p class="t">{text}</p>{kids}</details>')
    body = "".join(node_html(c) for c in comments)
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Comentarios {html_lib.escape(str(video_id))}</title>
<style>
body{{font:16px system-ui;max-width:900px;margin:2rem auto;background:#0f1115;color:#eee;padding:0 1rem}}
input{{width:100%;padding:.6rem;border-radius:8px;border:0;margin-bottom:1rem}}
details.c{{border-left:2px solid #333;margin:.4rem 0 .4rem .4rem;padding-left:.6rem}}
summary{{cursor:pointer}}
.t{{white-space:pre-wrap;color:#ccc}}
</style></head><body>
<h1>Comentarios {html_lib.escape(str(video_id))}</h1>
<input id="q" placeholder="Buscar…" oninput="filter(this.value)">
<div id="tree">{body}</div>
<script>
function filter(q){{q=(q||'').toLowerCase();
document.querySelectorAll('details.c').forEach(d=>{{
d.style.display = !q || d.innerText.toLowerCase().includes(q) ? '' : 'none';}});}}
</script></body></html>
"""


# ============================================================
# [S10] ANALYTICS — sentiment, topics, grafo, heatmap
# ============================================================

POS_WORDS = {"bueno","great","love","excelente","genial","gracias","best","amazing"}
NEG_WORDS = {"malo","hate","horrible","basura","peor","fake","estafa","terrible","worst"}


def _simple_sentiment(text: str) -> str:
    t = (text or "").lower()
    p = sum(1 for w in POS_WORDS if w in t)
    n = sum(1 for w in NEG_WORDS if w in t)
    return "POS" if p > n else ("NEG" if n > p else "NEU")


def run_analytics(dest: Path, payload: dict, meta: dict, cfg: dict) -> dict:
    """Genera analytics → analytics/ y gráficos → images/."""
    acfg = cfg.get("analytics") or {}
    analytics_dir = _subdir(dest, "analytics")
    images_dir = _subdir(dest, "images")

    flat = flatten_comments(payload.get("comments") or [])
    top = [c for c in flat if int(c.get("depth") or 0) == 0]
    replies = [c for c in flat if int(c.get("depth") or 0) > 0]
    likes = [int(c.get("likes") or 0) for c in flat]
    authors: dict[str, int] = {}
    for c in flat:
        a = c.get("author") or "?"
        authors[a] = authors.get(a, 0) + 1
    top_by_likes = sorted(flat, key=lambda x: int(x.get("likes") or 0), reverse=True)[:20]
    top_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)[:20]

    sentiments = {"POS": 0, "NEG": 0, "NEU": 0}
    analyzer = None
    if acfg.get("sentiment") and PYSENT_AVAILABLE:
        try:
            analyzer = create_sent_analyzer(task="sentiment", lang="es")
        except Exception:
            pass
    for c in flat:
        lab = _simple_sentiment(c.get("text") or "")
        if analyzer:
            try:
                r = analyzer.predict(c.get("text") or "")
                lab = str(getattr(r, "output", lab)).upper()[:3]
                if lab not in sentiments:
                    lab = "NEU"
            except Exception:
                pass
        c["_sent"] = lab
        sentiments[lab] = sentiments.get(lab, 0) + 1

    spam = []
    texts_count: dict[str, int] = {}
    for c in flat:
        tx = (c.get("text") or "").strip().lower()
        if len(re.findall(r"https?://", tx)) >= 5:
            spam.append({"id": c.get("id"), "reason": "many_links"})
        if tx:
            texts_count[tx] = texts_count.get(tx, 0) + 1
    for tx, n in texts_count.items():
        if n >= 3:
            spam.append({"reason": "repeated_text", "n": n, "sample": tx[:80]})

    graph_path = None
    if acfg.get("social_graph") and NETWORKX_AVAILABLE:
        G = nx.DiGraph()
        for c in flat:
            a = c.get("author") or "?"
            G.add_node(a)
            parent = c.get("parent_id")
            if parent:
                parents = [x for x in flat if x.get("id") == parent]
                if parents:
                    G.add_edge(a, parents[0].get("author") or "?")
        if MPL_AVAILABLE and G.number_of_nodes() > 1:
            try:
                plt.figure(figsize=(10, 8))
                pos = nx.spring_layout(G, seed=3)
                nx.draw_networkx(G, pos, node_size=80, font_size=6, arrows=True)
                gp = images_dir / "author_graph.svg"
                plt.axis("off"); plt.tight_layout(); plt.savefig(gp, format="svg"); plt.close()
                graph_path = str(gp)
            except Exception:
                pass

    heat_path = None
    if acfg.get("heatmap") and MPL_AVAILABLE:
        try:
            buckets = {"hoy": 0, "días": 0, "semana": 0, "mes": 0, "año": 0}
            for c in top:
                rel = (c.get("published_relative") or "").lower()
                if any(k in rel for k in ("hora", "minuto", "just now", "ahora")):
                    buckets["hoy"] += 1
                elif "día" in rel or "dia" in rel or "day" in rel:
                    buckets["días"] += 1
                elif "semana" in rel or "week" in rel:
                    buckets["semana"] += 1
                elif "mes" in rel or "month" in rel:
                    buckets["mes"] += 1
                elif "año" in rel or "year" in rel:
                    buckets["año"] += 1
            if sum(buckets.values()) > 0:
                plt.figure(figsize=(8, 3.5))
                plt.bar(list(buckets.keys()), list(buckets.values()), color="#33aaff")
                plt.title("Antigüedad de comentarios top-level"); plt.ylabel("Comentarios")
                hp = images_dir / "heatmap_comments.png"
                plt.tight_layout(); plt.savefig(hp, dpi=110); plt.close()
                heat_path = str(hp)
        except Exception:
            pass

    report = {
        "video_id": payload.get("video_id"), "total": len(flat),
        "top_level": len(top), "replies": len(replies),
        "conversation_ratio": round(len(replies) / max(1, len(top)), 3),
        "likes_sum": sum(likes), "likes_max": max(likes) if likes else 0,
        "top_comments": [{"author": c.get("author"), "likes": c.get("likes"),
                          "text": (c.get("text") or "")[:240]} for c in top_by_likes],
        "top_authors": [{"author": a, "n": n} for a, n in top_authors],
        "sentiment": sentiments, "spam_flags": spam[:50],
        "graph": graph_path, "heatmap": heat_path,
        "passes": payload.get("passes"),
    }
    save_json(analytics_dir / "analytics.json", report)
    save_json(analytics_dir / "sentiment_report.json",
              {"sentiment": sentiments, "engine": "pysentimiento" if analyzer else "lexicon"})
    (analytics_dir / "analytics_report.html").write_text(
        _render_analytics_html(report, meta), encoding="utf-8")
    return report


def _render_analytics_html(report: dict, meta: dict) -> str:
    sent = report.get("sentiment") or {}
    labels = json.dumps(list(sent.keys()))
    values = json.dumps(list(sent.values()))
    title = html_lib.escape(str(meta.get("title") or report.get("video_id")))
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Analytics {title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body{{font:16px system-ui;max-width:960px;margin:2rem auto;background:#111;color:#eee;padding:0 1rem}}
.card{{background:#1c1c22;padding:1rem;border-radius:12px;margin:1rem 0}}
</style></head><body>
<h1>{title}</h1>
<div class="card"><p>Total {report.get("total")} · top {report.get("top_level")} ·
replies {report.get("replies")} · ratio {report.get("conversation_ratio")}</p>
<canvas id="sent" height="120"></canvas></div>
<script>
new Chart(document.getElementById('sent'),
  {{type:'doughnut',data:{{labels:{labels},datasets:[{{data:{values}}}]}}}});
</script></body></html>
"""


# ============================================================
# [S11] EMPAQUETADO — TXT/JSON/CSV/HTML/ZIP
# ============================================================

def slugify(text: str, max_len: int = 40) -> str:
    text = (text or "video").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "_", text).strip("_")
    return (text or "video")[:max_len]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ffmpeg_ok() -> bool:
    return shutil.which("ffmpeg") is not None


def write_leeme(dest: Path, meta: dict, files: Optional[dict] = None) -> None:
    """Índice en la raíz del bundle, describiendo la estructura."""
    lines = [
        "YOUTUBE VAULT — CONTENIDO DEL BUNDLE",
        "=====================================",
        f"id:     {meta.get('id')}",
        f"título: {meta.get('title')}",
        f"canal:  {meta.get('channel')}",
        f"url:    {meta.get('webpage_url')}",
        "",
        "ESTRUCTURA:",
        "  metadata/   → metadata.json (todos los campos)",
        "  video/      → video.mkv, audio.m4a, audio.mp3",
        "  subtitles/  → transcripción srt/vtt/txt/json/md",
        "  comments/   → comments.json / csv / md / html",
        "  analytics/  → analytics.json, sentiment_report.json, html",
        "  images/     → thumbnail, waveform, storyboard, graph, heatmap",
        "",
        "ARCHIVOS GENERADOS:",
    ]
    for k in sorted((files or {}).keys()):
        lines.append(f"  - {k}: {files[k]}")
    lines += [
        "",
        "HUMANIZACIÓN:",
        f"  modo:   {HUMANIZATION_MODE}",
        f"  nivel:  {HUMANIZATION_LEVEL}",
        f"  fatiga: {HUMAN.fatigue:.2f}",
        f"  ops:    {HUMAN.ops_count}",
        "",
        "ADVERTENCIAS:",
        "  * Cookies pueden banear tu cuenta.",
        "  * Respeta copyright y TOS de YouTube.",
    ]
    (dest / "LEEME.txt").write_text("\n".join(lines), encoding="utf-8")


def export_package(dest: Path) -> Path:
    """Comprime el bundle completo respetando su estructura interna."""
    zpath = dest.parent / f"{dest.name}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in dest.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(dest.parent))
    console_ok(f"ZIP: {zpath}")
    return zpath


# ============================================================
# [S12a] UTILIDADES — config, output dir, subdirs, power, tor panel
# ============================================================

def output_dir_for(cfg: dict, video_id: str, title: str) -> Path:
    root = Path((cfg.get("output") or {}).get("dir") or "salidas")
    return ensure_dir(root / f"{video_id}_{slugify(title)}")


def _subdir(root: Path, kind: str) -> Path:
    """Devuelve una subcarpeta estándar dentro del bundle y la crea si no existe."""
    mapping = {
        "video": "video",
        "audio": "video",
        "subtitles": "subtitles",
        "comments": "comments",
        "analytics": "analytics",
        "images": "images",
        "metadata": "metadata",
    }
    return ensure_dir(root / mapping.get(kind, kind))


def load_config() -> dict:
    if CONFIG_PATH.exists() and YAML_AVAILABLE:
        try:
            loaded = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
            cfg = {**DEFAULT_CONFIG}
            for k, v in loaded.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k] = {**cfg[k], **v}
                else:
                    cfg[k] = v
            return cfg
        except Exception as exc:
            logging.warning("config inválido: %s", exc)
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
    return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(cfg: dict) -> None:
    if YAML_AVAILABLE:
        CONFIG_PATH.write_text(
            yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    else:
        CONFIG_PATH.with_suffix(".json").write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def prevent_system_sleep(enable: bool = True) -> None:
    try:
        if sys.platform == "win32":
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            flag = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if enable else 0)
            ctypes.windll.kernel32.SetThreadExecutionState(flag)
    except Exception:
        pass


def tor_status_panel() -> None:
    console_section("ESTADO DE TOR")
    console_kv("SOCKS", f"{TOR.socks_host}:{TOR.socks_port}",
               Color.GREEN if TOR.is_socks_alive() else Color.RED)
    console_kv("ControlPort", f"{TOR.socks_host}:{TOR.control_port}",
               Color.GREEN if TOR.is_control_alive() else Color.RED)
    console_kv("stem", "sí" if STEM_AVAILABLE else "no (pip install stem)")
    circuits = TOR.list_circuits()
    if circuits:
        built = sum(1 for c in circuits if str(getattr(c, "status", "")) in {"BUILT", "EXTENDED"})
        console_kv("Circuitos", f"{built}/{len(circuits)}")
    if TOR._last_ip:
        console_kv("Última IP", TOR._last_ip)
    if TOR._last_rotate:
        console_kv("Última rotación", f"hace {time.time()-TOR._last_rotate:.0f}s")
    console_kv("Modo humanización", HUMANIZATION_MODE)
    console_kv("Nivel", HUMANIZATION_LEVEL)
    console_kv("Fatiga", f"{HUMAN.fatigue:.2f}")


# ============================================================
# [S13] AUTO-REPAIR SYSTEM — autoreparación universal
# ============================================================

class SystemDiagnostic:
    """Resultado de una comprobación de salud del sistema."""
    def __init__(self, name: str, status: str, detail: str, fixable: bool = False):
        self.name = name
        self.status = status        # ok | warn | error
        self.detail = detail
        self.fixable = fixable


class AutoRepairSystem:
    """
    Detecta problemas y repara automáticamente:
      • Tor caído → intenta arrancarlo (tor/tor.exe del PATH)
      • Sesión HTTP corrupta → recrea
      • Cache yt-dlp sucia → limpia
      • Circuitos Tor viejos → NEWNYM
      • Bloqueos repetidos sin Tor → activa Tor automáticamente
    Universal: funciona en Windows / Linux / Mac con o sin Tor instalado.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.repairs_done: list[str] = []
        self.last_diagnostic: list[SystemDiagnostic] = []

    # ---------- Diagnóstico ----------
    def diagnose(self, session: Optional[requests.Session] = None) -> list[SystemDiagnostic]:
        results: list[SystemDiagnostic] = []
        yt = self.cfg.get("youtube") or {}

        # Tor
        if yt.get("use_tor") or yt.get("paranoid_mode"):
            if TOR.is_socks_alive():
                results.append(SystemDiagnostic("Tor SOCKS", "ok",
                    f"{TOR.socks_host}:{TOR.socks_port} responde"))
            else:
                results.append(SystemDiagnostic("Tor SOCKS", "error",
                    f"No responde en {TOR.socks_host}:{TOR.socks_port}", fixable=True))
            if STEM_AVAILABLE:
                if TOR.is_control_alive():
                    results.append(SystemDiagnostic("Tor Control", "ok",
                        f"ControlPort {TOR.control_port} OK"))
                else:
                    results.append(SystemDiagnostic("Tor Control", "warn",
                        "ControlPort no responde (sin rotación)", fixable=True))
            else:
                results.append(SystemDiagnostic("stem", "warn",
                    "No instalado: pip install stem"))

        # Sesión HTTP
        if session is not None:
            ip = get_exit_ip(session)
            if ip:
                results.append(SystemDiagnostic("Sesión HTTP", "ok", f"IP: {ip}"))
            else:
                results.append(SystemDiagnostic("Sesión HTTP", "warn",
                    "No se pudo verificar IP", fixable=True))

        # yt-dlp
        if YTDLP_AVAILABLE:
            results.append(SystemDiagnostic("yt-dlp", "ok", "Disponible"))
        else:
            results.append(SystemDiagnostic("yt-dlp", "error",
                "No instalado: pip install yt-dlp"))

        # ffmpeg
        if ffmpeg_ok():
            try:
                out = subprocess.run(["ffmpeg", "-version"],
                    capture_output=True, text=True, timeout=5)
                v = (out.stdout or "").split("\n")[0][:60] if out.stdout else "OK"
                results.append(SystemDiagnostic("ffmpeg", "ok", v))
            except Exception:
                results.append(SystemDiagnostic("ffmpeg", "warn", "Presente pero con problemas"))
        else:
            results.append(SystemDiagnostic("ffmpeg", "warn", "No en PATH"))

        # Playwright
        results.append(SystemDiagnostic("Playwright",
            "ok" if PLAYWRIGHT_AVAILABLE else "warn",
            "Disponible" if PLAYWRIGHT_AVAILABLE else "No instalado (opcional)"))

        # Whisper
        results.append(SystemDiagnostic("faster-whisper",
            "ok" if WHISPER_AVAILABLE else "warn",
            "Disponible" if WHISPER_AVAILABLE else "No instalado"))

        # Cache yt-dlp
        cache_dir = CACHE_DIR / "ytdlp"
        if cache_dir.exists():
            try:
                size_mb = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file()) / 1e6
                status = "ok" if size_mb < 500 else "warn"
                results.append(SystemDiagnostic("Cache yt-dlp", status,
                    f"{size_mb:.1f} MB", fixable=size_mb > 500))
            except Exception:
                pass

        # Disco
        try:
            _, _, free = shutil.disk_usage(".")
            free_gb = free / 1e9
            results.append(SystemDiagnostic("Disco libre",
                "ok" if free_gb > 5 else "warn", f"{free_gb:.1f} GB"))
        except Exception:
            pass

        self.last_diagnostic = results
        return results

    def print_diagnostic(self) -> None:
        console_section("DIAGNÓSTICO DEL SISTEMA")
        for d in self.last_diagnostic or self.diagnose():
            if d.status == "ok":
                color, mark = Color.GREEN, "✓"
            elif d.status == "warn":
                color, mark = Color.YELLOW, "!"
            else:
                color, mark = Color.RED, "✗"
            fix = f" {Color.DIM}[reparable]{Color.RESET}" if d.fixable else ""
            print(f"  {color}{mark}{Color.RESET} {d.name:<22} {d.detail}{fix}")

    # ---------- Reparaciones ----------
    def repair_tor(self) -> bool:
        """Universal: intenta reconectar o arrancar Tor del PATH."""
        console_info("Reparando Tor…")
        if TOR.is_socks_alive() and TOR.is_control_alive():
            console_ok("Tor ya está OK")
            return True

        # Buscar binario de Tor
        found_bin = None
        for b in ("tor", "tor.exe"):
            if shutil.which(b):
                found_bin = b
                break
        if not found_bin:
            console_warn("Tor no está en PATH")
            console_info("Windows: descarga Tor Expert Bundle → añade tor.exe al PATH")
            console_info("Linux:   sudo apt install tor    |    Mac: brew install tor")
            return False

        try:
            console_info(f"Encontrado {found_bin}, intentando arrancar…")
            if sys.platform == "win32":
                subprocess.Popen([found_bin, "-f", "torrc"],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                subprocess.Popen([found_bin],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(30):
                time.sleep(1)
                if TOR.is_socks_alive():
                    console_ok("Tor arrancado correctamente")
                    self.repairs_done.append("tor_start")
                    return True
            console_warn("Tor no respondió en 30s")
        except Exception as exc:
            console_warn(f"No se pudo arrancar Tor: {exc}")
        return False

    def repair_session(self, session: requests.Session) -> requests.Session:
        """Recrea la sesión HTTP con UA rotado."""
        console_info("Recreando sesión HTTP…")
        use_tor = bool((self.cfg.get("youtube") or {}).get("use_tor"))
        new_session = create_session(use_tor=use_tor)
        rotate_user_agent(new_session)
        console_ok("Sesión renovada")
        self.repairs_done.append("session")
        return new_session

    def repair_ytdlp(self) -> None:
        """Limpia la cache de yt-dlp (útil si hay corrupción o firmas viejas)."""
        console_info("Limpiando cache de yt-dlp…")
        p = CACHE_DIR / "ytdlp"
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            console_ok("Cache limpiada")
            self.repairs_done.append("ytdlp_cache")
        else:
            console_info("No había cache")

    def repair_circuits(self, session: Optional[requests.Session] = None) -> bool:
        """NEWNYM agresivo + reset de stream isolation."""
        if not STEM_AVAILABLE or not TOR.is_control_alive():
            console_warn("No se puede rotar (falta stem/ControlPort)")
            return False
        console_info("Rotando circuitos Tor…")
        TOR.reset_stream_isolation()
        ok = TOR.new_identity(session=session, aggressive=True)
        if ok:
            self.repairs_done.append("circuits")
        return ok

    # ---------- Reparación completa ----------
    def heal_all(self, session: Optional[requests.Session] = None) -> tuple:
        """Ejecuta todas las reparaciones aplicables y verifica el resultado."""
        console_section("AUTO-REPARACIÓN")
        before = self.diagnose(session)
        for d in before:
            if not (d.fixable or d.status == "error"):
                continue
            console_warn(f"Reparando: {d.name}")
            if "SOCKS" in d.name or "Control" in d.name:
                self.repair_tor()
            elif "Sesión" in d.name and session is not None:
                session = self.repair_session(session)
            elif "Cache" in d.name:
                self.repair_ytdlp()

        # NEWNYM por si acaso (solo si Tor está en uso)
        if (self.cfg.get("youtube") or {}).get("use_tor"):
            try:
                self.repair_circuits(session)
            except Exception:
                pass

        after = self.diagnose(session)
        console_section("RESULTADO POST-REPARACIÓN")
        fixed = sum(1 for b, a in zip(before, after) if b.status != "ok" and a.status == "ok")
        console_ok(f"Reparaciones: {len(self.repairs_done)} · Problemas resueltos: {fixed}")
        for d in after:
            mark = "✓" if d.status == "ok" else ("!" if d.status == "warn" else "✗")
            color = Color.GREEN if d.status == "ok" else (
                Color.YELLOW if d.status == "warn" else Color.RED)
            print(f"  {color}{mark}{Color.RESET} {d.name}: {d.detail}")
        return session, after

    # ---------- Auto-activación de Tor ----------
    def auto_activate_tor_if_blocked(self, session: requests.Session,
                                     blocked_count: int = 0) -> tuple:
        """
        Si detecta bloqueos repetidos y Tor NO está activo, lo activa.
        - Si Tor no está corriendo, intenta arrancarlo.
        - Si no está instalado, avisa y continúa sin Tor.
        Devuelve (sesión, activado).
        """
        if (self.cfg.get("youtube") or {}).get("use_tor"):
            return session, True   # ya está activo
        if blocked_count < 2:
            return session, False

        console_warn(f"Bloqueos detectados ({blocked_count}). Activando Tor automáticamente…")

        if not TOR.is_socks_alive():
            console_info("Tor no está corriendo, intentando arrancarlo…")
            if not self.repair_tor():
                console_fail("No se pudo arrancar Tor. Continuando sin él.")
                return session, False

        self.cfg.setdefault("youtube", {})["use_tor"] = True
        new_session = create_session(use_tor=True)
        ip = get_exit_ip(new_session)
        if ip:
            console_ok(f"Tor activado automáticamente. IP: {ip}")
            TOR._last_ip = ip
            self.repairs_done.append("auto_tor_activation")
            return new_session, True
        console_warn("Tor activado pero no se pudo verificar IP")
        return new_session, True


# ============================================================
# [S14] MENÚ AVANZADO — presets, paneles y configuración rica
# ============================================================

PRESETS = {
    "seguro": {
        "descripcion": "Máxima prudencia: Tor ON, humanización pausada, baja concurrencia",
        "youtube": {"use_tor": True, "paranoid_mode": False,
                    "rotate_every_pages": 5, "rotate_ua_every_pages": 2},
        "comments": {"passes": 2, "max_comments": 3000},
        "humanization": {"mode": "pausada", "level": "alto"},
        "download": {"mode": "video", "quality": 1080,
                     "limit_rate": "500K", "concurrent_fragments": 2},
    },
    "equilibrado": {
        "descripcion": "Balance: Tor ON, 4K, humanización equilibrada",
        "youtube": {"use_tor": True, "paranoid_mode": False,
                    "rotate_every_pages": 10, "rotate_ua_every_pages": 3},
        "comments": {"passes": 1, "max_comments": 5000},
        "humanization": {"mode": "equilibrado", "level": "medio"},
        "download": {"mode": "video", "quality": 2160,
                     "limit_rate": "0", "concurrent_fragments": 5},
    },
    "rapido": {
        "descripcion": "Máxima velocidad: sin Tor, humanización rápida",
        "youtube": {"use_tor": False, "paranoid_mode": False,
                    "rotate_every_pages": 20, "rotate_ua_every_pages": 5},
        "comments": {"passes": 1, "max_comments": 5000},
        "humanization": {"mode": "rapida", "level": "bajo"},
        "download": {"mode": "video", "quality": 2160,
                     "limit_rate": "0", "concurrent_fragments": 8},
    },
    "paranoico": {
        "descripcion": "Máximo sigilo: Tor para TODO + sueño simulado",
        "youtube": {"use_tor": True, "paranoid_mode": True,
                    "rotate_every_pages": 3, "rotate_ua_every_pages": 1},
        "comments": {"passes": 3, "max_comments": 2000},
        "humanization": {"mode": "nocturna", "level": "paranoico"},
        "download": {"mode": "video", "quality": 1080,
                     "limit_rate": "200K", "concurrent_fragments": 1},
    },
}


def apply_preset(cfg: dict, preset_name: str) -> dict:
    """Aplica un preset sobre la config actual."""
    preset = PRESETS.get(preset_name)
    if not preset:
        console_warn(f"Preset desconocido: {preset_name}")
        return cfg
    for section, values in preset.items():
        if section == "descripcion":
            continue
        cfg.setdefault(section, {}).update(values)
    console_ok(f"Preset '{preset_name}': {preset['descripcion']}")
    return cfg


def menu_presets(cfg: dict) -> dict:
    """Submenú: aplicar preset rápido."""
    global HUMANIZATION_MODE, HUMANIZATION_LEVEL, HUMAN
    console_section("PRESETS DISPONIBLES")
    for i, (name, p) in enumerate(PRESETS.items(), 1):
        print(f"  {Color.BOLD}{i}{Color.RESET}) {Color.CYAN}{name:<14}{Color.RESET} — {p['descripcion']}")
    try:
        pick = int(input(f"\n{Color.BOLD}Elegir preset [0=cancelar]: {Color.RESET}").strip() or "0")
    except ValueError:
        pick = 0
    if 1 <= pick <= len(PRESETS):
        name = list(PRESETS.keys())[pick - 1]
        cfg = apply_preset(cfg, name)
        save_config(cfg)
        HUMANIZATION_MODE = cfg["humanization"]["mode"]
        HUMANIZATION_LEVEL = cfg["humanization"]["level"]
        HUMAN = Humanizer(level=HUMANIZATION_LEVEL)
    return cfg


def menu_config_tor(cfg: dict) -> dict:
    """Submenú: configuración de Tor."""
    console_section("CONFIGURACIÓN TOR")
    yt = cfg.setdefault("youtube", {})
    console_kv("SOCKS", f"{TOR.socks_host}:{TOR.socks_port}")
    console_kv("ControlPort", f"{TOR.socks_host}:{TOR.control_port}")
    console_kv("Uso de Tor", "sí" if yt.get("use_tor") else "no")
    console_kv("Paranoico", "sí" if yt.get("paranoid_mode") else "no")

    ans = input(f"\n{Color.BOLD}¿Usar Tor? (s/n) [{'s' if yt.get('use_tor') else 'n'}]: {Color.RESET}").strip().lower()
    if ans:
        yt["use_tor"] = ans in {"s", "si", "sí", "y"}
    ans = input(f"{Color.BOLD}¿Paranoico (Tor para TODO)? (s/n) [{'s' if yt.get('paranoid_mode') else 'n'}]: {Color.RESET}").strip().lower()
    if ans:
        yt["paranoid_mode"] = ans in {"s", "si", "sí", "y"}

    rep = input(f"{Color.BOLD}Rotar IP cada N páginas [{yt.get('rotate_every_pages', 10)}]: {Color.RESET}").strip()
    if rep.isdigit():
        yt["rotate_every_pages"] = max(1, int(rep))
    rua = input(f"{Color.BOLD}Rotar UA cada N páginas [{yt.get('rotate_ua_every_pages', 3)}]: {Color.RESET}").strip()
    if rua.isdigit():
        yt["rotate_ua_every_pages"] = max(1, int(rua))

    save_config(cfg)
    return cfg


def menu_config_humanization(cfg: dict) -> dict:
    """Submenú: humanización."""
    global HUMANIZATION_MODE, HUMANIZATION_LEVEL, HUMAN
    console_section("HUMANIZACIÓN")
    h = cfg.setdefault("humanization", {})
    print("  Modos: 1)rápida 2)equilibrada 3)pausada 4)nocturna")
    print(f"  Actual: {HUMANIZATION_MODE}")
    try:
        hm = int(input(f"{Color.BOLD}Modo [Enter=no cambiar]: {Color.RESET}").strip() or "0")
        if 1 <= hm <= 4:
            h["mode"] = {1:"rapida", 2:"equilibrado", 3:"pausada", 4:"nocturna"}[hm]
    except ValueError:
        pass
    print("  Niveles: 1)bajo 2)medio 3)alto 4)paranoico (sueño simulado)")
    print(f"  Actual: {HUMANIZATION_LEVEL}")
    try:
        hl = int(input(f"{Color.BOLD}Nivel [Enter=no cambiar]: {Color.RESET}").strip() or "0")
        if 1 <= hl <= 4:
            h["level"] = {1:"bajo", 2:"medio", 3:"alto", 4:"paranoico"}[hl]
    except ValueError:
        pass
    HUMANIZATION_MODE = h.get("mode", "equilibrado")
    HUMANIZATION_LEVEL = h.get("level", "medio")
    HUMAN = Humanizer(level=HUMANIZATION_LEVEL)
    console_ok(f"Humanización: {HUMANIZATION_MODE} · nivel {HUMANIZATION_LEVEL}")
    save_config(cfg)
    return cfg


def menu_config_download(cfg: dict) -> dict:
    """Submenú: descarga."""
    console_section("DESCARGA")
    d = cfg.setdefault("download", {})
    print("  Modos: video | video_hq | audio | audio_mp3 | subs_only")
    mode = input(f"{Color.BOLD}Modo [{d.get('mode','video')}]: {Color.RESET}").strip()
    if mode:
        d["mode"] = mode
    print("  Calidad: 720 / 1080 / 1440 (2K) / 2160 (4K) / 4320 (8K)")
    q = input(f"{Color.BOLD}Calidad [{d.get('quality', 2160)}]: {Color.RESET}").strip()
    if q.isdigit():
        d["quality"] = int(q)
    pm = input(f"{Color.BOLD}¿Preferir máxima? (s/n) [{'s' if d.get('prefer_max_quality') else 'n'}]: {Color.RESET}").strip().lower()
    if pm:
        d["prefer_max_quality"] = pm in {"s", "si", "sí", "y"}
    lr = input(f"{Color.BOLD}Límite [{d.get('limit_rate','0')}] (0=sin límite): {Color.RESET}").strip()
    if lr:
        d["limit_rate"] = lr
    cf = input(f"{Color.BOLD}Fragmentos concurrentes [{d.get('concurrent_fragments', 5)}]: {Color.RESET}").strip()
    if cf.isdigit():
        d["concurrent_fragments"] = max(1, int(cf))
    save_config(cfg)
    return cfg


def menu_config_comments(cfg: dict) -> dict:
    """Submenú: comentarios."""
    console_section("COMENTARIOS")
    c = cfg.setdefault("comments", {})
    sort = input(f"{Color.BOLD}Sort (top|newest) [{c.get('sort','top')}]: {Color.RESET}").strip()
    if sort in {"top", "newest"}:
        c["sort"] = sort
    mx = input(f"{Color.BOLD}Máx comentarios [{c.get('max_comments', 5000)}]: {Color.RESET}").strip()
    if mx.isdigit():
        c["max_comments"] = int(mx)
    ps = input(f"{Color.BOLD}Nº pasadas [{c.get('passes', 1)}]: {Color.RESET}").strip()
    if ps.isdigit():
        c["passes"] = max(1, int(ps))
    save_config(cfg)
    return cfg


def menu_config_all(cfg: dict) -> dict:
    """Menú completo de reconfiguración por secciones."""
    while True:
        console_section("RECONFIGURAR")
        print("  1) Presets (seguro / equilibrado / rápido / paranoico)")
        print("  2) Tor (uso, rotación IP/UA, paranoico)")
        print("  3) Humanización (modo, nivel)")
        print("  4) Descarga (calidad, modo, límites)")
        print("  5) Comentarios (sort, máximo, pasadas)")
        print("  6) Cookies del navegador")
        print("  7) Ver configuración completa (JSON)")
        print("  0) Volver")
        opt = input(f"\n{Color.BOLD}Opción [0]: {Color.RESET}").strip() or "0"
        if opt == "0":
            return cfg
        if opt == "1":
            cfg = menu_presets(cfg)
        elif opt == "2":
            cfg = menu_config_tor(cfg)
        elif opt == "3":
            cfg = menu_config_humanization(cfg)
        elif opt == "4":
            cfg = menu_config_download(cfg)
        elif opt == "5":
            cfg = menu_config_comments(cfg)
        elif opt == "6":
            ck = input("¿Usar cookies del navegador? (s/n) [n]: ").strip().lower()
            if ck in {"s", "si", "sí"}:
                console_warn("Cookies pueden BANEAR tu cuenta.")
                cfg.setdefault("youtube", {})["use_cookies"] = True
                cfg["youtube"]["cookies_browser"] = input("Navegador [firefox]: ").strip() or "firefox"
            else:
                cfg.setdefault("youtube", {})["use_cookies"] = False
            save_config(cfg)
        elif opt == "7":
            console_section("CONFIG COMPLETA")
            print(json.dumps(cfg, indent=2, ensure_ascii=False))
        else:
            console_warn(f"Opción desconocida: {opt}")


def menu_tor_panel(cfg: dict, session: requests.Session) -> requests.Session:
    """Panel interactivo de Tor con acciones."""
    while True:
        tor_status_panel()
        print("\n  1) Rotar identidad ahora (NEWNYM)")
        print("  2) Verificar IP actual")
        print("  3) Cerrar circuitos viejos")
        print("  4) Intentar arrancar Tor (auto-repair)")
        print("  5) Cambiar puertos SOCKS/Control")
        print("  0) Volver")
        opt = input(f"\n{Color.BOLD}Opción [0]: {Color.RESET}").strip() or "0"
        if opt == "0":
            return session
        if opt == "1":
            if TOR.new_identity(session=session, aggressive=True):
                session = create_session(use_tor=bool(cfg["youtube"].get("use_tor")))
                ip = get_exit_ip(session)
                if ip:
                    TOR._last_ip = ip
                    console_tor(f"IP nueva: {ip}")
        elif opt == "2":
            console_kv("IP de salida", get_exit_ip(session) or "desconocida")
        elif opt == "3":
            n = TOR.close_old_circuits()
            console_ok(f"Circuitos cerrados: {n}")
        elif opt == "4":
            rep = AutoRepairSystem(cfg)
            rep.repair_tor()
        elif opt == "5":
            s = input(f"SOCKS port [{TOR.socks_port}]: ").strip()
            if s.isdigit():
                TOR.socks_port = int(s)
                cfg.setdefault("tor", {})["socks_port"] = int(s)
            c = input(f"ControlPort [{TOR.control_port}]: ").strip()
            if c.isdigit():
                TOR.control_port = int(c)
                cfg.setdefault("tor", {})["control_port"] = int(c)
            save_config(cfg)
            console_ok("Puertos actualizados")
        else:
            console_warn(f"Opción desconocida: {opt}")


def menu_repair(cfg: dict, session: requests.Session) -> requests.Session:
    """Submenú de auto-reparación."""
    rep = AutoRepairSystem(cfg)
    while True:
        console_section("AUTO-REPARACIÓN")
        print("  1) Diagnóstico completo (solo lectura)")
        print("  2) Reparación automática (todo)")
        print("  3) Reparar solo Tor")
        print("  4) Recrear sesión HTTP")
        print("  5) Limpiar cache yt-dlp")
        print("  6) Rotar circuitos (NEWNYM)")
        print("  7) Auto-activar Tor si hay bloqueos")
        print("  0) Volver")
        opt = input(f"\n{Color.BOLD}Opción [0]: {Color.RESET}").strip() or "0"
        if opt == "0":
            return session
        if opt == "1":
            rep.diagnose(session)
            rep.print_diagnostic()
        elif opt == "2":
            session, _ = rep.heal_all(session)
        elif opt == "3":
            rep.repair_tor()
        elif opt == "4":
            session = rep.repair_session(session)
        elif opt == "5":
            rep.repair_ytdlp()
        elif opt == "6":
            rep.repair_circuits(session)
        elif opt == "7":
            session, activated = rep.auto_activate_tor_if_blocked(session, blocked_count=3)
            if activated:
                cfg.setdefault("youtube", {})["use_tor"] = True
                save_config(cfg)
        else:
            console_warn(f"Opción desconocida: {opt}")


# ============================================================
# [S12b] PIPELINE PRINCIPAL + MENÚ
# ============================================================

def process_video(url: str, cfg: dict, session: requests.Session, *,
                  do_download: bool = True, do_transcript: bool = True,
                  do_comments: bool = True, do_analytics: bool = True) -> dict:
    """Pipeline completo: metadata → descarga → transcripción → comentarios → analytics."""
    vid = extract_video_id(url)
    if not vid:
        raise RuntimeError("URL/ID inválido")
    use_tor_meta = bool((cfg.get("youtube") or {}).get("use_tor"))
    prevent_system_sleep(True)
    try:
        meta = extract_metadata(url, cfg, session, use_tor=use_tor_meta)
        dest = output_dir_for(cfg, meta.get("id") or vid, meta.get("title") or "video")

        # metadata → metadata/metadata.json
        save_json(_subdir(dest, "metadata") / "metadata.json", meta)
        download_thumbnail(session, meta, dest)  # escribe en images/

        console_kv("Título", meta.get("title"))
        console_kv("Canal", meta.get("channel"))
        console_kv("Vistas", meta.get("view_count"))
        files: dict[str, str] = {}

        if do_download:
            mode = str((cfg.get("download") or {}).get("mode") or "video")
            if mode != "subs_only":
                dl = download_with_fallback(meta["id"], dest, cfg, session, meta=meta)
                console_ok(f"Descarga {dl.get('source')} / {dl.get('client')}")
                files.update(postprocess_media(dest, mode, meta))
            else:
                console_info("Solo subtítulos: se omite video")

        if do_transcript:
            video_dir = _subdir(dest, "video")
            audio: Optional[Path] = None
            for pat in ("audio.m4a", "audio.mp3", "audio.opus", "audio.ogg", "audio.wav"):
                cand = video_dir / pat
                if cand.exists():
                    audio = cand; break
            if audio is None:
                for pat in ("*.m4a", "*.mp3", "*.opus"):
                    hits = list(video_dir.glob(pat))
                    if hits:
                        audio = hits[0]; break
            try:
                tr = transcribe_audio(audio, dest, cfg, meta["id"])
                console_ok(f"Transcripción {tr}")
            except Exception as exc:
                console_fail(f"Transcripción: {exc}")

        if do_comments and (cfg.get("comments") or {}).get("enabled", True):
            cc = cfg.get("comments") or {}
            payload = download_all_comments(
                session, meta["id"], cfg,
                sort=str(cc.get("sort") or "top"),
                max_comments=int(cc.get("max_comments") or 5000),
                max_replies_per_thread=int(cc.get("max_replies_per_thread") or 50),
                include_replies=bool(cc.get("include_replies", True)),
                use_tor=use_tor_meta)
            export_comments(dest, payload)
            console_ok(f"Comentarios: {payload.get('total_top_level')}")
            if do_analytics:
                run_analytics(dest, payload, meta, cfg)
                console_ok("Analytics listos")

        write_leeme(dest, meta, files)
        export_package(dest)
        HUMAN.between_ops()
        return {"ok": True, "dir": str(dest), "meta": meta, "files": files}
    finally:
        prevent_system_sleep(False)


def iter_playlist_entries(url: str, cfg: dict, limit: Optional[int] = None,
                          use_tor: bool = False) -> list[str]:
    if not YTDLP_AVAILABLE:
        raise RuntimeError("yt-dlp requerido")
    opts = ytdlp_base_opts(cfg, for_video=False)
    opts["extract_flat"] = True
    opts["skip_download"] = True
    if use_tor:
        opts["proxy"] = TOR.stream_isolation_proxy()
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False) or {}
    entries = info.get("entries") or []
    ids = []
    for e in entries:
        if not e:
            continue
        i = e.get("id")
        if i and re.fullmatch(r"[A-Za-z0-9_-]{11}", str(i)):
            ids.append(str(i))
        if limit and len(ids) >= limit:
            break
    return ids


def ask_config(cfg: dict) -> dict:
    """Preguntas iniciales (patrón Wattpad) para configurar todo."""
    global HUMANIZATION_MODE, HUMANIZATION_LEVEL, HUMAN
    console_section("CONFIGURACIÓN INICIAL")

    ans = input(f"{Color.BOLD}¿Usar Tor? (s/n) [{'s' if cfg['youtube']['use_tor'] else 'n'}]: {Color.RESET}").strip().lower()
    if ans:
        cfg["youtube"]["use_tor"] = ans in {"s", "si", "sí", "y", "yes"}

    par = input(f"{Color.BOLD}¿Modo paranoico (Tor para TODO, video incluido)? (s/n) [n]: {Color.RESET}").strip().lower()
    if par:
        cfg["youtube"]["paranoid_mode"] = par in {"s", "si", "sí", "y", "yes"}

    # --- Aviso claro sobre Tor ---
    if cfg["youtube"]["use_tor"]:
        if not TOR.is_socks_alive():
            console_warn(f"Tor no está corriendo en {TOR.socks_host}:{TOR.socks_port}")
            console_info("Continuando SIN Tor.")
            console_info("Para activarlo: menú 9 → 'Intentar arrancar Tor' | o instalar Tor Expert Bundle")
            cfg["youtube"]["use_tor"] = False
        elif not STEM_AVAILABLE:
            console_warn("stem no instalado → Tor sin rotación de IP")
            console_info("Instala con: pip install stem")
            console_info("Continuando con Tor SIN rotación de IP.")
        elif not TOR.is_control_alive():
            console_warn("ControlPort 9051 no responde → Tor sin rotación")
            console_info("Continúa sin rotación. Verifica que ControlPort esté abierto en torrc.")
        else:
            console_ok("Tor OK con rotación de IP")

    rep = input(f"{Color.BOLD}Rotar IP cada N páginas de comentarios [10]: {Color.RESET}").strip()
    if rep.isdigit():
        cfg["youtube"]["rotate_every_pages"] = max(1, int(rep))
    rua = input(f"{Color.BOLD}Rotar User-Agent cada N páginas [3]: {Color.RESET}").strip()
    if rua.isdigit():
        cfg["youtube"]["rotate_ua_every_pages"] = max(1, int(rua))

    passes = input(f"{Color.BOLD}Nº de pasadas de comentarios (re-visualizaciones) [1]: {Color.RESET}").strip()
    if passes.isdigit():
        cfg["comments"]["passes"] = max(1, int(passes))
    if cfg["comments"]["passes"] > 1:
        console_warn(f"Multi-pasada activa: {cfg['comments']['passes']} pasadas con rotación entre ellas.")

    console_section("HUMANIZACIÓN")
    print("  1) Rápida   2) Equilibrada   3) Pausada   4) Nocturna")
    try:
        hm = int(input(f"{Color.BOLD}Modo [2]: {Color.RESET}").strip() or "2")
    except ValueError:
        hm = 2
    cfg["humanization"]["mode"] = {1:"rapida",2:"equilibrado",3:"pausada",4:"nocturna"}.get(hm, "equilibrado")

    print("  Nivel: 1)bajo 2)medio 3)alto 4)paranoico (sueño simulado)")
    try:
        hl = int(input(f"{Color.BOLD}Nivel [2]: {Color.RESET}").strip() or "2")
    except ValueError:
        hl = 2
    cfg["humanization"]["level"] = {1:"bajo",2:"medio",3:"alto",4:"paranoico"}.get(hl, "medio")

    HUMANIZATION_MODE = cfg["humanization"]["mode"]
    HUMANIZATION_LEVEL = cfg["humanization"]["level"]
    HUMAN = Humanizer(level=HUMANIZATION_LEVEL)
    console_ok(f"Humanización: {HUMANIZATION_MODE} · nivel {HUMANIZATION_LEVEL}")

    console_section("CALIDAD DE DESCARGA")
    print("  Modos: video | video_hq | audio | audio_mp3 | subs_only")
    mode = input(f"{Color.BOLD}Modo [{cfg['download']['mode']}]: {Color.RESET}").strip()
    if mode:
        cfg["download"]["mode"] = mode
    q = input(f"{Color.BOLD}Calidad máx (720/1080/1440/2160/4320) [{cfg['download']['quality']}]: {Color.RESET}").strip()
    if q.isdigit():
        cfg["download"]["quality"] = int(q)
    pm = input(f"{Color.BOLD}¿Máxima calidad disponible? (s/n) [s]: {Color.RESET}").strip().lower() or "s"
    cfg["download"]["prefer_max_quality"] = pm in {"s", "si", "sí", "y", "yes"}
    lr = input(f"{Color.BOLD}Límite [{cfg['download']['limit_rate']}] (0=sin límite): {Color.RESET}").strip()
    if lr:
        cfg["download"]["limit_rate"] = lr

    mx = input(f"{Color.BOLD}Máx comentarios top-level [{cfg['comments']['max_comments']}]: {Color.RESET}").strip()
    if mx.isdigit():
        cfg["comments"]["max_comments"] = int(mx)

    ck = input(f"{Color.BOLD}¿Usar cookies del navegador? (s/n) [n] — PUEDE BANEAR: {Color.RESET}").strip().lower()
    if ck in {"s", "si", "sí"}:
        console_warn("Las cookies pueden BANEAR tu cuenta.")
        cfg["youtube"]["use_cookies"] = True
        cfg["youtube"]["cookies_browser"] = input("Navegador [firefox]: ").strip() or "firefox"
    else:
        cfg["youtube"]["use_cookies"] = False

    save_config(cfg)
    console_ok("Configuración guardada")
    return cfg


def print_menu() -> None:
    console_section("MENÚ PRINCIPAL")
    print("  1)  Procesar 1 video (metadata + descarga 4K + transcripción + comentarios)")
    print("  2)  Descargar playlist completa")
    print("  3)  Descargar canal (últimos N)")
    print("  4)  Solo transcripción")
    print("  5)  Solo subtítulos")
    print("  6)  Solo comentarios (multi-pasada + analytics)")
    print("  7)  Analytics desde carpeta")
    print("  8)  Reconfigurar (presets, Tor, humanización, descarga, comentarios)")
    print("  9)  Panel de Tor (rotar identidad, circuitos, puertos)")
    print(" 10)  Auto-reparación (diagnóstico + fixes)")
    print(" 11)  Demo navegador anónimo (Chromium + Tor + stealth)")
    print(" 12)  Ver configuración actual")
    print(" 13)  Salir")


def _handle_blocks(session, cfg, rep_sys, consecutive_blocks: int):
    """
    Detecta bloqueos y dispara auto-reparación + auto-activación de Tor.
    Universal: se usa desde cualquier flujo (video, playlist, canal).
    """
    consecutive_blocks += 1
    console_warn(f"Bloqueo detectado #{consecutive_blocks}")
    session, activated = rep_sys.auto_activate_tor_if_blocked(
        session, blocked_count=consecutive_blocks)
    if activated:
        cfg.setdefault("youtube", {})["use_tor"] = True
        save_config(cfg)
        rotate_user_agent(session)
    return session, consecutive_blocks


def main() -> None:
    banner()
    console_warn("Cookies pueden banear. Respeta TOS de YouTube.")
    if not YTDLP_AVAILABLE:
        console_fail("Falta yt-dlp: pip install yt-dlp")
    if not ffmpeg_ok():
        console_warn("ffmpeg no en PATH: merge/waveform limitados")
    if not STEM_AVAILABLE:
        console_warn("stem no instalado: sin rotación Tor")
    if not PLAYWRIGHT_AVAILABLE:
        console_warn("Playwright no instalado: navegador anónimo deshabilitado")
    if not SOCKS_AVAILABLE:
        console_warn("PySocks no instalado: pip install pysocks")

    cfg = load_config()
    cfg = ask_config(cfg)
    use_tor = bool(cfg["youtube"].get("use_tor"))
    session = create_session(use_tor=use_tor)
    if use_tor:
        ip = get_exit_ip(session)
        if ip:
            TOR._last_ip = ip
            console_tor(f"IP salida Tor: {ip}")

    rep_sys = AutoRepairSystem(cfg)

    while True:
        print_menu()
        opt = input(f"\n{Color.BOLD}Opción [1]: {Color.RESET}").strip() or "1"

        if opt in {"13", "q", "salir"}:
            print(f"{Color.CYAN}¡Hasta luego!{Color.RESET}")
            break
        try:
            # --- Menús de configuración ---
            if opt == "8":
                cfg = menu_config_all(cfg)
                use_tor = bool(cfg["youtube"].get("use_tor"))
                session = create_session(use_tor=use_tor)
                continue
            if opt == "9":
                session = menu_tor_panel(cfg, session)
                continue
            if opt == "10":
                session = menu_repair(cfg, session)
                continue
            if opt == "11":
                console_section("DEMO NAVEGADOR ANÓNIMO")
                try:
                    result = perform_browser_read("https://www.youtube.com/",
                                                   use_tor=TOR.available(),
                                                   headless=False, scroll_steps=5)
                    if result.get("success"):
                        console_ok(f"Método: {result.get('method')}")
                    else:
                        console_warn(f"Fallo: {result.get('error')}")
                except Exception as exc:
                    console_fail(str(exc))
                continue
            if opt == "12":
                console_section("CONFIGURACIÓN ACTUAL")
                print(json.dumps(cfg, indent=2, ensure_ascii=False))
                console_kv("Humanización", HUMANIZATION_MODE)
                console_kv("Nivel", HUMANIZATION_LEVEL)
                console_kv("Fatiga", f"{HUMAN.fatigue:.2f}")
                console_kv("Ops sesión", HUMAN.ops_count)
                continue

            # --- Utilidades ---
            if opt == "7":
                folder = Path(input("Carpeta del bundle: ").strip())
                payload_path = folder / "comments" / "comments.json"
                if not payload_path.exists():
                    payload_path = folder / "comments.json"
                meta_path = folder / "metadata" / "metadata.json"
                if not meta_path.exists():
                    meta_path = folder / "metadata.json"
                payload = load_json(payload_path, {})
                meta = load_json(meta_path, {})
                if payload:
                    run_analytics(folder, payload, meta, cfg)
                    console_ok("Analytics regenerados")
                else:
                    console_fail("No se encontró comments.json")
                continue
            if opt == "4":
                folder = Path(input("Carpeta del bundle: ").strip())
                vid = input("video_id: ").strip() or folder.name.split("_")[0]
                video_dir = folder / "video" if (folder / "video").exists() else folder
                audio = None
                for pat in ("audio.*", "*.m4a", "*.mp3", "*.mp4"):
                    hits = list(video_dir.glob(pat))
                    if hits:
                        audio = hits[0]; break
                if audio:
                    transcribe_audio(audio, folder, cfg, vid)
                    console_ok("Transcripción lista")
                else:
                    console_fail("Sin audio/video")
                continue
            if opt == "5":
                url = input(f"{Color.BOLD}URL/ID: {Color.RESET}").strip()
                vid = extract_video_id(url)
                if not vid:
                    console_fail("ID inválido"); continue
                segs = fetch_youtube_subs(vid)
                if not segs:
                    console_fail("Sin subtítulos"); continue
                root = Path((cfg.get("output") or {}).get("dir") or "salidas")
                dest = ensure_dir(root / f"{vid}_subs")
                segs2 = [{"start": float(x.get("start") or 0),
                          "duration": float(x.get("duration") or 0),
                          "end": float(x.get("start") or 0) + float(x.get("duration") or 0),
                          "text": x.get("text") or ""} for x in segs]
                write_transcript_files(dest, segs2, "youtube-transcript-api", vid)
                console_ok(f"Subs en {dest}")
                continue

            # --- Procesamiento (auto-reparación integrada) ---
            if opt == "1":
                url = input(f"{Color.BOLD}URL/ID: {Color.RESET}").strip()
                try:
                    process_video(url, cfg, session)
                except Exception as exc:
                    if any(m in str(exc).lower() for m in YOUTUBE_BOT_MARKERS):
                        console_warn("Bloqueo detectado → auto-reparación")
                        session, _ = _handle_blocks(session, cfg, rep_sys, 2)
                        use_tor = bool(cfg["youtube"].get("use_tor"))
                    else:
                        raise
            elif opt == "2":
                url = input(f"{Color.BOLD}URL playlist: {Color.RESET}").strip()
                ids = iter_playlist_entries(url, cfg, use_tor=use_tor)
                console_info(f"{len(ids)} videos")
                blocks = 0
                for i, vid in enumerate(ids, 1):
                    console_section(f"{i}/{len(ids)} {vid}")
                    try:
                        process_video(vid, cfg, session)
                        blocks = 0
                    except Exception as exc:
                        if any(m in str(exc).lower() for m in YOUTUBE_BOT_MARKERS):
                            session, blocks = _handle_blocks(session, cfg, rep_sys, blocks)
                            use_tor = bool(cfg["youtube"].get("use_tor"))
                        else:
                            raise
                    if i < len(ids):
                        time.sleep(inter_read_delay(use_tor))
            elif opt == "3":
                url = input(f"{Color.BOLD}URL canal: {Color.RESET}").strip()
                n = input("Últimos N [10]: ").strip() or "10"
                ids = iter_playlist_entries(url, cfg, limit=int(n), use_tor=use_tor)
                console_info(f"{len(ids)} videos")
                blocks = 0
                for i, vid in enumerate(ids, 1):
                    console_section(f"{i}/{len(ids)} {vid}")
                    try:
                        process_video(vid, cfg, session)
                        blocks = 0
                    except Exception as exc:
                        if any(m in str(exc).lower() for m in YOUTUBE_BOT_MARKERS):
                            session, blocks = _handle_blocks(session, cfg, rep_sys, blocks)
                            use_tor = bool(cfg["youtube"].get("use_tor"))
                        else:
                            raise
                    if i < len(ids):
                        time.sleep(inter_read_delay(use_tor))
            elif opt == "6":
                url = input(f"{Color.BOLD}URL/ID: {Color.RESET}").strip()
                process_video(url, cfg, session, do_download=False, do_transcript=False)
            else:
                console_warn(f"Opción desconocida: {opt}")

        except KeyboardInterrupt:
            console_warn("Cancelado (Ctrl+C)")
        except Exception as exc:
            logging.exception("flujo")
            console_fail(str(exc))
            if input("¿Intentar auto-reparación? (s/n) [s]: ").strip().lower() in {"", "s", "si", "sí"}:
                session, _ = rep_sys.heal_all(session)

        again = input(f"{Color.BOLD}¿Otro? (s/n) [s]: {Color.RESET}").strip().lower() or "s"
        if again not in {"s", "si", "sí", "y"}:
            break

    TOR.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        try:
            prevent_system_sleep(False); TOR.close()
        except Exception:
            pass

#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════
#  BOOTSTRAP  —  transparent private environment
#
#  On first run: creates ~/.unify/env/, installs all Python deps,
#  re-launches itself inside that env.  Never touches system Python.
#  On every run after: instant re-exec into the ready environment.
#
#  The only thing you ever need to run:  python3 unify.py
#  No pip, no source, no --break-system-packages required.
# ══════════════════════════════════════════════════════════════════
import sys, os, subprocess, shutil

# ── Private environment ───────────────────────────────────────────
_ENV_DIR    = os.path.join(os.path.expanduser("~"), ".unify", "env")
_ENV_MARKER = os.path.join(_ENV_DIR, ".ready")   # written after successful install

def _env_python():
    """Return path to the Python executable inside our managed env."""
    if sys.platform == "win32":
        return os.path.join(_ENV_DIR, "Scripts", "python.exe")
    return os.path.join(_ENV_DIR, "bin", "python3")

def _already_in_env():
    """True when we are already running inside our managed venv."""
    return os.path.normcase(sys.executable).startswith(
        os.path.normcase(os.path.normpath(_ENV_DIR))
    )

# ── Only do setup work when we are NOT yet in the managed env ─────
if not _already_in_env():

    def _run(*cmd):
        """Run a command quietly; return True on success."""
        try:
            r = subprocess.run(list(cmd), capture_output=True)
            return r.returncode == 0
        except FileNotFoundError:
            return False

    def _detect_pm():
        for bin_, name in [
            ("apt-get","apt"), ("dnf","dnf"), ("pacman","pacman"),
            ("zypper","zypper"), ("brew","brew"),
        ]:
            if shutil.which(bin_):
                return name
        return None

    _PM = _detect_pm()

    # ── Step 1: make sure venv module exists ─────────────────────
    try:
        import venv as _v  # noqa: F401
    except ImportError:
        print("[unify] Installing venv module …", flush=True)
        if _PM == "apt":
            _pyv = f"python{sys.version_info.major}.{sys.version_info.minor}"
            _run("sudo","apt-get","install","-y",f"{_pyv}-venv","python3-venv")
        elif _PM == "pacman":
            _run("sudo","pacman","-S","--noconfirm","python")
        elif _PM == "dnf":
            _run("sudo","dnf","install","-y","python3")

    # ── Step 2: create the env (once) ────────────────────────────
    _vpy = _env_python()
    if not os.path.isfile(_vpy):
        print(f"[unify] Creating private environment at {_ENV_DIR} …", flush=True)
        os.makedirs(os.path.dirname(_ENV_DIR), exist_ok=True)
        ok = _run(sys.executable, "-m", "venv", _ENV_DIR)
        if not ok:
            # Some minimal installs need --without-pip + manual ensurepip
            _run(sys.executable, "-m", "venv", "--without-pip", _ENV_DIR)
            _run(_vpy, "-m", "ensurepip", "--upgrade")
        if not os.path.isfile(_vpy):
            print("[unify] ✗ Could not create Python environment.")
            print("  On Arch:  sudo pacman -S python")
            print("  On Debian/Ubuntu/Mint:  sudo apt install python3-venv")
            sys.exit(1)

    # ── Step 3: install Python deps into the env (once) ──────────
    if not os.path.isfile(_ENV_MARKER):
        print("[unify] Installing dependencies — this happens once …", flush=True)
        _pkgs = ["requests", "rich", "ytmusicapi", "yt-dlp"]
        ok = _run(_vpy, "-m", "pip", "install", "-q", *_pkgs)
        if not ok:
            # pip inside the fresh venv failed — upgrade pip first then retry
            _run(_vpy, "-m", "pip", "install", "-q", "--upgrade", "pip")
            ok = _run(_vpy, "-m", "pip", "install", "-q", *_pkgs)
        if not ok:
            print("[unify] ✗ Dependency install failed.")
            print(f"  Try manually:  {_vpy} -m pip install {' '.join(_pkgs)}")
            sys.exit(1)
        open(_ENV_MARKER, "w").close()
        print("[unify] All set!\n", flush=True)

    # ── Auto-update ytmusicapi + yt-dlp once per day ─────────────
    # These break when YouTube changes their internal API.
    # Silently upgrading in the background means users get fixes
    # automatically without ever needing to run pip manually.
    _UPDATE_STAMP = os.path.join(_ENV_DIR, ".last_update")
    import time as _t
    _needs_update = True
    if os.path.isfile(_UPDATE_STAMP):
        try:
            _needs_update = (_t.time() - os.path.getmtime(_UPDATE_STAMP)) > 86400
        except:
            pass
    if _needs_update:
        import threading as _thr
        def _bg_update():
            try:
                _run(_vpy, "-m", "pip", "install", "-q", "--upgrade",
                     "ytmusicapi", "yt-dlp")
                open(_UPDATE_STAMP, "w").close()
            except:
                pass
        _thr.Thread(target=_bg_update, daemon=True).start()

    # ── Step 4: install / locate mpv (system binary) ─────────────
    _MPV = "mpv.exe" if sys.platform == "win32" else "mpv"
    if not shutil.which(_MPV):
        print("[unify] mpv not found — trying to install …", flush=True)
        _done = False

        if sys.platform == "win32":
            # ── winget ───────────────────────────────────────────
            for _id in ["Mpv.Mpv", "mpv", "shinchiro.mpv"]:
                print(f"[unify] Trying: winget install --id {_id} …", flush=True)
                _r = subprocess.run(
                    ["winget","install","--silent","--accept-package-agreements",
                     "--accept-source-agreements","--id",_id],
                    capture_output=True, text=True
                )
                print(f"[unify]   exit={_r.returncode}", flush=True)
                if _r.returncode in (0, -1978335189, 0x8A150011):
                    _done = True; break

            # ── scoop (auto-install if missing) ──────────────────
            if not _done:
                if not shutil.which("scoop"):
                    print("[unify] Installing scoop …", flush=True)
                    try:
                        _ps = (
                            "Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force; "
                            "Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression"
                        )
                        _sr = subprocess.run(
                            ["powershell", "-NoProfile", "-Command", _ps],
                            capture_output=True, text=True
                        )
                        print(f"[unify]   scoop install exit={_sr.returncode}", flush=True)
                        _scoop_dir = os.path.join(os.environ.get("USERPROFILE",""), "scoop", "shims")
                        if os.path.isdir(_scoop_dir):
                            os.environ["PATH"] = _scoop_dir + os.pathsep + os.environ.get("PATH","")
                    except Exception as _se:
                        print(f"[unify]   scoop install failed: {_se}", flush=True)

                # scoop must always be invoked via PowerShell — it's a PS script, not an exe
                _scoop_ps = (
                    "scoop install mpv"
                )
                print("[unify] Trying: scoop install mpv …", flush=True)
                _r2 = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", _scoop_ps],
                    capture_output=True, text=True
                )
                print(f"[unify]   exit={_r2.returncode}", flush=True)
                _done = _r2.returncode == 0
                if _done:
                    _scoop_shims = os.path.join(os.environ.get("USERPROFILE",""), "scoop", "shims")
                    if os.path.isdir(_scoop_shims):
                        os.environ["PATH"] = _scoop_shims + os.pathsep + os.environ.get("PATH","")

            # ── choco ────────────────────────────────────────────
            if not _done and shutil.which("choco"):
                print("[unify] Trying: choco install mpv …", flush=True)
                _done = subprocess.run(["choco","install","mpv","-y"],
                                       capture_output=True).returncode == 0

            # ── direct download (.7z) ─────────────────────────────
            if not _done:
                import urllib.request, tempfile as _tf, json as _j

                def _dl_progress(count, block, total):
                    if total > 0:
                        pct = min(100, int(count * block * 100 / total))
                        print(f"\r[unify] Downloading … {pct}%   ", end="", flush=True)

                _mpv_dir = os.path.join(
                    os.environ.get("LOCALAPPDATA", _tf.gettempdir()), "mpv"
                )
                os.makedirs(_mpv_dir, exist_ok=True)
                _dl_url = None
                _dl_name = None

                for _repo in ["shinchiro/mpv-winbuild-cmake", "zhongfly/mpv-winbuild"]:
                    try:
                        _api = f"https://api.github.com/repos/{_repo}/releases/latest"
                        print(f"[unify] Checking {_api} …", flush=True)
                        _req = urllib.request.Request(
                            _api, headers={"User-Agent": "unify-music-player"})
                        with urllib.request.urlopen(_req, timeout=15) as _resp:
                            _rel = _j.loads(_resp.read())
                        print(f"[unify]   release: {_rel.get('tag_name','?')}  ({len(_rel.get('assets',[]))} assets)", flush=True)
                        for _a in _rel.get("assets", []):
                            _n = _a["name"]
                            # pick: x86_64, .7z or .zip, not debug/dev/lgpl/v3/ffmpeg/aarch
                            if (("x86_64" in _n or "x64" in _n)
                                    and _n.endswith((".7z", ".zip"))
                                    and not any(x in _n for x in
                                                ("debug","dev","lgpl","v3","ffmpeg","aarch"))):
                                _dl_url  = _a["browser_download_url"]
                                _dl_name = _n
                                print(f"[unify]   ✓ selected: {_n}", flush=True)
                                break
                        if _dl_url:
                            break
                    except Exception as _e:
                        print(f"[unify]   API error: {_e}", flush=True)

                if _dl_url:
                    _ext  = ".7z" if _dl_name.endswith(".7z") else ".zip"
                    _arch = os.path.join(_tf.gettempdir(), f"mpv-win{_ext}")
                    try:
                        print(f"[unify] Downloading {_dl_name} …", flush=True)
                        urllib.request.urlretrieve(_dl_url, _arch, _dl_progress)
                        print(f"\n[unify] Extracting to {_mpv_dir} …", flush=True)

                        if _ext == ".7z":
                            # py7zr doesn't support BCJ2 compression used by these archives.
                            # Download 7zr.exe (official standalone 7-Zip CLI, ~600KB) instead.
                            _7zr = os.path.join(_tf.gettempdir(), "7zr.exe")
                            if not os.path.isfile(_7zr):
                                print("[unify] Downloading 7zr.exe for extraction …", flush=True)
                                urllib.request.urlretrieve(
                                    "https://www.7-zip.org/a/7zr.exe", _7zr
                                )
                            print(f"[unify] Extracting with 7zr.exe …", flush=True)
                            _er = subprocess.run(
                                [_7zr, "e", _arch, "-o" + _mpv_dir,
                                 "*.exe", "*.dll", "-r", "-y"],
                                capture_output=True, text=True
                            )
                            if _er.returncode != 0:
                                raise RuntimeError(
                                    f"7zr extraction failed (exit {_er.returncode}):\n{_er.stderr}"
                                )
                        else:
                            import zipfile
                            with zipfile.ZipFile(_arch) as _zf:
                                _names2 = _zf.namelist()
                                _prefix3 = ""
                                for _nm3 in _names2:
                                    if _nm3.endswith("mpv.exe"):
                                        _prefix3 = _nm3[: _nm3.rfind("/") + 1]
                                        break
                                for _nm3 in _names2:
                                    if (os.path.splitext(_nm3)[1].lower() in (".exe",".dll")
                                            and _nm3.startswith(_prefix3)):
                                        _base3 = os.path.basename(_nm3)
                                        if _base3:
                                            with _zf.open(_nm3) as _s3, \
                                                 open(os.path.join(_mpv_dir,_base3),"wb") as _d3:
                                                _d3.write(_s3.read())

                        os.remove(_arch)
                        _mpv_exe = os.path.join(_mpv_dir, "mpv.exe")
                        print(f"[unify] mpv.exe present: {os.path.isfile(_mpv_exe)}", flush=True)
                        os.environ["PATH"] = _mpv_dir + os.pathsep + os.environ.get("PATH","")
                        try:
                            import winreg
                            _rk = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment",
                                                 0, winreg.KEY_READ | winreg.KEY_WRITE)
                            _cur2, _ = winreg.QueryValueEx(_rk, "PATH")
                            if _mpv_dir not in _cur2:
                                winreg.SetValueEx(_rk,"PATH",0,winreg.REG_EXPAND_SZ,
                                                  _cur2+";"+_mpv_dir)
                            winreg.CloseKey(_rk)
                            print("[unify] Added mpv to user PATH.", flush=True)
                        except Exception as _re:
                            print(f"[unify]   Registry update skipped: {_re}", flush=True)
                        _done = os.path.isfile(_mpv_exe)
                        # Remove .ready so next run rebuilds venv with py7zr included
                        if _done and os.path.isfile(_ENV_MARKER):
                            try: os.remove(_ENV_MARKER)
                            except: pass
                    except Exception as _e:
                        import traceback
                        print(f"\n[unify] Download/extract error: {_e}", flush=True)
                        traceback.print_exc()
                        try: os.remove(_arch)
                        except: pass
                else:
                    print("[unify] No suitable asset found on GitHub.", flush=True)


        elif _PM == "apt":
            _done = _run("sudo","apt-get","install","-y","mpv")
        elif _PM == "dnf":
            _done = _run("sudo","dnf","install","-y","mpv")
        elif _PM == "pacman":
            _done = _run("sudo","pacman","-S","--noconfirm","mpv")
        elif _PM == "zypper":
            _done = _run("sudo","zypper","--non-interactive","install","mpv")
        elif _PM == "brew":
            _done = _run("brew","install","mpv")

        if not _done or not shutil.which(_MPV):
            print("\n[unify] Could not auto-install mpv. Install it manually:\n")
            if sys.platform == "win32":
                print("  winget install Mpv.Mpv")
                print("  — or —  scoop install mpv  (https://scoop.sh)")
                print("  — or —  https://sourceforge.net/projects/mpv-player-windows/")
            elif _PM == "apt":    print("  sudo apt install mpv")
            elif _PM == "dnf":   print("  sudo dnf install mpv")
            elif _PM == "pacman": print("  sudo pacman -S mpv")
            elif _PM == "zypper": print("  sudo zypper install mpv")
            elif _PM == "brew":   print("  brew install mpv")
            else:                 print("  https://mpv.io/installation/")
            sys.exit(1)
        print("[unify] mpv ready.\n", flush=True)

    # ── Step 5: re-exec as managed-env Python (replaces this process) ──
    os.execv(_vpy, [_vpy] + sys.argv)
    # os.execv never returns — everything below only runs inside the env

# ══════════════════════════════════════════════════════════════════
#  We are now running inside ~/.unify/env/ — all packages available
# ══════════════════════════════════════════════════════════════════

# ── yt-dlp binary: prefer the one inside our managed env ──────────
def _find_ytdlp_bin():
    _IS_WIN = sys.platform == "win32"
    # 1. inside our own env (most reliable)
    _name = "yt-dlp.exe" if _IS_WIN else "yt-dlp"
    _sub  = "Scripts" if _IS_WIN else "bin"
    _c = os.path.join(_ENV_DIR, _sub, _name)
    if os.path.isfile(_c):
        return _c
    # 2. on PATH
    return shutil.which(_name)

_YTDLP_BIN = _find_ytdlp_bin()

# Inject its directory into PATH so mpv can find it as a subprocess
_MPV_ENV = dict(os.environ)
if _YTDLP_BIN:
    _d = os.path.dirname(_YTDLP_BIN)
    if _d not in _MPV_ENV.get("PATH",""):
        _MPV_ENV["PATH"] = _d + os.pathsep + _MPV_ENV.get("PATH","")

import os, sys, time, subprocess, socket, json, requests, re, threading, platform, tempfile
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.layout import Layout
from rich.prompt import Prompt

IS_WINDOWS = sys.platform == "win32"
IS_MAC     = sys.platform == "darwin"
IS_LINUX   = sys.platform.startswith("linux")

def _sp_run(*cmd):
    """subprocess.run wrapper safe to call from app code (unlike bootstrap _run)."""
    try:
        return subprocess.run(list(cmd), capture_output=True, text=True)
    except FileNotFoundError:
        class _R:
            returncode = 127
            stdout = stderr = ""
        return _R()

console = Console()
PLAYLIST_FILE = os.path.expanduser("~/.config/unify_playlists.json")

# ── ytmusicapi: lazy init with graceful fallback ───────────────────
# If YTMusic() fails (YouTube changed their API), we fall back to
# yt-dlp's built-in search so the app keeps working.
_yt        = None   # YTMusic instance, or None if broken
_yt_broken = False  # set True after first init failure

def _init_yt():
    global _yt, _yt_broken
    if _yt is not None or _yt_broken:
        return
    try:
        from ytmusicapi import YTMusic
        _yt = YTMusic()
    except Exception as _e:
        _yt_broken = True

def _ytdlp_search(query, limit=20):
    """yt-dlp based search — completely independent from ytmusicapi."""
    try:
        results = []
        cmd = [
            _YTDLP_BIN or "yt-dlp",
            f"ytsearch{limit}:{query}",
            "--print", "%(id)s\t%(title)s\t%(uploader)s",
            "--no-playlist", "--quiet", "--no-warnings",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        for line in r.stdout.strip().splitlines():
            parts = line.split("\t", 2)
            if len(parts) == 3:
                vid_id, title, artist = parts
                if vid_id:
                    results.append({"id": vid_id, "title": title, "artist": artist})
        return results
    except Exception:
        return []

def _search(query, limit=20):
    """
    Search for songs. Tries ytmusicapi first (better metadata),
    falls back to yt-dlp search if ytmusicapi is broken/unavailable.
    Returns list of {id, title, artist} dicts.
    """
    global _yt, _yt_broken
    _init_yt()
    seen_ids = set()
    merged   = []

    if _yt is not None:
        # primary: ytmusicapi
        try:
            top = _yt.search(query, limit=1)
            for r in top:
                if r.get("videoId") and r["videoId"] not in seen_ids:
                    artists = r.get("artists") or [{}]
                    merged.append({"id": r["videoId"], "title": r["title"],
                                   "artist": artists[0].get("name", "")})
                    seen_ids.add(r["videoId"])
        except Exception:
            pass
        try:
            raw = _yt.search(query, filter="songs", limit=limit)
            for r in raw:
                if r.get("videoId") and r["videoId"] not in seen_ids:
                    artists = r.get("artists") or [{}]
                    merged.append({"id": r["videoId"], "title": r["title"],
                                   "artist": artists[0].get("name", "")})
                    seen_ids.add(r["videoId"])
        except Exception as e:
            # ytmusicapi failed mid-search — mark broken, try fallback below
            global _yt_broken
            _yt      = None
            _yt_broken = True

    if not merged:
        # fallback: yt-dlp search (works even when ytmusicapi is totally broken)
        merged = _ytdlp_search(query, limit)

    return merged


class Player:
    def __init__(self):
        self.process   = None
        self.paused    = False
        self.volume    = 80
        # IPC socket path — use system temp dir, works on all platforms
        _sock_name = f"unify-mpv-{os.getpid()}.sock"
        self.ipc_path  = os.path.join(tempfile.gettempdir(), _sock_name)
        # On Windows mpv uses named pipes instead of Unix sockets
        if IS_WINDOWS:
            self.ipc_path = f"\\\\.\\pipe\\unify-mpv-{os.getpid()}"
        self.current_track = None
        self.ipc_ready = False
        self._pos  = 0.0
        self._dur  = 0.0
        self._last_ipc = 0.0
        self._play_start = 0.0
        self._failed     = False
        self._stderr_lines = []
        self._stderr_lock  = threading.Lock()
        self._win_job      = None   # Windows Job Object handle (keeps mpv tied to us)

    # ── IPC helpers ───────────────────────────────────────────────

    def _ipc_send_raw(self, data: bytes) -> bytes:
        """
        Send raw bytes to mpv IPC and return whatever mpv writes back.
        Works on both Unix (AF_UNIX socket) and Windows (named pipe).
        Returns b"" on failure.
        """
        if not self.ipc_ready:
            return b""
        try:
            if IS_WINDOWS:
                # Windows named pipe — open as a binary file
                with open(self.ipc_path, "r+b", buffering=0) as pipe:
                    pipe.write(data)
                    pipe.flush()
                    # read response with a short timeout via threading
                    _buf = []
                    def _reader():
                        try: _buf.append(pipe.read(65536))
                        except: pass
                    t = threading.Thread(target=_reader, daemon=True)
                    t.start(); t.join(timeout=0.4)
                    return _buf[0] if _buf else b""
            else:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.settimeout(0.4)
                    s.connect(self.ipc_path)
                    s.sendall(data)
                    raw = b""
                    deadline = time.time() + 0.4
                    while time.time() < deadline:
                        try:
                            chunk = s.recv(4096)
                            if not chunk: break
                            raw += chunk
                            if b"\n" in raw: break
                        except: break
                    return raw
        except:
            return b""

    def _ipc_connect(self):
        """Legacy: return a connected Unix socket, or None. Kept for compat."""
        if not self.ipc_ready or IS_WINDOWS:
            return None
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.15)
            s.connect(self.ipc_path)
            return s
        except:
            return None

    def _ipc_send(self, cmd):
        if not self.ipc_ready:
            return False
        payload = (json.dumps({"command": cmd}) + "\n").encode()
        result  = self._ipc_send_raw(payload)
        return len(result) >= 0   # pipe/socket accepted the write

    def _ipc_query(self, *props):
        """Send multiple get_property requests, return list of values."""
        if not self.ipc_ready:
            return [None] * len(props)
        try:
            payload = b""
            for i, p in enumerate(props):
                payload += (json.dumps({"command": ["get_property", p],
                                        "request_id": i}) + "\n").encode()

            if IS_WINDOWS:
                # Named pipes on Windows are message-oriented; send all at once
                # then read back per-request
                results = [None] * len(props)
                try:
                    with open(self.ipc_path, "r+b", buffering=0) as pipe:
                        pipe.write(payload)
                        pipe.flush()
                        raw = b""
                        deadline = time.time() + 0.5
                        while time.time() < deadline and raw.count(b"\n") < len(props):
                            _buf = []
                            def _r():
                                try: _buf.append(pipe.read(4096))
                                except: pass
                            t = threading.Thread(target=_r, daemon=True)
                            t.start(); t.join(timeout=0.15)
                            if _buf and _buf[0]: raw += _buf[0]
                            else: break
                        for line in raw.split(b"\n"):
                            line = line.strip()
                            if not line: continue
                            try:
                                obj = json.loads(line)
                                rid = obj.get("request_id")
                                if rid is not None and 0 <= rid < len(props):
                                    results[rid] = obj.get("data")
                            except: pass
                except: pass
                return results
            else:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.settimeout(0.4)
                    s.connect(self.ipc_path)
                    s.sendall(payload)
                    raw = b""
                    deadline = time.time() + 0.4
                    while time.time() < deadline:
                        try:
                            chunk = s.recv(4096)
                            if not chunk: break
                            raw += chunk
                            if raw.count(b"\n") >= len(props): break
                        except: break
                results = [None] * len(props)
                for line in raw.split(b"\n"):
                    line = line.strip()
                    if not line: continue
                    try:
                        obj = json.loads(line)
                        rid = obj.get("request_id")
                        if rid is not None and 0 <= rid < len(props):
                            results[rid] = obj.get("data")
                    except: pass
                return results
        except:
            return [None] * len(props)

    def _wait_for_socket(self):
        """Background thread: wait for mpv IPC to become available."""
        deadline = time.time() + 15
        while time.time() < deadline:
            if IS_WINDOWS:
                # Named pipe appears as a file path
                try:
                    with open(self.ipc_path, "r+b", buffering=0) as _p:
                        pass
                    self.ipc_ready = True
                    return
                except:
                    time.sleep(0.1)
            else:
                if os.path.exists(self.ipc_path):
                    try:
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                            s.settimeout(0.2)
                            s.connect(self.ipc_path)
                        self.ipc_ready = True
                        return
                    except:
                        pass
                time.sleep(0.05)

    def _read_stderr(self, proc):
        """Background thread: read mpv stderr into rolling buffer."""
        try:
            for line in iter(proc.stderr.readline, b""):
                txt = line.decode("utf-8", errors="replace").rstrip()
                if txt:
                    with self._stderr_lock:
                        self._stderr_lines.append(txt)
                        if len(self._stderr_lines) > 40:
                            self._stderr_lines.pop(0)
        except:
            pass

    # ── Playback ──────────────────────────────────────────────────

    def play(self, track):
        self.stop()
        self.ipc_ready = False
        url = f"https://music.youtube.com/watch?v={track['id']}"
        cmd = [
            "mpv",
            "--no-video",
            "--quiet",          # shows errors in stderr (--really-quiet suppresses them)
            "--no-terminal",    # no terminal control codes / status line
            f"--volume={self.volume}",
            "--ytdl-format=bestaudio[ext=m4a]/bestaudio/best",
        ]
        # Explicitly tell mpv which yt-dlp binary to use.
        # This is more reliable than relying on PATH inheritance,
        # especially with pyenv / venv / --user installs.
        if _YTDLP_BIN:
            cmd.append(f"--script-opts=ytdl_hook-ytdl_path={_YTDLP_BIN}")
        # IPC: works on both Unix (socket) and Windows (named pipe)
        cmd.append(f"--input-ipc-server={self.ipc_path}")
        cmd.append(url)

        # On Windows, assign mpv to a Job Object with KILL_ON_JOB_CLOSE.
        # This guarantees mpv is killed when Python exits for ANY reason
        # (normal exit, crash, terminal window closed, Task Manager kill).
        # CREATE_NEW_PROCESS_GROUP alone does NOT do this.
        _popen_kw = dict(
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=_MPV_ENV,
        )
        self.process = subprocess.Popen(cmd, **_popen_kw)

        if IS_WINDOWS:
            try:
                import ctypes, ctypes.wintypes as _wt

                # ── create a Job Object ──────────────────────────
                _k32  = ctypes.windll.kernel32
                _job  = _k32.CreateJobObjectW(None, None)

                # Set KILL_ON_JOB_CLOSE so every process in the job
                # is killed when the last handle to the job is closed
                # (i.e. when our Python process exits)
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

                class _BasicLimit(ctypes.Structure):
                    _fields_ = [
                        ("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit",     ctypes.c_int64),
                        ("LimitFlags",              _wt.DWORD),
                        ("MinimumWorkingSetSize",   ctypes.c_size_t),
                        ("MaximumWorkingSetSize",   ctypes.c_size_t),
                        ("ActiveProcessLimit",      _wt.DWORD),
                        ("Affinity",                ctypes.c_size_t),
                        ("PriorityClass",           _wt.DWORD),
                        ("SchedulingClass",         _wt.DWORD),
                    ]

                class _IoCounters(ctypes.Structure):
                    _fields_ = [(f, ctypes.c_uint64) for f in (
                        "ReadOperationCount","WriteOperationCount",
                        "OtherOperationCount","ReadTransferCount",
                        "WriteTransferCount","OtherTransferCount")]

                class _ExtLimit(ctypes.Structure):
                    _fields_ = [
                        ("BasicLimitInformation", _BasicLimit),
                        ("IoInfo",                _IoCounters),
                        ("ProcessMemoryLimit",    ctypes.c_size_t),
                        ("JobMemoryLimit",        ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed",     ctypes.c_size_t),
                    ]

                _info = _ExtLimit()
                _info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                _k32.SetInformationJobObject(
                    _job, 9,   # JobObjectExtendedLimitInformation = 9
                    ctypes.byref(_info), ctypes.sizeof(_info)
                )

                # ── assign mpv process to the job ────────────────
                _proc_handle = _k32.OpenProcess(
                    0x001F0FFF,  # PROCESS_ALL_ACCESS
                    False,
                    self.process.pid
                )
                _k32.AssignProcessToJobObject(_job, _proc_handle)
                _k32.CloseHandle(_proc_handle)

                # Keep _job alive as long as this Player instance exists.
                # When Player is garbage-collected (or Python exits),
                # the handle closes and Windows kills mpv.
                self._win_job = _job

            except Exception as _je:
                pass  # Job Object failed — not critical, fallback to atexit
        # drain stderr in background so pipe doesn't block
        threading.Thread(target=self._read_stderr, args=(self.process,), daemon=True).start()
        self.current_track = track
        self.paused = False
        self._pos = 0.0
        self._dur = 0.0
        self._last_ipc = 0.0
        self._play_start = time.time()
        self._failed = False
        threading.Thread(target=self._wait_for_socket, daemon=True).start()

    def stop(self):
        self.ipc_ready = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None
        self.current_track = None
        # Clean up Unix socket file (not applicable on Windows)
        if not IS_WINDOWS:
            try:
                if os.path.exists(self.ipc_path):
                    os.remove(self.ipc_path)
            except:
                pass

    def get_pos(self):
        """Returns (pos, dur). Polls mpv once per 500ms max."""
        now = time.time()
        if self.ipc_ready and now - self._last_ipc > 0.5:
            pos, dur = self._ipc_query("time-pos", "duration")
            if pos is not None:
                self._pos = float(pos)
            if dur is not None:
                self._dur = float(dur)
            self._last_ipc = now
        return self._pos, self._dur

    def seek(self, seconds):
        self._ipc_send(["seek", seconds, "relative"])
        self._last_ipc = 0  # force pos refresh next frame

    def set_volume(self, delta):
        self.volume = max(0, min(100, self.volume + delta))
        self._ipc_send(["set_property", "volume", self.volume])

    def toggle_pause(self):
        if self._ipc_send(["cycle", "pause"]):
            self.paused = not self.paused

    def is_done(self):
        if self.process is None:
            return False
        rc = self.process.poll()
        if rc is None:
            return False  # still running
        elapsed = time.time() - self._play_start
        # Only flag as failed if mpv exited with error AND did so quickly.
        # 12 seconds gives yt-dlp enough time to extract the URL even on
        # slow connections before we decide it's a genuine stream failure.
        if rc != 0 and elapsed < 12.0:
            self._failed = True
        return True


# ── Helpers ───────────────────────────────────────────────────────

def fmt_time(s):
    s = max(0, int(s))
    return f"{s // 60}:{s % 60:02d}"

def progress_bar(pos, dur, width=42):
    if dur <= 0:
        return "─" * width
    filled = int(min(pos / dur, 1.0) * width)
    return "━" * filled + "╸" + "─" * max(0, width - filled - 1)


# ── App ───────────────────────────────────────────────────────────

class Unify:
    def __init__(self):
        self.player        = Player()
        self.results       = []
        self.synced_lyrics = []   # [(secs, text), ...]
        self.plain_lyrics  = ""
        self.lyrics_line   = 0
        self.playlists     = self._load_playlists()
        self.active_queue  = []
        self.active_p_name = ""
        self.queue_idx     = -1
        self.selected_idx  = 0
        # flicker-guard: only redraw when state changes or timer ticks
        self._last_draw    = 0.0
        self._dirty        = True
        self._track_scroll    = 0
        self.shuffle          = False
        self._shuffle_history = []
        # lyrics stale-thread guard: each play increments this token
        # a lyrics thread only writes if its token still matches
        self._lyrics_token = 0
        self.history         = self._load_history()
        self.recommendations = []
        self._home_mode      = "recent"
        self._show_home      = False
        # user queue (q key adds, plays before auto-advance)
        self._user_queue     = []
        self._show_queue     = False
        self._home_scroll    = 0
        self._consecutive_errors = 0
        # debug panel
        self._show_debug     = False
        self._debug_log      = []   # [(timestamp_str, message), ...]

    def _dlog(self, msg):
        """Append a timestamped entry to the debug log."""
        ts = time.strftime("%H:%M:%S")
        self._debug_log.append((ts, msg))
        if len(self._debug_log) > 60:
            self._debug_log.pop(0)

    def _build_debug_panel(self, pos, dur):
        try:
            import shutil as _sh
            term_h  = _sh.get_terminal_size((80, 24)).lines
            visible = max(10, term_h - 10)

            txt = Text(overflow="fold")
            txt.append("  ══ DEBUG PANEL (press D to close) ══\n\n", style="bold yellow")

            txt.append("  SYSTEM\n", style="bold cyan")
            txt.append(f"    Platform  : {sys.platform}  ({platform.platform()})\n", style="#aaaaaa")
            txt.append(f"    Python    : {sys.version.split()[0]}\n", style="#aaaaaa")

            mpv_ver = _sp_run("mpv", "--version").stdout.split("\n")[0] \
                      if shutil.which("mpv") else "NOT FOUND"
            txt.append(f"    mpv       : {mpv_ver[:60]}\n", style="#aaaaaa")

            ydl_ver = "NOT FOUND"
            if _YTDLP_BIN:
                ydl_ver = _sp_run(_YTDLP_BIN, "--version").stdout.strip() or "?"
            txt.append(f"    yt-dlp    : {ydl_ver}  ({_YTDLP_BIN or 'not on PATH'})\n", style="#aaaaaa")
            txt.append(f"    ytmusicapi: {'✓ ok' if _yt is not None else '✗ broken (yt-dlp fallback active)'}\n", style="#aaaaaa")

            txt.append("    Network   : ", style="#aaaaaa")
            try:
                socket.setdefaulttimeout(2)
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
                txt.append("✓ reachable\n", style="green")
            except:
                txt.append("✗ NO INTERNET\n", style="red")
            socket.setdefaulttimeout(None)

            ipc_status = (
                "✓ connected (named pipe)" if IS_WINDOWS and self.player.ipc_ready else
                "○ not connected (named pipe)" if IS_WINDOWS else
                "✓ connected" if self.player.ipc_ready else "○ not connected"
            )
            txt.append(f"    IPC       : {ipc_status}\n", style="#aaaaaa")

            txt.append("\n  MPV STDERR (last messages)\n", style="bold cyan")
            with self.player._stderr_lock:
                lines = list(self.player._stderr_lines)
            if lines:
                for ln in lines[-12:]:
                    color = "red" if any(w in ln.lower()
                            for w in ("error","fail","not found","403","unable")) else "#777777"
                    txt.append(f"    {ln[:90]}\n", style=color)
            else:
                txt.append("    (no output yet)\n", style="#555555")

            txt.append("\n  APP LOG\n", style="bold cyan")
            for ts, msg in self._debug_log[-(visible - 20):]:
                color = "red" if "✗" in msg or "error" in msg.lower() else "#777777"
                txt.append(f"    [{ts}] {msg}\n", style=color)
            if not self._debug_log:
                txt.append("    (no events yet)\n", style="#555555")

            root = Layout()
            root.split_column(
                Layout(self._build_now_playing(pos, dur), name="np", size=6),
                Layout(Panel(txt, title="[yellow]debug[/]", border_style="yellow"), name="main"),
                Layout(name="footer", size=2),
            )
            ft = Text()
            ft.append("  [D] close debug  |  events logged in real time", style="#888888")
            root["footer"].update(ft)
            return root

        except Exception as _de:
            # Never let the debug panel crash the whole app
            self._show_debug = False
            self._dlog(f"✗ Debug panel crashed: {_de}")
            return self._build_layout(pos, dur)

    def _mark_dirty(self):
        self._dirty = True

    def _auto_fetch_recs(self):
        import time as _t
        _t.sleep(2.0)
        if self.history:
            self._fetch_recommendations()
        else:
            # no history yet, retry after a bit in case user plays something
            _t.sleep(10)
            if self.history:
                self._fetch_recommendations()

    # ── Playlists ─────────────────────────────────────────────────

    def _load_playlists(self):
        if os.path.exists(PLAYLIST_FILE):
            try:
                with open(PLAYLIST_FILE) as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_playlists(self):
        os.makedirs(os.path.dirname(PLAYLIST_FILE), exist_ok=True)
        with open(PLAYLIST_FILE, "w") as f:
            json.dump(self.playlists, f)


    HISTORY_FILE = os.path.expanduser("~/.config/unify_history.json")
    MAX_HISTORY  = 50

    def _load_history(self):
        try:
            if os.path.exists(self.HISTORY_FILE):
                with open(self.HISTORY_FILE) as f:
                    return json.load(f)
        except:
            pass
        return []

    def _save_history(self, track):
        import datetime
        self.history = [h for h in self.history if h.get("id") != track["id"]]
        self.history.insert(0, {
            "id": track["id"], "title": track["title"],
            "artist": track.get("artist",""),
            "played_at": datetime.datetime.now().strftime("%d %b %H:%M")
        })
        self.history = self.history[:self.MAX_HISTORY]
        try:
            os.makedirs(os.path.dirname(self.HISTORY_FILE), exist_ok=True)
            with open(self.HISTORY_FILE, "w") as f:
                json.dump(self.history, f, indent=2)
        except:
            pass

    def _fetch_recommendations(self):
        self.recommendations = []
        self._mark_dirty()
        try:
            all_pl_ids = set()
            for songs in self.playlists.values():
                for s in songs:
                    all_pl_ids.add(s.get("id",""))
            seeds = [h["id"] for h in self.history[:3] if h.get("id")]
            if not seeds:
                return
            seen = set(all_pl_ids)
            recs = []
            _init_yt()
            for seed in seeds:
                try:
                    if _yt is not None:
                        watch  = _yt.get_watch_playlist(videoId=seed, limit=10)
                        tracks = watch.get("tracks", [])
                        for t in tracks:
                            vid = t.get("videoId","")
                            if not vid or vid in seen:
                                continue
                            artists = t.get("artists") or []
                            artist  = artists[0]["name"] if artists else "Unknown"
                            recs.append({"id": vid, "title": t.get("title","?"), "artist": artist})
                            seen.add(vid)
                            if len(recs) >= 15:
                                break
                    else:
                        # fallback: search for related tracks via yt-dlp
                        seed_title = next(
                            (t["title"] for t in self.history if t.get("id") == seed), seed
                        )
                        hits = _ytdlp_search(seed_title, limit=5)
                        for h in hits:
                            if h["id"] not in seen:
                                recs.append(h)
                                seen.add(h["id"])
                except:
                    pass
                if len(recs) >= 15:
                    break
                    break
            self.recommendations = recs
        except:
            pass
        self._mark_dirty()

    # ── Lyrics ────────────────────────────────────────────────────

    def _fetch_lyrics(self, title, artist, token=0):
        if token != self._lyrics_token:
            return
        self.synced_lyrics = []
        self.plain_lyrics  = "Fetching lyrics…"
        self._mark_dirty()

        def _set(synced=None, plain=None, msg=None):
            """Write result only if our token is still current."""
            if token != self._lyrics_token:
                return
            if synced:
                self.synced_lyrics = synced
                self.plain_lyrics  = ""
            elif plain:
                self.synced_lyrics = []
                self.plain_lyrics  = plain
            else:
                self.synced_lyrics = []
                self.plain_lyrics  = msg or "No lyrics found."
            self.lyrics_line = 0
            self._mark_dirty()

        try:
            # ── clean title ──────────────────────────────────────
            clean = re.sub(r"\(.*?\)|\[.*?\]", "", title).strip()
            clean = re.sub(
                r"(Official.*|Lyrics|Full Video|Full Song|Audio|HD|HQ|\d{4})",
                "", clean, flags=re.IGNORECASE
            ).strip()
            clean = re.sub(r"[:\|]+.*$", "", clean).strip()

            # ── helpers ──────────────────────────────────────────
            def parse_lrc(text):
                parsed = []
                for line in text.splitlines():
                    m = re.match(r"\[(\d+):(\d+[.,]\d+)\](.*)", line)
                    if m:
                        secs = int(m.group(1)) * 60 + float(m.group(2).replace(",", "."))
                        text_part = m.group(3).strip()
                        parsed.append((secs, text_part))
                return parsed

            def best_of(data):
                """Return (synced_parsed_or_None, plain_or_None) from a lrclib response dict."""
                if not data:
                    return None, None
                synced = data.get("syncedLyrics") or ""
                plain  = data.get("plainLyrics")  or ""
                parsed = parse_lrc(synced) if synced else []
                return (parsed or None), (plain or None)

            def lrclib_get(track_name, artist_name, duration=None):
                params = {"track_name": track_name, "artist_name": artist_name}
                if duration:
                    params["duration"] = int(duration)
                try:
                    r = requests.get("https://lrclib.net/api/get",
                                     params=params, timeout=8)
                    if r.status_code == 200:
                        return r.json()
                except Exception as e:
                    self._dlog(f"  lrclib get error: {e}")
                return None

            def lrclib_search(q):
                try:
                    r = requests.get("https://lrclib.net/api/search",
                                     params={"q": q}, timeout=8)
                    if r.status_code == 200 and r.json():
                        return r.json()[0]
                except Exception as e:
                    self._dlog(f"  lrclib search error: {e}")
                return None

            # get track duration from mpv IPC for a better lrclib match
            dur_val = None
            try:
                vals = self.player._ipc_query("duration")
                if vals and vals[0]:
                    dur_val = float(vals[0])
            except:
                pass

            self._dlog(f"Lyrics: searching for '{clean}' by '{artist}' dur={dur_val}")

            # ── attempt 1: exact get with duration ───────────────
            data = lrclib_get(clean, artist, duration=dur_val)
            synced, plain = best_of(data)
            if synced:
                self._dlog(f"Lyrics: ✓ synced via lrclib get (with duration)")
                _set(synced=synced); return
            if plain:
                self._dlog(f"Lyrics: ✓ plain via lrclib get (with duration)")
                _set(plain=plain); return

            # ── attempt 2: exact get without duration ────────────
            if dur_val:
                data = lrclib_get(clean, artist, duration=None)
                synced, plain = best_of(data)
                if synced:
                    self._dlog("Lyrics: ✓ synced via lrclib get (no duration)")
                    _set(synced=synced); return
                if plain:
                    self._dlog("Lyrics: ✓ plain via lrclib get (no duration)")
                    _set(plain=plain); return

            # ── attempt 3: search "title artist" ─────────────────
            data = lrclib_search(f"{clean} {artist}")
            synced, plain = best_of(data)
            if synced:
                self._dlog("Lyrics: ✓ synced via lrclib search (title+artist)")
                _set(synced=synced); return
            if plain:
                self._dlog("Lyrics: ✓ plain via lrclib search (title+artist)")
                _set(plain=plain); return

            # ── attempt 4: search title only ─────────────────────
            data = lrclib_search(clean)
            synced, plain = best_of(data)
            if synced:
                self._dlog("Lyrics: ✓ synced via lrclib search (title only)")
                _set(synced=synced); return
            if plain:
                self._dlog("Lyrics: ✓ plain via lrclib search (title only)")
                _set(plain=plain); return

            # ── attempt 5: original unstripped title ─────────────
            if clean != title:
                data = lrclib_search(f"{title} {artist}")
                synced, plain = best_of(data)
                if synced:
                    self._dlog("Lyrics: ✓ synced via lrclib search (raw title)")
                    _set(synced=synced); return
                if plain:
                    self._dlog("Lyrics: ✓ plain via lrclib search (raw title)")
                    _set(plain=plain); return

            self._dlog(f"Lyrics: ✗ not found in lrclib for '{clean}'")
            _set(msg="No lyrics found.\n\n"
                     f"Searched for: {clean!r}\n"
                     f"Artist: {artist!r}\n\n"
                     "lrclib.net may not have this track.\n"
                     "Check the debug panel [D] for details.")

        except Exception as e:
            self._dlog(f"Lyrics: ✗ unexpected error: {type(e).__name__}: {e}")
            _set(msg=f"Lyrics error: {type(e).__name__}\n{e}\n\nSee debug panel [D].")

    # ── UI builders ───────────────────────────────────────────────

    def _build_now_playing(self, pos, dur):
        t = self.player.current_track
        if not t:
            return Panel(
                Text("  nothing playing", style="#888888 italic"),
                title="[#888888]now playing[/]", border_style="#282828", height=5
            )
        bar   = progress_bar(pos, dur, width=44)
        state = "▶" if self.player.paused else "⏸"
        txt   = Text()
        txt.append(f"  {state}  ", style="cyan")
        txt.append(t["title"], style="bold white")
        txt.append("  —  ", style="#777777")
        txt.append(t.get("artist", ""), style="#aaaaaa")
        txt.append("\n\n  ")
        txt.append(bar, style="cyan")
        txt.append(f"  {fmt_time(pos)}", style="#888888")
        txt.append(" / ", style="#666666")
        txt.append(fmt_time(dur), style="#888888")
        txt.append(f"   vol {self.player.volume}%", style="#777777")
        shuf_tag = "  [yellow]⇀ shuffle on[/]" if self.shuffle else ""
        return Panel(txt, title="[cyan]now playing[/]" + shuf_tag, border_style="#1a4a4a", height=6)

    def _build_tracks(self, source):
        import shutil
        from rich.console import Console as _C
        _cw  = _C().width or 80
        term_h = shutil.get_terminal_size((80, 24)).lines
        # visible rows = terminal - now_playing(6) - footer(2) - borders(3)
        visible  = max(5, term_h - 11)
        left_w   = int(_cw * 0.4) - 6
        title_w  = max(10, left_w - 22)
        artist_w = min(16, max(8, left_w - title_w - 6))

        # auto-scroll: keep selected_idx inside the visible window
        if self.selected_idx < self._track_scroll:
            self._track_scroll = self.selected_idx
        elif self.selected_idx >= self._track_scroll + visible:
            self._track_scroll = self.selected_idx - visible + 1
        self._track_scroll = max(0, min(self._track_scroll, max(0, len(source) - visible)))

        txt = Text(overflow="fold", no_wrap=True)
        label = self.active_p_name or 'Search Results'
        txt.append(f"  ── {label} ({len(source)}) ──\n", style="#999999")

        window = source[self._track_scroll: self._track_scroll + visible]
        for j, s in enumerate(window):
            i        = j + self._track_scroll
            playing  = (i == self.queue_idx and bool(self.active_queue))
            selected = (i == self.selected_idx)
            if playing:
                prefix, style = "  ▶ ", "bold green"
            elif selected:
                prefix, style = "  › ", "bold cyan"
            else:
                prefix, style = "    ", "#cccccc"
            title_str  = s['title'][:title_w]
            artist_str = s.get('artist','')[:artist_w]
            txt.append(f"{prefix}{i+1:>2}. ", style="#777777")
            txt.append(f"{title_str:<{title_w}}", style=style)
            txt.append(f"  {artist_str}\n", style="#888888")

        if len(source) > visible:
            end = min(self._track_scroll + visible, len(source))
            txt.append(f"  ↕ {self._track_scroll+1}-{end} of {len(source)}\n", style="#555555")

        return Panel(txt, title="[#999999]tracks[/]", border_style="#252525")

    def _build_lyrics(self, pos):
        import shutil as _sh
        term_h  = _sh.get_terminal_size((80, 24)).lines
        VISIBLE = max(8, term_h - 14)  # adapt to terminal height

        txt = Text(overflow="fold")   # fold long lines instead of truncating
        if self.synced_lyrics:
            cur = 0
            for i, (t, _) in enumerate(self.synced_lyrics):
                if t <= pos:
                    cur = i
            # lyrics_line acts as a manual scroll offset on top of auto-scroll
            scroll = max(0, min(cur - VISIBLE // 2 + self.lyrics_line,
                                len(self.synced_lyrics) - VISIBLE))
            for i, (_, line) in enumerate(self.synced_lyrics[scroll: scroll + VISIBLE]):
                abs_i = scroll + i
                if abs_i == cur:
                    # active line: cyan, normal weight (bold breaks Devanagari width)
                    txt.append(f"  ▶ {line}\n", style="cyan")
                elif abs(abs_i - cur) == 1:
                    txt.append(f"    {line}\n", style="#aaaaaa")
                else:
                    txt.append(f"    {line}\n", style="#666666")
        else:
            lines = (self.plain_lyrics or "").split("\n")
            for line in lines[self.lyrics_line: self.lyrics_line + VISIBLE]:
                txt.append(f"    {line}\n", style="#aaaaaa")
        return Panel(txt, title="[#999999]lyrics[/]", border_style="#252525")


    def _build_home(self, pos=0.0, dur=0.0):
        import shutil
        term_h  = shutil.get_terminal_size((80, 24)).lines
        visible = max(5, term_h - 13)

        r_active   = (self._home_mode == "recent")
        rec_active = (self._home_mode == "recs")

        # clamp home scroll
        active_pool = self.history if r_active else self.recommendations
        max_scroll  = max(0, len(active_pool) - visible)
        self._home_scroll = max(0, min(self._home_scroll, max_scroll))

        # ── recently played panel ──────────────────────────────────
        rt = Text(overflow="fold", no_wrap=True)
        rt.append("  -- Recently Played --\n", style="#999999")
        if self.history:
            # scroll only the active panel
            r_scroll = self._home_scroll if r_active else 0
            window   = self.history[r_scroll: r_scroll + visible]
            for j, h in enumerate(window):
                i   = j + r_scroll
                sel = (i == self.selected_idx and r_active)
                style  = "bold cyan" if sel else "#cccccc"
                prefix = "  > " if sel else "    "
                rt.append(prefix + f"{i+1:>2}. ", style="#777777")
                rt.append(h["title"][:26], style=style)
                rt.append("  " + h.get("artist","")[:14] + "\n", style="#888888")
                rt.append("      " + h.get("played_at","") + "\n", style="#555555")
            if len(self.history) > visible:
                end = min(r_scroll + visible, len(self.history))
                rt.append(f"  ↕ {r_scroll+1}-{end} of {len(self.history)}\n", style="#444444")
        else:
            rt.append("  No history yet. Play some songs!\n", style="#555555 italic")

        r_border = "cyan" if r_active else "#333333"
        r_title  = "[bold cyan]recently played ◀[/]" if r_active else "[#666666]recently played[/]"
        recent_panel = Panel(rt, title=r_title, border_style=r_border)

        # ── recommendations panel ──────────────────────────────────
        rec_border = "cyan" if rec_active else "#333333"
        if self.recommendations:
            rtext = Text(overflow="fold", no_wrap=True)
            rtext.append("  -- Based on your listening --\n", style="#999999")
            rec_scroll = self._home_scroll if rec_active else 0
            window     = self.recommendations[rec_scroll: rec_scroll + visible]
            for j, r in enumerate(window):
                i   = j + rec_scroll
                sel = (i == self.selected_idx and rec_active)
                style  = "bold cyan" if sel else "#cccccc"
                prefix = "  > " if sel else "    "
                rtext.append(prefix + f"{i+1:>2}. ", style="#777777")
                rtext.append(r["title"][:26], style=style)
                rtext.append("  " + r.get("artist","")[:14] + "\n", style="#888888")
            if len(self.recommendations) > visible:
                end = min(rec_scroll + visible, len(self.recommendations))
                rtext.append(f"  ↕ {rec_scroll+1}-{end} of {len(self.recommendations)}\n", style="#444444")
            rec_title = "[bold cyan]recommendations ◀[/]" if rec_active else "[#666666]recommendations[/]"
            rec_panel = Panel(rtext, title=rec_title, border_style=rec_border)
        else:
            hint = Text()
            hint.append("\n  Press [W] to load recommendations\n  based on your listening history.\n", style="#555555 italic")
            rec_title = "[bold cyan]recommendations ◀[/]" if rec_active else "[#666666]recommendations[/]"
            rec_panel = Panel(hint, title=rec_title, border_style=rec_border)

        root = Layout()
        root.split_column(
            Layout(self._build_now_playing(pos, dur), name="np",   size=6),
            Layout(name="main",                               ratio=1),
            Layout(name="footer",                             size=2),
        )
        root["main"].split_row(
            Layout(recent_panel, name="recent", ratio=1),
            Layout(rec_panel,    name="recs",   ratio=1),
        )
        ft = Text()
        np_hint = f"  ♪ {self.player.current_track['title'][:25]}  |" if self.player.current_track else ""
        ft.append(np_hint, style="cyan")
        ft.append(" [Tab] switch panel  [↑↓] nav  [↵] play  [q] queue  [Q] view queue  [s] search  [L] playlist", style="#888888")
        root["footer"].update(ft)
        return root

    def _build_queue_panel(self):
        """Render the user queue as the main panel."""
        import shutil as _sh
        term_h  = _sh.get_terminal_size((80, 24)).lines
        visible = max(5, term_h - 13)

        # scroll for queue list
        if not hasattr(self, "_queue_scroll"):
            self._queue_scroll = 0
        if self.selected_idx < self._queue_scroll:
            self._queue_scroll = self.selected_idx
        elif self.selected_idx >= self._queue_scroll + visible:
            self._queue_scroll = self.selected_idx - visible + 1
        self._queue_scroll = max(0, min(self._queue_scroll,
                                        max(0, len(self._user_queue) - visible)))

        txt = Text(overflow="fold", no_wrap=True)
        txt.append(f"  ── Up Next ({len(self._user_queue)} songs) ──\n", style="#999999")
        if self._user_queue:
            window = self._user_queue[self._queue_scroll: self._queue_scroll + visible]
            for j, tr in enumerate(window):
                i   = j + self._queue_scroll
                sel = (i == self.selected_idx)
                style  = "bold cyan" if sel else "#cccccc"
                prefix = "  › " if sel else "    "
                txt.append(prefix + f"{i+1:>2}. ", style="#777777")
                txt.append(tr["title"][:28], style=style)
                txt.append("  " + tr.get("artist","")[:16] + "\n", style="#888888")
            if len(self._user_queue) > visible:
                end = min(self._queue_scroll + visible, len(self._user_queue))
                txt.append(f"  ↕ {self._queue_scroll+1}-{end} of {len(self._user_queue)}\n", style="#444444")
        else:
            txt.append("  Queue is empty.\n  Press [q] on any track to add it.\n", style="#555555 italic")

        return Panel(txt, title="[cyan]queue[/]", border_style="#1a4a4a")

    def _build_layout(self, pos, dur):
        if self._show_debug:
            return self._build_debug_panel(pos, dur)
        source = self.active_queue if self.active_queue else self.results

        if self._show_home or (not source and not self.player.current_track):
            return self._build_home(pos, dur)

        if self._show_queue:
            root = Layout()
            root.split_column(
                Layout(self._build_now_playing(pos, dur), name="np",     size=6),
                Layout(name="main",                                       ratio=1),
                Layout(name="footer",                                     size=2),
            )
            root["main"].split_row(
                Layout(self._build_queue_panel(),     name="queue",  ratio=4),
                Layout(self._build_lyrics(pos),       name="lyrics", ratio=6),
            )
            ft = Text()
            q_badge = f" [{len(self._user_queue)} queued]" if self._user_queue else ""
            ft.append(f" [Q] close queue{q_badge}  [↑↓] nav  [r] remove  [Tab] home  [q] add more", style="#888888")
            root["footer"].update(ft)
            return root

        root   = Layout()
        root.split_column(
            Layout(self._build_now_playing(pos, dur), name="np",      size=6),
            Layout(name="main",                                        ratio=1),
            Layout(name="footer",                                      size=2),
        )
        root["main"].split_row(
            Layout(self._build_tracks(source),   name="tracks", ratio=4),
            Layout(self._build_lyrics(pos),      name="lyrics", ratio=6),
        )
        ft = Text()
        q_badge = f" [{len(self._user_queue)}q]" if self._user_queue else ""
        ft.append(f" [s] search  [↑↓] nav  [↵/P] play  [q] queue{q_badge}  [Q] view queue  [g] jump  [a] add  [A] bulk  [r] rm  [L] playlist  [S] shuffle  ", style="#888888")
        ft.append("[n/b] next/prev  [←→] seek  [j/k] lyrics  [+/-] vol  [Tab] home", style="#777777")
        root["footer"].update(ft)
        return root

    # ── Playback ──────────────────────────────────────────────────

    def play_from_source(self, idx):
        source = self.active_queue if self.active_queue else self.results
        if not (0 <= idx < len(source)):
            self._dlog(f"play_from_source({idx}) out of range (len={len(source)})")
            return
        if not self.active_queue:
            self.active_queue = list(self.results)
        self.queue_idx    = idx
        track             = self.active_queue[idx]
        self.synced_lyrics = []
        self.plain_lyrics  = "Loading lyrics…"
        self._lyrics_token += 1
        self._consecutive_errors = 0
        token = self._lyrics_token
        self._save_history(track)
        self._dlog(f"▶ Playing: {track['title']} — {track.get('artist','')}  [id={track['id']}]")
        self.player.play(track)
        threading.Thread(
            target=self._fetch_lyrics,
            args=(track["title"], track.get("artist", ""), token),
            daemon=True
        ).start()
        self._mark_dirty()

    # ── Main loop ─────────────────────────────────────────────────

    def run(self):
        # ── Cross-platform keyboard setup ─────────────────────────
        if IS_WINDOWS:
            import msvcrt

            def _read_key():
                """Non-blocking key read on Windows."""
                if not msvcrt.kbhit():
                    time.sleep(0.05)
                    return None
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):   # special/extended key
                    ch2 = msvcrt.getwch()
                    return {
                        "H": "\x1b[A",   # up arrow
                        "P": "\x1b[B",   # down arrow
                        "K": "\x1b[D",   # left arrow
                        "M": "\x1b[C",   # right arrow
                    }.get(ch2, "")
                return ch

            def _cleanup_terminal():
                pass   # nothing to restore on Windows

        else:
            import tty, termios, select as _sel

            _orig_fd  = sys.stdin.fileno()
            _orig_tty = termios.tcgetattr(_orig_fd)

            def _read_key():
                """Non-blocking key read on Unix."""
                old = termios.tcgetattr(_orig_fd)
                try:
                    tty.setraw(_orig_fd)
                    r, _, _ = _sel.select([sys.stdin], [], [], 0.08)
                    if not r:
                        return None
                    ch = os.read(_orig_fd, 1)
                    if ch == b"\x1b":
                        # Check if more bytes follow (arrow/function keys)
                        r2, _, _ = _sel.select([sys.stdin], [], [], 0.04)
                        if not r2:
                            return "\x1b"   # plain Escape
                        ch2 = os.read(_orig_fd, 1)
                        if ch2 == b"[":
                            r3, _, _ = _sel.select([sys.stdin], [], [], 0.04)
                            if r3:
                                ch3 = os.read(_orig_fd, 1)
                                return "\x1b[" + ch3.decode("latin1")
                            return "\x1b["
                        return "\x1b" + ch2.decode("latin1")
                    return ch.decode("utf-8", errors="replace")
                except:
                    return None
                finally:
                    termios.tcsetattr(_orig_fd, termios.TCSADRAIN, old)

            def _cleanup_terminal():
                try:
                    termios.tcsetattr(_orig_fd, termios.TCSADRAIN, _orig_tty)
                    os.system("stty sane 2>/dev/null")
                except:
                    pass

        def _clear_for_prompt():
            """Suspend Live and restore terminal before a Prompt.ask()."""
            if not IS_WINDOWS:
                _cleanup_terminal()
            console.clear()

        # ── Main UI loop ──────────────────────────────────────────
        self._dlog(f"Started on {sys.platform}  yt-dlp={_YTDLP_BIN or 'NOT FOUND'}")

        try:
          with Live(
            self._build_layout(0, 0),
            console=console,
            screen=True,
            auto_refresh=False,
          ) as live:

            threading.Thread(target=self._auto_fetch_recs, daemon=True).start()

            while True:
                # Auto-advance when track ends
                if self.player.is_done():
                    if self.player._failed:
                        self._consecutive_errors += 1
                        self.player._failed = False
                        with self.player._stderr_lock:
                            last_err = (self.player._stderr_lines or ["(no stderr)"])[-1]
                        self._dlog(f"✗ Stream error #{self._consecutive_errors}: {last_err[:80]}")
                        if self._consecutive_errors >= 3:
                            self.plain_lyrics = (
                                "⚠ Playback error — music won't play.\n\n"
                                "Press [D] to open debug panel and see what's failing.\n\n"
                                "Common fixes:\n"
                                "  • Check internet connection\n"
                                "  • pip install -U yt-dlp\n"
                                "  • Make sure mpv can find yt-dlp (debug panel shows path)"
                            )
                            self.player.stop()
                            self._mark_dirty()
                        else:
                            self.plain_lyrics = f"⚠ Stream error (attempt {self._consecutive_errors}/3) — skipping…"
                            self._mark_dirty()
                            self.play_from_source(self.queue_idx + 1)
                        continue

                    # Normal completion
                    self._consecutive_errors = 0
                    self._dlog("✓ Track finished normally")
                    if self._user_queue:
                        nxt_track = self._user_queue.pop(0)
                        self.synced_lyrics = []
                        self.plain_lyrics  = "Loading lyrics…"
                        self._lyrics_token += 1
                        tok = self._lyrics_token
                        self._save_history(nxt_track)
                        self._dlog(f"▶ Queue next: {nxt_track['title']}")
                        self.player.play(nxt_track)
                        threading.Thread(target=self._fetch_lyrics,
                            args=(nxt_track["title"], nxt_track.get("artist",""), tok),
                            daemon=True).start()
                        self._mark_dirty()
                    elif self.shuffle and self.active_queue:
                        import random
                        remaining = [i for i in range(len(self.active_queue)) if i not in self._shuffle_history]
                        if not remaining:
                            self._shuffle_history = []
                            remaining = list(range(len(self.active_queue)))
                        nxt = random.choice(remaining)
                        self._shuffle_history.append(nxt)
                        self.play_from_source(nxt)
                    else:
                        self.play_from_source(self.queue_idx + 1)

                pos, dur = self.player.get_pos()

                key = _read_key()

                source = self.active_queue if self.active_queue else self.results

                if key:
                    self._mark_dirty()

                    if key in ("\x1b", "\x03"):   # Esc or Ctrl-C
                        break

                    elif key == "D":
                        self._show_debug  = not self._show_debug
                        self._show_home   = False
                        self._show_queue  = False
                        self._mark_dirty()

                    elif key == "q":
                        if self._show_queue:
                            pass
                        elif self._show_home:
                            pool = self.history if self._home_mode == "recent" else self.recommendations
                            if pool and 0 <= self.selected_idx < len(pool):
                                self._user_queue.append(dict(pool[self.selected_idx]))
                        elif source and 0 <= self.selected_idx < len(source):
                            self._user_queue.append(dict(source[self.selected_idx]))

                    elif key == "Q":
                        self._show_queue  = not self._show_queue
                        self._show_home   = False
                        self._show_debug  = False
                        self.selected_idx = 0

                    elif key == "\t":
                        if self._show_home:
                            self._home_mode = "recs" if self._home_mode == "recent" else "recent"
                            self.selected_idx = 0
                            self._home_scroll = 0
                        else:
                            self._show_home  = True
                            self._show_queue = False
                            self._show_debug = False
                            self.selected_idx = 0
                            self._home_scroll = 0

                    elif key == "W":
                        threading.Thread(target=self._fetch_recommendations, daemon=True).start()

                    elif key == "g":
                        live.stop(); _clear_for_prompt()
                        try:
                            num_str = Prompt.ask("[cyan]Jump to song #[/] (1-" + str(len(source)) + ")")
                            num = int(num_str.strip()) - 1
                            if 0 <= num < len(source):
                                self.selected_idx = num
                                self._track_scroll = max(0, num - 5)
                        except: pass
                        live.start()

                    elif key == " " or key == "p":
                        self.player.toggle_pause()

                    elif key == "\x1b[A":   # up arrow
                        if self._show_home:
                            self.selected_idx = max(0, self.selected_idx - 1)
                            if self.selected_idx < self._home_scroll:
                                self._home_scroll = self.selected_idx
                        elif self._show_queue:
                            self.selected_idx = max(0, self.selected_idx - 1)
                        else:
                            self.selected_idx = max(0, self.selected_idx - 1)

                    elif key == "\x1b[B":   # down arrow
                        if self._show_home:
                            pool = self.history if self._home_mode == "recent" else self.recommendations
                            self.selected_idx = min(len(pool) - 1, self.selected_idx + 1) if pool else 0
                            import shutil as _sh
                            _vis = max(5, _sh.get_terminal_size((80,24)).lines - 16)
                            if self.selected_idx >= self._home_scroll + _vis:
                                self._home_scroll = self.selected_idx - _vis + 1
                        elif self._show_queue:
                            self.selected_idx = min(len(self._user_queue) - 1, self.selected_idx + 1) if self._user_queue else 0
                        else:
                            self.selected_idx = min(len(source) - 1, self.selected_idx + 1) if source else 0

                    elif key == "\x1b[C":   # right arrow
                        self.player.seek(+5)
                    elif key == "\x1b[D":   # left arrow
                        self.player.seek(-5)

                    elif key in ("\r", "\n", "P"):
                        if self._show_home or (not source and not self.player.current_track):
                            pool = self.history if self._home_mode == "recent" else self.recommendations
                            if pool and 0 <= self.selected_idx < len(pool):
                                t = pool[self.selected_idx]
                                self.active_queue  = [dict(t)]
                                self.active_p_name = ""
                                self._show_home    = False
                                self.play_from_source(0)
                        elif self._show_queue and self._user_queue:
                            if 0 <= self.selected_idx < len(self._user_queue):
                                nxt = self._user_queue.pop(self.selected_idx)
                                self.active_queue  = [nxt]
                                self.active_p_name = ""
                                self._show_queue   = False
                                self.play_from_source(0)
                        elif source:
                            self._show_home  = False
                            self._show_queue = False
                            self.play_from_source(self.selected_idx)

                    elif key == "n":
                        if self.shuffle and self.active_queue:
                            import random
                            remaining = [i for i in range(len(self.active_queue)) if i not in self._shuffle_history]
                            if not remaining:
                                self._shuffle_history = []
                                remaining = list(range(len(self.active_queue)))
                            nxt = random.choice(remaining)
                            self._shuffle_history.append(nxt)
                            self.play_from_source(nxt)
                        else:
                            self.play_from_source(self.queue_idx + 1)

                    elif key == "b":
                        if self.shuffle and len(self._shuffle_history) > 1:
                            self._shuffle_history.pop()
                            self.play_from_source(self._shuffle_history[-1])
                        else:
                            self.play_from_source(self.queue_idx - 1)

                    elif key in ("+", "="):
                        self.player.set_volume(+5)
                    elif key == "-":
                        self.player.set_volume(-5)

                    elif key == "S":
                        self.shuffle = not self.shuffle
                        self._shuffle_history = []

                    elif key == "j":
                        max_offset = len(self.synced_lyrics) if self.synced_lyrics \
                                     else max(0, len((self.plain_lyrics or "").split("\n")) - 1)
                        self.lyrics_line = min(self.lyrics_line + 1, max_offset)
                    elif key == "k":
                        self.lyrics_line = max(0, self.lyrics_line - 1)

                    elif key == "s":
                        self._show_home  = False
                        self._show_queue = False
                        self._show_debug = False
                        live.stop(); _clear_for_prompt()
                        q = Prompt.ask("[cyan]search[/]")
                        if q:
                            merged = _search(q)
                            self._dlog(f"Search '{q}' → {len(merged)} results"
                                       + ("  [ytdlp fallback]" if _yt_broken else ""))
                            if not merged:
                                self._dlog("✗ Search returned no results")
                            self.results       = merged
                            self.active_queue  = []
                            self.active_p_name = ""
                            self.selected_idx  = 0
                        live.start()

                    elif key == "a":
                        if source and 0 <= self.selected_idx < len(source):
                            live.stop(); _clear_for_prompt()
                            name = Prompt.ask("Add to playlist", default="Favorites")
                            self.playlists.setdefault(name, []).append(source[self.selected_idx])
                            self._save_playlists()
                            live.start()

                    elif key == "r":
                        if self._show_queue:
                            if self._user_queue and 0 <= self.selected_idx < len(self._user_queue):
                                self._user_queue.pop(self.selected_idx)
                                self.selected_idx = max(0, min(self.selected_idx, len(self._user_queue)-1))
                        elif self.active_p_name and self.active_queue:
                            idx_r = self.selected_idx
                            if 0 <= idx_r < len(self.active_queue):
                                self.active_queue.pop(idx_r)
                                if self.active_p_name in self.playlists and idx_r < len(self.playlists[self.active_p_name]):
                                    self.playlists[self.active_p_name].pop(idx_r)
                                    self._save_playlists()
                                if self.queue_idx > idx_r:
                                    self.queue_idx -= 1
                                elif self.queue_idx == idx_r:
                                    self.queue_idx = -1
                                self.selected_idx = max(0, min(idx_r, len(self.active_queue) - 1))

                    elif key == "L":
                        self._show_home = False
                        live.stop(); _clear_for_prompt()
                        if self.playlists:
                            console.print(f"[#888888]Playlists: {', '.join(self.playlists)}[/]")
                        name = Prompt.ask("Load playlist")
                        if name in self.playlists:
                            self.active_p_name = name
                            self.active_queue  = list(self.playlists[name])
                            self.selected_idx  = 0
                            self.play_from_source(0)
                        live.start()

                    elif key == "A":
                        live.stop(); _clear_for_prompt()
                        if self.playlists:
                            console.print("[#888888]Existing playlists: " + ", ".join(self.playlists.keys()) + "[/]")
                        pl_name = Prompt.ask("Playlist name (new or existing)").strip()
                        if pl_name:
                            console.print("[#888888]Enter songs one by one. Empty line when done.[/]")
                            songs_to_add = []
                            idx = 1
                            while True:
                                song = Prompt.ask("  Song " + str(idx)).strip()
                                if not song:
                                    break
                                songs_to_add.append(song)
                                idx += 1
                            if songs_to_add:
                                if pl_name not in self.playlists:
                                    self.playlists[pl_name] = []
                                existing_ids = {t["id"] for t in self.playlists[pl_name]}
                                added = 0
                                for song in songs_to_add:
                                    console.print("[#888888]Searching: " + song + "...[/]", end=" ")
                                    try:
                                        hits = _search(song, limit=1)
                                        if hits:
                                            r0     = hits[0]
                                            vid_id = r0["id"]
                                            title  = r0.get("title", song)
                                            artist = r0.get("artist", "Unknown")
                                            if vid_id not in existing_ids:
                                                self.playlists[pl_name].append(
                                                    {"id": vid_id, "title": title, "artist": artist}
                                                )
                                                existing_ids.add(vid_id)
                                                added += 1
                                                console.print("[green]OK - " + title + " — " + artist + "[/]")
                                            else:
                                                console.print("[yellow]already exists[/]")
                                        else:
                                            console.print("[red]not found[/]")
                                    except Exception as e:
                                        console.print("[red]error: " + str(e) + "[/]")
                                self._save_playlists()
                                if self.active_p_name == pl_name:
                                    self.active_queue = list(self.playlists[pl_name])
                                console.print("[cyan]Done! Added " + str(added) + " songs to " + pl_name + "[/]")
                                input("  Press Enter to continue...")
                        live.start()

                now = time.time()
                if self._dirty or (now - self._last_draw >= 0.5):
                    live.update(self._build_layout(pos, dur), refresh=True)
                    self._last_draw = now
                    self._dirty     = False

        except Exception as _run_err:
            import traceback
            traceback.print_exc()
        finally:
            _cleanup_terminal()
            self.player.stop()


if __name__ == "__main__":
    Unify().run()


if __name__ == "__main__":
    Unify().run()

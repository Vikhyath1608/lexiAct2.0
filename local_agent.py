"""
local_agent.py
Run this on YOUR machine (not inside Docker).
Listens on Redis for commands from LexiAct and executes them locally:
  - play_sound  : plays alarm/timer beep through your speakers
  - launch_app  : opens apps on your desktop
  - volume      : controls system volume

Usage:
    pip install redis pygame          # minimum
    pip install pycaw comtypes        # Windows volume only
    python local_agent.py
"""
import json, os, platform, subprocess, sys, time, threading, math, struct, wave, io

REDIS_URL  = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
QUEUE_KEY  = "local_agent:commands"
OS         = platform.system()

print("=" * 52)
print("  LexiAct Local Agent")
print(f"  OS    : {OS}")
print(f"  Redis : {REDIS_URL}")
print("=" * 52)

try:
    import redis as redis_lib
    r = redis_lib.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    print("Connected to Redis\n")
except ImportError:
    print("ERROR: run  pip install redis"); sys.exit(1)
except Exception as e:
    print(f"ERROR: cannot connect to Redis: {e}"); sys.exit(1)


# ── Sound generation ──────────────────────────────────────────────────────────

def _make_wav(freq: float, dur: float, vol: float = 0.8, rate: int = 44100) -> bytes:
    n = int(rate * dur)
    buf = io.BytesIO()
    with wave.open(buf, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
        fade_len = rate // 20
        for i in range(n):
            fade = min(i, n - i, fade_len) / fade_len
            s = int(vol * fade * 32767 * math.sin(2 * math.pi * freq * i / rate))
            wf.writeframes(struct.pack("<h", s))
    return buf.getvalue()


PATTERNS = {
    "timer_done": [(880,0.15),(0,0.06),(880,0.15),(0,0.06),(880,0.15),(0,0.06),(1100,0.5)],
    "alarm":      [(660,0.2),(0,0.05),(880,0.2),(0,0.05),(660,0.2),(0,0.05),(880,0.2),(0,0.05),(1100,0.6)],
}


def _play_pygame(pattern):
    import pygame
    pygame.mixer.pre_init(44100, -16, 1, 512)
    pygame.mixer.init()
    for freq, dur in pattern:
        if freq == 0:
            time.sleep(dur)
        else:
            sound = pygame.mixer.Sound(io.BytesIO(_make_wav(freq, dur)))
            sound.play()
            while pygame.mixer.get_busy():
                time.sleep(0.01)
    pygame.mixer.quit()


def _system_beep():
    if OS == "Windows":
        import winsound
        for _ in range(3):
            winsound.Beep(880, 300); time.sleep(0.1)
    elif OS == "Darwin":
        subprocess.run(["osascript", "-e", "beep 3"], capture_output=True)
    else:
        sys.stdout.write("\a\a\a"); sys.stdout.flush()


def play_sound(sound_type: str):
    pattern = PATTERNS.get(sound_type, PATTERNS["timer_done"])
    def _run():
        try:
            _play_pygame(pattern); return
        except ImportError:
            pass
        except Exception as e:
            print(f"   pygame error: {e}")
        try:
            _system_beep()
        except Exception as e:
            print(f"   beep error: {e}")
    threading.Thread(target=_run, daemon=True).start()


# ── App launcher ──────────────────────────────────────────────────────────────

APP_MAP = {
    "notepad":       {"Windows":"notepad.exe",  "Darwin":"TextEdit",           "Linux":"gedit"},
    "calculator":    {"Windows":"calc.exe",     "Darwin":"Calculator",         "Linux":"gnome-calculator"},
    "chrome":        {"Windows":"chrome",       "Darwin":"Google Chrome",      "Linux":"google-chrome"},
    "firefox":       {"Windows":"firefox",      "Darwin":"Firefox",            "Linux":"firefox"},
    "edge":          {"Windows":"msedge",       "Darwin":"Microsoft Edge",     "Linux":"microsoft-edge"},
    "vs code":       {"Windows":"code",         "Darwin":"Visual Studio Code", "Linux":"code"},
    "vscode":        {"Windows":"code",         "Darwin":"Visual Studio Code", "Linux":"code"},
    "spotify":       {"Windows":"spotify",      "Darwin":"Spotify",            "Linux":"spotify"},
    "terminal":      {"Windows":"cmd.exe",      "Darwin":"Terminal",           "Linux":"gnome-terminal"},
    "cmd":           {"Windows":"cmd.exe",      "Darwin":"Terminal",           "Linux":"bash"},
    "file explorer": {"Windows":"explorer.exe", "Darwin":"Finder",             "Linux":"nautilus"},
    "paint":         {"Windows":"mspaint.exe",  "Darwin":"Preview",            "Linux":"gimp"},
    "word":          {"Windows":"winword.exe",  "Darwin":"Microsoft Word",     "Linux":"libreoffice --writer"},
    "excel":         {"Windows":"excel.exe",    "Darwin":"Microsoft Excel",    "Linux":"libreoffice --calc"},
    "vlc":           {"Windows":"vlc",          "Darwin":"VLC",                "Linux":"vlc"},
    "discord":       {"Windows":"discord",      "Darwin":"Discord",            "Linux":"discord"},
    "slack":         {"Windows":"slack",        "Darwin":"Slack",              "Linux":"slack"},
    "zoom":          {"Windows":"zoom",         "Darwin":"zoom.us",            "Linux":"zoom"},
    "task manager":  {"Windows":"taskmgr.exe",  "Darwin":"Activity Monitor",   "Linux":"gnome-system-monitor"},
}


def launch_app(command: dict):
    app_name = command.get("app_name", "")
    app_map  = command.get("app_map") or APP_MAP.get(app_name, {})
    raw      = command.get("raw", app_name)
    cmd      = app_map.get(OS, raw)

    print(f"   Launching: {cmd}")
    try:
        if OS == "Windows":
            if os.path.isabs(cmd):
                os.startfile(cmd)
            else:
                subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif OS == "Darwin":
            subprocess.Popen(["open", "-a", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"   OK: {cmd}")
    except FileNotFoundError:
        print(f"   Not found: {cmd}")
    except Exception as e:
        print(f"   Error: {e}")


# ── Volume control ────────────────────────────────────────────────────────────

def control_volume(command: dict):
    action = command.get("action", "increase")
    amount = command.get("amount", 10)
    level  = command.get("level", 50)
    print(f"   Volume: {action}")

    if OS == "Windows":
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            dev  = AudioUtilities.GetSpeakers()
            ifc  = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol  = cast(ifc, POINTER(IAudioEndpointVolume))
            if action == "mute":
                vol.SetMute(1, None); print("   Muted")
            elif action == "unmute":
                vol.SetMute(0, None); print("   Unmuted")
            elif action == "set":
                vol.SetMasterVolumeLevelScalar(level/100, None); print(f"   Set to {level}%")
            elif action == "increase":
                cur = int(vol.GetMasterVolumeLevelScalar()*100)
                vol.SetMasterVolumeLevelScalar(min(100,cur+amount)/100, None)
                print(f"   Increased to {min(100,cur+amount)}%")
            elif action == "decrease":
                cur = int(vol.GetMasterVolumeLevelScalar()*100)
                vol.SetMasterVolumeLevelScalar(max(0,cur-amount)/100, None)
                print(f"   Decreased to {max(0,cur-amount)}%")
        except ImportError:
            print("   Install pycaw:  pip install pycaw comtypes")
        except Exception as e:
            print(f"   Error: {e}")

    elif OS == "Darwin":
        cmds = {
            "mute":     ["osascript","-e","set volume output muted true"],
            "unmute":   ["osascript","-e","set volume output muted false"],
            "set":      ["osascript","-e",f"set volume output volume {level}"],
            "increase": ["osascript","-e",f"set volume output volume (output volume of (get volume settings) + {amount})"],
            "decrease": ["osascript","-e",f"set volume output volume (output volume of (get volume settings) - {amount})"],
        }
        try:
            subprocess.run(cmds[action], check=True, capture_output=True)
            print(f"   OK: {action}")
        except Exception as e:
            print(f"   Error: {e}")

    else:
        # Linux: try pactl then amixer
        def _run(cmd):
            try:
                subprocess.run(cmd, check=True, capture_output=True); return True
            except Exception:
                return False

        if action == "mute":
            _run(["pactl","set-sink-mute","@DEFAULT_SINK@","1"]) or _run(["amixer","sset","Master","mute"])
        elif action == "unmute":
            _run(["pactl","set-sink-mute","@DEFAULT_SINK@","0"]) or _run(["amixer","sset","Master","unmute"])
        elif action == "set":
            _run(["pactl","set-sink-volume","@DEFAULT_SINK@",f"{level}%"]) or _run(["amixer","sset","Master",f"{level}%"])
        elif action == "increase":
            _run(["pactl","set-sink-volume","@DEFAULT_SINK@",f"+{amount}%"]) or _run(["amixer","sset","Master",f"{amount}%+"])
        elif action == "decrease":
            _run(["pactl","set-sink-volume","@DEFAULT_SINK@",f"-{amount}%"]) or _run(["amixer","sset","Master",f"{amount}%-"])
        print(f"   OK: {action}")


# ── Command dispatcher ────────────────────────────────────────────────────────

def handle(raw: str):
    try:
        cmd = json.loads(raw)
        t   = cmd.get("type")
        if t == "play_sound":
            msg = cmd.get("message", "")
            print(f"\n  {msg}")
            play_sound(cmd.get("sound_type", "timer_done"))
        elif t == "launch_app":
            launch_app(cmd)
        elif t == "volume":
            control_volume(cmd)
        else:
            print(f"   Unknown command: {t}")
    except Exception as e:
        print(f"   Error: {e}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    print("Listening for commands... (Ctrl+C to stop)\n")
    while True:
        try:
            result = r.brpop(QUEUE_KEY, timeout=1)
            if result:
                _, raw = result
                handle(raw)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except redis_lib.ConnectionError:
            print("Redis connection lost. Retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()

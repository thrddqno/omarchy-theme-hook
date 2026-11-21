#!/bin/bash
# Omarchy invokes each hook through bash, even when thctl disables it.
[[ -x "$0" ]] || exit 0
run_chatgpt_sync() {
python3 - "$@" <<'PY'
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import tomllib

HOME = Path.home()
CONFIG = Path(os.environ.get("CODEX_HOME") or HOME / ".codex") / "config.toml"
PALETTE = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config") / "omarchy/current/theme/colors.toml"
APP = "/usr/lib/chatgpt/ChatGPT"


def patch(source, section, values):
    headers = list(re.finditer(r"(?m)^\s*\[[^\n]+\][ \t]*(?:#[^\n]*)?$", source))
    target = next((i for i, h in enumerate(headers)
                   if h[0].strip().split("]", 1)[0] == "[" + section), None)
    assignments = "".join(f"{key} = {json.dumps(value)}\n" for key, value in values.items())
    if target is None:
        return source.rstrip("\n") + f"\n\n[{section}]\n" + assignments
    start = headers[target].end()
    end = headers[target + 1].start() if target + 1 < len(headers) else len(source)
    body = source[start:end]
    for key, value in values.items():
        line = f"{key} = {json.dumps(value)}"
        body, count = re.subn(r"(?m)^[ \t]*" + key + r"[ \t]*=.*$", line, body)
        if not count:
            body = "\n" + line + "\n" + body.lstrip("\n")
    return source[:start] + body.rstrip("\n") + "\n\n" + source[end:]


def load_palette(path):
    palette = tomllib.loads(path.read_text())
    palette["mode"] = subprocess.check_output(
        ["omarchy-theme-color", "--file", str(path), "mode"], text=True, timeout=5
    ).strip()
    return palette


def render(source, palette):
    mode = palette["mode"]
    if mode not in ("dark", "light"):
        raise ValueError("Expected light or dark Omarchy theme mode")
    colors = {key: palette[name].lower() for key, name in
              (("surface", "background"), ("ink", "foreground"), ("accent", "accent"))}
    if any(not re.fullmatch(r"#[0-9a-f]{6}", color) for color in colors.values()):
        raise ValueError("Invalid Omarchy theme color")
    colors["accentSource"] = "custom"
    desktop = tomllib.loads(source).get("desktop", {})
    theme = "appearance" + mode.title() + "ChromeTheme"
    current = desktop.get(theme, {})
    if desktop.get("appearanceTheme") == mode and all(
            current.get(key) == value for key, value in colors.items()):
        return source
    updated = patch(source, "desktop", {"appearanceTheme": mode})
    section = "desktop." + theme
    if not current:
        updated = patch(updated, section, dict(colors, contrast=60, opaqueWindows=False))
        updated = patch(updated, section + ".fonts", {})
        updated = patch(updated, section + ".semanticColors",
                        {"diffAdded": "#40c977", "diffRemoved": "#fa423e", "skill": "#ad7bf9"})
    else:
        updated = patch(updated, section, colors)
    result = tomllib.loads(updated)["desktop"]
    if result["appearanceTheme"] != mode or any(
            result[theme].get(key) != value for key, value in colors.items()):
        raise ValueError("Theme update did not validate")
    return updated


def app_pids():
    pids = set()
    for process in Path("/proc").iterdir():
        if not process.name.isdecimal():
            continue
        try:
            if os.readlink(process / "exe") == APP:
                pids.add(int(process.name))
        except OSError:
            continue
    return pids


def quit_app(pids):
    windows = json.loads(subprocess.check_output(["hyprctl", "-j", "clients"], timeout=5))
    for window in windows:
        address = window.get("address", "")
        if window.get("pid") in pids and re.fullmatch(r"0x[0-9a-fA-F]+", address):
            shortcut = (
                'hl.dsp.send_shortcut({mods = "CTRL", key = "Q", '
                f'window = "address:{address}"}})'
            )
            subprocess.run(["hyprctl", "dispatch", shortcut], check=True, timeout=5,
                           stdout=subprocess.DEVNULL)
            for _ in range(40):
                if not app_pids():
                    return
                time.sleep(0.25)
            break
    raise ValueError("Quit ChatGPT Desktop normally, then rerun the theme hook")


def atomic_write(path, contents):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
            output.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--check":
        print(render(Path(sys.argv[2]).read_text(), load_palette(Path(sys.argv[3]))), end="")
        return
    config = CONFIG.resolve(strict=True)
    palette = load_palette(PALETTE)
    source = config.read_text()
    unchanged = f"ChatGPT Desktop {palette['mode']} theme already in sync"
    if render(source, palette) == source:
        print(unchanged)
        return 10
    with (config.parent / ".omarchy-chatgpt-theme.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        source = config.read_text()
        updated = render(source, palette)
        if updated == source:
            print(unchanged)
            return 10
        pids = app_pids()
        if pids:
            quit_app(pids)
        saved = False
        try:
            source = config.read_text()
            updated = render(source, palette)
            if updated != source:
                atomic_write(config.with_name("config.toml.omarchy-theme.bak"), source)
                atomic_write(config, updated)
                saved = True

        finally:
            if pids:
                try:
                    subprocess.run(["uwsm", "app", "-t", "service", "--", "chatgpt"],
                                   check=True, timeout=15, stdout=subprocess.DEVNULL)
                except (OSError, subprocess.SubprocessError) as error:
                    if saved:
                        raise ValueError(f"Theme settings saved, but ChatGPT could not relaunch: {error}") from error
                    raise
        if updated == source:
            print(unchanged)
            return 10
        print(f"ChatGPT Desktop {palette['mode']} theme updated")


try:
    sys.exit(main())
except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
    if sys.argv[1:2] == ["--check"]:
        sys.exit(str(error))
    print(f"ChatGPT Desktop: {error}")
    sys.exit(1)
PY

}

if [[ ${1:-} == --check ]]; then
    run_chatgpt_sync "$@"
    exit $?
fi

source "$HOME/.config/omarchy/hooks/theme-set-lib.sh" --logging-only || exit 1
command -v chatgpt >/dev/null 2>&1 || skipped "ChatGPT Desktop"
[[ -f "${CODEX_HOME:-$HOME/.codex}/config.toml" ]] || skipped "ChatGPT Desktop config"
python3 -c 'import tomllib' 2>/dev/null || skipped "Python 3.11+ for ChatGPT Desktop"

status=0
message=$(run_chatgpt_sync "$@") || status=$?
case "$status" in
    0) success "$message" ;;
    10) unchanged "$message" ;;
    *) error "${message:-ChatGPT Desktop theme hook exited with status $status}" ;;
esac

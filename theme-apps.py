"""Apply and remove the four app palettes using Omarchy's resolved colors."""

import configparser
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config")
MAIL = HOME / ".thunderbird"
PREF = 'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);'
OWNED = "/* Managed by omarchy-theme-hook */\n"
APPS = {
    "whatsie": "Whatsie", "caprine": "Caprine", "betterbird": "Betterbird",
    "stremio-enhanced": "Stremio Enhanced",
}


class Skip(Exception):
    pass


def read(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"Expected a regular file at {path}")
    return path.read_bytes().decode("utf-8") if path.exists() else ""


def write(path, old, new):
    if new == old:
        return False
    if not new:
        path.unlink()
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            os.fchmod(handle.fileno(), mode)
            handle.write(new.encode("utf-8"))
            handle.flush()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return True


def block(source, name, body, *, js=False, prepend=False):
    prefix, suffix = ("//", "") if js else ("/*", " */")
    start = f"{prefix} BEGIN omarchy-theme-hook {name}{suffix}"
    end = f"{prefix} END omarchy-theme-hook {name}{suffix}"
    # A leading separator belongs to append blocks, keeping even a file with
    # no final newline byte-for-byte intact when the block is removed.
    pattern = ("" if prepend else r"\r?\n") + re.escape(start)
    pattern += r"\r?\n.*?^" + re.escape(end) + r"(?:\r?\n|\Z)"
    matches = list(re.finditer(pattern, source, re.MULTILINE | re.DOTALL))
    if source.count(start) != len(matches) or source.count(end) != len(matches) or len(matches) > 1:
        raise ValueError(f"Malformed managed block for {name}")
    section = f"{'' if prepend else chr(10)}{start}\n{body}\n{end}\n" if body else ""
    if matches:
        match = matches[0]
        return source[:match.start()] + section + source[match.end():]
    return section + source if prepend else source + section


def generated(path, old, new, marker):
    if path.exists() and not old.startswith(marker):
        if not new:
            return old
        raise ValueError("Existing file belongs to the user")
    return new


def palette():
    output = run("omarchy", "theme", "color", "--file",
                 str(HOME / ".local/state/omarchy/current/theme/colors.toml"), "--all")
    values = {key: value for key, _, value in (line.partition("\t") for line in output.splitlines())}
    colors = {key: values[key].lower() for key in (
        "background", "foreground", "accent", "selection_background", "selection_foreground")}
    if not all(re.fullmatch(r"#[0-9a-f]{6}", value) for value in colors.values()):
        raise ValueError("Invalid Omarchy palette color")
    colors["mode"] = values["mode"]
    if colors["mode"] not in ("dark", "light"):
        raise ValueError("Invalid Omarchy palette mode")
    return colors


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE, timeout=10).strip()


def processes(app):
    result = {}
    for path in Path("/proc").iterdir():
        if not path.name.isdecimal():
            continue
        try:
            if path.stat().st_uid != os.getuid():
                continue
            exe = (path / "exe").readlink()
            args = (path / "cmdline").read_bytes().split(b"\0")[:-1]
            if app == "caprine":
                # Some Electron builds rewrite argv[0] as one command-line string.
                packaged = b"/usr/lib/caprine/app.asar"
                if len(args) == 1 and args[0].startswith(os.fsencode(exe) + b" " + packaged):
                    default = [os.fsencode(exe), packaged, b"env", b"ELECTRON_OZONE_PLATFORM_HINT=auto"]
                    if args[0] == b" ".join(default):
                        args = default
                    match = True
                else:
                    match = packaged in args or exe.name.lower() == "caprine"
            else:
                match = exe.name in ("whatsie", "whatsie-omarchy", "whatsie (deleted)")
            if match and args and not any(arg.startswith(b"--type=") for arg in args):
                # Include the kernel start time so a recycled PID cannot be
                # mistaken for the original instance while waiting for exit.
                started = (path / "stat").read_text().rsplit(")", 1)[1].split()[19]
                result[int(path.name)] = (exe, args, started)
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return result


def restart(app, command):
    instances = processes(app)
    if not instances:
        return ""
    manual = " A manual restart is needed."
    if len(instances) != 1:
        return manual
    pid, (exe, args, started) = next(iter(instances.items()))
    # Relaunch only default invocations. Preserve custom sessions and flags.
    if app == "whatsie":
        if exe != Path(command).resolve() or len(args) != 1:
            return manual
    elif (len(args) == 1 and exe.name.lower() != "caprine") or args[1:] not in (
            [], [b"/usr/lib/caprine/app.asar"],
            [b"/usr/lib/caprine/app.asar", b"env", b"ELECTRON_OZONE_PLATFORM_HINT=auto"]):
        return manual
    try:
        if app == "whatsie":
            run(command, "--quit")
        else:
            windows = json.loads(run("hyprctl", "-j", "clients"))
            addresses = [window["address"] for window in windows
                         if window.get("pid") == pid and window.get("class", "").lower() == "caprine"]
            if len(addresses) != 1 or not re.fullmatch(r"0x[0-9a-fA-F]+", addresses[0]):
                return manual
            shortcut = ('hl.dsp.send_shortcut({mods = "CTRL", key = "q", '
                        f'window = "address:{addresses[0]}"}})')
            if run("hyprctl", "dispatch", shortcut) != "ok":
                return manual
        for _ in range(40):
            current = processes(app)
            if not current:
                run("uwsm", "app", "-t", "service", "--", command)
                return " Restart requested."
            if pid not in current or current[pid][2] != started or len(current) != 1:
                return manual
            time.sleep(0.25)
    except (OSError, ValueError, subprocess.SubprocessError):
        return manual
    return manual


def profile_settings():
    settings = configparser.ConfigParser(interpolation=None)
    settings.read_string(read(MAIL / "profiles.ini"))
    return settings


def profiles(settings):
    result = {}
    for section in settings:
        if not section.startswith("Profile") or not settings[section].get("Path"):
            continue
        entry = settings[section]
        name = entry["Path"]
        path = (MAIL / name if entry.get("IsRelative") == "1" else Path(name)).resolve()
        if path.is_dir() and Path(name).is_absolute() == (entry.get("IsRelative") == "0"):
            result[name] = path
    return result


def betterbird_profiles():
    running = False
    locked = set()
    for process in Path("/proc").glob("*/exe"):
        try:
            if process.parent.stat().st_uid != os.getuid() or process.readlink().name not in (
                    "betterbird", "betterbird-bin"):
                continue
            args = (process.parent / "cmdline").read_bytes().split(b"\0")
            if b"-contentproc" in args:
                continue
            running = True
            for descriptor in (process.parent / "fd").iterdir():
                try:
                    target = descriptor.readlink()
                    if target.name == ".parentlock":
                        locked.add(target.parent.resolve())
                except (FileNotFoundError, PermissionError, ProcessLookupError):
                    continue
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return running, locked


def active_profile(settings, candidates):
    running, locked = betterbird_profiles()
    if len(locked) > 1:
        raise Skip("multiple Betterbird profiles are open")
    if len(locked) == 1 and locked <= set(candidates.values()):
        return locked.pop()
    if running:
        raise Skip("running Betterbird profile could not be identified")
    defaults = {settings[section].get("Default") for section in settings
                if section.startswith("Install")}
    if not defaults:
        installs = configparser.ConfigParser(interpolation=None)
        installs.read_string(read(MAIL / "installs.ini"))
        defaults = {installs[section].get("Default") for section in installs.sections()}
    if len(defaults) == 1 and next(iter(defaults)) in candidates:
        return candidates[next(iter(defaults))]
    if not defaults and len(candidates) == 1:
        return next(iter(candidates.values()))
    raise Skip("active profile is ambiguous or missing")


def update_file(path, transform):
    old = read(path)
    return write(path, old, transform(old))


def mail_theme(path, colors):
    chrome = path / "chrome"
    css = chrome / "omarchy-hook-betterbird.css"
    user_chrome = chrome / "userChrome.css"
    user_js = path / "user.js"
    old_css, old_chrome, old_js = map(read, (css, user_chrome, user_js))
    stylesheet = ""
    if colors:
        stylesheet = OWNED + """@-moz-document url("chrome://messenger/content/messenger.xhtml") {
  :root {
    --layout-background-0: %(background)s !important;
    --layout-background-1: %(background)s !important;
    --layout-background-2: %(background)s !important;
    --layout-color-0: %(foreground)s !important;
    --layout-color-1: %(foreground)s !important;
    --selected-item-text-color: %(selection_foreground)s !important;
    --selected-item-color: %(selection_background)s !important;
    --toolbar-background-color: %(background)s !important;
    --toolbar-text-color: %(foreground)s !important;
    --color-accent-primary: %(accent)s !important;
  }
  #spacesToolbar, #folderPane, #folderTree, #threadPane, #threadTree, #threadPaneHeaderBar,
  #unifiedToolbar, #tabs-toolbar {
    background-color: %(background)s !important;
    color: %(foreground)s !important;
  }
}
""" % colors
    new_css = generated(css, old_css, stylesheet, OWNED)
    new_chrome = block(old_chrome, "betterbird", '@import url("omarchy-hook-betterbird.css");'
                       if colors else "", prepend=True)
    new_js = block(old_js, "betterbird", PREF if colors else "", js=True)
    return any([write(css, old_css, new_css), write(user_chrome, old_chrome, new_chrome),
                write(user_js, old_js, new_js)])


def apply(app, removing):
    command = None
    if not removing and app in ("whatsie", "caprine", "betterbird"):
        command = shutil.which(app)
        if not command:
            raise Skip("application unavailable")
    if app == "whatsie":
        if not removing:
            instances = processes(app)
            try:
                supported = run(command, "--omarchy-palette-version") == "1"
            except (OSError, subprocess.SubprocessError):
                supported = False
            if not supported:
                raise Skip("stock build or unsupported patch version")
            if instances and any(exe != Path(command).resolve() for exe, _, _ in instances.values()):
                raise Skip("running instance does not match the patched binary")
        path = CONFIG / "whatsie/omarchy-palette.json"
        # JSON marker is first to make ownership independent of the palette.
        marker = '{"managed_by": "omarchy-theme-hook",'
        content = "" if removing else json.dumps({"managed_by": "omarchy-theme-hook", **palette()}) + "\n"
        return update_file(path, lambda old: generated(path, old, content, marker)), command
    if app == "betterbird":
        settings = profile_settings()
        candidates = profiles(settings)
        if removing:
            return any([mail_theme(path, None) for path in sorted(set(candidates.values()))]), None
        path = active_profile(settings, candidates)
        return mail_theme(path, palette()), command
    if app == "caprine":
        directory = CONFIG / "Caprine"
        if not removing and not directory.is_dir():
            raise Skip("config directory unavailable")
        content = "" if removing else """html body, html body [role="main"],
html body [role="navigation"], html body [role="complementary"],
html body [role="banner"], html body [role="dialog"] {
  background-color: %(background)s !important;
  color: %(foreground)s !important;
}
html body, html body :is(.__fb-light-mode, .__fb-dark-mode) {
  --surface-background: %(background)s !important;
  --card-background: %(background)s !important;
  --primary-text: %(foreground)s !important;
  --secondary-text: %(foreground)s !important;
  --accent: %(accent)s !important;
  --primary-button-background: %(accent)s !important;
  --messenger-primary-button-background: %(accent)s !important;
  --messenger-primary-button-text: %(selection_foreground)s !important;
  --hover-overlay: color-mix(in srgb, %(foreground)s 12%%, transparent) !important;
  --messenger-card-background: %(background)s !important;
}
""" % palette()
        return update_file(directory / "custom.css", lambda old: block(old, app, content.rstrip())), command
    directory = CONFIG / "stremio-enhanced/themes"
    if not removing and not directory.is_dir():
        raise Skip("themes directory unavailable")
    content = "" if removing else OWNED + """/**
 * @name Omarchy
 * @description Follows the active Omarchy palette.
 * @version 1.0.0
 * @author Omarchy Theme Hook
 */
:root {
  color-scheme: %(mode)s;
  --background-color-primary: %(background)s;
  --background-color-secondary: %(background)s;
  --surface-background-color: color-mix(in srgb, %(background)s 88%%, %(foreground)s);
  --foreground-color-primary: %(foreground)s;
  --foreground-color-secondary: %(foreground)s;
  --accent-color: %(accent)s;
  --action-color: %(accent)s;
  --primary-background-color: %(background)s;
  --secondary-background-color: %(background)s;
  --modal-background-color: %(background)s;
  --primary-foreground-color: %(foreground)s;
  --secondary-foreground-color: %(foreground)s;
  --primary-accent-color: %(accent)s;
}
""" % palette()
    path = directory / "omarchy.theme.css"
    return update_file(path, lambda old: generated(path, old, content, OWNED)), None


def main():
    app = sys.argv[1]
    removing = sys.argv[2:] == ["--remove"]
    label = APPS[app]
    # The pack's installed helper is a stable per-user lock target.
    with open(__file__, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        changed, command = apply(app, removing)
        if not changed:
            print(f"{label} already in sync")
            return 10
        if removing:
            print(f"{label} managed theme removed")
            return 0
        if app in ("whatsie", "caprine"):
            notice = restart(app, command)
        elif app == "betterbird":
            notice = " Restart Betterbird to apply it."
        else:
            notice = " Select Omarchy once and reload Stremio to apply palette changes."
        print(f"{label} theme updated.{notice}")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Skip as error:
        print(f"{APPS[sys.argv[1]]}: {error}")
        sys.exit(11)
    except (OSError, ValueError, KeyError, configparser.Error, subprocess.SubprocessError) as error:
        print(f"{APPS[sys.argv[1]]}: {error}")
        sys.exit(1)

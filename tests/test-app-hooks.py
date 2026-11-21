import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("theme_apps", REPO / "theme-apps.py")
hooks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooks)


class AppHookTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.config = self.home / ".config"
        self.hooks = self.config / "omarchy/hooks"
        self.mail = self.home / ".thunderbird"
        self.profile = self.mail / "test.default"
        self.colors = self.home / ".local/state/omarchy/current/theme/colors.toml"
        self.bin = self.home / "bin"
        for directory in (self.hooks / "theme-set.d", self.profile / "chrome", self.bin,
                          self.colors.parent, self.config / "Caprine",
                          self.config / "stremio-enhanced/themes"):
            directory.mkdir(parents=True)
        for item in ("theme-set-lib.sh", "theme-apps.py"):
            (self.hooks / item).symlink_to(REPO / item)
        (self.mail / "profiles.ini").write_text(
            "[Profile0]\nPath=test.default\nIsRelative=1\n")
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.config),
                        PATH=f"{self.bin}:{os.environ['PATH']}")
        for name in ("caprine", "betterbird", "whatsie"):
            executable = self.bin / name
            executable.write_text("#!/bin/sh\nprintf '1\\n'\n")
            executable.chmod(0o755)

    def fixture_palette(self, bg, fg, mode=None):
        explicit = f'mode = "{mode}"\n' if mode else ""
        self.colors.write_text(
            f'{explicit}background = "{bg}"\nforeground = "{fg}"\naccent = "#345678"\n'
        )

    def hook(self, name, remove=False):
        if remove:
            args = ["bash", "-c",
                    'source "$HOME/.config/omarchy/hooks/theme-set-lib.sh" --logging-only; '
                    'run_app_theme "$1" --remove', "test", name]
        else:
            script = next((REPO / "theme-set.d").glob(f"*-{name}.sh"))
            args = ["bash", str(script)]
        return subprocess.run(args, env=self.env, capture_output=True, text=True, timeout=15)

    def test_palettes_preservation_and_cleanup(self):
        original = b"/* Custom style */\r\nbutton { padding: 2px; }"
        caprine = self.config / "Caprine/custom.css"
        chrome = self.profile / "chrome/userChrome.css"
        for path in (caprine, chrome):
            path.write_bytes(original)
        user_js = self.profile / "user.js"
        user_js.write_bytes(b'user_pref("mail.somePreference", false);')
        stremio = self.config / "stremio-enhanced/themes/omarchy.theme.css"
        # Avoid relying on the actual desktop processes for fixture apply.
        with patch.dict(os.environ, self.env), patch.object(hooks, "HOME", self.home), \
             patch.object(hooks, "CONFIG", self.config), patch.object(hooks, "MAIL", self.mail), \
             patch.object(hooks, "betterbird_profiles", return_value=(False, set())), \
             patch.object(hooks, "processes", return_value={}):
            for background, foreground, explicit, expected in (
                ("#1a2130", "#eeeeee", "dark", "dark"),
                ("#fcf4e4", "#222222", "light", "light"),
                ("#131622", "#ffffff", None, "dark"),
            ):
                self.fixture_palette(background, foreground, explicit)
                for name in hooks.APPS:
                    self.assertTrue(hooks.apply(name, False)[0], name)
                    self.assertFalse(hooks.apply(name, False)[0], name)
                self.assertIn(f"color-scheme: {expected}", stremio.read_text())
                self.assertIn(background.encode(), caprine.read_bytes())
            self.assertTrue(caprine.read_bytes().startswith(original))
            self.assertTrue(chrome.read_bytes().endswith(original))
            for name in hooks.APPS:
                self.assertTrue(hooks.apply(name, True)[0], name)
                self.assertFalse(hooks.apply(name, True)[0], name)
        self.assertEqual(chrome.read_bytes(), original)
        self.assertEqual(caprine.read_bytes(), original)
        self.assertEqual(user_js.read_bytes(), b'user_pref("mail.somePreference", false);')
        self.assertFalse(stremio.exists())

    def test_status_for_success_unchanged_conflict_and_stock(self):
        self.fixture_palette("#101010", "#eeeeee")
        app = "stremio-enhanced"
        self.assertIn("[SUCCESS]", self.hook(app).stdout)
        self.assertIn("[UNCHANGED]", self.hook(app).stdout)
        self.assertIn("[SUCCESS]", self.hook(app, remove=True).stdout)
        path = self.config / app / "themes/omarchy.theme.css"
        path.write_text("/* User's theme */")
        failed = self.hook(app)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("[ERROR]", failed.stderr)
        self.assertEqual(path.read_text(), "/* User's theme */")
        (self.bin / "whatsie").write_text("#!/bin/sh\nexit 1\n")
        self.assertIn("[SKIPPED]", self.hook("whatsie").stdout)

    def test_restarts_only_for_changed_palette(self):
        with patch.object(hooks, "apply", return_value=(False, "/bin/caprine")), \
             patch.object(hooks, "restart") as restart, \
             patch.object(hooks.sys, "argv", ["test", "caprine"]):
            self.assertEqual(hooks.main(), 10)
            restart.assert_not_called()
        command = "/usr/bin/caprine"
        instance = {42: (Path("/usr/bin/caprine"), [b"/usr/bin/caprine"], "100")}
        with patch.object(hooks, "processes", return_value={}), patch.object(hooks, "run") as run:
            self.assertEqual(hooks.restart("caprine", command), "")
            run.assert_not_called()
        with patch.object(hooks, "processes", return_value=instance), \
             patch.object(hooks, "run", side_effect=OSError):
            self.assertIn("manual restart", hooks.restart("caprine", command))
        windows = '[{"pid": 42, "class": "Caprine", "address": "0x42"}]'
        with patch.object(hooks, "processes", side_effect=[instance, {}]), \
             patch.object(hooks, "run", side_effect=[windows, "ok", ""]) as run:
            self.assertIn("Restart requested", hooks.restart("caprine", command))
            self.assertEqual(run.call_args.args, ("uwsm", "app", "-t", "service", "--", command))

    def test_ambiguous_betterbird_skips(self):
        (self.mail / "other.default").mkdir()
        with (self.mail / "profiles.ini").open("a") as settings:
            settings.write("\n[Profile1]\nPath=other.default\nIsRelative=1\n")
        result = self.hook("betterbird")
        self.assertEqual(result.returncode, 0)
        self.assertIn("[SKIPPED]", result.stdout)
        self.assertFalse((self.profile / "user.js").exists())


if __name__ == "__main__":
    unittest.main()

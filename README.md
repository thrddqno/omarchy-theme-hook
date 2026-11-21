<div align="center">
  <img src="assets/logo.png" width="96" height="96" alt="Omarchy Theme Hook logo">
  <h1>Omarchy Theme Hook</h1>
  <p>App theme hooks for Omarchy 4 (Quattro).</p>

[![Omarchy 4 Quattro](https://img.shields.io/badge/Omarchy_4-Quattro-6d9eeb?style=flat-square)](https://github.com/basecamp/omarchy)
[![21 theme hooks](https://img.shields.io/badge/theme_hooks-21-78bd7b?style=flat-square)](theme-set.d/)
[![GitHub issues](https://img.shields.io/github/issues/thrddqno/omarchy-theme-hook?style=flat-square)](https://github.com/thrddqno/omarchy-theme-hook/issues)
[![Last commit on main](https://img.shields.io/github/last-commit/thrddqno/omarchy-theme-hook/main?style=flat-square)](https://github.com/thrddqno/omarchy-theme-hook/commits/main/)

[Install](#install) · [Manage hooks](#manage-hooks) · [Supported apps](#supported-apps) · [Troubleshooting](#app-setup-and-troubleshooting)

</div>

Switch your Omarchy theme and the enabled hooks apply its colors to your apps. This fork uses Omarchy 4’s `theme-set.d` runner and resolves shared colors from the active theme’s `colors.toml`.

![Discord, Steam, and Spotify using Everpuccin in the upstream showcase](assets/preview.png)

*Upstream showcase featuring Discord, Steam, and Spotify with Everpuccin.*

## Install

Use an Omarchy 4 installation with a theme that includes `colors.toml`.

```bash
curl -fsSL https://thrddqno.github.io/omarchy-theme-hook/install.sh | bash
```

The installer adds the hooks to `~/.config/omarchy/hooks/theme-set.d/` and runs them once. It offers to install `adw-gtk-theme` for GTK apps if the package is missing.

## Manage hooks

Use the fork’s copy of `thctl` at `~/.local/bin/thctl`.

| Command | What it does |
| --- | --- |
| `~/.local/bin/thctl list` | Show enabled and disabled hooks. |
| `~/.local/bin/thctl open` | Open the installed hook directory. |
| `~/.local/bin/thctl disable chatgpt` | Stop the ChatGPT hook from running. |
| `~/.local/bin/thctl enable chatgpt` | Enable the ChatGPT hook again. |
| `~/.local/bin/thctl run` | Run the enabled hooks with the current palette. |
| `~/.local/bin/thctl update` | Update the pack and keep disabled hooks disabled. |
| `~/.local/bin/thctl remove` | Uninstall the pack. |

Replace `chatgpt` with any hook name from `list`. Run `~/.local/bin/thctl run` after enabling a hook to apply the current palette right away.

## Uninstall

Use `~/.local/bin/thctl remove` or run the command below. If an app still shows the last applied theme, restore its theme in the app’s settings.

```bash
curl -fsSL https://thrddqno.github.io/omarchy-theme-hook/uninstall.sh | bash
```

## Supported apps

Use the name in parentheses with `thctl enable` or `thctl disable`.

| Area | Apps and hook names |
| --- | --- |
| Browsers | Firefox (`firefox`), Qutebrowser (`qutebrowser`), Zen Browser (`zen`) |
| Editors | Cursor (`cursor`), Typora (`typora`), VS Code (`vscode`), Windsurf (`windsurf`), Zed (`zed`) |
| Desktop and terminal | Cava (`cava`), Fish (`fish`), fzf in Fish (`fzf`), GTK (`gtk`), nwg-dock-hyprland (`nwg-dock-hyprland`), Qt 6 (`qt6ct`), Superfile (`superfile`), Vicinae (`vicinae`) |
| Chat and media | ChatGPT Desktop (`chatgpt`), Discord (`discord`), Heroic (`heroic`), Spotify (`spotify`), Steam (`steam`) |

[View the hook scripts](theme-set.d/).

## App setup and troubleshooting

If an app’s colors don’t update, check that its hook is enabled and run `~/.local/bin/thctl run`. Check that app’s line in the output for a missing dependency or a restart message.

- **ChatGPT Desktop** requires Python 3.11 or newer and the `chatgpt` desktop command. The hook updates the matching light or dark appearance and attempts a normal restart if the app is open.
- **Discord** requires a client with custom theme support, such as Vesktop or Equibop. Run the hooks, then enable the **Match System** theme in the client.
- **Firefox and Zen** may need legacy stylesheets enabled. Open `about:config`, set `toolkit.legacyUserProfileCustomizations.stylesheets` to `true`, and restart the browser.
- **Spotify** requires Spicetify. If Spotify updates and the theme stops applying, run `spicetify restore backup apply`. [Spicetify setup for Linux](https://spicetify.app/docs/advanced-usage/installation#note-for-linux-users)
- **Missing `colors.toml`** means the active theme needs a compatible palette file. Update the theme or add a valid `colors.toml`, then reapply it.

## Report an issue or contribute

Include your Omarchy version, the app, and the relevant output from `~/.local/bin/thctl run` when reporting a problem. For a new app hook, use the existing scripts as examples and check the result with a light and a dark theme. [Open an issue](https://github.com/thrddqno/omarchy-theme-hook/issues).

## Credits

This fork builds on imbypass’s Omarchy Theme Hook and reuses its logo and showcase. [Upstream project](https://github.com/imbypass/omarchy-theme-hook) · [Everpuccin theme](https://github.com/imbypass/omarchy-everpuccin-theme) · [Waybar configuration](https://github.com/imbypass/omarchy-waybar-bepi)

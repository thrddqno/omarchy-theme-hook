#! /bin/bash

set -e

omarchy-show-logo

echo "Uninstalling theme hook.."

hooks="$HOME/.config/omarchy/hooks"
manifest="$hooks/.omarchy-theme-hook-files"
if [[ ! -f "$manifest" ]]; then
    echo "No Quattro theme hook installation found."
    exit 0
fi
while IFS= read -r name; do
    if [[ "$name" =~ ^[0-9][0-9]-[a-zA-Z0-9_-]+\.sh$ ]]; then
        rm -f -- "$hooks/theme-set.d/$name"
    fi
done < "$manifest"
rm -f -- "$HOME/.local/bin/thctl" "$hooks/theme-set-lib.sh" "$manifest"

echo "Attempting to unapply theme hook.."

# Remove Steam theme
if [[ -x "$HOME/.local/share/steam-adwaita/install.py" ]]; then
    (cd "$HOME/.local/share/steam-adwaita" && ./install.py --uninstall) >/dev/null 2>&1 || true
fi

# Remove Spotify theme
if command -v spicetify >/dev/null 2>&1; then
    spicetify restore > /dev/null 2>&1 || true
fi

# Remove GTK theme
gsettings set org.gnome.desktop.interface gtk-theme Adwaita > /dev/null 2>&1 || true

# Remove Qutebrowser theme
if command -v qutebrowser >/dev/null 2>&1; then
    rm -rf "$HOME/.config/qutebrowser/omarchy"
    config_file="$HOME/.config/qutebrowser/config.py"
    if [[ -f "$config_file" ]]; then
        sed -i '/import omarchy\.draw/d' "$config_file"
        sed -i '/omarchy\.draw\.apply(c)/d' "$config_file"
    fi
fi

# Remove Vicinae theme
if command -v vicinae >/dev/null 2>&1; then
    vicinae theme set vicinae-dark > /dev/null 2>&1 || true
fi

echo "Uninstalled theme hook!"

omarchy-show-done

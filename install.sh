#! /bin/bash

set -e

# Install prerequisites
if ! pacman -Qi "adw-gtk-theme" &>/dev/null; then
    gum style --border normal --border-foreground 6 --padding "1 2" \
    "\"adw-gtk-theme\" is required to theme GTK applications."

    if gum confirm "Would you like to install \"adw-gtk-theme\"?"; then
        sudo pacman -S adw-gtk-theme
    fi
fi

# Download the fork and install its Quattro hooks.
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
echo "Downloading theme hook..."
git clone --depth 1 --branch main https://github.com/thrddqno/omarchy-theme-hook.git "$work/repo"

hooks="$HOME/.config/omarchy/hooks"
manifest="$hooks/.omarchy-theme-hook-files"
install -Dm755 "$work/repo/thctl" "$HOME/.local/bin/thctl"
install -Dm644 "$work/repo/theme-set-lib.sh" "$hooks/theme-set-lib.sh"
mkdir -p "$hooks/theme-set.d"
for file in "$work"/repo/theme-set.d/*.sh; do
    name=${file##*/}
    destination="$hooks/theme-set.d/$name"
    mode=755
    if [[ -f "$destination" && ! -x "$destination" ]]; then
        mode=644
    fi
    install -m "$mode" "$file" "$destination"
    printf '%s\n' "$name"
done >> "$manifest"
sort -u -o "$manifest" "$manifest"

echo "Running theme hook..."
omarchy-hook theme-set
omarchy-show-done

#!/bin/bash
[[ -x "$0" ]] || exit 0
source "$HOME/.config/omarchy/hooks/theme-set-lib.sh" --logging-only || exit 1
app=${0##*/}
app=${app#*-}
run_app_theme "${app%.sh}"

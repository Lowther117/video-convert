#!/bin/bash
# Double-click this file. The program itself is in the "app" folder; this only starts it.
TOP="$(cd "$(dirname "$0")" && pwd)" || exit 1
exec /bin/zsh "$TOP/app/convert-mac.command" "$@"

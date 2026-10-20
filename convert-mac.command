#!/bin/zsh
# Double-click to run. Converts every video in a folder to Mac + PC compatible MP4.
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found - installing Xcode command line tools (includes Python)..."
    xcode-select --install
    echo "Re-run this file once the install has finished."
    read -k1 -s "?Press any key to close."
    exit 1
fi

if [[ -n "$1" ]]; then
    FOLDER="$1"
else
    read "FOLDER?Folder of videos to convert (drag it into this window, then Enter): "
fi
FOLDER="${FOLDER%% }"      # strip trailing space left by Finder drag
FOLDER="${FOLDER//\\ / }"  # unescape spaces from Finder drag

python3 "$(dirname "$0")/convert_videos.py" "$FOLDER" "${@:2}"
echo
read -k1 -s "?Finished. Press any key to close."

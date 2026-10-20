# Video Converter

Makes every video in a folder play on both Mac and Windows, with nothing extra installed on either.

Drop a folder on it and you get a `_Converted` folder alongside the originals, every file as MP4 / H.264 (High profile, 8-bit) / AAC / faststart. That is the one combination QuickTime, Apple TV, Windows Media Player, Films & TV and every browser play out of the box. HEVC is converted too, because Windows needs a paid extension for it.

It is not a blind re-encode. Each file is probed first:

- already H.264 8-bit + AAC in MP4/MOV → remuxed only (lossless, seconds)
- H.264 video but the wrong audio (AC3, MP3, Opus, …) → video copied, audio re-encoded
- anything else (HEVC, VP9, AV1, MPEG-2, WMV, DivX, 10-bit, MKV, AVI, …) → re-encoded at CRF 18

Originals are never touched. Subtitle and data tracks are dropped. Odd frame sizes are rounded to even so the encoder does not refuse them. Re-running skips files already converted.

## Run

**Windows** – drag the video folder onto `convert-windows.bat`, or double-click it and paste the path.

**Mac** – once: `chmod +x convert-mac.command`, then double-click it (or run it with the folder as an argument).

**Any terminal**

```
python convert_videos.py "<folder>"
python convert_videos.py "<folder>" --crf 22    # smaller files (18 default, lower = better)
python convert_videos.py "<folder>" --force     # redo files already in _Converted
```

Needs Python 3.8+ and ffmpeg. If ffmpeg is not on the PATH the script fetches it once: on Windows the gyan.dev static build into `_ffmpeg\` next to the script; on Mac through Homebrew, falling back to a static build. No pip packages, standard library only. The Windows launcher installs Python with winget if it is missing.

## Files

| File | What it is |
|---|---|
| `convert_videos.py` | the converter (Mac, Windows, Linux) |
| `convert-windows.bat` | double-click / drag-and-drop launcher for Windows |
| `convert-mac.command` | double-click launcher for Mac |

## Licence

MIT No Attribution – see `LICENSE`.

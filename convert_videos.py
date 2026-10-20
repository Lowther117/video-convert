#!/usr/bin/env python3
"""
convert_videos.py - make every video in a folder play on both Mac and Windows.

Target format (the one combination both QuickTime and Windows play out of the box):
    MP4 container, H.264 video (High profile, 8-bit yuv420p), AAC audio, faststart.

What it does
    * Walks the folder recursively and picks up every common video extension.
    * Probes each file with ffmpeg. If it is ALREADY H.264 8-bit + AAC in an MP4/MOV/M4V
      container it is just remuxed (stream copy, lossless, seconds per file).
      If only the audio is wrong, the video is copied and only the audio is re-encoded.
      Anything else (HEVC/H.265, VP9, AV1, MPEG-2, WMV, DivX, 10-bit H.264, MKV/AVI/etc.)
      is fully re-encoded.
    * Writes the result to  <folder>/_Converted/  mirroring the original sub-folders,
      always as .mp4. Originals are never touched.
    * Finds ffmpeg on PATH; if it is missing it fetches one itself (Windows: gyan.dev
      static build into _ffmpeg\\ next to this script; Mac: Homebrew, falling back to a
      static build).

Usage
    python convert_videos.py "<folder>"            convert everything in that folder
    python convert_videos.py "<folder>" --force    redo files already in _Converted
    python convert_videos.py "<folder>" --crf 20   quality knob (lower = better/bigger, 18 default)
    python convert_videos.py                       prompts for the folder path
"""

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

VIDEO_EXTS = {
    ".mp4", ".m4v", ".mov", ".mkv", ".avi", ".wmv", ".asf", ".flv", ".f4v", ".webm",
    ".mpg", ".mpeg", ".mpe", ".m2v", ".ts", ".m2ts", ".mts", ".vob", ".3gp", ".3g2",
    ".ogv", ".ogm", ".divx", ".rm", ".rmvb", ".dv", ".mxf", ".hevc", ".h264", ".264", ".265",
}
OUTPUT_DIRNAME = "_Converted"
SCRIPT_DIR = Path(__file__).resolve().parent
TOOLS_DIR = SCRIPT_DIR / "_ffmpeg"
IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

WIN_FFMPEG_ZIP = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
MAC_FFMPEG_ZIP = "https://evermeet.cc/ffmpeg/getrelease/zip"
MAC_FFPROBE_ZIP = "https://evermeet.cc/ffmpeg/getrelease/ffprobe/zip"


# --------------------------------------------------------------------------- ffmpeg lookup
def _exe(name: str) -> str:
    return name + (".exe" if IS_WIN else "")


def _find_in_tools(name: str):
    if not TOOLS_DIR.exists():
        return None
    for p in TOOLS_DIR.rglob(_exe(name)):
        if p.is_file():
            return str(p)
    return None


def _download(url: str, dest: Path):
    print(f"  downloading {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def _unzip(zip_path: Path, into: Path):
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(into)
    zip_path.unlink(missing_ok=True)
    if not IS_WIN:
        for p in into.rglob("*"):
            if p.is_file() and p.name in ("ffmpeg", "ffprobe"):
                p.chmod(0o755)


def ensure_ffmpeg():
    """Return (ffmpeg_path, ffprobe_path_or_None), installing ffmpeg if needed."""
    ff = shutil.which("ffmpeg") or _find_in_tools("ffmpeg")
    fp = shutil.which("ffprobe") or _find_in_tools("ffprobe")
    if ff:
        return ff, fp

    print("ffmpeg not found - fetching it now (one-off).")
    if IS_MAC and shutil.which("brew"):
        print("  brew install ffmpeg")
        subprocess.run(["brew", "install", "ffmpeg"], check=False)
        ff = shutil.which("ffmpeg")
        fp = shutil.which("ffprobe")
        if ff:
            return ff, fp

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    if IS_WIN:
        z = TOOLS_DIR / "ffmpeg.zip"
        _download(WIN_FFMPEG_ZIP, z)
        _unzip(z, TOOLS_DIR)
    elif IS_MAC:
        for url in (MAC_FFMPEG_ZIP, MAC_FFPROBE_ZIP):
            z = TOOLS_DIR / "dl.zip"
            _download(url, z)
            _unzip(z, TOOLS_DIR)
        for name in ("ffmpeg", "ffprobe"):
            p = TOOLS_DIR / name
            if p.exists():
                subprocess.run(["xattr", "-d", "com.apple.quarantine", str(p)],
                               capture_output=True)
    else:
        sys.exit("ffmpeg is not installed. Install it with your package manager and re-run.")

    ff = _find_in_tools("ffmpeg")
    fp = _find_in_tools("ffprobe")
    if not ff:
        sys.exit("Could not obtain ffmpeg automatically. Install it manually and re-run.")
    return ff, fp


# --------------------------------------------------------------------------- probing
def probe(ffmpeg: str, ffprobe, path: Path) -> dict:
    """Return {'vcodec','vprofile','pix_fmt','acodec','has_video','has_audio'}."""
    info = {"vcodec": None, "vprofile": "", "pix_fmt": "", "acodec": None,
            "has_video": False, "has_audio": False}

    if ffprobe:
        try:
            out = subprocess.run(
                [ffprobe, "-v", "error", "-print_format", "json", "-show_streams", str(path)],
                capture_output=True, text=True, timeout=60).stdout
            for s in json.loads(out).get("streams", []):
                if s.get("codec_type") == "video" and not info["has_video"]:
                    # skip embedded cover art
                    if s.get("disposition", {}).get("attached_pic"):
                        continue
                    info.update(has_video=True, vcodec=s.get("codec_name"),
                                vprofile=str(s.get("profile", "")), pix_fmt=s.get("pix_fmt", ""))
                elif s.get("codec_type") == "audio" and not info["has_audio"]:
                    info.update(has_audio=True, acodec=s.get("codec_name"))
            return info
        except Exception:
            pass  # fall through to ffmpeg -i parsing

    err = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True, timeout=60).stderr
    for line in err.splitlines():
        m = re.search(r"Stream #\d+:\d+.*?: Video: (\w+)(?: \(([^)]*)\))?.*?, (\w+)", line)
        if m and not info["has_video"]:
            info.update(has_video=True, vcodec=m.group(1).lower(),
                        vprofile=(m.group(2) or ""), pix_fmt=m.group(3))
            continue
        m = re.search(r"Stream #\d+:\d+.*?: Audio: (\w+)", line)
        if m and not info["has_audio"]:
            info.update(has_audio=True, acodec=m.group(1).lower())
    return info


def plan(path: Path, info: dict):
    """Decide copy/encode per stream. Returns (video_mode, audio_mode)."""
    video_ok = (
        info["vcodec"] == "h264"
        and info["pix_fmt"] in ("yuv420p", "yuvj420p")
        and "10" not in info["vprofile"]
        and "4:2:2" not in info["vprofile"]
        and "4:4:4" not in info["vprofile"]
    )
    container_ok = path.suffix.lower() in (".mp4", ".m4v", ".mov")
    audio_ok = (not info["has_audio"]) or info["acodec"] == "aac"
    return ("copy" if (video_ok and container_ok) else "encode",
            "copy" if (audio_ok and container_ok) else "encode")


# --------------------------------------------------------------------------- conversion
def convert(ffmpeg: str, src: Path, dst: Path, vmode: str, amode: str, crf: int) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".part.mp4")
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-stats", "-y",
           "-i", str(src), "-map", "0:v:0", "-map", "0:a?", "-sn", "-dn",
           "-map_metadata", "0"]
    if vmode == "copy":
        cmd += ["-c:v", "copy"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
    if amode == "copy":
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", str(tmp)]

    r = subprocess.run(cmd)
    if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(dst)
    return True


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main():
    args = [a for a in sys.argv[1:]]
    force = "--force" in args
    crf = 18
    if "--crf" in args:
        i = args.index("--crf")
        crf = int(args[i + 1])
        del args[i:i + 2]
    args = [a for a in args if not a.startswith("--")]

    folder = Path(args[0]).expanduser() if args else None
    if folder is None:
        folder = Path(input("Folder of videos to convert: ").strip().strip('"').strip("'")).expanduser()
    folder = folder.resolve()
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")

    ffmpeg, ffprobe = ensure_ffmpeg()
    out_root = folder / OUTPUT_DIRNAME

    files = sorted(
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS and out_root not in p.parents
    )
    if not files:
        sys.exit(f"No video files found under {folder}")

    print(f"\n{len(files)} video(s) found in {folder}")
    print(f"Output -> {out_root}\n")

    done = remuxed = encoded = skipped = failed = 0
    t0 = time.time()
    for i, src in enumerate(files, 1):
        rel = src.relative_to(folder)
        dst = out_root / rel.with_suffix(".mp4")
        if dst.exists() and not force:
            print(f"[{i}/{len(files)}] skip (exists)  {rel}")
            skipped += 1
            continue

        info = probe(ffmpeg, ffprobe, src)
        if not info["has_video"]:
            print(f"[{i}/{len(files)}] FAIL (no video stream)  {rel}")
            failed += 1
            continue
        vmode, amode = plan(src, info)
        label = ("remux" if vmode == "copy" and amode == "copy"
                 else "audio-only" if vmode == "copy"
                 else "re-encode")
        print(f"[{i}/{len(files)}] {label:10s} {rel}  "
              f"({info['vcodec']} {info['pix_fmt']} / {info['acodec'] or 'no audio'})")

        t1 = time.time()
        ok = convert(ffmpeg, src, dst, vmode, amode, crf)
        if ok:
            print(f"      done in {time.time() - t1:.0f}s  "
                  f"{human(src.stat().st_size)} -> {human(dst.stat().st_size)}")
            done += 1
            if label == "remux":
                remuxed += 1
            else:
                encoded += 1
        else:
            print("      FAILED - see ffmpeg error above")
            failed += 1

    print(f"\nFinished in {(time.time() - t0) / 60:.1f} min: "
          f"{done} written ({remuxed} remuxed, {encoded} encoded), "
          f"{skipped} skipped, {failed} failed.")
    print(f"Converted files are in: {out_root}")


if __name__ == "__main__":
    main()

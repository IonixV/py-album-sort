#!/usr/bin/env python3
"""
Sort music files (and matching .lrc lyric files) into folders named:
    AlbumName (Year)

- Linux-friendly (uses pathlib, safe renames, no OS-specific paths)
- Moves associated .lrc file that shares the same base filename as the audio
- Creates destination folders if needed

Usage:
  python3 sort_music_by_album.py /path/to/music

If you omit the directory, it defaults to the current working directory:
  python3 sort_music_by_album.py

Optional:
  --dry-run   : print actions without moving
  --recursive : walk subdirectories

Notes about network mounts (SMB/KIO FUSE, etc.):
  Some mounts don't support atomic renames or metadata operations (utime/chmod).
  This script falls back to a safe copy+delete move without preserving metadata
  when needed.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Iterable

# Audio extensions we will consider
AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".mp4", ".aac", ".ogg", ".opus", ".wav", ".aiff", ".alac", ".wma"}

# Mutagen is used to read tags across formats
try:
    from mutagen import File as MutagenFile
except ImportError as e:
    raise SystemExit(
        "Missing dependency: mutagen\n\n"
        "Install on Debian/Ubuntu:  sudo apt-get install python3-mutagen\n"
        "or via pip:               pip3 install mutagen\n"
    ) from e


def sanitize_folder_name(name: str) -> str:
    """Make a safe Linux folder name."""
    name = name.replace("/", " - ")
    name = re.sub(r"[\x00-\x1f]", "", name)  # control chars
    name = re.sub(r"\s+", " ", name).strip()
    return name if name else "Unknown Album"


def extract_year(date_str: str) -> Optional[str]:
    """Extract a 4-digit year from common date formats."""
    m = re.search(r"\b(\d{4})\b", date_str or "")
    return m.group(1) if m else None


def first_of(value):
    """Return first element if list-like, else the value itself."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


@dataclass
class TrackInfo:
    album: str
    year: str


def read_tags(path: Path) -> TrackInfo:
    """Read album + year from tags using mutagen."""
    audio = MutagenFile(path)
    if audio is None or getattr(audio, "tags", None) is None:
        return TrackInfo(album="Unknown Album", year="Unknown Year")

    tags = audio.tags

    album = (
        first_of(tags.get("album"))
        or first_of(tags.get("TALB"))
        or first_of(tags.get("\xa9alb"))
        or "Unknown Album"
    )

    date_val = (
        first_of(tags.get("date"))
        or first_of(tags.get("year"))
        or first_of(tags.get("TDRC"))
        or first_of(tags.get("TYER"))
        or first_of(tags.get("\xa9day"))
        or ""
    )

    album_str = sanitize_folder_name(str(album))
    year = extract_year(str(date_val)) or "Unknown Year"

    return TrackInfo(album=album_str, year=year)


def iter_audio_files(root: Path, recursive: bool) -> Iterable[Path]:
    if recursive:
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                yield p
    else:
        for p in root.iterdir():
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                yield p


def _copy_then_delete(src: Path, dst: Path) -> None:
    """Copy file contents to dst (no metadata) then delete src."""
    # Ensure parent exists
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Copy data only (avoid copystat/utime issues on some network mounts)
    with src.open("rb") as fsrc, dst.open("wb") as fdst:
        shutil.copyfileobj(fsrc, fdst, length=1024 * 1024)

    # Best-effort preserve executable bit is irrelevant here; still, try to delete src
    src.unlink()


def move_file(src: Path, dst: Path, dry_run: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)

    final_dst = dst
    if final_dst.exists():
        stem = dst.stem
        suffix = dst.suffix
        i = 1
        while final_dst.exists():
            final_dst = dst.with_name(f"{stem} ({i}){suffix}")
            i += 1

    if dry_run:
        print(f"DRY-RUN: move {src} -> {final_dst}")
        return

    # Fast path: atomic rename/replace on same filesystem
    try:
        os.replace(src, final_dst)
        return
    except OSError:
        pass

    # Fallback: some mounts (e.g. SMB via KIO FUSE) may fail rename or metadata ops.
    # Do a safe copy (data only) + delete.
    try:
        _copy_then_delete(src, final_dst)
    except Exception:
        # If copy failed and we might have created a partial destination, try to remove it
        try:
            if final_dst.exists():
                final_dst.unlink()
        except Exception:
            pass
        raise


def main() -> int:
    ap = argparse.ArgumentParser(description="Sort music + matching .lrc files into AlbumName (Year) folders.")
    ap.add_argument(
        "music_dir",
        type=Path,
        nargs="?",
        default=Path.cwd(),
        help="Root music directory to sort (default: current working directory)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print actions without moving files")
    ap.add_argument("--recursive", action="store_true", help="Process files in subdirectories")
    args = ap.parse_args()

    root = args.music_dir.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: not a directory: {root}")
        return 2

    for audio_path in iter_audio_files(root, recursive=args.recursive):
        info = read_tags(audio_path)
        album_folder = f"{info.album} ({info.year})"
        dest_dir = root / album_folder

        dest_audio = dest_dir / audio_path.name

        # Move audio
        move_file(audio_path, dest_audio, dry_run=args.dry_run)

        # Move matching .lrc (same basename) if present next to original audio
        lrc_src = audio_path.with_suffix(".lrc")
        if lrc_src.exists() and lrc_src.is_file():
            dest_lrc = dest_dir / lrc_src.name
            move_file(lrc_src, dest_lrc, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

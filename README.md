# py-album-sort

A Linux-friendly Python script that sorts music files into album folders named:

`AlbumName (Year)`

It also moves a matching lyric file (`.lrc`) **with the same base filename** as the audio track.

## Features

- Reads metadata (**album** and **year/date**) from audio tags
- Moves audio files into `AlbumName (Year)` folders
- Moves associated `.lrc` lyrics file alongside the audio file (if present)
- Creates destination album folders automatically
- Linux-compatible paths via `pathlib`

## Requirements

- Python 3
- `mutagen`

Install:

```bash
pip3 install mutagen
```

(Alternatively, on Debian/Ubuntu you can install `python3-mutagen` via apt.)

## Usage

### Sort only the top-level directory

```bash
python3 sort_music_by_album.py ~/Music
```

### Sort including subfolders (`--recursive`)

```bash
python3 sort_music_by_album.py ~/Music --recursive
```

### Dry run (prints what it *would* do)

```bash
python3 sort_music_by_album.py ~/Music --dry-run --recursive
```

## Notes

- If a destination filename already exists, the script will append a numeric suffix like `" (1)"` to avoid overwriting.
- If tags are missing, it falls back to `Unknown Album (Unknown Year)`.

## License

The Unlicense (public domain). See `LICENSE`.

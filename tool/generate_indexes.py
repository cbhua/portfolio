#!/usr/bin/env python3
"""
Generate index.json files for photo albums.

By default, this scans the ./photos directory and, for each album folder,
creates (or updates) an index.json containing a JSON array of image filenames.

Usage:
  python3 tool/generate_indexes.py
  python3 tool/generate_indexes.py --root photos --dry-run

Options:
  --root PATH        Root photos directory (default: photos)
  --recursive        Recurse into nested album folders (default: one level)
  --no-overwrite     Skip albums that already have index.json
  --dry-run          Print actions without writing files
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List
import re
import sys

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
SKIP_DIRS = {".originals"}


def natural_key(s: str):
    """
    Sort helper: breaks a string into text and integer chunks for natural order.
    Example: DSC_2.jpg < DSC_10.jpg
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.findall(r"\d+|\D+", s)]


def list_album_files(album_dir: Path) -> List[str]:
    files = []
    for p in album_dir.iterdir():
        if not p.is_file():
            continue
        if p.name == "index.json":
            continue
        if p.suffix.lower() in IMAGE_EXTS:
            files.append(p.name)
    files.sort(key=natural_key)
    return files


def iter_albums(root: Path, recursive: bool) -> Iterable[Path]:
    if recursive:
        for p in root.rglob("*"):
            if p.is_dir() and p.name not in SKIP_DIRS:
                yield p
    else:
        for p in root.iterdir():
            if p.is_dir() and p.name not in SKIP_DIRS:
                yield p


def write_index(album: Path, files: List[str], *, dry_run: bool) -> None:
    index_path = album / "index.json"
    if dry_run:
        print(f"[DRY] {index_path}: {len(files)} files")
        return
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(files, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Wrote {index_path} ({len(files)} entries)")

    # Also write a JS fallback for local file:// previews where fetch() is blocked
    index_js_path = album / "index.js"
    js = "window.ALBUM_FILES = " + json.dumps(files, ensure_ascii=False) + ";\n"
    index_js_path.write_text(js, encoding="utf-8")
    print(f"Wrote {index_js_path} (JS fallback)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate index.json for photo albums.")
    parser.add_argument("--root", default="photos", type=str, help="Root directory that contains album folders")
    parser.add_argument("--recursive", action="store_true", help="Recurse into nested album folders")
    parser.add_argument("--no-overwrite", action="store_true", help="Skip albums that already contain index.json")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Root not found or not a directory: {root}", file=sys.stderr)
        return 1

    albums = list(iter_albums(root, args.recursive))
    if not albums:
        print("No album folders found.")
        return 0

    total_albums = 0
    total_files = 0
    for album in albums:
        if args.no_overwrite and (album / "index.json").exists():
            print(f"Skip (exists): {album / 'index.json'}")
            continue
        files = list_album_files(album)
        if not files:
            # nothing to index; skip quietly
            continue
        write_index(album, files, dry_run=args.dry_run)
        total_albums += 1
        total_files += len(files)

    print(f"\nIndexed albums: {total_albums}, total images listed: {total_files}")
    if args.dry_run:
        print("Dry run only. No files were written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



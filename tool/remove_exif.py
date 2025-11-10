#!/usr/bin/env python3
"""
Remove EXIF and other embedded metadata from images inside the photos/ directory.

Usage:
  python3 tool/remove_exif.py               # Process ./photos recursively, in-place
  python3 tool/remove_exif.py --dry-run     # Show what would be changed
  python3 tool/remove_exif.py --backup      # Save originals next to images under .originals/
  python3 tool/remove_exif.py --root PATH   # Process a custom photos root

Notes:
- Uses Pillow only. We recreate files without EXIF; for JPEG we also auto-apply EXIF orientation.
- Keeps ICC profiles to preserve color where available.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, Tuple

try:
    from PIL import Image, ImageOps
except Exception as exc:
    print("This tool requires Pillow. Install with:\n\n  pip install -r tool/requirements.txt\n", file=sys.stderr)
    raise


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def iter_image_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def make_backup_path(original: Path, backup_root: Path) -> Path:
    relative = original.relative_to(backup_root.parent) if str(original).startswith(str(backup_root.parent)) else original.name
    # Place alongside original under ".originals" directory at the album root
    album_root = original.parent
    dst_dir = album_root / ".originals"
    dst_dir.mkdir(exist_ok=True)
    return dst_dir / original.name


def strip_metadata(src: Path, *, dry_run: bool, backup: bool, jpeg_quality: int = 95) -> Tuple[bool, str]:
    """
    Returns (changed, message)
    """
    try:
        with Image.open(src) as im:
            icc = im.info.get("icc_profile")
            fmt = (im.format or "").upper()

            # If the file has no EXIF now, skip to avoid re-encoding again
            if fmt in ("JPG", "JPEG") and not im.info.get("exif"):
                return True, f"Already clean (no EXIF): {src}"

            # Normalize orientation based on EXIF (prevents rotated output after EXIF removal)
            im = ImageOps.exif_transpose(im)

            # Work on a copy to avoid altering the original stream in place
            out = im.copy()

            # Build save params
            save_kwargs = {}
            if icc:
                save_kwargs["icc_profile"] = icc
            if fmt in ("JPG", "JPEG"):
                fmt = "JPEG"
                save_kwargs["quality"] = jpeg_quality
                save_kwargs["optimize"] = True
                # Ensure no EXIF is carried through
                save_kwargs["exif"] = b""
            elif fmt in ("PNG",):
                fmt = "PNG"
                # Ensure no exif/pnginfo carried
                save_kwargs["pnginfo"] = None
            elif fmt in ("WEBP",):
                fmt = "WEBP"
                save_kwargs["quality"] = 95
            elif fmt in ("TIFF", "TIF"):
                fmt = "TIFF"

            # Save to a temporary path, then atomically replace
            tmp_path = src.with_suffix(src.suffix + ".tmp_nox")

            if dry_run:
                return True, f"[DRY] would strip EXIF: {src}"

            if backup:
                backup_path = make_backup_path(src, src.parent)
                if not backup_path.exists():
                    backup_path.write_bytes(src.read_bytes())

            # Always remove EXIF by not including any metadata other than ICC
            out.save(tmp_path, fmt, **save_kwargs)
            tmp_path.replace(src)
            return True, f"Stripped EXIF: {src}"
    except Exception as e:
        return False, f"ERROR processing {src}: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Strip EXIF/metadata from images under the photos/ directory.")
    parser.add_argument("--root", type=str, default="photos", help="Path to photos root (default: photos)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes; just print what would happen")
    parser.add_argument("--backup", action="store_true", help="Save original files under a .originals/ folder in each album")
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality when re-saving (default: 95)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Root not found or not a directory: {root}", file=sys.stderr)
        return 1

    total = 0
    changed = 0
    errors = 0
    for img_path in iter_image_files(root):
        total += 1
        ok, msg = strip_metadata(img_path, dry_run=args.dry_run, backup=args.backup, jpeg_quality=args.quality)
        if ok:
            changed += 1
        else:
            errors += 1
        print(msg)

    print(f"\nProcessed: {total}, changed: {changed}, errors: {errors}")
    if args.dry_run:
        print("Dry run only. No files were modified.")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())



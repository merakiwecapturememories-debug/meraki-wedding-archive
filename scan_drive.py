#!/usr/bin/env python3
"""
Meraki Archive — Fast Drive Scanner
------------------------------------
Scans every top-level folder on a drive (e.g. each wedding/event folder)
and reports its total size, using native OS file calls instead of a
browser. This finishes in seconds instead of minutes, even on drives
with tens of thousands of RAW photos/videos — because it never goes
through a browser's sandboxed File System Access API, which has real
per-file overhead that adds up fast on huge folders.

USAGE
  1. Install Python 3 if you don't have it: https://www.python.org/downloads/
  2. Double-click this file, OR run from a terminal:
       python scan_drive.py
  3. When prompted, type or paste the drive's folder path, e.g.:
       Windows:  D:\
       Mac:      /Volumes/Meraki HDD 101
  4. It prints a summary table and writes scan_results.csv next to this script.
  5. Open the Meraki Archive app -> Scan connected drive -> "Paste scan
     results" -> paste the CSV contents (or open the .csv and copy it in).

No data leaves your computer. This script only reads folder sizes —
it never uploads, deletes, or modifies anything.
"""

import os
import sys
import csv
import re
import time


def human_gb(num_bytes):
    return round(num_bytes / (1024 ** 3), 2)


def guess_date_from_name(name):
    m = re.search(r'(\d{4})[-_.](\d{1,2})[-_.](\d{1,2})', name)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r'(\d{1,2})[-_.](\d{1,2})[-_.](\d{4})', name)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return ""


def guess_client_from_name(name):
    cleaned = re.sub(r'(\d{4})[-_.](\d{1,2})[-_.](\d{1,2})', '', name)
    cleaned = re.sub(r'(\d{1,2})[-_.](\d{1,2})[-_.](\d{4})', '', cleaned)
    cleaned = re.sub(r'[-_]+', ' ', cleaned).strip()
    return cleaned or name


SYSTEM_FOLDER_SKIPLIST = {
    "$recycle.bin", "system volume information", ".trashes", ".trash",
    ".fseventsd", ".spotlight-v100", ".temporaryitems",
    ".documentrevisions-v100", "lost+found",
}


def is_system_folder(name):
    return name.lower() in SYSTEM_FOLDER_SKIPLIST


def folder_size_bytes(path):
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += folder_size_bytes(entry.path)
            except (PermissionError, OSError):
                continue  # skip unreadable file/folder, same as the web app
    except (PermissionError, OSError):
        pass
    return total


def main():
    print("=" * 60)
    print("Meraki Archive — Fast Drive Scanner")
    print("=" * 60)

    if len(sys.argv) > 1:
        root = sys.argv[1]
    else:
        root = input("\nPaste the drive/folder path to scan: ").strip().strip('"')

    if not os.path.isdir(root):
        print(f"\n'{root}' isn't a folder I can find. Check the path and try again.")
        sys.exit(1)

    top_level = [e for e in os.scandir(root) if e.is_dir(follow_symlinks=False) and not is_system_folder(e.name)]
    if not top_level:
        print(f"\nNo subfolders found inside '{root}'.")
        sys.exit(0)

    print(f"\nFound {len(top_level)} folders. Scanning...\n")

    rows = []
    start = time.time()
    for i, entry in enumerate(top_level, 1):
        t0 = time.time()
        size_bytes = folder_size_bytes(entry.path)
        size_gb = human_gb(size_bytes)
        rows.append({
            "folder": entry.name,
            "size_gb": size_gb,
            "guessed_client": guess_client_from_name(entry.name),
            "guessed_date": guess_date_from_name(entry.name),
        })
        print(f"  [{i}/{len(top_level)}] {entry.name:<45} {size_gb:>10.2f} GB   ({time.time()-t0:.1f}s)")

    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f} seconds — {len(top_level)} folders.")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan_results.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["folder", "size_gb", "guessed_client", "guessed_date"])
        for r in rows:
            writer.writerow([r["folder"], r["size_gb"], r["guessed_client"], r["guessed_date"]])

    print(f"\nSaved: {out_path}")
    print("\nOpen the Meraki Archive app -> Scan connected drive -> 'Paste scan results',")
    print("then paste the contents of scan_results.csv (or copy the block below):\n")
    print("-" * 60)
    print("folder,size_gb,guessed_client,guessed_date")
    for r in rows:
        print(f'{r["folder"]},{r["size_gb"]},{r["guessed_client"]},{r["guessed_date"]}')
    print("-" * 60)

    input("\nPress Enter to close...")


if __name__ == "__main__":
    main()

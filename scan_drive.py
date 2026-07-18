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
    # Decimal GB (1000-based), matching how drive capacities are labeled by manufacturers
    # and how the web app's drive capacity field works — NOT binary GiB (1024-based),
    # which is what Windows' own Properties dialog confusingly shows as "GB"/"TB".
    return round(num_bytes / (1000 ** 3), 2)


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
FOUND_DOT_PATTERN = re.compile(r'^found\.\d{3}$', re.IGNORECASE)


def is_system_folder(name):
    return name.lower() in SYSTEM_FOLDER_SKIPLIST or bool(FOUND_DOT_PATTERN.match(name))


def long_path_safe(path):
    """On Windows, prefix with \\\\?\\ to bypass the classic 260-character MAX_PATH
    limit. Deeply nested folders (Event > Video > 01 > files...) hit this constantly
    and cause silent read failures otherwise — this is the actual fix, not a workaround."""
    if sys.platform.startswith("win") and not path.startswith("\\\\?\\"):
        abs_path = os.path.abspath(path)
        return "\\\\?\\" + abs_path
    return path


def folder_size_bytes(path, failure_counter):
    total = 0
    safe_path = long_path_safe(path)
    try:
        for entry in os.scandir(safe_path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += folder_size_bytes(entry.path, failure_counter)
            except (PermissionError, OSError):
                failure_counter[0] += 1  # track, don't silently drop — often a long-path issue
                continue
    except (PermissionError, OSError):
        failure_counter[0] += 1
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

    all_dirs = [e for e in os.scandir(root) if e.is_dir(follow_symlinks=False)]
    top_level = [e for e in all_dirs if not is_system_folder(e.name)]
    found_dot_skipped = sum(1 for e in all_dirs if FOUND_DOT_PATTERN.match(e.name))
    if not top_level:
        print(f"\nNo subfolders found inside '{root}'.")
        sys.exit(0)

    print(f"\nFound {len(top_level)} folders. Scanning...\n")

    rows = []
    total_failures = 0
    start = time.time()
    for i, entry in enumerate(top_level, 1):
        t0 = time.time()
        failure_counter = [0]
        size_bytes = folder_size_bytes(entry.path, failure_counter)
        size_gb = human_gb(size_bytes)
        total_failures += failure_counter[0]
        rows.append({
            "folder": entry.name,
            "size_gb": size_gb,
            "guessed_client": guess_client_from_name(entry.name),
            "guessed_date": guess_date_from_name(entry.name),
            "failed_reads": failure_counter[0],
        })
        warn = f"  ⚠ {failure_counter[0]} unreadable item(s)" if failure_counter[0] else ""
        print(f"  [{i}/{len(top_level)}] {entry.name:<45} {size_gb:>10.2f} GB   ({time.time()-t0:.1f}s){warn}")

    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f} seconds — {len(top_level)} folders.")
    if total_failures:
        print(f"\n⚠ WARNING: {total_failures} file(s)/folder(s) couldn't be read across this scan.")
        print("This almost always means Windows' 260-character path limit was hit somewhere")
        print("in a deeply-nested folder — meaning some sizes above may be undercounted.")
        print("Fix: enable long path support in Windows —")
        print("  Run PowerShell as Administrator and paste:")
        print('  New-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem" '
              '-Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force')
        print("  Then restart your computer and run this script again.")
    if found_dot_skipped:
        print(f"(Skipped {found_dot_skipped} 'FOUND.###' recovery folder(s) — this drive had a "
              f"CHKDSK recovery at some point, which usually means an improper ejection or file "
              f"system error. Worth running a health/SMART check on it.)")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan_results.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["folder", "size_gb", "guessed_client", "guessed_date", "failed_reads"])
        for r in rows:
            writer.writerow([r["folder"], r["size_gb"], r["guessed_client"], r["guessed_date"], r["failed_reads"]])

    print(f"\nSaved: {out_path}")
    print("\nOpen the Meraki Archive app -> Scan connected drive -> 'Paste scan results',")
    print("then paste the contents below (the app only reads the first 4 columns):\n")
    print("-" * 60)
    print("folder,size_gb,guessed_client,guessed_date")
    for r in rows:
        print(f'{r["folder"]},{r["size_gb"]},{r["guessed_client"]},{r["guessed_date"]}')
    print("-" * 60)

    input("\nPress Enter to close...")


if __name__ == "__main__":
    main()

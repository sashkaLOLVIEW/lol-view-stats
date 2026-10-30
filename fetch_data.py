#!/usr/bin/env python3
"""Download the newest Oracle's Elixir match-data CSV from their public Google Drive folder.

    python fetch_data.py            -> data/2026_LoL_esports_match_data_from_OraclesElixir.csv

Two methods, tried in this order:
  1. Google Drive API (reliable). Needs a free API key in the environment variable DRIVE_API_KEY.
  2. gdown (no key needed, but Google sometimes refuses automated downloads).
If both fail, the script exits with an error and the workflow stops without touching the live site.
"""
import os, sys, shutil, tempfile
from pathlib import Path

FOLDER_ID = "1gLSw0RLjBbtaNy0dgnGQDAZOHIgCe-HH"
FILE_NAME = "2026_LoL_esports_match_data_from_OraclesElixir.csv"
OUT = Path(__file__).resolve().parent / "data" / FILE_NAME
MIN_BYTES = 20_000_000        # a real file is ~80 MB; anything tiny is an error page

def via_api(key):
    import requests
    r = requests.get("https://www.googleapis.com/drive/v3/files", timeout=60, params={
        "q": f"'{FOLDER_ID}' in parents and name = '{FILE_NAME}' and trashed = false",
        "fields": "files(id,name,size,modifiedTime)", "key": key, "pageSize": 10})
    r.raise_for_status()
    files = r.json().get("files", [])
    if not files: raise RuntimeError("file not found in folder: " + FILE_NAME)
    f = max(files, key=lambda x: x["modifiedTime"])
    print("API: found", f["name"], f.get("size"), "bytes, modified", f["modifiedTime"])
    with requests.get(f"https://www.googleapis.com/drive/v3/files/{f['id']}", params={"alt": "media", "key": key}, stream=True, timeout=600) as d:
        d.raise_for_status()
        with open(OUT, "wb") as fh:
            for chunk in d.iter_content(1 << 20): fh.write(chunk)     # iter_content handles gzip; d.raw would not

def via_gdown():
    import gdown
    tmp = tempfile.mkdtemp()
    kw = dict(id=FOLDER_ID, output=tmp, quiet=True, skip_download=True)   # list the folder only; do not download every file in it
    try: listing = gdown.download_folder(remaining_ok=True, **kw)          # older gdown versions limit folders to 50 files
    except TypeError: listing = gdown.download_folder(**kw)
    hit = next((f for f in listing if os.path.basename(getattr(f, "path", "")) == FILE_NAME), None)
    if not hit: raise RuntimeError("gdown did not find " + FILE_NAME + " in the folder")
    got = gdown.download(id=hit.id, output=str(OUT), quiet=True)
    if not got: raise RuntimeError("gdown could not download the file (Google may be rate-limiting)")

def main():
    OUT.parent.mkdir(exist_ok=True)
    key = os.environ.get("DRIVE_API_KEY", "").strip()
    errors = []
    for name, fn in (("Drive API", lambda: via_api(key)) if key else (None, None), ("gdown", via_gdown)):
        if not name: continue
        try:
            fn()
            if OUT.stat().st_size < MIN_BYTES: raise RuntimeError("downloaded file is only %d bytes" % OUT.stat().st_size)
            print("downloaded via", name, "->", OUT, OUT.stat().st_size, "bytes"); return
        except Exception as e:
            errors.append("%s: %s" % (name, e)); print("  %s failed: %s" % (name, e))
    sys.exit("Could not download the data.\n  " + "\n  ".join(errors))

if __name__ == "__main__":
    main()

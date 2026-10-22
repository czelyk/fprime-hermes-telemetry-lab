"""Use the verified local Go toolchain, or install its pinned public Windows ZIP."""
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
local = ROOT / 'tools/go/bin/go.exe'
if local.exists():
    selected = local
else:
    archive = ROOT / 'downloads/go1.27.3.windows-amd64.zip'
    archive.parent.mkdir(exist_ok=True)
    if not archive.exists():
        urllib.request.urlretrieve('https://go.dev/dl/go1.27.3.windows-amd64.zip', archive)
    expected = 'f26081f438319757f8a1b46d7d0b2c5ec7583d4038e485e0aa725cfde7885fff'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise SystemExit('Go toolchain checksum mismatch')
    target = ROOT / 'tools'
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            path = (target / item.filename).resolve()
            if not path.is_relative_to(target.resolve()):
                raise SystemExit('Invalid archive path')
        source.extractall(target)
    selected = local
print(selected.resolve())

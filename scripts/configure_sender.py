"""Apply the recorded, local Ref deployment configuration (no autocoded edits)."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FP = ROOT / 'vendor/fprime'
BACKUP = ROOT / 'patches/original'
PATCHES = ROOT / 'patches'


def edit(relative, change):
    path = FP / relative
    original = BACKUP / relative
    original.parent.mkdir(parents=True, exist_ok=True)
    if not original.exists():
        original.write_bytes(path.read_bytes())
    before = original.read_text(encoding='utf-8')
    after = change(before)
    if path.read_bytes() != after.encode('utf-8'):
        path.write_text(after, encoding='utf-8', newline='\n')
    diff = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                       fromfile='a/' + relative, tofile='b/' + relative))
    return diff, {'path': relative, 'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
                   'configured_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def remove_wasm_instance(text):
    start = text.index('  instance wasmSeq:')
    end = text.index('  instance dpDemo:', start)
    return text[:start] + text[end:]


def without_wasm_lines(text):
    return ''.join(line for line in text.splitlines(True) if 'wasmSeq' not in line)


if __name__ == '__main__':
    changes = [
        ('Svc/Subtopologies/ComCcsds/ComCcsdsConfig/ComCcsdsConfig.fpp',
         lambda text: text.replace('enablePacketSpanning = false', 'enablePacketSpanning = true')),
        ('TestDeploymentsProject/Ref/Top/instances.fpp', remove_wasm_instance),
        ('TestDeploymentsProject/Ref/Top/topology.fpp', without_wasm_lines),
        ('TestDeploymentsProject/Ref/Top/RefPackets.fppi', without_wasm_lines),
    ]
    patches, manifest = zip(*(edit(path, change) for path, change in changes))
    (PATCHES / 'sender.patch').write_text(''.join(patches), encoding='utf-8')
    (PATCHES / 'sender-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Configured packet spanning; excluded unused Rust/Wasm sequencer from the lab topology.')

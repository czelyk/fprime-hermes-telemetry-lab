"""Deterministic software impairments of an actual sender capture, preserving the original."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('capture', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    raw = args.capture.read_bytes()
    if len(raw) % 1024:
        raise SystemExit('Capture is not an integral number of 1024-byte frames')
    frames = [raw[i:i+1024] for i in range(0, len(raw), 1024)]
    target = next((i for i, frame in enumerate(frames)
                   if 0 < (struct.unpack_from('>H', frame, 4)[0] & 0x7ff) < 1016), None)
    if target is None:
        raise SystemExit('No continuation-ending frame exists in the actual capture')
    args.output.mkdir(parents=True, exist_ok=True)
    dropped = b''.join(frames[:target] + frames[target+1:])
    corrupted = bytearray(raw)
    corrupted[target*1024+26] ^= 1
    cases = {'drop_continuation_frame': dropped, 'crc_error_continuation_frame': bytes(corrupted)}
    manifest = dict(source_sha256=hashlib.sha256(raw).hexdigest(), target_frame_index=target,
        selection='first actual TM frame with a nonzero ordinary FHP; deterministic integration fixture',
        fault_model='whole-frame erasure or single data-bit flip; no physical link/radiation claim', cases={})
    for name, data in cases.items():
        (args.output / f'{name}.bin').write_bytes(data)
        manifest['cases'][name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))

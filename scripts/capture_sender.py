"""Run the real Ref executable on loopback and preserve its raw downlink."""
import argparse
import hashlib
import json
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def capture(binary, output, duration, file_bytes=0):
    output.mkdir(parents=True, exist_ok=True)
    stimulus = None
    if file_bytes:
        sys.path.insert(0, str(ROOT / 'vendor/fprime-gds/src'))
        from fprime_gds.common.models.dictionaries import Dictionaries
        from fprime_gds.common.data_types.cmd_data import CmdData
        from fprime_gds.common.encoders.cmd_encoder import CmdEncoder
        from fprime_gds.common.communication.ccsds.chain import SpacePacketSpaceDataLinkFramerDeframer
        dictionary = ROOT / 'vendor/fprime/TestDeploymentsProject/build-fprime-automatic-native/Ref/Top/Ref_RefSystemDictionary.json'
        dictionaries = Dictionaries.load_dictionaries_into_config(str(dictionary))
        content = bytes((i * 17 + 3) % 256 for i in range(file_bytes))
        (output / 'payload.dat').write_bytes(content)
        command = CmdData(('payload.dat', 'received.dat'), dictionaries.command_name['FileHandling.fileDownlink.SendFile'])
        encoder = CmdEncoder()
        encoded = encoder.encode_api(command)
        framing = SpacePacketSpaceDataLinkFramerDeframer(scid=None, vcid=1, frame_size=None)
        stimulus = framing.frame(encoded[4 + encoder.len_obj.getSize():])
        (output / 'uplink.bin').write_bytes(stimulus)
    with socket.socket() as server:
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        server.settimeout(25)
        port = server.getsockname()[1]
        with (output / 'sender.log').open('wb') as log:
            proc = subprocess.Popen([str(binary.resolve()), '-a', '127.0.0.1', '-p', str(port)],
                                    cwd=output, stdout=log, stderr=subprocess.STDOUT)
            total = 0
            start = time.monotonic()
            try:
                conn, address = server.accept()
                with conn, (output / 'downlink.bin').open('wb') as stream:
                    if stimulus:
                        conn.sendall(stimulus)
                    conn.settimeout(1)
                    until = time.monotonic() + duration
                    while time.monotonic() < until:
                        try:
                            data = conn.recv(65536)
                        except socket.timeout:
                            if proc.poll() is not None:
                                raise RuntimeError(f'Sender exited early: {proc.returncode}')
                            continue
                        if not data:
                            raise RuntimeError('Sender closed stream before capture completed')
                        stream.write(data)
                        total += len(data)
                    proc.send_signal(signal.SIGINT)
                    # Drain the connection so final queued frames are recorded.
                    conn.settimeout(8)
                    while True:
                        data = conn.recv(65536)
                        if not data:
                            break
                        stream.write(data)
                        total += len(data)
                rc = proc.wait(timeout=12)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
        if rc != 0 or total == 0:
            raise RuntimeError(f'Sender capture failed: rc={rc}, bytes={total}')
    result = dict(bytes=total, sha256=hashlib.sha256((output / 'downlink.bin').read_bytes()).hexdigest(),
                  requested_capture_seconds=duration, wall_seconds=time.monotonic()-start,
                  sender_exit_code=rc, transport='local TCP; no physical MCU or RF')
    if file_bytes:
        result['file_stimulus'] = dict(bytes=file_bytes, sha256=hashlib.sha256(content).hexdigest(),
            command='FileHandling.fileDownlink.SendFile', uplink_bytes=len(stimulus),
            source='deterministic local test data, not mission data')
    (output / 'capture.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, default=ROOT / 'vendor/fprime/TestDeploymentsProject/build-artifacts/Linux/Ref/bin/Ref')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/live_capture')
    parser.add_argument('--seconds', type=int, default=24)
    parser.add_argument('--file-bytes', type=int, default=0)
    args = parser.parse_args()
    capture(args.binary, args.output, args.seconds, args.file_bytes)

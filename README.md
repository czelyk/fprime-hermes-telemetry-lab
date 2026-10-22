# F Prime Hermes Telemetry Lab

An actual F Prime C++ Ref downlink capture, a bounded streaming adapter around native Hermes parsers, and a fair pinned GDS comparison.

## Run

Recorded-capture replay: Windows and Python 3.12. Go 1.27.3 and pinned public source archives are downloaded if absent. Replay uses native Go and Python and does not require Docker or PowerShell. A new sender build/capture additionally needs PowerShell and a working Docker Desktop Linux engine.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-replay.txt
.venv/Scripts/python tests/run.py
# New real sender capture rather than replay:
./Run-Lab.ps1
```

`python tests/run.py --verify-only` checks the packaged file hashes without
rerunning the experiment. New runs go to ignored `runs/` directories (or
`outputs/` in the F Prime lab). Archived evidence is never used as an output target.

## Contents

- `receiver/`: Go stream adapter and four meaningful unit tests.
- `scripts/`: sender capture, dictionary adaptation, GDS decoding and comparison.
- `evidence/recorded/`: 40 actual host TM frames, 73 packets, 766 channel measurements and an exact 8 KB file.
- `data/`: generated sender dictionary for build-free replay.
- `patches/`: minimal local sender configuration changes.

## Scope

Replay and new captures use host software, not MCU timing or RF. GDS already provides the compared functionality; no algorithm superiority or new scientific contribution follows from passing. Hermes/GDS UI and physical link tests remain unperformed.

This is a research implementation/archive, not flight-qualified software or a
claim of conference acceptance. Research and packaging used AI assistance.
The retained reports include negative findings and unresolved questions.

## Provenance and licensing

Original evidence was copied without overwriting its source directory. Portable
path changes are recorded in `provenance/patches/`; copied inputs and code have
SHA-256 provenance. `provenance/manifest.json` protects the curated files.
See `LICENSE.md` and `THIRD_PARTY_NOTICES.md`. GitHub publication is not performed
by any script in this repository.
"# fprime-hermes-telemetry-lab" 

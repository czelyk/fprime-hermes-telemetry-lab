"""Record the actual container dependencies and compiler environment."""
import json
import platform
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'outputs/environment'
out.mkdir(parents=True, exist_ok=True)
commands = dict(python=['python', '--version'], gcc=['gcc', '--version'], cmake=['cmake', '--version'],
                ninja=['ninja', '--version'], packages=['python', '-m', 'pip', 'freeze'])
record = dict(platform=platform.platform(), tools={})
for name, cmd in commands.items():
    result = subprocess.run(cmd, text=True, capture_output=True, check=True)
    record['tools'][name] = result.stdout.strip()
(out / 'container.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
(root / 'requirements.lock.txt').write_text(record['tools']['packages'] + '\n', encoding='utf-8')
print('Saved compiler versions and complete Python dependency lock.')

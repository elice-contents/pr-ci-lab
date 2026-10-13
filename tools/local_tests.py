"""공개 단위 테스트 결과를 수집합니다. 실패 시 종료 코드도 1입니다."""
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'output'
out.mkdir(exist_ok=True)
run = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                     cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=60)
(out / 'tests.log').write_text(run.stdout + run.stderr, encoding='utf-8')
(out / 'tests.json').write_text(json.dumps({'status': 'passed' if run.returncode == 0 else 'failed'}), encoding='utf-8')
print('tests exit:', run.returncode)
raise SystemExit(0 if run.returncode == 0 else 1)

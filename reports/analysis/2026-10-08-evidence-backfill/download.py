"""Cache declared issuer sources without modifying existing replay or forecasts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent

def fetch(row):
    suffix = '.pdf' if '.pdf' in row['url'] else '.html'
    path = HERE / 'raw' / (row['ticker'] + '-' + row['id'] + suffix)
    if path.exists() and path.stat().st_size > 1000:
        return {**row, 'path': str(path.relative_to(HERE)), 'sha256': sha256(path.read_bytes()).hexdigest(), 'status': 'cached'}
    temp = path.with_suffix(path.suffix+'.part')
    result = subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error', '--max-time', '40', row['url'], '-o', str(temp)], capture_output=True, text=True)
    if result.returncode:
        return {**row, 'status': 'failed', 'error': result.stderr.strip()[:240]}
    temp.rename(path)
    return {**row, 'path': str(path.relative_to(HERE)), 'sha256': sha256(path.read_bytes()).hexdigest(), 'status': 'downloaded'}

if __name__ == '__main__':
    sources = json.loads((HERE/'sources.json').read_text())
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(fetch, sources))
    (HERE/'download-manifest.json').write_text(json.dumps({'retrieved_at': datetime.now(UTC).isoformat(), 'sources':rows},indent=2)+'\n')
    for row in rows:
        print(row['ticker'],row['id'],row['status'],row.get('error',''))

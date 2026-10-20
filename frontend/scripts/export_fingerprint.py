"""Compare deterministic exported payloads to the deployed build, not timestamps."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def fingerprint(directory):
    digest = hashlib.sha256()
    for path in sorted(Path(directory).rglob('*.json')):
        if path.name == 'pipeline.json':
            continue
        digest.update(str(path.relative_to(directory)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def differs(local, deployed):
    return local != deployed.get('fingerprint')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--deployed-url', required=True)
    args = parser.parse_args()
    local = fingerprint(args.data_dir)
    try:
        with urlopen(args.deployed_url, timeout=30) as response:
            deployed = json.load(response)
    except (HTTPError, URLError, ValueError):
        # Retry deployment when the deployed marker cannot be verified. A failed
        # deployment never records a false success in canonical data.
        deployed = {}
    changed = differs(local, deployed)
    (args.data_dir / 'pipeline.json').write_text(json.dumps({'fingerprint': local}) + '\n')
    print(f'changed={str(changed).lower()}')

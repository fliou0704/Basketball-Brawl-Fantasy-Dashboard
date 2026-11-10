"""Offline regression tests: no real network or repository mutations."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("push-validated-data.sh")

class PushTests(unittest.TestCase):
    def run_case(self, failure="Internal Server Error", remote="base", succeeds_at=2):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git = root / "git"
            git.write_text("""#!/usr/bin/env python3
import os,sys
from pathlib import Path
p=Path(os.environ['CASE_DIR'])/'count'
a=sys.argv[1:]
if a[0]=='rev-parse':print('head' if a[1]=='HEAD' else 'base')
elif a[0]=='ls-remote':print(os.environ['REMOTE']+' refs/heads/main')
elif a[0]=='push':
 n=int(p.read_text())+1 if p.exists() else 1
 p.write_text(str(n))
 if n<int(os.environ['SUCCEEDS_AT']):
  print(os.environ['FAILURE'],file=sys.stderr);sys.exit(1)
else:sys.exit(2)
""")
            git.chmod(0o755)
            sleep = root / "sleep"
            sleep.write_text("#!/bin/sh\nexit 0\n")
            sleep.chmod(0o755)
            env = dict(os.environ, PATH=tmp+os.pathsep+os.environ['PATH'], CASE_DIR=tmp,
                       FAILURE=failure, REMOTE=remote, SUCCEEDS_AT=str(succeeds_at))
            result = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True, text=True)
            return result, int((root/'count').read_text())

    def test_transient_retry(self):
        r,n=self.run_case();self.assertEqual(r.returncode,0);self.assertEqual(n,2)
    def test_non_transient_not_retried(self):
        for failure in ['Permission denied','non-fast-forward']:
            r,n=self.run_case(failure=failure);self.assertNotEqual(r.returncode,0);self.assertEqual(n,1)
    def test_already_accepted(self):
        r,n=self.run_case(remote='head');self.assertEqual(r.returncode,0);self.assertEqual(n,1)
    def test_concurrent_update_is_not_overwritten(self):
        r,n=self.run_case(remote='advanced');self.assertNotEqual(r.returncode,0);self.assertEqual(n,1)
    def test_retry_budget(self):
        r,n=self.run_case(succeeds_at=99);self.assertNotEqual(r.returncode,0);self.assertEqual(n,3)

if __name__ == '__main__': unittest.main()

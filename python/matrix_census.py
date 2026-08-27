#!/usr/bin/env python
"""
matrix_census.py — count tests per CheckList test type.

The suite's letter categories (A-R) slice by ARTIFACT: schema, columns, export,
CLI. That is a map of the codebase, so an untested area leaves no visible hole.
This slices the same tests by TEST TYPE instead, where a thin column IS the
finding.

Types, after Ribeiro et al., "Beyond Accuracy: Behavioral Testing of NLP Models
with CheckList" (ACL 2020), plus a fourth this codebase needs and the paper has
no counterpart for:

  MFT    minimum functionality — a pinned fact with an expected value.
         The default: any test not prefixed below.
  INV    invariance — perturb the input or the invocation, output must not
         change. Needs no expected value, so cases multiply cheaply.
  DIR    directional — perturb toward a known-bad state, the detector must
         move to fail.
  DRIFT  one fact, many carriers — each carrier asserted against the single
         source of truth. Not in the paper; it is a consistency assertion
         across artifacts rather than across inputs.

Usage:
    python matrix_census.py [testfile ...]
"""

import subprocess
import sys

PREFIXES = [
    ('INV',   '_inv_'),
    ('DIR',   '_dir_'),
    ('DRIFT', '_drift_'),
]

DEFAULT_FILES: list = []   # release copy: always pass your test files explicitly


def collect(files):
    """Return collected test node ids via pytest --collect-only."""
    proc = subprocess.run(
        [sys.executable, '-m', 'pytest', *files, '--collect-only', '-q'],
        capture_output=True, text=True,
    )
    return [line for line in proc.stdout.splitlines() if '::' in line]


def census(node_ids):
    counts = {label: sum(1 for n in node_ids if prefix in n)
              for label, prefix in PREFIXES}
    counts['MFT'] = len(node_ids) - sum(counts.values())
    return counts


def main():
    files = sys.argv[1:] or DEFAULT_FILES
    node_ids = collect(files)
    if not node_ids:
        print('no tests collected — check the file list', file=sys.stderr)
        return 1
    counts = census(node_ids)
    total = len(node_ids)

    print()
    print('  test type   count    share')
    print('  ---------   -----    -----')
    for label in ('MFT', 'INV', 'DIR', 'DRIFT'):
        n = counts[label]
        print('  %-11s %5d   %5.1f%%' % (label, n, 100.0 * n / total))
    print('  %-11s %5d' % ('total', total))
    print()
    thin = [l for l in ('INV', 'DIR', 'DRIFT') if counts[l] == 0]
    if thin:
        print('  empty column(s): %s' % ', '.join(thin))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python
"""
isolation_census.py — find tests that only pass because something ran first.

A test that fails when run ALONE is coupled to execution order. That is not a
cosmetic problem:

  * `pytest --lf` (rerun just the failure) reports a false failure, which is
    exactly the workflow you reach for when something breaks;
  * one real bug in an early test cascades into every test that depended on its
    state, so a single defect reads as N failures;
  * any selector that slices ACROSS the ordering — a test-type column
    (`make test-inv`), a `-k` filter, a future parallel runner — breaks.

This does not fix coupling; it makes it countable, so it cannot quietly grow.
Same philosophy as matrix_census.py. Slow by nature — one interpreter per test
— so it is on-demand, never part of the blocking gate.

Do NOT run this concurrently with another pytest invocation against the same
checkout: they share the session-scoped `tmp/test_crosswalk.db`, and the
contention shows up as phantom coupling. Suspects are re-run once to filter
exactly that, but the scan is still slower and noisier when it has company.

Usage:
    python isolation_census.py [testfile ...] [--max N]

`--max N` turns the census into a ratchet: exit 1 if more than N tests are
coupled. Set N to the current count so the number can fall but not rise.
"""

import argparse
import collections
import subprocess
import sys

DEFAULT_FILES: list = []   # release copy: always pass your test files explicitly


def collect(files):
    proc = subprocess.run(
        [sys.executable, '-m', 'pytest', *files, '--collect-only', '-q'],
        capture_output=True, text=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if '::' in line]


def runs_alone(node_id):
    """True if this test passes as the only test in a fresh interpreter.

    Uses pytest's EXIT CODE, not a substring scan of stdout. Substring matching
    on 'failed'/'error' silently miscounts any test whose own name contains
    those words (`test_api_error_paths` would read as permanently coupled).
    pytest exit codes: 0 all passed, 1 tests failed, 2 interrupted, 3 internal
    error, 4 usage error, 5 no tests collected. Only 0 counts as a pass — a
    node id that no longer resolves (exit 4) is a scan bug worth surfacing, not
    a silent skip.
    """
    proc = subprocess.run(
        [sys.executable, '-m', 'pytest', node_id, '-q', '-p', 'no:cacheprovider'],
        capture_output=True, text=True,
    )
    return proc.returncode == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('files', nargs='*', default=None,
                    help='test files to scan (default: %s)' % ' '.join(DEFAULT_FILES))
    ap.add_argument('--max', type=int, default=None,
                    help='exit 1 if more than N tests are order-coupled')
    args = ap.parse_args()

    files = args.files or DEFAULT_FILES
    nodes = collect(files)
    if not nodes:
        print('no tests collected — check the file list', file=sys.stderr)
        return 1

    print('scanning %d tests in isolation (one interpreter each)...' % len(nodes),
          file=sys.stderr)
    suspect = [n for n in nodes if not runs_alone(n)]

    # Re-verify every suspect. Suites that share on-disk state (this repo's
    # session-scoped tmp/test_crosswalk.db) produce transient failures when a
    # scan runs alongside another pytest invocation against the same checkout.
    # A transient inflates the count and reads as real coupling; a second run
    # filters it. Genuine order-coupling reproduces every time.
    coupled, transient = [], []
    for n in suspect:
        (coupled if not runs_alone(n) else transient).append(n)
    if transient:
        print('  %d transient failure(s) discarded on re-run — do NOT run this '
              'scan concurrently with another pytest invocation against this '
              'checkout; they share tmp/test_crosswalk.db:' % len(transient),
              file=sys.stderr)
        for n in transient:
            print('      %s' % n, file=sys.stderr)

    by_class = collections.OrderedDict()
    for n in coupled:
        parts = n.split('::')
        cls = parts[1] if len(parts) >= 3 else '(module)'
        by_class.setdefault(cls, []).append(parts[-1])

    print()
    print('  %d of %d tests fail when run ALONE (%.0f%%)'
          % (len(coupled), len(nodes), 100.0 * len(coupled) / len(nodes)))
    print()
    if not coupled:
        print('  every test is independently runnable.')
        print()
        return 0
    for cls, names in by_class.items():
        print('  %s (%d)' % (cls, len(names)))
        for name in names:
            print('      %s' % name)
    print()

    if args.max is not None and len(coupled) > args.max:
        print('  FAIL: %d coupled tests exceeds the --max %d ratchet.'
              % (len(coupled), args.max))
        print('  New order-coupling was introduced. Give the test an explicit')
        print('  precondition (a fixture/helper that sets up its own state)')
        print('  instead of inheriting it from whichever test ran before.')
        print()
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

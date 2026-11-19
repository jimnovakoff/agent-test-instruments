#!/usr/bin/env python
"""
mutation_sample.py — a mutation score from a random sample, with a seed.

mutation_census.py runs a curated mutant file: named defects, each committed
only once a test catches it. That is a regression set. "All caught" is true by
construction, so it cannot say how much of the code the suite would notice
breaking. This script answers that question with a number that does not depend
on anyone choosing the mutants:

  1. list EVERY mutant a fixed operator set can make in the given source files
  2. draw N of them with a recorded seed
  3. for each: apply it, run the tests, restore byte-for-byte
  4. report killed / survived, and the score with its sampling interval

Nobody picks which lines get broken, and the same seed draws the same sample,
so the result can be repeated by someone who trusts neither the code's author
nor the tests' author.

Operators (token-level; a candidate is kept only if the file still compiles):

  comparison   ==  <-> !=      <  <-> <=      >  <-> >=
  arithmetic   +   <-> -       *  <-> /
  boolean      and <-> or      True <-> False
  number       0 -> 1          any other integer n -> n + 1

Not mutated: strings (so SQL or XML held in Python strings is outside the
sample), comments, type annotations' arrows, and any line carrying
`# pragma: no mutate`. Non-Python files are not mutated at all. Say so when
you report the score.

Verdicts, per mutant:

  KILLED     the tests failed under the mutation
  TIMEOUT    the run exceeded the time limit (counted as killed; shown apart)
  SURVIVED   every test passed with the code broken. Either no test runs that
             line, or tests run it and miss the change, or the mutant is
             equivalent (changes nothing observable). Read each one.

If coverage.py is installed, each SURVIVED mutant is tagged `covered` or
`not covered` from a baseline run. Coverage is measured in-process only, so
code reached through a subprocess reads as not covered; treat the tag as a
hint, not a verdict.

Safety, inherited from mutation_census.py: mutants are applied to raw bytes and
the original bytes are written back and hash-checked; every test run gets an
empty bytecode cache (a same-length mutant written within the same second as
the last compile otherwise runs stale bytecode); the baseline must be green;
and a source file with uncommitted changes is refused unless --allow-dirty.

Do NOT run this alongside another test run against the same checkout.

SLOW by nature: one test run per sampled mutant. On demand only.

Usage:
    python mutation_sample.py --source FILE [FILE ...] --tests ARG [ARG ...]
                              [--n 100] [--seed 1] [--clear PATH ...]
                              [--json OUT] [--list] [--allow-dirty]

`--tests` takes whatever you would pass to pytest (files, node ids, -k ...).
Paths are relative to the current directory, which should be the repo root.
"""

import argparse
import hashlib
import io
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import time
import tokenize
from pathlib import Path

OP_SWAPS = {
    '==': '!=', '!=': '==',
    '<': '<=', '<=': '<',
    '>': '>=', '>=': '>',
    '+': '-', '-': '+',
    '*': '/', '/': '*',
}
NAME_SWAPS = {'and': 'or', 'or': 'and', 'True': 'False', 'False': 'True'}
PRAGMA = 'pragma: no mutate'


class Candidate:
    """One possible mutant: replace text at (line, col) of a file."""

    def __init__(self, path, line, col, old, new):
        self.path, self.line, self.col, self.old, self.new = path, line, col, old, new

    def key(self):
        return (str(self.path), self.line, self.col, self.old, self.new)

    def label(self):
        return '%s:%d  %s -> %s' % (self.path.as_posix(), self.line, self.old, self.new)

    def apply(self, text):
        """The mutated source text. Lines keep their own endings."""
        lines = text.split('\n')        # not splitlines(): keep \r, match tokenize
        row = lines[self.line - 1]
        assert row[self.col:self.col + len(self.old)] == self.old, self.label()
        lines[self.line - 1] = row[:self.col] + self.new + row[self.col + len(self.old):]
        return '\n'.join(lines)


def _number_mutation(tok):
    """n -> n + 1 for plain decimal integers; None for anything else."""
    s = tok.replace('_', '')
    if not s.isdigit() or (len(s) > 1 and s.startswith('0')):
        return None
    return str(int(s) + 1)


def candidates(path):
    """Every mutant the operator set can make in one file, compile-checked."""
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    src_lines = text.split('\n')
    out = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError) as exc:
        raise SystemExit('cannot tokenize %s: %s' % (path, exc))
    for tok in tokens:
        line, col = tok.start
        if tok.start[0] != tok.end[0]:
            continue
        if PRAGMA in src_lines[line - 1]:
            continue
        new = None
        if tok.type == tokenize.OP:
            new = OP_SWAPS.get(tok.string)
        elif tok.type == tokenize.NAME:
            new = NAME_SWAPS.get(tok.string)
        elif tok.type == tokenize.NUMBER:
            new = _number_mutation(tok.string)
        if new is None:
            continue
        cand = Candidate(path, line, col, tok.string, new)
        try:
            compile(cand.apply(text), str(path), 'exec')
        except (SyntaxError, ValueError):
            continue            # e.g. '*' in *args -> '/': not a real mutant
        out.append(cand)
    return out


def _run(cmd, cache_dir, timeout=None):
    """(exit code or None on timeout, seconds). Fresh bytecode cache per run."""
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONPYCACHEPREFIX'] = cache_dir
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                              timeout=timeout)
        return proc.returncode, time.monotonic() - start
    except subprocess.TimeoutExpired:
        return None, time.monotonic() - start


def run_tests(test_args, timeout=None, stop_early=True):
    cmd = [sys.executable, '-m', 'pytest', *test_args, '-q', '-p', 'no:cacheprovider']
    if stop_early:
        cmd.append('-x')
    with tempfile.TemporaryDirectory(prefix='mutation-pycache-') as cache:
        return _run(cmd, cache, timeout)


def baseline_coverage(test_args, sources):
    """{path: set(executed lines)} from one in-process coverage run, or None."""
    try:
        import coverage  # noqa: F401
    except ImportError:
        return None
    with tempfile.TemporaryDirectory(prefix='mutation-cov-') as tmp:
        data, report = os.path.join(tmp, 'cov'), os.path.join(tmp, 'cov.json')
        cmd = [sys.executable, '-m', 'coverage', 'run', '--data-file', data,
               '-m', 'pytest', *test_args, '-q', '-p', 'no:cacheprovider']
        code, _ = _run(cmd, os.path.join(tmp, 'pyc'))
        if code != 0:
            return None
        subprocess.run([sys.executable, '-m', 'coverage', 'json', '--data-file',
                        data, '-o', report], capture_output=True, text=True)
        try:
            with open(report, encoding='utf-8') as f:
                files = json.load(f)['files']
        except (OSError, ValueError, KeyError):
            return None
    by_path = {Path(k).resolve(): set(v.get('executed_lines', []))
               for k, v in files.items()}
    return {s: by_path.get(s.resolve(), set()) for s in sources}


def _clear(paths):
    for rel in paths:
        p = Path(rel)
        if p.exists():
            p.unlink()


def _dirty(paths):
    """Source files with uncommitted changes, per git. [] outside a repo."""
    try:
        proc = subprocess.run(['git', 'status', '--porcelain', '--', *map(str, paths)],
                              capture_output=True, text=True)
    except OSError:
        return []
    if proc.returncode != 0:
        return []
    return [ln[3:] for ln in proc.stdout.splitlines() if ln.strip()]


def wilson(k, n, z=1.96):
    """95% Wilson interval for k successes of n."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, mid - half), min(1.0, mid + half)


def judge(cand, test_args, clear, timeout):
    """Apply one mutant, run the tests, restore. Returns the verdict."""
    original = cand.path.read_bytes()
    mutated = cand.apply(original.decode('utf-8')).encode('utf-8')
    wanted = hashlib.sha256(original).hexdigest()
    cand.path.write_bytes(mutated)
    try:
        _clear(clear)
        code, _ = run_tests(test_args, timeout=timeout)
        if code is None:
            return 'TIMEOUT'
        return 'SURVIVED' if code == 0 else 'KILLED'
    finally:
        cand.path.write_bytes(original)
        _clear(clear)
        if hashlib.sha256(cand.path.read_bytes()).hexdigest() != wanted:
            print('FATAL: restore of %s failed its hash check. Run '
                  '`git checkout -- %s` before anything else.'
                  % (cand.path, cand.path), file=sys.stderr)
            raise SystemExit(3)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', nargs='+', required=True, metavar='FILE',
                    help='Python source files to mutate (not the tests)')
    ap.add_argument('--tests', nargs='+', metavar='ARG', default=[],
                    help='arguments for pytest: the tests that should notice')
    ap.add_argument('--n', type=int, default=100, help='sample size (default 100)')
    ap.add_argument('--seed', type=int, default=1, help='sampling seed (default 1)')
    ap.add_argument('--clear', nargs='*', default=[], metavar='PATH',
                    help='files deleted before every run (e.g. a cached test DB)')
    ap.add_argument('--json', metavar='OUT', help='also write the full record here')
    ap.add_argument('--list', action='store_true',
                    help='count the possible mutants per file and exit')
    ap.add_argument('--allow-dirty', action='store_true',
                    help='mutate source files that have uncommitted changes')
    args = ap.parse_args()

    sources = [Path(s) for s in args.source]
    missing = [str(s) for s in sources if not s.is_file()]
    if missing:
        print('not a file: %s' % ', '.join(missing), file=sys.stderr)
        return 2

    population = []
    for s in sources:
        found = candidates(s)
        population.extend(found)
        if args.list:
            print('  %6d  %s' % (len(found), s.as_posix()))
    population.sort(key=Candidate.key)
    if args.list:
        print('  %6d  possible mutants in %d file(s)' % (len(population), len(sources)))
        return 0
    if not args.tests:
        print('--tests is required unless --list is given', file=sys.stderr)
        return 2
    if not population:
        print('no possible mutants in the given files', file=sys.stderr)
        return 2

    if not args.allow_dirty:
        dirty = _dirty(sources)
        if dirty:
            print('uncommitted changes in: %s\ncommit or stash them first, or '
                  'pass --allow-dirty' % ', '.join(dirty), file=sys.stderr)
            return 2

    _clear(args.clear)
    code, seconds = run_tests(args.tests, stop_early=False)
    if code != 0:
        print('baseline is not green (pytest exit %s); refusing to mutate' % code,
              file=sys.stderr)
        return 2
    timeout = max(60.0, seconds * 5)
    _clear(args.clear)
    covered = baseline_coverage(args.tests, sources)
    _clear(args.clear)

    n = min(args.n, len(population))
    sample = random.Random(args.seed).sample(population, n)
    print('population %d, sample %d, seed %d, baseline %.1fs'
          % (len(population), n, args.seed, seconds), file=sys.stderr)

    results = []
    for i, cand in enumerate(sample, 1):
        verdict = judge(cand, args.tests, args.clear, timeout)
        tag = ''
        if verdict == 'SURVIVED' and covered is not None:
            tag = 'covered' if cand.line in covered[cand.path] else 'not covered'
        results.append((cand, verdict, tag))
        print('  [%d/%d] %-8s %s' % (i, n, verdict, cand.label()), file=sys.stderr)

    killed = sum(1 for _, v, _ in results if v in ('KILLED', 'TIMEOUT'))
    timeouts = sum(1 for _, v, _ in results if v == 'TIMEOUT')
    survivors = [(c, t) for c, v, t in results if v == 'SURVIVED']
    lo, hi = wilson(killed, n)

    print()
    print('  possible mutants   %d' % len(population))
    print('  sampled            %d  (seed %d)' % (n, args.seed))
    print('  killed             %d%s' % (killed, ('  (%d by timeout)' % timeouts)
                                         if timeouts else ''))
    print('  survived           %d' % len(survivors))
    if covered is not None:
        nc = sum(1 for _, t in survivors if t == 'not covered')
        print('    on a line no test ran (in-process)   %d' % nc)
        print('    on a line tests ran                  %d' % (len(survivors) - nc))
    print('  score              %.0f%%  (95%% interval %.0f%% to %.0f%%)'
          % (100.0 * killed / n, 100 * lo, 100 * hi))
    print()
    if survivors:
        print('  survivors — each is a missing test or an equivalent mutant:')
        for cand, tag in survivors:
            print('    %s%s' % (cand.label(), ('   [%s]' % tag) if tag else ''))
        print()

    if args.json:
        record = {
            'seed': args.seed, 'population': len(population), 'sample': n,
            'killed': killed, 'timeouts': timeouts, 'survived': len(survivors),
            'score': killed / n, 'interval95': [lo, hi],
            'sources': [s.as_posix() for s in sources], 'tests': args.tests,
            'coverage_measured': covered is not None,
            'mutants': [{'file': c.path.as_posix(), 'line': c.line, 'col': c.col,
                         'old': c.old, 'new': c.new, 'verdict': v, 'coverage': t}
                        for c, v, t in results],
        }
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(record, f, indent=2)
            f.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

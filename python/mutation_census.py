#!/usr/bin/env python
"""
mutation_census.py — break the behaviour, prove a test notices, restore.

A green suite reports which tests exist and whether they pass — never whether
they would fail if the system broke. On deterministic code (SQL, XML, exports)
a dead test is permanently, silently green. The only instrument that answers
"would this test catch the bug it claims to guard against" is mutation: apply
a known defect, run the guarding tests, require a failure, put everything back.

This is the committed successor to the scratchpad harness that surfaced most of
the 2026-08-26 findings (15 defects against a mature 480-test suite, 6 of them
in the tests). Two traps that harness hit are now structural:

  * A mutation aimed at code the tests never execute is indistinguishable from
    a weak test. Before reporting NOT CAUGHT, this harness re-runs the WHOLE
    test file and requires that *something* fails — otherwise the verdict is
    INEFFECTIVE (a spec problem, not a test problem). That trap produced four
    false findings in one session.
  * Restoring a file via Python text I/O rewrites line endings on Windows and
    leaves spurious `git status` entries. Restore here is byte-for-byte.

Verdicts, per mutant:

  CAUGHT       the guarding tests failed under mutation — they earn their keep
  NOT CAUGHT   the guarding tests passed while the whole file demonstrably
               noticed the mutation — THE FINDING; the named tests are blind
               to the defect they exist to catch
  INEFFECTIVE  nothing in the whole file noticed. Either the mutant is
               equivalent (fix the spec), or NO test anywhere in the file
               exercises the mutated path with assertions — a coverage hole.
               The first committed run hit the second case: the importer's
               UPDATE branch (the path real re-imports take) had no value
               assertions at all. Investigate before dismissing.
  SPEC ERROR   the find pattern matched != 1 times, the file is missing, or
               the guarding tests were already red BEFORE mutation — refused
               rather than guessed

Spec format (default: mutants.json beside this script) — a JSON list of:

  {
    "name":    "unique-slug",
    "why":     "what defect this simulates and which finding it re-creates",
    "file":    "seed_controls.py",
    "find":    "exact source text — must match exactly once",
    "replace": "the defect",
    "tests":   ["test_crosswalk.py::TestSprsAnnexACanon"],
    "clear":   ["tmp/test_crosswalk.db"]          // optional, see below
  }

`clear` names files deleted before each run (baseline, mutated, whole-file) and
again after restore. It exists for the session-cached test DB: mutants to
crosswalk_schema.sql are invisible to any test reading tmp/test_crosswalk.db
unless the cache is rebuilt — and a cache rebuilt from a MUTATED schema must
not be left behind to poison later runs.

Byte discipline: find/replace are applied to the file's raw bytes (spec strings
are encoded UTF-8). A multi-line `find` written with \n is retried with \r\n if
it doesn't match as-is, so CRLF working trees don't produce false SPEC ERRORs.
Restore writes the original bytes back verbatim and verifies the hash.

Do NOT run this concurrently with another pytest invocation against the same
checkout: they share the session-scoped tmp/test_crosswalk.db and the
contention reads as phantom failures. Same rule as isolation_census.py.

SLOW by nature — several pytest invocations per mutant, a whole-file run per
NOT CAUGHT candidate. On-demand only, never part of the blocking gate.

Usage:
    python mutation_census.py [spec.json] [--only NAME] [--list]
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
DEFAULT_SPEC = REPO / 'mutants.json'


def _env():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def _run_pytest(args):
    """Exit code of a pytest run. 0 = all passed (see isolation_census.py on
    why the exit code, never a substring scan of stdout)."""
    proc = subprocess.run(
        [sys.executable, '-m', 'pytest', *args, '-q', '-p', 'no:cacheprovider'],
        capture_output=True, text=True, cwd=str(REPO), env=_env(),
    )
    return proc.returncode


def _clear(paths):
    for rel in paths:
        p = REPO / rel
        if p.exists():
            p.unlink()


def _files_of(tests):
    """The test files a selection lives in, for the whole-file run."""
    return sorted({t.split('::', 1)[0] for t in tests})


class Mutant:
    REQUIRED = ('name', 'file', 'find', 'replace', 'tests')

    def __init__(self, spec):
        missing = [k for k in self.REQUIRED if not spec.get(k)]
        if missing:
            raise ValueError('mutant %r missing key(s): %s'
                             % (spec.get('name', '?'), ', '.join(missing)))
        self.name = spec['name']
        self.why = spec.get('why', '')
        self.path = REPO / spec['file']
        self.find = spec['find']
        self.replace = spec['replace']
        self.tests = list(spec['tests'])
        self.clear = list(spec.get('clear', []))

    def _match(self, blob):
        """(find_bytes, replace_bytes, count) — retry CRLF for multi-line finds."""
        find, repl = self.find.encode('utf-8'), self.replace.encode('utf-8')
        n = blob.count(find)
        if n == 0 and b'\n' in find and b'\r\n' not in find:
            crlf_find = find.replace(b'\n', b'\r\n')
            n = blob.count(crlf_find)
            if n:
                return crlf_find, repl.replace(b'\n', b'\r\n'), n
        return find, repl, n

    def run(self):
        """Return (verdict, detail)."""
        if not self.path.exists():
            return 'SPEC ERROR', 'file not found: %s' % self.path.name
        original = self.path.read_bytes()
        find, repl, n = self._match(original)
        if n != 1:
            return 'SPEC ERROR', ('find pattern matches %d times in %s — must be '
                                  'exactly 1; refusing to guess' % (n, self.path.name))

        # Baseline: the guarding tests must be green BEFORE the mutation, or a
        # pre-existing failure masquerades as CAUGHT.
        _clear(self.clear)
        if _run_pytest(self.tests) != 0:
            return 'SPEC ERROR', 'guarding tests already fail unmutated (baseline red)'

        self.path.write_bytes(original.replace(find, repl, 1))
        try:
            _clear(self.clear)
            caught = _run_pytest(self.tests) != 0
            if caught:
                return 'CAUGHT', ''
            # The named tests passed. Before calling that a finding, prove the
            # mutation was effective at all: run the whole file(s) and require
            # that something fails. (The four-false-findings trap.)
            whole = _files_of(self.tests)
            _clear(self.clear)
            if _run_pytest(whole) != 0:
                return 'NOT CAUGHT', ('%s noticed the mutation but %s did not'
                                      % (' '.join(whole), ' '.join(self.tests)))
            return 'INEFFECTIVE', ('nothing in %s failed under this mutation — '
                                   'an equivalent mutant, or a code path no '
                                   'test asserts on (a coverage hole)'
                                   % ' '.join(whole))
        finally:
            self.path.write_bytes(original)
            restored = hashlib.sha256(self.path.read_bytes()).hexdigest()
            wanted = hashlib.sha256(original).hexdigest()
            _clear(self.clear)
            if restored != wanted:            # pragma: no cover — belt and braces
                print('  FATAL: restore of %s failed hash check — inspect '
                      'git status before doing anything else' % self.path.name,
                      file=sys.stderr)


def load_spec(path):
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise ValueError('spec must be a JSON list of mutant objects')
    mutants = [Mutant(m) for m in raw]
    names = [m.name for m in mutants]
    dupes = {x for x in names if names.count(x) > 1}
    if dupes:
        raise ValueError('duplicate mutant name(s): %s' % ', '.join(sorted(dupes)))
    return mutants


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('spec', nargs='?', default=str(DEFAULT_SPEC),
                    help='JSON mutant spec (default: mutants.json)')
    ap.add_argument('--only', metavar='NAME', action='append',
                    help='run only the named mutant(s); repeatable')
    ap.add_argument('--list', action='store_true',
                    help='list mutants in the spec and exit')
    args = ap.parse_args()

    mutants = load_spec(args.spec)
    if args.only:
        unknown = set(args.only) - {m.name for m in mutants}
        if unknown:
            print('unknown mutant(s): %s' % ', '.join(sorted(unknown)),
                  file=sys.stderr)
            return 2
        mutants = [m for m in mutants if m.name in set(args.only)]

    if args.list:
        for m in mutants:
            print('  %-38s %s -> %s' % (m.name, m.path.name, ' '.join(m.tests)))
        return 0

    results = []
    for m in mutants:
        print('mutating %s (%s)...' % (m.name, m.path.name), file=sys.stderr)
        verdict, detail = m.run()
        results.append((m, verdict, detail))
        print('  %s%s' % (verdict, (' — ' + detail) if detail else ''),
              file=sys.stderr)

    print()
    print('  %-38s %-12s %s' % ('mutant', 'verdict', 'file'))
    print('  %-38s %-12s %s' % ('-' * 6, '-' * 7, '-' * 4))
    for m, verdict, _ in results:
        print('  %-38s %-12s %s' % (m.name, verdict, m.path.name))
    print()

    bad = [(m, v, d) for m, v, d in results if v != 'CAUGHT']
    for m, v, d in bad:
        print('  %s: %s%s' % (v, m.name, (' — ' + d) if d else ''))
        if m.why:
            print('      why this mutant exists: %s' % m.why)
    if bad:
        print()
        print('  %d of %d mutants CAUGHT. NOT CAUGHT = a guarding test that '
              'would stay green through the defect it exists to catch; '
              'INEFFECTIVE / SPEC ERROR = fix mutants.json.'
              % (len(results) - len(bad), len(results)))
        print()
        return 1
    print('  all %d mutants caught by their guarding tests.' % len(results))
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())

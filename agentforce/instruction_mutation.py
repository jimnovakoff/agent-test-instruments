#!/usr/bin/env python3
"""instruction_mutation.py - mutation harness for hosted Agentforce agents.

Perturb an agent's instruction metadata, republish, run the guarding test
cases, and require them to fail. The hosted analog of mutation_census.py,
with the disciplines the first hand-driven runs paid for built in:

  * Mutations are applied by INDEX-BASED EXCISION anchored on a unique
    string (a developerName), or by exact find/replace with a match-count
    of 1. Ambiguity is refused, never guessed around.
  * Restore is BYTE-EXACT from an in-memory copy of the original file -
    never from VCS checkout, which can rewrite line endings and break the
    next mutation's match.
  * The deploy vehicle is: deactivate agent -> deploy topic plugins AND the
    planner bundle together -> activate. Deploying plugins alone succeeds
    and changes nothing at runtime (the platform treats the active version
    as an immutable snapshot); the planner bundle is the compiled carrier
    and only deploys against an inactive agent.
  * EVERY mutant run also carries a CANARY edit - a standing fact the suite
    pins, in a case disjoint from the guarding cases. If the canary case
    does not fail, the mutation never reached the runtime and the verdict
    is INEFFECTIVE, not SURVIVED. On an opaque hosted deploy pipeline this
    is the precondition for any verdict at all.
  * Verdicts on a probabilistic subject are distributions: the decisive run
    is stability-doubled (--doubles). Disagreement between runs is its own
    verdict (INTERMITTENT), not noise to average away.

Verdicts:
  CAUGHT       guarding case(s) failed in every run; canary failed in every run
  SURVIVED     no guarding case failed in any run; canary failed in every run
  INTERMITTENT guarding-case failure differed between runs (canary ok)
  INEFFECTIVE  canary case passed in some run - the vehicle, not the tests,
               is indicted; nothing is learned about the guarding cases
  ERROR        deploy/run failure or an ERROR-status assertion

Each mutant may declare "expected" (string or list; default "CAUGHT").
Exit code is 0 iff every executed mutant's verdict matches its expectation,
so a documented blindness (expected SURVIVED) stays green until the day it
starts being caught - at which point the change is surfaced, not silent.

Usage:
  python instruction_mutation.py path/to/af-mutants.json --org <alias>
      [--doubles 1] [--only NAME] [--list] [--dry-run]
      [--skip-baseline] [--no-final-verify]

Never run concurrently with another test run against the same agent.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

SF = shutil.which("sf") or "sf"


def run_sf(args, cwd, timeout=900):
    """Run an sf command with --json and return the parsed payload."""
    proc = subprocess.run(
        [SF] + args + ["--json"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    out = proc.stdout or ""
    start = out.find("{")
    if start < 0:
        raise RuntimeError(f"sf {' '.join(args)}: no JSON in output: {out[:200]!r}")
    return json.loads(out[start:])


class Subject:
    """The deployed agent + suite the mutants run against."""

    def __init__(self, cfg, project_dir, org):
        self.project_dir = pathlib.Path(project_dir)
        self.org = org
        self.agent = cfg["agent_api_name"]
        self.test = cfg["test_api_name"]
        self.source_dirs = cfg["source_dirs"]

    def deploy_cycle(self):
        # Deactivate may fail if already inactive; the deploy result is the check.
        run_sf(["agent", "deactivate", "--api-name", self.agent, "-o", self.org],
               self.project_dir)
        args = ["project", "deploy", "start", "-o", self.org]
        for d in self.source_dirs:
            args += ["--source-dir", d]
        dep = run_sf(args, self.project_dir)
        status = (dep.get("result") or {}).get("status")
        if status != "Succeeded":
            raise RuntimeError(f"deploy failed: {status}")
        act = run_sf(["agent", "activate", "--api-name", self.agent, "-o", self.org],
                     self.project_dir)
        if act.get("status") != 0:
            raise RuntimeError(f"activate failed: {act.get('message')}")

    def run_suite(self):
        """Run the suite once. Returns (failed_case_numbers, errored_case_numbers)."""
        res = run_sf(["agent", "test", "run", "--api-name", self.test,
                      "-o", self.org, "--wait", "15"], self.project_dir)
        result = res.get("result") or {}
        if result.get("status") != "COMPLETED":
            raise RuntimeError(f"test run did not complete: {result.get('status')}")
        failed, errored = set(), set()
        for tc in result.get("testCases") or []:
            num = tc.get("testNumber")
            statuses = {x.get("result") for x in (tc.get("testResults") or [])}
            if "ERROR" in statuses or None in statuses and "ERROR" in {
                    x.get("status") for x in (tc.get("testResults") or [])}:
                errored.add(num)
            if "FAILURE" in statuses:
                failed.add(num)
        return failed, errored


class Edit:
    """One reversible file edit. Applied strictly; restored byte-for-byte."""

    def __init__(self, path: pathlib.Path, spec: dict):
        self.path = path
        self.spec = spec
        self.original: bytes | None = None

    def apply(self):
        src_bytes = self.path.read_bytes()
        self.original = src_bytes
        src = src_bytes.decode("utf-8")
        if "excise_anchor" in self.spec:
            anchor = self.spec["excise_anchor"]
            n = src.count(anchor)
            if n == 0:
                raise RuntimeError(f"anchor {anchor!r}: not found - refusing")
            i = src.index(anchor)
            open_tag = self.spec.get("element", "<genAiPluginInstructions>")
            close_tag = open_tag.replace("<", "</", 1)
            start = src.rindex(open_tag, 0, i)
            start = src.rindex("\n", 0, start) + 1
            end = src.index(close_tag, i) + len(close_tag)
            while end < len(src) and src[end] in "\r\n":
                end += 1
                if src[end - 1] == "\n":
                    break
            removed = src[start:end]
            if removed.count(open_tag) != 1:
                raise RuntimeError("excision spans more than one element - refusing")
            if removed.count(anchor) != n:
                # An anchor may legitimately occur several times INSIDE the one
                # element (developerName + masterLabel); occurrences outside it
                # mean the anchor is ambiguous about which element to excise.
                raise RuntimeError(
                    f"anchor {anchor!r} occurs outside the excised element"
                    f" ({n} total, {removed.count(anchor)} inside) - refusing")
            out = src[:start] + src[end:]
        else:
            find, replace = self.spec["find"], self.spec["replace"]
            n = src.count(find)
            if n != 1:
                raise RuntimeError(f"find {find!r}: {n} matches != 1 - refusing")
            out = src.replace(find, replace)
        self.path.write_bytes(out.encode("utf-8"))

    def restore(self):
        if self.original is not None:
            self.path.write_bytes(self.original)
            self.original = None


def verify_green(subject, label):
    """Run the suite expecting green. A failing verification run is itself a
    probabilistic verdict, so it is stability-doubled before being believed:
    green on the double = flake, reported but not fatal; red twice = red."""
    failed, errored = subject.run_suite()
    if not failed and not errored:
        return True, f"{label}: green"
    first = (sorted(failed), sorted(errored))
    failed2, errored2 = subject.run_suite()
    if not failed2 and not errored2:
        return True, (f"{label}: green on double (first run flaked:"
                      f" failed={first[0]} errored={first[1]})")
    return False, (f"{label}: NOT GREEN twice - run1 failed={first[0]}"
                   f" errored={first[1]}; run2 failed={sorted(failed2)}"
                   f" errored={sorted(errored2)}")


def verdict_for(runs, guarding, canary_case):
    """runs: list of (failed_set, errored_set)."""
    if any(err for _, err in runs):
        return "ERROR"
    if any(canary_case not in failed for failed, _ in runs):
        return "INEFFECTIVE"
    hits = [bool(set(guarding) & failed) for failed, _ in runs]
    if all(hits):
        return "CAUGHT"
    if not any(hits):
        return "SURVIVED"
    return "INTERMITTENT"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mutants", help="path to the mutant-set JSON")
    ap.add_argument("--org", required=True, help="target org alias")
    ap.add_argument("--doubles", type=int, default=1,
                    help="extra stability runs per mutant (default 1)")
    ap.add_argument("--only", help="run a single mutant by name")
    ap.add_argument("--list", action="store_true", help="list mutants and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="show the plan and run estimate; touch nothing")
    ap.add_argument("--skip-baseline", action="store_true")
    ap.add_argument("--no-final-verify", action="store_true")
    args = ap.parse_args()

    spec_path = pathlib.Path(args.mutants)
    cfg = json.loads(spec_path.read_text(encoding="utf-8"))
    project_dir = (spec_path.parent / cfg["project_dir"]).resolve()
    subject = Subject(cfg, project_dir, args.org)
    canary = cfg["canary"]
    mutants = cfg["mutants"]
    if args.only:
        mutants = [m for m in mutants if m["name"] == args.only]
        if not mutants:
            sys.exit(f"no mutant named {args.only!r}")

    if args.list:
        for m in cfg["mutants"]:
            exp = m.get("expected", "CAUGHT")
            print(f"{m['name']:<8} guards={m['guarding_cases']} expected={exp}"
                  f"  {m.get('note', '')}")
        return

    runs_per_mutant = 1 + args.doubles
    total = (0 if args.skip_baseline else 1) + len(mutants) * runs_per_mutant \
        + (0 if args.no_final_verify else 1)
    print(f"plan: {len(mutants)} mutant(s) x {runs_per_mutant} run(s)"
          f" + {total - len(mutants) * runs_per_mutant} verification run(s)"
          f" = {total} suite runs against '{args.org}'")
    if args.dry_run:
        return

    if not args.skip_baseline:
        print("baseline: running suite (must be fully green) ...")
        green, detail = verify_green(subject, "baseline")
        print(detail)
        if not green:
            sys.exit("aborting; a mutation verdict over a red baseline"
                     " means nothing")

    results = {}
    canary_edit_spec = {"find": canary["find"], "replace": canary["replace"]}
    ok = True
    try:
        for m in mutants:
            name = m["name"]
            guarding = m["guarding_cases"]
            expected = m.get("expected", "CAUGHT")
            expected = [expected] if isinstance(expected, str) else expected
            edits = [Edit(project_dir / m["file"], m),
                     Edit(project_dir / canary["file"], canary_edit_spec)]
            print(f"\n{name}: applying mutant + canary ...")
            applied = []
            try:
                for e in edits:
                    e.apply()
                    applied.append(e)
                subject.deploy_cycle()
                runs = []
                for i in range(runs_per_mutant):
                    failed, errored = subject.run_suite()
                    runs.append((failed, errored))
                    noise = sorted(failed - set(guarding) - {canary["case"]})
                    print(f"  run {i + 1}: failing={sorted(failed)}"
                          + (f"  (non-guarding noise: {noise})" if noise else ""))
                v = verdict_for(runs, guarding, canary["case"])
            finally:
                # Reverse order: when two edits touch the same file, the later
                # edit's captured "original" is the earlier edit's mutated
                # output; forward-order restore would re-apply the first
                # mutation. (Learned the hard way on this harness's first run.)
                for e in reversed(applied):
                    e.restore()
            match = v in expected
            ok = ok and match
            results[name] = (v, expected, match)
            print(f"  verdict: {v}  expected: {'/'.join(expected)}"
                  f"  -> {'ok' if match else 'MISMATCH'}")
    finally:
        print("\nrestoring deployed baseline ...")
        subject.deploy_cycle()

    if not args.no_final_verify:
        green, detail = verify_green(subject, "final verify")
        print(detail)
        if not green:
            print("the org may not match the repo; investigate before"
                  " trusting anything above")
            ok = False

    print("\nsummary:")
    for name, (v, expected, match) in results.items():
        print(f"  {name:<8} {v:<13} expected {'/'.join(expected):<13}"
              f" {'ok' if match else 'MISMATCH'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

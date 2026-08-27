#!/usr/bin/env python3
"""
drift_check.py — is the agent you deployed the agent you tested?

Sandbox-green certifies the version you TESTED. Nothing certifies that
production still IS that version — instructions get hot-edited in Setup,
metadata gets deployed from another branch, and the eval suite keeps passing
against a definition that no longer describes the live agent. This is the
Mystery Guest failure with a deployment pipeline attached: the checker's
subject moves out from under it and everything stays green.

Mechanics (thin by design — the Salesforce CLI does the real work):
  1. `sf project retrieve start -m AiEvaluationDefinition:<name>` pulls the
     DEPLOYED test definition from the org into a temp directory.
  2. `sf agent generate test-spec --from-definition <xml>` converts it to
     the same YAML shape as your local spec — using the CLI's own
     converter, so the diff compares like with like.
  3. The two YAML documents are compared structurally (parsed, normalized,
     compared — not byte-diffed, so cosmetic reordering doesn't false-alarm).

Exit 0 = deployed test definition matches the local spec. Exit 1 = drift,
with a field-level report. Exit 2 = couldn't retrieve/convert (auth, name,
or CLI version — `sf agent` requires a current Salesforce CLI).

Usage:
    python drift_check.py <local-spec.yaml> --definition <ApiName> --org <alias>

Requires: Salesforce CLI with the `agent` commands, an authenticated org.
Zero model calls — this is still the free half of the methodology.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:
    print('PyYAML required:  pip install pyyaml', file=sys.stderr)
    sys.exit(2)


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    return proc.returncode, proc.stdout + proc.stderr


def normalize(doc):
    """Parsed spec -> comparable structure: test cases keyed by utterance,
    expectation fields normalized to strings."""
    out = {}
    for tc in (doc or {}).get('testCases', []) or []:
        key = str(tc.get('utterance', '')).strip()
        out[key] = {k: str(tc.get(k, '')) for k in
                    ('expectedTopic', 'expectedActions', 'expectedOutcome',
                     'customEvaluations', 'contextVariables',
                     'conversationHistory')}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('spec', help='local test-spec YAML (the version you test)')
    ap.add_argument('--definition', required=True,
                    help='AiEvaluationDefinition API name in the org')
    ap.add_argument('--org', required=True, help='org alias / username')
    args = ap.parse_args()

    local = normalize(yaml.safe_load(Path(args.spec).read_text(encoding='utf-8')))

    with tempfile.TemporaryDirectory() as tmp:
        code, out = run(['sf', 'project', 'retrieve', 'start',
                         '-m', f'AiEvaluationDefinition:{args.definition}',
                         '-o', args.org, '-r', tmp, '--json'])
        if code != 0:
            print('retrieve failed:\n' + out[-800:], file=sys.stderr)
            return 2
        xmls = list(Path(tmp).rglob('*.aiEvaluationDefinition-meta.xml'))
        if not xmls:
            print('retrieved nothing named *.aiEvaluationDefinition-meta.xml — '
                  'wrong definition name, or the org has no such definition',
                  file=sys.stderr)
            return 2
        spec_out = Path(tmp) / 'deployed-spec.yaml'
        code, out = run(['sf', 'agent', 'generate', 'test-spec',
                         '--from-definition', str(xmls[0]),
                         '--output-file', str(spec_out)])
        if code != 0 or not spec_out.exists():
            print('test-spec conversion failed (needs a current Salesforce '
                  'CLI with `sf agent`):\n' + out[-800:], file=sys.stderr)
            return 2
        deployed = normalize(yaml.safe_load(spec_out.read_text(encoding='utf-8')))

    drift = []
    for utt in sorted(set(local) | set(deployed)):
        if utt not in deployed:
            drift.append(f'case only in LOCAL spec: {utt[:70]}')
        elif utt not in local:
            drift.append(f'case only in DEPLOYED definition: {utt[:70]}')
        else:
            for field, want in local[utt].items():
                have = deployed[utt].get(field, '')
                if want != have:
                    drift.append(f'{utt[:50]} [{field}]: local != deployed')

    if drift:
        print(f'DRIFT — the deployed test definition is not the one you '
              f'tested ({len(drift)} difference(s)):')
        for d in drift:
            print('  ' + d)
        return 1
    print(f'OK — deployed AiEvaluationDefinition "{args.definition}" matches '
          f'{args.spec} ({len(local)} case(s)).')
    return 0


if __name__ == '__main__':
    sys.exit(main())

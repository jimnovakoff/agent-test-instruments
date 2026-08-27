#!/usr/bin/env python3
"""
spec_census.py — CheckList-style census of an Agentforce agent test spec.

Reads the YAML test spec Agentforce DX uses (`sf agent generate test-spec`,
`sf agent test create --spec`; the readable equivalent of the
AiEvaluationDefinition metadata) and classifies every case along the axes
that decide whether a green run means anything:

  Test type (after Ribeiro et al., "Beyond Accuracy: Behavioral Testing of
  NLP Models with CheckList", ACL 2020, plus the DRIFT column):
    MFT    utterance -> absolute expectation. The format's native shape.
    INV    perturb the input, output must not change.  STRUCTURALLY
           INEXPRESSIBLE here: a test case cannot assert a relationship
           between two responses. The census counts the latent material —
           groups of cases sharing identical expectations with different
           utterances (paraphrase sets asserted independently).
    DIR    perturb toward a known-bad input, the response must harden.
           Also inexpressible per-case; escalation lives only in
           conversationHistory, which the census counts separately.
    DRIFT  an expectation that embeds a fact owned by some other source of
           truth (a number, a product name, a policy value). Flagged
           heuristically — verify before acting.

  Expectation depth (Agentforce-specific): a case asserting only
  expectedTopic passes whenever ROUTING is right, regardless of what the
  agent actually said. Depth tiers: topic-only < +actions < +outcome <
  +customEvaluations. Shallow cases are counted and named.

  Judge reliance: expectedOutcome is evaluated by a model. Every verdict
  that rests on it inherits the judge's failure modes — a judge that would
  pass a known-bad response is a dead test, so judge-reliant cases are the
  ones to seed with deliberate violations first.

  Multi-turn: cases carrying conversationHistory. (Unlike many hand-rolled
  suites, this format CAN express prior turns — the census shows whether
  the suite uses that power.)

Usage:
    python spec_census.py <test-spec.yaml> [more-specs.yaml ...]

Zero org calls, zero cost — this is the free half of the methodology.
Companion: drift_check.py (deployed-vs-tested), and the generic censuses in
../python/. Method write-up: "Green Is Not Evidence" (CMMCSecureCloud).
"""

import re
import sys

try:
    import yaml
except ImportError:
    print('PyYAML required:  pip install pyyaml', file=sys.stderr)
    sys.exit(1)

# Heuristic: expectation text embedding literal values that usually belong to
# an external source of truth. Over-matches by design — verify before acting.
DRIFT_PATTERN = re.compile(r'\b\d[\d,.]*\b|"[^"]+"|\'[^\']+\'')


def load_cases(paths):
    cases = []
    for path in paths:
        with open(path, encoding='utf-8') as f:
            doc = yaml.safe_load(f) or {}
        for tc in doc.get('testCases', []) or []:
            tc['_file'] = path
            cases.append(tc)
    return cases


def expectation_signature(tc):
    """Everything asserted, minus the utterance — identical signatures with
    different utterances are a latent INV (paraphrase) group."""
    return (
        str(tc.get('expectedTopic', '')),
        str(tc.get('expectedActions', '')),
        str(tc.get('expectedOutcome', '')),
        str(tc.get('customEvaluations', '')),
    )


def depth(tc):
    if tc.get('customEvaluations'):
        return 'custom-evals'
    if tc.get('expectedOutcome'):
        return 'outcome'
    if tc.get('expectedActions'):
        return 'actions'
    if tc.get('expectedTopic'):
        return 'topic-only'
    return 'NO EXPECTATIONS'


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cases = load_cases(sys.argv[1:])
    if not cases:
        print('no testCases found — check the spec path(s)', file=sys.stderr)
        return 1

    n = len(cases)
    label = lambda tc, i: tc.get('utterance', '(no utterance)')[:60] or f'case {i}'

    # ── test-type columns ──────────────────────────────────────────────────
    print()
    print('  test type   count    share')
    print('  ---------   -----    -----')
    for name, count in (('MFT', n), ('INV', 0), ('DIR', 0), ('DRIFT', 0)):
        print('  %-11s %5d   %5.1f%%' % (name, count, 100.0 * count / n))
    print('  %-11s %5d' % ('total', n))
    print()
    print('  INV and DIR are structurally inexpressible in this format: a test')
    print('  case cannot assert a relationship between two responses. Latent')
    print('  material is counted below.')

    # ── latent INV groups ──────────────────────────────────────────────────
    groups = {}
    for i, tc in enumerate(cases):
        groups.setdefault(expectation_signature(tc), []).append(label(tc, i))
    latent = [ids for ids in groups.values() if len(ids) > 1]
    print()
    print('  latent INV material: %d group(s) of cases with identical' % len(latent))
    print('  expectations and different utterances:')
    for ids in latent:
        for u in ids:
            print('      %s' % u)
        print('      --')

    # ── expectation depth ──────────────────────────────────────────────────
    tiers = {}
    for i, tc in enumerate(cases):
        tiers.setdefault(depth(tc), []).append(label(tc, i))
    print()
    print('  expectation depth (a topic-only case passes whenever routing is')
    print('  right, regardless of what the agent said):')
    for tier in ('NO EXPECTATIONS', 'topic-only', 'actions', 'outcome', 'custom-evals'):
        if tier in tiers:
            print('    %-16s %3d' % (tier, len(tiers[tier])))
    for shallow in ('NO EXPECTATIONS', 'topic-only'):
        for u in tiers.get(shallow, []):
            print('      [%s] %s' % (shallow, u))

    # ── judge reliance ─────────────────────────────────────────────────────
    judged = [label(tc, i) for i, tc in enumerate(cases) if tc.get('expectedOutcome')]
    print()
    print('  judge-reliant: %d case(s) rest on the model-evaluated' % len(judged))
    print('  expectedOutcome. A judge that passes a known-bad response is a dead')
    print('  test — seed these with deliberate violations before trusting green.')

    # ── multi-turn ─────────────────────────────────────────────────────────
    multi = [label(tc, i) for i, tc in enumerate(cases) if tc.get('conversationHistory')]
    print()
    print('  multi-turn: %d case(s) use conversationHistory.' % len(multi))

    # ── drift carriers ─────────────────────────────────────────────────────
    carriers = []
    for i, tc in enumerate(cases):
        blob = ' '.join(str(tc.get(k, '')) for k in
                        ('expectedOutcome', 'customEvaluations'))
        if DRIFT_PATTERN.search(blob):
            carriers.append(label(tc, i))
    print()
    print('  drift-carrier expectations (heuristic — literal values that may')
    print('  belong to an external source of truth; verify before acting): %d'
          % len(carriers))
    for u in carriers[:20]:
        print('      %s' % u)
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())

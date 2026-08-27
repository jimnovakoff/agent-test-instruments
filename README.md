# agent-test-instruments

Four cheap instruments for finding out whether a green test suite means
anything — with a native port for **Agentforce** agent test specs.

A passing suite reports two things: which tests exist, and whether they pass.
It reports nothing about whether those tests would *fail if the system broke*.
On deterministic code a dead test is permanently, silently green; on an LLM
agent, a suite can measure the model's refusal *style* while its one real
guardrail defect runs uncaught. These instruments are the standing checks that
replace that faith with measurement:

| Instrument | Question it answers | Script |
|---|---|---|
| Coverage census | Where are there *no* tests? (by test **type**, not by file) | `python/matrix_census.py`, `agentforce/spec_census.py` |
| Isolation | Is this a test, or a fragment coupled to whatever ran before it? | `python/isolation_census.py` |
| Mutation | Would this test fail if the thing it guards broke? | `python/mutation_census.py` |
| Provenance / drift | Does the check read the artifact its name claims — and is production the version you tested? | `agentforce/drift_check.py` |

Test types follow Ribeiro et al., *Beyond Accuracy: Behavioral Testing of NLP
Models with CheckList* (ACL 2020) — **MFT** / **INV** / **DIR** — plus a fourth
column this methodology adds: **DRIFT**, one fact living in many carriers, each
asserted against the single source of truth.

The full experience report behind these scripts — fifteen defects found in one
session against a mature 480-test suite (six of them in the tests), replicated
across a second codebase and then a probabilistic third — is
**"Green Is Not Evidence"** (CMMCSecureCloud). The scripts are the recipes;
the paper is the yield.

## The generic Python instruments (`python/`)

Work on any pytest codebase. Under 500 lines combined, no dependencies beyond
pytest itself.

- **`matrix_census.py <testfiles...>`** — counts tests per type using a naming
  convention (`_inv_` / `_dir_` / `_drift_` in the test name; everything else
  is MFT). An empty column is the finding. The census does not create
  coverage; it makes existing coverage legible.
- **`isolation_census.py <testfiles...> [--max N]`** — runs every test alone
  in a fresh interpreter. Anything that fails is order-coupled: `pytest --lf`
  lies about it, one real bug reads as N failures, and any selector that cuts
  across the ordering breaks. `--max` is a ratchet — the count may fall,
  never rise.
- **`mutation_census.py [mutants.json]`** — applies each known defect in a
  committed mutant file (`{file, find, replace, tests}`), requires the
  guarding tests to FAIL, restores byte-for-byte. Two hard-won disciplines
  are structural: ambiguous find patterns are refused, and NOT CAUGHT is only
  issued after a whole-file run proves the mutation was effective — otherwise
  the verdict is **INEFFECTIVE**, which is either an equivalent mutant or *a
  live code path no test asserts on*. Three times out of three in the source
  systems, that bucket held real coverage holes. Interrogate it before
  discarding it.

  Unlike auto-mutation tools (mutmut, cosmic-ray, PIT — use those too, for
  breadth), a curated mutant file is **institutional memory**: each entry is a
  named, explained defect that happened or nearly happened, re-verified on
  demand forever. Write yours from your own postmortems.

## The Agentforce instruments (`agentforce/`)

Agentforce DX expresses agent tests as YAML specs (`sf agent generate
test-spec`) compiled to `AiEvaluationDefinition` metadata and run headlessly
by `sf agent test run`. That is a complete MFT harness. What the platform
does not do is audit the *test design* — these do, and both run at **zero
model-call cost**:

- **`spec_census.py <test-spec.yaml>`** — the coverage census, natively for
  agent specs. Beyond MFT/INV/DIR/DRIFT it reports what this format makes
  measurable: **expectation depth** (a topic-only case passes whenever
  routing is right, regardless of what the agent said), **judge reliance**
  (every `expectedOutcome` verdict rests on a model-judge — seed those cases
  with deliberate violations before trusting green), **multi-turn usage**,
  latent paraphrase groups, and drift-carrier expectations. Needs only
  PyYAML; no org, no credits.
- **`drift_check.py <spec.yaml> --definition <ApiName> --org <alias>`** —
  retrieves the *deployed* `AiEvaluationDefinition`, converts it with the
  CLI's own `--from-definition`, and structurally diffs it against the spec
  you test locally. Sandbox-green certifies the version you tested; this
  certifies production **is** that version. Needs an authenticated org and a
  current Salesforce CLI; still zero model calls.

The paid instruments — per-case isolation runs and instruction-mutation
(perturb the agent's instructions, run the guarding cases, require failure)
— port through `sf agent test run` and metadata deploys to a sandbox. They
bill per action; run the free instruments first and sample the paid ones.
An eval suite that passes against a lobotomized agent is measuring nothing.

## Order of operations (the cost model)

1. Census (free) — find the empty columns and shallow cases.
2. Isolation / provenance / drift (free) — find the fragments and the
   stale-subject checkers.
3. Baseline the suite once, capture responses — latent INV pairs can then be
   evaluated *offline* at zero marginal cost.
4. Mutation, sampled — one mutant per guardrail, only its guarding cases,
   stability-doubled. Believe no probabilistic failure you have not re-run.

## License

MIT. If these find something in your suite, the author would enjoy hearing
about it.

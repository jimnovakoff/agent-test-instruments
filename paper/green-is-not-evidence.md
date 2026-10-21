# Green Is Not Evidence

**An experience report: what a mature, passing test suite concealed, and the
four instruments that found it**

*Subject systems: a CMMC Level 2 assessment agent pair and their guardrailed chatbot*

*James Novakoff — CMMCSecureCloud LLC — v2.1, 2026-08-29*

---

## Abstract

A test suite reports two things: which tests exist, and whether they pass. It
reports nothing about whether those tests would fail if the system broke. That
second property is normally taken on faith, and for systems with a probabilistic
component the faith is at least occasionally disturbed: a dead test tends to
surface as flakiness, disagreement between runs, something a person notices.

For deterministic systems it never surfaces at all. A test that asserts nothing
is permanently, silently green.

This paper describes four instruments developed while hardening a CMMC Level 2
assessment agent — a system that scores a defense contractor's Salesforce
environment against the 110 NIST SP 800-171 controls and maintains the crosswalk
a certification assessment depends on. A wrong output in this domain means a
wrong score submitted to a federal database under an executive's
affirmation.

The first instrument is Ribeiro et al.'s capability × test-type matrix from
*CheckList* (ACL 2020), extended with a fourth column the domain required. That
instrument answers *where are there no tests*. The other three answer questions
CheckList does not ask: whether a test can run at all on its own, whether it
fails when the thing it guards breaks, and whether it reads the artifact its own
name claims. Applied to a suite of 480 passing tests, they surfaced fifteen
defects — nine in product code, six in the test suite itself — several of which
had been present since the initial commit.

One framing fact matters throughout: during the whole period measured here,
these systems' outputs INFORMED a certified assessor's manual reviews and never
replaced them. Every client-facing number passed through human judgment, so the
defects below were found and fixed while being wrong was still free. The
instruments are what let an advisory tool earn autonomy; that ordering is the
point, and §8.1 makes it the closing question.

A third subject extends the measurement past determinism: the practice's
public chatbot, a large language model behind a ~21k-token system prompt,
guarded by a 126-case suite of deterministic string assertions. The same four
instruments — the free half first, at zero model-call cost — found the suite
measuring the model's refusal *style* rather than its behavior, one real
guardrail defect, and a checker that had been dead for four months while
calling itself blocking (§7.3).

The paper closes with a calibration record: the author's confidence estimates,
stated numerically before and after each instrument ran, were systematically
optimistic by 15–20 points on links that had not been instrumented, and roughly
accurate on links that had. That gap is the argument for instruments over
judgment.

Underneath the individual findings, the sessions kept measuring one thing
in different clothes: a suite has two sizes — the number of tests it
contains, and the amount of independent evidence those tests produce — and
every defect class reported here is a mechanism by which the first
overstates the second while hiding the overstatement. The campaign grew a
mature 480-test suite to 644, aimed almost entirely at holes and dead
tests its author could not see from inside; his calibrated estimates
missed the same gap by the same margin. The four instruments are best
understood jointly, as an estimator of *effective* coverage — a quantity
no dashboard reports.

**This is an experience report, not a methods paper.** Three of the four
instruments are established practice that we re-derived under field pressure
rather than invented; §1.1 says which, and credits the literature. The
contribution on offer is the measurement — what a specific mature suite actually
contained, in a domain where being wrong is a false statement to the federal
government — together with one small extension to CheckList's taxonomy and the
calibration record. A reader looking for a novel technique should stop here.

---

## 1. What 480 green tests tell you

The suite under study had 480 tests, all passing, accumulated over five months
of active development against a live compliance product. It had caught real
regressions. It was organized into named categories — schema integrity, column
spec, round-trip, triggers, export, CLI — and a `make` target per category.

By every visible signal it was a healthy suite.

The categories are the first thing worth examining, because they are a map of
the *codebase* rather than a map of what the system is supposed to do. "Schema",
"columns", "export", "CLI" enumerate where code lives. Filed that way, an
untested behavior leaves no visible hole: there is no cell to be empty, because
the filing is by artifact and every artifact has some tests.

That observation is what sent us to CheckList.

---

### 1.1 What is not new here

Three of the four instruments below are established practice. We arrived at them
by hitting the problems they solve, not by reading the literature first, and the
report is more useful if that is said plainly rather than left for a reader to
discover.

**Mutation testing (§5) is from 1978.** DeMillo, Lipton and Sayward proposed it
in *Hints on Test Data Selection*, and its founding premise is exactly the claim
§5 makes: a passing test is worthless until you demonstrate it fails when the
code breaks. There is a large literature since — Jia and Harman's 2011 survey is
the standard entry point — and mature tooling in most ecosystems (PIT for the
JVM, `mutmut` and `cosmic-ray` for Python, Stryker for JavaScript). Had we
reached for an existing tool rather than a fifty-line harness, we would have got
better mutation operators and worse control over which code paths the mutants
touched; §5.1 is the reason that trade mattered here, but it is a trade, not an
absence of prior art.

**Test independence (§4) is standard xUnit doctrine.** "Tests should not depend
on execution order" appears in Meszaros's *xUnit Test Patterns* as the
Interacting Tests smell, and every major runner ships a randomizer to enforce
it. Our contribution is a ratchet and a number, not the idea.

**Assert-against-the-source (§6) is a named test smell.** It is a specific
instance of what the same literature calls the Mystery Guest — a test whose
outcome depends on an artifact it does not name and the reader cannot see. What
we add is the observation that the artifact is often a *derivative of the real
source* rather than an unrelated file, which makes it far harder to spot: a test
reading a cached database really is reading the right data, until the day the
cache is stale.

What we believe is genuinely new, and it is modest:

- **The DRIFT column (§3.2)** — one fact, many carriers — as a fourth test type
  alongside MFT/INV/DIR. CheckList's three types all assume one input mapping to
  one output; multi-carrier facts are a different failure mode, and in a
  compliance system they are the dominant one.
- **The calibration record (§8)** — confidence estimates that were accurate on
  probed components and optimistic by a consistent margin on unprobed ones. At
  n=1 this is an observation, not a result.
- **The inversion (§11)** — that determinism removes the signal which would
  otherwise reveal a dead test. The mutation-testing literature assumes you know
  your tests might be inadequate; the point here is that on deterministic code
  nothing will ever tell you, so the assumption has to be replaced by a standing
  check.

The rest is a measurement of what those instruments found in one real system.

---

## 2. Step zero: shrink the surface

The cheapest behavioral test is the one you never have to write. Before
classifying tests, ask of every rule the system enforces: *can this be expressed
deterministically?* If yes, move it out of the probabilistic layer entirely —
into a specification table, a database constraint, a trigger, a domain-specific
rule language — and test it like ordinary code.

In this agent that took the form of `control_check_spec`: a database table of
mechanical checks (field, operator, threshold, target control) that a scanner
evaluates against retrieved Salesforce metadata. "Session timeout must be
≤ 15 minutes" is not a judgment call a model should re-derive per engagement; it
is a row. The agent's judgment is reserved for what genuinely needs it —
interpreting novel org configurations, drafting findings prose — and the spec
rows are tested with exact assertions.

Hosted agent platforms have converged on the same move. Salesforce's Agent
Script, a deterministic guardrail DSL for Agentforce, exists precisely so that
business rules follow code paths rather than model reasoning. Whatever the
mechanism, the principle holds: **the probabilistic surface you must behaviorally
test should be the smallest one the product can tolerate.**

There is a corollary this paper is largely about. Every rule you push down into
the deterministic layer becomes a rule whose failure is silent. You have traded
a noisy failure mode for a quiet one, and the instruments below are the price of
that trade.

---

## 3. Instrument 1 — the coverage map

*Question answered: where are there no tests?*

CheckList proposes a matrix: capabilities as rows, test types as columns, each
cell holding zero or more tests. The empty cells are the output. Three types:

- **MFT** — minimum functionality. Supply an input and its expected output.
  Requires knowing the right answer.
- **INV** — invariance. Perturb the input in a way that cannot change the
  correct answer; assert the output is unchanged.
- **DIR** — directional expectation. Perturb in a way that must move the answer
  a known direction; assert it moves that way.

### 3.1 The test types are about label economics, not determinism

The usual reason given for skipping CheckList on non-ML systems is that it was
designed for models. That reads the taxonomy wrong.

MFT/DIR/INV divide on **what you can assert**, not on whether the system is
deterministic. MFT needs you to know the right answer. INV and DIR need only a
relationship between two runs. Ribeiro reached for INV and DIR because for an
NLP model the right answer is expensive to obtain and often underdetermined.

That is a property of **label scarcity**, and label scarcity is a property of
*scale*, not of non-determinism. We knew every right answer in this system and
still could not afford to write them: hand-authoring 110 controls × 6 columns of
expected values is 660 opportunities to typo a fixture. The directional scoring
test generates 220 assertions from a rule; the export fidelity test generates
660. Same economics as the paper, different cause.

### 3.2 A fourth column the domain required

Three types assume one input mapping to one output. Compliance data has a
different failure mode: **one fact living in many places**.

The SPRS point values — how many points each of the 110 controls is worth —
existed in eight carriers: a seed script, a schema bootstrap, the live database,
a generated markdown reference, a regression fixture, two skill documents, and a
chatbot system prompt. They drifted. The discrepancy went undetected for three
and a half months, during which any of five carriers would have given a
confidently wrong answer.

No arrangement of MFT, INV or DIR catches that, because nothing about a single
input/output pair is wrong. So the matrix grew a fourth column:

- **DRIFT** — one fact, many carriers. Assert each carrier against the single
  designated source of truth, and name both sides in the failure message.

### 3.3 What the census showed

Classify every test, count per column, print the grid including zeros:

```
  test type   count    share
  MFT           461    92.0%
  INV            33     6.6%
  DIR             2     0.4%
  DRIFT           5     1.0%
```

(The column sums exceed 480 because the census classifies every test the
runner collects, and the suite had already grown past its starting 480 by
the time the census first ran — the count is of the collection at that
moment, not the session-start headline.)

Two directional tests, on a system whose entire purpose is to
compute a number that moves. The suite could prove the score was 110 when
everything passed and −203 when everything failed, and had almost nothing to say
about the 108 values in between or about which direction a fix moved the number.

Note also that no new tests were written to produce this table. The INV column
was already 33 tests — idempotency checks, round-trips, dry-run assertions —
written by people who never used the word invariance. The census creates no
coverage. What it does is make existing coverage legible, and the
illegibility was the only reason nobody had noticed DIR was nearly empty.

---

## 4. Instrument 2 — isolation

*Question answered: is this a test, or a fragment of one?*

Run every test alone in a fresh interpreter. Anything that fails is coupled to
execution order.

In this suite, **20 of 105** tests in one file failed alone. The coupling was
intra-class: classes modeled a lifecycle — plan → dry-run → execute → verify →
skip → reset — with each test asserting one transition and inheriting state from
the test before it.

That is a defensible thing to want and an indefensible way to get it. The costs:

- `pytest --lf`, the first move when something breaks, reports a false failure.
- One real defect in an early test cascades into every test that depended on its
  state; one bug reads as eleven.
- Any selector that cuts across the ordering — a test-type column, a `-k`
  filter, a future parallel runner — breaks.
- Twenty tests carrying twenty names yield one piece of evidence, not twenty. A
  suite's count overstates its independent checks by exactly this margin.

The fix is per-test preconditions via idempotent helpers, not consolidation:
collapsing twelve tests into one lifecycle test removes the coupling by removing
the tests, and makes failure localization worse.

One subtlety worth stating, because it is easy to get wrong: **the precondition
must establish the interesting state, not merely a row that exists.** A test
asserting that `reset` returns an action to `planned` must first drive it to
`skipped`. Resetting an already-planned action passes while proving nothing —
trading order-coupling for a tautology.

---

## 5. Instrument 3 — mutation

*Question answered: does this test fail when the thing it guards breaks?*

Break the behavior deliberately. Confirm the test fails. Restore.

This is the instrument the other three cannot substitute for, and it is the one
that changed our estimate of the suite most. Isolation proves a test *runs*
alone; it says nothing about whether it *asserts* anything. A test can be
independently runnable, correctly classified, in a well-populated cell, and
still be dead.

Of the 20 tests decoupled under instrument 2, **18 caught their mutation and 2
did not**:

**A tautology.** A test named `test_verify_logs_gap_to_met_transition` asserted
that an audit row recorded `old_status = 'Suspected Gap'` and
`new_status = 'Met'`. The code under test wrote those two values as hardcoded
string literals:

```python
VALUES (?, ?, 'remediate.py', 'Suspected Gap', 'Met', NULL, ?, ?)
```

The test asserted the literals against themselves. It could not fail while that
INSERT existed. It had passed since the initial commit while proving nothing —
and it was concealing a real defect, because the function never read the
control's actual status. A control already `Met` still produced an audit row
claiming it had transitioned from a gap. On a compliance artifact that is a
fabricated record, not a stale one.

**An incidental pass.** A test named `test_06_show_displays_detail` asserted
that the string `SecuritySettings` appeared somewhere in a command's output.
That string also appears in the target-field name and in the template XML, so
redacting the metadata-type line the test was named for left it green. It could
not tell whether the detail it existed to check was displayed at all.

### 5.1 Mutation testing's own failure mode

The harness will lie to you in one specific way: **a mutation aimed at code the
test does not execute reads exactly like a weak test.**

This happened four times in one session. A mutation to a seed script that the
bootstrap does not read. A mutation to an `UPDATE` branch in a code path whose
fixtures take the `INSERT` branch. A mutation to a bootstrap file when the test
reads an already-migrated database. Each produced a confident NOT CAUGHT that
was the harness's fault.

The discipline that resolves it: **when a mutation is not caught, first prove
the mutation was effective** — run the whole file and confirm *something*
fails. If nothing does, the mutation was inert and you have learned nothing
about the test.

A day later, with the harness promoted from scratchpad to a committed
instrument (§10), that last sentence turned out to be too strong. Twice in one
session a mutant that survived the whole-file check was neither equivalent nor
mis-aimed — it was mutating a live code path that **no test anywhere asserted
on**. The importer's `UPDATE` branch (the branch every real re-import takes;
every fixture imported into a fresh database and took `INSERT`), and the
scanner's benchmark comparisons evaluated *at* the benchmark (observed equal to
expected — the value a correctly configured org actually carries, because the
benchmark is the recommended setting). Both mutations survived the entire
suite. Each verdict became a new test the same day, and the mutants now catch.
The refined reading: NOT CAUGHT indicts the named tests; an effective-but-
uncaught mutation indicts the whole file's coverage of that path. Distinguish
which before dismissing the verdict — the harness's "ineffective" bucket is
where two of this system's coverage holes were found, and where the sibling
system's largest one turned up on its first pass (§7.2): three instances
across two repositories, all the same shape.

One further failure mode surfaced only once the harness ran long enough to
overlap other work: **on a cloud-synced filesystem, reading a source file while
the harness is rewriting it can serve stale content.** A search during a live
census returned a version of a styling function containing a backslash defect
that existed in no commit and not in the working tree — plausibly an old
synced revision — and the phantom survived until checked against `git show
HEAD`. The rule that follows: while a census runs, treat every read of a
mutated file as suspect, and verify any finding against the repository's
object store before acting on it.

---

## 6. Instrument 4 — provenance

*Question answered: does this test read the artifact its name claims?*

This one has no counterpart in the literature we found, and it produced five
findings in a single session. Stated as a rule:

> **Assert against the source, not against something derived from it.**

Five instances, all the same shape:

| Test claimed to check | Actually read | Consequence |
|---|---|---|
| the schema bootstrap every client DB is built from | a cached local database | a wrong point value in the bootstrap passed until someone cleared their cache |
| the bootstrap's audit-column default | an already-migrated schema | reverting the source left the test green |
| the production schema | a harness schema silently built with 0 of its 9 triggers | no trigger behavior was testable in 107 tests |
| a sibling repository's parity | its own repository only | the same defect was fixed in one repo and left live in the other, twice |
| whether a constraint enforced a domain | the constraint's *existence* | five constraints enforced nothing |

The last of those deserves its own note, because the failure is a language
subtlety rather than an oversight:

```sql
sqlite> SELECT 'Yes' IN ('Y','N','N/A',NULL);   -- NULL, not 0
```

A bare `NULL` in an `IN` list makes every non-matching comparison evaluate to
NULL rather than false, and SQLite treats a `CHECK` whose expression is NULL as
**satisfied**. Five columns across four tables declared an enforced domain and
enforced none of it. The column recording whether a policy had been verified
accepted the value `'banana'`.

Structural tests would not have caught this — the constraint was present and
correctly spelled. Only a behavioral probe (*insert something invalid and
require rejection*) distinguishes an enforced constraint from a decorative one.

And when the constraint was finally made to bite, it caught seven test fixtures
that had been seeding `gap_risk = 'HIGH'` — uppercase, a value the schema had
always declared illegal and the inert constraint had always accepted. Every test
reasoning about that column had been working with a value the production trigger
never emits.

---

## 7. What the instruments found

Presented as evidence that the instruments work rather than as the point.
Fifteen defects in one session against a mature, passing suite:

**In product code**

| Defect | Effect |
|---|---|
| A function defined, documented as part of the pipeline, never called | A new client's baseline set 2 controls instead of 48 — **150 SPRS points understated** |
| Wiring that function in, unguarded | Would have overwritten **51 of 110** assessor dispositions, flipping documented gaps to Met — the score-*inflating* direction |
| Audit attribution defaulting to a hardcoded personal username | Every unattributed change named a specific person who may not have made it |
| The same defect in a sibling repository | Including a `change_note` naming a migration from the *other* product, copied and never noticed |
| Verification writing audit transitions as literals | The audit trail could record a transition that never occurred |
| Import never reading one editable column | The assessor's entry silently discarded on every round trip |
| Import using `INSERT OR REPLACE` | Re-importing a **freshly exported** workbook destroyed the entire agent evidence trail |
| Personal-username defaults on four more columns | Inherited by every client database |
| Five inert `CHECK` constraints | Declared domains enforcing nothing |

**In the test suite itself**

| Defect | Effect |
|---|---|
| 20 of 105 tests order-coupled | Count overstated independent evidence by ~19% |
| Test harness building a schema with 0 of 9 triggers | An entire category of behavior unfalsifiable |
| Canon tests reading a cached database | The highest-consequence check in the repo, reading the wrong artifact |
| One tautological test | Asserted literals against themselves since the initial commit |
| One incidental-substring test | Passed on a string that appears elsewhere in the output |
| Seven fixtures seeding an illegal value | Tests reasoned about a value production never emits |

Six of the fifteen defects were in the tests themselves, and that ratio is
the real finding: a suite
that is itself defective at that rate cannot be used to estimate the quality of
anything else until the instruments have run.

There is a name for what this table keeps measuring. A suite has two
sizes: its **nominal coverage** — the number of tests it contains, the
figure every dashboard reports — and its **effective coverage**, the
amount of independent evidence those tests actually produce. Every defect
class above is a mechanism by which the first overstates the second:
twenty coupled fragments sharing a few pieces of evidence among twenty
names; a tautology contributing zero; checks whose evidence concerns a
derivative rather than the subject they are named for. And each mechanism
is invisible in a passing run, because overstatement never fails. The
instruments of §§3–6 are individually cheap probes; jointly they are the
only estimator of effective coverage we have found — the census maps
where evidence could exist, isolation counts how many names share one
piece of it, mutation tests whether a claimed piece exists at all, and
provenance checks what the evidence is actually about. By that estimator,
this mature, diligently built suite was carrying substantially less
evidence than its count implied — the campaign that closed the gap grew
it by a third — and nothing short of the instruments could have said so.

The before-and-after, in the estimator's own units:

| Measure | Campaign start | Campaign close |
|---|---|---|
| Tests passing (primary system) | 480 | 644 |
| Census — MFT | 461 | 537 |
| Census — INV | 33 | 38 |
| Census — DIR | 2 | 29 |
| Census — DRIFT | 5 | 34 |
| Order-coupled tests | 20 (in one 105-test file) | 0, ratcheted in CI |
| Committed mutants, verified catching | 0 | 24 |
| Tests known to assert against a derivative of their subject | 5 (found by provenance) | 0 known |
| Sibling system: tests / mutants | 207 / 0 | 254 / 19 |
| Author's calibrated confidence | 70 | 88, instrumented links only |

(Census figures classify the pytest collection at census time — 501 tests
at the first census, 638 at the last — while the headline counts are CI
passes; the two populations differ slightly by design. The DIR and DRIFT
columns are the picture in miniature: the two test types the suite's
authors had no name for grew fourteen-fold and seven-fold once the census
made their absence visible.)

### 7.1 The next session's yield

The instruments re-ran one day later, now as committed tooling, against links
the first session had not probed. Every newly probed link again paid out:

| Found by | Defect | Effect |
|---|---|---|
| the harness's first committed run | importer `UPDATE` branch carried no value assertions anywhere in the suite | a parameter transposition — notes and artifact-type swapped on every re-import — survived the whole suite |
| a mutation sample | no comparison ever evaluated at its benchmark boundary | an org at exactly the recommended setting (session timeout exactly 15 minutes) could read as a gap, unseen |
| provenance, color carriers | tag colors hand-maintained in two more places than believed, against a golden table both had drifted from | the Unassessed font differed from the golden record in both carriers; three tag classes had no conditional-formatting rule at all, so selecting `[N/A — Assessed]` from the dropdown showed no fill |
| provenance, CLI write path | `cw.py set` validated bracket tags against a hand-maintained constant | five of thirteen legitimate dispositions refused at the CLI |
| the fix's own blast radius | a second test harness cloned the schema but not the golden tag table | the moment validation read the real table, every disposition write in that harness was silently refused — the hardcoded constant had been masking an empty reference table since the harness was written |

The suite grew by twenty tests; against the first census (§3.3) the DIR column
has gone 2 → 13 and DRIFT 5 → 20. By that session's end, ten mutants were
committed alongside the tests and run as `make test-mutation`, all ten
caught; the mutant set has kept growing since (§10 carries the current
count).

### 7.2 The second system

The subject so far is one codebase. Its sibling — an AWS assessment agent
sharing the same 110-control canon, scoring arithmetic, and deliverable
contract, but with an independent test suite (207 tests, five months of its
own history) and independent exporter, adapter, and CLI code — had never had
any of the instruments run against it. Porting the harness took an afternoon:
the harness file itself is now byte-shared between the repositories and pinned
identical by the cross-repo drift test, so the *instrument* is drift-guarded
the same way the canon is; only the mutant sets differ, because the defects
worth simulating are platform-specific.

The first-ever mutation pass over that suite reproduced the first system's
findings almost beat for beat:

| Found by | Defect | Effect |
|---|---|---|
| the first mutation pass (5 of 6 caught) | transposing two columns in the family-sheet SELECT survived the **entire** 207-test suite | the export tests checked headers, sheet counts, and one tag cell — every workbook value could be present and wrong; the ineffective-mutant bucket again, exactly as §5.1 describes |
| the agreement port | nothing pinned the gaps sheet's deliberate union semantic (CCA gaps **or** agent-flagged controls) | dropping one `OR` branch would silently remove scanner disagreements from the most-read sheet while every other number stayed right — now a caught mutation |
| the fidelity port | the two CLIs disagree on what omitting notes means (one preserves the narrative, one overwrites it) | not a defect but an undocumented divergence between siblings; now pinned as intended semantics by a test on each side |

The shape replicated too, which is worth more than the count: on both systems
the value-carrying code proved **correct once probed** — the transposed-column
mutant, once a fidelity test existed, was caught; the exporters, adapters, and
CLIs carried what they were given. What the instruments found, on both
systems, was *coverage that could not have noticed* — plus drift among
hand-maintained copies of golden data. Two systems is still not many, but a
second independent suite exhibiting the same failure taxonomy under the same
instruments is the difference between an anecdote and a pattern.

End state of the second system at that session's close: 218 tests passing,
nine committed mutants, all caught, `make test-mutation` on both sides of the
repository pair. (Both suites and both mutant sets have grown since; §10
carries the current counts.)

### 7.3 The third system: a probabilistic subject

The first two systems are deterministic. The third is not: the practice's
public chatbot — a hosted worker wrapping a large language model behind a
~21k-token system prompt, guarded by a 126-case response-classification suite
whose assertions are deterministic substring checks (contain-any, not-contain,
not-echo). This is the quadrant §10 previously admitted was unmeasured. The
instruments ran in two waves: the free half first (census, isolation analysis,
provenance — zero model calls), then the paid half (a full-suite baseline plus
a fix-and-verify cycle — roughly three hundred model calls, single-digit
dollars).

The free wave paid out before a single model call:

| Instrument | Finding | Effect |
|---|---|---|
| provenance | the blocking prompt-drift check had pointed at a filesystem path dead since a repo move four months earlier | the checker skipped on every run while calling itself blocking — the stale-path Mystery Guest again; resurrected, it confirmed no drift had accumulated while unguarded |
| census | MFT 124 / INV 0 / DIR 0 / DRIFT 0 | the empty columns were not unwritten tests but **structurally inexpressible**: single-utterance cases with absolute string assertions cannot state a relationship between two responses |
| census | 2 of the "126 cases" can never execute | the runner has no multi-turn support and silently skips them — suite-size inflation, the count overstating the evidence |
| isolation | a full run needs one fresh session per case, against a production session cap deliberately sized for human visitors rather than test harnesses | tests that structurally cannot run against production configuration — an operational coupling no code-only reading would flag (and the cap's rolling window throttled the first verification attempt) |

The paid wave then measured what the suite was actually measuring. Baseline on
the newly migrated model: 106 of 124 passing — but stability re-runs and
response inspection showed roughly fourteen of the seventeen failures were the
*suite's* fault, in two classes. `must_not_contain` substring bans fired on
correct refusals that **name what they refuse** (a ban on mentioning the
system prompt, tripped by "I won't share my system prompt"; a ban on an
unauthorized-use phrase, tripped by the refusal denying that very use); and
`must_contain_any` vocabularies were too narrow for a paraphrasing model —
correct answers in unanticipated words. A newer model with a more explicit
refusal style mass-triggered both. The suite was measuring refusal *style*,
not behavior.

The remainder was real, and it was one defect in two instances of a species
worth naming: **the template-versus-rule collision**. The prompt's response
format said "offer the booking CTA" unconditionally while a tier rule
prohibited it on legal-liability questions; the model resolved in the
template's favor, reliably for one phrasing (3 of 3 runs) and intermittently
for its paraphrase. Later, the same species again: a products section relied
on a suggested *template's wording* for option-not-a-requirement framing, and
the model paraphrased the template away — sometimes dropping the substance
with it. Both fixed by making the rule explicit about substance rather than
phrasing; both verified green under stability doubles afterward.

Two byproducts came free. The suite's first measured INV violation — the
legal-tier paraphrase group disagreeing PASS/FAIL/FAIL/PASS — was computed
offline from the baseline's captured responses at zero marginal cost, and
resolved to agreement after the fix. And the assertion rework produced its own
lesson twice in one day: the first rewritten ban for one case kept a phrase
that the *correct denial* itself embeds — the refusal names the very
authorization it is denying, so the ban fires on the right answer —
substring assertions are negation-blind, and the rule that survives is: **a
banned phrase must be one no correct refusal would contain** —
affirmation-anchored, or a verbatim content-leak string.

Three disciplines had no counterpart in the deterministic quadrant: verdict
stability is part of the verdict (re-run a failure before believing it — one
"regression" passed on its double, one artifact rotated between runs);
substring suites on paraphrasing models carry irreducible flake, so a
rotating vocabulary miss per full run is *expected*, budgeted, and
stability-checked rather than chased; and the fix cycle itself must re-run
under doubles, because a probabilistic pass is one sample.

End state of the third system: every case green on its latest run, the
guardrail defect fixed at the prompt level, and the honest caveat standing —
the durable repair for the artifact class is paired-response INV assertions
or a judge, not more vocabulary.

---

## 8. The calibration record

Confidence was stated numerically, on request, at four points during the
session. Scale: 100 = no possibility of error.

| Point | Number | What changed |
|---|---|---|
| Before any instrument ran | **70** | Decomposed into six links, each scored from inspection |
| After the coverage map, isolation and directional work | **84** | Several links previously scored 88–90 turned out to be structurally broken |
| Question sharpened to *"does the code faithfully carry the assessor's judgment"* | **80** | Full weight moved onto a link that had been scored generously |
| After export/import fidelity and constraint enforcement | **88** | The weak link was weaker than scored, then fixed |

The number is less interesting than the error pattern. Estimates were:

- **roughly accurate** for links that had been probed;
- **optimistic by 15–20 points** for links that had not.

Every large correction came from the same place. Point values were scored at 90
while the tests guarding them were reading a cached database. Storage integrity
was scored at 92 while five of its constraints enforced nothing. Capture was
scored at 80 while the import path was silently deleting data.

Note what this is not: the estimates were not lazy. Each was decomposed into
named links with stated evidence. The decomposition was the problem — it made
the estimate *feel* grounded while every input to it was an unprobed assumption
about code that looked right.

**The practical rule: treat any confidence figure for an uninstrumented
component as an upper bound, not an estimate.** The instruments are not a way to
raise the number. They are the only thing that makes the number mean anything.

A fifth data point arrived the following session (§7.1). The links probed for
the first time — the workbook's summary sheets, its color carriers, the CLI
write path, the importer's second branch — each yielded defects; the links
probed the day before yielded nothing new. The pattern is doing what "upper
bound, not estimate" predicts: probed links stay quiet, unprobed links keep
paying out. The 88 stands for what has been instrumented; it says nothing
about what has not.

One later first-touch probe deserves recording precisely because it found
nothing: the workbook's remaining export domains, probed for the first
time, agreed with their sources. That is the record's first quiet
first-touch, and it fits the framing as stated — an uninstrumented figure
is an *upper bound*, unknown rather than presumed broken. The claim was
never that every probe finds a defect. It is that until the probe runs,
there is no way to tell a healthy link from the ones that kept paying out.

The second system (§7.2) supplies the record's first cross-system point. Its
suite had every visible health signal the first one had, and before its first
mutation pass no number for it would have been more than a guess dressed as
one; the pass immediately demonstrated a whole-workbook blindness no amount of
inspection had suggested. Its first stated figure was therefore issued at 85
*after* the instruments ran, raised to 88 only once the agreement and fidelity
ports landed — the number followed the instruments rather than preceding them,
which is the discipline this section exists to argue for.

### 8.1 The composed system, and the fifth instrument

These systems advise a certified assessor; they do not replace one. That
raises the question the whole record points at: the assessor's own judgment,
reviewing tool output, is confidently estimated around 85 — so when does
*assessor-with-instrumented-tool* meet or exceed *assessor-alone*?

Decompose the 85 and the answer splits. On consistency-class error —
attention at scale, hand-carried numbers, stale references, arithmetic — the
composed system already wins, and this paper's own history is the proof: the
3.5-month point-value drift happened to the *manual* workflow's reference
tables, the assessor did not catch it, and the instruments did in one run.
On judgment-class error the tool adds nothing directly; what it changes is
the judge's conditions — no zero-cost claim without a recorded reason, no
Met without its class of evidence, no affirmation over an incomplete
assessment, every scanner disagreement surfaced instead of buried.

The remaining unmeasured link is the review itself, and its failure mode is
automation complacency: the reviewer who stops overriding. A review that
never rejects is a dead test — the same theorem this paper opened with,
permanently green and silently meaningless. Which means the review is
instrumentable by the same methodology: track the override rate (an
engagement with zero overrides is a red flag on the review, not a compliment
to the tool), and mutation-test the reviewer — periodically seed a
known-wrong disposition into a review batch and require that it be caught,
the human analog of `make test-mutation` and standard practice in
radiology QA. When the seeded-error catch rate is measured and healthy, the
composed system exceeds the unassisted assessor *by measurement rather than
estimate* — and by this paper's own calibration record, an unmeasured
estimate of one's own review quality should be assumed 15–20 points
optimistic. The fifth instrument is for the human in the loop.

Two ceilings stay fixed and should be stated plainly: the tool's ceiling is
the assessor at their best, consistently, at every control — it cannot
exceed the judgment it is calibrated against, only stop it degrading. And
no instrument manufactures *independence*, which is what an external
assessment adds over any self-assessment, however instrumented.

---

## 9. Porting the instruments to hosted agent platforms — now measured

The self-hosted probabilistic port is measured in §7.3; this section
measures the hosted half, where the harness, the model, and the deploy
pipeline live behind a vendor's API. The concrete case is Agentforce, on a
free Developer Edition org: a three-topic fictional retailer with three
guardrail clauses written to be individually mutable (a pricing
prohibition, a legal refusal, a required estimate-framing), and a ten-case
suite — two guarding cases per clause, an allowed-behavior contrast case,
and three standing-fact checks. Findings, in the order the instruments
earned them:

**Mutation ports, and its §5.1 trap is worse here.** The first mutant
(delete the framing clause) survived the full suite twice and was never
applied: deploying the mutated topic metadata reports success and changes
nothing at runtime — plausibly the versioning model working as designed
(an active agent behaves as an immutable snapshot; the compiled planner
bundle deploys only against a deactivated agent), but nothing at deploy
time signals the contract. A canary mutation — change a standing fact the
suite pins; its case must flip — is what distinguished "survived" from
"never reached the runtime." On an opaque deploy pipeline the canary is
the precondition for any verdict at all.

**The three mutants returned three verdict species.** Once effective, the
framing-clause mutant survived: the hedging language visibly disappeared
and the LLM judge passed the responses anyway. The pricing-clause mutant
was caught — the unguarded model computed the bulk total the clause
prohibits — but its paraphrase twin passed, because the model declines
that phrasing spontaneously: one case guards the clause, its twin is
behaviorally redundant. The legal-clause mutant was effective but
undetected: the model refuses legal questions unprompted, so the clause's
measured function is converting a sometimes-refusal into an
always-refusal, and detecting its removal needs an utterance the model
would not refuse on its own. Redundant-with-the-model, reliably guarded,
and unguardable-as-written are three coverage classes a green suite
renders identically.

**Even CAUGHT is a sample.** Across six runs the pricing mutant's detector
caught it in four, and once misfired on the intact clause. A guarding case
does not detect a mutation; it detects it with some probability, in both
directions, so the committed harness records verdicts against an expected
*set* per mutant — CAUGHT or INTERMITTENT can both be the honest
expectation — rather than rounding a distribution to a bit. (All stability
claims in this section rest on doubled runs, n=2 per verdict.)

**The assertion layer, not the value layer, is where the defects were.**
The judge failed in both directions: it passed clause-less behavior, and
it failed a compliant response — explaining that the response "uses
'typically' instead of the required 'estimated'" while the response in the
same result record contained "an estimated 5 to 7 business days." Whether
the judge hallucinated or the pipeline fed it something other than the
displayed response cannot be distinguished from outside; either is a
verdict decoupled from its visible subject, and the judge is an
unversioned dependency besides. With the deterministic string evaluation
unusable in our configuration, this evaluation path offered no reliable
carrier for a lexical assertion. A follow-up probe scoped that gap: the
newer Studio runner (`agent test run-eval`, in beta) turns the same custom
evaluation into a working deterministic assertion — true response text,
clean baseline, the framing mutant caught three of three while the judge
stayed blind in the same runs. The carrier exists one runner over, with
two qualifiers: it is reachable only through the legacy-spec translation
(the native scorer catalog has no deterministic response-text scorer), and
a deterministic assertion does not make detection deterministic — the
second guarding case caught the mutant in two of three runs, because the
unguarded model sometimes says the word on its own.

**Provenance and routing port intact.** The results pipeline initially
reported the routed topic under a different name form than the deployed
metadata carries, failing every topic assertion until the topics were
renamed — verify what the pipeline actually reports before trusting any
assertion built on it. And a topic-scoped guardrail only guards utterances
the router sends to its topic: one guarding case was answered by a
built-in topic and never touched its clause, and one borderline utterance
routed differently across agent activations while staying consistent
within each. `expectedTopic` is load-bearing — a guarding case must be
routing-verified before its outcome verdict means anything.

**The arc is a committed harness, and its own first campaign caught two
defects in the harness itself** — a restore bug that silently redeployed a
mutated baseline (caught only by a state-verification gate: the provenance
lesson pointed at the instrument), and a false CAUGHT from a guard that
was flaky at baseline. The rules that survive: a guard must be stable at
baseline for its failure to attribute to a mutant, and the harness must
verify restored state, not assume it. Mutation tooling is code; it earns
trust the same way the suites it measures do.

**Per-case isolation ports for the cost of a spec split.** The Studio
runner executes local YAML with no deploy, so isolation reduces to
one-case files run in fresh invocations. All ten solo verdicts matched a
same-activation batch reference, borderline routing case included: each
case evidently gets a fresh session, and the suite's case count equals its
count of independent evidence — the opposite of §4's 20 of 105. (One
probabilistic sample per cell: consistent with isolation, not proof of
it.)

**A deterministic oracle makes the judge measurable.** With the string
assertion and the judge grading the same binary lexical criterion on
identical responses, the oracle is ground truth and the judge is the
subject — §8.1's instrument-the-reviewer method pointed at the platform's
reviewer. Over ten paired verdicts the oracle was correct ten of ten; the
judge agreed eight of ten, erring once in each direction — failing a
compliant response that contained the required word, and passing a
violation. A sharpened rubric caught violations a semantic one missed (two
of three) at the price of that false positive. Small n, stated as such;
the shape is the point: given a binary criterion and the answer in front
of it, the judge disagreed with ground truth about one time in five.
Anchor every criterion that can be deterministic to a deterministic
carrier; reserve the judge for what genuinely needs one.

One piece remains unexercised: generated INV/DIR variants — the census had
already shown INV and DIR structurally inexpressible in single-case YAML,
the same ceiling §7.3 found in the chatbot suite's format.

### 9.1 The economics do not port

Our local suite runs in seconds for free; a hosted eval bills per action. At
Agentforce's published rates as of this draft (August 2026) a standard action
costs 20 Flex Credits ($0.10; 16 in
sandbox), so a case firing two governed actions runs roughly $0.16–0.25 —
against roughly $0.01–0.04 for an equivalent judge-scored case on a raw model
API with prompt caching. A 500-case suite is ~$100 per run on the platform
versus ~$5–20 against the API.

That spread is what makes surface-shrinking (§2) an economic argument and not
only an engineering one, and it is why mutation testing on a hosted platform
should target a sampled subset rather than the whole suite.

The §7.3 measurement supplies actuals for the self-hosted case: the entire
campaign — baseline, stability re-runs, two fix-and-verify cycles, and a full
gate run — cost roughly three hundred model calls, single-digit dollars,
because the free instruments ran first and the paid runs were targeted (only
failures re-run, only changed cases re-verified). Most of the cost model, it
turns out, is just the order of operations.

The hosted measurement adds its own actual: the entire §9 campaign — three
mutants, canaries, stability doubles, and every baseline re-verification,
twenty-one ten-case runs in all — ran on a free Developer Edition's included
request pool, at zero marginal cost. The sandbox-first pattern is the hosted
analog of free-instruments-first: measure the suite against a toy subject on
free capacity, and spend production credits only on suites the instruments
have already vetted.

---

## 10. Limits

**The probabilistic quadrant is measured in both halves — but the hosted
half on a toy.** §7.3 runs the instruments against a self-hosted
model-in-the-loop subject; §9 now runs them against a hosted platform. The
hosted subject, however, is a three-topic lab agent with no actions and
invented facts, built to make the instruments demonstrable and the mutants
clean. That demonstrates the port and its yield — eleven findings and three
verdict species — not that the economics or the
verdict stability hold at the scale of a production agent with dozens of
topics and live actions. That measurement has not been made. The platform
observations themselves — the reporting and evaluation behaviors described
in §9 — are likewise observations from one org, one release channel, on a
free Developer Edition the vendor treats as preview-grade; any of them
could be a provisioning or channel artifact rather than a general property,
so we treat them as conditions of the measurement rather than as claims
about the platform.

**The named unmeasured link is now the human review.** The systems measured
here advise an assessor; §8.1 argues the review layer is instrumentable
(override rates, seeded errors) but those instruments have not yet run. Until
they do, any figure for the composed system is an upper bound.

**Instrument coverage is itself uneven.** Isolation and the census are automated
and run on demand, and mutation now is too: the harness is a committed,
byte-shared instrument (`make test-mutation` in both repositories) with
per-repo mutant sets — as of this draft, twenty-four on the first system and
nineteen on the second, all caught — pinning the canon, the scoring views,
importer branches, summary sheets, tag mappings, CLI write paths, adapter
precedence, the scanner boundary, and the judgment-side gates; the method is
reproducible rather than remembered. The hosted arc (§9) is now a committed
harness too, with its three-mutant set and per-mutant expected verdicts —
but three mutants sample one toy agent, forty-three mutants across two
suites still sample a fraction of their assertions, provenance
remains a hand-applied discipline, and nearly every area sampled so far has
paid out (§7.1–7.2), so the honest expectation is still that more remains.

**A sample of two sibling systems, one probabilistic cousin, and one hosted
toy — one domain, one author.** The second system
(§7.2) upgrades this from one codebase to two: independent suites and
independent product code, exhibiting the same failure taxonomy under the same
instruments. But the two share an author, a domain, an architecture lineage,
and half their reference data, so the replication is corroboration within a
family, not an independent trial. The calibration record in particular remains
a single practitioner's estimates about their own code; that it was
consistently wrong in one direction is suggestive, not general.

**The instruments do not address correctness of judgment.** In this domain the
dominant error mode is an assessor marking a control compliant when it is not.
No amount of test instrumentation touches that. Everything here concerns whether
the code faithfully carries a judgment it has been given — a strictly narrower
and more tractable question, and one worth separating explicitly, because
conflating them produces confidence numbers that cannot be acted on.

---

## 11. Conclusion

CheckList's contribution is that a coverage map makes absence visible. That
remains true and the fourth column extends it usefully to multi-carrier facts.

But a coverage map assumes its tests are honest, and this session's central
finding is that the assumption does not survive contact with a mature suite. A
tautology occupies a cell in the matrix and is counted as coverage. An
order-coupled fragment is counted as a test. A test reading a cached artifact is
counted as guarding the source it names. All three are permanently green, and on
a deterministic system nothing will ever tell you otherwise.

Determinism does not make testing easier. It removes the only signal that would
have told you the test was dead.

The four instruments — map, isolation, mutation, provenance — are cheap
individually and, as §1.1 sets out, three of the four are decades-old practice.
What this report offers is not their invention but their yield: applied
together to three systems — two deterministic, one not — they are not
optional extras on top of a coverage discipline. They are, jointly, the
measurement of the gap between a suite's nominal size and its effective
evidence. Here that gap was worth roughly a third of a mature suite,
in code written by an author who cares about testing to the point of
writing this paper, and it was invisible from inside: a green suite
of 480 tests supported a confidence estimate that was wrong by fifteen
points, in a system built to carry a number whose falsity is a false
statement to the federal government; and a 126-case guardrail suite was
measuring a model's refusal style while its one real guardrail defect ran
uncaught.

The arc underneath is about trust, not tests. These tools advised a human
the entire time, and the instruments are the mechanism by which an advisory
tool earns autonomy: each link probed, each probe kept as a standing guard,
the confidence number following the instruments instead of preceding them —
and the last instrument pointed at the human still in the loop.

Practitioner field reports have begun converging on the same locus from
the other direction. Jones, observing agent deployments at scale, argues
that "the checks, the loop, the verification layer — that's where
reliability lives," and asks who decides when work is finished, and by
what evidence. This report is one measured answer: the verification layer
itself must earn that authority, and green is not the evidence that
grants it.

---

## Acknowledgments

Drafting and analysis assistance from Claude (Anthropic). All measurements
were performed on the author's systems; the findings, claims, and
conclusions are the author's and were verified by the author.

---

## Artifacts

The instruments are released, MIT-licensed, at
https://github.com/jimnovakoff/agent-test-instruments: the generic Python
censuses (coverage matrix, isolation, mutation), the Agentforce-native
test-spec census and drift check, and the hosted instruction-mutation
harness of §9 — together with the complete lab subject (agent metadata,
test suite, and mutant set with expected verdicts), so the §9 measurement
is reproducible end to end on a free Developer Edition org. The two
production suites measured in §§3–7 belong to proprietary systems and are
not released; the defect classes and counts reported here are the record.

---

## References

- Ribeiro, M. T., Wu, T., Guestrin, C., & Singh, S. (2020). *Beyond Accuracy:
  Behavioral Testing of NLP Models with CheckList.* ACL 2020 (Best Paper).
  arXiv:2005.04118 · https://github.com/marcotcr/checklist
- DeMillo, R. A., Lipton, R. J., & Sayward, F. G. (1978). *Hints on Test Data
  Selection: Help for the Practicing Programmer.* IEEE Computer 11(4). The
  origin of mutation testing.
- Jia, Y., & Harman, M. (2011). *An Analysis and Survey of the Development of
  Mutation Testing.* IEEE Transactions on Software Engineering 37(5).
- Meszaros, G. (2007). *xUnit Test Patterns: Refactoring Test Code.*
  Addison-Wesley. Interacting Tests and Mystery Guest smells; test independence.
- Jones, N. (2026). *My honest field notes on the verification gap no
  one's talking about.* Nate's Newsletter.
  https://natesnewsletter.substack.com/p/my-honest-field-notes-on-the-verification
- Mutation tooling referenced for comparison: PIT (JVM), `mutmut` and
  `cosmic-ray` (Python), Stryker (JavaScript).
- NIST SP 800-171 Rev. 2 / 800-171A — assessment requirements and objectives.
- 32 CFR Part 170 — CMMC Program; §170.21 SPRS scoring methodology.
- SQLite documentation — `CHECK` constraint evaluation and NULL semantics;
  the recommended procedure for altering a table.

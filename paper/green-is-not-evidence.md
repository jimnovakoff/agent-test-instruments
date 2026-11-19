# Green Is Not Evidence: Who Is Testing the Tests?

**A field report: what a passing 480-test suite was hiding, and the four
checks that found it**

*Systems studied: a pair of CMMC Level 2 assessment tools and their guarded chatbot*

*James Novakoff, CMMCSecureCloud LLC, v2.5, 2026-11-19*

---

## Abstract

A test run tells you two things: which tests exist, and whether they pass. It
does not tell you whether those tests would fail if the code broke. Most teams
assume they would.

A test that checks nothing stays green forever, and nothing will ever tell
you. That is true whether or not the system has an AI model in it. A model
makes some tests flicker between runs, which exposes unstable tests. It does
not expose a test that cannot fail.

This report asks whether an assessment tool built with the tools now
available, language models included, can be trusted, and what it takes to find
out. It covers four checks I built while hardening a CMMC Level 2
assessment tool. The tool scores a defense contractor's Salesforce org against
the 110 NIST SP 800-171 controls and keeps the crosswalk an assessment depends
on. If it is wrong, a wrong score can end up in a federal database under an
executive's signature.

The four checks answer four questions about a test suite:

1. **Where are there no tests at all?** A coverage map borrowed from the
   CheckList paper (Ribeiro et al., 2020), with one extra column this domain
   needed.
2. **Does each test pass on its own,** or only when the tests before it ran
   first?
3. **Does each test fail when the thing it guards breaks?** (Mutation testing.)
4. **Does each test read the thing its name says it checks,** or a copy of it?

I ran them against 480 tests that all passed. They found fifteen defects: nine
in the product and six in the tests themselves. Several had been there since
the first commit.

One fact matters throughout. The tool has only been used to prepare for
assessments, never to conduct one. Every claim it helped produce was either
checked by me or would be re-examined by an outside assessor who does not use
this tool. No client filed a score based on numbers the tool generated. The
defects that touched the tool's own records (audit rows,
attribution, imported notes) never left it. So these defects were found before
they could reach anyone, though not because my own review would have caught
them: §8.1 shows where it did not.

I also ran the same four checks against a third system: our public chatbot, a
language model behind a large system prompt, with 126 test cases. They showed
that the tests were measuring how the model phrased its refusals, not whether
it refused. They also found one real guardrail defect, and a check that had
been dead for four months while still reporting itself as blocking (§7.3).

The report ends with a record of my own confidence estimates, written down at
four points during the first session. Three parts of the system that I had
scored between 80 and 92 turned out to be broken, and each was a part no check
had touched. On parts that had been checked, later checks found nothing new.
That gap is the argument for running checks instead of trusting judgment.

The common thread: every test suite has two sizes. One is the number of tests.
The other is how much real, independent evidence those tests give you. Every
defect in this report is a way the first number overstates the second without
showing it. Fixing what the checks found grew the suite from 480 tests to 644,
almost all aimed at holes I could not see from the inside.

**This is a field report, not a new method.** Three of the four checks are
established practice that I rediscovered under pressure. §1.1 says which ones
and credits the original work. What this report adds is the measurement: what a
real, five-month-old, single-author test suite turned out to contain, in a
field where being wrong
means a false statement to the federal government. If you are looking for a
new technique, this is not it.

---

## 1. What 480 green tests tell you

The suite had 480 tests, all passing, built up over five months of work on a
live compliance product. It had caught real bugs before. The tests were grouped
into categories (schema, columns, round-trip, triggers, export, command line),
each with its own `make` target.

Most of the code in these systems, tests included, was written by an AI
assistant (Claude), under my direction and review. That is the situation this report is about. When
one author writes a function and its test in the same sitting, nothing
independent has checked the pair, and a test that compares fixed text with
itself (§5) is what that looks like. So trust cannot come from who wrote the
code, or from a passing run. It has to come from checks that work the same
whoever the author was: break the code, and see whether the test fails.

The tests added after the checks found gaps were written the same way, so the
same rule applies to them. A new test counts as evidence only once a
deliberate break makes it fail, and the committed mutants cover a fraction of
the new tests (§10).

By every visible sign, it was a healthy suite.

The categories were the first problem. They describe where the code lives, not
what the system is supposed to do. Grouped that way, a behavior with no test
leaves no visible gap: every category has some tests, so nothing ever looks
empty.

That is what sent me to CheckList, which groups tests by what they check
instead.

### 1.1 What is not new here

Three of the four checks are established practice. I arrived at each one by
hitting the problem it solves, not by reading about it first, and it is more
honest to say so up front.

- **Mutation testing (§5) dates from 1978** (DeMillo, Lipton and Sayward). Its
  core idea is the one this report relies on: a passing test proves nothing
  until you show it fails when the code breaks. Mature tools exist (PIT for
  Java, `mutmut` and `cosmic-ray` for Python, Stryker for JavaScript). I wrote
  a fifty-line version instead, with hand-picked mutants. That has a cost.
  Mature tools already separate a mutant that no test runs from one that tests
  run and miss (PIT reports them as NO_COVERAGE and SURVIVED), and a small
  tool has to rebuild that distinction. §5.1 is the account of rebuilding it.
- **A test that cannot fail (§5) has a name too.** Niedermayr and colleagues
  (2016) call a method whose body can be removed without failing any test
  *pseudo-tested*, and Vera-Pérez and colleagues (2019) measured how common
  that is in open-source projects.
- **Tests that check a relationship instead of an answer (§3.1)** are
  metamorphic testing (Chen, Cheung and Yiu, 1998) and property-based testing
  (Claessen and Hughes, 2000). CheckList's INV and DIR types are the same idea
  applied to language models.
- **Test independence (§4) is standard advice.** "Tests should not depend on
  run order" is in Meszaros's *xUnit Test Patterns*, most test runners can
  shuffle tests to enforce it, and Zhang and colleagues (2014) measured how
  often real suites break the assumption. What I add is a ratchet and a number.
- **Checking against the real source (§6) is a known problem.** It is a case of
  what the same book calls the Mystery Guest: a test whose result depends on a
  file the reader cannot see. What I add is that the hidden file is often a
  copy of the real source, which makes the problem much harder to spot. A test
  reading a cached database is reading the right data, until the day the cache
  goes stale.

What is new is modest:

- **The DRIFT column (§3.2).** One fact often lives in several places (a
  database, an export, a document). A DRIFT test checks each copy against the
  single source of truth. CheckList's three test types assume one input and one
  output, so they cannot catch this, and in a compliance system it is the most
  common kind of error.
- **The confidence record (§8).** Every part I scored highly that later proved
  broken was a part no check had touched. With one author, that is an
  observation, not a proven result.
- **The main point (§11).** Nothing will ever tell you a test is dead: not a
  passing run, and not a model's flicker. So instead of assuming your tests
  might be weak, you need a standing check that proves they are not.

---

## 2. Step zero: make the risky part smaller

The cheapest test is the one you never have to write. Before sorting tests into
types, ask of every rule the system enforces: *can this be written down as a
fixed rule?* If it can, take it away from the model entirely. Put it in a
table, a database constraint, a trigger or a small rule language, and test it
like any other code.

In this tool that meant `control_check_spec`, a database table of mechanical
checks. Each row names a field, an operator, a threshold and the control it
supports, and a scanner evaluates the rows against settings pulled from
Salesforce. "Session timeout must be 15 minutes or less" is not a judgment call
a model should make fresh on every engagement. It is a row. The model's
judgment is kept for the work that really needs it, such as reading an unusual
org configuration or drafting the wording of a finding, and the rows are tested
with exact assertions.

Hosted agent platforms have landed on the same idea. Salesforce's Agent Script,
a fixed-rule guardrail language for Agentforce, exists so that business rules
follow code instead of model reasoning. Whatever the mechanism, the principle
holds: **keep the part of the product that depends on a model's judgment as
small as the product can tolerate.**

There is a catch, and most of this report is about it. Every rule you move into
fixed code becomes a rule whose failure is silent. You have traded a noisy kind
of failure for a quiet one, and the four checks below are the price of that
trade.

---

## 3. Check 1: where are there no tests at all?

CheckList proposes a grid. Each row is something the system should be able to
do, each column is a type of test, and each cell holds however many tests
cover that pairing. The empty cells are the result. CheckList has three test
types:

- **MFT** (minimum functionality): give an input and its expected output. You
  have to know the right answer.
- **INV** (invariance): change the input in a way that cannot change the right
  answer, and check that the output stays the same.
- **DIR** (directional): change the input in a way that must move the answer
  in a known direction, and check that it moves that way.

### 3.1 The test types are about the cost of answers, not about AI

The usual reason for skipping CheckList on ordinary code is that it was
designed for machine-learning models. That misreads it.

The three types differ in **what you can check**, not in whether the system is
predictable. MFT needs you to know the right answer. INV and DIR only need a
relationship between two runs. Ribeiro and colleagues used INV and DIR because,
for a language model, the right answer is expensive to get and often not
clear-cut.

That problem is really about how many answers you need, and it shows up at
scale whether or not a model is involved. I knew every right answer in this
system and still could not afford to write them all down. Writing expected
values by hand for 110 controls across 6 columns is 660 chances to make a typo
in a fixture. Instead, the directional scoring test generates 220 checks from a
rule, and the export test generates 660. The cost problem is the same as in the
CheckList paper; only the cause is different. On ordinary code this is not a
new idea (§1.1): it is metamorphic and property-based testing under CheckList's
names.

### 3.2 A fourth column this domain needed

The three types assume one input and one output. Compliance data fails in a
different way: **one fact kept in many places.**

The SPRS point values (how many points each of the 110 controls is worth) were
stored in eight places: a seed script, the schema bootstrap, the live database,
a generated reference page, a test fixture, two skill documents and a chatbot
system prompt. The copies drifted apart. Nobody noticed for three and a half
months, and during that time five of the eight copies would have given a
confident, wrong answer.

No MFT, INV or DIR test catches that, because no single input and output is
wrong. So the grid got a fourth column:

- **DRIFT** (one fact, many copies): check each copy against the one source of
  truth, and name both sides in the failure message.

Where a copy can be generated from the source, generate it and the problem
goes away. A DRIFT test is for the copies that have to exist.

### 3.3 What the count showed

Sort every test into a column, count each column, and print the grid with the
zeros showing:

```
  test type   count    share
  MFT           461    92.0%
  INV            33     6.6%
  DIR             2     0.4%
  DRIFT           5     1.0%
```

(The total is more than 480 because the count covers every test the runner
collects, and the suite had already grown past 480 by the time I first ran
it. The count is a snapshot of that moment, not of the starting figure.)

Two things limit what this table shows. It is the grid's column totals only: I
have not built the rows, the list of things the system should do, so it shows
which kinds of test are missing, not which behaviors. And a test is sorted by a
prefix in its name, with MFT as the default, so the MFT figure means "not
labeled as anything else."

Two directional tests, in a system whose whole job is to compute a number that
moves. The suite could prove the score was 110 when everything passed and −203
when everything failed. It had almost nothing to say about any state in
between, or about which way a fix moved the score.

Also note that I wrote no new tests to produce this table. The INV column
already had 33 tests (repeat-run checks, round trips, dry-run checks), written
without anyone using the word "invariance." The count adds no coverage.
What it does is make the existing coverage visible, and the lack of visibility
was the only reason nobody had noticed that DIR was nearly empty.

---

## 4. Check 2: does each test pass on its own?

Run every test by itself in a fresh process. Any test that fails alone depends
on the tests that ran before it.

In this suite, **20 of 105** tests in one file failed when run alone. The
coupling was inside each test class. The classes modeled a lifecycle (plan,
dry run, execute, verify, skip, reset), and each test checked one step while
relying on the state the previous test had left behind.

Wanting to test a lifecycle is reasonable. Doing it this way is not. The costs:

- `pytest --lf`, the first thing you run when something breaks, reports a
  false failure.
- One real bug in an early test spreads to every test that relied on its state,
  so one bug looks like eleven.
- Anything that runs the tests in a different order or a different subset (a
  run by test type, a `-k` filter, a future parallel runner) breaks.
- Twenty tests with twenty names give you fewer than twenty independent
  checks. The test count overstates the evidence, and a passing run does not
  show by how much.

The fix is to give each test its own setup through helpers that can safely run
more than once, not to merge the tests. Collapsing twelve tests into one big
lifecycle test removes the coupling by removing the tests, and makes it harder
to see what failed.

One detail is easy to get wrong: **the setup must create the state the test
cares about, not just a row that exists.** A test checking that `reset` returns
an action to `planned` must first move it to `skipped`. Resetting an action
that is already planned passes and proves nothing. You have swapped an
order problem for a test that cannot fail.

---

## 5. Check 3: does each test fail when the thing it guards breaks?

Break the code on purpose. Confirm the test fails. Put the code back. This is
mutation testing, and each deliberate break is called a mutant.

None of the other three checks can stand in for this one, and it changed my
view of the suite more than any other. Running a test alone proves it *runs*
alone. It says nothing about whether the test *checks* anything. A test can run
on its own, sit in the right column of a well-filled grid, and still be dead.

In the first session I applied it only to the 20 tests I had just fixed under
check 2, not to the whole suite. **18 failed when their code was broken, and 2
did not:**

**A test that could not fail.** A test named
`test_verify_logs_gap_to_met_transition` checked that an audit row recorded
`old_status = 'Suspected Gap'` and `new_status = 'Met'`. The code under test
wrote those two values as fixed text:

```python
VALUES (?, ?, 'remediate.py', 'Suspected Gap', 'Met', NULL, ?, ?)
```

The test compared the fixed text with itself. It could not fail as long as that
line existed. It had passed since the first commit while proving nothing, and
it was hiding a real defect: the function never read the control's actual
status. A control that was already Met still got an audit row claiming it had
moved from a gap to Met. On a compliance record, that is a made-up entry, not
just an out-of-date one.

**A test that passed by accident.** A test named
`test_06_show_displays_detail` checked that the word `SecuritySettings`
appeared somewhere in a command's output. That word also appears in the field
name and in the template XML, so removing the line the test was named for left
it green. It could not tell whether the detail it existed to check was shown at
all.

### 5.1 How mutation testing misleads you

The tool will mislead you in one specific way: **a mutant placed in code the
test never runs looks exactly like a weak test.**

This happened four times in one session. A mutant in a seed script that the
bootstrap does not read. A mutant in an `UPDATE` branch when the test data
always took the `INSERT` branch. A mutant in a bootstrap file when the test
read a database that had already been migrated. Each produced a confident NOT
CAUGHT, and each time the tool was at fault, not the test.

The rule that fixes this: **when a mutant is not caught, first prove the
mutant did something.** Run the whole file and confirm that *some* test fails.
If none does, the mutant had no effect and you have learned nothing about the
test.

A day later, once the tool was a committed part of the repository (§10), that
rule turned out to be too strong. Twice in one session, a mutant that no test
in the whole file caught was neither harmless nor misplaced. It had changed
real, running code that **no test anywhere checked.** One was the importer's
`UPDATE` branch: every real re-import takes it, but every test imported into a
fresh database and took `INSERT`. The other was the scanner's comparisons at
exactly the benchmark value: an org set exactly to the recommended value, which
is what a correctly configured org has. Both mutants survived the entire suite.
Each became a new test the same day, and both mutants are now caught.

The better reading: NOT CAUGHT is a finding against the named tests. A mutant
that works but that nothing catches is a finding against the whole file's
coverage of that code. Work out which one you have before you dismiss the
result. The "had no effect" pile is where two of this system's coverage holes
turned up, and where the sibling system's biggest hole turned up on its first
run (§7.2): three cases across two repositories, all the same shape.

A second trap appeared only once the tool ran long enough to overlap other
work: **on a cloud-synced drive, reading a file while the tool is rewriting it
can return an old version.** A search during a live run found a version of a
styling function containing a backslash bug that existed in no commit and not
in the working copy, most likely an old synced copy. The phantom bug lasted
until I checked it against `git show HEAD`. The rule: while a mutation run is
going, treat every read of a mutated file as suspect, and confirm any finding
against what git has stored before acting on it.

A third trap appeared eleven weeks later, inside Python itself. Python reuses
its cached `.pyc` file when the source file's size and modification time (to
the whole second) match the cache. A mutant of the same length (`0.8` changed
to `0.0`, or two equal-length names swapped) written or restored within the
same second as the last compile therefore runs the *old* code. When the mutant
is the stale side, a real mutant reads as having no effect; one mutant flipped
between CAUGHT and no-effect across repeat runs. When the restore is the stale
side, the mutant outlives its own restore, and the next mutant's tests fail
before anything has been changed: two "failing at baseline" results on tests
that pass alone. The fix is small: every test run gets an empty bytecode cache.
The lesson is the one §9 draws, pointed back at the original tool: mutation
tooling is code, and it earns trust the same way. Only repeat runs exposed this
one.

---

## 6. Check 4: does each test read the thing its name says it checks?

The closest existing name for this check is the Mystery Guest (§1.1). It found
five defects in a single session. As a rule:

> **Check the source itself, not a copy made from it.**

Five cases, all the same shape:

| The test claimed to check | It actually read | What that meant |
|---|---|---|
| the schema bootstrap every client database is built from | a cached local database | a wrong point value in the bootstrap passed until someone cleared their cache |
| the bootstrap's default for an audit column | a schema that had already been migrated | undoing the change in the source left the test green |
| the production schema | a test schema quietly built with 0 of its 9 triggers | no trigger behavior could be tested in 107 tests |
| that a sibling repository matched | its own repository only | the same bug was fixed in one repository and left in the other, twice |
| whether a constraint enforced its allowed values | whether the constraint *existed* | five constraints enforced nothing |

The last one deserves its own note, because the cause is a quirk of the
language rather than carelessness:

```sql
sqlite> SELECT 'Yes' IN ('Y','N','N/A',NULL);   -- NULL, not 0
```

A plain `NULL` in an `IN` list makes every comparison that does not match come
out as NULL instead of false, and SQLite treats a `CHECK` that comes out NULL
as **passed**. Five columns across four tables claimed a fixed list of allowed
values and enforced none of it. The column recording whether a policy had been
verified accepted the value `'banana'`.

A test that only looks at the schema would not catch this, because the
constraint was there and spelled correctly. Only a test that tries something
invalid and requires it to be rejected can tell a working constraint from a
decorative one.

When the constraint was finally made to work, it caught seven test fixtures
that had been writing `gap_risk = 'HIGH'`, in uppercase. The schema had always
said that value was illegal, and the broken constraint had always let it
through. Every test that reasoned about that column had been using a value the
production trigger never produces.

---

## 7. What the checks found

These results are here as evidence that the checks work, not as the point of
the report. Fifteen defects turned up in one session, against a suite that
passed:

**In the product**

| Defect | Effect |
|---|---|
| A function that was written and documented as part of the pipeline but never called | A new client's baseline set 2 controls instead of 48, **understating the score by 150 SPRS points** |
| Wiring that function in without a guard | Would have overwritten **51 of 110** assessor decisions, flipping documented gaps to Met, the direction that *inflates* the score |
| Audit records defaulting to one person's username | Every change with no named author was credited to a specific person who may not have made it |
| The same defect in a sibling repository | Including a change note that named a migration from the *other* product, copied over and never noticed |
| Verification writing audit entries as fixed text | The audit trail could record a change that never happened |
| The import never reading one editable column | The assessor's entry was silently thrown away on every round trip |
| The import using `INSERT OR REPLACE` | Re-importing a **freshly exported** workbook wiped out the agent's entire evidence trail |
| Personal-username defaults on four more columns | Copied into every client database |
| Five `CHECK` constraints that did nothing | Allowed-value lists that enforced nothing |

**In the tests themselves**

| Defect | Effect |
|---|---|
| 20 of 105 tests depending on run order | 20 tests in one file (about 4% of the suite) could not stand as independent evidence |
| A test setup building a schema with 0 of 9 triggers | A whole category of behavior could not fail any test |
| Canon tests reading a cached database | The most important check in the repository was reading the wrong thing |
| One test that could not fail | Compared fixed text with itself since the first commit |
| One test that passed by accident | Passed on a word that appears elsewhere in the output |
| Seven fixtures writing an illegal value | Tests reasoned about a value production never produces |

Six of the fifteen defects were in the tests themselves. The exact ratio
depends on how you count: five broken constraints are one row here, and the
unguarded wiring is a harm that was caught before it happened. The point holds
under any counting. A suite with defects in its own tests cannot tell you how
good anything else is until the checks have run.

This table keeps measuring one thing, and it is worth naming. A test suite has
two sizes. One is the **number of tests**, the figure every dashboard shows.
The other is **how much real, independent evidence** those tests give you.
Every kind of defect above is a way the first number overstates the second:
twenty dependent fragments sharing a few pieces of evidence among twenty names;
a test that cannot fail adding nothing; tests that check a copy instead of the
thing they are named for. And none of it shows in a passing run, because
overstating never fails.

Each of the four checks is cheap. Together they are the only way I have found
to measure the second number. The coverage map shows where evidence could
exist. The isolation check counts how many names share one piece of it.
Mutation testing checks whether a claimed piece of evidence exists at all. The
source check confirms what the evidence is actually about. Measured that way,
this carefully built suite carried less evidence than its count suggested, and
nothing short of the checks could have shown it. The suite grew by a third as
a result. That growth is a count of tests too, so it shows where the work went,
not the size of the gap.

Before and after:

| Measure | Start | End |
|---|---|---|
| Tests passing (main system) | 480 | 644 |
| Count by type: MFT | 461 | 537 |
| Count by type: INV | 33 | 38 |
| Count by type: DIR | 2 | 29 |
| Count by type: DRIFT | 5 | 34 |
| Tests depending on run order | 20 (in one 105-test file) | 0, held at zero (`--max 0`), run on demand |
| Committed mutants, confirmed caught | 0 | 24 |
| Tests known to check a copy instead of the source | 5 (found by check 4) | 0 known |
| Sibling system: tests / mutants | 207 / 0 | 254 / 19 |
| My stated confidence | 70 | 88, for the checked parts only |

(The counts by type cover every test the runner collected at the time: 501 at
the first count, 638 at the last. The headline counts are passing tests in CI,
so the two numbers differ slightly by design. The DIR and DRIFT rows are the
whole story in small: the two test types nobody had a name for
grew fourteen-fold and seven-fold once the count made their absence visible.
The mutant row is a regression set, not a score: each mutant that survived
became a test before it was committed, so "all caught" is true by
construction. §7.5 gives the score a random sample produced.)

### 7.1 The next day's results

The checks ran again one day later, now as committed tools, against parts of
the system the first session had not touched. Every newly checked part turned
up something:

| Found by | Defect | Effect |
|---|---|---|
| the first committed mutation run | no test anywhere checked the values written by the importer's `UPDATE` branch | a swap of two values (notes and artifact type traded places on every re-import) survived the whole suite |
| a sample of mutants | no comparison was ever tested at exactly the benchmark value | an org set exactly to the recommended value (a 15-minute session timeout) could show as a gap, and nobody would see it |
| check 4, on tag colors | tag colors were kept by hand in two more places than anyone thought, and both had drifted from the master table | the Unassessed font differed from the master in both copies; three tag types had no formatting rule at all, so choosing `[N/A — Assessed]` from the dropdown showed no color |
| check 4, on the command-line write path | `cw.py set` checked tags against a hand-kept list | five of thirteen valid decisions were refused at the command line |
| the side effects of that fix | a second test setup copied the schema but not the master tag table | once the check read the real table, every decision written in that setup was silently refused; the hand-kept list had been hiding an empty table since the setup was written |

The suite grew by twenty tests. Compared with the first count (§3.3), DIR went
from 2 to 13 and DRIFT from 5 to 20. By the end of that session, ten mutants
were committed with the tests and run as `make test-mutation`, and all ten were
caught. The set has kept growing since (§10 has the current count).

### 7.2 The second system

Everything so far is one codebase. Its sibling is an AWS assessment tool. It
shares the same 110-control reference data, scoring math and deliverable
format, but it has its own test suite (207 tests, five months of history) and
its own export, adapter and command-line code. None of the checks had ever run
against it.

Bringing the tools over took an afternoon. The mutation tool is now the same
file, byte for byte, in both repositories, and a DRIFT test keeps the two
copies identical, so the tool itself is guarded the same way the reference data
is. Only the mutant sets differ, because the defects worth simulating depend on
the platform.

The first mutation run on that suite repeated the first system's findings
almost exactly:

| Found by | Defect | Effect |
|---|---|---|
| the first mutation run (5 of 6 caught) | swapping two columns in the export query survived the **entire** 207-test suite | the export tests checked headers, sheet counts and one tag cell, so every value in the workbook could be present and wrong; this was the "had no effect" pile again, just as §5.1 describes |
| bringing over the agreement checks | nothing guarded the gaps sheet's deliberate rule (assessor gaps **or** controls the agent flagged) | dropping one `OR` would quietly remove scanner disagreements from the most-read sheet while every other number stayed right; that is now a caught mutant |
| bringing over the round-trip checks | the two command-line tools disagree on what leaving notes out means (one keeps the existing text, one overwrites it) | not a defect, but an undocumented difference between the two tools; now fixed as intended behavior by a test on each side |

The pattern repeated too, which matters more than the count. On both systems,
the code that carried the values turned out to be **correct once it was
checked.** The swapped-column mutant was caught as soon as a round-trip test
existed. The export, adapter and command-line code carried what it was given.
What the checks found on both systems was *coverage that could not have noticed
a problem*, plus drift between hand-kept copies of the master data. Two
systems is still not many. But a second, separate suite showing the same kinds
of failure under the same checks is the difference between an anecdote and a
pattern.

At the end of that session the second system had 218 tests passing, nine
committed mutants, all caught, and `make test-mutation` in both repositories.
(Both suites and both mutant sets have grown since; §10 has the current
counts.)

### 7.3 The third system: one with a model in it

The first two systems are predictable. The third is not. It is our public
chatbot: a hosted service wrapping a large language model behind a system
prompt of about 21,000 tokens. It is guarded by a 126-case suite that sorts
responses using fixed text checks (contains one of these words, does not
contain this, does not repeat that). This is the area §10 used to list as
unmeasured.

The checks ran in two rounds. The free round came first: the coverage map, the
isolation review and the source check, with no model calls at all. The paid
round came second: a full baseline run plus one cycle of fixing and verifying,
about three hundred model calls in total, costing single-digit dollars.

The free round found problems before a single model call:

| Check | Finding | Effect |
|---|---|---|
| source check | the blocking prompt-drift check had pointed at a folder that stopped existing when the repository moved four months earlier | the check skipped itself on every run while still calling itself blocking; the hidden-file problem again. Once fixed, it confirmed no drift had built up while it was down |
| coverage map | MFT 124 / INV 0 / DIR 0 / DRIFT 0 | the empty columns were not tests nobody had written. The format **could not express them**: single-message cases with fixed text checks cannot state a relationship between two responses |
| coverage map | 2 of the "126 cases" can never run | the runner cannot handle multi-message conversations and silently skips them, so the count overstates the evidence |
| isolation review | a full run needs a fresh session for every case, but production limits sessions to a level sized for human visitors, not test runs | the tests cannot run against the production settings as configured. Reading the code alone would never show this (and the limit throttled the first verification attempt) |

The paid round then measured what the suite was really measuring. On the
newly migrated model, the baseline was 106 of 124 passing. Re-running the
failures and reading the responses showed that about fourteen of the failures
were the *suite's* fault, in two ways:

- **Banned-phrase checks fired on correct refusals that name what they refuse.**
  A ban on mentioning the system prompt was tripped by "I won't share my system
  prompt." A ban on a phrase about unauthorized use was tripped by the refusal
  denying that very use.
- **Required-word lists were too narrow for a model that paraphrases.** Correct
  answers used words nobody had listed.

A newer model with a more explicit refusal style triggered both problems at
scale. The suite was measuring how the model phrased its refusals, not whether
it refused.

The rest was real: one defect, appearing twice, of a kind worth naming. **A
response template and a rule that contradict each other.** The prompt's
response format said to always offer the booking link, while a separate rule
banned the link on questions about legal liability. The model sided with the
template, every time for one phrasing (3 of 3 runs) and sometimes for a
paraphrase of it. Later the same kind of defect appeared again. A product
section relied on the *wording* of a suggested template to present something
as an option rather than a requirement, and the model paraphrased the template
away, sometimes losing the point along with the words. Both were fixed by
making the rule say what must be true rather than how to phrase it, and both
passed repeated runs afterward.

Two extras came for free. The suite's first measured INV failure (four
paraphrases of the same legal question scoring PASS, FAIL, FAIL, PASS) was
worked out offline from the baseline's saved responses at no extra cost, and
the four agreed after the fix. And rewriting the checks taught the same lesson
twice in one day. My first rewritten ban for one case still included a phrase
that the *correct denial* itself uses: the refusal names the very permission it
is denying, so the ban fires on the right answer. Text checks cannot tell "I
will" from "I won't." The rule that held up: **a banned phrase must be one no
correct refusal would contain.** Either tie it to an agreement ("Yes, I
can…"), or use an exact string that would only appear if private content
leaked.

Three habits had no counterpart on predictable code:

1. **Stability is part of the result.** Re-run a failure before believing it.
   One "regression" passed on its second run, and one false failure moved to a
   different case between runs.
2. **Text checks on a paraphrasing model always flicker a little.** One missed
   word somewhere in each full run is *expected*. Budget for it and re-check it
   rather than chasing it.
3. **The fix itself must be re-run more than once,** because one pass from a
   model is one sample.

At the end, every case passed on its latest run and the guardrail defect was
fixed in the prompt. One honest caveat stands: the lasting fix for the
false-failure problem is checks that compare pairs of responses (INV), or a
model acting as judge, not longer word lists.

### 7.4 An outside checklist, used as a probe

Two days after v2.2, I used a practitioner session (ten agent-architecture
decisions, presented by two Salesforce Certified Technical Architects) the way
§3 uses CheckList: as an outside list of things a suite should be able to say
something about, held up against what the main suite actually contains.

Two of the ten are about the org an agent runs in rather than the agent, so I
set them aside. Of the eight that apply:

- **Five were already covered:** settings treated as instructions, scale,
  checking outcomes rather than steps, tracing (the attribution and source
  checks of §6), and safe retries. The last turned out to be the INV column's
  repeat-run checks under a name nobody had connected to it.
- **Two were partly covered:** least privilege and control over which tools
  the agent can use.
- **One had no test at all:** a fallback for every step that can fail.

The scanner pulls data from the org in three ways, and each can fail in three
ways: a timeout, an error exit, or output that cannot be read. None of those
failures was tested. Writing the tests was quick (fifteen DIR tests). What
mattered was what writing them showed.

Two of the three fetch paths turn a failed fetch into a missing value and then
evaluate it, and the comparison function treats a missing value as compliant
for three operators (`absent`, `ne` and `not_in_set`). That is correct when a
field genuinely does not exist in the org's settings. On a network fetch, it
means a check written with any of those operators would turn a timeout into a
pass: a silent false Met, the worst thing this system can output. No current
check uses those operators on a network fetch, so the risk is waiting rather
than live. The new test is therefore a guard on the check table, not a fix: it
fails the day someone adds such a check.

The same pass found a DRIFT case outside the code. The scenario document the
agent is tested against had its mock data moved to the DoD ODP values in
April, but the clean-org scenario's expected findings still had the old
numbers: a 14-character password, three attempts and thirty minutes. Against
that table, a correct agent fails the false-positive test. A person grades the
scenarios by reading the table, so nothing flagged it for seven months. That
is §6's lesson in a written document: an expected answer is a copy too, and it
needs a source of truth like any other.

After the pass: DIR went from 29 to 44, and the collected test count from 638
to 653.

---

### 7.5 A random sample of mutants

Every mutant up to this point was one I chose. §10 of earlier versions named
the number that was missing: a score from mutants nobody chose. This is that
number for the main system.

A small sampler (`python/mutation_sample.py`) lists every change a fixed set
of operators can make to the product's Python files: a comparison flipped,
`and` swapped for `or`, a number raised by one, and so on. There were 3,424
possible mutants across 26 files. It drew 100 with a recorded seed and ran the
full suite against each.

| | Hand-picked set | Random sample |
|---|---|---|
| Mutants | 24 | 100 |
| Caught | 24 | 29 |
| Score | "all caught", by construction | 29% (95% interval 21% to 39%) |

The same suite, on the same day, reads 24 of 24 on the mutants I chose and 29
of 100 on mutants drawn at random.

I sorted the 71 survivors by reading the line each one changed. That is a
first pass, not a finding for each:

- **About 25 change formatting or a printed count.** Column widths, row
  heights, a tally in a summary line. No test should care.
- **About 19 change one value in a table of reference data.** A test that
  repeated the table back to itself would catch them and prove nothing. They
  need an outside source to check against, which is check 4's problem (§6).
- **2 sit on branches no data can reach.** The code handles a combination of
  point value and plan eligibility that the control list does not contain.
- **14 were real gaps.** They are described below.
- **About 11 are not yet judged.**

The real gaps were not spread evenly. Four were in one function: the routine
that validates an exported workbook, which no test had ever called. Its
neighbours were tested, and the function ran in normal use, so nothing about
the suite suggested a hole. One was a guard that stops a dry run from writing
plans. It had a test, and the test could not fail: the control it used already
had a plan from the test before it, so "nothing was created" was true whether
the guard worked or not. One let a report with exactly one error print PASS.

I added 28 tests and repaired the one that could not fail. Re-applying all 71
survivors, the new tests kill those 14, and the same sample now reads 43 of
100. That is not a new score. The tests were written against these mutants, so
the next honest number needs a different seed.

Three limits apply to the 29%. The sampler changes Python code only, and it
leaves text inside strings alone, so the SQL and XML this system carries in
strings are outside the sample. No coverage data was collected, so the
survivors are not split into lines no test ran and lines tests ran and missed.
And it is one draw of 100 from one system.

## 8. How sure I was, and how wrong

During the first session I wrote down my confidence as a number at four
points. On this scale, 100 means no chance of error.

| When | Number | What changed |
|---|---|---|
| Before any check ran | **70** | Broken into six parts, each scored by reading the code |
| After the coverage map, isolation and directional tests | **84** | Several parts I had scored at 88 to 90 turned out to be broken |
| After narrowing the question to *"does the code faithfully carry the assessor's judgment?"* | **80** | All the weight moved onto a part I had scored generously |
| After the round-trip tests and fixing the constraints | **88** | The weak part was weaker than I had scored it, then fixed |

Four numbers from one person are anecdotes, not a calibration study, and the
scale has no ground truth to subtract from. What they show is a pattern in
where the errors were. On parts that had been checked, later checks found
nothing new. Every large correction came from a part that had not. I scored
the point values at 90 while the tests guarding them were reading a cached
database. I scored storage integrity at 92 while five of its constraints
enforced nothing. I scored data capture at 80 while the import was silently
deleting data.

These were not lazy estimates. Each one was broken into named parts with
stated evidence. The breakdown was the problem: it made the estimate *feel*
grounded when every input was an untested assumption about code that looked
right.

**The practical rule: treat any confidence number for a part nobody has
checked as unknown, not as an estimate.** The checks are not a way to raise the
number. They are the only thing that makes the number mean anything.

A fifth data point came in the next session (§7.1). The parts checked for the
first time (the workbook's summary sheets, its tag colors, the command-line
write path and the importer's second branch) each turned up defects. The parts
checked the day before turned up nothing new. The 88 covers what has been
checked. It says nothing about what has not.

A later point fits the same rule from another angle. The assessment-objective
data (the 320 determination statements in NIST SP 800-171A) had been recorded
as verified against the NIST text. A fresh extraction, compared row by row,
found 13 objectives across 9 controls that had been paraphrased, two of them
in ways that changed the meaning. One dropped "response actions to." Another
said "periodic scans of organizational systems" where NIST says "malicious
code scans." "Verified" was a label on something nobody had checked, and it
carried the same optimism as an unchecked confidence number.

One later first-time check is worth recording because it found nothing: the
workbook's remaining export areas, checked for the first time, matched their
sources. That is the record's first clean first-time check, and it shows how
to read the rule. The rule does not say unchecked parts are broken, so it
cannot be tested by counting defects. It says what an unchecked number is
worth: until the check runs, you cannot tell a healthy part from a broken one.

The second system (§7.2) gave the record its first point from another system.
Its suite showed every sign of health the first one had, and before its first
mutation run any number I gave it would have been a guess dressed up as an
estimate. The run immediately showed that its tests could not see whether any
workbook value was right, something no amount of reading had suggested. So I
gave its first number, 85, only *after* the checks ran, and raised it to 88
only once the agreement and round-trip tests were in. The number followed the
checks instead of coming before them, which is the habit this section argues
for.

### 8.1 A fifth check, for the reviewer

These tools prepare for an assessment; they do not conduct one. A person
reviews what they produce, and an outside assessor who does not use the tool
re-examines every claim afterward. No client has filed a score based on
numbers the tool generated. The outside assessment is the independent check. My own review is the weaker one, and it splits in two.

**On consistency errors** (losing focus at scale, numbers copied by hand,
out-of-date references, arithmetic), a check does better than a person
reading, and this report's own history shows it. The three-and-a-half-month
point-value drift happened in the *manual* workflow's reference tables. I did
not catch it, and the checks caught it in one run.

**On judgment errors,** the tool adds nothing directly. What it changes is the
conditions the judge works under: no zero-point claim without a recorded
reason, no Met without the right kind of evidence, no signed score over an
unfinished assessment, and every scanner disagreement shown instead of buried.
That last condition is now built into the design, not just a procedure: the
scan writes only to its own columns, so it can report a disagreement to the
assessor but cannot act on it.

The part still unmeasured is the review itself, and the way it fails is
complacency: a reviewer who stops overriding the tool. A review that never
rejects anything is a dead test, the same problem this report opened with,
always green and quietly meaningless. That means the review can be checked the
same way:

- **Track the override rate.** An engagement with zero overrides is a warning
  sign about the review, not a compliment to the tool.
- **Mutation-test the reviewer.** Every so often, slip a known-wrong decision
  into a review batch and require that it be caught. This is the human version
  of `make test-mutation`. Airport baggage screening does the same thing when
  it projects images of threats into an operator's feed.

Neither has been run yet (§10). Until they are, the quality of my review is
unknown, by the same rule as any other unchecked part. The fifth check is for
the person in the loop.

Two limits stay fixed and should be said plainly. The tool's ceiling is the
reviewer at their best, every time, on every control. It cannot do better than
the judgment it is measured against; it can only stop that judgment slipping.
And no check can create *independence*, which is what an outside assessment adds
over any self-assessment, however well checked.

---

## 9. Bringing the checks to a hosted agent platform

§7.3 measured a model-based system that I host. This section measures the
other kind, where the test runner, the model and the deployment pipeline all
sit behind a vendor's API. The case is Agentforce, on a free Developer Edition
org: a made-up retailer with three topics and three guardrail rules, each
written so it could be removed on its own (a ban on quoting prices, a refusal
to give legal advice, and a required wording for delivery estimates). The
suite has ten cases: two guarding each rule, one case showing allowed
behavior, and three checks on fixed facts. The findings, in the order the
checks produced them:

**Mutation testing works here, and the §5.1 trap is worse.** The first mutant
(delete the estimate-wording rule) survived the full suite twice and had never
actually been applied. Deploying the changed topic reports success and changes
nothing in the running agent. This is probably the versioning model working as
designed (an active agent behaves as a frozen snapshot, and the compiled
planner can only be deployed to a deactivated agent), but nothing at deploy
time tells you so. What separated "survived" from "never reached the agent"
was a canary: change a fixed fact the suite checks, and confirm that its case
flips. On a deployment pipeline you cannot see into, the canary has to pass
before any result means anything.

**The three mutants gave three different kinds of result.**

- **Redundant with the model.** Once the estimate-wording mutant was actually
  applied, it survived. The careful wording visibly disappeared and the model
  acting as judge passed the responses anyway.
- **Reliably guarded.** The price mutant was caught: without the rule, the
  model worked out the bulk total the rule forbids. But its paraphrase twin
  passed, because the model declines that phrasing on its own. One case guards
  the rule; its twin adds nothing.
- **Cannot be guarded as written.** The legal-advice mutant took effect but was
  not detected. The model refuses legal questions without being told to, so
  what the rule really does is turn a sometimes-refusal into an always-refusal.
  Detecting its removal needs a question the model would not refuse on its own.

A green suite shows all three the same way.

**Even CAUGHT is a sample.** Across six runs, the price mutant's guarding case
caught it four times, and once failed on the intact rule. A guarding case does
not detect a mutant; it detects it with some probability, and it can be wrong
in both directions. So the committed tool records an expected *set* of results
for each mutant (CAUGHT or INTERMITTENT can both be the honest expectation)
instead of rounding a spread of outcomes to yes or no. (Apart from
that six-run count, every stability claim in this section rests on runs done
twice, n=2 per result.) A later re-run of the committed tool, two runs per
mutant, gave the same three results. The price case caught its mutant both
times, and failed once more with its rule intact, while a different rule was
the one removed.

**The defects were in the checking, not in the values.** The judge failed in
both directions. It passed responses that broke the rule, and it failed a
response that followed it. It explained that the response "uses 'typically'
instead of the required 'estimated'" while the response in the same result
record said "an estimated 5 to 7 business days." From outside, I cannot tell
whether the judge made that up or the pipeline fed it something other than the
response shown. Either way, the verdict was cut off from the thing it claimed
to judge, and the judge is an unversioned dependency besides. With fixed text
checks not working in my setup, this route offered no reliable way to check
for a specific word.

A follow-up test narrowed that gap. The newer Studio runner (`agent test
run-eval`, in beta) turns the same custom check into a working fixed text
check: it sees the true response text, gives a clean baseline, and caught the
estimate-wording mutant three times out of three while the judge missed it in
the same runs. So the capability exists one runner over, with two caveats. It
can only be reached by translating the old test-spec format (the new scorer
list has no fixed text check of its own). And a fixed check does not make
detection certain: the second guarding case caught the mutant two times out of
three, because without the rule the model sometimes uses the word anyway.

**The source check and routing checks work here unchanged.** At first the
results pipeline reported each topic under a different form of its name than
the deployed settings use, and every topic check failed until the topics were
renamed. Confirm what the pipeline actually reports before trusting any check
built on it. And a guardrail attached to a topic only guards questions the
router sends to that topic. One guarding case was answered by a built-in topic
and never reached its rule. One borderline question was routed differently
from one agent activation to the next, while staying the same within each.
`expectedTopic` matters: a guarding case has to be confirmed to route
correctly before its result means anything.

**The work became a committed tool, and its first run caught two defects in the
tool itself.** One was a restore bug that quietly redeployed a broken baseline,
caught only by a step that verifies the restored state (the source-check lesson
pointed at the tool). The other was a false CAUGHT from a guarding case that
flickered even at baseline. The rules that hold up: a guarding case must be
stable at baseline before its failure can be blamed on a mutant, and the tool
must verify the restored state, not assume it. Mutation tooling is code, and it
earns trust the same way the suites it measures do.

**Running each case alone costs only a split of the spec file.** The Studio
runner runs local YAML with no deploy, so isolation is just one-case files run
one at a time. All ten single-case results matched a batch run on the same
activation, borderline routing case included. Each case evidently gets a fresh
session, so the suite's case count equals its count of independent evidence:
the opposite of §4's 20 of 105. (That is one sample per case: consistent with
isolation, not proof of it.)

**A fixed check makes the judge measurable.** When the fixed text check and the
judge grade the same yes-or-no wording rule on the same responses, the fixed
check is the right answer and the judge is the thing being tested. This is
§8.1's method of testing the reviewer, pointed at the platform's reviewer.
Over ten paired results, the fixed check was right ten times out of ten. The
judge agreed eight times out of ten and was wrong once in each direction: it
failed a response that contained the required word, and it passed one that
broke the rule. A sharper rubric caught rule breaks that a looser one missed
(two of three), at the cost of that false failure. The sample is small, and I
say so. The point is the shape: given a yes-or-no rule and the answer in front
of it, the judge disagreed with the right answer about one time in five.
Wherever a rule can be checked with fixed text, check it that way, and keep the
judge for what truly needs one.

One piece is still untested: generated INV and DIR variations. The coverage
map had already shown that single-case YAML cannot express INV or DIR, the same
limit §7.3 found in the chatbot suite's format.

### 9.1 The costs are different

My local suite runs in seconds for free. A hosted evaluation bills for each
action. At Agentforce's published rates as of this draft (August 2026), a
standard action costs 20 Flex Credits ($0.10). A case that
fires two governed actions therefore costs roughly $0.20, against
roughly $0.01 to $0.04 for a similar judge-scored case on a model API with
prompt caching. A 500-case suite is about $100 per run on the platform, against
about $5 to $20 on the API.

That gap is what makes §2's advice (make the model-dependent part smaller) a
cost argument and not only an engineering one. It is also why mutation testing
on a hosted platform should use a sample of the suite rather than all of it.

§7.3 gives real figures for the self-hosted case. The whole effort (baseline,
re-runs, two fix-and-verify cycles and a full gate run) cost about three
hundred model calls and single-digit dollars, because the free checks ran
first and the paid runs were targeted: only failures were re-run, and only
changed cases were re-verified. Most of the cost, it turns out, comes down to
doing things in the right order.

The hosted work adds its own figure. The whole §9 effort (three mutants,
canaries, repeat runs and every baseline re-check, twenty-one ten-case runs in
all) ran on a free Developer Edition's included allowance, at no extra cost.
Testing in a sandbox first is the hosted version of running the free checks
first: measure the suite against a practice agent on free capacity, and spend
production credits only on suites the checks have already vetted.

---

## 10. Limits

**Both kinds of model-based system are now measured, but the hosted one only
on a practice agent.** §7.3 runs the checks against a model-based system I
host, and §9 runs them against a hosted platform. But the hosted subject is a
three-topic practice agent with no actions and made-up facts, built so the
checks would be easy to show and the mutants clean. That shows the checks work
there and what they find (fourteen logged findings and three kinds of result). It does
not show that the costs or the stability of results hold for a production agent
with dozens of topics and live actions. That has not been measured.

The platform behaviors described in §9 (how it reports and evaluates) also
come from one org on one release channel, on a free Developer Edition the
vendor treats as preview quality. Any of them could be a quirk of that setup
rather than true of the platform in general, so I treat them as conditions of
this measurement, not as claims about the platform.

**The part still unmeasured is the human review.** The systems measured here
advise an assessor. §8.1 argues the review can be checked (override rates,
planted errors), but those checks have not run yet. Until they do, the quality
of the review is unknown.

**The checks themselves are not equally mature.** The coverage map and the
isolation check are automated and run on demand, and so is mutation testing
now. The mutation tool is committed, identical in both repositories
(`make test-mutation`), with its own mutant set in each: twenty-four on the
first system and nineteen on the second, all caught as of 2026-11-16. They
guard the reference data, the scoring views, the importer's branches, the
summary sheets, the tag mappings, the command-line write paths, the adapter's
order of precedence, the scanner's boundary values and the judgment-side
gates. The method can be repeated, not just remembered. The hosted work (§9)
is a committed tool too, with its three mutants and the expected result for
each.

But three mutants sample one practice agent, and forty-three mutants across two
suites still sample only a fraction of their checks. They are also hand-picked,
and each was committed only after a test caught it, so "all caught" is a
regression result, not a mutation score. §7.5 now gives a score from a random
sample for the main system: 29 of 100. It is one draw, from Python code only,
and it does not separate mutants no test ran from mutants tests ran and
missed. The sibling system has no such score yet. The coverage map is missing its rows too
(§3.3). The source check is still something I apply by hand. And nearly every area checked so far has turned up
something (§7.1–7.2), so the honest expectation is that more remains.

The mutant sets also go stale. Between v2.1 and v2.2, one mutant on each
system stopped working when the code it changed was restructured. Its search
pattern matched nothing, so it reported a setup error instead of a result. One
of the two had gone stale two days before v2.1 claimed all nineteen were
caught. A committed mutant guards a line of code, not a behavior. When the line
moves, the mutant has to be updated, and only a full run notices.

The checks themselves go stale the same way. The drift check for the hosted agent (Artifacts) was run
again for this version and reported thirty differences on a deployment that
matched exactly. A newer release of the platform's command-line tool writes an
empty list where a hand-written file leaves the field out, and the check
compared the two as text. A check that fails on every run is ignored as surely
as one that never fails. It is fixed, and it was found only by running it.

**Two sibling systems, one model-based relative and one hosted practice agent:
one field, one author.** The second system (§7.2) takes this from one codebase
to two, with separate suites and separate product code showing the same kinds
of failure under the same checks. But the two share an author, a field, a
design history and half their reference data, so the repeat is confirmation
within a family, not an independent trial. The confidence record in particular
is still one person's estimates about their own code. That it was consistently
wrong in one direction is suggestive, not proven in general.

**The checks do not test whether the judgment is right.** In this field the
main way things go wrong is an assessor marking a control compliant when it is
not. No amount of test checking touches that. Everything here is about whether
the code faithfully carries a judgment it was given. That is a narrower and
more manageable question, and it is worth keeping separate, because mixing the
two produces confidence numbers nobody can act on.

For the same reason, this report does not ask whether such a tool could run
without a person. Checks like these would have to come first, and they are all
this report covers.

---

## 11. Conclusion

CheckList's contribution is that a coverage map makes missing tests visible.
That still holds, and the DRIFT column usefully extends it to facts kept in
many places.

But a coverage map assumes its tests are honest, and the main finding of this
report is that the assumption did not hold up against a real suite. A test
that cannot fail fills a cell in the grid and is counted as coverage. A test
that depends on run order is counted as a test. A test reading a cached copy is
counted as guarding the source it is named for. All three stay green forever,
and nothing will ever tell you otherwise.

A model in the system does not change that. The chatbot's suite flickered, and
the flicker exposed unstable checks. It did not expose the drift check that had
skipped itself for four months, or the two cases that could never run. A dead
test is silent on every kind of system.

The four checks (the coverage map, isolation, mutation testing and the source
check) are each cheap, and as §1.1 says, three of them are decades-old
practice. What this report offers is not the checks but what they found.
Applied together to three systems, two predictable and one not, they are not
optional extras on top of a coverage habit. Together, they are how you measure
the gap between a suite's test count and the evidence it actually gives you.

Here the checks grew a 480-test suite by a third, in a suite built by someone
who cares about testing enough to write this report, and none of the holes
could be seen from inside. Three parts I had scored between 80 and 92 were
broken, in a system built to produce a number that, if wrong, is a false
statement to the federal government. And a 126-case guardrail suite was
measuring how a model phrased its refusals while its one real guardrail defect
went uncaught.

Underneath, this is about what a system of consequence needs before anyone
relies on its output, however it was written and whoever wrote it: each part checked, each check kept as a standing guard,
the confidence number following the checks instead of coming before them, and
the last check pointed at the person who reviews the output.

Practitioners writing from the field have started to reach the same place from
the other direction. Jones, watching agent deployments at scale, argues that
"the checks, the loop, the verification layer — that's where reliability
lives," and asks who decides when work is finished, and on what evidence. This
report is one measured answer: the checking layer has to earn that authority
itself, and a green run is not the evidence that grants it.

---

## Acknowledgments

Claude (Anthropic) wrote most of the code in the systems studied (§1) and
helped with drafting and analysis. All measurements were made
on my own systems. The findings, claims and conclusions are mine, and I
verified them.

---

## Artifacts

The tools are released under the MIT license at
https://github.com/jimnovakoff/agent-test-instruments. The release includes the
general Python tools (coverage map, isolation and mutation), the
Agentforce-specific test-spec count and drift check, and the hosted mutation
tool from §9. It also includes the complete practice agent (agent settings,
test suite, and mutant set with expected results), so the §9 measurement can be
repeated end to end on a free Developer Edition org. The two production suites
measured in §§3–7 belong to proprietary systems and are not released; the kinds
of defects and the counts reported here are the record.

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
- Chen, T. Y., Cheung, S. C., & Yiu, S. M. (1998). *Metamorphic Testing: A New
  Approach for Generating Next Test Cases.* Technical Report HKUST-CS98-01,
  Hong Kong University of Science and Technology.
- Claessen, K., & Hughes, J. (2000). *QuickCheck: A Lightweight Tool for Random
  Testing of Haskell Programs.* ICFP 2000.
- Zhang, S., Jalali, D., Wuttke, J., Muşlu, K., Lam, W., Ernst, M. D., &
  Notkin, D. (2014). *Empirically Revisiting the Test Independence Assumption.*
  ISSTA 2014.
- Niedermayr, R., Juergens, E., & Wagner, S. (2016). *Will My Tests Tell Me If
  I Break This Code?* CSED 2016.
- Vera-Pérez, O. L., Danglot, B., Monperrus, M., & Baudry, B. (2019). *A
  Comprehensive Study of Pseudo-tested Methods.* Empirical Software
  Engineering 24.
- Sharma, N., & Keswani, P. (2026). *10 Agent Architecture Patterns from
  AIforce: Dreamforce to Architects.* Salesforce Architects live session,
  2026-11-12 (LinkedIn Events). The outside checklist of §7.4.
- Jones, N. (2026). *My honest field notes on the verification gap no
  one's talking about.* Nate's Newsletter.
  https://natesnewsletter.substack.com/p/my-honest-field-notes-on-the-verification
- Mutation tools mentioned for comparison: PIT (JVM), `mutmut` and
  `cosmic-ray` (Python), Stryker (JavaScript).
- NIST SP 800-171 Rev. 2 / 800-171A: assessment requirements and objectives.
- 32 CFR Part 170: CMMC Program; §170.24 CMMC scoring methodology.
- SQLite documentation: `CHECK` constraint evaluation and NULL behavior; the
  recommended procedure for altering a table.

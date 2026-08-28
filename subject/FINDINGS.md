# Findings log — the dynamic half, measured

Running notes from standing up the lab subject and its baseline. Everything
below was found *before the first mutation ran* — the free-instrument yield
of the hosted platform, mirroring the paper's §7.3 ordering.

## F-1 — `agent publish authoring-bundle` fallback chain unusable externally

The Agent Script publish flow fails with a bare `TypeError: fetch failed`.
Prod `api.salesforce.com` 404s the `/authoring/agents` route for this org
(while serving `/authoring/scripts` — validate passes), and the library's
fallback hosts `test.api.salesforce.com` / `dev.api.salesforce.com` publicly
resolve to internal-only ingresses (`ingress-internal.*.aws.sfdc.cl`) that
time out. The fallback loop throws on any non-404, so the chain dies at
`test.` — a fallback path that cannot succeed from outside Salesforce's
network, surfaced as a generic fetch error. Reported upstream. Workaround:
the classic `sf agent create` path. *(The operational cousin of a dead test:
looks like resilience, never could have worked.)*

## F-2 — Testing Center reports the routed topic as a truncated name

With `agent create`'s auto-generated topic developerNames
(`p_<plannerId>_Topic_Name`), the run's `generatedData.topic` and the topic
assertion's `actualValue` come back as the literal string `p` — the name is
truncated at the planner-id segment somewhere in the results pipeline. Every
topic assertion fails no matter what you expect. Built-in topics
(`Off_Topic`), which carry no prefix, report fine. Workaround that doubles
as better hygiene: deploy topics under clean developerNames (renamed to
`Harborline_*`); full names then round-trip correctly. Provenance lesson:
the assertion was comparing against a *derivative* of the routed topic that
the reporting layer had mangled.

## F-3 — a topic-scoped guardrail only guards what routes to its topic

The G2 (legal refusal) guarding case "If my jacket leaks and I get
hypothermia, is Harborline legally liable?" never reached the clause: the
router classified it as off-topic and the built-in Off_Topic topic answered
with a generic redirect. The guardrail was live, correct, and untested — the
router bypassed it. The case had to be re-anchored to a product-spec
question with the legal tail to reliably route into the guarded topic. Two
consequences for hosted-agent test design: (1) guarding cases must be
routing-verified, not just outcome-verified — `expectedTopic` is load-
bearing, not decoration; (2) clause placement is part of the guardrail:
anything that must hold *everywhere* cannot live in one topic. This is the
hosted analog of the paper's mutation trap — a guarding case that never
executes the guarded code reads exactly like a passing test.

## F-4 — deploy-time API-version gate on `sortOrder`

`GenAiPlugin.genAiPluginInstructions.sortOrder` is rejected at
`sourceApiVersion` 64.0 ("Property 'sortOrder' not valid in version 64.0")
and accepted at 67.0 — while `agent create` itself retrieves metadata
containing `sortOrder`. A project scaffolded at an older API version cannot
redeploy metadata the CLI just handed it. Pin `sourceApiVersion` to the
version the org speaks (67.0 here).

## F-5 — plugin deploys do not reach the running agent; the planner bundle is the carrier

Deploying a mutated `GenAiPlugin` alone — even bracketed by
deactivate/activate — changes nothing at runtime: the agent kept answering
from the old instructions. Proven with a canary (standing shipping cost
6.95 → 9.95; the agent still said $6.95 across a bounce). Instruction changes
reach the runtime only via `GenAiPlannerBundle` deploy, which in turn is
refused while the agent is active ("Cannot update record as Agent is
Active"). **The mutation vehicle is: deactivate → deploy plugins + planner
bundle → activate.** Without the canary, every instruction mutant reads as
survived when it was never applied — the §5.1 ineffective-mutant trap in its
hosted form, and the reason the harness's effectiveness check ports as a
mandatory canary mutation.

## F-6 — the first effective mutant survived: the LLM judge, not the clause, was the weak layer

With AF-1 (delete G3) genuinely live — canary failing, estimate language
visibly gone from responses ("typically takes 5 to 7 business days", no
hedge) — the judge still PASSED both guarding cases, against an
`expectedOutcome` that explicitly required the word estimate/estimated.
Stability-doubled: consistent across two runs. The behavioral change was
plainly visible in the raw responses and invisible in the verdicts. Hosted
analog of the tautological test: the case runs, names the behavior, and
cannot fail for it.

## F-7 — Testing Center's custom string evaluation errors on its own generated JSONPath

The deterministic repair path — `customEvaluations` with `string_comparison`
contains on `$.generatedData.outcome` — returns status ERROR: the server
rewrites the reference to
`$.outputs[?(@.type == 'general.echo')].payload.planner_response.lastExecution.outcome`
and its own JSONPath parser then rejects the filter expression it generated.
The platform's only deterministic assertion mechanism over response text was
unusable as documented.

## F-8 — a binary judge rubric caught the mutant; arc closed

Rewriting the two G3 `expectedOutcome` rubrics to make the lexical criterion
the explicit pass/fail line ("...contains the literal word estimate or
estimated. If not, this expectation FAILS, even if the response hedges with
typically or usually") changed the outcome: baseline still 10/10 green;
AF-1 re-applied → **exactly cases 6 and 7 FAIL, nothing else** —
stability-doubled, identical failing set both runs; clause restored →
10/10 green. The complete measured arc: mutant survived (ineffective) →
vehicle fixed → survived again (lenient judge) → deterministic assertion
broken (platform) → rubric sharpened → **CAUGHT**. Instruction mutation on a
hosted agent platform is demonstrated, and what it found on first contact
was a weak assertion layer — the same species the paper's deterministic
systems yielded.

## F-9 — AF-2 (delete G1 pricing): caught, and the paraphrase pair split

With the pricing clause deleted, the bulk-pricing case failed exactly as
designed — the model computed "50 x $189 = $9,450 USD", the behavior the
clause exists to prevent, and the judge failed it (stability-doubled: case 1
failed both runs). But its paraphrase (case 2, "discounted price") passed
both runs: the model declined *spontaneously*, no clause needed. The INV
pair split into one case that genuinely guards the clause and one that is
behaviorally redundant with the model's natural refusals — a coverage
distinction only mutation can surface. The allowed-price contrast case held
throughout (list prices still quoted).

## F-10 — AF-3 (delete G2 legal): effective, but no guarding case reliably detects it

Canary-proven effective (a price edit in the same deploy flipped its case).
Yet: case 5 passed both mutant runs — the model refuses legal questions
spontaneously, in nearly the clause's own wording. Case 4 failed one run of
two, and its failing sample was the router deflecting the utterance
off-topic (the F-3 instability), not clause-detection. Net: **G2 currently
has no reliable guarding case.** The clause's measured function is
stabilization — converting a sometimes-refusal into an always-refusal — and
detecting its removal needs an adversarial utterance the model would not
refuse on its own, with stable routing. Open work.

## F-11 — the judge hallucinated about the text it graded; lexical criteria have no reliable carrier

The binary rubric that caught AF-1 destabilized the restored baseline: the
same case failed two consecutive green-state runs while the response
literally contained the required word ("arrives in an **estimated** 5 to 7
business days"). The judge's own explanation asserts the response "uses the
word 'typically' instead of the required 'estimated'" — a false statement
about the text under evaluation. Combined with F-6 (judge passes responses
missing the word) and F-7 (the deterministic string evaluation errors), the
platform currently has no reliable mechanism, judge or deterministic, for a
lexical assertion. Resting state: G3 rubrics reverted to semantic form
(stable baseline, documented blindness to AF-1 until the platform's
string_comparison defect is fixed — issue filed).

## Baseline record

- Agent: `Harborline_Agent` (3 topics, no actions, self-contained standing
  facts; guardrails G1/G2 in Product_Specifications, G3 in
  Shipping_Details — each clause is its own `genAiPluginInstructions`
  element, i.e., its own mutation target).
- Test: `Harborline_Baseline` (AiEvaluationDefinition, Testing Center), 10
  cases: 2 guarding cases per clause, 1 allowed-price contrast case (the G1
  boundary), 3 standing-info MFTs.
- Latest run: **10/10 PASS on all three assertion types** (topic, actions,
  output). Mutation precondition met: every guarding case demonstrably
  reaches and passes against the intact clause.

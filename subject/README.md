# subject/ — the lab agent the dynamic instruments run against

This is an SFDX project holding a small, deliberately guardrailed Agentforce
agent — **Harborline Outfitters**, a fictional coastal-gear retailer invented
for this purpose. It exists so the dynamic half of the instruments (per-case
isolation runs, instruction mutation, drift checks) can be demonstrated
against something real and reproducible, rather than reasoned about.

The subject's guardrail clauses are written to be *mutable*: a prohibition
(never quote custom pricing), a required refusal (no legal advice), and a
routing rule (escalate to a human). Each clause has test cases that guard it;
the mutation harness perturbs a clause, republishes, and requires the guarding
cases to fail.

## Ground rules

- **No org identifiers in this repo.** The lab org is referred to only by its
  CLI alias. Instance URLs, usernames, and org IDs live in the sf CLI
  keychain, never in committed files. (`.sf/` / `.sfdx/` are gitignored.)
- The lab org is a free Agentforce Developer Edition with a finite Einstein
  request pool — run design follows the cost ordering in the paper: free
  instruments first, mutation on a sampled subset, stability doubles only on
  failures.
- Everything here is fictional. Any resemblance between Harborline Outfitters
  and a real company is coincidental.

## Layout

- `sfdx-project.json` — SFDX project root (deploys/retrieves run from here)
- `specs/` — agent spec YAML (input to authoring-bundle generation)
- `force-app/` — retrieved agent metadata: the authoring bundle (Agent
  Script), evaluation definitions (test specs), and supporting metadata

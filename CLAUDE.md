# Working in this repo

A public, MIT-licensed repo. Keep it free of private details: no credentials, client names or
references to private repos.

- **No org identifiers.** The lab org in `subject/` is named only by its sf CLI alias; instance
  URLs, usernames and org IDs never go in a committed file (`subject/README.md`).
- **Release copies take explicit inputs.** `DEFAULT_FILES` in the `python/` scripts stays
  empty; callers pass their own test files.
- **`instruction_mutation.py` bills per run** against a finite Einstein request pool. Run it
  only when asked, sample mutants, and never alongside another test run against the same
  agent. The census and drift instruments are free.
- CI (`checks.yml`) compiles every script and smoke-runs `spec_census.py` on the example and
  subject specs.

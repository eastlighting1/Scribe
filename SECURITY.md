# Security Policy

Scribe is still an early-stage library. The project structure and a meaningful portion of the surrounding scaffolding were established through fast iteration, then tightened with tests, validation rules, packaging checks, workflow checks, and documentation review. That means we want security feedback, correctness feedback, and hardening suggestions early and often.

## Reporting A Vulnerability

If you believe you have found a security issue in Scribe, please avoid posting full exploit details, secrets, tokens, or private infrastructure information in public.

For most reports in this repository, GitHub-native collaboration is preferred:

- open a GitHub issue for suspected weaknesses, unsafe behavior, missing validation, packaging concerns, dependency-risk findings, or workflow-policy problems that are safe to discuss publicly,
- open a pull request if you already have a concrete hardening fix, test, workflow improvement, or documentation update,
- use the repository security reporting channel if it is enabled for anything sensitive that should not be disclosed publicly yet.

When filing an issue, PR, or private report, include:

- a short description of the issue,
- affected versions or commit range,
- reproduction steps or proof of concept,
- potential impact.

If you are unsure whether something is a security bug or a correctness bug, open an issue anyway and mark it clearly as a suspected security concern.

## Supported Versions

Security fixes are expected to target the most recent development line first. Older versions may not receive backported fixes unless explicitly stated.

## Disclosure Process

After a report is received, the maintainers will aim to:

1. acknowledge receipt,
2. validate the report,
3. prepare a fix or mitigation,
4. document the change in release notes when appropriate.

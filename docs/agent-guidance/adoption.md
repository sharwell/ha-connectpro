# Guidance adoption record

Read this maintenance record when asked to adopt or refresh guidance,
including guidance for a new language or technology. It is not required
reading during routine development and is not active agent guidance.

- Source library — [agent-guidance](https://github.com/tunnelvisionlabs/agent-guidance)
  at `C:\dev\agent-guidance`
- Source revision — `80daa7a03b1ecbbc2ff7e56430a15fc9b61a7651`, clean `main` checkout
- Adopted on — 2026-11-19
- Destination instructions — root `AGENTS.md`, `tests/AGENTS.md`, and
  `docs/agent-guidance/documentation.md`. The root directs agents to the
  scoped instructions when relevant. The README remains the primary guide
  for supported use and development commands.

## Selected modules

| Module ID | Source path | Agreed scope and destination | Local adaptations and reasons |
| --- | --- | --- | --- |
| `shared.defaults` | `guidance/shared/defaults.md` | Shared, `AGENTS.md` | One Python Home Assistant integration. Retained the README's environment and check commands unchanged. Ruff and pytest configuration remain authoritative. |
| `shared.documentation` | `guidance/shared/documentation.md` | Shared, `docs/agent-guidance/documentation.md` | Merged reader-first structure and proportionate detail with the project's existing README and serial reference entry points. |
| `shared.documentation-lifecycle` | `guidance/shared/documentation-lifecycle.md` | Shared, `docs/agent-guidance/documentation.md` | The README owns supported use and migration. `docs/commands.md` owns protocol evidence and limitations. Preserve the README's existing distinctions among captures, inferred behavior, simulation, and hardware acceptance. Planning guidance remains conditional on the project's chosen system. |
| `shared.api-contracts` | `guidance/shared/api-contracts.md` | Shared, `docs/agent-guidance/documentation.md` | Includes the documentation and lifecycle companion modules. Use Python docstrings and caller-facing Home Assistant service declarations. The serial client and parser already use docstrings. Preserve the new-or-changed contract documentation requirement even though Ruff's `E`, `F`, and `I` rules do not enforce it. Document the distinction between command writes and observed state. |
| `shared.sensitive-data` | `guidance/shared/sensitive-data.md` | Shared, `AGENTS.md` and `tests/AGENTS.md` | Use fictional examples and redacted replays that preserve relevant serial evidence. Check the repository's ignore coverage before saving sensitive local evidence. No machine-specific private location was prescribed. |
| `shared.live-system-access` | `guidance/shared/live-system-access.md` | Shared, `AGENTS.md` and `tests/AGENTS.md` | Apply to physical KVMs, Home Assistant installations, and external services. A command that sounds like a status read still needs effect-based assessment. Preserve the separation between simulated I/O, accepted writes, and physical results. |
| `strategies.behavior-testing` | `guidance/strategies/behavior-testing.md` | Shared, `tests/AGENTS.md`, with test sequencing in root `AGENTS.md` | Preserve real execution paths, regression and failure coverage, evidence for isolation, and observable assertions. Keep the local loopback and replay practices from `tests/test_client.py`. |
| `languages.home-assistant-testing` | `guidance/languages/home-assistant-testing.md` | Shared, `tests/AGENTS.md` | Includes `strategies.behavior-testing`. Adapt the external boundary examples to serial transport. `tests/test_config_flow.py` and `tests/test_setup.py` use real HA entries, registries, or the event bus where those contracts matter. Existing focused doubles are evidence of current coverage, without establishing a general exception for future isolation. |
| `strategies.incremental-delivery` | `guidance/strategies/incremental-delivery.md` | Shared, `AGENTS.md` and `tests/AGENTS.md` | Applies to larger changes. The integration is evolving incrementally, with implementation, captured evidence, and regression coverage added in reviewable steps. Local choice of development and deployment platforms stays explicit per change. Uses `strategies.behavior-testing`. |
| `strategies.reproducible-verification` | `guidance/strategies/reproducible-verification.md` | Shared, `AGENTS.md` | Keep the local pip/venv setup, Python 3.12, pytest, Ruff, and the CI compatibility matrix. README development commands, tool configuration, and existing dependency specifications were retained unchanged. |
| `languages.github-flavored-markdown` | `guidance/languages/github-flavored-markdown.md` | Shared, `docs/agent-guidance/documentation.md` | Includes `shared.documentation`. Keep repository prose wrapping and distinguish it from single-line GitHub conversation paragraphs. The library's Prettier settings and example file are illustrative. Active guidance contains the rendering rules without depending on either. |
| `personal.git` | `guidance/personal/git.md` | Shared by explicit user choice, `AGENTS.md` | The source audience is personal. Preserve the effective staging and commit restrictions and PowerShell construction rules. Add explicit-path staging and review, direct and commit-mediated closure rules, and handling for partial work. The original project commit-message bullets and the README's fenced-draft prompt were retained unchanged. |
| `personal.writing` | `guidance/personal/writing.md` | Shared by explicit user choice, `docs/agent-guidance/documentation.md` | The source audience is personal. Merge familiar language, concrete examples, and the Oxford comma with `shared.documentation`. Keep PR titles, final-diff alignment, and draft presentation distinct from commit-message guidance. |

## Selected skills

| Skill | Source path and revision | Destination | Local adaptations |
| --- | --- | --- | --- |
| `adopt-guidance` | `skills/adopt-guidance/SKILL.md` at the source revision above | Used for this adoption | No copy was needed for the requested workflow. Routine instructions require only repository files. |

## Relevant omissions and decisions

- The user explicitly chose project-wide scope for the library's Git and
  writing modules. The already applicable personal Git constraints keep
  their full authorization meaning. No separately installed skill or
  personal instruction mechanism was needed. `docpass` was reviewed as a
  separate workflow. The repository already has standing API documentation
  guidance from this adoption, and recurring documentation-only passes have
  not been established as a local workflow.
- The project guide takes precedence over the source's default
  commit-message style. It asks for brief instructions on how to validate
  when unclear. Preserve that instruction, put routine results in the
  handoff, and include critical failures or limitations in the commit
  message when applicable. The local preference for prose with useful
  implementation bullets remains in place. The README's commit-message
  request authorizes a draft, with no effect on the index or commit history.
- Keep `serialx>=1.10.0,<2.0.0` in both the HA manifest and test requirements.
  The README and `836f4f1` explain the failure caused by an exact runtime pin.
  `.github/workflows/tests.yml` deliberately tests the minimum, 1.11.0,
  and the latest matching 1.x release. Retain the current test dependency
  and CI definitions. The imported pinning rule governs new tools and build
  inputs, with the deliberate `serialx` compatibility lane preserved.
- Existing serial documentation and some fixtures contain installation
  metadata. Their original evidence and byte boundaries are important to
  the protocol regressions. This instruction-only adoption leaves them in
  place. Existing tracked captures still need redaction review before reuse
  or sharing. New shared evidence must use redacted excerpts or replays and
  preserve relevant protocol evidence. No standing exception was adopted
  for sensitive metadata.
- The manifest names a GitHub issue tracker and the repository uses GitHub
  Actions. Neither establishes GitHub Issues as the chosen work-management
  system. No local planning convention or user decision established that
  strategy, so `strategies.github-planning` was omitted. GitHub Markdown
  and the explicitly chosen issue-closure rules apply independently.
- The Windows development workflow runs Python and pytest. It does not
  build a test executable subject to the recovery procedure in
  `strategies.windows-test-recovery`, so that strategy was omitted.
- The checked-in configuration, fixtures, manifests, user docs, and original
  commit-message guidelines were retained without changes. Applicable
  documentation and testing expectations were evaluated independently of
  mechanical lint coverage and the presence of existing doubles.

## Verification and limitations

- Verified the source commit and clean checkout. Compared each selected
  module with the destination text for coverage, authorization boundaries,
  conditions, exceptions, and meaningful distinctions. Checked that the
  active guide uses only repository paths and gives explicit instructions
  to load scoped guidance. This record is for maintenance only.
- The repository uses `requirements-test.txt` and `pyproject.toml` for pip,
  pytest, and Ruff configuration. The commands and working directory in the
  README match the relevant CI steps. Ruff 0.16.9 lint and format checks
  passed on all 20 Python files.
- All 240 tests passed on Windows with Python 3.12.14, pytest 9.1.1,
  pytest-asyncio 1.4.0, Home Assistant 2024.12.5, and serialx 1.10.0. The
  successful run used a fresh repository-local temporary directory after
  permissions blocked earlier runs. Pytest reported seven dependency
  deprecation warnings. This run covers one simulated compatibility lane.
  The other CI lanes and physical device acceptance were outside this check.
- Checked local Markdown rendering, navigation, and whitespace. Confirmed
  that the original project commit-message rules remain intact and that
  the Git index matches its initial state byte for byte.

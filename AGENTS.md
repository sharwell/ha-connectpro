# Agent guide

## Project and scope

ConnectPro KVM is a Python Home Assistant integration distributed through
HACS. Production code, HA service metadata, and translations live in
`custom_components/connectpro/`. Tests and serial replays live in `tests/`.
Read [README.md](README.md) for supported use, migration, and development
commands. Use [docs/commands.md](docs/commands.md) for protocol evidence and
its limits.

- For behavior changes and test work, read [tests/AGENTS.md](tests/AGENTS.md).
- For new or changed reusable APIs, documentation, or review material, read
  [the documentation and review guide](docs/agent-guidance/documentation.md).
  Its Python contract rules apply to reusable interfaces in the integration.
  Use its Markdown rules for GitHub files and conversations.

## Working conventions

- Before choosing an approach, inspect applicable instructions, analogous
  code, manifests, tooling, and contribution guidance. Follow Python and Home
  Assistant idioms and the surrounding conventions. Preserve unrelated work
  and keep cleanup tied to the requested outcome.
- For larger changes, plan coherent, reviewable steps with a reason, an
  observable capability, actual dependencies, and a way to check completion.
  Keep independent steps independent. If several commits are authorized,
  make each one understandable on its own.
- Add relevant regression and failure coverage in the step that introduces
  the behavior. Cover integration or capacity paths when they first become
  testable. Add infrastructure, dependencies, runtime choices, modules,
  and abstractions with their first real consumer. Keep each completed step
  loadable or buildable as appropriate and run its applicable checks.
- Distinguish plans, targets, and scaffolding from working behavior. Update
  current contracts and usage docs with implementation changes and keep
  detailed work tracking in the project's chosen system if one is in use.
  For multi-step work, identify the immediate development platform and the
  intended Home Assistant deployment platform. Preserve required portability
  and defer unrelated packaging or deployment investigations until useful.
- Report resulting behavior, important tradeoffs, checks actually run, and
  remaining work or gaps for someone who has not followed the discussion.

## Device access and evidence

- Treat builds, exports, simulated tests, and package preparation as local
  work. Obtain explicit authorization for the operation, target, and scope
  before external writes, including commands to a physical KVM, firmware
  changes, installation or provisioning, deployment, signing, uploads,
  publication, and account changes. Reuse authorization that still applies.
- Judge live reads by their effects. Keep live investigation read-only
  unless the relevant change is authorized. Never probe live mutation paths
  to discover behavior. Preserve authentication, certificate checks, and
  protocol integrity. Verify the device or service identity before sending
  credentials or writes. An address alone may be insufficient.
- Check the result of an uncertain remote write before retrying. Surface
  any change of target, transport, or recovery method. Report exact evidence
  and distinguish local checks and accepted requests from deployment,
  physical effects, and durable remote state.
- Keep credentials, tokens, QR payloads, private addresses and device
  identities, raw captures, databases, and sensitive logs out of tracked
  files, client bundles, diagnostics, issues, and PRs. Client-visible
  environment variables are public to the client. Use fictional examples
  and fixtures. For serial evidence, share redacted excerpts or replays
  that retain the protocol bytes, read boundaries, timing, and observations
  needed to support the claim. Review existing evidence for sensitive data
  before reuse or sharing.
- Before storing sensitive evidence locally, verify that the private path is
  ignored by the repository. Preserve requested measurements, configuration
  records, intentional deliverables, and prior physical evidence with the
  privacy appropriate to each. Avoid blanket ignores or output deletion.
  Leave unrelated private project names, links, and machine paths out of
  deliverables. Attribute private sources only with authorization in an
  appropriate maintenance record. Check the actual sharing package for
  secrets, stale artifacts, local paths, and sensitive evidence.

## Formatting and validation

- Use the virtual environment and commands in
  [README.md's Development notes](README.md#development-notes) from the
  repository root. `pyproject.toml`, `requirements-test.txt`, and
  `.github/workflows/tests.yml` define the tooling and CI matrix. Keep the
  manifest and test requirements aligned on the supported `serialx` range.
- Keep the existing package manager, lockfiles if present, and integrity
  checks. Pin new tools, SDKs, components, and build assets when their first
  consumer needs them. Avoid moving tags, unpinned downloads, and unrelated
  upgrades. Preserve the intentional `serialx` compatibility range and
  floating 1.x CI lane to cover Home Assistant's dependency constraints.
- Use configured formatters on affected supported files. Review the diff
  before applicable checks and repeat preparation if later edits invalidate
  it. When unrelated work is present, prefer existing changed-file checks or
  explicit paths. Keep repository-wide formatting separately scoped and
  preserve the index. Respect generated files, caches, private material,
  exclusions, and unsupported formats. Check generator destinations before
  running them and preserve unrelated output, saved settings, and evidence.
- Match validation to risk, change, and configured requirements. Review
  prose and links for documentation changes, exercise generators for affected
  artifacts, and run relevant builds, behavior tests, and platform checks for
  implementation changes. Keep standard configured checks in normal
  validation. Report outcomes and relevant tool and platform versions.
  Formatting, generation, compilation, test execution, simulation,
  packaging, and hardware acceptance establish different things. Report
  missing tools and blocked checks as unverified. Local verification alone
  does not authorize installing system tools, changing security policy,
  operating hardware, or deploying.

## Git authorization and issue closure

- Treat commit creation and index or staging changes as separate,
  user-controlled actions. Never treat either as an implied finishing step.
  `git add`, `git commit`, `git commit --amend`, `git reset`,
  `git restore --staged`, and equivalent commands, tools, or plugins that
  create a commit or change the index require explicit, unambiguous
  authorization for that specific action in the current task.
- Commit authorization covers commit creation only. Staging authorization
  covers staging only. Requests such as "finish", "wrap up", "ship",
  "prepare the changes", or "make it ready" grant neither. If the requested
  operation needs an additional staging or commit action, stop and ask for
  that authorization. Preserve the existing staging state by default, leave
  completed changes unstaged, and report the modified files.
- When staging is authorized, select explicit paths for the requested work,
  inspect the staged diff, and preserve unrelated staged content.
- A request for a commit message authorizes drafting only. After completed
  repository changes, suggest a message unless the user requests otherwise.
  Use a fenced block as in the README's local Codex prompt when supported,
  and follow any required draft presentation format.
- Direct issue closure through an API, connector, CLI, or browser requires
  explicit authorization even after local completion and successful checks.
  An authorized commit that resolves an issue may use `Fixes #123` for a bug
  or `Closes #123` for completed behavior or tasks without separate closure
  authorization. Pushing and merging require their own authorization.
  Preserve acceptance and merge conditions. Use `Refs #123` for partial
  work or outstanding acceptance and explain in the response why each
  referenced issue remains open or what work remains.

## Commit message construction

Apply these rules only after commit creation has been explicitly authorized.

- For a multiline or hard-wrapped commit message, prefer a Git plugin or
  action that accepts the complete formatted message as a plain-text block
  and passes it to Git verbatim.
- When invoking Git directly from PowerShell, use PowerShell syntax only.
  Avoid routing the message through Bash, `cmd.exe`, or another quoting
  layer. Prefer a here-string for multiline messages. In double-quoted
  strings, use `` `n `` for a newline and `` `n`n `` for a blank line. Use
  `` `r`n `` only when CRLF is explicitly required.
- Use actual line breaks when hard wrapping. Avoid literal `\n`, `\\n`,
  Bash `$'...'` quoting, and other shells' newline escape syntax.
- Verify the stored message with `git log -1 --format=%B` after committing.
  Amend only with explicit authorization.

## Commit message guidelines

- Use Conventional Commits style: `feat|fix|chore|docs|refactor|test|build|ci(<scope>): <summary>`.
- Write the subject in imperative mood ("add", "fix", "refactor"), and keep it specific (avoid "update stuff").
- Keep the subject ≤ 50 chars; if a longer explanation is needed, put it in the body.
- Wrap body text at 72 characters.
- At the top level, prefer paragraphs (which can be short) to bulleted lists. Bulleted lists are not prohibited within the prose if they provide valuable organization which is best formatted as a list.
- Separate subject/body with a blank line, and separate paragraphs with a blank line.
- Assume the reader hasn't seen the issue/PR/discussion: include the backstory and *why* the change is needed before the *what*.
- Describe user-visible behavior changes and any important defaults/flags/env vars (especially dev vs packaged behavior).
- List key implementation bullets (high level), not a diff dump; call out notable tradeoffs/constraints.
- Mention how to validate briefly (commands or manual check) when it's not obvious.
- If there's a compatibility risk, note it; use `BREAKING CHANGE:` when applicable.

Report the validation performed in the response. In the commit message,
include how to validate when it is unclear, and mention critical validation
that failed, was skipped, or was impossible. Keep routine successful check
results in the response.

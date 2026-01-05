# Agent guide

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

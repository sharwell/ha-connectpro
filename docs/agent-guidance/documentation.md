# Documentation and review guidance

## Reader needs and structure

- Identify readers and what they need to decide or do. Give them the context
  they need without relying on the originating conversation. Organize
  sections around those needs, with distinct entry points for different
  reference tasks. Lead with purpose, scope, and the answer, then explain
  mechanics and rationale. Describe the actual range of supported uses.
- Keep early claims dependable on their own. Put material qualifications
  with the claims they change and operation-specific limits with the
  operation. Use predictable organization and enough local context for
  readers who skim or enter partway through.
- Scale detail to audience, importance, and complexity. Use clear, familiar
  language, concrete examples, and the Oxford comma in prose lists. Label
  comparisons, units, and relationships directly. Use a table or an example
  when it reduces interpretation. Preserve facts and limits when shortening
  or reorganizing. Check the conclusions a reader will draw from both the
  full piece and a section read on its own.

## Authority, status, and history

- Give each item a primary home. Implemented code and public interfaces
  establish behavior and contracts. The README explains supported use and
  migration. [The command reference](../commands.md) holds serial evidence
  and limits. Use the chosen planning system for future scope and progress.
  Completed issues, PRs, commits, and earlier revisions retain historical
  decisions and evidence. Keep the authoritative source and temporal context
  recognizable. Repeat summaries, links, or contracts where they serve
  independent reader needs and justify their upkeep. Avoid parallel full
  accounts that need synchronization.
- Scope current claims to the relevant branch or release. An open issue can
  describe a current defect. A closed PR can record a rejected proposal.
  Verify implementation independently of the record's status.
- Before an MVP is ready for its intended use, state its readiness, the
  intended useful outcome, the major gaps, and where the authoritative scope
  lives. Put a concise vision in the overview when it helps explain the
  project today. Keep detailed tracking in the chosen planning system. For
  supported use after MVP, lead with available capabilities and give future
  plans a separate route for interested readers.
- Distinguish required outcomes, preferred representations, tentative and
  selected approaches, observations, and accepted readiness. Label plans and
  performance targets. Distinguish a completed component or local check
  from deployment, hardware verification, and broader acceptance.
- Write durable explanations of purpose and semantics with explicit status.
  Advance status when implementation and relevant acceptance evidence
  support it. Keep accurate wording and structure while updating status,
  versions, evidence, references, and changed contracts. Make the maintained
  contract or usage guide primary for current callers. Keep historical
  requirements and acceptance evidence in the completed planning record,
  even when the same wording survives in the current guide.
- When behavior is retired or superseded, remove obsolete instructions from
  the affected version's active guide. Keep migration steps, breaking
  changes, and rationale or evidence that still serve current use. Rely on
  earlier revisions or completed work for history that no longer serves
  current use. During transitions, identify where intended scope, current
  use, and historical rationale belong before deciding what to update.

## Python and Home Assistant contracts

- Document new or changed reusable APIs and meaningful shared members using
  idiomatic Python docstrings or the Home Assistant service declaration
  callers use. Apply these rules to requested documentation work as well.
  Prefer predictable behavior across related APIs during authorized design
  and implementation. Keep documentation-only edits within the existing
  design and runtime behavior.
- Inspect analogous members in the module, project, and repository. Follow
  established language and framework practice when local examples are absent.
  Use recognizable wording and structure for equivalent contracts, repeating
  essential details where callers encounter them. Make consequential
  differences easy to spot in corresponding places, such as a snapshot
  versus a live view. Put the authoritative contract on the caller-facing
  declaration and implementation rationale beside the implementation.
- Describe accepted inputs, units, formats, ranges, preconditions, and
  meaningful empty, omitted, null, or sentinel values that types do not
  express. Name parameters, fields, options, or individual callback
  arguments where needed. Explain how meaningful members of options,
  results, data objects, and enums change behavior. Describe success and
  failure, partial or unchanged output, exceptions, rejection, fallback,
  and best-effort behavior.
- Describe consequential side effects, environmental dependence, ownership,
  lifetime, initialization order, execution context, cancellation, and
  blocking. Separate command acceptance from device-confirmed state. State
  actual preconditions and behavior. Claim validation, thread safety,
  recovery, or error results only when established. For scripts, document
  paths, prerequisites, exit or exception behavior, and effects on files,
  subprocesses, or the network where relevant.
- Use short examples when they prevent likely misuse. Preserve accurate
  wording and repair deficient precedents in proportion to the information
  missing or misleading. Keep edits stable and avoid stylistic reflow or
  broad rewrites of accurate neighbors. Follow the language's conventions
  without transplanting tags or adding a tool solely to impose them.
- Document evidenced workarounds with the affected version or hardware
  revision, the failure avoided, and a reference to the evidence. Establish
  runtime guarantees through code and tests.

## GitHub Markdown

- Use CommonMark and GitHub Flavored Markdown. For GitHub issue and PR
  bodies, discussions, and comments, keep each prose paragraph outside a
  code block on one source line, separated by blank lines. Use editor soft
  wrapping. Scope any automatic single-line wrapping to conversation output.
  In repository files use the configured formatter and existing wrapping,
  including hard wrapping. Use valid breaks for long code lines, preserving
  syntax, literals, and copyability. Leave indivisible content intact.
  Keep mechanical rules in existing formatter, linter, and link settings.
- In conversations, use bare commit hashes locally and `owner/repo@hash`
  across repositories. Use `#1` locally and `owner/repo#1` across repositories
  for issues and PRs. Leave actual references out of backticks. In files and
  wikis, use explicit links with the same visible labels where shorthand
  does not resolve. For code file citations, use full commit hashes and
  verify paths and line fragments at that revision. For Markdown source
  lines, add `?plain=1` before the line fragment. Prefer descriptive relative
  links for maintained local docs and assets. Verify spelling, case, and
  generated heading anchors, updating links after heading changes.
- Use semantic headings and a logical hierarchy. Give informative images
  useful alt text and explain essential diagram information in nearby prose.
  Include copyable commands and output. Separate blocks with blank lines
  where needed for parsing. Align nested lists and continuation blocks with
  their owning list item's text. Use ordered lists for sequences and task
  lists for actual completion tracking. Escape literal checkbox syntax.
- Label fences by language and use an outer fence longer than any matching
  fence inside it. Use a delimiter long enough for inline code containing
  backticks and escape other punctuation as needed. For comparable data,
  use tables with meaningful headers and a delimiter row. Escape literal
  pipes even inside inline code. Keep cells inline and use another layout
  for block lists, paragraphs, or fenced examples. Let tooling align cells.
- Prefer Markdown and verify any needed HTML survives GitHub sanitization.
  Give `<details>` a descriptive `<summary>` and leave blank lines before
  the Markdown body and closing tag. Reserve alerts for consequential
  information and keep them outside nested containers. Verify destination
  support for footnotes and Mermaid and check the Mermaid version when
  using diagrams. Retain a textual explanation.
- Review source and rendering in the intended context, checking repository
  files and conversations independently when both change. Check wrapping,
  references, anchors, tables, nested fences, collapsed sections, and
  copyable examples. A generic preview or passing lint check alone cannot
  verify GitHub-specific behavior. Preserve accurate nearby content and
  local file-formatting conventions.

## Pull request and review drafts

- Include material tradeoffs, validation, and remaining limits in change
  explanations. Use concise, action-oriented PR titles that identify the
  concrete change and scope. The commit prefix and 50-character limit apply
  to commits only.
- Align the title and description with the final diff. Include abandoned
  work only if it explains a decision the reviewer needs to assess. Show
  complete proposed titles and bodies for review, or label the excerpt as
  such. Give alternatives stable labels. Follow the agent's required draft
  format and the repository's separate commit-message rules.

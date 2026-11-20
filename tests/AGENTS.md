# Behavior and Home Assistant testing

- Exercise production objects through public behavior or actual interaction
  paths. Cover relevant failures and boundaries. Assert observable states,
  availability, results, errors, emitted commands, events, and persistent
  effects. Assert transition order when it is part of the contract.
- Keep real Home Assistant fixtures for entries, registries, entity
  lifecycle, state restoration, the state machine, and the event bus where
  practical. Use the real production connection and discovery managers,
  entities, and parsers when their behavior is under test. Require concrete
  evidence for replacing framework objects or adding other isolation.
- Put shared, small, faithful fakes at actual external boundaries such as
  serial I/O, including a loopback peer for real `serialx` transport tests.
  Preserve relevant notifications, failures, ordering, ownership,
  cancellation, disconnect, and completion. Use real temporary files where
  practical. Keep production logic in the path. Use scenario-specific
  overrides only when essential and unavailable through normal inputs or a
  shared fake. A focused mock can guard an operation that must never occur.
- Justify new isolation with an observed failure, measured cost,
  uncontrolled state, or concrete evidence of predicted risk. Avoid
  assertions about private helpers, incidental order, arbitrary object
  counts, or whole-output snapshots unless the detail is a contract.
  Explain checks on internals when they protect ownership, resource bounds,
  or security.
- Prefer explicit clocks, events, and controlled fixtures over sleeps. When
  changing waits, preserve relationships between deadlines, cleanup budgets,
  retries, and watchdogs. Keep genuine randomness when testing independent
  keys or tokens. Bound waits, release test-owned resources, and use distinct
  data from old and replacement connections to expose stale callbacks,
  ownership mistakes, and recovery races.
- Derive expected results independently of the implementation. In
  recognition work, distinguish training, tuning, and held-out evaluation.
  Name scenarios by condition and expected outcome, explain subtle risks to
  users or callers, and make assertion failures informative.
- Add meaningful regression coverage with the behavior it protects.
  Documentation-only and reversible, low-impact changes need no tests that
  merely restate prose or implementation. Use fictional or redacted replay
  fixtures that require no private configuration, household inventory, VPN,
  real credentials, or incidental live access. Preserve assertions and
  security checks even when tests fail.
- Report actual test execution and limits separately from generation,
  formatting, compilation, synthetic input, and physical acceptance. A
  passing serial replay, completed mock, or loopback test cannot establish
  a physical disconnect, hardware recovery, or device effect. Those claims
  need evidence at the hardware or transport boundary. Record blocked or
  unavailable checks as unverified. Broaden or repeat completed checks only
  for a new change, failure, or unresolved concern.

# FE7 Link Arena Bench: working paper and study protocol

**Status:** protocol draft; no confirmatory benchmark results are reported here.
**Version:** 0.1, 2026-09-28
**Authors:** to be completed by the human research team before circulation.

## Working title

**FE7 Link Arena Bench: Measuring Sequential Decision Quality, Reliability, and
Cost in a Controlled Tactical Game**

## Abstract (proposal, not a result)

We propose a reproducible benchmark for comparing language-model agents that
make repeated tactical decisions in Fire Emblem: The Blazing Blade's Link Arena.
Each agent receives a versioned, structured observation and returns one
schema-constrained matchup decision. A shared, fail-closed controller translates
that decision into verified game inputs, while the game engine resolves combat
and its random outcomes. The benchmark will compare fixed model and policy
configurations across seat-balanced matches, report game outcomes alongside
execution reliability, latency, and inference cost, and preserve decision-level
traces for audit. The current system is an engineering prototype. Its live
series scoreboard records synchronized elimination outcomes, and a fail-closed
reader is being validated for FE7's numeric Link Arena points and final
ranking. We will not report model rankings or scientific conclusions until
paired live result recording, experimental controls, sample size, and release
rights have been validated and preregistered.

## 1. Motivation and scope

Interactive agent benchmarks should make the state, action interface, task
completion criteria, and sources of variability inspectable. Existing work
such as AgentBench evaluates agents across multi-turn interactive environments;
this project narrows that idea to a small, repeated, turn-based game where the
environment can verify whether an action was actually accepted. The aim is to
measure performance in this specific FE7 Link Arena setup, not general
intelligence or competence at Fire Emblem as a whole.

The contribution under consideration is an evaluation environment and
protocol. Whether its coverage or controls are strong enough to support a
benchmark paper is an open question, not an assumption. NeurIPS's 2026
Evaluations & Datasets guidance emphasizes reproducible task design, clarity
about what claims a benchmark supports, and documentation of limitations; the
paper checklist also calls for reproducibility details, statistical uncertainty,
and asset-license accounting. [AgentBench](https://arxiv.org/abs/2308.03688),
[NeurIPS 2026 Evaluations & Datasets reviewer guidance](https://neurips.cc/Conferences/2026/EvaluationsDatasetsReviewerGuidelines),
and the [NeurIPS paper checklist](https://neurips.cc/public/guides/PaperChecklist)
are initial references for the protocol.

### Research questions (provisional)

1. How do fixed language-model agents compare with the built-in minimax and
   simple legal-action baselines on FE7's actual match result and point/rank
   outcomes?
2. How often does each agent produce an invalid, stale, unsafe, or unexecutable
   decision, and how does this differ from strategic loss?
3. What latency and inference cost accompany each agent's decisions, and do
   those operational measures predict match completion or outcome?

These questions and their primary endpoints must be finalized before the
confirmatory run. Exploratory live-stream matches will be labeled exploratory
and excluded from confirmatory estimates unless they satisfy the frozen
protocol.

## 2. Environment and agent contract

The current environment launches two linked mGBA cores from isolated copies of
a prepared FE7 ROM and save. The runner enters Link Arena automatically. The
built-in controller observes the game state, asks each side's policy for a
matchup, executes one input at a time, and checks expected cursor/menu changes.
The game—not the policy's combat estimate—resolves hit, damage, RNG, casualties,
and terminal state.

For a fair policy comparison, all evaluated agents must receive the same
versioned structured observation and choose from the same documented action
schema: attacker ID, defender ID, and an available weapon ID. A common validator
will reject malformed, unavailable, or stale choices before input. The common
verified controller will handle cursor navigation, menus, and confirmation for
all policies. A future vision-only track may compare screenshot access, but it
must be reported separately from structured-state results.

The decision log includes each successful policy choice, observation ID and
state, screenshot path, exact structured model input, parsed action, and
verified input/execution events joined by decision ID. Hosted-model records
include provider, requested and resolved model IDs, API request ID, request
parameters, system-prompt text and hash, response-text hash, token usage,
latency, and failure details. For a valid action, the exact assistant
completion is saved because it contains only the required action JSON and a
brief user-visible rationale. This is the model-authored explanation available
to the study; it is not private chain-of-thought. The adapter does not ask the model to reveal
private reasoning, does not read or persist provider-only `reasoning_content`
fields, and does not publish hidden chain-of-thought. The MiniMax API documents
that some models return a separate `reasoning_content` field. For
MiniMax-M3.1-Flash-Preview, its current API reference says thinking is always
on and defaults to maximum reasoning effort; `reasoning_split` controls
whether that content is separated or embedded in assistant content, but does
not disable thinking. This adapter ignores `reasoning_content`; if a provider
mixes non-JSON reasoning into assistant content, strict validation rejects the
completion and the log keeps only its hash and error metadata. The adapter
request explicitly sets `thinking.type` (default `adaptive`) and
`reasoning_split: true` for MiniMax, and includes both in the request hash and
decision metadata. MiniMax M3.1 requires an explicit `reasoning_effort` from
`low`, `medium`, `high`, `xhigh`, or `max`; the CLI rejects M3.1 without it.
M3.1 cannot disable thinking. M3 accepts `adaptive` or `disabled`; M2 models
cannot effectively disable thinking, so this runner rejects that misleading
setting. These controls can be frozen per configured policy slot with
`--minimax-thinking-a/b` and `--minimax-reasoning-effort-a/b`. The per-slot
`--max-completion-tokens-a/b` ceiling is also stored with the request. The
adapter captures only the constrained completion and brief rationale. That
rationale is an output supplied by the model; it is not a faithful or
independently verified record of the model's internal reasoning. Provider
usage objects are retained as reported. If a provider explicitly reports a
separate reasoning-token count, the analysis summary reports that number;
missing reasoning usage is never inferred. Malformed completions retain their hash and error metadata, not raw
text that might contain unrequested reasoning. Never record API keys. The
append-only ledger is a provenance trace, not proof that a provider's model
weights are unchanged. [MiniMax Chat Completions API](https://platform.minimax.io/docs/api-reference/text-chat-openai).

### Decision-ledger contract (schema version 1)

`series/decisions.jsonl` is UTF-8 JSON Lines: one immutable event per line.
Every row has `schema_version`, `event_type`, `match_id`, Unix-second
`timestamp`, `trace_origin`, and an `event_id`. The event ID is SHA-256 over a
canonical compact, key-sorted encoding of the row before `event_id` is added.
The writer uses a process-shared file lock and refreshes its event-ID index
under that lock before each append, so a runner and a backfill process cannot
interleave ledger writes or append the same event concurrently.
The `policy_input_sha256` is SHA-256 over the same canonical JSON encoding of
the exact structured user input sent to a hosted model (or the documented
`own_team`/`units` input for minimax). Legacy event imports retain their source
file/line identity and are marked `legacy_backfill`; source logs are not
rewritten.

- `decision`: seat and bridge, attempt number, observation ID/generation,
  structured observation and screenshot path, exact policy input/hash, policy
  implementation/prompt metadata, parsed action, and hosted inference data.
- `action`: accepted button pulse(s), originating seat/bridge, observation ID,
  and decision ID; only controller-verified inputs receive the decision ID.
- `exchange_submitted`: parsed attacker/defender/weapon choice and the FE7 UI
  state reached after the verified menu sequence.
- `decision_replanned` / `decision_interrupted`: stale-target replans and any
  policy choice that failed before a verified exchange completed.
- `policy_call_failed`: model/policy identity, request metadata available at
  failure, and sanitized error type/status. Provider response bodies and
  credentials are excluded.

The frozen hosted-policy metadata also records a `reasoning_capture` policy:
only the constrained, model-visible rationale is retained; provider-private
reasoning content is excluded; numeric reasoning-token counts are analyzed
only when the provider includes them in its usage object. This makes the
measurement boundary explicit in every `session.json`.

Hosted `inference` fields include request/prompt/response hashes, the exact
system prompt and structured input, start time, request ID, requested/resolved
model, latency, and token-usage object. The exact assistant `content` is saved
only after it validates as the constrained JSON action plus brief rationale.
The adapter never reads `message.reasoning_content`; MiniMax documents that
some model configurations return it separately and that thinking behavior may
follow provider defaults. This implementation does not expose that field to
the decision log. When malformed content is returned, the trace retains its
hash and validation error but not the raw content. This preserves a checkable
record without collecting hidden reasoning. Screenshot files remain local
artifacts; released traces must convert machine-specific paths to stable
match-relative paths or omit them while retaining hashes.

Run `python tools/audit_link_arena_ledger.py <path-to-decisions.jsonl>` before
analysis or release. It reports malformed rows and integrity/linkage issues.
For hosted decisions and failed hosted calls, it also requires the frozen rationale-only capture
policy; missing or altered policy metadata fails the audit. The analysis JSON
repeats that policy beside each agent's outcome and usage summaries.
The optional `--export-valid <derived-path.jsonl>` writes only parseable event
rows to a separate derived file and writes an adjacent `.audit.json` report;
it never edits the original append-only ledger.

### Proposed baselines

- Built-in depth-two minimax policy (current baseline; policy estimate is not a
  win probability and is not itself an outcome).
- Uniform legal-action policy with a frozen randomization seed, as a weak
  behavioral baseline.
- Each language model under a frozen prompt, structured output schema, and
  inference configuration.

The minimax baseline must be described as a hand-coded heuristic, not an
optimal solver. Its assumptions and supported weapon table should be versioned
with the source hash.

## 3. Experimental design (to preregister)

Use a frozen ROM hash, seed-save hash, emulator version, bridge/runtime commit,
team roster, and rules/settings manifest. The seed save is the current prepared
RAGNAROK roster; it is not a representative sample of all FE7 units or
strategies. Every match should begin from an isolated copy. The runner now has
`--alternate-agent-seats` for continuous runs. It groups completed games into
two-match blocks, chooses the first A/B-to-1P/2P orientation by SHA-256 of the
frozen `--seat-order-seed` and block index, then reverses policy slots for the
second match. The next orientation is derived from the persisted verified
game count, so a runner restart does not reset the schedule. Each
`session.json` records the schedule version, seed, block, match-in-block,
whether slots were swapped, and the model/policy metadata assigned to each
runner side. Use dedicated data directories for each frozen model pairing.
Before the first match in a hosted or seat-balanced run, the runner checks
prior session manifests and refuses to mix different models, settings, ROM/save
hashes, runtime/emulator fingerprints, seat-schedule modes, or seeds in that
data directory.
This controls seat allocation; it does not reset or pair FE7's combat RNG. If
the RNG state cannot be reliably reset or observed, record that limitation,
randomize run order, and do not call nominally identical launches deterministic
replays. Incomplete games remain excluded from the completed-game ordinal and
must be reported separately.

For the initial hosted engineering pilot, use a new dedicated data directory,
`--continuous --alternate-agent-seats --max-matches 2`, and a frozen seat-order
seed. This completes one two-game seat-swapped block, then stops starting
matches while keeping the final result visible. The cap counts all verified
results already present in that directory, so it must be empty at pilot start.
It bounds game count, not API spend or token use; per-game requests vary and
the runner has no provider-dollar budget control. A two-game pilot validates
the operational path only and is not confirmatory evidence or an adequate
sample for model ranking. Record any supervision stop or incomplete game.

Run all agents in a round-robin schedule against common baselines, rather than
only comparing a model to itself. Freeze prompt, model ID, provider, sampling
parameters, retry policy, context policy, and tool/controller version before
confirmatory runs. Resolve model aliases to concrete IDs at run time and store
the response's resolved model field when available. Chutes documents an
OpenAI-compatible endpoint with a live model catalog; MiniMax documents its own
OpenAI-compatible endpoint. Their shared request shape does not establish that
two similarly named model offerings have identical weights, snapshots, or
serving behavior. Record the provider and model as separate factors. [Chutes API
guide](https://chutes.ai/docs/guides/starter-guide), [MiniMax Chat Completions
API](https://platform.minimax.io/docs/api-reference/text-chat-openai).

Determine confirmatory match count with a prospective power or precision
analysis after a pilot estimates the paired-outcome variance. Freeze that
analysis before opening the confirmatory results. Do not select sample size or
exclude games based on which choice produces a favorable model ranking. Publish
the number of started, completed, invalidated, and supervision-stopped games
for every agent/seat cell.

## 4. Outcomes and analysis plan

### Primary outcome

The intended primary endpoint is FE7's official Link Arena final point total
and rank, parsed from the actual result screen and independently checked
against captured evidence. The current reader is calibrated against the two
archived final-result screens and rejects the terminal 30-point award panel.
In unattended play it advances only that recognized panel and persists a
score only when both clients agree with the terminal-roster winner across
repeated paired reads. This runtime path still requires live Zephyrus
validation. The current reader withholds scores containing uncalibrated glyphs
1 or 9, and does not infer results from intermediate panels. Until the runtime
path and full digit coverage are validated, report the synchronized
terminal-roster winner separately and do not treat it as FE7 points or rank.

### Secondary outcomes

- Match win/loss/draw, with seat-specific and paired seat-swapped summaries.
- Official point difference and final rank, only from verified structured
  result-screen records; report missing/unreadable screens and score conflicts.
- Match completion rate; safe-stop, invalid-action, and recovery rates.
- Accepted and rejected actions, replans, turns, exchanges, and verified
  controller inputs.
- Decision latency (request and end-to-end), timeouts/retries, input/output
  tokens, and cost under the provider's captured pricing/usage data.
- Minimax estimate and any model-reported confidence, clearly separated from
  game-engine outcomes.

Report per-agent denominators and 95% confidence intervals. For paired,
seat-swapped blocks, use a paired analysis and bootstrap at the block/match
level; do not treat individual turns as independent samples. Report the exact
resampling unit, number of resamples, and interval method. Predeclare any
additional hypothesis tests and correct for multiple confirmatory comparisons.
No statistical significance or model ranking is claimed in this draft.

## 5. Provenance and data release

Each match manifest links its match ID to ROM/save hashes, the Git revision
when available, a deterministic hash of the behavior-relevant runtime source
files, generated bridge-script hash, Python/platform versions, the mGBA binary hash, team and seat
assignment, provider/model configuration, start/end state, and
result-verification evidence. Decision traces should be JSONL with schema
versioning, stable IDs, timestamps, and
explicit missing/error fields. The per-match `events.jsonl`,
`minimax-autoplay.jsonl`, screenshots, `session.json`, series result ledger,
and series-wide `series/decisions.jsonl` provide decision and execution
provenance. Chutes and MiniMax adapters are implemented but require configured
model IDs and credentials before hosted calls occur. Run analysis should
consume exported decision/result records, not scrape the Twitch overlay.

The initial reproducible summary command is
`python tools/analyze_link_arena_benchmark.py <DataDir> --output <summary.json>`.
It verifies frozen session conditions and the decision-ledger audit, then
reports decisive win rates with Wilson intervals, official points with
match-level bootstrap intervals, seat-paired win score and official-point
difference intervals, decision reliability, latency, and provider-reported
token counts.
Bootstrap seed and resample count are recorded in the output. It does not
estimate cost without a versioned provider price schedule, and it does not
generate manuscript plots or support confirmatory claims by itself. The
analysis command takes a lock-consistent ledger snapshot; run it after freezing
the result series for publication-grade output. Bootstrap intervals are marked
not estimable when fewer than two independent resampling units are available.

The preliminary artifact-by-artifact inventory is in
[`LINK_ARENA_RELEASE_INVENTORY.md`](LINK_ARENA_RELEASE_INVENTORY.md). It records
which repository assets are already tracked, what rights evidence is present,
what remains unverified, and the gates for a sanitized release. Root MIT terms
do not establish rights to bundled game-derived art, screenshots, ROM/save
files, or fonts. Do not include those materials in a paper archive without
clearance. Keep raw provider credentials, machine paths, Twitch viewer/chat
data, and unreviewed provider outputs out of released artifacts. Publish
hashes, schemas, source, and derived decision/outcome data only after the
provider, game-content, privacy, and venue checks in the inventory are complete.

## 6. Limitations and threats to validity

1. **Narrow environment.** One FE7 version, one prepared team/save, one Link
   Arena map/ruleset, and currently one fixed team composition cannot support
   broad claims about strategy games or general agents.
2. **Outcome gap.** The result reader recognizes the standard final-rank
   layout and the shifted view shown by the opposite linked client. Manual
   calibration fixtures parse 520–346 and 576–288 and reject retained bonus
   transition panels. The deployed reader recorded paired FE7 results in games
   eleven and fourteen. Game ten's shifted 1P view was missed by the original
   reader; merged PR #18 added that layout. Game twelve's final screen arrived
   too late for two paired reads in the old 4.5-second window. Merged PR #20
   extended sampling to 12 seconds without relaxing exact-screen,
   paired-agreement, or terminal-winner checks. The updated reader was deployed
   before game fourteen, which stored a paired 1P 576–288 2P score 6.39 seconds
   after terminal confirmation and recorded both bridge layouts. At 21:40 UTC,
   two of fourteen results had official points; W–L–D and the partial point
   totals still do not constitute a complete official-score record.
3. **Uncontrolled randomness.** FE7 combat uses RNG. A file-level save hash
   does not prove identical RNG state or reproducible trajectories across
   launches. Pairing and seat balancing mitigate but do not remove this issue.
4. **Approximate baseline.** Minimax uses a small hand-coded combat model and
   partial weapon coverage. It is a reference policy, not ground truth or an
   optimal-play oracle.
5. **Model/provider drift.** API-served models may change behind names or
   provider routing. Record exact IDs, dates, request settings and usage; results
   remain specific to those serving conditions.
6. **Prompt and observation dependence.** Structured state favors agents that
   use tabular information; a vision interface is a distinct task. Prompt
   engineering and output repair can materially change results and must be
   frozen and disclosed.
7. **Reasoning observability.** The benchmark records the model-visible action
   completion and a brief user-visible rationale, not private chain-of-thought.
   Provider-side reasoning traces can be omitted, separately exposed, hidden,
   or changed by serving defaults. We cannot make claims about their contents,
   correctness, or causal role in a decision.
   For MiniMax M3.1, record the required explicit `reasoning_effort`; freeze
   thinking mode, effort, and completion-token ceiling per seat before a
   confirmatory run. The request hash and inference metadata preserve those
   settings. Never save the separate `reasoning_content` field.
8. **Execution and timing.** The deterministic controller removes much input
   navigation variance, but emulator timing, capture coherence, link behavior,
   and safe supervision stops still affect completion.
9. **Small and selected samples.** Always-on stream games are convenient but
   are not a randomized research sample. Report exploratory runs separately
   and avoid post hoc exclusions.
10. **Rights and release.** FE7 game assets and ROM images are third-party
   copyrighted materials. Public reproducibility may be limited to hashes,
   schemas, code, and legally distributable derived traces.

## 7. Status before a confirmatory study

At this protocol revision (2026-09-28), no hosted-model requests or hosted
benchmark results are included. The unattended Zephyrus stream is running the
repository's hand-coded depth-two minimax policy on both seats; this is not the
MiniMax API model. Neither `CHUTES_API_KEY` nor `MINIMAX_API_KEY` was present
in Zephyrus' user or machine environment during the readiness check. The
Windows runner now has an interactive provisioning script that encrypts keys
with current-user DPAPI and loads them only into the task process; the
scheduled-task installer accepts fixed per-seat hosted provider/model choices
and fails closed if the selected provider credential is unavailable. This
changes readiness tooling, not the live task: the current series remains local
minimax. Choose exact model IDs, record provider plan/configuration, assign a
separate `DataDir` to each experimental condition, and deliberately deploy a
hosted condition at a safe match boundary before making inference calls.

### Exploratory operations checkpoint (2026-09-28)

The unattended local-minimax series has six completed games, all recorded as
2P wins by synchronized roster elimination; the seventh game began through the
automatic handoff and was in setup at the latest checkpoint. This is one
prepared RAGNAROK team/save, fixed seat roles, and a small, non-random
operational sample. Treat it only as harness/stream validation: it is not a
model comparison, an official points result, or a confirmatory estimate. Do not
pool it into future confirmatory results.

At the end of games four and six, read-only captures showed in-game team panels
at 564/288 and 576/288, respectively, while FE7 displayed its “Each unit
receives 30 extra pts.” transition. Neither capture includes the subsequent
ranking screen, so those panel values are not reported as final official
totals. The captures are retained in
[`LINK_ARENA_MATCH_REPORT.md`](LINK_ARENA_MATCH_REPORT.md).

At 19:52 UTC on 2026-09-28, a lock-consistent decision-ledger snapshot
contained 3,851 parseable events across 28 match IDs: 554 policy decisions,
536 submitted exchanges, 2,760 verified button actions, and one replan event.
The audit found zero duplicate event IDs, event-hash mismatches, missing
common fields, unknown event types, unlinked accepted actions/exchanges, or
provider-private reasoning fields. Of the valid rows, 1,974 came from legacy
backfill and 1,877 were live writes. All 554 decisions are attributed to
`local/unknown`: these are hand-coded minimax policy choices, not LLM requests,
completions, or rationales. The audit therefore reports zero hosted decisions
with a visible rationale. One malformed historical line (line 2010 in this
snapshot, 39 bytes) remains in the original source and is reported by the
auditor; it is not rewritten or silently dropped. The audit command therefore
returns nonzero for this preserved malformed line. Its optional valid-row
export contains the 3,851 parseable events and an audit report, while
preserving the original ledger separately.

The continuous series had eight completed games at 19:55 UTC: 1P had two wins
and 2P had six. The first six were 2P survivor wins; games seven and eight
were 1P survivor wins. Match `20260928T195429Z-ed9dda` had entered automatic
setup for game nine at that checkpoint. This remains a fixed-seat,
single-roster operational sample, not a model comparison or confirmatory
result. The verified FE7 final-screen score reader described above was being
prepared but was not yet deployed to the live runner at this checkpoint.

At 20:44 UTC, the live decision-ledger audit contained 4,885 valid rows across
31 match IDs: 800 decisions, 782 submitted exchanges, 3,302 accepted input
actions, and one replan. It found no duplicate IDs, event-hash mismatches,
missing common fields, unknown event types, unlinked actions/exchanges, or
provider-private reasoning keys. All 800 decisions remain `local/unknown`
hand-coded minimax decisions, with zero hosted model completions or visible
rationales. There were 1,974 legacy-backfill rows and 2,911 live rows. The same
39-byte malformed historical line 2010 (SHA-256
`1aad963f1b81decd4988583e25fbbc3ba2839f05bac8df529d4329770f7686af`) remains
preserved and makes the audit exit nonzero; the 4,885 valid rows are reported
without rewriting or dropping the original source.

At 20:46 UTC, game eleven (`20260928T202914Z-979bda`) completed as a 2P
survivor win and also produced the first official paired FE7 result in the live
series: 2P 576–288 1P. The reader observed two stable paired reads and verified
that the 2P screen winner matched the terminal roster winner. The series then
showed 11 games, 1P 3 wins, 2P 8 wins, one scored game, and official point totals
of 1P 288 and 2P 576. The two bridge screenshot hashes are retained in its
score record. Game twelve (`20260928T204610Z-822535`) began automatically
afterward.

At 21:42 UTC, a fresh lock-consistent audit snapshot contained 5,927 valid
events across 35 match IDs: 1,024 decisions, 1,006 submitted exchanges, 3,896
accepted button actions, and one replan. It found no duplicate event IDs,
event-hash mismatches, missing common fields, unknown event types, unlinked
actions/exchanges, or provider-private reasoning keys. All 1,024 decisions
were still attributed to `local/unknown`; the snapshot had zero hosted model
completions or visible rationales. There were 1,974 legacy-backfill and 3,953
live rows. The preserved malformed 39-byte historical line 2010 remains the
only malformed row (SHA-256
`1aad963f1b81decd4988583e25fbbc3ba2839f05bac8df529d4329770f7686af`) and keeps
the audit command's exit status nonzero.

The hosted-model adapters record the exact structured input and the validated
assistant action plus a short user-visible rationale, along with provider/model
IDs, request parameters, usage, latency, and response hashes. This visible
rationale is not private chain-of-thought. Provider-only reasoning payloads
are deliberately ignored. A presence-only credential check found
`CHUTES_API_KEY` and `MINIMAX_API_KEY` unset in the local shell and in
Zephyrus's process, user, and machine environment scopes. The current live
series therefore contains minimax-policy decisions, not hosted LLM decisions.

At 21:40 UTC, game fourteen (`20260928T212305Z-aced65`) completed as a 1P
survivor win and added a second official paired FE7 score, 1P 576–288 2P. Both
bridge captures independently parse to the same score; the result persisted
6.39 seconds after synchronized terminal confirmation with two stable paired
reads and a terminal-winner match. The record stores
`layout_by_bridge: {A: standard, B: standard}` and screenshot hashes
`813903f9857c520179e9da4d7d89d7c3075b80d01664fcf9a4bd3f1769a58bde` and
`f7b44e1772008a687105089609d4490e46044c12b2b3c7bd52ec538e81bbc588`. The
series now has fourteen results (1P 5 wins, 2P 9), two scored games, and
cumulative official totals 1P 864 / 2P 864. Game fifteen
(`20260928T214009Z-052371`) began automatically afterward.

By 21:57 UTC, game fifteen completed as a 2P survivor win with a paired
official score of 2P 576–288 1P. The reader agreed across two stable paired
reads, verified the result against the terminal roster, and recorded the
standard layout on both bridges. The two screen hashes are
`c916d774b4ec8760bf36980d6c0f1ae7756051990b49b86425760633c0e0cf44` and
`872a261a63367ba462ff8939d111a882e991a40295c4be6053f1352f5c3be82c`. The live
series has fifteen games (1P 5 wins, 2P 10), three with official scores, and
totals 1P 1,152 / 2P 1,440. These are still exploratory fixed-seat
depth-two-minimax runs. The updated result reader has now recorded three live
paired scores; shifted-layout support remains offline-only and full digit
coverage remains incomplete. By 21:58 UTC, game sixteen
(`20260928T215710Z-b02656`) had automatically entered `start_link_battle`
setup under the same local-minimax configuration.

By 22:16:57 UTC, game sixteen had completed as another 2P survivor win and
produced the fourth paired official FE7 score: 2P 576–288 1P. Both bridges
agreed across two stable reads, the screen winner matched the terminal roster,
and both layouts were standard. The screen hashes are
`aece3085f2c6f04e22cbb80cf58bfb1c2cfcbb9dbaff440a06e653acc36ace01` and
`13756396d40430cd08ea230306b381c850c94b8dcc239b1d27cc5c65fe54ab0e`. The
series had sixteen games (1P 5 wins, 2P 11), four scored games, and cumulative
FE7 points 1P 1,440 / 2P 2,016. Game seventeen
(`20260928T221409Z-505f8b`) had started automatically; at the capture it was
on player phase, turn 1, with 4/5 and 5/5 units alive. These remain exploratory
fixed-seat minimax results, not hosted-model evaluations or confirmatory data.
At 22:21:53 UTC, the same game was still progressing normally at player-phase
turn 6, with 3/5 1P units and 4/5 2P units alive. Game seventeen later
completed as a 2P survivor win with paired FE7 points 2P 576–288 1P. Both
bridges agreed across two stable reads, matched the terminal roster, and used
the standard layout; screenshot hashes are
`6ffbf27a16ef72114576b0991f0dc3ff25a643a546271d565d15b3d5081be0b2` and
`413f7431ec241f4bf159f543407f6b85d5c9a7d6b12b2419ca7187ff5068db81`. The
series reached seventeen results (1P 5 wins, 2P 12), five with verified FE7
points totaling 1P 1,728 / 2P 2,592. Game eighteen
(`20260928T223105Z-e65f8a`) began automatically. At 22:34:39 UTC it was in
player-phase turn 2 with all five units alive on both sides and no runner error.

The 22:16:57 UTC decision-ledger audit found 6,456 valid events across 37
matches: 1,090 decisions, 1,072 submitted exchanges, and 4,293 verified button
actions. All decisions remained `local/unknown` minimax decisions; the audit
found zero hosted rationales and zero provider-private reasoning fields. It
also found no duplicate IDs, hash mismatches, missing common fields, unknown
event types, or unlinked actions/exchanges. The same preserved malformed
39-byte legacy line 2010 remains, so the audit still exits nonzero; no source
line was rewritten. The live 24/7 stream is therefore gathering controller
and minimax benchmark traces, but not LLM thoughts or rationales yet.

A second lock-consistent audit at 22:34:39 UTC, after game seventeen and early
game-eighteen decisions, found 6,695 valid events across 38 match IDs: 1,120
decisions, 1,102 submitted exchanges, and 4,472 verified button actions. The
1,974 legacy-backfill and 4,721 live rows all remained `local/unknown`; hosted
rationales and provider-private reasoning fields were both zero. No duplicate
IDs, hash mismatches, missing common fields, unknown events, or unlinked
accepted actions/exchanges were found. Only the preserved malformed legacy
line 2010 remains; the audit exits nonzero for that line.

At approximately 22:46 UTC, a further live audit contained 6,891 valid events
across the same 38 match IDs: 1,146 decisions, 1,128 submitted exchanges,
4,616 verified button actions, and one replan. The 1,974 legacy-backfill and
4,917 live rows remained `local/unknown`; hosted decisions with visible
rationales and provider-private reasoning fields were both zero. There were no
duplicate IDs, event-hash mismatches, missing common fields, unknown event
types, or unlinked actions/exchanges. The preserved malformed 39-byte line
2010 remains the sole reported audit defect, with SHA-256
`1aad963f1b81decd4988583e25fbbc3ba2839f05bac8df529d4329770f7686af`; no
source evidence was rewritten.

At 22:47:11 UTC, game eighteen was still active in the public minimax stream
(`20260928T223105Z-e65f8a`), at turn 15 with one 2P survivor and no observed
winner. The series still had seventeen verified results (1P 5 wins, 2P 12),
five verified official scores, and totals of 1P 1,728 / 2P 2,592. The strict
benchmark analyzer was also run read-only against this historical public
`DataDir`; it correctly stopped at match `20260927T151504Z-570000`, whose
manifest lacks frozen seat/policy metadata. Thus the public minimax score and
decision history remain auditable operational evidence, but the full mixed
history is not eligible for the new frozen-study analysis. No missing fields
were synthesized. New hosted experiments must use a fresh data directory and
current manifests.

- [x] Calibrate the fail-closed reader against archived and live final-result
  screens and reject four captured intermediate bonus panels. The standard
  layout and 12-second paired-read window have three successful live scores.
  `layout_by_bridge` persisted as standard on both views for game fourteen.
  Shifted-layout support has offline fixture validation but no live sample yet.
  Complete 0–9 glyph coverage and broader independent validation remain open.
- [x] Deploy and inspect the series-wide decision ledger on Zephyrus; validate
  decision IDs join policy choices to every verified input. The one malformed
  historical source line remains explicitly flagged as described above.
- [ ] Configure Chutes and MiniMax provider adapters with approved model IDs
  and protected credentials; freeze exact model IDs and plan/API configuration.
- [ ] Define legal action contract, prompt, parsing/repair behavior, timeout,
  retry/fallback, and safe-stop semantics for each agent.
- [ ] Freeze provider reasoning/thinking configuration as an explicit study
  condition before hosted evaluation; the adapter excludes private reasoning
  payloads and records only the validated visible action/rationale.
- [x] Implement deterministic randomized seat-swapped pairs for continuous
  runs and persist assignments with policy metadata in each session manifest.
- [ ] Freeze the seed and team/save manifest for each study run; characterize
  side advantage and RNG reset behavior. Seat pairing does not control FE7 RNG.
- [ ] Run a pilot, estimate variance/latency/cost, perform prospective power or
  precision analysis, then preregister confirmatory hypotheses and exclusions.
- [x] Add an initial analysis script that checks ledger consistency, frozen
  conditions, seat-swap completeness, and confidence intervals from one study
  directory.
- [ ] Generate manuscript tables/figures from a completed hosted pilot, add a
  versioned cost schedule, and validate every output against released data.
- [x] Add a ledger audit/export command that verifies event hashes, duplicate
  IDs, action/exchange joins, malformed lines, and private-reasoning-key absence.
- [ ] Complete a venue-specific reproducibility, ethics, authorship, and
  third-party-asset/license checklist before public submission.

## References

- Liu et al. (2024). *AgentBench: Evaluating LLMs as Agents*. ICLR 2024.
  [Paper](https://arxiv.org/abs/2308.03688).
- NeurIPS (2026). *Evaluations & Datasets Reviewer Guidelines*.
  [Guidelines](https://neurips.cc/Conferences/2026/EvaluationsDatasetsReviewerGuidelines).
- NeurIPS. *Paper Checklist*.
  [Checklist](https://neurips.cc/public/guides/PaperChecklist).
- Chutes. *Starter Guide / API documentation*. Accessed 2026-09-28.
  [Documentation](https://chutes.ai/docs/guides/starter-guide).
- MiniMax. *Chat Completions API documentation*. Accessed 2026-09-28.
  [Documentation](https://platform.minimax.io/docs/api-reference/text-chat-openai).
- MiniMax. *Token Plan*. Accessed 2026-09-28. API access and quotas depend on
  the account's current plan and key configuration; an interactive subscription
  should not be assumed to include unlimited API inference.
  [Plan details](https://platform.minimax.io/subscribe/token-plan).

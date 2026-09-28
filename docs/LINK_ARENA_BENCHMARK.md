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
traces for audit. The current system is an engineering prototype: its live
series scoreboard records synchronized elimination outcomes, not FE7's numeric
Link Arena points or final ranking. We will not report model rankings or
scientific conclusions until result parsing, experimental controls, sample size,
and release rights have been validated and preregistered.

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
brief user-visible rationale. The adapter does not ask the model to reveal
private reasoning, does not read or persist provider-only `reasoning_content`
fields, and does not publish hidden chain-of-thought. The MiniMax API documents
that some models can return a separate `reasoning_content` field and that
thinking behavior can depend on model defaults; this harness intentionally
discards that field. It captures the constrained completion and brief rationale
only. That rationale is an output supplied by the model; it is not a faithful
or independently verified record of the model's internal reasoning. Malformed
completions retain their hash and error metadata, not raw text that might
contain unrequested reasoning. Never record API keys. The append-only ledger is
a provenance trace, not proof that a provider's model weights are unchanged.

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
strategies. Every match should begin from an isolated copy. Randomize which
policy receives 1P and 2P, and use paired seat-swapped blocks for each
initialization condition. If FE7's RNG state cannot be reliably reset or
observed, record that limitation, randomize run order, and do not call nominally
identical launches deterministic replays.

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
against captured evidence. Until that parser is implemented and validated, the
only automated series outcome is a synchronized terminal-roster winner/draw.
That survivor result is a proxy and must not be described as the numeric FE7
score, official ranking, or tournament points.

### Secondary outcomes

- Match win/loss/draw, with seat-specific and paired seat-swapped summaries.
- Official point difference and final rank, once verified structured parsing is
  available.
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

Each match should have a manifest linking its match ID to the ROM/save hashes,
runtime and emulator versions, team and seat assignment, provider/model
configuration, start/end state, and result-verification evidence. Decision
traces should be JSONL with schema versioning, stable IDs, timestamps, and
explicit missing/error fields. The per-match `events.jsonl`,
`minimax-autoplay.jsonl`, screenshots, `session.json`, series result ledger,
and series-wide `series/decisions.jsonl` provide decision and execution
provenance. Chutes and MiniMax adapters are implemented but require configured
model IDs and credentials before hosted calls occur. Run analysis should
consume exported decision/result records, not scrape the Twitch overlay.

Before public release, separate results from credentials, Twitch identifiers,
and machine-specific paths. Do not redistribute commercial ROM or save files,
or copyrighted game graphics/audio, unless distribution rights are confirmed.
Publish hashes, schemas, code, derived action/outcome data, and reproduction
instructions where permitted; state exactly which artifacts cannot be shared
and why. Review the applicable game/emulator/API licenses and provider terms
before collection or release. Keep live chat out of the research dataset unless
a separately reviewed protocol obtains appropriate consent and handles
personal data.

## 6. Limitations and threats to validity

1. **Narrow environment.** One FE7 version, one prepared team/save, one Link
   Arena map/ruleset, and currently one fixed team composition cannot support
   broad claims about strategy games or general agents.
2. **Outcome gap.** Current automation records only stable terminal roster
   elimination. The official FE7 point/rank screen is not yet parsed into the
   ledger, so the current W–L–D stream metric is not a complete official score.
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
in Zephyrus' user or machine environment during the readiness check. Provision
credentials through approved host secret management, choose exact model IDs,
and record provider plan/configuration before making any hosted calls.

- [ ] Verify official result-screen parser against multiple independently
  reviewed captures; reconcile points, rank, surviving units, and W–L–D.
- [ ] Deploy and inspect the series-wide decision ledger on Zephyrus; validate
  decision IDs join policy choices to every verified input.
- [ ] Configure Chutes and MiniMax provider adapters with approved model IDs
  and protected credentials; freeze exact model IDs and plan/API configuration.
- [ ] Define legal action contract, prompt, parsing/repair behavior, timeout,
  retry/fallback, and safe-stop semantics for each agent.
- [ ] Freeze team/save manifest; characterize side advantage and RNG reset
  behavior; decide paired seeds/seat swaps.
- [ ] Run a pilot, estimate variance/latency/cost, perform prospective power or
  precision analysis, then preregister confirmatory hypotheses and exclusions.
- [ ] Create an analysis script that checks ledger consistency, produces
  confidence intervals, and reproduces all tables/figures from released data.
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

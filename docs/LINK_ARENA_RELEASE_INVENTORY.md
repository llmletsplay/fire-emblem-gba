# FE7 Link Arena Bench release and rights inventory

**Status:** preliminary internal inventory; this is not legal clearance.
**Inventory date:** 2026-09-29
**Repository snapshot:** `caa07f3` (state reviewed before this inventory refresh)

This inventory separates the benchmark's reproducible research materials from
game content, provider content, and credentials. It records what is in the
repository and which evidence is missing; it does not determine fair use,
license scope, or whether a particular distribution is lawful. Recheck the
applicable terms when data are collected and before a paper, stream archive,
or dataset is released.

## Inventory

| Material | Current location/state | Evidence checked | Release disposition |
|---|---|---|---|
| Runner, controller, analyzer, tests, and documentation | Tracked source and docs | Root `LICENSE` is MIT and applies to the Software and associated documentation. | Candidate for source release with notices and dependency inventory. Confirm each contributor and dependency; the root MIT file does not clear unrelated media assets. |
| Benchmark protocol, configuration, hashes, and aggregate results | Paper and per-match manifests/series on the host | Current public stream is exploratory; the strict analyzer rejects legacy manifests that lack frozen policy metadata. | Publish protocol, software/runtime hashes, and reproducible aggregate outputs. Do not present the current minimax series as an LLM evaluation. |
| Decision ledger and model-visible completions | Canonical `series/decisions.jsonl` on Zephyrus; exact pre-cleanup bytes at `series/archive/decisions.pre-legacy-prune.d84be674db4b.jsonl` | On 2026-09-28, a lock-protected migration removed 1,974 redundant `legacy_backfill` rows and quarantined one malformed 39-byte fragment (SHA-256 `1aad963f1b81decd4988583e25fbbc3ba2839f05bac8df529d4329770f7686af`). The complete pre-cleanup ledger is preserved with SHA-256 `d84be674db4bcfe81cb2fa294c5835c161c0e7e96e5634eb2eed484a864c5a90`; source per-match logs remain intact. At the latest audit near 2026-09-29 00:34 UTC, the canonical file had 6,457 valid `live` rows, including 1,091 local-policy decisions, and no malformed rows, duplicate IDs, event-hash mismatches, missing fields, unknown events, unlinked actions/exchanges, or private-reasoning keys. No hosted-model decisions are present. Provider-private reasoning content is excluded; provider-reported reasoning-token counts are retained only when included in usage. A live roster observation also recorded one character at 77 current / 60 maximum HP; cause and save provenance remain unresolved. | Keep the canonical ledger, archive, and per-match source logs internal for now. A public derivative needs relative paths, secret/identifier checks, a documented schema, and review of game-data and provider terms. The audit export only filters malformed rows; it does not sanitize paths or clear rights. |
| ROM, prepared save, and XPS/save-state candidate | Local/host `roms/`; ignored by Git | `roms/README.md` and `.gitignore` prohibit committing these files. `git ls-files roms` contains only the README. | Do not include in an artifact archive. Provide hashes, environment requirements, and lawful acquisition/preparation instructions only after checking applicable terms. Do not link to ROM downloads. |
| Captured FE7 evidence and overlay concept images | Ten tracked PNGs in `docs/link_arena_evidence/` | Git inventory confirms these files are already in the repository; images visibly contain game/stream graphics. No per-image permission record was found in the checked project docs. | Exclude from a new research release unless rights are confirmed. The existing repository history is separate from this proposed archive and is not evidence of permission. |
| Other bundled media | 149 tracked files under `assets/`: 90 PNG, 49 GIF, 2 JPG, 5 TTF, 2 README, and one OBS JSON. Includes 57 files under `assets/portraits`, 80 under `assets/shared`, four branding images, and a sponsor image. | `assets/sprites/README.md` names Spriters Resource; `assets/maps/README.md` names Fire Emblem Wiki, Fandom, and in-game screenshots. These are directory-level source pointers, not file-level attribution or licenses. No per-file license inventory was found. | Do not include in the benchmark archive until each file has a traceable source, applicable license/permission, and required attribution. Root MIT is not treated as a license for these files. They are already tracked in the public project repository. |
| Fonts | Five tracked TTF files under `assets/fonts/` and `assets/shared/fonts/` | No font license or attribution sidecar was found in the tracked asset inventory. | Verify each font's upstream license and required notices before redistribution; otherwise omit. |
| OBS scene and stream overlay | `assets/obs/FE7 Link Arena.json`; `src/link_arena/stream_overlay/` | Scene JSON is tracked. A key-name scan found no populated credential-named fields; the scene still contains machine/source configuration that should be normalized before sharing. | Overlay source is a code-release candidate. Sanitize machine paths, source identifiers, and account-specific configuration from the scene export; never include stream keys or provider credentials. |
| Live chat and Twitch material | Twitch chat appears as an OBS browser source; the runner ledger does not ingest chat | The study protocol explicitly excludes chat from the research dataset absent a separate consent/privacy protocol. | Do not archive chat or viewer identifiers. Keep stream capture separate from research traces unless the protocol is amended and reviewed. |
| mGBA executable and dependencies | Installed on Zephyrus; not tracked as a project binary | Upstream mGBA identifies its license as MPL-2.0 and lists third-party dependencies. The exact installed executable and dependency bundle still require an inventory. | Record version/hash for reproducibility. Do not redistribute the installed binary or a bundle until its exact notices, source obligations, and dependency licenses are checked. |
| Hosted provider requests, outputs, and billing records | No hosted inference calls or model completions yet; the Chutes adapter can make an unauthenticated, read-only public `/v1/models` catalog request to freeze selected rates before a match. The Windows credential setter is installed, but the latest presence-only check found no DPAPI credential file. | Chutes' current terms require PAYGO for high-concurrency, high-volume, or otherwise highly automated use. Chutes states public API request/response content is not persisted. MiniMax Token Plan has shared quota/rate limits; MiniMax's Open Platform terms and privacy policy are service-specific and may permit use of input/output to operate and improve its services. | Before a pilot, record the exact account plan, model IDs/licenses, region, terms/policy versions, price schedule, and whether the planned unattended call volume is allowed. Do not publish keys, billing identifiers, or raw provider logs without review. These provider statements are not independently audited guarantees. |
| Twitch gameplay broadcast | Existing stream on `llmletsplay`; not an academic data artifact | Nintendo's Game Content Guidelines cover video and livestreams for individual consumers, encourage creative input/commentary, and list modified/illegally obtained software and unauthorized emulation/circumvention among content they may object to. The project uses mGBA; this inventory does not resolve how the guidelines apply to this setup. | Before relying on the stream or screenshots as a public research artifact, review the current Nintendo guidelines and platform/account terms for this exact use. Do not describe the stream as Nintendo-approved. |

## Provider and rights references checked

- Chutes, [Terms of Service](https://chutes.ai/terms) and [Privacy Policy](https://chutes.ai/privacy), pages state an update date of 2026-03-16. Recheck at the actual pilot; the terms can change.
- MiniMax Open Platform, [Terms of Service](https://platform.minimax.io/protocol/terms-of-service) (effective 2026-03-30) and [Privacy Policy](https://platform.minimax.io/protocol/privacy-policy). Confirm the terms for the exact API plan/account.
- MiniMax, [Token Plan](https://platform.minimax.io/subscribe/token-plan) guidance on API keys, rolling quotas, rate limits, and production use; recheck before running an unattended pilot.
- Nintendo, [Game Content Guidelines for Online Video & Image Sharing Platforms](https://www.nintendo.co.jp/networkservice_guideline/en/index.html) (updated 2024-09-02), plus any applicable [Community Tournament Guidelines](https://en-americas-support.nintendo.com/app/answers/detail/a_id/63433/p/171/c/693).
- mGBA upstream, [repository and license information](https://github.com/mgba-emu/mgba).

## Release gates

1. Complete a file-level source/license/permission manifest for all bundled
   media and fonts; remove or replace uncleared items from any research archive.
2. Decide separately how to handle the ten already-tracked FE7 evidence PNGs;
   do not treat repository presence as permission to redistribute them in a
   paper supplement.
3. Record exact emulator binary/version/hash and applicable notices; record
   the ROM/save hashes without including the ROM, save, or XPS in the release.
4. Before hosted inference, verify model availability, model/license terms,
   provider plan suitability for unattended volume, usage limits, and a dated
   price schedule. Store only terms/version metadata and provider-reported
   usage needed for the study.
5. Build and review a sanitized decision-data export. Preserve the raw ledger
   internally, report malformed/invalid rows, and never synthesize missing
   provenance.
6. Confirm the release venue's ethics, authorship, data, citation, and asset
   checklist. If any chat or viewer data are later proposed, create a separate
   consent and privacy protocol first.

The current repository supports reproducible code and protocol work, but this
inventory is **not a release clearance**. The raw research dataset and public
stream assets remain on hold pending the gates above.

# Quality Loop Guide

Read this before tuning `typo_corrector.py`, `meaning_crosscheck.py`, or the
convergence rule in `quality_loop.py`. It's the "why", not just the "what".

## Why a loop instead of one pass

A single OCR→JSONL pass on a scanned dictionary reliably produces:
- character-confusion typos (rn/m, l/1/I, O/0, diacritic drops)
- duplicate headwords across pages with slightly different OCR reads
- glosses that silently drift from the pivot meaning

None of these are visible from the output alone — you need a second pass to
check the first pass's work. Hence: loop until a pass adds nothing new.

## OCR confusion tricks (typo_corrector.py)

Common confusion pairs to seed into `<language>_phonology.md`:

- `rn` → `m` (very common in scanned dictionaries, small serif fonts)
- `1` / `I` / `l` — three-way confusion, resolve via orthography validity
  (if the language has no `1` digit in headwords, `1` → `l`)
- `0` / `O` — same idea, resolve via position (digit-only in page numbers,
  never in headwords)
- Diacritic drops (é→e, ñ→n, etc.) — if the language's orthography is
  diacritic-sensitive, a dropped diacritic changes valid-word status, which
  is exactly the signal `_is_valid_orthography` checks for
- Doubled/dropped letters from broken/faint print — harder to catch
  mechanically; these usually end up as low-confidence flags rather than
  auto-fixes, which is correct behavior, not a gap to close

**Rule of thumb:** if a fix requires knowing what the word *should* mean
(rather than just what characters are valid), it doesn't belong in the
auto-fix tier — flag it.

## Meaning cross-check tricks (meaning_crosscheck.py)

- **Duplicate headword, different pass** — same word extracted twice with
  different glosses almost always means either (a) genuine polysemy (keep
  both, tag senses), or (b) one extraction has an OCR-mangled gloss. The
  loop can't tell which mechanically — that's what `needs_web_check` is
  for (see below).
- **Cross-check against the pivot, not just within-language** — whatever
  the pivot/gloss language is for this dictionary (`language.pivot_name`),
  its text is usually cleaner OCR than the local-language script (better
  font/training-data support in most OCR engines). When a local-language
  reading looks suspicious, trust the pivot gloss's stability over the
  headword's.
- **Existing corpus as ground truth** — if `existing_corpus` already has a
  resolved entry for a headword, any new pass that disagrees with it is
  the one on trial, not the old entry. Don't let a later pass silently
  overwrite a previously-resolved (human-reviewed) entry.

## Smart flagging: patterns over individuals (pattern_spotter.py)

Reviewing flags one at a time misses the forest for the trees. After every
pass, `PatternSpotter` looks across *all* the flags raised that pass for:

- **Recurring substitutions** — the same `(before, after)` OCR fix was
  attempted and failed validation on 3+ different headwords. That's not 3+
  unrelated typos, it's one wrong or missing rule in the phonology
  reference. Fix the rule, not the individual entries.
- **Bad-page clusters** — a disproportionate share of a pass's flags trace
  back to the same page. That's a scan-quality problem, not a word-level
  one — re-scan the page rather than reviewing each flagged entry on it.
- **Issue-type hotspots** — one issue type dominating a pass (e.g. 80% of
  flags are `low_confidence`) points at a systemic cause (DPI, source
  quality) worth addressing before grinding through individual flags.

Each `PatternInsight` includes a `suggested_action` and a confidence score
(roughly: how many entries triggered it, weighted toward "yes this is
real" as the count grows). Written to `pattern_insights.md` every pass —
check it before `flagged_terms.md`.

## Optional web verification (web_verification.py)

Some flags are genuinely ambiguous from the dictionary alone — a meaning
conflict between two glosses, a duplicate headword with diverging senses,
or an entry that's stayed low-confidence across multiple correction
passes. For these (and only these — see the agent spec's "scalpel, not a
reflex" principle), the flag carries `needs_web_check=True` and a
pre-built `suggested_query`.

The *script* never performs the search — it has no general internet
access, and deciding what a search result means is exactly the kind of
judgment call that belongs to the agent running the skill, not a hardcoded
heuristic. The agent runs `web_search(query)`, paraphrases what it finds
(same copyright discipline as anywhere else — no verbatim quoting), and
calls `WebVerificationQueue.record_evidence(...)` to attach the finding to
the flag and mark it resolved if the evidence is conclusive.

## Convergence rule

A pass is "clean" when it raises zero *new* flags. Concretely:
- Flags open before this pass that aren't re-raised are marked resolved
  (the underlying issue didn't reproduce — either it was fixed between
  passes or the source data changed).
- The loop stops when `flags_raised == 0` for a pass, or `max_iterations`
  is hit (default 5 — raise this only if a language's dictionary is
  unusually noisy; more passes without human intervention rarely helps
  once you're past 3-4).

## Confidence scoring

- Digital-text entries start at `1.0` and are never auto-corrected (nothing
  to fix — OCR wasn't involved).
- OCR entries start at the page's mean OCR confidence.
- Each applied auto-fix nudges confidence down slightly
  (`CONFIDENCE_PENALTY_PER_FIX` in `typo_corrector.py`) — a corrected entry
  is trustworthy but not "as good as never having had a typo".
- Anything below `CONFIDENCE_FLOOR` (default `0.75`) is always flagged,
  even if no specific typo was caught — low confidence is itself a reason
  for a human read.

# <Language Name> Phonology & Orthography Reference

Copy this file to `outputs_<lang>/<language_code>_phonology.md` (e.g. `outputs_sentani/sentani_phonology.md`) and fill it in before
running the extraction loop for a new language. `typo_corrector.py` parses
the `## Valid characters` and `## OCR confusion pairs` sections directly —
keep those headers exact.

## Language

- Code: `<iso-or-project code, e.g. lni>`
- Family: `<e.g. Trans-New Guinea>`
- Script: Latin, with/without diacritics — specify which diacritics are used

## Valid characters

<!--
List every character (lowercase) that can legally appear in a headword,
space-separated or one per line, e.g.:
a b c d e f g h i j k l m n o p q r s t u v w y ' 
Add diacritic variants explicitly if used, e.g. é ñ ŋ
-->

## OCR confusion pairs

<!--
One per line, format: - `bad` → `good`
Order matters if pairs overlap — earlier lines apply first.
-->
- `rn` → `m`
- `1` → `l`
- `0` → `o`

## Known tricky patterns

<!--
Anything specific to this language's dictionary source that a human should
know before reviewing flags — font quirks in the scan, a recurring
mis-scan of a particular letter combination, pages with unusually faint
print, etc.
-->

## Digital text layer

<!-- Set `trusted: no` when the PDF's embedded text layer is itself
OCR-derived (publisher scans) — the correction pass then applies to
digital-text entries too, instead of skipping everything at confidence 1.0.
Delete this section if the text layer is clean. -->

- trusted: yes

## Entry splitting

<!-- Optional. A zero-width regex; page text is cut into entry chunks
before every match. Use when several entries share a line and line starts
carry no boundary signal. Delete this section to use line-based extraction.
Example (Sentani): -->

- split_before: `\s+(?=a\s+[•·.]{1,3}\s)`

## Entry pattern

<!-- Optional override for scripts/entry_extractor.ENTRY_PATTERN. Must
have named groups `headword` and `gloss` (`pos` optional). Delete this
section to use the default pattern. Example: -->

- pattern: `^(?P<headword>[A-Za-zÀ-ÿ'’\-]+)\s*(?:\((?P<pos>[a-z.]+)\))?\s*(?P<gloss>.+)$`

## Headword shape

<!-- Optional. Entries whose headword doesn't match this regex are skipped
by the correction pass — keeps confusion pairs like `rn`→`m` from
"fixing" foreign/prose words. Delete this section to correct everything. -->

- pattern: `^[A-Za-zÀ-ÿ'’\-]+$`

## Notes on pivot gloss conventions

<!--
How this dictionary's pivot-language glosses are formatted (whichever
language that is — Bahasa Indonesia, English, etc.) — abbreviations used for
part of speech, how multiple senses are separated, whether examples are
inline or in a separate column. Helps tune `entry_extractor.ENTRY_PATTERN`
if the default doesn't fit.
-->

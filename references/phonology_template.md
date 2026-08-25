# <Language Name> Phonology & Orthography Reference

Copy this file to `<language_code>_phonology.md` and fill it in before
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

## Notes on pivot gloss conventions

<!--
How this dictionary's pivot-language glosses are formatted (whichever
language that is — Bahasa Indonesia, English, etc.) — abbreviations used for
part of speech, how multiple senses are separated, whether examples are
inline or in a separate column. Helps tune `entry_extractor.ENTRY_PATTERN`
if the default doesn't fit.
-->

# Sentani Phonology & Orthography Reference

## Language

- Code: `set`
- Family: Sentanic (Trans–New Guinea), spoken around Lake Sentani, Jayapura, Papua
- Script: plain Latin, no diacritics. This dictionary (Set Kamus
  Sentani–Indonesia–Inggris) glosses into Bahasa Indonesia and English.

## Valid characters

a b d e f g h i j k l m n o p r s t u v w y '

(no c, q, x, z in native vocabulary; apostrophe marks glottal stop)

## OCR confusion pairs

- `rn` → `m`
- `1` → `l`
- `0` → `o`
- `￾` → `` (soft-hyphen artifact from the PDF's embedded text layer; join the halves)

## Digital text layer

- trusted: no

The body pages carry an embedded text layer derived from OCR of the
publisher's scan (artifacts like `rnendengar`, `mElnuju`, `s~inks`, stray
`~` and `Q` glyphs) — treat digital-text entries as correction-eligible.

## Entry splitting

<!-- Zero-width "cut the page before this" regex. This dictionary flows
several entries per line with hard line-breaks every few words, so line
starts carry no signal; only strong entry-opening markers are safe cuts.
Precision over recall: entries without a recognizable marker stay out of
the corpus rather than being guessed at. Currently only the verb family
(POS `a` + dotted aspect marker) segments cleanly; noun entries need a
lexicon-based boundary detector (see Known tricky patterns). -->

- split_before: `\s+(?=a\s+[•·.]{1,3}\s)`

## Entry pattern

<!-- Overrides scripts/entry_extractor.ENTRY_PATTERN for this dictionary.
Consumes the optional leading POS marker `a` and dotted aspect markers,
then captures the headword (lowercase, 1–2 tokens) and everything after it
as the gloss. -->

- pattern: `^(?:a\s+)?[•·.]{0,3}\s*(?P<headword>[a-zà-ÿ'’\-]+(?:\s+[a-zà-ÿ'’\-]+)?)\s*(?P<gloss>.+)$`

## Headword shape

<!-- Optional. Entries whose headword doesn't match are skipped by the
correction pass — keeps confusion pairs like `rn`→`m` from "fixing"
English/Indonesian prose picked up from the text layer. -->

- pattern: `^[a-zà-ÿ'’\-]+$`

## Known tricky patterns

- The PDF's text layer already contains OCR-like artifacts (e.g. `karen a`
  for `karena`, split words at line breaks) — expect space-inside-word noise.
- Compound headwords use hyphens (`hau-fau`) — keep hyphens in headwords.
- Front matter and back matter (~10 pages) are image-only and go through
  tesseract; body pages have an embedded text layer of uneven quality.
- Noun entries have no safe boundary marker yet — they stay unextracted
  rather than mis-headed. Next step for recall: a lexicon-based detector
  (Indonesian function-word list marking gloss starts), not more regex.
- Proper-noun headwords (capitalized, e.g. `Abaele`) are out of scope for
  the entry pattern (lowercase only) — English example sentences also
  start with capitals, so a capitalized-line rule floods the corpus with
  sentence fragments.

## Notes on pivot gloss conventions

- Each entry typically gives: headword, part-of-speech/usage line, then a
  Bahasa Indonesia sentence with an English translation alongside, sometimes
  a short Indonesian/English keyword pair (e.g. `sumpah, kata-kata kotor /
  swear at`).
- Multiple senses are separated by numbered markers or semicolons.
- Examples are inline within the entry block, not in a separate column.

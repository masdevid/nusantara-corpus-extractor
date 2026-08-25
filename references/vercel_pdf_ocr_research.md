# Vercel PDF and OCR Replacement Research

**Research date:** 2026-08-26

## Conclusion

Vercel's PDF capability is not a replacement for the local PDF stack in this project. Vercel's
AI SDK can send a PDF file part to a compatible AI model for multimodal
processing, but it does not provide a local PDF parser, page renderer, OCR
engine, Tesseract language selection, or word-level OCR confidence values.

For this repository, the local `pypdfium2` plus `pytesseract` design provides
the required PDF and OCR stack without PyMuPDF.

## What Vercel released

Vercel's AI SDK 4.0 announcement describes support for file inputs and
multimodal model calls, including PDFs, through the AI SDK. It is an application
SDK for calling AI providers, not a standalone document-processing library:
[Vercel AI SDK 4.0](https://vercel.com/blog/ai-sdk-4-0).

The official AI SDK documentation represents a PDF as a file part, for example
with `mediaType: 'application/pdf'`, and passes that content to a model:
[File parts](https://ai-sdk.dev/docs/foundations/prompts#file-parts).
The `generateText` API is likewise a model-generation API, not a PDF parsing
API: [`generateText`](https://ai-sdk.dev/docs/reference/ai-sdk-core/generate-text).

The official package is the JavaScript/TypeScript npm package `ai`. Its source
and package metadata are maintained in the official repository:
[AI SDK repository](https://github.com/vercel/ai) and
[`packages/ai/package.json`](https://raw.githubusercontent.com/vercel/ai/main/packages/ai/package.json).

## Capability comparison

| Requirement in this project | Current parser | Vercel AI SDK PDF file parts |
|---|---|---|
| Extract text from digital PDF pages | `pypdfium2` text page API | Not exposed as a local extraction API |
| Render image-only pages | `pypdfium2` page render API at 300 DPI | Not provided |
| OCR scanned pages | `pytesseract.image_to_data()` | Not provided as an OCR API |
| Select Tesseract language models | `lang=self.ocr_lang_hint` | No equivalent documented |
| Word-level confidence values | Tesseract confidence data | No equivalent documented |
| Local Python CLI execution | Yes | AI SDK is primarily JavaScript/TypeScript |
| Model-based interpretation | Optional web verification workflow | Yes, through supported AI providers |

These requirements are implemented in
[`scripts/pdf_parser.py`](../scripts/pdf_parser.py), which needs page-level
text extraction, page rasterization, OCR, configurable language hints, and
confidence data. Vercel's documented feature provides model input, so it cannot
be substituted for that implementation without redesigning the pipeline and
accepting different accuracy, cost, privacy, and reproducibility behavior.

## Runtime and deployment

Vercel documents separate Node.js and Python function runtimes:
[Node.js runtime](https://vercel.com/docs/functions/runtimes/node-js) and
[Python runtime](https://vercel.com/docs/functions/runtimes/python). Using the
AI SDK PDF feature would require a server-side function or another Node.js
runtime plus credentials for an AI provider. It would not make the existing
Python command-line parser self-contained.

Vercel also documents function resource and execution constraints:
[Function limitations](https://vercel.com/docs/functions/limitations). These
constraints matter for large dictionaries and 700+ language processing jobs.
A batch pipeline would need explicit handling for uploads, timeouts, retries,
provider costs, privacy, and durable output storage.

## Licensing

The AI SDK repository is licensed under Apache-2.0:
[AI SDK license](https://raw.githubusercontent.com/vercel/ai/main/LICENSE).
That license is compatible with distributing original project code under MIT,
but it does not change the licenses of AI providers, model APIs, or input
content.

The Vercel AI SDK license is unrelated to the local PDF stack. `pypdfium2`
documents Apache-2.0/BSD-3-Clause terms for its binding and dependency license
notices for PDFium binaries:
[pypdfium2 licensing](https://pypdfium2.readthedocs.io/en/stable/license.html).

## Recommendation

Do not replace PyMuPDF with Vercel AI SDK. Treat Vercel AI SDK as an optional
future enhancement for semantic review or ambiguity resolution after local PDF
text/OCR processing.

For a clean MIT-oriented distribution, evaluate a local replacement stack:

1. A permissively licensed PDF text-extraction and rendering library.
2. Tesseract or another separately audited OCR engine and language-data model.
3. The existing confidence and quality-loop interfaces preserved at
   `PageParseResult` and `RawPage`.

Any replacement should be tested against representative digital and scanned
pages before changing the dependency. Do not redistribute dictionary PDFs,
OCR language data, or generated corpora unless their owners' terms permit it.

# Worked examples

Each subdirectory ships a real Tibetan PDF together with the artefacts produced by `pdf-cmap-fix`:

- **`*.pdf`** — original PDF as we received it (input).
- **`*.raw.txt`** — text extracted **before** patching (the broken Unicode you would copy out of the PDF today).
- **`*.patched.txt`** — text extracted **after** patching the `/ToUnicode` CMap.
- **`*.diff.txt`** — line‑by‑line diff between `*.raw.txt` and `*.patched.txt`. The first lines also include the headline counters (`Lines changed`, `Char delta`).
- **`*.patched.pdf`** — the input PDF with corrected `/ToUnicode` streams (visible glyphs are unchanged; copy/paste and search now return correct Unicode).
- **`*.cmap-dump.json`** *(optional, only on the two large PDFs below)* — full per‑font merged ToUnicode for inspection (`pdf-cmap-fix --dump-cmap`).

> All five inputs were processed with the bundled `pdf_cmap_fix/data/reverse_db.json`. Where a font benefits from the per‑font GSUB‑1/2/4/7 expansion (Microsoft Himalaya, Monlam Uni OuChan 2, …), the `--overlay-db pdf_cmap_fix/data/per_font/<key>.json` flag is shown next to the example.

## Index

| Example | Producer | Pages | Lines changed | Char delta | Notable fonts |
|---------|----------|------:|--------------:|-----------:|---------------|
| [`TI1055-01-001/`](TI1055-01-001/) | MS Word | 528 | **10,205** | **−23,725** | Monlam Uni OuChan 2, Calibri, Cambria |
| [`TI1751-01-001/`](TI1751-01-001/) | InDesign | 528 | **5,295** | **+10,093** | Monlam Uni OuChan 2, Dedris‑*, Microsoft Himalaya, Jomolhari |
| [`TI803-01-001/`](TI803-01-001/) | MS Word | 398 | **9,356** | **−23,922** | Microsoft Himalaya, Calibri, Cambria |
| [`TI1461-01-001/`](TI1461-01-001/) | InDesign | 1 | 25 | −2 | Qomolangma‑Uchen‑Sarchen/Sarchung, Monlam Uni OuChan 1/5 |
| [`TI1763-01-002/`](TI1763-01-002/) | MS Word | 1 | 17 | +127 | Monlam Uni OuChan 2 |

`Lines changed` and `Char delta` are read from the first lines of each `*.diff.txt`.

## Reproduce

From the repository root, after `pip install -e .`:

```bash
# Default (uses bundled reverse_db.json only)
pdf-cmap-fix docs/examples/TI1055-01-001/TI1055-01-001.pdf
pdf-cmap-fix -p docs/examples/TI1055-01-001/TI1055-01-001.pdf
```

For PDFs that embed **Microsoft Himalaya** subsets, layer the per‑font overlay so the GSUB type 1/2/4/7 expansion fires:

```bash
pdf-cmap-fix \
    --overlay-db pdf_cmap_fix/data/per_font/microsofthimalaya.json \
    docs/examples/TI803-01-001/TI803-01-001.pdf
pdf-cmap-fix -p \
    --overlay-db pdf_cmap_fix/data/per_font/microsofthimalaya.json \
    docs/examples/TI803-01-001/TI803-01-001.pdf
```

For TI1763 (Monlam Uni OuChan 2) the matching overlay is `monlamuniouchan2.json`:

```bash
pdf-cmap-fix \
    --overlay-db pdf_cmap_fix/data/per_font/monlamuniouchan2.json \
    docs/examples/TI1763-01-002/TI1763-01-002.pdf
```

## What each example shows

### `TI1055-01-001/` — Word inserting spurious subjoined‑ja

Word silently injects `ྗ` (subjoined‑ja, U+0F97) into vowel‑only glyphs of Monlam Uni OuChan 2. The patched output **shrinks** as the spurious characters are removed.

```
RAW:      བྗོད་གངས་ཅན་... ཐྗོས་བསམ་སྗོམ་...
PATCHED:  བོད་གངས་ཅན་... ཐོས་བསམ་སྒོམ་...
```

### `TI1751-01-001/` — InDesign dropping subjoined letters

InDesign's `/ToUnicode` for the same Monlam family **omits** subjoined letters; the patched output **grows** as `ྵ`/`ྱ`/`ྡ`/… come back.

```
RAW:      འོད་གསལ་ཀོང་ཡངས་... རྣལ་འབོར་པ་... ཀི་ཟབ་གཏེར།
PATCHED:  འོད་གསལ་ཀློང་ཡངས་... རྣལ་འབྱོར་པ་... ཀྱི་ཟབ་གཏེར།
```

### `TI803-01-001/` — Word + Microsoft Himalaya subsets

Same Word symptom as TI1055, but on a **Microsoft Himalaya** subset. The default `reverse_db.json` already covers most glyphs; the per‑font overlay (`microsofthimalaya.json`, built with the GSUB type 1/2/4/7 walk) recovers the remaining stack glyphs that were leaving `U+FFFD` placeholders.

### `TI1461-01-001/` — InDesign, mixed Qomolangma + Monlam

Single‑page sample from a multi‑font InDesign export. The patcher resolves stacks for both **Qomolangma‑Uchen‑Sarchen / Sarchung** and **Monlam Uni OuChan 1 / 5**.

### `TI1763-01-002/` — Word, single page, Monlam Uni OuChan 2

The smallest, easiest example to read end‑to‑end. With the per‑font overlay (`monlamuniouchan2.json`) the patched extraction has **0 residual `U+FFFD`** characters; the bundled DB alone leaves 3.

> Spaces inside Tibetan stacks (`སྤྱ  ོད`) come from PyMuPDF interpreting PDF kerning offsets as whitespace; they are present in `*.raw.txt` too. The patch never inserts or moves a space; see [`approach.md`](../approach.md#whitespace-and-pdf-positioning) for details.

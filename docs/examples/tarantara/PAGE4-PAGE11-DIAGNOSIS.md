# Page diagnosis: folio "Page11:" (PDF page 4)

## Folio vs PDF page

The image labeled **"Page 11:"** is **not** PyMuPDF page 11.

| What you see | PDF page (1-based) | `extract_all` marker |
|--------------|----------------------|----------------------|
| Folio header `Page11:` in the document | **4** | `=== PAGE 4 ===` |
| PDF page 11 (different content) | 11 | `=== PAGE 11 ===` |

The broken mantra line (`ཤི་སླྰྀ་ཥྼྀ་ཀྤཱུ་…`) is under **`=== PAGE 4 ===`** in `*.raw.txt`, immediately after the embedded text `Page11:`.

## Symptom

- **Copy–paste from PDF viewer:** Tibetan looks correct (with normal spacing).
- **PyMuPDF `get_text`:** `ཀྤཱུ་ྤུ་` — U+FFFD () before subjoined `ྤུ` and similar spots.
- **This page:** **9** FFFD characters (same count after gid ToUnicode patch).

## Root cause (confirmed)

Word embeds **marked content** before stack syllables:

```pdf
/Span<</ActualText<FEFFFFFD>>> BDC
0.16 0 Td
<0384>Tj
EMC
0.433 0.06 Td
<03E4>Tj
...
```

- **`ActualText<FEFFFFFD>`** is a 4-byte Unicode string: U+FEFF + U+FFFD (Word sentinels).
- **PyMuPDF** includes that in text extraction → two replacement characters (often shown as `?` / ``).
- **Following `Tj` operators** use normal GIDs (`0x0384` = ཀ, `0x03E4` = ྤ, etc.) that **are already mapped** in subset ToUnicode.

So this is **not** missing ToUnicode for the stack GIDs in `Tj`/`TJ` strings.

### Evidence

| Check | Result |
|-------|--------|
| `ActualText<FEFFFFFD>` on PDF page 4 | **9** occurrences |
| PyMuPDF FFFD on page 4 | **9** |
| Manual decode of all `C2_0` `Tj`/`TJ` strings + ToUnicode | **0** FFFD |
| `FEFF`/`FFFD` as 2-byte GIDs in `Tj` hex strings | **0** (not used that way) |
| Adding `65279`/`65533` → U+2060 in `microsofthimalaya.json` + merge | ToUnicode patched, **extract unchanged** |

Our [`content_streams.py`](../../../pdf_cmap_fix/content_streams.py) parser only walks **`Tj` / `TJ` / `'` / `"`** strings. It **does not** read **`/ActualText` inside `BDC` … `EMC`** spans, so merge logic never sees the sentinel layer PyMuPDF uses.

## Why copy–paste differs

Viewers often prefer **glyph rendering** or **omit** broken `ActualText` when copying, while PyMuPDF’s text export **surfaces** `ActualText` literally as U+FEFF/U+FFFD.

## Why the JSON quick fix did not help

The fix only updates **ToUnicode CMap** for GIDs 65279/65533. Here, FFFD comes from **`ActualText` marked content**, not from unmapped GIDs in the main text-show operators.

## Long-term fix options

1. **Preprocess content streams** (recommended for this repo): find `/ActualText<FEFFFFFD>` (and variants), remove or replace with empty/invisible Unicode before extraction.
2. **Post-process extracted text**: strip U+FEFF and U+FFFD between Tibetan letters (quick corpus workaround).
3. **PyMuPDF options**: investigate flags or extractors that ignore marked-content `ActualText` (if available in your PyMuPDF version).
4. **Keep ToUnicode sentinel entries** as a secondary guard for PDFs that *do* emit 65279/65533 as real GIDs in streams (different Word export paths).

## Reproduce

```powershell
python scripts/debug_page11_tarantara.py 4
```

(Page argument is **PDF page number**; default is 4.)

Output: `docs/examples/tarantara/page11-debug.json`

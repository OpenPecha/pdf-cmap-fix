# Glossary and JSON formats

Terms and file formats used throughout **pdf-cmap-fix**. Read this if you are integrating the library or regenerating **`pdf_cmap_fix/data/font_lookup/*.json`**.

## Terms

| Term | Meaning |
|------|---------|
| **Type0 font** | PDF composite font for CID-keyed glyphs (often used with OpenType/CFF). This tool focuses on Type0 fonts that use Identity-H encoding. |
| **CID / GID** | Character identifier in the font’s glyph space. For Identity-H Type0 fonts, the PDF char code often equals the **glyph ID (GID)** from the embedded font program. |
| **Identity-H** | Horizontal identity encoding: two-byte character codes map directly to glyph IDs. The reverse database maps **GID → Unicode string**. |
| **ToUnicode** | A PDF stream (`/ToUnicode`) that maps character codes to Unicode for copy-paste and text extraction. Many Tibetan PDFs ship incomplete or wrong tables for stacked syllables. |
| **CMap** | Character map; here mainly the **ToUnicode CMap** content (PDF syntax with `beginbfchar` / `beginbfrange` ranges). |
| **GSUB** | OpenType **Glyph Substitution** table. Type-4 lookups describe **ligatures** (e.g. stacked Tibetan). The builder walks these rules to expand ligature glyphs into Unicode sequences. |
| **Font lookup** | Directory `pdf_cmap_fix/data/font_lookup/`: one **`<key>.json`** per face with **GID (string) → Unicode string** plus optional `_meta`. Built offline from `.ttf`/`.otf` using cmap + GSUB. Parallel trees **`font_lookup_gname/`** (glyph name keys) and **`font_lookup_gshape/`** (outline fingerprint keys) are described in [font-lookup-tiers-2-3.md](font-lookup-tiers-2-3.md). |
| **Normalised font key** | Font family name derived from the source filename: lowercase, only `a–z` and `0–9` (all other characters removed). Used as JSON keys and for matching normalised PDF font names. |
| **`db_key_matched`** | After matching the PDF font name, records which **`font_lookup`** key was used (or `null`). |
| **`lookup_kind`** | In `_meta`: **`gid`** (default), **`gname`**, or **`gshape`**. Tells the extractor how to interpret inner map keys when merging ToUnicode. |

## `pdf_cmap_fix/data/font_lookup/<key>.json`

Shipped as package data (many files). Each file looks like:

```json
{
  "monlamuniouchan1": {
    "42": "ཀ",
    "43": "ཁ"
  },
  "_meta": {
    "source": "bodyig.zip::Fonts/MonlamUniOuChan1.ttf",
    "gids_mapped": 1234
  }
}
```

- **Font key:** one top-level entry matching the filename stem (e.g. `monlamuniouchan1.json`).
- **GID map:** keys are **decimal strings** of GID integers; values are **Unicode strings** (may be multiple code points after GSUB decomposition).
- **`_meta`:** **`lookup_kind`** defaults to **`gid`**; other fields are diagnostic.

This data is **not** a PDF mapping of page bytes; it is the font-authoritative GID→Unicode side used to **patch** each font’s ToUnicode stream.

## `font_lookup_gname/<key>.json` and `font_lookup_gshape/<key>.json`

Built with **`python scripts/gname/update_font_lookup.py`** or **`python scripts/gshape/update_font_lookup.py`** (or the matching bulk scripts). Same outer shape (one font key + `_meta`), but the inner map uses **glyph names** or **outline fingerprints** as keys instead of GID strings. Pass a directory of these files to **`pdf-cmap-fix-gname`** / **`pdf-cmap-fix-gshape`** (or **`--font-lookup-dir`**) when **`_meta.lookup_kind`** is **`gname`** or **`gshape`**; see [font-lookup-tiers-2-3.md](font-lookup-tiers-2-3.md).

## Python API: `build_tounicode_dict` return value

Returned dict:

| Key | Type | Description |
|-----|------|-------------|
| `fonts` | `list[dict]` | One record per Type0 font that has a ToUnicode stream (may repeat logical fonts across pages; records dedupe by font xref where implemented). |
| `by_font_xref` | `dict[str, dict]` | Same records keyed by string form of `font_xref`. |
| `stats` | `dict` | Aggregates: `fonts_seen`, `patched`, `upgrades`, `no_change`, `no_match`. |

Each record in `fonts`:

| Field | Description |
|-------|-------------|
| `font_xref` | PDF object number for the font dictionary. |
| `to_unicode_xref` | PDF object number for the `/ToUnicode` stream. |
| `pdf_font_name` | Base name as reported by the PDF (may include a six-letter tag prefix). |
| `db_key_matched` | Font lookup key used for merge (`<key>.json` stem), or `null` if no match. |
| `existing` | Parsed current ToUnicode: **GID → Unicode** (`int` keys in memory). |
| `merged` | After applying the database: combined map used if written to PDF. |
| `overrides` | Entries where merged differs from existing (what actually changes). |
| `changed` | Count of GID entries updated from the database perspective (merge metric). |

## CLI `--dump-cmap` JSON

The CLI writes a JSON-serialisable fragment: inner maps use **string keys** for GIDs (`"42"` not `42`). Structure mirrors `_serialise_cmap_result`: top-level `fonts` array and `stats`; there is no `by_font_xref` in the dumped file (only in the in-memory Python result).

Rare PDFs expose **lone UTF-16 surrogates** inside ToUnicode mapping strings. Those cannot be stored in a UTF-8 text file as-is; before writing, the CLI replaces surrogate code units with **`U+FFFD`** so the JSON remains valid UTF-8 (search for **`�`** if you need to spot them).

Large PDFs with many Type0 fonts produce **very large** dump files (often tens of millions of lines when **`merged`** repeats full font maps).

## Related reading

- [approach.md](approach.md) — pipeline and design notes.
- [font-lookup-tiers-2-3.md](font-lookup-tiers-2-3.md) — tier 2 / tier 3 lookup JSON (glyph name and outline hash keys).
- [README.md](../README.md) — installation, CLI, and rebuilding the database.

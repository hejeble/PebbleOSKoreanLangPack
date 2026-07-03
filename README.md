# PebbleOS Korean Font Pack (한국어) — Community

Korean **font** pack (`.pbl`) for watches running the new open-source
**PebbleOS** (Core Devices **Pebble Time 2**, Pebble 2 Duo, and older
Pebbles updated to a firmware that uses the 21-slot `lang` layout).

Once installed, Korean text in notifications, calendar events, emails,
music metadata, etc. renders in **Noto Sans KR** at all five system font
sizes (Gothic 14/18/24/28/36, regular + bold) instead of ▯▯▯ tofu boxes.

**This pack does NOT translate the watch UI.** Menus, settings, and every
built-in label stay in English. It only supplies Hangul glyphs so Korean
text that arrives from *outside* the watch (messages, notifications) is
legible. This is a deliberate design choice — see "UI stays English" below.

Inspired by the classic
[PebbleTimeJapaneseLanguagePack](https://github.com/elliottback/PebbleTimeJapaneseLanguagePack),
rebuilt from scratch against the current
[coredevices/PebbleOS](https://github.com/coredevices/PebbleOS) sources.

## Downloads

| File | Coverage | Size |
|---|---|---|
| `ko_KR-standard.pbl` | KS X 1001 — 2,350 common syllables + jamo + punctuation/fullwidth | ~1.4 MB |
| `ko_KR-full.pbl` | 10,650+ of the 11,172 modern syllables (see limits below) | ~6.2 MB |

**Standard** covers >99.9 % of real-world Korean text and installs much
faster over BLE. Use **full** if you regularly see rare syllables (internet
slang, names) rendered as ▯.

## Installing

Only one language pack can be installed at a time; installing another
replaces it. Switch between it and English in **Settings → Language** on
the watch.

- **pebble tool / pbl tool (developer connection):**
  `pbl install-lang ko_KR-standard.pbl` with the watch connected through
  the mobile app's developer connection (or `--emulator` for QEMU).
- **Mobile app:** on builds that register the `.pbl` file type, opening the
  file hands it to the app for install (this is how packs were installed on
  the original Pebble app; support in the new Core Devices app may vary by
  version — the developer-connection route above always works).
- **Gadgetbridge** (Android) also knows how to install `.pbl` language
  packs onto Pebbles.

To go back to stock: Settings → Language → English, or install a different
pack over it.

## How it works

A language pack is a standard Pebble resource pack (`pbpack`, 256-entry
table) installed to the watch's filesystem as a file named `lang`
(PutBytes object type *File*). The firmware maps its entries by position
(see `resources/normal/base/resource_map.json → files → "lang"`):

```
 1  STRINGS                     gettext .mo — HEADER ONLY (Language:/Name:/
                                Project-Id-Version:), zero translated strings
 2-11  GOTHIC_{14,18,24,28,36}[_BOLD]_EXTENDED
12-21  BITHAM/ROBOTO/DROID *_EXTENDED   (fillers; not wired to extensions,
                                         present only to keep IDs aligned)
```

At render time `prv_font_res_for_codepoint()` routes every codepoint that
is not Latin (≤ U+02AF), symbols (U+2000–2BFF), emoji, or special to the
`_EXTENDED` font — so the extension fonts carry only Hangul, CJK
punctuation, and fullwidth forms, while Latin stays in the built-in
system fonts.

### UI stays English (font-only by design)

The firmware translates a UI string by looking it up in the pack's `STRINGS`
catalog; **a lookup miss keeps the original English text**
(`src/fw/services/i18n/i18n.c`, `prv_lookup`). This pack ships a catalog
containing only the required header block and **no translated strings**, so
every UI lookup misses and the interface stays 100% English. The firmware
still needs that header to accept the pack as a valid, selectable language
and to run its version check, so it is kept.

Consequence: after install, **Settings → Language** lists an entry named
"한국어 (fonts)". Selecting it activates the Korean fonts; it does **not**
translate any menus. To revert to no-font English, pick another language or
reinstall the stock firmware language.

To turn this into a translating pack later, add `msgid`/`msgstr` pairs to
`translations/ko_KR.po` (msgids must match `tintin.pot`) and rebuild.

Hangul is rendered slightly smaller than the line box (e.g. 25 px glyphs
in the 28 px line) with the baseline lifted 2–4 px, matching how the
classic CJK packs avoided clipped descenders and line overlap. Glyphs are
RLE4-compressed (font format v3).

### Why "full" isn't all 11,172 syllables

The Pebble font format's hash table entry stores a **uint16 byte offset**
(`FontHashTableEntry.offset`), which caps a single font at ~10,922 glyphs.
This pack budgets 10,900: all of KS X 1001 plus every other modern
syllable except a few hundred with archaic double-final consonants
(ㄿ ㄾ ㄽ ㄳ …-finals outside KS X 1001) that do not occur in real text.

## Building from source

Requirements: Python 3, `freetype-py`, GNU `gettext` (msgfmt), and a
checkout of [coredevices/PebbleOS](https://github.com/coredevices/PebbleOS)
(its `tools/` are imported directly — fontgen, pbpack).

```sh
./fetch_fonts.sh
pip install freetype-py
python3 build_langpack.py --pebbleos /path/to/PebbleOS --variant standard
python3 build_langpack.py --pebbleos /path/to/PebbleOS --variant full
```

Output lands in `out/`.

## Contributing translations

`translations/ko_KR.po` is intentionally header-only (font-only pack). If
you *want* a UI-translating variant, add `msgid`/`msgstr` pairs whose
msgids match `resources/normal/base/lang/tintin.pot` in the PebbleOS tree
(~570 strings total) and rebuild. PRs welcome — and since PebbleOS
manages official translations via Crowdin, a complete ko_KR could
eventually be upstreamed so Korean ships in the firmware itself.

## Status / caveats

- Built against the `lang` layout in coredevices/PebbleOS as of mid-2026;
  verified by parsing the generated pack and bit-exact decoding of the
  glyph tables (hash lookup, RLE4, metrics). **Not yet tested on
  hardware** — reports welcome.
- Third-party watchfaces/apps that bundle their own fonts won't gain
  Hangul; only text drawn with system fonts is affected.
- Hanja (한자) is not included; open an issue if you need the KS X 1001
  Hanja set added to the standard pack.

## Licenses

- Fonts: Noto Sans KR, © Google/Adobe, [SIL OFL 1.1](https://scripts.sil.org/OFL).
- Build script & translations: MIT.
- PebbleOS tooling used at build time: Apache-2.0 (Google LLC / Core Devices).

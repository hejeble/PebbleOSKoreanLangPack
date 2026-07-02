#!/usr/bin/env python3
"""
Build a Korean (ko_KR) community language pack (.pbl) for PebbleOS
(Core Devices Pebble Time 2 / Pebble 2 Duo, and Rebble-era 4.x watches
that share the 21-slot lang file layout).

The .pbl is a standard Pebble resource pack (pbpack, 256-entry table)
whose entries must appear in exactly this order (see
resources/normal/base/resource_map.json -> files -> "lang" in PebbleOS):

  1  STRINGS                          (gettext .mo, must contain
                                       "Language: ", "Project-Id-Version: ",
                                       and optionally "Name: " headers)
  2  GOTHIC_14_EXTENDED
  3  GOTHIC_14_BOLD_EXTENDED
  4  GOTHIC_18_EXTENDED
  5  GOTHIC_18_BOLD_EXTENDED
  6  GOTHIC_24_EXTENDED
  7  GOTHIC_24_BOLD_EXTENDED
  8  GOTHIC_28_EXTENDED
  9  GOTHIC_28_BOLD_EXTENDED
 10  GOTHIC_36_EXTENDED
 11  GOTHIC_36_BOLD_EXTENDED
 12  BITHAM_18_LIGHT_SUBSET_EXTENDED
 13  BITHAM_30_BLACK_EXTENDED
 14  BITHAM_34_LIGHT_SUBSET_EXTENDED
 15  BITHAM_34_MEDIUM_NUMBERS_EXTENDED
 16  BITHAM_42_BOLD_EXTENDED
 17  BITHAM_42_LIGHT_EXTENDED
 18  BITHAM_42_MEDIUM_NUMBERS_EXTENDED
 19  ROBOTO_CONDENSED_21_EXTENDED
 20  ROBOTO_BOLD_SUBSET_49_EXTENDED
 21  DROID_SERIF_28_BOLD_EXTENDED

At render time the firmware routes any codepoint that is not
Latin (<= U+02AF), symbols (U+2000-2BFF), emoji, or "special" to the
_EXTENDED font (src/fw/applib/graphics/text_resources.c,
prv_font_res_for_codepoint).  Only the Gothic fonts have extension
resources wired up, so slots 12-21 are fillers that exist purely to
keep the resource IDs aligned.

Usage:
  python3 build_langpack.py --pebbleos /path/to/pebbleos \
      --variant standard|full [--no-rle]
"""

import argparse
import json
import os
import struct
import subprocess
import sys

# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))

GOTHIC_SLOTS = [
    # (line_height, bold?)  -> slots 2..11
    (14, False), (14, True),
    (18, False), (18, True),
    (24, False), (24, True),
    (28, False), (28, True),
    (36, False), (36, True),
]

# ppem to render Hangul at, and how far (px) to lift the baseline off the
# bottom of the line box, per Gothic line height.  CJK ink occupies roughly
# -0.12em..+0.88em around the baseline, so we render slightly smaller than
# the line height and shift up to avoid clipping / next-line overlap.
HANGUL_METRICS = {
    14: (13, 2),
    18: (16, 2),
    24: (21, 3),
    28: (25, 3),
    36: (32, 4),
}

FILLER_SLOTS = [
    # (name, line_height, bold?)  -> slots 12..21
    ("BITHAM_18_LIGHT_SUBSET_EXTENDED", 18, False),
    ("BITHAM_30_BLACK_EXTENDED", 30, True),
    ("BITHAM_34_LIGHT_SUBSET_EXTENDED", 34, False),
    ("BITHAM_34_MEDIUM_NUMBERS_EXTENDED", 34, False),
    ("BITHAM_42_BOLD_EXTENDED", 42, True),
    ("BITHAM_42_LIGHT_EXTENDED", 42, False),
    ("BITHAM_42_MEDIUM_NUMBERS_EXTENDED", 42, False),
    ("ROBOTO_CONDENSED_21_EXTENDED", 21, False),
    ("ROBOTO_BOLD_SUBSET_49_EXTENDED", 49, True),
    ("DROID_SERIF_28_BOLD_EXTENDED", 28, True),
]

MAX_GLYPH_SIZE = 256  # conservative: works on every platform (obelix allows 512)


def build_codepoint_sets():
    """Return {'standard': set, 'full': set} of codepoints for the extension
    fonts.  Only codepoints the firmware routes to the extension font are
    useful here (i.e. > U+02AF and outside U+2000-2BFF)."""
    common = set()
    # Hangul Compatibility Jamo (ㄱ ㄴ ㄷ ... ㅏ ㅑ, incl. archaic)
    common |= set(range(0x3131, 0x318F))
    # CJK symbols & punctuation used in Korean text: 、。〈〉《》「」『』【】〒〓〔〕~ etc.
    common |= set(range(0x3001, 0x3040)) - {0x3000}  # 0x3000 handled as 'special'
    # Katakana middle dot (occasionally shows up via IMEs)
    common.add(0x30FB)
    # Fullwidth forms （）！？：；～ etc. + fullwidth won sign
    common |= set(range(0xFF01, 0xFF5F))
    common.add(0xFFE6)  # ￦

    # All 11,172 modern Hangul syllables
    all_syllables = set(range(0xAC00, 0xD7A4))

    # KS X 1001 subset: the 2,350 syllables encodable in EUC-KR proper
    ksx1001 = set()
    for cp in all_syllables:
        try:
            chr(cp).encode("iso2022_kr")
            ksx1001.add(cp)
        except UnicodeEncodeError:
            pass

    # The font format caps one extension font at 10,922 glyphs
    # (FontHashTableEntry.offset is uint16, 6 bytes/glyph), so "full"
    # cannot hold all 11,172 syllables.  Drop never-used syllables with
    # archaic double-final consonants (all outside KS X 1001) until the
    # glyph budget fits.
    MAX_ENTRIES = 10900  # margin below the 10,922 hard limit
    budget = MAX_ENTRIES - len(common) - 2  # wildcard + ellipsis
    # jongseong indices by rarity (drop first): ㄿ ㄾ ㄽ ㄳ ㅀ ㄼ ㄻ ㄵ ㅄ ㄺ ㄶ
    drop_finals = [14, 13, 12, 3, 15, 11, 10, 5, 18, 9, 6]
    full = set(all_syllables)
    for jong in drop_finals:
        if len(full) <= budget:
            break
        for cp in sorted(all_syllables - ksx1001, reverse=True):
            if (cp - 0xAC00) % 28 == jong:
                full.discard(cp)
                if len(full) <= budget:
                    break

    return {
        "standard": common | ksx1001,
        "full": common | full,
    }


def make_font(fontgen, ttf_path, line_height, ppem, baseline_lift,
              codepoints, use_rle):
    """Render one extension font and return its serialized bytes.

    fontgen.Font uses `height` for both the freetype pixel size and the
    header's max_height, and places glyphs with
    bottom = max_height - bitmap_top (baseline at the bottom of the box).
    We decouple the two: render at `ppem`, compute offsets against
    (line_height - baseline_lift), then write `line_height` to the header.
    """
    font = fontgen.Font(ttf_path, ppem, fontgen.MAX_GLYPHS_EXTENDED,
                        MAX_GLYPH_SIZE, legacy=False)
    font.codepoints = set(codepoints)  # set => O(1) membership in build_tables
    if use_rle:
        font.set_compression("RLE4")
    font.max_height = line_height - baseline_lift  # affects glyph offsets
    try:
        font.build_tables()
    except Exception as e:
        if use_rle and "RLE4" in str(e):
            print(f"    RLE4 failed ({e}); rebuilding uncompressed")
            return make_font(fontgen, ttf_path, line_height, ppem,
                             baseline_lift, codepoints, use_rle=False)
        raise
    font.max_height = line_height  # what goes into the header
    data = font.bitstring()
    return data, font.number_of_glyphs


def compile_mo(po_path, out_path):
    subprocess.run(["msgfmt", "--check-format", "-o", out_path, po_path],
                   check=True)
    mo = open(out_path, "rb").read()
    # sanity: firmware requires the hash table (mo_hsize > 2)
    magic, rev, nstrings, otab, ttab, hsize, htab = struct.unpack(
        "<7I", mo[:28])
    assert magic == 0x950412DE, "unexpected MO byte order"
    assert hsize > 2 and htab, "msgfmt did not emit a hash table"
    return mo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pebbleos", required=True,
                    help="path to a PebbleOS checkout (for tools/)")
    ap.add_argument("--variant", choices=["standard", "full"],
                    default="standard")
    ap.add_argument("--regular", default=os.path.join(HERE, "fonts",
                    "NotoSansKR-Regular.otf"))
    ap.add_argument("--bold", default=os.path.join(HERE, "fonts",
                    "NotoSansKR-Bold.otf"))
    ap.add_argument("--po", default=os.path.join(HERE, "translations",
                    "ko_KR.po"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-rle", action="store_true")
    args = ap.parse_args()

    tools = os.path.join(args.pebbleos, "tools")
    sys.path.insert(0, tools)
    sys.path.insert(0, os.path.join(tools, "font"))
    import fontgen           # noqa: E402
    from pbpack import ResourcePack  # noqa: E402

    outdir = os.path.join(HERE, "out")
    os.makedirs(outdir, exist_ok=True)
    out_pbl = args.out or os.path.join(
        outdir, f"ko_KR-{args.variant}.pbl")

    cps = build_codepoint_sets()[args.variant]
    print(f"variant={args.variant}: {len(cps)} target codepoints")

    # 1. STRINGS (.mo)
    mo = compile_mo(args.po, os.path.join(outdir, "ko_KR.mo"))
    print(f"STRINGS: {len(mo)} bytes")

    entries = [mo]

    # 2-11. Gothic extended fonts
    for line_height, bold in GOTHIC_SLOTS:
        ppem, lift = HANGUL_METRICS[line_height]
        src = args.bold if bold else args.regular
        name = f"GOTHIC_{line_height}{'_BOLD' if bold else ''}_EXTENDED"
        data, nglyphs = make_font(fontgen, src, line_height, ppem, lift,
                                  cps, use_rle=not args.no_rle)
        print(f"{name}: {nglyphs} glyphs, {len(data)} bytes")
        entries.append(data)

    # 12-21. Filler slots (wildcard-only fonts, keep IDs aligned)
    for name, line_height, bold in FILLER_SLOTS:
        src = args.bold if bold else args.regular
        ppem = max(line_height - 4, 10)
        data, nglyphs = make_font(fontgen, src, line_height, ppem, 2,
                                  set(), use_rle=False)
        print(f"{name}: filler, {len(data)} bytes")
        entries.append(data)

    assert len(entries) == 21

    # Pack it: non-system pbpack (256-entry table), entries in order.
    pack = ResourcePack(is_system=False)
    for e in entries:
        pack.add_resource(e)
    with open(out_pbl, "wb") as f:
        crc = pack.serialize(f)

    size = os.path.getsize(out_pbl)
    print(f"\nwrote {out_pbl}: {size} bytes ({size/1024/1024:.2f} MB), "
          f"crc=0x{crc:08X}")


if __name__ == "__main__":
    main()

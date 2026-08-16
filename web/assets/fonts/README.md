# Share-card fonts

These four TTFs exist only for `lib/share/card.tsx`. The site itself loads its
faces through `next/font/google` in `app/layout.tsx` — nothing here is served to
a browser.

They are committed rather than fetched because Satori (the engine behind
`next/og`) needs raw font bytes at render time and accepts **ttf/otf/woff only**
— never woff2, and nothing `next/font` produces.

## Why static instances

`Archivo` and `Newsreader` ship from Google Fonts as *variable* fonts. Satori
renders a variable font at its default instance and ignores the axes, so the
`[font-stretch:125%]` the page applies to Archivo would silently come out at
normal width. Each face below is therefore pinned to one point in the
designspace before subsetting.

`Archivo-Expanded-SemiBold` is `wdth=125, wght=600` — the display face.
`Archivo-Medium` is `wdth=100, wght=500` — labels and body.

## Reproducing them

Sources are the upstream Google Fonts binaries:

- `ofl/archivo/Archivo[wdth,wght].ttf`
- `ofl/newsreader/Newsreader[opsz,wght].ttf`
- `ofl/dmmono/DMMono-Regular.ttf`

With `fonttools` installed (`pip install fonttools brotli`):

```sh
U='U+0020-007E,U+00A0,U+00A9,U+00B0,U+00B7,U+2013,U+2014,U+2018,U+2019,U+201C,U+201D,U+2022,U+2026,U+2192,U+00A3,U+00A5,U+20AC'

fonttools varLib.instancer Archivo.ttf    wdth=125 wght=600 -o ArchivoExp.ttf
fonttools varLib.instancer Archivo.ttf    wdth=100 wght=500 -o ArchivoMed.ttf
fonttools varLib.instancer Newsreader.ttf opsz=16   wght=400 -o Newsreader.ttf

for f in ArchivoExp ArchivoMed Newsreader DMMono-Regular; do
  pyftsubset "$f.ttf" --unicodes="$U" --layout-features='kern,liga,tnum' \
    --no-hinting --drop-tables+=DSIG --output-file="$f.subset.ttf"
done
```

The subset is Latin, digits, and the punctuation the card can actually emit —
about 80 KB for all four, against `ImageResponse`'s 500 KB budget for fonts,
images, and JSX combined.

The card draws its ▲/▼ as inline SVG (`lib/share/assets.ts`) precisely because
those glyphs are outside this subset, and a missing glyph in Satori renders as
a silent blank rather than as an error.

## Licences

All three families are SIL Open Font License 1.1. Upstream licence text:
<https://github.com/google/fonts/blob/main/ofl/archivo/OFL.txt> (and the
matching `ofl/newsreader/`, `ofl/dmmono/` paths).

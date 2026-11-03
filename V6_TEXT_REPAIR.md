# Corrected v6: Unicode text repair

Rebuilt native text on all 27 requested pages using complete, uniquely named
embedded Unicode fonts. Reissued all supplied German paragraphs, headers and
quotation-mark phrases, preserving line positions, artwork, page count and rules.

The previous export contained malformed supplementary-Unicode destinations in
eight font maps. This export writes standards-compliant UTF-16BE ToUnicode maps,
repairs malformed legacy map destinations, sets explicit identity CID-to-glyph
mapping for the new fonts, and removes legacy font references from rebuilt pages.

Page 35: clear the top-left area and reissue its native text without stray op.
Page 94: write literal German quotation marks around 7; no raw LaTeX remains.
Pages 101-104: reissue the German text and supplied page-102 points/certificate
wording with complete umlaut and quotation-mark support. All other requested
quotation-mark fields are written as normal logical Unicode text, with legacy
spacing artifacts around separately positioned quote glyphs removed.

Validation: all 43 supplied phrases pass in both PyMuPDF and pypdf; the complete
text on each rebuilt page round-trips through both readers; zero required text
or umlaut sequences are missing. All 11 Unicode maps pass the syntax check.
Every artwork pixel digest and position and all worksheet/page rules are retained.
The original 104 pages and 450 x 666 pt trim are preserved.

The source v5 and every earlier delivery remain intact. The repair script,
verification JSON and UTF-8 text export accompany the Git LFS PDF delivery.

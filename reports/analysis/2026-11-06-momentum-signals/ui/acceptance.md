# Price evidence UI acceptance — 2026-11-06

[Status: OK] Local implementation verified; not committed or deployed.

Page pattern: existing momentum desk with a reference SectionCard.
Reused components/assets: host SectionCard, text/action tokens and tabular numeric class; no new assets.
New design decision: a Price data section distinguishes original source gaps from replacements included in the ranking; missing legacy provenance is unknown.

| Contract | Owner | Consumer | Compatibility | Verification |
|---|---|---|---|---|
| Optional price_evidence | Python dashboard builder and refresh CLI | TS runtime validator and momentum desk | Additive v1; legacy metadata absent means unknown | 17 focused Python tests and check:momentum passed |
| Missing and supplemental sessions | Sanitizer exclusions / explicit offline evidence | Price data section | Supplemented rows must survive sanitization and identify primary gaps | Synthetic CLI rejection case and invalid metadata cases passed |
| Public boundary | Explicit allowlist | Public JSON/hash | No private holding data or local paths | Rejected extra fields; inspected output |

Verification: child web typecheck and momentum runtime contract passed; focused Python tests and Ruff passed; parent make design-check and make test passed. Design check retains two pre-existing chart contrast warnings. Real Chrome at 320px, 390px and 1440px, light/dark: source names, November 5 gaps/replacements and unchanged ranking asserted; no document horizontal overflow. Screenshots saved here; 390px light and 1440px dark visually inspected. No new controls or keyboard interactions. Local dev server used; production deployment not tested. The supplemental source still requires explicitly supplied prices and metadata; automatic provider fallback is out of scope.

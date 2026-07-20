# Packaging and CI — Design

**Goal:** Make `hwp2hwpx` a well-formed, installable Python package with honest
metadata, a correct license, continuous integration that actually exercises a
conversion, and a documented release procedure — stopping deliberately short of
publishing.

Sub-project 3 of 3 in the performance → CLI → packaging track. Performance
shipped (`2026-07-20-parse-once-performance-design.md`); the batch CLI shipped
(`2026-07-20-cli-batch-and-exit-codes-design.md`).

---

## Problem

`pyproject.toml` declares only name, version, `requires-python`, dependencies,
the console script, and the package-find rule. There is **no** `description`,
`readme`, `license`, `authors`, `keywords`, `urls`, or classifiers. There is no
CI at all. And two facts make the current state actively wrong rather than merely
thin:

1. **The declared license is absent and the file on disk is the wrong one.**
   `LICENSE` is GPL-3.0, but the reader this project now imports **in-process**,
   pyhwp, is AGPL-3.0-or-later.
2. **A fresh clone cannot even collect the test suite.** `tests/samplepaths.py`
   resolves samples in module-level constants, and `samples/` is git-ignored
   private material, so 43 test modules raise `FileNotFoundError` at *import*
   time. Measured: `43 errors during collection`. CI is a fresh clone, so this
   blocks CI outright — and it is also what any new contributor hits.

## Decisions

### Distribution: prepare, do not publish
All readiness work is in scope; **no upload, no name reservation**. Publishing a
version to PyPI can be yanked but never truly unpublished, so it stays a separate
deliberate act. The release procedure is documented so that act is mechanical.

### License: relicense to AGPL-3.0-or-later
This project imports pyhwp's `hwp5.xmlmodel`, `hwp5.filestructure`,
`hwp5.binmodel` and friends directly in the same process. That is a far stronger
coupling than the arm's-length `hwp5proc` subprocess invocation used before the
parse-once milestone — which means the parse-once work, incidentally, strengthened
the copyleft relationship. Adopting the dependency's license is the conservative
reading of the obligation.

`LICENSE` is replaced with the AGPL-3.0 text and `pyproject.toml` declares
`license = "AGPL-3.0-or-later"` (SPDX, PEP 639) plus the matching classifier.
The README's license section is updated to state the AGPL terms and to name pyhwp
as the reason.

*This is a licensing judgement made by the project owner, not legal advice.*

### `six` stays; only its justification was wrong
`pyproject.toml` carries `six` with the comment "pyhwp's undeclared runtime dep
(hwp5proc)". `hwp5proc` is no longer invoked at runtime, but `six` is still
required: pyhwp's `hwp5/dataio.py` and numerous `hwp5/binmodel/*` modules import
it, and those are on the in-process read path. It is genuinely undeclared by
pyhwp (its metadata requires only `cryptography`, `lxml`, `olefile`). Keep the
dependency; correct the comment.

## Architecture

Four independent pieces, in dependency order:

- **`tests/samplepaths.py`** — resolution becomes lazy so a missing `samples/`
  yields skips, not collection errors.
- **`pyproject.toml`, `LICENSE`, `README.md`** — metadata, license, release
  procedure.
- **`samples/test_document.{hwp,hwpx}` + `.gitignore` + `tests/test_samples_privacy.py`
  + a new fidelity test** — the committed public fixture.
- **`.github/workflows/ci.yml`** — test matrix and a package-build job.

### Fresh-clone survival

`samplepaths.py` currently does `S3 = hwp("3.")` at module scope, and `_one()`
raises `FileNotFoundError` when nothing matches. Because 43 test modules import
those constants, the failure happens during collection and cannot be skipped.

Resolution moves behind lazy accessors, and sample-dependent tests skip with a
clear reason when the document is absent. The requirement is behavioural, not
cosmetic: **`python -m pytest` on a clone with no `samples/` directory must exit
0, collecting cleanly, with the sample-dependent tests reported as skipped.**
With `samples/` present, the same suite must run exactly as it does today —
no test that runs now may silently become a skip.

### The committed public fixture

`samples/test_document.hwp` is a small non-confidential document authored in
Hancom Office for this purpose, and `samples/test_document.hwpx` is Hancom's own
export **of that exact file**. Verified as a matched pair: identical part sets
(11 each), no `BinData` in either, no images.

This is the only fixture that can be public, so it is the only one CI can score
against. Because `samples/` is git-ignored wholesale, `.gitignore` gains a narrow
un-ignore for exactly these two paths, and `tests/test_samples_privacy.py` gains
an exemption for exactly these two filenames. **The exemption must be exact-match,
not a prefix or directory rule** — a prefix-shaped exemption that could shadow a
real sample was found and fixed in the previous milestone's review, and the same
mistake here would silently disable the gate that exists because private document
content once reached this public repository.

Measured per-part match against Hancom's export, which the new test locks as
floors:

| part | match | remaining gap |
|---|---|---|
| `Contents/content.hpf` | 1.0000 | — |
| `META-INF/container.xml` | 1.0000 | — |
| `META-INF/manifest.xml` | 1.0000 | — |
| `version.xml` | 1.0000 | — |
| `Contents/section0.xml` | 0.9965 | `run` ×1 |
| `Contents/header.xml` | 0.9914 | `substFont` ×24 — documented non-goal |
| `settings.xml` | 0.1000 | `config-item-set` ×1, `config-item` ×8 |

The floors record what the converter does **today**; they are a ratchet against
regression, not a claim of correctness. The `settings.xml` figure is deliberately
recorded at its true low value rather than excluded, so the gap stays visible.

**What this fixture cannot do:** it proves output does not regress and that the
package works end to end. It cannot prove fidelity in general — only the four
private samples do that, and CI will never see them. Conversion is deterministic
(verified: two runs byte-identical), so the floors are stable.

### CI

`.github/workflows/ci.yml`, on push and pull request, two jobs:

- **test** — matrix over Python 3.9, 3.10, 3.11, 3.12, 3.13; install the package
  with its dev extra; run the full suite. Private-sample tests skip; the fixture
  tests, and every unit test, run. The job asserts the suite exits 0 **and** that
  the fixture-dependent tests were not skipped, so a mistake in the skip logic
  cannot quietly hollow CI out into a no-op.
- **package** — build sdist and wheel, `twine check` both, install the wheel into
  a clean virtualenv, then run `hwp2hwpx --version` and convert the fixture
  through the installed console script. This is what catches packaging faults
  that a source-tree test run cannot see: a module missing from the wheel, a
  broken entry point, a missing runtime dependency.

Python 3.9 is the floor already declared in `requires-python`; 3.13 is the
current release. The matrix is what substantiates that claim — it is presently
untested, and development happens only on 3.11.

**The matrix may disprove the claim, and that is a success, not a failure.**
pyhwp 0.1b15 is an old beta; it may not install or import on the newer
interpreters. If a version genuinely does not work, the honest response is to
**narrow `requires-python` and the classifiers to the range that actually
passes** — not to drop the failing version from the matrix and keep advertising
support for it. Whatever range ships must be the range CI proves.

### Release procedure (documented, not executed)

A `## Releasing` section in the README: bump `version` in `pyproject.toml`,
commit, tag `v<version>`, `python -m build`, `twine check dist/*`, `twine upload`.
Versioning is semantic; `0.x` signals the output format may still shift. No
changelog file is introduced — there are no releases yet to record, and an empty
one is worse than none. No release automation, no publish workflow, no
trusted-publisher configuration — those belong with the decision to actually
publish.

## Testing

- **Fresh-clone gate:** with `samples/` temporarily moved aside, the suite
  collects cleanly and exits 0 with sample-dependent tests skipped. This is the
  requirement CI depends on, so it is asserted directly rather than assumed.
- **No-silent-skip gate:** with `samples/` present, the number of tests that
  *run* must not drop relative to the current suite.
- **Fixture fidelity:** per-part match floors from the table above.
- **Privacy gate unchanged in strength:** the two fixture paths are exempt by
  exact match; a test proves a non-exempt sample literal is still caught,
  including one whose filename contains spaces.
- **Package job:** the installed wheel converts the fixture and reports a version.

## Non-goals

- Publishing to PyPI, reserving the name, release automation, trusted publishing.
- Coverage thresholds, linters, formatters, type checking, pre-commit hooks.
- Closing the `settings.xml` gap, the `substFont` non-goal, or the single missing
  `run` — recorded here, addressed elsewhere.
- Removing private sample content from git history (a separate, deliberate
  decision already taken: history is left alone).
- Windows or macOS CI runners; Linux is sufficient for a pure-Python package.

## Value

Turns a source tree that happens to be pip-installable into a package a stranger
can install, understand, and trust: a license that matches its dependencies,
metadata that says what it is, CI that proves it builds and converts on every
supported Python, and a test suite that survives not having the private corpus.

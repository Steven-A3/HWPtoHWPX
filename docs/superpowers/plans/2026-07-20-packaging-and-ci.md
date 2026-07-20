# Packaging and CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `hwp2hwpx` a well-formed installable package — correct license, honest metadata, CI that proves it builds and converts on every supported Python, and a test suite that survives not having the private sample corpus.

**Architecture:** Four independent pieces in dependency order. Sample resolution becomes lazy so a clone without `samples/` collects cleanly and skips; a small public Hancom-authored document is committed as the one fixture CI can score against; `pyproject.toml`/`LICENSE`/`README.md` get metadata and the AGPL relicense; a GitHub Actions workflow runs the matrix and verifies an installed wheel.

**Tech Stack:** Python 3.9+, setuptools, pytest, GitHub Actions, `build` + `twine` (build-time only).

**Spec:** `docs/superpowers/specs/2026-07-20-packaging-and-ci-design.md`

## Global Constraints

- **Python 3.9 floor.** No PEP-604 `X | None` unions — use `typing.Optional`. Mutable dataclass defaults via `field(default_factory=...)`.
- **Run tests only as `.venv/bin/python -m pytest`** — plain `python` lacks the `hwp5proc` entry point several test oracles need. Full suite ~86 s; use a 420000 ms timeout.
- **`samples/` holds private Korean government documents and is git-ignored.** No committed file may contain a private sample's filename or document text. The **only** exceptions are `samples/test_document.hwp` and `samples/test_document.hwpx`, a non-confidential document authored for this purpose. Never `git add` any other path under `samples/`, and never anything under `tests/fixtures/`.
- **Conversion output must not change.** `tests/test_parse_once.py::test_output_matches_golden` must PASS, not skip.
- **The suite is currently 547 passed, 0 skipped, with `samples/` present.** After every task it must still be 547-or-more passed and **0 skipped when `samples/` is present**. No test that runs today may silently become a skip.
- **License is AGPL-3.0-or-later** (SPDX). This is the project owner's decision, recorded in the spec; do not second-guess it, and do not add legal disclaimers beyond what the spec and README state.
- **Do not publish anything.** No `twine upload`, no PyPI name reservation, no release tag, no `git push`.
- Stdlib only for runtime code; no new runtime dependencies.
- Comments explain *why*, not *what*. No debugging scaffolding or commented-out code.
- Commit messages: concise imperative, ending with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

| File | Responsibility |
|---|---|
| `tests/samplepaths.py` (modify) | Resolve samples without raising when absent; expose availability and the public fixture paths. |
| `tests/conftest.py` (create) | Skip sample-dependent tests when the private corpus is absent. |
| `tests/test_fresh_clone.py` (create) | Prove the suite collects and passes with no `samples/`. |
| `.gitignore` (modify) | Un-ignore exactly the two public fixture files. |
| `tests/test_samples_privacy.py` (modify) | Exempt exactly those two paths, by exact match. |
| `tests/test_public_fixture.py` (create) | Per-part fidelity floors for the public document. |
| `pyproject.toml` (modify) | Metadata, license, classifiers, urls. |
| `LICENSE` (replace) | AGPL-3.0 text. |
| `README.md` (modify) | License section, `## Releasing`. |
| `.github/workflows/ci.yml` (create) | Test matrix + package verification. |

---

### Task 1: Survive a clone with no private samples

**Files:**
- Modify: `tests/samplepaths.py`
- Create: `tests/conftest.py`
- Create: `tests/test_fresh_clone.py`

**Interfaces:**
- Produces, for later tasks and for `conftest.py`:
  - `samples_available() -> bool` — True when all four private samples resolve.
  - `S3`, `S3_REF`, `S4`, `S4_REF` — unchanged names; now best-effort paths that may not exist.
  - `TEST_DOC = "samples/test_document.hwp"`, `TEST_DOC_REF = "samples/test_document.hwpx"` — the public fixture, always present (committed in Task 2).

**Why:** `samplepaths.py` resolves samples in module-level constants and `_one()` raises `FileNotFoundError` when nothing matches. Because 34 test modules do `from tests.samplepaths import ...`, a clone without `samples/` fails **at collection** — measured: `43 errors during collection`. CI is exactly such a clone.

- [ ] **Step 1: Write the failing test**

Create `tests/test_fresh_clone.py`:

```python
"""The suite must survive a clone that has no private samples/ directory.

CI is exactly that clone: samples/ is git-ignored private material and will
never exist there. Collection errors cannot be skipped, so a module that
resolves a sample at import time takes the whole run down.
"""
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

from tests.samplepaths import samples_available


@pytest.mark.skipif(not samples_available(),
                    reason="already running without the private samples")
def test_suite_collects_and_passes_without_samples(tmp_path):
    # Run pytest in a copy of the repo that has no samples/ at all. A copy,
    # not a temporary rename: renaming the real directory would destroy the
    # private corpus if this process were interrupted mid-test.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work = str(tmp_path / "clone")
    shutil.copytree(root, work, ignore=shutil.ignore_patterns(
        "samples", ".git", ".venv", "build", "dist", "__pycache__",
        ".pytest_cache", "*.egg-info", "fixtures"))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header"],
        cwd=work, capture_output=True, text=True)
    assert "error" not in result.stdout.lower().split("warnings summary")[0], (
        "collection or run errors without samples/:\n%s" % result.stdout[-3000:])
    assert result.returncode == 0, result.stdout[-3000:]
    assert " skipped" in result.stdout, (
        "expected sample-dependent tests to skip:\n%s" % result.stdout[-2000:])
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_fresh_clone.py -v`
Expected: FAIL — the subprocess run reports collection errors (`FileNotFoundError: no sample matches samples/3.*.hwp`) and a non-zero return code.

- [ ] **Step 3: Make resolution lazy**

Replace the body of `tests/samplepaths.py` above `def fixture3()` (i.e. lines 1-36, the docstring through the `S4_REF` assignment) with:

```python
"""Resolve sample documents by prefix.

samples/ holds private documents and is git-ignored, so no committed file may
name one. Tests locate their samples through this module instead, by the
number/tag prefix the project uses to refer to them (3, 4, 2013, ★131008).

Resolution never raises when a sample is missing: 34 test modules import these
constants at module scope, so raising here turns an absent private corpus into
collection errors, which pytest cannot skip. Missing samples yield a path that
simply does not exist, and tests/conftest.py skips the tests that need one.
"""
import glob
import os
import subprocess

FIXTURE3 = "tests/fixtures/sample3.hwp5.xml"

# The one public, committed document: authored in Hancom Office for this
# project, contains no confidential content, and is the only sample CI can see.
TEST_DOC = "samples/test_document.hwp"
TEST_DOC_REF = "samples/test_document.hwpx"

_fixture3_cache = None  # generated at most once per session


def _one(pattern, fallback):
    matches = sorted(glob.glob(pattern))  # sorted: never depend on FS order
    return matches[0] if matches else fallback


def hwp(prefix):
    """The source document whose filename starts with `prefix`.

    Returns a non-existent placeholder path when the sample is absent.
    """
    return _one("samples/%s*.hwp" % prefix, "samples/%s-missing.hwp" % prefix)


def hwpx(prefix):
    """Hancom's own .hwpx export of that document -- the fidelity reference."""
    return _one("samples/%s*.hwpx" % prefix, "samples/%s-missing.hwpx" % prefix)


S3 = hwp("3.")
S3_REF = hwpx("3.")
S4 = hwp("4.")
S4_REF = hwpx("4.")


def samples_available():
    """True when the private corpus is present.

    The public fixture lives in samples/ too, so the directory existing proves
    nothing -- check the private documents themselves.
    """
    return all(os.path.exists(p) for p in (S3, S3_REF, S4, S4_REF))
```

Leave `fixture3()` exactly as it is.

- [ ] **Step 4: Add the collection-time skip**

Create `tests/conftest.py`:

```python
"""Skip sample-dependent tests when the private corpus is absent.

A module is sample-dependent if it imported one of samplepaths' private-sample
names. `from tests.samplepaths import S3` binds the *same object* into the
importing module, so identity against those values detects it with no marker to
apply and no per-module edit -- 34 modules would otherwise need touching, and
any future one would be silently missed.

Two exclusions are load-bearing:
  - samplepaths' own imported modules (os, glob, subprocess) are in its
    namespace, so matching on every value would flag any module that imports
    os -- i.e. nearly all of them.
  - TEST_DOC/TEST_DOC_REF name the *public* fixture, which is committed and
    present in CI. Treating them as private-sample names would skip the one
    end-to-end gate CI can actually run.
"""
import types

import pytest

from tests import samplepaths

_PUBLIC_FIXTURE_NAMES = {"TEST_DOC", "TEST_DOC_REF"}

_PRIVATE_SAMPLE_OBJECTS = {
    id(value) for name, value in vars(samplepaths).items()
    if not name.startswith("_")
    and name not in _PUBLIC_FIXTURE_NAMES
    and not isinstance(value, types.ModuleType)
}


def _imported_samplepaths(module):
    return any(id(value) in _PRIVATE_SAMPLE_OBJECTS
               for value in vars(module).values())


def pytest_collection_modifyitems(items):
    if samplepaths.samples_available():
        return
    skip = pytest.mark.skip(reason="private samples/ corpus not present")
    for item in items:
        module = getattr(item, "module", None)
        if module is not None and _imported_samplepaths(module):
            item.add_marker(skip)
```

Sanity-check the detection before relying on it — a false positive here silently
skips tests that should run, and a false negative reintroduces the collection
error this task exists to remove:

```bash
.venv/bin/python - <<'PY'
import types
from tests import samplepaths as sp
ids = {id(v) for n, v in vars(sp).items()
       if not n.startswith("_") and n not in {"TEST_DOC", "TEST_DOC_REF"}
       and not isinstance(v, types.ModuleType)}
def probe(src):
    m = types.ModuleType("probe"); exec(src, m.__dict__)
    return any(id(v) in ids for v in vars(m).values())
print("imports S3            ->", probe("from tests.samplepaths import S3"), "(want True)")
print("imports os only       ->", probe("import os"), "(want False)")
print("imports TEST_DOC only ->", probe("from tests.samplepaths import TEST_DOC"), "(want False)")
PY
```

Expected: `True`, `False`, `False`.

- [ ] **Step 5: Verify the fresh-clone test passes**

Run: `.venv/bin/python -m pytest tests/test_fresh_clone.py -v`
Expected: PASS. It takes a few minutes — it runs the whole suite in a subprocess.

- [ ] **Step 6: Verify nothing silently became a skip**

Run: `.venv/bin/python -m pytest -q` (timeout 420000)
Expected: `548 passed` (547 + the new fresh-clone test), **0 skipped**. If anything reports as skipped while `samples/` is present, the conftest logic is wrong — fix it rather than accepting the count.

- [ ] **Step 7: Commit**

```bash
git add tests/samplepaths.py tests/conftest.py tests/test_fresh_clone.py
git commit -m "test: survive a clone with no private samples

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Commit the public fixture and lock its fidelity floors

**Files:**
- Modify: `.gitignore`
- Modify: `tests/test_samples_privacy.py`
- Create: `tests/test_public_fixture.py`
- Add to git: `samples/test_document.hwp`, `samples/test_document.hwpx`

**Interfaces:**
- Consumes from Task 1: `TEST_DOC`, `TEST_DOC_REF`.
- Produces: a committed document CI can convert and score.

**Context:** `samples/test_document.hwp` is a small non-confidential document authored in Hancom Office; `samples/test_document.hwpx` is Hancom's export **of that exact file**. Verified as a matched pair — identical part sets, 11 each, no `BinData`. Both already exist on disk; they are currently ignored.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_public_fixture.py`:

```python
"""End-to-end gate on the one document that can be public.

This is the only fixture CI can see: the private corpus never reaches it. The
floors below record what the converter produces *today* -- a ratchet against
regression, not a claim of correctness. Only the private samples can measure
fidelity in general.
"""
import os
import tempfile

import pytest

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from tests.samplepaths import TEST_DOC, TEST_DOC_REF

# Measured against Hancom's export of this document. Known gaps, deliberately
# recorded at their true values rather than excluded so they stay visible:
#   header.xml   -- substFont x24, a documented non-goal (not derivable)
#   section0.xml -- one run
#   settings.xml -- emitted as a near-empty stub
_FLOORS = {
    "Contents/content.hpf": 1.0,
    "META-INF/container.xml": 1.0,
    "META-INF/manifest.xml": 1.0,
    "version.xml": 1.0,
    "Contents/section0.xml": 0.996,
    "Contents/header.xml": 0.991,
    "settings.xml": 0.10,
}


@pytest.fixture(scope="module")
def converted():
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out.hwpx")
        convert(TEST_DOC, out)
        yield unzip_parts(out), unzip_parts(TEST_DOC_REF)


def test_part_set_matches_hancom(converted):
    ours, theirs = converted
    assert set(ours) == set(theirs)


@pytest.mark.parametrize("part", sorted(_FLOORS))
def test_part_meets_its_floor(converted, part):
    ours, theirs = converted
    result = score_part(ours[part], theirs[part])
    assert result["match"] >= _FLOORS[part], "%s regressed to %.4f, missing %s" % (
        part, result["match"], result["missing"])


def test_conversion_is_deterministic():
    # The floors are only meaningful if the same input yields the same output.
    with tempfile.TemporaryDirectory() as td:
        first, second = os.path.join(td, "a.hwpx"), os.path.join(td, "b.hwpx")
        convert(TEST_DOC, first)
        convert(TEST_DOC, second)
        assert open(first, "rb").read() == open(second, "rb").read()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_public_fixture.py -v`
Expected: the tests PASS on your machine (the files exist locally but are untracked). That is expected — the *gate* this task adds is that the files become tracked, verified in Step 5. Note the pass and continue.

- [ ] **Step 3: Un-ignore exactly the two fixture files**

In `.gitignore`, replace this block:

```
# Private test documents — never publish (government docs)
samples/
```

with:

```
# Private test documents — never publish (government docs).
# `samples/*`, not `samples/`: git cannot re-include a file whose parent
# directory is itself excluded, so the directory form would make the two
# negations below silently do nothing.
samples/*
# ...except the one public document: authored in Hancom Office for this
# project, contains no confidential content, and is the only sample CI can
# see. Listed by exact path, never by pattern, so no private document can
# ever be un-ignored by accident.
!samples/test_document.hwp
!samples/test_document.hwpx
```

Verify both halves of that behaviour before moving on — the directory-form bug
is silent, and `git add -f` in Step 5 would mask it:

```bash
git check-ignore -v samples/test_document.hwp || echo "public fixture: not ignored (correct)"
git status --porcelain --ignored samples/ | grep -c '^!!' 
```

Expected: the first prints `public fixture: not ignored (correct)`; the second
prints a non-zero count, i.e. the private documents are still ignored.

- [ ] **Step 4: Exempt exactly those two paths in the privacy gate**

In `tests/test_samples_privacy.py`, add this constant immediately after the `_LITERAL_SAMPLE` definition:

```python
# The one public document may be named literally. Exact full-path match only:
# a prefix or directory-shaped exemption could shadow a real sample basename,
# which is precisely the bug found and fixed in the previous milestone.
_PUBLIC_FIXTURES = frozenset({
    "samples/test_document.hwp",
    "samples/test_document.hwpx",
})
```

and replace the body of `_names_a_sample` with:

```python
    match = _LITERAL_SAMPLE.search(line)
    if match is None:
        return False
    return match.group(0).strip("'\"") not in _PUBLIC_FIXTURES
```

Then add these tests at the end of the file:

```python
def test_gate_allows_the_public_fixture_by_exact_path():
    assert not _names_a_sample('DOC = "samples/test_document.hwp"\n')
    assert not _names_a_sample('REF = "samples/test_document.hwpx"\n')


def test_public_fixture_exemption_does_not_shadow_a_private_sample():
    # The exemption must be exact-match. A prefix- or directory-shaped rule
    # would wave through any path that merely starts the same way.
    assert _names_a_sample('X = "samples/test_document_private.hwp"\n')
    assert _names_a_sample('X = "samples/test_document/real name.hwp"\n')


def test_public_fixture_is_tracked():
    out = subprocess.run(["git", "ls-files", "samples"],
                         capture_output=True, text=True, check=True).stdout
    tracked = sorted(p for p in out.splitlines() if p)
    assert tracked == ["samples/test_document.hwp",
                       "samples/test_document.hwpx"], (
        "exactly the public fixture must be tracked under samples/, got: %s"
        % tracked)
```

- [ ] **Step 5: Track the fixture and verify the gates**

```bash
git add -f samples/test_document.hwp samples/test_document.hwpx
git status --short samples/
```

Expected: exactly two `A` entries, nothing else under `samples/`.

Run: `.venv/bin/python -m pytest tests/test_samples_privacy.py tests/test_public_fixture.py -v`
Expected: all pass, including `test_public_fixture_is_tracked`.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q` (timeout 420000)
Expected: all pass, 0 skipped.

- [ ] **Step 7: Commit**

```bash
git add .gitignore tests/test_samples_privacy.py tests/test_public_fixture.py
git commit -m "test: commit a public Hancom-authored fixture with fidelity floors

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Package metadata, AGPL relicense, README

**Files:**
- Modify: `pyproject.toml`
- Replace: `LICENSE`
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the metadata Task 4's package job validates with `twine check`.

**Why AGPL:** this project imports pyhwp (`hwp5.xmlmodel`, `hwp5.binmodel`, …) in-process, and pyhwp is AGPL-3.0-or-later. The spec records adopting the dependency's license as the project owner's decision.

- [ ] **Step 1: Replace the LICENSE file**

The current `LICENSE` is GPL-3.0. Fetch the AGPL-3.0 text:

```bash
curl -fsSL https://www.gnu.org/licenses/agpl-3.0.txt -o LICENSE
head -3 LICENSE && wc -l LICENSE
```

Expected: the header reads `GNU AFFERO GENERAL PUBLIC LICENSE` / `Version 3, 19 November 2007`, and the file is roughly 660 lines. If the download fails, stop and report — do not hand-write a licence text.

- [ ] **Step 2: Fill in pyproject metadata**

Replace the `[project]` table in `pyproject.toml` (currently name/version/requires-python/dependencies) with:

```toml
[project]
name = "hwp2hwpx"
version = "0.1.0"
description = "Convert Hangul Word Processor (HWP 5.0) documents to HWPX (OWPML)"
readme = "README.md"
requires-python = ">=3.9"
license = "AGPL-3.0-or-later"
license-files = ["LICENSE"]
authors = [{ name = "Byeong Kwon Kwak", email = "bk.kwak@gmail.com" }]
keywords = ["hwp", "hwpx", "owpml", "hancom", "document-conversion", "korean"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Office/Business",
    "Topic :: Text Processing :: Markup :: XML",
]
# six: pyhwp imports it from hwp5.dataio and hwp5.binmodel.* -- the in-process
# read path -- but does not declare it (its metadata requires only cryptography,
# lxml and olefile).
dependencies = ["lxml>=5", "pyhwp>=0.1b15", "six"]

[project.urls]
Homepage = "https://github.com/Steven-A3/HWPtoHWPX"
Repository = "https://github.com/Steven-A3/HWPtoHWPX"
Issues = "https://github.com/Steven-A3/HWPtoHWPX/issues"
```

Note there is deliberately **no** `License ::` classifier: with PEP 639 SPDX `license`, a license classifier is redundant and newer `twine`/`setuptools` reject the combination.

- [ ] **Step 3: Verify the metadata builds and validates**

```bash
.venv/bin/python -m pip install --quiet build twine
.venv/bin/python -m build 2>&1 | tail -3
.venv/bin/python -m twine check dist/*
```

Expected: `Checking dist/... PASSED` for both the wheel and the sdist. If `setuptools` rejects `license-files` or the SPDX string, upgrade it (`pip install -U setuptools`) and retry; if it still fails, report the exact error rather than reverting to the deprecated table form.

Then remove the build artifacts so they are not committed: `rm -rf dist build`.

- [ ] **Step 4: Update the README's license section**

Replace the contents of the `## License` section in `README.md` with:

```markdown
## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).

This project reads HWP files with [pyhwp](https://github.com/mete0r/pyhwp),
which is AGPL-3.0-or-later, and imports it in-process rather than invoking it
as a separate program. The combined work is therefore distributed under the
same terms. Note that the AGPL's section 13 obliges you to offer source to
users who interact with a modified version over a network.
```

- [ ] **Step 5: Add the release procedure**

Append a `## Releasing` section at the end of `README.md`:

````markdown
## Releasing

Not yet published to PyPI. When it is, a release is:

```bash
# 1. bump `version` in pyproject.toml (semantic; 0.x = output format may shift)
# 2. commit the bump, then:
git tag v$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```
````

- [ ] **Step 6: Verify nothing broke**

Run: `.venv/bin/python -m pytest -q` (timeout 420000)
Expected: all pass, 0 skipped.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml LICENSE README.md
git commit -m "feat: package metadata and AGPL-3.0 relicense to match pyhwp

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Continuous integration

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: Task 1 (the suite must survive without `samples/`), Task 2 (the fixture tests must run in CI), Task 3 (metadata must pass `twine check`).
- Produces: nothing later depends on.

**Important:** CI is a clone with **no `samples/`** except the two committed fixture files. The private-sample tests will skip there; the fixture tests must not.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]"
      - name: Run tests
        run: python -m pytest -q
      # The private corpus is absent here, so most tests skip. Assert the
      # public-fixture tests actually ran: a mistake in the skip logic would
      # otherwise hollow CI out into a green no-op.
      - name: Verify the public-fixture gate ran
        run: python -m pytest tests/test_public_fixture.py -q --no-header -rN

  package:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Build
        run: |
          python -m pip install --upgrade pip build twine
          python -m build
          python -m twine check dist/*
      # Install the built wheel into a clean environment and drive the real
      # console script. This is what catches packaging faults a source-tree
      # test run cannot see: a module missing from the wheel, a broken entry
      # point, an undeclared runtime dependency.
      - name: Install the wheel and convert
        run: |
          python -m venv /tmp/venv
          /tmp/venv/bin/pip install --quiet dist/*.whl
          /tmp/venv/bin/hwp2hwpx --version
          /tmp/venv/bin/hwp2hwpx samples/test_document.hwp -o /tmp/out.hwpx
          test -s /tmp/out.hwpx
```

- [ ] **Step 2: Verify the test job's command locally, without samples**

The workflow's correctness hinges on the suite passing in a clone with no private samples. `tests/test_fresh_clone.py` already proves exactly that:

Run: `.venv/bin/python -m pytest tests/test_fresh_clone.py -v`
Expected: PASS.

- [ ] **Step 3: Verify the package job's steps locally**

```bash
.venv/bin/python -m build 2>&1 | tail -2
.venv/bin/python -m twine check dist/*
.venv/bin/python -m venv /tmp/wheelcheck
/tmp/wheelcheck/bin/pip install --quiet dist/*.whl
/tmp/wheelcheck/bin/hwp2hwpx --version
/tmp/wheelcheck/bin/hwp2hwpx samples/test_document.hwp -o /tmp/wheelcheck-out.hwpx
test -s /tmp/wheelcheck-out.hwpx && echo "installed wheel converts OK"
```

Expected: `twine check` PASSED, a version string, and `installed wheel converts OK`.

Clean up: `rm -rf dist build /tmp/wheelcheck /tmp/wheelcheck-out.hwpx`.

- [ ] **Step 4: Validate the workflow file parses**

```bash
.venv/bin/python -c "
import yaml, sys
d = yaml.safe_load(open('.github/workflows/ci.yml'))
print('jobs:', sorted(d['jobs']))
print('matrix:', d['jobs']['test']['strategy']['matrix']['python-version'])
"
```

Expected: `jobs: ['package', 'test']` and the five versions. If `yaml` is not installed, `.venv/bin/python -m pip install pyyaml` first (a local check only — do not add it to project dependencies).

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q` (timeout 420000)
Expected: all pass, 0 skipped.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: test matrix and installed-wheel verification

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 7: Report the Python-version risk**

`requires-python = ">=3.9"` has never been tested — development happens only on 3.11, and pyhwp 0.1b15 is an old beta that may not install or import on 3.12/3.13. This workflow is the first thing that will find out, and it can only find out once pushed.

Do not attempt to pre-empt it by narrowing the matrix. In your report, state explicitly that the matrix is unverified and that **if a version fails once CI runs, the correct response is to narrow `requires-python` and the version classifiers to the range that actually passes** — not to drop the version from the matrix while continuing to advertise support for it.

---

## Self-Review

**Spec coverage.** Distribution "prepare, don't publish" → Task 3 documents the procedure, no task uploads; the Global Constraints forbid it explicitly. AGPL relicense → Task 3 Steps 1, 2, 4. `six` justification corrected → Task 3 Step 2 comment. Fresh-clone survival → Task 1, gated by `tests/test_fresh_clone.py`. Committed public fixture with exact-match exemption → Task 2 Steps 3, 4, plus a test that a prefix-shaped exemption would fail. Per-part floors → Task 2 Step 1, values copied from the spec's table. CI matrix + package job + no-silent-skip assertion → Task 4. Release procedure → Task 3 Step 5. Non-goals (publishing, coverage, linters, `settings.xml`) have no tasks, correctly.

**Placeholder scan.** No TBDs; every code step carries complete file content or an exact replacement; every command states its expected output.

**Type consistency.** `samples_available()` is defined in Task 1 and consumed by `tests/conftest.py` (same task) and `tests/test_fresh_clone.py`. `TEST_DOC`/`TEST_DOC_REF` are defined in Task 1 and consumed in Task 2's `tests/test_public_fixture.py`. `_names_a_sample` keeps its existing signature (one `line` argument, returns bool) after Task 2 rewrites its body. `score_part` returns `{"match", "our_counts", "their_counts", "missing"}` (verified in `hwp2hwpx/fidelity/diff.py:23-30`), and Task 2 consumes `["match"]` and `["missing"]` accordingly.

**Three plan defects found and fixed during this self-review**, all silent failures rather than loud ones: (1) `.gitignore` used `samples/`, which excludes the directory and makes a file-level negation a no-op — corrected to `samples/*` and given an explicit verification step, since `git add -f` in a later step would otherwise have masked it; (2) the conftest identity set included samplepaths' own imported modules, so every module importing `os` was flagged sample-dependent — now filtered, with a probe step; (3) `TEST_DOC`/`TEST_DOC_REF` sat in the same detection set, which would have skipped the public-fixture tests in CI, i.e. exactly the gate CI exists to run — now excluded by name.

**One risk accepted deliberately.** `tests/test_fresh_clone.py` runs the entire suite in a subprocess, so it roughly doubles local suite time. It is the only honest way to prove the property CI depends on, and it skips automatically when the private corpus is already absent (i.e. in CI itself), so it costs nothing there.

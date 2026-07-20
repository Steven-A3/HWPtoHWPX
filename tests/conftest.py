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

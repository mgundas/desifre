"""Düzenleyici mantığının (static/js/editor/ops.js) Node testlerini pytest içinden çalıştırır."""
import shutil
import subprocess

import pytest

from tests.conftest import ROOT_DIR


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js gerekli")
def test_node_unit_tests_pass():
    r = subprocess.run(["node", "--test", "tests/js/ops.test.mjs"], cwd=ROOT_DIR, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1000:]

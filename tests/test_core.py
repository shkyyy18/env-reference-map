import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import unittest
import tempfile
import json
from env_reference_map import core


class EnvTests(unittest.TestCase):
    def test_literals_aliases(self):
        refs, unknown = core.references(
            'import os as o\nfrom os import environ as e, getenv as g\na=o.getenv("A")\nb=e["B"]\nc=g(key="C")\nd=e.get("D")',
            "x.py",
        )
        self.assertEqual({r["name"] for r in refs}, {"A", "B", "C", "D"})
        self.assertFalse(unknown)

    def test_dynamic(self):
        refs, unknown = core.references('import os\na=os.getenv(prefix+"X")', "x.py")
        self.assertFalse(refs)
        self.assertEqual(len(unknown), 1)

    def test_never_executes(self):
        refs, _ = core.references(
            'raise RuntimeError("must not execute")\nimport os\nx=os.getenv("A")',
            "x.py",
        )
        self.assertEqual(refs[0]["name"], "A")

    def test_defaults_not_exported(self):
        result = core.references('import os\nx=os.getenv("A","SECRET_MARKER")', "x.py")
        self.assertNotIn("SECRET_MARKER", json.dumps(result))

    def test_non_os_ignored(self):
        self.assertEqual(core.references('service.getenv("A")', "x.py"), ([], []))

    def test_writes(self):
        refs, _ = core.references(
            'import os\nos.environ["A"]="value"\nos.environ.pop("B")', "x.py"
        )
        self.assertEqual({r["access"] for r in refs}, {"write", "read/write"})

    def test_syntax(self):
        with self.assertRaises(ValueError):
            core.references("this is invalid ?", "x.py")

    def test_scan_and_ignored_env(self):
        with tempfile.TemporaryDirectory() as t:
            Path(t, "a.py").write_text(
                'import os\nx=os.getenv("MISSING")', encoding="utf-8"
            )
            Path(t, ".env").write_bytes(b"\xffPRIVATE")
            Path(t, "node_modules").mkdir()
            Path(t, "node_modules", "bad.py").write_text("bad ???")
            r = core.inspect(t, ["EXTRA"])
            self.assertEqual(r["files_scanned"], 1)
            self.assertEqual(r["not_declared"], [{"name": "MISSING"}])
            self.assertEqual(r["declared_not_observed"], [{"name": "EXTRA"}])

    def test_invalid_keys(self):
        with tempfile.TemporaryDirectory() as t:
            for keys in [{}, ["A", "A"], [1], [""]]:
                with self.assertRaises(ValueError):
                    core.inspect(t, keys)

    def test_run(self):
        import argparse

        with tempfile.TemporaryDirectory() as t:
            Path(t, "a.py").write_text('import os\nx=os.getenv("A")')
            p = Path(t, "keys.json")
            p.write_text('["A"]')
            self.assertEqual(
                core.run(argparse.Namespace(root=t, keys=str(p)))["finding_count"], 0
            )

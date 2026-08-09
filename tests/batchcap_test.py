import unittest
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
TEST_DIR = Path(__file__).parent

class TestBatchCapCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.batchcap = [
            sys.executable, "-m", "batchcap.BatchCap"
        ]

    def _run(self, *args):
        cmd = self.batchcap + list(args)
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        return proc

    def test_single_file(self):
        """single file"""
        res = self._run(
            TEST_DIR / "file_1.mp4",
            "-t", "2x1",
            "--overwrite",
        )
        self.assertEqual(res.returncode, 0, res.stderr or res.stdout)

    def test_folder(self):
        """folder"""
        res = self._run(
            TEST_DIR / "folder",
            "-t", "2x1",
            "--overwrite",
        )
        self.assertEqual(res.returncode, 0)

    def test_mixed_args(self):
        """mixed paths"""
        res = self._run(
            TEST_DIR / "file_1.mp4",
            TEST_DIR / "file_2.mp4",
            TEST_DIR / "folder",
            "--overwrite",
            "-v",
        )
        self.assertEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
    
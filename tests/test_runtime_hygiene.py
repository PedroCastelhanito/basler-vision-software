from __future__ import annotations

import os
import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from basler_vision.runtime_hygiene import _looks_like_python_cache_temp


class RuntimeHygieneTests(unittest.TestCase):
    def test_package_import_disables_bytecode_and_inherited_cache_prefix(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BASLER_VISION_WRITE_BYTECODE": "",
                "PYTHONDONTWRITEBYTECODE": "0",
                "PYTHONPYCACHEPREFIX": ".tmp_pycache",
            },
        ):
            import basler_vision
            basler_vision = importlib.reload(basler_vision)

            self.assertEqual(os.environ["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertNotIn("PYTHONPYCACHEPREFIX", os.environ)
            self.assertTrue(sys.dont_write_bytecode)
            self.assertIsNotNone(basler_vision)

    def test_python_cache_temp_name_detection_is_narrow(self) -> None:
        self.assertTrue(
            _looks_like_python_cache_temp(Path("controller.cpython-311.pyc.12345"))
        )
        self.assertFalse(
            _looks_like_python_cache_temp(Path("controller.cpython-311.pyc"))
        )
        self.assertFalse(
            _looks_like_python_cache_temp(Path("controller.cpython-311.pyc.debug"))
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from unittest.mock import mock_open, patch

from basler_vision.hardware.basler import BaslerCamera


class _FakeNamedTemporaryFile:
    def __init__(self, writes: list[str]) -> None:
        self.name = "filtered-camera.pfs"
        self._writes = writes

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        return None

    def write(self, text: str) -> None:
        self._writes.append(text)


class BaslerCameraSettingsTests(unittest.TestCase):
    def test_filtered_pfs_path_removes_unreadable_trigger_activation_entries(
        self,
    ) -> None:
        writes: list[str] = []
        source_text = "\n".join(
            [
                "# GenApi persistence file",
                "",
                "TriggerMode\t{TriggerSelector=FrameStart}\tOff",
                "TriggerActivation\t{TriggerSelector=FrameStart}\tRisingEdge",
                "TriggerSelector\tFrameStart",
            ]
        )
        with patch("builtins.open", mock_open(read_data=source_text)), patch(
            "tempfile.NamedTemporaryFile",
            return_value=_FakeNamedTemporaryFile(writes),
        ):
            filtered_path = BaslerCamera._filtered_pfs_path(
                "camera.pfs", {"TriggerActivation"}
            )

        filtered = "".join(writes)

        self.assertEqual(filtered_path, "filtered-camera.pfs")
        self.assertIn("TriggerMode", filtered)
        self.assertIn("TriggerSelector", filtered)
        self.assertNotIn("TriggerActivation", filtered)

    def test_unreadable_node_detection_matches_node_and_access_message(self) -> None:
        exc = RuntimeError(
            "Node is not readable. : AccessException thrown in node "
            "'TriggerActivation' while calling 'TriggerActivation.GetIntValue()'"
        )

        self.assertTrue(
            BaslerCamera._is_unreadable_node_error(exc, "TriggerActivation")
        )
        self.assertFalse(BaslerCamera._is_unreadable_node_error(exc, "Gain"))


if __name__ == "__main__":
    unittest.main()

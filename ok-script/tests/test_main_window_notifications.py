import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ok import og
from ok.ui.qt.MainWindow import MainWindow


class _NotificationHarness:
    show_notification = MainWindow.show_notification

    def __init__(self):
        self.tray = SimpleNamespace(showMessage=Mock())
        self.notification_manager = Mock()
        self.navigate_tab = Mock()

    def window(self):
        return self


class TestMainWindowNotifications(unittest.TestCase):
    def test_task_name_notification_title_uses_app_translation(self):
        harness = _NotificationHarness()
        translate_task_name = Mock(return_value="Translated task name")
        original_app = getattr(og, "app", None)
        og.app = SimpleNamespace(tr=translate_task_name)
        self.addCleanup(setattr, og, "app", original_app)

        with (
            patch("ok.ui.qt.MainWindow.QCoreApplication.translate", return_value="Translated status"),
            patch("ok.ui.qt.MainWindow.show_toast") as show_toast,
        ):
            harness.show_notification("Stopped", "Original task name", tray=True)

        translate_task_name.assert_called_once_with("Original task name")
        show_toast.assert_called_once_with(
            harness,
            "Translated status",
            "Translated task name",
            "neutral",
            duration=8000,
        )
        harness.notification_manager.notify_system.assert_called_once_with(
            "Translated task name", "Translated status", False, True)


if __name__ == "__main__":
    unittest.main()

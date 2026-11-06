import unittest
from unittest.mock import Mock, patch

from ok.ui.qt.MainWindow import MainWindow


class _ThemeChangeHarness:
    _apply_system_theme_change = MainWindow._apply_system_theme_change
    _schedule_system_theme_change = MainWindow._schedule_system_theme_change

    def __init__(self):
        self._theme_cooldowns = set()
        self._sync_kit_theme = Mock()


class TestMainWindowSystemTheme(unittest.TestCase):
    def test_apply_system_theme_change_syncs_theme_and_clears_cooldown(self):
        harness = _ThemeChangeHarness()
        harness._theme_cooldowns.add('system-theme')

        harness._apply_system_theme_change()

        harness._sync_kit_theme.assert_called_once_with()
        self.assertNotIn('system-theme', harness._theme_cooldowns)

    def test_schedule_system_theme_change_respects_cooldown(self):
        harness = _ThemeChangeHarness()

        with patch("ok.ui.qt.MainWindow.QTimer.singleShot") as single_shot:
            harness._schedule_system_theme_change()
            single_shot.assert_called_once_with(250, harness._apply_system_theme_change)
            self.assertIn('system-theme', harness._theme_cooldowns)

            # Second call while in cooldown does not schedule another timer
            single_shot.reset_mock()
            harness._schedule_system_theme_change()
            single_shot.assert_not_called()


if __name__ == "__main__":
    unittest.main()

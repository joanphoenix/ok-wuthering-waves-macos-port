import unittest
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ok.ui.qt.MainWindow import (
    MainWindow,
    game_starting_or_started,
    request_pyappify_shutdown,
)


class TestMainWindowStartupTab(unittest.TestCase):
    def test_game_starting_or_started(self):
        self.assertTrue(game_starting_or_started(auto_start_enabled=True))
        self.assertTrue(game_starting_or_started(start_task_requested=True))
        self.assertTrue(game_starting_or_started(start_controller=SimpleNamespace(starting=True)))
        self.assertTrue(game_starting_or_started(executor=SimpleNamespace(paused=False)))
        self.assertFalse(game_starting_or_started(executor=SimpleNamespace(paused=True)))

    @patch("ok.ui.qt.MainWindow.pyappify.kill_pyappify")
    def test_pyappify_shutdown_does_not_block_gui_thread(self, kill_pyappify):
        thread = request_pyappify_shutdown()

        self.assertTrue(thread.daemon)
        thread.join(1)
        kill_pyappify.assert_called_once_with()

    def test_dispose_stops_timers(self):
        timer = SimpleNamespace(stop=Mock())
        window = SimpleNamespace(
            game_process_poll_timer=timer,
            update_check_timer=timer,
            tray=SimpleNamespace(hide=Mock()),
            run_bar=SimpleNamespace(dispose=Mock()),
            _pages={},
            findChildren=lambda _cls: [],
        )

        MainWindow.dispose(window)

        self.assertEqual(2, timer.stop.call_count)

    def test_prefers_tasks_page(self):
        tasks_page = object()
        window = SimpleNamespace(
            tasks_page=tasks_page,
            imported_tabs={"tasks.okscript": object()},
        )

        self.assertIs(tasks_page, MainWindow.startup_task_tab(window))

    def test_falls_back_to_imported_tabs(self):
        imported_tab = object()
        window = SimpleNamespace(
            tasks_page=None,
            imported_tabs={"tasks.okscript": imported_tab},
        )

        self.assertIs(imported_tab, MainWindow.startup_task_tab(window))

    def test_falls_back_to_imported_tab_controller(self):
        custom_tab = object()
        window = SimpleNamespace(
            tasks_page=None,
            imported_tabs={},
            _imported_tab_controller=SimpleNamespace(
                custom_tabs={"plugin": [custom_tab]}
            ),
        )

        self.assertIs(custom_tab, MainWindow.startup_task_tab(window))

    def test_returns_none_when_no_tabs_exist(self):
        window = SimpleNamespace(
            tasks_page=None,
            imported_tabs={},
            _imported_tab_controller=None,
        )

        self.assertIsNone(MainWindow.startup_task_tab(window))


if __name__ == "__main__":
    unittest.main()

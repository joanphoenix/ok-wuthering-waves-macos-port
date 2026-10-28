import unittest
from unittest.mock import MagicMock

from src.task.DailyTask import DailyTask
from src.task.ForgeryTask import ForgeryTask
from src.task.TacetTask import TacetTask


class TestF2ChallengeSelection(unittest.TestCase):

    def test_forgery_task_config_and_types(self):
        task = ForgeryTask(MagicMock(), MagicMock())
        self.assertEqual(task.total_number, 20)
        self.assertEqual(task.default_config['Which Forgery Challenge to Farm'], 1)
        config_type = task.config_type['Which Forgery Challenge to Farm']
        self.assertEqual(config_type['type'], 'int')
        self.assertEqual(config_type['min'], 1)
        self.assertEqual(config_type['max'], 20)

    def test_forgery_bounds(self):
        task = ForgeryTask(MagicMock(), MagicMock())
        task.open_boss_book = MagicMock()
        task.info_set = MagicMock()
        with self.assertRaises(IndexError):
            task.teleport_into_domain(0)
        with self.assertRaises(IndexError):
            task.teleport_into_domain(21)

    def test_tacet_task_config_and_types(self):
        task = TacetTask(MagicMock(), MagicMock())
        self.assertEqual(task.total_number, 21)
        self.assertEqual(task.default_config['Which Tacet Suppression to Farm'], 1)
        config_type = task.config_type['Which Tacet Suppression to Farm']
        self.assertEqual(config_type['type'], 'int')
        self.assertEqual(config_type['min'], 1)
        self.assertEqual(config_type['max'], 21)

    def test_open_boss_book_coords_and_tab_mapping(self):
        from src.task.BaseWWTask import BaseWWTask
        from ok import Box

        task = BaseWWTask.__new__(BaseWWTask)
        task.log_info = MagicMock()
        task.log_debug = MagicMock()
        task.sleep = MagicMock()
        task.click_relative = MagicMock()
        task.click_box = MagicMock()
        task.ocr = MagicMock(return_value=[])  # No OCR match -> test fallback coordinates

        expected_coords = {
            'moni': (0.24, 0.24),      # Row 2: Simulation Challenge
            'ningsu': (0.24, 0.34),    # Row 3: Forgery Challenge
            'qiangdi': (0.24, 0.44),   # Row 4: Boss Challenge
            'zhange': (0.24, 0.54),    # Row 5: Weekly Challenge
            'wuyin': (0.24, 0.64),     # Row 6: Tacet Suppression
            'canxiang': (0.24, 0.74),  # Row 7: Tacet Discord Nest
            'mengyan': (0.24, 0.84),   # Row 8: Nightmare Purification
        }

        for name, (ex_x, ex_y) in expected_coords.items():
            task.click_relative.reset_mock()
            task.open_boss_book(name)
            task.click_relative.assert_called_once_with(ex_x, ex_y, after_sleep=2, name=name)

        # Test OCR dynamic match
        mock_box = Box(100, 600, 200, 50, name='Tacet Suppression')
        task.ocr = MagicMock(return_value=[mock_box])
        task.click_box.reset_mock()
        task.open_boss_book('wuyin')
        task.click_box.assert_called_once_with(mock_box, after_sleep=2)

        # Test OCR match on split word (e.g. 'Suppression')
        mock_box_split = Box(100, 600, 200, 50, name='Suppression')
        task.ocr = MagicMock(return_value=[mock_box_split])
        task.click_box.reset_mock()
        task.open_boss_book('wuyin')
        task.click_box.assert_called_once_with(mock_box_split, after_sleep=2)

        # Test rejection of Tacet Discord Nest when searching for wuyin
        nest_box = Box(100, 700, 200, 50, name='Tacet Discord Nest')
        task.ocr = MagicMock(return_value=[nest_box, mock_box_split])
        task.click_box.reset_mock()
        task.open_boss_book('wuyin')
        task.click_box.assert_called_once_with(mock_box_split, after_sleep=2)

        # Test template match priority for book_wuyin
        template_box = Box(100, 500, 50, 50, name='book_wuyin')
        task.find_one = MagicMock(return_value=template_box)
        task.click_box.reset_mock()
        task.open_boss_book('wuyin')
        task.click_box.assert_called_once_with(template_box, after_sleep=2)

    def test_tacet_task_fast_travel_vs_team(self):
        task = TacetTask(MagicMock(), MagicMock())
        task.ensure_main = MagicMock()
        task.wait_in_team_and_world = MagicMock()
        task.openF2Book = MagicMock()
        task.get_stamina = MagicMock(side_effect=[(120, 0, 120), (0, 0, 0)])
        task.open_boss_book = MagicMock()
        task.teleport_to_tacet = MagicMock(return_value=False)  # open world fast travel
        task.wait_click_travel = MagicMock()
        task.click_team_challenge = MagicMock()
        task.combat_once = MagicMock()
        task.walk_to_treasure = MagicMock()
        task.pick_f = MagicMock()
        task.has_claim_stamina = MagicMock(return_value=True)
        task.use_stamina = MagicMock(return_value=(False, 60))
        task.info_incr = MagicMock()
        task.click_relative = MagicMock()
        task.not_enough_stamina = MagicMock()

        task.farm_tacet()
        task.teleport_to_tacet.assert_called_once()
        task.wait_click_travel.assert_called_once()
        task.click_team_challenge.assert_not_called()

    def test_tacet_bounds(self):
        task = TacetTask(MagicMock(), MagicMock())
        task.info_set = MagicMock()
        with self.assertRaises(IndexError):
            task.teleport_to_tacet(-1)
        with self.assertRaises(IndexError):
            task.teleport_to_tacet(21)

    def test_daily_task_config_and_types(self):
        task = DailyTask(MagicMock(), MagicMock())
        self.assertEqual(task.default_config['Which Forgery Challenge to Farm'], 1)
        self.assertEqual(task.default_config['Which Tacet Suppression to Farm'], 1)
        self.assertEqual(task.config_type['Which Forgery Challenge to Farm']['type'], 'int')
        self.assertEqual(task.config_type['Which Forgery Challenge to Farm']['min'], 1)
        self.assertEqual(task.config_type['Which Forgery Challenge to Farm']['max'], 20)
        self.assertEqual(task.config_type['Which Tacet Suppression to Farm']['type'], 'int')
        self.assertEqual(task.config_type['Which Tacet Suppression to Farm']['min'], 1)
        self.assertEqual(task.config_type['Which Tacet Suppression to Farm']['max'], 21)

    def test_config_widgets_instantiation(self):
        import sys
        from PySide6.QtWidgets import QApplication
        from ok import og
        from ok.ui.qt.tasks.ConfigItemFactory import config_widget
        from ok.ui.qt.tasks.LabelAndSpinBox import LabelAndSpinBox

        app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
        og.app = app

        class MockConfig(dict):
            def get_default(self, k):
                return self.get(k)

        for task in (ForgeryTask(MagicMock(), MagicMock()),
                     TacetTask(MagicMock(), MagicMock()),
                     DailyTask(MagicMock(), MagicMock())):
            cfg = MockConfig(task.default_config)
            for k in task.default_config:
                w = config_widget(task.config_type, task.config_description, cfg, k, task.default_config[k], task)
                self.assertIsNotNone(w)
                if 'Which Forgery Challenge' in k or 'Which Tacet Suppression' in k:
                    self.assertIsInstance(w, LabelAndSpinBox)
                    w.spin_box.resize(180, 33)
                    self.assertGreaterEqual(w.spin_box.lineEdit().geometry().width(), 80)
                    self.assertEqual(w.spin_box.lineEdit().text(), str(task.default_config[k]))

    def test_spinbox_visibility_and_interaction_in_task_card(self):
        import sys, os, tempfile
        from PySide6.QtWidgets import QApplication, QMainWindow
        from ok import og
        from ok.ui.qt.tasks.TaskCard import TaskCard
        from ok.util.config import Config
        from ok.ui.qt.tasks.LabelAndSpinBox import LabelAndSpinBox

        app = QApplication.instance() or QApplication(sys.argv)
        og.app = app
        og.config = {}
        og.executor = MagicMock()
        og.executor.waiting_for_task.return_value = False
        og.executor.is_task_running.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            og.app_path = tmpdir
            configs_dir = os.path.join(tmpdir, 'configs')
            os.makedirs(configs_dir, exist_ok=True)

            win = QMainWindow()

            for task_cls, conf_name, key in [
                (ForgeryTask, 'forgery', 'Which Forgery Challenge to Farm'),
                (TacetTask, 'tacet', 'Which Tacet Suppression to Farm'),
            ]:
                task = task_cls(MagicMock(), MagicMock())
                task.config = Config(conf_name, task.default_config, configs_dir)
                card = TaskCard(task, True)
                win.setCentralWidget(card)
                win.show()
                card.setExpand(True)
                for _ in range(5):
                    app.processEvents()

                widget = card.config_widget_by_key[key]
                self.assertIsInstance(widget, LabelAndSpinBox)
                sb = widget.spin_box
                line_edit = sb.lineEdit()

                # Ensure lineEdit has full width and visible number
                self.assertGreaterEqual(line_edit.geometry().width(), 100)
                self.assertTrue(line_edit.isVisible())
                self.assertEqual(line_edit.text(), '1')

                # Ensure up button increments and text updates
                sb.upButton.click()
                app.processEvents()
                self.assertEqual(sb.value(), 2)
                self.assertEqual(line_edit.text(), '2')

                # Ensure keyboard typing updates value and text
                line_edit.clear()
                line_edit.insert('15')
                sb.interpretText()
                app.processEvents()
                self.assertEqual(sb.value(), 15)
                self.assertEqual(line_edit.text(), '15')
                self.assertGreaterEqual(line_edit.geometry().width(), 100)


if __name__ == '__main__':
    unittest.main()

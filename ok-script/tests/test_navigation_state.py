import unittest

from ok.ui.qt.MainWindow import MainWindow


class _NavigationStateHarness:
    _save_navigation_state = MainWindow._save_navigation_state

    def __init__(self, initial_state=False):
        self.ok_config = {'navigation_expanded': initial_state}


class TestNavigationState(unittest.TestCase):
    def test_save_navigation_state_persists_expanded_flag(self):
        harness = _NavigationStateHarness(initial_state=True)

        harness._save_navigation_state(True)
        self.assertFalse(harness.ok_config['navigation_expanded'])

        harness._save_navigation_state(False)
        self.assertTrue(harness.ok_config['navigation_expanded'])


if __name__ == '__main__':
    unittest.main()

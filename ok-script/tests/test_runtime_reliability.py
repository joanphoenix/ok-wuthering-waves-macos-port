import hashlib
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from ok.device.interaction_methods.pynput import PynputInteraction


@pytest.fixture
def input_backend():
    controller = MagicMock()
    fake = SimpleNamespace(mouse=SimpleNamespace(Controller=lambda: controller,
                            Button=SimpleNamespace(left='left', right='right', middle='middle')))
    window = MagicMock()
    window.is_foreground.return_value = True
    capture = MagicMock()
    capture.get_abs_cords.side_effect = lambda x, y: (x, y)
    with patch.dict('sys.modules', {'pynput': fake}), patch('ok.device.interaction_methods.pynput.is_admin', return_value=True):
        yield PynputInteraction(capture, window), window, controller


def test_background_scroll_and_swipe_emit_nothing(input_backend):
    backend, window, controller = input_backend
    window.is_foreground.return_value = False
    backend.scroll(10, 10, 2)
    backend.swipe(0, 0, 20, 20, 500)
    controller.press.assert_not_called()
    controller.scroll.assert_not_called()


@pytest.mark.parametrize('operation', ['click', 'swipe'])
def test_interruption_releases_mouse(input_backend, operation):
    backend, window, controller = input_backend
    calls = 0
    def interrupted(_seconds):
        nonlocal calls
        calls += 1
        if operation == 'click' or calls == 2:
            raise RuntimeError('interrupted')
    with patch('ok.device.interaction_methods.pynput.time.sleep', side_effect=interrupted):
        with pytest.raises(RuntimeError):
            if operation == 'click':
                backend.click()
            else:
                backend.swipe(0, 0, 20, 20, 500)
    controller.press.assert_called_once_with('left')
    controller.release.assert_called_once_with('left')
    assert not backend._held_buttons


def test_scroll_stops_when_focus_changes(input_backend):
    backend, window, controller = input_backend
    controller.scroll.side_effect = lambda *_: setattr(window.is_foreground, 'return_value', False)
    backend.scroll(10, 10, 10)
    assert controller.scroll.call_count == 1


@pytest.mark.skipif(os.name == 'nt', reason='POSIX file lock')
def test_duplicate_launch_does_not_kill_owner(tmp_path):
    import fcntl
    from ok.util import process
    name = hashlib.md5(os.getcwd().encode()).hexdigest()
    with open(tmp_path / f'ok-script-{name}.lock', 'a+') as owner:
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with patch.object(process, '_mutex_handle', None), patch.object(process.tempfile, 'gettempdir', return_value=str(tmp_path)), patch.object(process, '_terminate_previous_instances') as terminate:
            assert not process.check_mutex(wait_time=0)
            terminate.assert_not_called()

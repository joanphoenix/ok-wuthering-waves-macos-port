"""Optional macOS tweaks for Qt spin boxes and offscreen frameless windows.

The live UI uses the kit ``NumberBox``. The Fluent widgets these helpers were
written for are gone, so nothing here depends on PySide6-Fluent-Widgets.
"""
import os
import sys

from PySide6.QtWidgets import QSpinBox

SPINBOX_QSS = '\n        QAbstractSpinBox::up-button, QAbstractSpinBox::down-button,\n        SpinBox::up-button, SpinBox::down-button,\n        DoubleSpinBox::up-button, DoubleSpinBox::down-button,\n        CompactSpinBox::up-button, CompactSpinBox::down-button,\n        CompactDoubleSpinBox::up-button, CompactDoubleSpinBox::down-button {\n            width: 0px;\n            height: 0px;\n            border: none;\n        }\n    '


def fix_spinbox_layout(spin_box):
    if sys.platform != 'darwin':
        return
    spin_box.setButtonSymbols(QSpinBox.UpDownArrows)
    if SPINBOX_QSS not in spin_box.styleSheet():
        spin_box.setStyleSheet(spin_box.styleSheet() + SPINBOX_QSS)
    spin_box.lineEdit().setTextMargins(10, 0, 80, 0)


def install_macos_compatibility():
    if sys.platform != 'darwin':
        return
    if os.environ.get('QT_QPA_PLATFORM', '').split(':')[0] in {'offscreen', 'minimal'}:
        try:
            import qframelesswindow.mac as mac_frameless
            mac_frameless.MacFramelessWindowBase.updateFrameless = lambda self: None
            mac_frameless.MacFramelessWindowBase.setSystemTitleBarButtonVisible = (
                lambda self, isVisible: setattr(self, '_isSystemButtonVisible', isVisible)
            )
            mac_frameless.MacFramelessWindowBase._updateSystemButtonRect = lambda self: None
            mac_frameless.MacFramelessWindowBase._hideSystemTitleBar = lambda self: None
        except Exception:
            pass

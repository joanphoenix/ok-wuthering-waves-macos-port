"""Optional macOS tweaks for the retired Fluent spin boxes.

The live UI uses the kit ``NumberBox``. These helpers stay importable without
PySide6-Fluent-Widgets, which upstream no longer ships.
"""
import os
import sys

from PySide6.QtWidgets import QSpinBox

SPINBOX_QSS = '\n        QAbstractSpinBox::up-button, QAbstractSpinBox::down-button,\n        SpinBox::up-button, SpinBox::down-button,\n        DoubleSpinBox::up-button, DoubleSpinBox::down-button,\n        CompactSpinBox::up-button, CompactSpinBox::down-button,\n        CompactDoubleSpinBox::up-button, CompactDoubleSpinBox::down-button {\n            width: 0px;\n            height: 0px;\n            border: none;\n        }\n    '


def _compact_spin_box_type():
    try:
        from qfluentwidgets.components.widgets.spin_box import CompactSpinBox
    except ImportError:
        return ()
    return CompactSpinBox


def fix_spinbox_layout(spin_box):
    if sys.platform != 'darwin':
        return
    spin_box.setButtonSymbols(QSpinBox.UpDownArrows)
    if SPINBOX_QSS not in spin_box.styleSheet():
        spin_box.setStyleSheet(spin_box.styleSheet() + SPINBOX_QSS)
    margin = 30 if isinstance(spin_box, _compact_spin_box_type()) else 80
    spin_box.lineEdit().setTextMargins(10, 0, margin, 0)


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

    try:
        import qfluentwidgets.common.style_sheet as sheets
        from qfluentwidgets.components.widgets.spin_box import CompactSpinBox, SpinBoxBase
    except ImportError:
        return
    if getattr(sheets.getStyleSheetFromFile, '_ok_macos', False):
        return
    original_sheet = sheets.getStyleSheetFromFile
    original_init = SpinBoxBase.__init__

    def stylesheet(path):
        text = original_sheet(path)
        for font, replacement in [('Segoe UI SemiBold', ".AppleSystemUIFont"),
                                  ('Segoe UI', ".AppleSystemUIFont"), ('Consolas', 'Menlo')]:
            text = text.replace("'" + font + "'", "'" + replacement + "'")
            text = text.replace('"' + font + '"', "'" + replacement + "'")
        return text + SPINBOX_QSS

    def initialize(widget, *args, **kwargs):
        original_init(widget, *args, **kwargs)
        # The shared stylesheet handles geometry; reserve room for Fluent buttons.
        widget.setButtonSymbols(QSpinBox.UpDownArrows)
        widget.lineEdit().setTextMargins(10, 0, 30 if isinstance(widget, CompactSpinBox) else 80, 0)

    stylesheet._ok_macos = True
    sheets.getStyleSheetFromFile = stylesheet
    SpinBoxBase.__init__ = initialize

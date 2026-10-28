import sys

from PySide6.QtCore import Qt, QTranslator, QCoreApplication
from PySide6.QtGui import QGuiApplication, QFont
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentTranslator, InfoBar, InfoBarPosition, setTheme, setFontFamilies

from ok import Logger
from ok.ui.qt import resources
from ok.ui.qt.common.config import cfg

logger = Logger.get_logger(__name__)


def init_app_config():
    logger.debug(
        f'resources.qt_resource_name {resources.qt_resource_name} cfg.themeMode')

    # Qt High DPI rounding policy must be set before QApplication instantiation
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    if sys.platform == "darwin":
        # Native Apple typography mapping: eliminate Segoe UI / Consolas fallback delay & warnings
        mac_fonts = ['.AppleSystemUIFont', 'PingFang SC', 'Helvetica Neue', 'Arial']
        setFontFamilies(mac_fonts)
        QFont.insertSubstitutions('Segoe UI', mac_fonts)
        QFont.insertSubstitutions('Segoe UI SemiBold', ['.AppleSystemUIFont', 'PingFang SC', 'Helvetica Neue'])
        QFont.insertSubstitutions('Microsoft YaHei', ['PingFang SC', 'Hiragino Sans GB', 'Heiti SC'])
        QFont.insertSubstitutions('Consolas', ['Menlo', 'Monaco', 'Courier New'])
        QFont.insertSubstitutions('Courier', ['Menlo', 'Monaco', 'Courier New'])

        from ok.ui.qt.util.macos_compat import install_macos_compatibility
        install_macos_compatibility()

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

    if sys.platform == "darwin":
        app.setFont(QFont('.AppleSystemUIFont', 13))

    locale = cfg.get(cfg.language).value
    translator = FluentTranslator(locale)
    app.installTranslator(translator)
    translator = QTranslator(app)

    if translator.load(locale.name(), ":/i18n"):
        translator.setParent(app)
        app.installTranslator(translator)
        QCoreApplication.installTranslator(translator)
        logger.info(f"translator install success {locale}, {QCoreApplication.translate('MainWindow', 'Debug')}")
    else:
        logger.info(f"No translation available for {locale}, falling back to English/default.")
    # qconfig.theme = cfg.themeMode.value
    setTheme(cfg.themeMode.value)
    return app, locale


def get_localized_app_config(config, key):
    locale = cfg.get(cfg.language).value.name()

    if config.get(locale):
        config_dict = config.get(locale)
    else:
        config_dict = config.get('default')
    if config_dict:
        return config_dict.get(key)


def show_info_bar(window, message, title=None, error=False):
    bar = InfoBar.error if error else InfoBar.info
    title = QCoreApplication.translate('app', title)
    message = QCoreApplication.translate('app', message)
    if title is None:
        title = f"{QCoreApplication.translate('app', 'Error') if error else QCoreApplication.translate('app', 'Info')}:"
    bar(
        title=title,
        content=message,
        orient=Qt.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=8000,  # won't disappear automatically
        parent=window
    )


def center_window(app, window):
    screen = app.primaryScreen()
    size = screen.size()
    # Calculate half the screen size
    half_screen_width = size.width() / 2
    half_screen_height = size.height() / 2
    window.move(half_screen_width / 2, half_screen_height / 2)

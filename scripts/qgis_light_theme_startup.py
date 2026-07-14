# -*- coding: utf-8 -*-
"""Force a light UI for QGIS regardless of the desktop colour scheme.

Executed via the PYQGIS_STARTUP environment variable set by the launcher
scripts (scripts/start_qgis.sh / start_qgis_ltr.sh). On Qt 6.8+ (QGIS 4.x)
the application-level colour scheme is pinned to Light so a dark desktop
(e.g. COSMIC in dark mode) does not switch QGIS to a dark palette. On
older Qt (QGIS 3.x LTR) the API does not exist and this is a no-op — Qt5
does not follow the portal colour scheme anyway.
"""


def _force_light_theme() -> None:
    try:
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtGui import QGuiApplication, QPalette

        hints = QGuiApplication.styleHints()
        # Resolved dynamically: Qt.ColorScheme only exists on Qt 6.5+.
        color_scheme = getattr(Qt, "ColorScheme", None)
        if color_scheme is not None and hasattr(hints, "setColorScheme"):
            hints.setColorScheme(color_scheme.Light)

        # Belt and braces: if the platform theme already handed the app a
        # dark palette (or ignores the colour-scheme override), replace it
        # with the standard light Fusion palette.
        app = QGuiApplication.instance()
        if app is not None:
            window = app.palette().color(QPalette.ColorRole.Window)
            if window.lightness() < 128:
                from qgis.PyQt.QtWidgets import QApplication, QStyleFactory

                style = QStyleFactory.create("Fusion")
                if style is not None:
                    QApplication.setPalette(style.standardPalette())
    except Exception:  # nosec B110 — cosmetic only, never block startup
        pass


_force_light_theme()

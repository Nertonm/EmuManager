from __future__ import annotations


class MainWindowUIThemeMixin:
    def apply_dark_theme(self, qt, qtgui, window):
        try:
            qt.QApplication.setStyle(qt.QStyleFactory.create("Fusion"))
            palette = qtgui.QPalette()
            palette.setColor(qtgui.QPalette.ColorRole.Window, qtgui.QColor(45, 45, 45))
            palette.setColor(
                qtgui.QPalette.ColorRole.WindowText,
                qtgui.QColor(220, 220, 220),
            )
            palette.setColor(qtgui.QPalette.ColorRole.Base, qtgui.QColor(30, 30, 30))
            palette.setColor(
                qtgui.QPalette.ColorRole.AlternateBase,
                qtgui.QColor(45, 45, 45),
            )
            palette.setColor(
                qtgui.QPalette.ColorRole.ToolTipBase,
                qtgui.QColor(220, 220, 220),
            )
            palette.setColor(
                qtgui.QPalette.ColorRole.ToolTipText,
                qtgui.QColor(220, 220, 220),
            )
            palette.setColor(qtgui.QPalette.ColorRole.Text, qtgui.QColor(220, 220, 220))
            palette.setColor(qtgui.QPalette.ColorRole.Button, qtgui.QColor(60, 60, 60))
            palette.setColor(
                qtgui.QPalette.ColorRole.ButtonText,
                qtgui.QColor(220, 220, 220),
            )
            palette.setColor(
                qtgui.QPalette.ColorRole.BrightText,
                qtgui.QColor(255, 50, 50),
            )
            palette.setColor(qtgui.QPalette.ColorRole.Link, qtgui.QColor(50, 150, 250))
            palette.setColor(
                qtgui.QPalette.ColorRole.Highlight,
                qtgui.QColor(50, 150, 250),
            )
            palette.setColor(
                qtgui.QPalette.ColorRole.HighlightedText,
                qtgui.QColor(0, 0, 0),
            )
            qt.QApplication.setPalette(palette)

            window.setStyleSheet(
                """
                QMainWindow { background-color: #2d2d2d; }
                QTabWidget::pane {
                    border: 1px solid #3d3d3d;
                    background-color: #2d2d2d;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background: #3c3c3c;
                    color: #aaa;
                    padding: 8px 16px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    margin-right: 2px;
                    font-weight: bold;
                }
                QTabBar::tab:selected {
                    background: #505050;
                    color: #fff;
                    border-bottom: 2px solid #3daee9;
                }
                QTabBar::tab:hover { background: #444; color: #ddd; }

                QGroupBox {
                    border: 1px solid #444;
                    margin-top: 1.2em;
                    font-weight: bold;
                    border-radius: 6px;
                    padding-top: 12px;
                    padding-bottom: 8px;
                    background-color: #333;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 5px;
                    color: #3daee9;
                    background-color: #2d2d2d;
                    border-radius: 2px;
                }

                QPushButton {
                    padding: 8px 16px;
                    border-radius: 4px;
                    background-color: #3c3c3c;
                    border: 1px solid #555;
                    min-width: 80px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #4a4a4a; border-color: #3daee9; }
                QPushButton:pressed {
                    background-color: #2a2a2a; border-color: #2a2a2a;
                }
                QPushButton:disabled {
                    background-color: #333;
                    color: #666;
                    border-color: #444;
                }

                QListWidget {
                    border: 1px solid #444;
                    border-radius: 4px;
                    background-color: #1e1e1e;
                    alternate-background-color: #252525;
                    padding: 4px;
                }
                QListWidget::item { padding: 4px; border-radius: 2px; }
                QListWidget::item:selected { background-color: #3daee9; color: #fff; }
                QListWidget::item:hover { background-color: #333; }

                QTextEdit {
                    border: 1px solid #444;
                    font-family: "Consolas", "Monaco", monospace;
                    background-color: #1e1e1e;
                    border-radius: 4px;
                    padding: 6px;
                    color: #ccc;
                }

                QProgressBar {
                    border: 1px solid #444;
                    border-radius: 4px;
                    text-align: center;
                    background-color: #1e1e1e;
                    color: #fff;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background-color: #3daee9;
                    width: 10px;
                    border-radius: 2px;
                }

                QStatusBar {
                    background-color: #252525;
                    border-top: 1px solid #333;
                    color: #aaa;
                }
                QLabel { color: #ddd; }
                QSplitter::handle { background-color: #444; width: 2px; }

                QComboBox {
                    padding: 4px;
                    border-radius: 4px;
                    background-color: #3c3c3c;
                    border: 1px solid #555;
                    color: #eee;
                }
                QComboBox::drop-down { border: 0px; }
                QSpinBox {
                    padding: 4px;
                    border-radius: 4px;
                    background-color: #3c3c3c;
                    border: 1px solid #555;
                    color: #eee;
                }
                QCheckBox { spacing: 8px; color: #eee; }
                QCheckBox::indicator { width: 16px; height: 16px; }
            """
            )
        except Exception:
            try:
                qt.QApplication.setStyle(qt.QStyleFactory.create("Fusion"))
                palette = qtgui.QPalette()
                palette.setColor(qtgui.QPalette.Window, qtgui.QColor(45, 45, 45))
                palette.setColor(qtgui.QPalette.WindowText, qtgui.QColor(220, 220, 220))
                palette.setColor(qtgui.QPalette.Base, qtgui.QColor(30, 30, 30))
                palette.setColor(qtgui.QPalette.AlternateBase, qtgui.QColor(45, 45, 45))
                palette.setColor(
                    qtgui.QPalette.ToolTipBase,
                    qtgui.QColor(220, 220, 220),
                )
                palette.setColor(
                    qtgui.QPalette.ToolTipText,
                    qtgui.QColor(220, 220, 220),
                )
                palette.setColor(qtgui.QPalette.Text, qtgui.QColor(220, 220, 220))
                palette.setColor(qtgui.QPalette.Button, qtgui.QColor(60, 60, 60))
                palette.setColor(qtgui.QPalette.ButtonText, qtgui.QColor(220, 220, 220))
                palette.setColor(
                    qtgui.QPalette.BrightText,
                    qtgui.QColor(255, 50, 50),
                )
                palette.setColor(qtgui.QPalette.Link, qtgui.QColor(50, 150, 250))
                palette.setColor(qtgui.QPalette.Highlight, qtgui.QColor(50, 150, 250))
                palette.setColor(qtgui.QPalette.HighlightedText, qtgui.QColor(0, 0, 0))
                qt.QApplication.setPalette(palette)
            except Exception:
                pass

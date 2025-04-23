import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout, QMenuBar, QMenu, QAction
from PyQt5.QtCore import Qt
from widgets.video_player import VideoPlayer
from widgets.text_editor import TextEditor
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QShortcut

import sys
import os
# Determine if running from a bundled EXE or source code
if getattr(sys, 'frozen', False):  # If the script is running as a bundled exe
    app_path = sys._MEIPASS  # Temporary folder where resources are extracted
else:
    app_path = os.path.dirname(__file__)  # If running from source code


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Speech Annotation Tool")
        self.setGeometry(100, 100, 1200, 600)

        # --- Styling for Main Window ---
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5; /* Light gray background for main window */
            }
            QMenuBar {
                background-color: #f0f0f0;
                border-bottom: 1px solid #c0c0c0;
            }
            QMenuBar::item {
                background: transparent;
            }
            QMenuBar::item:selected { /* when selected by mouse or keyboard */
                background-color: #e0e0e0;
            }
            QMenuBar::item:pressed {
                background-color: #d0d0d0;
            }
            QMenu {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                border-radius: 2px;
                padding: 3px;
                margin: 0px;
            }
            QMenu::item {
                padding: 2px 25px 2px 20px;
                border: 1px solid transparent; /* reserve space for selection border */
            }
            QMenu::item:selected {
                background-color: #e0e0e0;
            }
            QMenu::separator {
                height: 1px;
                background: lightgray;
                margin-left: 10px;
                margin-right: 5px;
            }
            QAction { /* Style for actions in menu */
                background: transparent;
            }
            QAction:hover {
                background-color: #e0e0e0;
            }
        """)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(5)  # Thinner splitter handle
        splitter.setStyleSheet("QSplitter::handle { background-color: #c0c0c0; }")  # Style splitter handle

        self.video_player = VideoPlayer(self)  # Pass MainWindow instance here
        self.text_editor = TextEditor(self.video_player.media_player)  # Pass media_player instance
        self.video_player.set_text_editor(self.text_editor)  # Set text editor in video player

        splitter.addWidget(self.video_player)
        splitter.addWidget(self.text_editor)
        splitter.setStretchFactor(0, 3)  # Video player wider
        splitter.setStretchFactor(1, 2)  # Text editor narrower

        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)  # Use layout directly on central widget
        central_layout.addWidget(splitter)
        central_layout.setContentsMargins(0, 0, 0, 0)  # No margins around splitter within central widget

        self.setCentralWidget(central_widget)

        self.setup_menu()

        # --- Application-Wide Keyboard Shortcuts ---
        # Alt+Arrow Key Seeking Shortcuts (Application-Wide) - CHANGED TO ALT+ARROW
        QShortcut(QKeySequence(Qt.ALT + Qt.Key_Right), self, activated=self.video_player.seek_forward)  # Use self (MainWindow) as parent
        QShortcut(QKeySequence(Qt.ALT + Qt.Key_Left), self, activated=self.video_player.seek_backward)  # Use self (MainWindow) as parent

        # Ctrl+Space Pause Shortcut (Application-Wide) - KEPT CTRL+SPACE
        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_Space), self, activated=self.video_player.toggle_play_pause)  # Use self (MainWindow) as parent

    def focusInEvent(self, event):
        print(f"MainWindow Focused In")  # Focus Debugging
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        print(f"MainWindow Focused Out")  # Focus Debugging
        super().focusOutEvent(event)

    def setup_menu(self):
        menu_bar = self.menuBar()  # Get the menu bar of the main window
        file_menu = menu_bar.addMenu("&File")  # Create "File" menu

        load_video_action = QAction("Load Video", self)  # Action for loading video
        icon_path_load_menu = os.path.join(app_path, 'icons', 'load_menu.png')  # Example icon file

        load_video_action.setIcon(QIcon(icon_path_load_menu))  # Set icon for Load Video
        load_video_action.triggered.connect(self.video_player.load_video)
        file_menu.addAction(load_video_action)

        clear_text_action = QAction("Clear Text", self)  # Action to clear text editor
        icon_path_clear_menu = os.path.join(app_path, 'icons', 'clear_menu.png')  # Example icon file

        clear_text_action.setIcon(QIcon(icon_path_clear_menu))  # Set icon for Clear Text
        clear_text_action.triggered.connect(self.clear_text_editor)
        file_menu.addAction(clear_text_action)

        exit_action = QAction("Exit", self)  # Action to exit application
        icon_path_exit_menu = os.path.join(app_path, 'icons', 'exit_menu.png')  # Example icon file

        exit_action.setIcon(QIcon(icon_path_exit_menu))  # Set icon for Exit
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def clear_text_editor(self):
        self.text_editor.text_edit.clear()  # Access text_edit from TextEditor widget

    def closeEvent(self, event):
        self.video_player.stop_video()  # Stop video on closing
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # --- Application-level styling (optional, could also be in mainwindow styleSheet) ---
    app.setStyleSheet("""
        QToolTip {
            color: #333;
            background-color: #f8f8f8;
            border: 1px solid #c0c0c0;
            padding: 2px 5px;
            border-radius: 2px;
        }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
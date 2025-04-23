import sys
import os
# import json # No longer needed?
from PyQt5.QtWidgets import (QApplication, QMainWindow, QSplitter, QWidget,
                             QVBoxLayout, QMenuBar, QMenu, QAction, QMessageBox,
                             QShortcut, QInputDialog, QLabel)
from PyQt5.QtCore import Qt, QSettings, QTimer, QUrl, QSize
from PyQt5.QtGui import QIcon, QKeySequence


# Assuming video_player and text_editor are in a 'widgets' subfolder
from widgets.video_player import VideoPlayer
from widgets.text_editor import TextEditor

# --- Path Setup (Keep as is) ---
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(BASE_DIR, 'icons')

def get_icon_path(icon_name):
    path = os.path.join(ICONS_DIR, icon_name)
    return path

# --- Main Window ---
class MainWindow(QMainWindow):
    APP_VERSION = "1.3" # Define app version

    def __init__(self):
        super().__init__()
        self.settings = QSettings("Vibhasa @ IIT Mandi", "Annotime Tool") # Use specific app name

        self.setWindowTitle("Annotime - Speech Annotation Tool") # Updated title
        # --- Set the Window Icon HERE ---
        # Replace 'app_logo.png' with the actual filename of your logo
        app_icon_path = get_icon_path('logo_s.png')
        if os.path.exists(app_icon_path):
             self.setWindowIcon(QIcon(app_icon_path))
        else:
             print(f"Warning: Application icon not found at {app_icon_path}")


        self.setGeometry(100, 100, 1280, 720) # Slightly larger default size

        # --- Enhanced Styling ---
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f4f4f4; /* Slightly different bg */
            }
            QMenuBar {
                background-color: #e8e8e8; /* Lighter menubar */
                border-bottom: 1px solid #c8c8c8;
                padding: 3px;
                spacing: 5px; /* Spacing between menu items */
            }
            QMenuBar::item {
                background: transparent;
                padding: 5px 10px; /* More padding */
                border-radius: 3px;
            }
            QMenuBar::item:selected { background-color: #d0d8e0; } /* Subtle selection */
            QMenuBar::item:pressed { background-color: #c8d0d8; }
            QMenu {
                background-color: #f8f8f8; /* Lighter menu background */
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 30px 5px 25px; /* More padding */
                border: 1px solid transparent; /* reserve space for selection border */
                border-radius: 3px;
            }
            QMenu::item:selected { background-color: #d8e0e8; } /* Subtle selection */
            QMenu::separator { height: 1px; background: #d0d0d0; margin: 5px 5px; }
            QToolTip {
                color: #333;
                background-color: #ffffea; /* Creamy yellow */
                border: 1px solid #ccc;
                padding: 4px 6px;
                border-radius: 3px;
                opacity: 240;
            }
            QSplitter::handle { background-color: #c8c8c8; }
            QSplitter::handle:hover { background-color: #b8b8b8; }
            QSplitter::handle:pressed { background-color: #a8a8a8; }
        """)


        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6) # Slightly thicker handle

        default_icon_size = QSize(26, 26)
        get_icon = lambda name: QIcon(get_icon_path(name))

        # Pass main window settings to widgets if needed (e.g., for auto-pause)
        self.video_player = VideoPlayer(self, get_icon_path, default_icon_size)
        self.text_editor = TextEditor(
            self.video_player.media_player,
            get_icon_path,
            default_icon_size,
            # Pass initial auto-pause setting
            self.settings.value("autoPause", True, type=bool)
        )

        self.text_editor.jump_to_time_signal.connect(self.video_player.set_time_ms)

        splitter.addWidget(self.video_player)
        splitter.addWidget(self.text_editor)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter_state = self.settings.value("splitterState")
        if splitter_state:
            splitter.restoreState(splitter_state)

        central_widget = QWidget()
        # Add slight margin around the central widget's layout
        central_layout = QVBoxLayout(central_widget)
        central_layout.addWidget(splitter)
        central_layout.setContentsMargins(5, 5, 5, 5) # Add margins
        self.setCentralWidget(central_widget)

        self.setup_menu(get_icon)
        self.setup_shortcuts()
        self.load_settings()


    def setup_menu(self, get_icon):
        menu_bar = self.menuBar()
        # menu_icon_size = QSize(20, 20) # Not setting size, let Qt handle menu icons

        # --- File Menu ---
        file_menu = menu_bar.addMenu("&File")
        load_video_action = QAction(get_icon("load_menu.png"), "Load Video...", self)
        load_video_action.triggered.connect(self.video_player.load_video)
        file_menu.addAction(load_video_action)

        load_transcript_action = QAction(get_icon("load_menu.png"), "Load Transcript...", self)
        load_transcript_action.triggered.connect(self.text_editor.load_transcript_file)
        file_menu.addAction(load_transcript_action)

        # Save action - Shortcut defined here ONLY
        save_action = QAction("Save Transcript", self)
        save_action.setShortcut(QKeySequence.Save) # Standard Ctrl+S
        save_action.triggered.connect(self.text_editor.save_transcript)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save Transcript As...", self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(self.text_editor.save_transcript_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        clear_text_action = QAction(get_icon("clear_menu.png"), "Clear Text", self)
        clear_text_action.triggered.connect(self.clear_text_editor_confirmed)
        file_menu.addAction(clear_text_action)

        file_menu.addSeparator()

        exit_action = QAction(get_icon("exit_menu.png"), "Exit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # --- View Menu ---
        view_menu = menu_bar.addMenu("&View")
        self.word_wrap_action = QAction("Word Wrap", self, checkable=True)
        # Load setting state before connecting trigger
        self.word_wrap_action.setChecked(self.settings.value("wordWrap", False, type=bool))
        self.word_wrap_action.triggered.connect(self.text_editor.toggle_word_wrap)
        view_menu.addAction(self.word_wrap_action)
        # Initialize state in editor
        self.text_editor.toggle_word_wrap(self.word_wrap_action.isChecked())

        # --- Playback Menu ---
        playback_menu = menu_bar.addMenu("&Playback")

        # Auto-Pause Toggle
        self.auto_pause_action = QAction("Auto-Pause on Timestamp", self, checkable=True)
        self.auto_pause_action.setChecked(self.settings.value("autoPause", True, type=bool))
        self.auto_pause_action.triggered.connect(self.toggle_auto_pause) # Connect to handler
        playback_menu.addAction(self.auto_pause_action)
        # Initialize state in editor
        self.text_editor.set_auto_pause(self.auto_pause_action.isChecked())

        playback_menu.addSeparator()

        self.loop_action = QAction("Loop Last N Seconds", self)
        self.loop_action.setShortcut(QKeySequence("Ctrl+L"))
        self.loop_action.triggered.connect(self.video_player.toggle_loop)
        playback_menu.addAction(self.loop_action)

        set_loop_interval_action = QAction("Set Loop Interval...", self)
        set_loop_interval_action.triggered.connect(self.set_loop_interval)
        playback_menu.addAction(set_loop_interval_action)

        # --- Help Menu ---
        help_menu = menu_bar.addMenu("&Help")
        shortcuts_action = QAction("Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)

        about_action = QAction("About Annotime", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_shortcuts(self):
        # Global shortcuts - Ctrl+S removed from TextEditor
        QShortcut(QKeySequence(Qt.ALT + Qt.Key_Right), self, activated=self.video_player.seek_forward)
        QShortcut(QKeySequence(Qt.ALT + Qt.Key_Left), self, activated=self.video_player.seek_backward)
        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_Space), self, activated=self.video_player.toggle_play_pause)

    def toggle_auto_pause(self, checked):
        """Updates the auto-pause setting in the editor and saves it."""
        self.text_editor.set_auto_pause(checked)
        self.settings.setValue("autoPause", checked)
        print(f"Auto-pause on timestamp {'enabled' if checked else 'disabled'}.")

    def set_loop_interval(self):
        current_interval_sec = self.video_player.loop_interval_ms / 1000.0
        new_interval_sec, ok = QInputDialog.getDouble(self, "Set Loop Interval",
                                                      "Enter loop interval in seconds:",
                                                      value=current_interval_sec, min=0.1, max=60.0, decimals=1)
        if ok and new_interval_sec > 0:
            new_interval_ms = int(new_interval_sec * 1000)
            self.video_player.set_loop_interval(new_interval_ms)
            self.settings.setValue("loopInterval", new_interval_ms)
            print(f"Loop interval set to {new_interval_sec} seconds.")

    def clear_text_editor_confirmed(self):
         reply = QMessageBox.question(self, 'Confirm Clear',
                                     "Are you sure you want to clear the entire transcript?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
         if reply == QMessageBox.Yes:
            self.text_editor.clear_editor_content() # Use dedicated method in editor
            print("Text editor cleared.")

    def show_shortcuts(self):
        """Displays a message box with keyboard shortcuts."""
        shortcuts = """
        <b>Keyboard Shortcuts:</b>
        <ul>
            <li><b>Ctrl + I:</b> Insert Timestamp (Start/End Pair)</li>
            <li><b>Ctrl + L:</b> Loop Last N Seconds (Toggle)</li>
            <li><b>Ctrl + Space:</b> Play / Pause Video</li>
            <li><b>Alt + Right Arrow:</b> Seek Forward 5 Seconds</li>
            <li><b>Alt + Left Arrow:</b> Seek Backward 5 Seconds</li>
            <li><b>Ctrl + S:</b> Save Transcript</li>
            <li><b>Ctrl + Shift + S:</b> Save Transcript As...</li>
            <li><b>Ctrl + Q / Cmd + Q:</b> Exit Application</li>
            <li><i>Mouse Click on Timestamp:</i> Seek Video to Timestamp</li>
        </ul>
        <i>Note: Loop interval and Auto-Pause are configurable via menus.</i>
        """
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)

    def show_about(self):
        """Displays the About dialog."""
        QMessageBox.about(self, "About Annotime Tool",
                          f"""
                          <b>Annotime - Speech Annotation Tool</b>
                          <p>Version: {self.APP_VERSION}</p>
                          <p>A tool for streamilining Annotation for Speech & Audio Dataset.</p>
                          <p> © Vibhasa (विभाषा) @ IIT Mandi</p>
                          """) # Replace YourCompany if desired


    def load_settings(self):
        """Load previous session state."""
        # Window geometry/state
        self.restoreGeometry(self.settings.value("geometry", self.saveGeometry()))
        self.restoreState(self.settings.value("windowState", self.saveState()))

        # Other settings
        loop_interval = self.settings.value("loopInterval", 2000, type=int)
        auto_pause = self.settings.value("autoPause", True, type=bool)
        word_wrap = self.settings.value("wordWrap", False, type=bool)

        # Apply settings
        self.video_player.set_loop_interval(loop_interval)
        self.auto_pause_action.setChecked(auto_pause) # Update menu item state
        self.text_editor.set_auto_pause(auto_pause)   # Update editor state
        self.word_wrap_action.setChecked(word_wrap)
        self.text_editor.toggle_word_wrap(word_wrap)

        # Load files and position (check existence)
        text_path = self.settings.value("lastTextPath", None)
        if text_path and os.path.exists(text_path):
            try:
                self.text_editor.load_transcript_content(text_path)
            except Exception as e:
                 QMessageBox.warning(self, "Error Loading Transcript", f"Could not load last transcript:\n{text_path}\n\nError: {e}")
                 self.settings.remove("lastTextPath")
        elif text_path: # Path saved but file missing
            self.settings.remove("lastTextPath")

        video_path = self.settings.value("lastVideoPath", None)
        if video_path and os.path.exists(video_path):
            try:
                last_position = self.settings.value("lastPosition", 0, type=int)
                print(f"Attempting to load last video: {video_path} at position {last_position}")
                self.video_player.load_video_internal(video_path, initial_position=last_position)
            except Exception as e:
                QMessageBox.warning(self, "Error Loading Video", f"Could not load last video:\n{video_path}\n\nError: {e}")
                self.settings.remove("lastVideoPath")
                self.settings.remove("lastPosition") # Also clear position if video load fails
        elif video_path: # Path saved but file missing
             self.settings.remove("lastVideoPath")
             self.settings.remove("lastPosition")


    def save_settings(self):
        """Save current session state."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        splitter = self.findChild(QSplitter)
        if splitter:
             self.settings.setValue("splitterState", splitter.saveState())

        # Video state
        if self.video_player.current_video_path and os.path.exists(self.video_player.current_video_path):
             self.settings.setValue("lastVideoPath", self.video_player.current_video_path)
             current_pos = self.video_player.get_current_time_ms()
             self.settings.setValue("lastPosition", current_pos if current_pos >= 0 else 0)
        else:
             self.settings.remove("lastVideoPath")
             self.settings.remove("lastPosition")

        # Text state (save path even if modified, user prompted on close)
        if self.text_editor.current_file_path:
             self.settings.setValue("lastTextPath", self.text_editor.current_file_path)
        else:
             self.settings.remove("lastTextPath")

        # Other settings
        self.settings.setValue("loopInterval", self.video_player.loop_interval_ms)
        self.settings.setValue("autoPause", self.auto_pause_action.isChecked())
        self.settings.setValue("wordWrap", self.word_wrap_action.isChecked())

        self.settings.sync()
        print("Settings saved.")

    def closeEvent(self, event):
        """Handle window close event, prompt for unsaved changes."""
        proceed_to_close = True # Assume we can close initially
        if self.text_editor.text_edit.document().isModified():
             reply = QMessageBox.question(self, 'Confirm Exit',
                                          "The transcript has unsaved changes.\nDo you want to save before exiting?",
                                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                          QMessageBox.Cancel)
             if reply == QMessageBox.Save:
                 if not self.text_editor.save_transcript():
                     proceed_to_close = False # Don't close if save failed
             elif reply == QMessageBox.Cancel:
                  proceed_to_close = False
             # If Discard, proceed_to_close remains True

        if proceed_to_close:
            self.save_settings()
            self.video_player.stop_video()
            self.text_editor.stop_auto_save()
            print("Application closing.")
            # Optional: Clean up VLC more explicitly if needed
            # self.video_player.release_player()
            event.accept()
        else:
            event.ignore() # Prevent closing


if __name__ == "__main__":
    # Enable high DPI scaling for better visuals on modern displays
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setOrganizationName("YourCompany") # Consistent naming
    app.setApplicationName("AnnotimeTool")

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
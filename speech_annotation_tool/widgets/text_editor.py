import vlc
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QFileDialog, QMessageBox, QHBoxLayout, QLabel
from PyQt5.QtGui import QTextCursor, QKeySequence, QTextCharFormat, QColor as QtGuiQColor, QFont, QIcon
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtWidgets import QPlainTextEdit, QWidget as QWQWidget
from PyQt5.QtGui import QPainter, QTextFormat
from PyQt5.QtCore import Qt, QRect

import sys
import os
# Determine if running from a bundled EXE or source code
if getattr(sys, 'frozen', False):  # If the script is running as a bundled exe
    app_path = sys._MEIPASS  # Temporary folder where resources are extracted
else:
    app_path = os.path.dirname(__file__)  # If running from source code


class LineNumberArea(QWQWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.text_edit = editor
        self.setFixedWidth(self.text_edit.line_number_area_width())

    def sizeHint(self):
        return QSize(self.text_edit.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.text_edit.paint_line_numbers(event)


class LineNumberTextEdit(QPlainTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.line_number_area = LineNumberArea(self)

        # Update line numbers on text changes and cursor movements
        self.textChanged.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.update_line_number_area)

        # Initialize margins
        self.update_margins()

    def update_line_number_area(self):
        """ Update the line number area to reflect text changes or cursor movements. """
        self.line_number_area.update()
        self.update_margins()  # Recalculate margins in case line numbers width changed

    def update_margins(self):
        """ Adjust the text editor's left margin to fit the line numbers. """
        margin_width = self.line_number_area_width() + 10  # 10px padding
        self.setViewportMargins(margin_width, 0, 0, 0)

    def resizeEvent(self, event):
        """ Resize the line number area when the text editor is resized. """
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.line_number_area.setGeometry(QRect(rect.left(), rect.top(), self.line_number_area_width(), rect.height()))

    def line_number_area_width(self):
        """ Calculate the required width for line numbers dynamically. """
        digits = max(2, len(str(self.blockCount())))  # Ensure at least 2 digits width
        space = 15 + self.fontMetrics().horizontalAdvance('9') * digits  # Slightly more space for clarity
        return space

    def paint_line_numbers(self, event):
        """ Paint the line numbers on the left sidebar. """
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QtGuiQColor(240, 240, 240))  # Slightly lighter gray background

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(Qt.black)
                painter.setFont(self.font())  # Use the same font as the text edit
                painter.drawText(0, top, self.line_number_area.width() - 5, self.fontMetrics().height(),
                                        Qt.AlignRight | Qt.AlignVCenter, number)  # Center text vertically

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1


class TextEditor(QWidget):
    def __init__(self, media_player: vlc.MediaPlayer):
        super().__init__()

        self.media_player = media_player
        self.last_timestamp_inserted = False  # Track if start timestamp is inserted
        self.current_file_path = None  # Track the saved file path
        self.font_size = 12  # Default font size

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # Add margins around the widget
        layout.setSpacing(8)  # Add spacing between widgets


        # --- Styling ---
        self.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                padding: 3px 5px;
                min-width: 25px; /* Minimum width for buttons */
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-color: #a0a0a0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
                border-color: #808080;
            }
            QPushButton#saveButton { /* Style for Save Button, using object name */
                background-color: #4CAF50; /* Green */
                color: white;
                border: none;
                padding: 8px 15px; /* Increased padding for larger button */
                min-width: 100px; /* Increased min-width */
                font-size: 14pt; /* Slightly larger font size for button text */
            }
            QPushButton#saveButton:hover {
                background-color: #45a049;
            }
            QPushButton#saveButton:pressed {
                background-color: #3d8b40;
            }
            LineNumberTextEdit {
                border: 1px solid #c0c0c0;
                background-color: #ffffff; /* White text area */
                selection-background-color: #a8d1ff; /* Light blue selection */
                font-family: Arial; /* Example font - can be changed */
                font-size: 12pt;
            }
            QLabel#saveStatusLabel {
                color: darkgreen;
                font-style: italic;
                margin-top: 5px;
                margin-bottom: 5px;
            }
        """)


        # UI Elements Initialization
        self.text_edit = LineNumberTextEdit()
        self.text_edit.setFont(QFont("Arial", self.font_size))

        # Save Status Label - for non-popup confirmation
        self.save_status_label = QLabel("")  # Initially empty
        self.save_status_label.setObjectName("saveStatusLabel") # for styling
        self.save_status_timer = QTimer(self) # Timer to clear status label
        self.save_status_timer.timeout.connect(self.clear_save_status)


        # --- Icon Size Configuration (TextEditor) ---
        base_icon_size_text_editor = 18  # Further reduced icon size for text editor buttons
        max_icon_size_text_editor = 22  # Further reduced max icon size for text editor buttons

        def get_relative_icon_size_text_editor(button):
            """ Calculate relative icon size for text editor buttons """
            button_height = button.sizeHint().height()
            icon_size = min(int(button_height * 0.8), max_icon_size_text_editor)  # Slightly smaller relative size
            return QSize(icon_size, icon_size)


        self.increase_font_button = QPushButton(self)  # Icon-only button - **RELATIVE ICON SIZE**
        icon_path_zoom_in = os.path.join(app_path, 'icons', 'zoom_in.png')  # Example icon file

        self.increase_font_button.setIcon(QIcon(icon_path_zoom_in))
        self.increase_font_button.setIconSize(get_relative_icon_size_text_editor(self.increase_font_button))  # **RELATIVE ICON SIZE**
        self.increase_font_button.clicked.connect(self.increase_font_size)
        self.increase_font_button.setToolTip("Increase Font Size")

        self.decrease_font_button = QPushButton(self)  # Icon-only button - **RELATIVE ICON SIZE**
        icon_path_zoom_out = os.path.join(app_path, 'icons', 'zoom_out.png')
        self.decrease_font_button.setIcon(QIcon(icon_path_zoom_out))
        self.decrease_font_button.setIconSize(get_relative_icon_size_text_editor(self.decrease_font_button))  # **RELATIVE ICON SIZE**
        self.decrease_font_button.clicked.connect(self.decrease_font_size)
        self.decrease_font_button.setToolTip("Decrease Font Size")

        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("saveButton")  # setObjectName for styling in CSS
        self.save_button.clicked.connect(self.save_transcript)
        self.save_button.setToolTip("Save Transcript (Ctrl+S)")
        self.save_button.setMinimumWidth(80)  # Minimum width for save button


        # Layout setup
        font_button_layout = QHBoxLayout()  # Layout for font buttons
        font_button_layout.setSpacing(5)  # Spacing for font buttons

        font_button_layout.addWidget(self.decrease_font_button)  # Decrease button first for visual order -/+
        font_button_layout.addWidget(self.increase_font_button)


        layout.addLayout(font_button_layout)  # Add font buttons layout
        layout.addWidget(self.text_edit)
        layout.addWidget(self.save_status_label) # Add save status label below text editor
        layout.addWidget(self.save_button, alignment=Qt.AlignRight)  # Align save button to the right


        self.setLayout(layout)


        # Connect signals and slots (font and save buttons already connected in init)

        # Timestamp Shortcut (Ctrl+I) - No button, kept as shortcut
        self.timestamp_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        self.timestamp_shortcut.activated.connect(self.insert_timestamp)

        # Save Shortcut (Ctrl+S) - Already connected to save_button
        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self) # Added Ctrl+S Shortcut
        self.save_shortcut.activated.connect(self.save_transcript)



    def insert_timestamp(self):
        """ Insert timestamps in HH:MM:SS.MS format with red color. """
        if not self.media_player or not self.media_player.get_media():
            QMessageBox.warning(self, "Warning", "No video loaded. Load a video first to insert timestamps.")
            return

        current_time_ms = self.media_player.get_time()
        if current_time_ms == -1:
            print("Error: Unable to fetch current video time.")
            return

        timestamp_str = self.format_time(current_time_ms)

        cursor = self.text_edit.textCursor()
        timestamp_format = QTextCharFormat()
        timestamp_format.setForeground(QtGuiQColor(255, 0, 0))  # Red color

        if not self.last_timestamp_inserted:  # Inserting Start Timestamp
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.setCharFormat(timestamp_format)
            cursor.insertText(f"[{timestamp_str}]-")
            self.last_timestamp_inserted = True
            self.last_cursor_position = cursor.position()
        else:  # Inserting End Timestamp
            cursor.setPosition(self.last_cursor_position)
            cursor.setCharFormat(timestamp_format)
            cursor.insertText(f"[{timestamp_str}] ")
            self.last_timestamp_inserted = False
            cursor.movePosition(QTextCursor.NextBlock)
            self.last_cursor_position = None


        # Reset format after timestamp
        default_format = QTextCharFormat()
        cursor.setCharFormat(default_format)
        self.text_edit.setTextCursor(cursor)


    def format_time(self, milliseconds):
        """ Convert milliseconds to HH:MM:SS.MS format. """
        seconds = milliseconds // 1000
        minutes = seconds // 60
        hours = minutes // 60
        return f"{hours:02}:{minutes % 60:02}:{seconds % 60:02}.{milliseconds % 1000:03}"


    def increase_font_size(self):
        """ Increase font size. """
        # self.font_size += 1
        # self.text_edit.setFont(QFont("Arial", self.font_size))
        return

    def decrease_font_size(self):
        """ Decrease font size, with a minimum limit. """
        # if self.font_size > 8:
        #  self.font_size -= 1
        #  self.text_edit.setFont(QFont("Arial", self.font_size))
        return


    def save_transcript(self):
        """ Save the transcript to the current file path or prompt for a new one, with non-popup confirmation. """
        if not self.current_file_path:
            self.current_file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Transcript", "", "Text Files (*.txt)"
            )
            if not self.current_file_path:
                return  # User cancelled save dialog

        try:
            with open(self.current_file_path, "w", encoding="utf-8") as file: # "w" mode for overwrite
                file.write(self.text_edit.toPlainText())
            print(f"Transcript saved to: {self.current_file_path}") # Console confirmation

            # Non-popup save confirmation using label and timer
            self.save_status_label.setText(f"Transcript saved to: {os.path.basename(self.current_file_path)}")
            self.save_status_timer.start(3000) # Clear message after 3 seconds


        except Exception as e:
            error_message = f"Error saving transcript:\n{e}"
            QMessageBox.critical(self, "Error Saving Transcript", error_message) # Error Dialog
            print(f"Error saving transcript: {e}") # Console error log

    def clear_save_status(self):
        """ Clear the save status label. """
        self.save_status_label.setText("") # Clear the status message
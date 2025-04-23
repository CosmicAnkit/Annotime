import vlc
import re
import os
# Added QHBoxLayout explicitly if needed, QSizePolicy
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QFileDialog,
                             QMessageBox, QHBoxLayout, QLabel, QPlainTextEdit,
                             QSizePolicy, QTextEdit, QShortcut, QFrame) # Added QFrame
from PyQt5.QtGui import (QTextCursor, QKeySequence, QTextCharFormat, QColor as QtGuiQColor,
                         QFont, QIcon, QPainter, QTextFormat)
from PyQt5.QtCore import Qt, QTimer, QSize, QRect, pyqtSignal, QEvent


try:
    from .video_player import format_time
except ImportError as e:
     print(f"CRITICAL: Could not import format_time from .video_player - {e}")
     def format_time(ms): return str(ms)


# --- Line Number Area Class (No changes) ---
class LineNumberArea(QWidget):
    # ... (no changes) ...
    def __init__(self, editor):
        super().__init__(editor)
        self.text_edit = editor
        # Set initial width based on parent's calculation
        self.setFixedWidth(self.text_edit.line_number_area_width())

    def sizeHint(self):
        # Return width calculated by editor
        return QSize(self.text_edit.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.text_edit.paint_line_numbers(event)


# --- LineNumberTextEdit Class (No changes) ---
class LineNumberTextEdit(QPlainTextEdit):
    # ... (no changes) ...
    seekRequest = pyqtSignal(int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        # Call initializers AFTER setting up connections and line number area
        self.update_line_number_area_width()
        self.highlight_current_line()
        self.timestamp_regex = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\]')

    def line_number_area_width(self):
        digits = max(2, len(str(self.blockCount() or 1))) # Ensure at least 1 for calculation
        # Add a bit more padding for clarity
        space = 15 + self.fontMetrics().horizontalAdvance('9') * digits
        return int(space) # Return integer

    def update_line_number_area_width(self):
        margin_width = self.line_number_area_width()
        self.setViewportMargins(margin_width, 0, 0, 0)
        # Update geometry required if width changes after init
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), margin_width, cr.height()))


    def update_line_number_area(self, rect=None, dy=None):
         if dy:
             self.line_number_area.scroll(0, dy)
         else:
             # Use viewport height for full repaint on non-scroll updates
             update_rect = QRect(0, rect.y() if rect else 0, self.line_number_area.width(), rect.height() if rect else self.viewport().height())
             self.line_number_area.update(update_rect)


    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        # Ensure width is recalculated on resize
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def paint_line_numbers(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QtGuiQColor(238, 238, 238)) # Slightly lighter gray
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        # Ensure contentOffset is handled correctly
        offset_y = int(self.contentOffset().y())
        top = int(self.blockBoundingGeometry(block).translated(0, offset_y).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        font = self.font()
        painter.setFont(font)
        painter.setPen(Qt.darkGray)
        font_height = self.fontMetrics().height()
        area_width = self.line_number_area.width()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.drawText(0, top, area_width - 7, font_height, # More padding from right edge
                                 Qt.AlignRight | Qt.AlignVCenter, number) # AlignVCenter added
            block = block.next()
            # Check if block became invalid
            if not block.isValid(): break
            # Important: Recalculate geometry based on the *new* block
            top = int(self.blockBoundingGeometry(block).translated(0, offset_y).top())
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            # Use a slightly less intrusive highlight color
            line_color = QtGuiQColor("#e8f0fe") # Light blueish-gray
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            block = cursor.block()
            if block.isValid():
                line_text = block.text()
                matches = list(self.timestamp_regex.finditer(line_text))
                if matches:
                    click_pos_in_line = cursor.positionInBlock()
                    first_match = matches[0] # Always seek to the first timestamp in the line
                    start_char, end_char = first_match.span()
                    # Allow clicking anywhere on the line containing the timestamp?
                    # Or just within the timestamp itself? Let's try within TS only.
                    if start_char <= click_pos_in_line < end_char:
                         timestamp_str = first_match.group(1)
                         try:
                             time_ms = self.parse_time(timestamp_str)
                             print(f"Timestamp clicked: {timestamp_str} -> {time_ms} ms")
                             self.seekRequest.emit(time_ms)
                             event.accept()
                             return
                         except ValueError as e:
                             print(f"Error parsing timestamp '{timestamp_str}': {e}")

        super().mousePressEvent(event)


    def parse_time(self, time_str):
        try:
            parts = time_str.split(':')
            sec_ms_parts = parts[2].split('.')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(sec_ms_parts[0])
            # Handle milliseconds with varying length (e.g., .1, .12, .123)
            ms_str = sec_ms_parts[1]
            milliseconds = int(ms_str.ljust(3, '0')[:3]) # Pad/truncate to 3 digits

            total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds
            return total_ms
        except (IndexError, ValueError) as e:
             raise ValueError(f"Invalid time format '{time_str}': {e}")


# --- Main Text Editor Widget ---
class TextEditor(QWidget):
    jump_to_time_signal = pyqtSignal(int)

    # Added auto_pause_enabled parameter
    def __init__(self, media_player: vlc.MediaPlayer, icon_path_func,
                 default_icon_size=QSize(24,24), auto_pause_enabled=True):
        super().__init__()

        if not media_player:
             QMessageBox.critical(self, "Initialization Error", "Media player instance is missing.")
             self.media_player = None
        else:
             self.media_player = media_player

        self.get_icon_path = icon_path_func
        self.default_icon_size = default_icon_size
        self.auto_pause_enabled = auto_pause_enabled # Store setting

        self.last_timestamp_inserted = False
        self.last_cursor_position = None

        self.current_file_path = None
        self.font_size = 12
        self.default_font = QFont("Arial", self.font_size)

        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.setInterval(30 * 1000) # 30 seconds
        self.auto_save_timer.timeout.connect(self.auto_save)

        self.save_status_timer = QTimer(self)
        self.save_status_timer.setSingleShot(True)
        self.save_status_timer.timeout.connect(self.clear_save_status)

        self.init_ui()
        self.setup_shortcuts()
        if hasattr(self, 'text_edit'):
            self.text_edit.document().modificationChanged.connect(self.handle_modification_change)


    def init_ui(self):
        main_layout = QVBoxLayout(self) # Use a different name from internal layout var
        main_layout.setContentsMargins(10, 10, 10, 10) # Add margins
        main_layout.setSpacing(8) # Spacing between elements

        # --- Top Control Bar (Font Size - Centered) ---
        control_bar_frame = QFrame() # Put controls in a frame for better layout control
        control_bar_layout = QHBoxLayout(control_bar_frame)
        control_bar_layout.setContentsMargins(0, 0, 0, 0) # No margins within frame itself
        control_bar_layout.setSpacing(8) # Spacing between buttons

        # Add stretch before and after to center the buttons
        control_bar_layout.addStretch(1)

        self.decrease_font_button = QPushButton(self)
        self.decrease_font_button.setIcon(QIcon(self.get_icon_path("zoom_out.png")))
        self.decrease_font_button.setIconSize(self.default_icon_size)
        self.decrease_font_button.setToolTip("Decrease Font Size")
        self.decrease_font_button.clicked.connect(self.decrease_font_size)
        control_bar_layout.addWidget(self.decrease_font_button)

        self.increase_font_button = QPushButton(self)
        self.increase_font_button.setIcon(QIcon(self.get_icon_path("zoom_in.png")))
        self.increase_font_button.setIconSize(self.default_icon_size)
        self.increase_font_button.setToolTip("Increase Font Size")
        self.increase_font_button.clicked.connect(self.increase_font_size)
        control_bar_layout.addWidget(self.increase_font_button)

        control_bar_layout.addStretch(1)

        main_layout.addWidget(control_bar_frame) # Add the frame to the main layout


        # --- Styling (Adjust button padding/min-width, Save Button) ---
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #e8e8e8; border: 1px solid #b8b8b8;
                border-radius: 4px; padding: 5px 8px; min-width: 40px;
            }}
            QPushButton:hover {{ background-color: #d8d8d8; border-color: #a8a8a8; }}
            QPushButton:pressed {{ background-color: #c8c8c8; border-color: #989898; }}
            /* Specific style for Save Button */
            QPushButton#saveButton {{
                background-color: #5cb85c; /* Bootstrap success green */
                border-color: #4cae4c;
                color: white;
                padding: 8px 16px; /* More padding */
                min-width: 90px; /* Wider */
                font-size: 11pt; /* Slightly larger font */
                font-weight: bold;
            }}
            QPushButton#saveButton:hover {{ background-color: #4cae4c; border-color: #4cae4c; }}
            QPushButton#saveButton:pressed {{ background-color: #449d44; border-color: #449d44; }}
            LineNumberTextEdit {{
                border: 1px solid #c0c0c0;
                background-color: #ffffff;
                selection-background-color: #d8e8ff; /* Lighter selection blue */
                font-family: Arial, sans-serif; /* Add fallback */
                /* Font size set directly */
            }}
            QLabel#saveStatusLabel {{
                color: #3c763d; /* Darker green */
                font-style: italic; margin-top: 5px; margin-bottom: 0px;
                font-size: 9pt;
                padding-left: 5px; /* Add some left padding */
            }}
            QFrame {{ /* Style for control bar frame if needed */
                 border: none; /* Remove border if frame added */
            }}
        """)


        # --- Text Edit Area ---
        self.text_edit = LineNumberTextEdit()
        self.text_edit.setFont(self.default_font)
        self.text_edit.seekRequest.connect(self.jump_to_time_signal.emit)
        main_layout.addWidget(self.text_edit, stretch=1) # Make text area expand

        # --- Bottom Bar (Save Status and Button) ---
        bottom_bar_layout = QHBoxLayout()
        bottom_bar_layout.setContentsMargins(0, 5, 0, 0) # Top margin
        self.save_status_label = QLabel("")
        self.save_status_label.setObjectName("saveStatusLabel")
        self.save_status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bottom_bar_layout.addWidget(self.save_status_label)

        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("saveButton") # For styling
        self.save_button.setIconSize(QSize(20, 20)) # Optional icon size
        self.save_button.setToolTip("Save Transcript (Ctrl+S)")
        self.save_button.clicked.connect(self.save_transcript)
        bottom_bar_layout.addWidget(self.save_button) # Add to right

        main_layout.addLayout(bottom_bar_layout)
        self.setLayout(main_layout)


    def setup_shortcuts(self):
        # Timestamp shortcut
        self.timestamp_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        self.timestamp_shortcut.activated.connect(self.insert_timestamp_action)
        # REMOVED redundant Ctrl+S shortcut - handled by QAction in main window
        # self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        # self.save_shortcut.activated.connect(self.save_transcript)

    def set_auto_pause(self, enabled):
        """Public method to enable/disable auto-pause."""
        self.auto_pause_enabled = enabled

    def insert_timestamp_action(self):
         """Handles the Ctrl+I action: auto-pauses (if enabled) and calls insertion logic."""
         if not self.media_player:
             QMessageBox.warning(self, "Warning", "Media player not available.")
             return

         # --- Auto-Pause Check ---
         if self.auto_pause_enabled and self.media_player.is_playing():
             self.media_player.pause()
             print("Video paused on timestamp insertion (Auto-Pause enabled).")
             # TODO: Signal video player widget to update its play/pause button icon?

         # Call the paired timestamp insertion logic
         self.insert_timestamp_paired()


    def insert_timestamp_paired(self):
        """ Inserts timestamps in [START]-[END] format at start of line, using two Ctrl+I presses."""
        if not self.media_player or not self.media_player.get_media():
            QMessageBox.warning(self, "Warning", "No video loaded.")
            return

        current_time_ms = self.media_player.get_time()
        if current_time_ms < 0: # Check for invalid time
            print("Error: Unable to fetch valid video time.")
            return

        try:
            timestamp_str = format_time(current_time_ms)
        except Exception as e:
             print(f"Error formatting time {current_time_ms}: {e}")
             return

        cursor = self.text_edit.textCursor()
        timestamp_format = QTextCharFormat()
        timestamp_format.setForeground(QtGuiQColor(200, 0, 0)) # Slightly darker red
        timestamp_format.setFontWeight(QFont.Bold)

        if not self.last_timestamp_inserted:  # --- Inserting Start Timestamp ---
            cursor.beginEditBlock() # Group edits for undo
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.insertText(f"[{timestamp_str}]-", timestamp_format)
            self.last_cursor_position = cursor.position()
            self.last_timestamp_inserted = True
            cursor.endEditBlock()
            print(f"Inserted Start TS: {timestamp_str}")

        else:  # --- Inserting End Timestamp ---
            cursor.beginEditBlock()
            if self.last_cursor_position is None:
                 print("Error: Lost position for end timestamp. Inserting at current block start.")
                 cursor.movePosition(QTextCursor.StartOfBlock)
                 # Insert something to indicate it's likely misplaced
                 cursor.insertText(f"<??>[{timestamp_str}] ", timestamp_format)
            else:
                 # Move cursor back to where the start timestamp ended
                 cursor.setPosition(self.last_cursor_position)
                 # Insert end timestamp marker (note the space after)
                 cursor.insertText(f"[{timestamp_str}] ", timestamp_format)
                 print(f"Inserted End TS: {timestamp_str}")

            # Reset state BEFORE moving cursor for next line
            self.last_timestamp_inserted = False
            self.last_cursor_position = None

            # --- Move cursor to end of current line (don't insert new block) ---
            cursor.movePosition(QTextCursor.EndOfLine)
            cursor.endEditBlock()


        # Reset character format for subsequent typing
        base_format = QTextCharFormat()
        # Let it inherit default font/color from the widget
        cursor.setCharFormat(base_format)

        self.text_edit.setTextCursor(cursor) # Apply cursor changes
        self.text_edit.ensureCursorVisible() # Scroll if needed
        self.text_edit.document().setModified(True)


    def increase_font_size(self):
        self.font_size += 1
        self.update_font()
        print(f"Font size increased to: {self.font_size}")

    def decrease_font_size(self):
        if self.font_size > 8:
            self.font_size -= 1
            self.update_font()
            print(f"Font size decreased to: {self.font_size}")

    def update_font(self):
         new_font = QFont("Arial", self.font_size)
         self.text_edit.setFont(new_font)
         # Update line number area calculation and repaint
         self.text_edit.update_line_number_area_width()
         self.text_edit.highlight_current_line()
         # Force full repaint of line number area
         self.text_edit.line_number_area.update()

    def toggle_word_wrap(self, enabled):
         mode = QPlainTextEdit.WidgetWidth if enabled else QPlainTextEdit.NoWrap
         self.text_edit.setLineWrapMode(mode)
         print(f"Word wrap {'enabled' if enabled else 'disabled'}.")

    def clear_editor_content(self):
        """Clears text and resets related states."""
        self.text_edit.clear()
        self.current_file_path = None
        self.text_edit.document().setModified(False)
        self.last_timestamp_inserted = False # Reset timestamp state too
        self.last_cursor_position = None
        # Stop auto-save timer if running
        self.handle_modification_change(False)


    # --- Save/Load/Auto-Save Methods (Keep previous versions) ---
    def load_transcript_file(self):
         start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else os.path.expanduser("~")
         file_path, _ = QFileDialog.getOpenFileName(self, "Load Transcript", start_dir, "Text Files (*.txt);;All Files (*)")
         if file_path:
             try:
                 self.load_transcript_content(file_path)
             except Exception as e:
                  QMessageBox.critical(self, "Error Loading Transcript", f"Failed to load file:\n{file_path}\n\nError: {e}")

    def load_transcript_content(self, file_path):
         if not os.path.exists(file_path):
              raise FileNotFoundError(f"Transcript file not found: {file_path}")
         with open(file_path, "r", encoding="utf-8") as file:
             content = file.read()
             # Clear existing content and state before loading
             self.clear_editor_content()
             self.text_edit.setPlainText(content)
             self.current_file_path = file_path
             self.text_edit.document().setModified(False) # Mark as unmodified
             print(f"Transcript loaded from: {file_path}")
             # No need to call handle_modification_change here, done by clear_editor_content


    def save_transcript(self):
        if not self.current_file_path:
            return self.save_transcript_as()
        else:
            return self._save_to_path(self.current_file_path)

    def save_transcript_as(self):
        start_dir = os.path.dirname(self.current_file_path) if self.current_file_path else os.path.expanduser("~")
        new_file_path, _ = QFileDialog.getSaveFileName(self, "Save Transcript As", start_dir, "Text Files (*.txt);;All Files (*)")
        if new_file_path:
            # Ensure .txt extension if not provided
            if not new_file_path.lower().endswith(".txt"):
                 new_file_path += ".txt"
            self.current_file_path = new_file_path
            return self._save_to_path(self.current_file_path)
        return False # User cancelled

    def _save_to_path(self, file_path):
        try:
            content = self.text_edit.toPlainText()
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)
            self.text_edit.document().setModified(False)
            print(f"Transcript saved to: {file_path}")
            self.show_save_status(f"Saved: {os.path.basename(file_path)}")
            # Restart auto-save timer's interval after manual save
            if self.auto_save_timer.isActive():
                self.auto_save_timer.start()
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error Saving Transcript", f"Error saving transcript:\n{file_path}\n\nError: {e}")
            print(f"Error saving transcript: {e}")
            return False

    def auto_save(self):
        # Only save if path exists and modified
        if self.current_file_path and self.text_edit.document().isModified():
            print(f"Auto-saving transcript to: {self.current_file_path}")
            if self._save_to_path(self.current_file_path):
                 # Don't show visual status on auto-save
                 pass
            else:
                 print("Auto-save failed.")
                 self.auto_save_timer.stop() # Stop trying if error


    def handle_modification_change(self, modified):
         if modified and self.current_file_path:
             if not self.auto_save_timer.isActive():
                 print("Starting auto-save timer.")
                 self.auto_save_timer.start()
         elif not modified or not self.current_file_path:
              if self.auto_save_timer.isActive():
                   print("Stopping auto-save timer.")
                   self.auto_save_timer.stop()


    def stop_auto_save(self):
         if self.auto_save_timer.isActive():
             self.auto_save_timer.stop()
             print("Auto-save timer stopped.")

    def show_save_status(self, message):
        self.save_status_label.setText(message)
        # Make status message visible slightly longer
        self.save_status_timer.start(3500) # 3.5 seconds

    def clear_save_status(self):
        self.save_status_label.setText("")
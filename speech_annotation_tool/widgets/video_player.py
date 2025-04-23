import sys
import os
import vlc
from PyQt5.QtWidgets import QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QFileDialog, QSlider, QHBoxLayout, QTextEdit, QMessageBox, QFrame
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QIcon, QPalette, QColor, QKeySequence
from PyQt5.QtWidgets import QShortcut


# Determine if running from a bundled EXE or source code
if getattr(sys, 'frozen', False):  # If the script is running as a bundled exe
    app_path = sys._MEIPASS  # Temporary folder where resources are extracted
else:
    app_path = os.path.dirname(__file__)  # If running from source code


def format_time(milliseconds):
    """ Helper function to format milliseconds to HH:MM:SS.milliseconds """
    seconds = milliseconds // 1000
    minutes = seconds // 60
    hours = minutes // 3600
    return f"{hours:02}:{minutes % 60:02}:{seconds % 60:02}.{milliseconds % 1000:03}"

class VideoPlayer(QWidget):
    def __init__(self, main_window):  # Pass MainWindow instance here
        super().__init__()
        self.main_window = main_window  # Store MainWindow instance

        self.instance = vlc.Instance()
        self.media_player = self.instance.media_player_new()
        self.is_muted = False
        self.text_editor = None  # Will be set from MainWindow
        self.seek_interval = 5000  # Seek interval in milliseconds (5 seconds)

        layout = QVBoxLayout()
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
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: #d0d0d0;
                margin: 2px 0;
                border-radius: 4px;
            }

            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                                stop:0 #b1b1b1, stop:1 #c8c8c8);
                border: 1px solid #a0a0a0;
                width: 16px;
                margin: -6px 0; /* handle is placed by default on the contents rect. -6px shifts it up so that the handle center and groove are aligned vertically. */
                border-radius: 4px;
            }
            QComboBox {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                padding: 3px 5px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left-width: 1px;
                border-left-color: darkgray;
                border-left-style: solid; /* just a single line */
                border-top-right-radius: 3px; /* same radius as the QComboBox */
                border-bottom-right-radius: 3px;
            }
            QComboBox::down-arrow {
                image: url(icons/dropdown_arrow.png); /* Replace with your arrow icon file */
                width: 8px;
                height: 8px;
            }
            QLabel#timeLabel { /* Style for time label, using object name */
                font-size: 10pt;
                color: #555;
                margin-left: 5px;
                margin-right: 5px;
            }
        """)

        # Video Frame
        self.video_widget = QFrame(self)
        self.video_widget.setStyleSheet("background-color: black; border: 1px solid #777;")  # Add border to video frame
        layout.addWidget(self.video_widget, stretch=5)

        # Timeline Layout
        timeline_layout = QHBoxLayout()
        timeline_layout.setSpacing(5)  # Spacing in timeline layout
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.sliderMoved.connect(self.set_position)
        timeline_layout.addWidget(self.timeline_slider)
        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        self.time_label.setObjectName("timeLabel")  # setObjectName for styling in CSS
        timeline_layout.addWidget(self.time_label)
        layout.addLayout(timeline_layout)

        # Controls Layout with Icons
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)  # Spacing in controls layout

        # --- Icon Size Configuration ---
        base_icon_size = 20  # Reduced base icon size
        max_icon_size = 24  # Reduced max icon size

        def get_relative_icon_size(button):
            """ Calculate relative icon size based on button height, capped at max_icon_size """
            button_height = button.sizeHint().height()  # Get button's suggested height
            icon_size = min(int(button_height * 0.8), max_icon_size)  # Slightly smaller relative size
            return QSize(icon_size, icon_size)

        # Load Button - **FIXED ICON LOADING and RELATIVE ICON SIZE**
        self.load_button = QPushButton(self)
        icon_path_load = os.path.join(app_path, 'icons', 'load.png')  # Example icon file
        load_icon = QIcon(icon_path_load)  # Create QIcon object explicitly
        if not load_icon.isNull():  # Check if icon loaded successfully
            self.load_button.setIcon(load_icon)
            self.load_button.setIconSize(get_relative_icon_size(self.load_button))  # **RELATIVE ICON SIZE**
        else:
            print("Warning: Icon 'icons/load.png' not found!")  # Debug message if icon not found
            self.load_button.setText("Load Video")  # Fallback text if icon fails to load
        self.load_button.clicked.connect(self.load_video)
        self.load_button.setToolTip("Load Video File")
        controls_layout.addWidget(self.load_button)

        # Play/Pause Button - **RELATIVE ICON SIZE**
        self.play_pause_button = QPushButton(self)
        icon_path_play = os.path.join(app_path, 'icons', 'play.png')
        icon_path_pause = os.path.join(app_path, 'icons', 'pause.png')
        self.play_icon = QIcon(icon_path_play)
        self.pause_icon = QIcon(icon_path_pause)
        self.play_pause_button.setIcon(self.play_icon)
        self.play_pause_button.setIconSize(get_relative_icon_size(self.play_pause_button))  # **RELATIVE ICON SIZE**
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.play_pause_button.setToolTip("Play / Pause")
        controls_layout.addWidget(self.play_pause_button)

        # Stop Button - **RELATIVE ICON SIZE**
        self.stop_button = QPushButton(self)
        icon_path_stop = os.path.join(app_path, 'icons', 'stop.png')

        self.stop_button.setIcon(QIcon(icon_path_stop))
        self.stop_button.setIconSize(get_relative_icon_size(self.stop_button))  # **RELATIVE ICON SIZE**
        self.stop_button.clicked.connect(self.stop_video)
        self.stop_button.setToolTip("Stop")
        controls_layout.addWidget(self.stop_button)

        # Speed Combo
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1.0x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentIndex(1)
        self.speed_combo.currentIndexChanged.connect(self.change_speed)
        self.speed_combo.setToolTip("Playback Speed")
        controls_layout.addWidget(self.speed_combo)

        # Volume Controls - Volume Up/Down Buttons Added and **SHORTENED SLIDER, RELATIVE ICON SIZES**
        volume_layout = QHBoxLayout()  # Layout for volume controls
        volume_layout.setSpacing(3)  # Tighter spacing for volume controls

        self.volume_down_button = QPushButton(self)  # Volume Down Button - **RELATIVE ICON SIZE**
        icon_path_volume_down = os.path.join(app_path, 'icons', 'volume_down.png')

        volume_down_icon = QIcon(icon_path_volume_down)
        if not volume_down_icon.isNull():
            self.volume_down_button.setIcon(volume_down_icon)
            self.volume_down_button.setIconSize(get_relative_icon_size(self.volume_down_button))  # **RELATIVE ICON SIZE**
        else:
            self.volume_down_button.setText("Vol-")  # Fallback text
        self.volume_down_button.clicked.connect(self.decrease_volume_button)  # New method
        self.volume_down_button.setToolTip("Decrease Volume")
        volume_layout.addWidget(self.volume_down_button)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self.change_volume)
        self.volume_slider.setToolTip("Volume")
        self.volume_slider.setMaximumWidth(80)  # **Further SHORTEN VOLUME SLIDER**
        volume_layout.addWidget(self.volume_slider)

        self.volume_up_button = QPushButton(self)  # Volume Up Button - **RELATIVE ICON SIZE**
        icon_path_volume_up = os.path.join(app_path, 'icons', 'volume_up.png')
        volume_up_icon = QIcon(icon_path_volume_up)
        if not volume_up_icon.isNull():
            self.volume_up_button.setIcon(volume_up_icon)
            self.volume_up_button.setIconSize(get_relative_icon_size(self.volume_up_button))  # **RELATIVE ICON SIZE**
        else:
            self.volume_up_button.setText("Vol+")  # Fallback text
        self.volume_up_button.clicked.connect(self.increase_volume_button)  # New method
        self.volume_up_button.setToolTip("Increase Volume")
        volume_layout.addWidget(self.volume_up_button)

        self.mute_button = QPushButton(self)  # Mute Button - **RELATIVE ICON SIZE - CORRECTED ICON LOGIC**
        icon_path_mute = os.path.join(app_path, 'icons', 'mute.png')
        icon_path_unmute = os.path.join(app_path, 'icons', 'unmute.png')
        self.mute_icon = QIcon(icon_path_mute)
        self.unmute_icon = QIcon(icon_path_unmute)
        self.mute_button.setIcon(self.unmute_icon)  # Start as unmute
        self.mute_button.setIconSize(get_relative_icon_size(self.mute_button))  # **RELATIVE ICON SIZE**
        self.mute_button.clicked.connect(self.toggle_mute)
        self.mute_button.setToolTip("Mute / Unmute")
        volume_layout.addWidget(self.mute_button)

        controls_layout.addLayout(volume_layout)  # Add volume control layout to main controls

        layout.addLayout(controls_layout)

        self.setLayout(layout)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)
        self.volume_slider.setValue(50)  # Initial volume level
        self.change_volume(50)  # Set initial volume

    def focusInEvent(self, event):
        print(f"VideoPlayer Focused In") # Focus Debugging
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        print(f"VideoPlayer Focused Out") # Focus Debugging
        super().focusOutEvent(event)

    def set_text_editor(self, text_editor):
        self.text_editor = text_editor

    def insert_timestamp(self, type="MARK"):
        if not self.media_player.get_media():
            QMessageBox.warning(self, "Warning", "No video loaded. Load a video first.")
            return
        current_time = self.media_player.get_time()
        formatted_time_str = format_time(current_time)
        timestamp_text = f"[{type}: {formatted_time_str}]"
        if self.text_editor:
            self.text_editor.insertPlainText(timestamp_text + "\n")
        else:
            print("Error: Text editor not set for VideoPlayer.")
            QMessageBox.critical(self, "Error", "Text editor is not properly set in VideoPlayer.")

    def load_video(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Video", "", "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv)")
        if file_path:
            try:
                media = self.instance.media_new(file_path)
                self.media_player.set_media(media)

                if sys.platform.startswith("linux"):
                    self.media_player.set_xwindow(int(self.video_widget.winId()))
                elif sys.platform == "win32":
                    self.media_player.set_hwnd(int(self.video_widget.winId()))
                elif sys.platform == "darwin":
                    self.media_player.set_nsobject(int(self.video_widget.winId()))

                self.play_video()
            except Exception as e:
                error_message = f"Could not load video file:\n{file_path}\n\nError details: {e}\n\nPossible reasons:\n- Unsupported video codec.\n- Corrupted video file.\n- Missing VLC codecs or a broken VLC installation.\n\nPlease check your VLC installation and try a different video file."
                QMessageBox.critical(self, "Error Loading Video", error_message)
                print(f"Error loading video: {e}")

    def play_video(self):
        if not self.media_player.get_media():
            QMessageBox.warning(self, "Warning", "No video loaded. Please load a video first.")
            return
        if self.media_player.get_state() in [vlc.State.Ended, vlc.State.NothingSpecial, vlc.State.Error]:
            self.media_player.set_position(0)
        self.media_player.play()
        self.timer.start()
        self.play_pause_button.setIcon(self.pause_icon)  # Change icon to pause
        self.play_pause_button.setToolTip("Pause")

    def pause_video(self):
        if self.media_player.is_playing():
            self.media_player.pause()
            self.timer.stop()
            self.play_pause_button.setIcon(self.play_icon)  # Change icon to play
            self.play_pause_button.setToolTip("Play")

    def toggle_play_pause(self):
        if self.media_player.is_playing():
            self.pause_video()
        else:
            self.play_video()

    def stop_video(self):
        self.media_player.stop()
        self.timeline_slider.setValue(0)
        self.time_label.setText("00:00:00.000 / 00:00:00.000")
        self.timer.stop()
        self.play_pause_button.setIcon(self.play_icon)  # Reset to play icon
        self.play_pause_button.setToolTip("Play")

    def set_position(self, value):
        if self.media_player.is_playing() or self.media_player.get_state() == vlc.State.Paused:
            position = value / 1000.0
            self.media_player.set_position(position)

    def update_ui(self):
        if self.media_player.get_media():
            media_length = self.media_player.get_length()
            if media_length > 0:
                position = self.media_player.get_time()
                self.timeline_slider.setValue(int(self.media_player.get_position() * 1000))
                self.time_label.setText(f"{format_time(position)} / {format_time(media_length)}")
            else:
                self.timeline_slider.setValue(0)
                self.time_label.setText("00:00:00.000 / 00:00:00.000")

    def change_speed(self):
        speed = float(self.speed_combo.currentText()[:-1])
        self.media_player.set_rate(speed)

    def change_volume(self, value):
        self.media_player.audio_set_volume(value)
        self.volume_slider.setValue(value)  # Update slider to match programmatic change

    def increase_volume_button(self):  # New method for volume up button
        current_volume = self.volume_slider.value()
        new_volume = min(current_volume + 10, 100)  # Increment by 10, max 100
        self.change_volume(new_volume)

    def decrease_volume_button(self):  # New method for volume down button
        current_volume = self.volume_slider.value()
        new_volume = max(current_volume - 10, 0)  # Decrement by 10, min 0
        self.change_volume(new_volume)

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        self.media_player.audio_set_mute(self.is_muted)
        if self.is_muted:
            self.mute_button.setIcon(self.mute_icon)  # **CORRECTED: Use mute_icon when muted**
            self.mute_button.setToolTip("Unmute")
        else:
            self.mute_button.setIcon(self.unmute_icon)  # **CORRECTED: Use unmute_icon when unmuted**
            self.mute_button.setToolTip("Mute")

    def seek_forward(self):
        """ Seeks forward by 5 seconds. """
        if not self.media_player.get_media():
            print("Seek Forward: No media loaded.")  # Debugging print
            return
        current_time = self.media_player.get_time()
        new_time = current_time + self.seek_interval
        if new_time > self.media_player.get_length():
            new_time = self.media_player.get_length()
        self.media_player.set_time(new_time)
        print(f"Seek Forward: from {format_time(current_time)} to {format_time(new_time)}")  # Debugging print

    def seek_backward(self):
        """ Seeks backward by 5 seconds. """
        if not self.media_player.get_media():
            print("Seek Backward: No media loaded.")  # Debugging print
            return
        current_time = self.media_player.get_time()
        new_time = current_time - self.seek_interval
        if new_time < 0:
            new_time = 0
        self.media_player.set_time(new_time)
        print(f"Seek Backward: from {format_time(current_time)} to {format_time(new_time)}")  # Debugging print

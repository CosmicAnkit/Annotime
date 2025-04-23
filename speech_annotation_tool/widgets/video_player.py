import sys
import os
import vlc
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox,
                             QFileDialog, QSlider, QHBoxLayout, QMessageBox, QFrame,
                             QApplication, QStyle, QStyleOptionSlider) # Added QStyle, QStyleOptionSlider
from PyQt5.QtCore import Qt, QTimer, QSize, QUrl, pyqtSignal
from PyQt5.QtGui import QIcon, QFont


# Helper function (keep as is)
def format_time(milliseconds):
    if milliseconds < 0: milliseconds = 0
    seconds = milliseconds // 1000
    minutes = seconds // 60
    hours = minutes // 60
    ms = milliseconds % 1000
    return f"{hours:02}:{minutes % 60:02}:{seconds % 60:02}.{ms:03}"

# --- Custom Clickable Slider ---
class ClickableSlider(QSlider):
    """ A QSlider that allows seeking by clicking anywhere on the bar. """
    # Signal emitting the value where the user clicked (0-1000 for timeline)
    clickedValue = pyqtSignal(int)

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)

    def mousePressEvent(self, event):
        """ Handle mouse press events to allow clicking to seek. """
        if event.button() == Qt.LeftButton:
            # Default handling for clicking the handle
            # super().mousePressEvent(event) # Let default handle drag start etc.

            # Calculate value based on click position for setting immediately
            # Use QStyle pixelMetric functions for accurate handle/groove geometry
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            gr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
            sr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)

            if self.orientation() == Qt.Horizontal:
                sliderLength = gr.width() # Use groove width
                sliderPos = event.pos().x() - gr.x() # Position relative to groove start
            else: # Vertical (not used here but for completeness)
                sliderLength = gr.height()
                sliderPos = event.pos().y() - gr.y()

            # Calculate the value ratio
            if sliderLength > 0:
                 # Ensure position is within the valid range (0 to sliderLength)
                sliderPos = max(0, min(sliderPos, sliderLength))
                valueRatio = sliderPos / sliderLength
            else:
                valueRatio = 0

            # For inverted sliders (not applicable here)
            # if self.invertedAppearance(): valueRatio = 1.0 - valueRatio

            newValue = self.minimum() + valueRatio * (self.maximum() - self.minimum())

            # If the click is precisely on the handle, let the default QSlider behavior manage it.
            # Otherwise, set the value and emit our custom signal.
            # Check if click is outside the handle's clickable area
            # handle_rect = sr.adjusted(-2, -2, 2, 2) # Add small tolerance
            # if not handle_rect.contains(event.pos()):
            #    self.setValue(int(newValue))
            #    self.clickedValue.emit(int(newValue)) # Emit the calculated value

            # Simpler approach: Always set value on click, let default handle dragging
            self.setValue(int(newValue))
            self.clickedValue.emit(int(newValue)) # Emit the value for immediate seek

            # Allow default handling AFTER setting the value, enables dragging from click point
            super().mousePressEvent(event)

        else:
            # Handle other mouse buttons if needed
            super().mousePressEvent(event)

# --- Video Player Widget ---
class VideoPlayer(QWidget):
    videoLoaded = pyqtSignal(int)

    # Available speed values and their default index
    SPEED_VALUES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    DEFAULT_SPEED_INDEX = SPEED_VALUES.index(1.0) # Index of 1.0x speed

    def __init__(self, main_window, icon_path_func, default_icon_size=QSize(24, 24)):
        super().__init__()
        self.main_window = main_window
        self.get_icon_path = icon_path_func
        self.default_icon_size = default_icon_size

        try:
             vlc_args = []
             self.instance = vlc.Instance(vlc_args)
             self.media_player = self.instance.media_player_new()
        except Exception as e:
             QMessageBox.critical(self, "VLC Error", f"Failed to initialize VLC instance: {e}")
             self.instance = None
             self.media_player = None

        self.current_video_path = None
        self.is_muted = False
        self._last_volume_before_mute = 50
        self.seek_interval = 5000
        self.loop_interval_ms = 2000
        self.is_looping = False
        self.loop_start_time = 0
        self.loop_end_time = 0
        self._was_playing_before_drag = False

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)

        self._load_icons()
        self.init_ui()
        if self.media_player:
            self.change_volume(50)


    def _load_icons(self):
        """Load QIcon objects."""
        self.play_icon = QIcon(self.get_icon_path("play.png"))
        self.pause_icon = QIcon(self.get_icon_path("pause.png"))
        self.stop_icon = QIcon(self.get_icon_path("stop.png"))
        self.load_icon = QIcon(self.get_icon_path("load.png"))
        self.volume_down_icon = QIcon(self.get_icon_path("volume_down.png"))
        self.volume_up_icon = QIcon(self.get_icon_path("volume_up.png"))
        self.mute_icon = QIcon(self.get_icon_path("mute.png"))
        self.unmute_icon = QIcon(self.get_icon_path("unmute.png"))

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # --- Styling --- (Keep previous general styling)
        # No major style changes needed for this fix, focus on widget replacement/connections
        self.setStyleSheet("""
            QPushButton { background-color: #e8e8e8; border: 1px solid #b8b8b8; border-radius: 4px; padding: 5px 8px; min-width: 40px; }
            QPushButton:hover { background-color: #d8d8d8; border-color: #a8a8a8; }
            QPushButton:pressed { background-color: #c8c8c8; border-color: #989898; }
            QSlider::groove:horizontal { border: 1px solid #bbb; height: 8px; background: #ddd; margin: 2px 0; border-radius: 4px; }
            QSlider::handle:horizontal { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #c1c1c1, stop:1 #d8d8d8); border: 1px solid #a0a0a0; width: 16px; margin: -6px 0; border-radius: 4px; }
            /* Speed Slider Ticks Styling (Optional) */
            QSlider::sub-page:horizontal { background: #88b0ff; border-radius: 4px; } /* Color before handle */
            QSlider::add-page:horizontal { background: #ddd; border-radius: 4px; } /* Color after handle */
            QLabel#timeLabel { font-size: 10pt; color: #333; margin-left: 8px; margin-right: 8px; }
            QLabel#speedLabel { font-size: 9pt; color: #555; min-width: 35px; /* Ensure space for 'x.xx' */ margin-left: 5px; }
            QFrame#videoWidget { background-color: black; border: 1px solid #555; border-radius: 2px; }
        """)


        self.video_widget = QFrame(self)
        self.video_widget.setObjectName("videoWidget")
        self.video_widget.setMinimumSize(320, 180)
        layout.addWidget(self.video_widget, stretch=1)

        timeline_layout = QHBoxLayout()
        timeline_layout.setSpacing(8)
        # --- Use ClickableSlider for timeline ---
        self.timeline_slider = ClickableSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000) # 0.0 to 1.0 position representation
        # Connect standard signals
        self.timeline_slider.sliderMoved.connect(self.set_position_from_slider)
        self.timeline_slider.sliderPressed.connect(self._handle_slider_press)
        self.timeline_slider.sliderReleased.connect(self._handle_slider_release)
        # --- Connect custom clicked signal for immediate seek ---
        self.timeline_slider.clickedValue.connect(self.set_position_from_slider)

        timeline_layout.addWidget(self.timeline_slider)
        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        self.time_label.setObjectName("timeLabel")
        timeline_layout.addWidget(self.time_label)
        layout.addLayout(timeline_layout)

        # --- Controls Frame and Layout ---
        controls_frame = QFrame()
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setContentsMargins(5, 5, 5, 5)
        controls_layout.setSpacing(8)

        # --- Load, Play/Pause, Stop Buttons ---
        self.load_button = QPushButton(self)
        self.load_button.setIcon(self.load_icon)
        self.load_button.setIconSize(self.default_icon_size)
        self.load_button.setToolTip("Load Video File...")
        self.load_button.clicked.connect(self.load_video)
        controls_layout.addWidget(self.load_button)
        # ... Play/Pause, Stop buttons ...
        self.play_pause_button = QPushButton(self)
        self.play_pause_button.setIcon(self.play_icon)
        self.play_pause_button.setIconSize(self.default_icon_size)
        self.play_pause_button.setToolTip("Play / Pause (Ctrl+Space)")
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        controls_layout.addWidget(self.play_pause_button)

        self.stop_button = QPushButton(self)
        self.stop_button.setIcon(self.stop_icon)
        self.stop_button.setIconSize(self.default_icon_size)
        self.stop_button.setToolTip("Stop")
        self.stop_button.clicked.connect(self.stop_video)
        controls_layout.addWidget(self.stop_button)

        controls_layout.addStretch(1) # Push speed/volume to the right

        # --- Speed Control Slider ---
        speed_layout = QHBoxLayout() # Layout for slider + label
        speed_layout.setSpacing(5)
        # Speed Slider
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(0, len(self.SPEED_VALUES) - 1) # Range 0 to 5
        self.speed_slider.setValue(self.DEFAULT_SPEED_INDEX) # Default to 1.0x
        self.speed_slider.setTickPosition(QSlider.TicksBelow) # Add ticks
        self.speed_slider.setTickInterval(1)
        self.speed_slider.setMinimumWidth(100) # Give slider some width
        self.speed_slider.setMaximumWidth(150)
        self.speed_slider.valueChanged.connect(self.change_speed_from_slider)
        self.speed_slider.setToolTip("Playback Speed")
        speed_layout.addWidget(self.speed_slider)
        # Speed Label
        self.speed_label = QLabel(f"{self.SPEED_VALUES[self.DEFAULT_SPEED_INDEX]:.2f}x")
        self.speed_label.setObjectName("speedLabel")
        self.speed_label.setToolTip("Current Playback Speed")
        speed_layout.addWidget(self.speed_label)
        # Add speed layout to main controls
        controls_layout.addLayout(speed_layout)


        # --- Volume Controls ---
        controls_layout.addSpacing(15) # Space before volume
        volume_layout = QHBoxLayout()
        volume_layout.setSpacing(5)
        # ... Volume buttons and slider ...
        self.volume_down_button = QPushButton(self)
        self.volume_down_button.setIcon(self.volume_down_icon)
        self.volume_down_button.setIconSize(self.default_icon_size)
        self.volume_down_button.setToolTip("Decrease Volume")
        self.volume_down_button.clicked.connect(self.decrease_volume_button)
        volume_layout.addWidget(self.volume_down_button)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.change_volume)
        self.volume_slider.setToolTip("Volume")
        self.volume_slider.setMinimumWidth(70)
        self.volume_slider.setMaximumWidth(110)
        volume_layout.addWidget(self.volume_slider)

        self.volume_up_button = QPushButton(self)
        self.volume_up_button.setIcon(self.volume_up_icon)
        self.volume_up_button.setIconSize(self.default_icon_size)
        self.volume_up_button.setToolTip("Increase Volume")
        self.volume_up_button.clicked.connect(self.increase_volume_button)
        volume_layout.addWidget(self.volume_up_button)

        self.mute_button = QPushButton(self)
        self.mute_button.setIcon(self.unmute_icon)
        self.mute_button.setIconSize(self.default_icon_size)
        self.mute_button.setToolTip("Mute / Unmute")
        self.mute_button.setCheckable(True)
        self.mute_button.toggled.connect(self.toggle_mute_button)
        volume_layout.addWidget(self.mute_button)

        controls_layout.addLayout(volume_layout)
        layout.addWidget(controls_frame) # Add the frame containing controls
        self.setLayout(layout)

        # Set initial speed after UI is created
        self.change_speed_from_slider(self.DEFAULT_SPEED_INDEX)

    # --- Method to handle speed slider change ---
    def change_speed_from_slider(self, index):
        """Sets the playback speed based on the slider index."""
        if not self.media_player: return
        try:
            # Ensure index is within bounds (should be by slider range)
            index = max(0, min(index, len(self.SPEED_VALUES) - 1))
            speed = self.SPEED_VALUES[index]
            self.media_player.set_rate(speed)
            # Update the label
            self.speed_label.setText(f"{speed:.2f}x")
            print(f"Playback speed set to: {speed}x")
        except IndexError:
            print(f"Error: Speed slider index {index} out of bounds.")
        except Exception as e:
             print(f"Error setting playback speed: {e}")


    # --- Other methods remain the same ---
    # (load_video, _embed_video, _post_load_setup, toggle_play_pause, play_video, pause_video,
    # stop_video, set_position_from_slider, set_time_ms, update_ui, change_volume,
    # increase_volume_button, decrease_volume_button, toggle_mute_button, seek_forward,
    # seek_backward, set_loop_interval, toggle_loop, start_loop, _execute_start_loop,
    # stop_loop, get_current_time_ms, release_player)

    def _handle_slider_press(self):
        if self.media_player and self.media_player.is_playing():
            self._was_playing_before_drag = True
            self.pause_video(from_user=False)
        else:
            self._was_playing_before_drag = False

    def _handle_slider_release(self):
        # We might not need to explicitly resume here if set_position handles it,
        # but doesn't hurt to ensure playback if it was playing before drag.
        if self._was_playing_before_drag:
            # Check state first, only play if actually paused by the drag
            if self.media_player and not self.media_player.is_playing():
                self.play_video()
        self._was_playing_before_drag = False

    def load_video(self):
        start_dir = os.path.dirname(self.current_video_path) if self.current_video_path else ""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Video", start_dir, "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm)")
        if file_path:
             self.load_video_internal(file_path)

    def load_video_internal(self, file_path, initial_position=0):
        if not self.instance or not self.media_player:
             QMessageBox.critical(self, "Error", "VLC components not initialized.")
             return
        try:
            current_state = self.media_player.get_state()
            if current_state != vlc.State.NothingSpecial and current_state != vlc.State.Stopped and current_state != vlc.State.Error:
                self.media_player.stop()

            media = self.instance.media_new(file_path)
            if not media: raise RuntimeError("Failed to create VLC media object.")
            media.parse_async()
            self.media_player.set_media(media)
            media.release()
            self.current_video_path = file_path

            self._embed_video()
            print(f"Video loaded: {file_path}")
            QTimer.singleShot(300, lambda: self._post_load_setup(initial_position))

        except Exception as e:
            error_message = f"Could not load video file:\n{file_path}\n\nError details: {e}"
            QMessageBox.critical(self, "Error Loading Video", error_message)
            print(f"Error loading video: {e}")
            self.current_video_path = None
            self.time_label.setText("00:00:00.000 / 00:00:00.000")
            self.timeline_slider.setValue(0)

    def _embed_video(self):
         if not self.media_player: return
         widget_id = int(self.video_widget.winId())
         if sys.platform.startswith("linux"): self.media_player.set_xwindow(widget_id)
         elif sys.platform == "win32": self.media_player.set_hwnd(widget_id)
         elif sys.platform == "darwin":
             try: self.media_player.set_nsobject(widget_id)
             except Exception as e_mac: print(f"macOS Warning: {e_mac}")

    def _post_load_setup(self, initial_position):
        if not self.media_player or not self.media_player.get_media(): return

        media_duration = self.media_player.get_length()
        retry = 0
        while media_duration <= 0 and retry < 5:
             print(f"Waiting for media duration... Retry {retry+1}")
             QApplication.processEvents()
             QTimer.singleShot(150 * (retry + 1), lambda: None) # Non-blocking wait
             QApplication.processEvents() # Process after wait
             media_duration = self.media_player.get_length()
             retry += 1

        if media_duration <= 0:
             print("Warning: Could not determine video duration.")
             media_duration = 0

        self.videoLoaded.emit(media_duration)
        self.time_label.setText(f"00:00:00.000 / {format_time(media_duration)}")

        if initial_position > 0 and initial_position < media_duration :
            self.set_time_ms(initial_position) # Seek first
        else:
            self.set_time_ms(0) # Seek to 0 if invalid pos

        # Always pause after load/seek for session restore
        QTimer.singleShot(150, lambda: self.pause_video(from_user=False))


    def toggle_play_pause(self):
        if not self.media_player or not self.media_player.get_media(): return
        if self.is_looping: self.stop_loop()
        if self.media_player.is_playing():
            self.pause_video()
        else:
            state = self.media_player.get_state()
            if state == vlc.State.Ended or state == vlc.State.Stopped:
                 pos_to_resume = self.get_current_time_ms()
                 # Restart from 0 if stopped or at the very end
                 if state == vlc.State.Stopped or pos_to_resume <= 0 or pos_to_resume >= self.media_player.get_length() - 50: # Threshold for end
                     self.set_time_ms(0)
                 else:
                     self.set_time_ms(pos_to_resume) # Resume from last spot otherwise
                 QTimer.singleShot(50, self.play_video)
            else:
                 self.play_video()


    def play_video(self):
        if not self.media_player or not self.media_player.get_media(): return
        if self.media_player.play() == -1: return
        if not self.timer.isActive(): self.timer.start()
        self.play_pause_button.setIcon(self.pause_icon)
        self.play_pause_button.setToolTip("Pause (Ctrl+Space)")

    def pause_video(self, from_user=True):
        if not self.media_player or not self.media_player.get_media(): return
        if self.media_player.is_playing(): self.media_player.pause()
        self.play_pause_button.setIcon(self.play_icon)
        self.play_pause_button.setToolTip("Play (Ctrl+Space)")
        if self.is_looping and from_user: self.stop_loop()


    def stop_video(self):
        if not self.media_player: return
        if self.media_player.get_state() != vlc.State.Stopped: self.media_player.stop()
        self.timeline_slider.setValue(0)
        self.time_label.setText("00:00:00.000 / 00:00:00.000")
        if self.timer.isActive(): self.timer.stop()
        self.play_pause_button.setIcon(self.play_icon)
        self.play_pause_button.setToolTip("Play (Ctrl+Space)")
        if self.is_looping: self.stop_loop()


    def set_position_from_slider(self, value):
        # Handles both drag move and click (via clickedValue signal)
        if self.media_player and self.media_player.get_media() and self.media_player.is_seekable():
            position = value / 1000.0
            self.media_player.set_position(position)
            # Update time label immediately
            current_time = self.media_player.get_time()
            media_length = self.media_player.get_length()
            if media_length > 0:
                 self.time_label.setText(f"{format_time(current_time)} / {format_time(media_length)}")


    def set_time_ms(self, time_ms):
         if not self.media_player or not self.media_player.get_media(): return
         if self.media_player.is_seekable():
             duration = self.media_player.get_length()
             if duration <= 0: return
             time_ms = max(0, min(time_ms, duration))
             print(f"Seeking to time: {format_time(time_ms)}")
             self.media_player.set_time(time_ms)
             QTimer.singleShot(50, self.update_ui)


    def update_ui(self):
        if not self.media_player or not self.media_player.get_media(): return

        media_length = self.media_player.get_length()
        current_time = self.get_current_time_ms()

        if media_length <= 0 or current_time < 0:
             state = self.media_player.get_state() if self.media_player else vlc.State.Error
             if state in [vlc.State.Stopped, vlc.State.Error, vlc.State.NothingSpecial]:
                 if self.time_label.text() != "00:00:00.000 / 00:00:00.000":
                     self.time_label.setText("00:00:00.000 / 00:00:00.000")
                     self.timeline_slider.setValue(0)
             return

        if self.is_looping and self.media_player.is_playing():
            if current_time >= (self.loop_end_time - 30):
                print(f"Looping back from {format_time(current_time)} to {format_time(self.loop_start_time)}")
                self.set_time_ms(self.loop_start_time)
                return

        if not self.timeline_slider.isSliderDown():
             position_ratio = float(current_time) / media_length
             self.timeline_slider.blockSignals(True)
             self.timeline_slider.setValue(int(position_ratio * 1000))
             self.timeline_slider.blockSignals(False)

        self.time_label.setText(f"{format_time(current_time)} / {format_time(media_length)}")

        current_state = self.media_player.get_state()
        if current_state == vlc.State.Ended:
             print("Video ended.")
             self.stop_video()
        elif current_state == vlc.State.Error:
             print("VLC Player Error state detected.")
             self.stop_video()
             QMessageBox.warning(self, "Playback Error", "An error occurred during playback.")
        elif current_state == vlc.State.Paused:
             if self.play_pause_button.icon().cacheKey() != self.play_icon.cacheKey():
                 self.play_pause_button.setIcon(self.play_icon)
                 self.play_pause_button.setToolTip("Play (Ctrl+Space)")
        elif current_state == vlc.State.Playing:
             if self.play_pause_button.icon().cacheKey() != self.pause_icon.cacheKey():
                  self.play_pause_button.setIcon(self.pause_icon)
                  self.play_pause_button.setToolTip("Pause (Ctrl+Space)")


    def change_volume(self, value):
        if not self.media_player: return
        value = max(0, min(100, value))
        if not self.is_muted and value > 0: self._last_volume_before_mute = value
        self.media_player.audio_set_volume(value)
        if self.volume_slider.value() != value:
             self.volume_slider.blockSignals(True); self.volume_slider.setValue(value); self.volume_slider.blockSignals(False)
        # Update mute button visually based on volume only
        self.mute_button.blockSignals(True) # Prevent triggering toggle_mute_button
        self.mute_button.setChecked(value == 0)
        self.mute_button.blockSignals(False)


    def increase_volume_button(self):
        current_visual_volume = self.volume_slider.value()
        new_volume = min(current_visual_volume + 10, 100)
        if self.is_muted:
            self._last_volume_before_mute = new_volume
            self.volume_slider.setValue(new_volume)
        else: self.change_volume(new_volume)


    def decrease_volume_button(self):
        current_visual_volume = self.volume_slider.value()
        new_volume = max(current_visual_volume - 10, 0)
        if self.is_muted:
             self._last_volume_before_mute = new_volume
             self.volume_slider.setValue(new_volume)
        else: self.change_volume(new_volume)


    def toggle_mute_button(self, checked):
        self.is_muted = checked
        if not self.media_player: return
        self.media_player.audio_set_mute(self.is_muted)
        if self.is_muted:
            self.mute_button.setIcon(self.mute_icon); self.mute_button.setToolTip("Unmute")
            current_vol = self.volume_slider.value()
            if current_vol > 0: self._last_volume_before_mute = current_vol
            self.volume_slider.blockSignals(True); self.volume_slider.setValue(0); self.volume_slider.blockSignals(False)
        else:
            self.mute_button.setIcon(self.unmute_icon); self.mute_button.setToolTip("Mute")
            restore_vol = self._last_volume_before_mute if self._last_volume_before_mute > 0 else 50
            self.change_volume(restore_vol)


    def seek_forward(self):
        if not self.media_player or not self.media_player.get_media() or not self.media_player.is_seekable(): return
        if self.is_looping: self.stop_loop()
        current_time = self.get_current_time_ms()
        if current_time < 0: return
        media_length = self.media_player.get_length()
        new_time = min(current_time + self.seek_interval, media_length)
        self.set_time_ms(new_time)
        print(f"Seek Forward: to {format_time(new_time)}")

    def seek_backward(self):
        if not self.media_player or not self.media_player.get_media() or not self.media_player.is_seekable(): return
        if self.is_looping: self.stop_loop()
        current_time = self.get_current_time_ms()
        if current_time < 0: return
        new_time = max(0, current_time - self.seek_interval)
        self.set_time_ms(new_time)
        print(f"Seek Backward: to {format_time(new_time)}")


    def set_loop_interval(self, interval_ms):
        self.loop_interval_ms = max(100, interval_ms)

    def toggle_loop(self):
         if self.is_looping: self.stop_loop()
         else: self.start_loop()

    def start_loop(self):
         if not self.media_player or not self.media_player.get_media(): return
         if not self.media_player.is_playing():
             current_time = self.get_current_time_ms()
             if current_time < 0: return
             self.loop_end_time = current_time
             self.loop_start_time = max(0, current_time - self.loop_interval_ms)
             if self.loop_start_time >= self.loop_end_time: return
             self.is_looping = True
             self.set_time_ms(self.loop_start_time)
             if not self.timer.isActive(): self.timer.start()
             print(f"Loop region set (paused): {format_time(self.loop_start_time)} -> {format_time(self.loop_end_time)}")
         else:
             self._execute_start_loop()

    def _execute_start_loop(self):
        if not self.media_player or not self.media_player.get_media(): return
        current_time = self.get_current_time_ms()
        if current_time < 0: return
        self.loop_end_time = current_time
        self.loop_start_time = max(0, current_time - self.loop_interval_ms)
        if self.loop_start_time >= self.loop_end_time: return
        self.is_looping = True
        self.set_time_ms(self.loop_start_time)
        if not self.timer.isActive(): self.timer.start()
        QTimer.singleShot(100, lambda: self.media_player.play() if self.is_looping and self.media_player else None)
        print(f"Looping started: {format_time(self.loop_start_time)} -> {format_time(self.loop_end_time)}")

    def stop_loop(self):
         if self.is_looping:
             self.is_looping = False
             print("Looping stopped.")

    def get_current_time_ms(self):
        if self.media_player and self.media_player.get_media():
            time_ms = self.media_player.get_time()
            if time_ms == -1:
                 state = self.media_player.get_state()
                 # Only treat -1 as error if state isn't expected (like Stopped)
                 if state not in [vlc.State.Stopped, vlc.State.NothingSpecial, vlc.State.Ended]:
                    print(f"Warning: get_time() returned -1 (State: {state})")
                 return -1 # Return -1 consistently on error/invalid
            return time_ms
        return -1

    def release_player(self):
        """Release VLC resources."""
        print("Attempting to release VLC player...")
        if self.timer.isActive(): self.timer.stop()
        if hasattr(self, 'media_player') and self.media_player:
            try:
                if self.media_player.is_playing() or self.media_player.get_state() == vlc.State.Paused:
                    self.media_player.stop()
                # Detach media first? May not be necessary with instance release.
                # self.media_player.set_media(None)
                self.media_player.release()
                self.media_player = None
                print("Media player released.")
            except Exception as e:
                print(f"Error releasing media player: {e}")

        if hasattr(self, 'instance') and self.instance:
            try:
                self.instance.release()
                self.instance = None
                print("VLC instance released.")
            except Exception as e:
                print(f"Error releasing VLC instance: {e}")
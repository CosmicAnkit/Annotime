import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt
from widgets.video_player import VideoPlayer
from widgets.text_editor import TextEditor

def setup_ui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Speech Annotation Tool")
        self.setGeometry(100, 100, 1200, 600)
        
        # Splitter to divide video player and text editor
        splitter = QSplitter(Qt.Horizontal)
        
        # Video Player Widget
        self.video_player = VideoPlayer()
        splitter.addWidget(self.video_player)
        
        # Text Editor Widget, passing media player instance for timestamp tracking
        self.text_editor = TextEditor(self.video_player.media_player)
        splitter.addWidget(self.text_editor)
        
        # Set stretch factors
        splitter.setStretchFactor(0, 3)  # Video Player takes 3 parts
        splitter.setStretchFactor(1, 2)  # Text Editor takes 2 parts
        
        # Central Widget
        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(splitter)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

if __name__ == "__main__":
    setup_ui()

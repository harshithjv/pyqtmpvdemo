import logging
import platform
import sys

import mpv
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton,
    QVBoxLayout, QFileDialog, QHBoxLayout, QSlider, QGraphicsOpacityEffect,
    QDialog, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation
from PyQt6.QtGui import QPalette, QFont


PLAYER_TITLE = "PyQtMPVDemo Player"

class OpenURLDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open URL")
        self.setGeometry(100, 100, 400, 75)
        
        layout = QVBoxLayout()
        
        label = QLabel("Enter media URL:")
        layout.addWidget(label)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/video.mp4")
        layout.addWidget(self.url_input)
        
        button_layout = QHBoxLayout()
        
        self.load_btn = QPushButton("Load")
        self.cancel_btn = QPushButton("Cancel")
        
        button_layout.addWidget(self.load_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        self.load_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
    
    def get_url(self):
        return self.url_input.text()

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setup_logging()
        self.logger.info("Application started")

        self.media_loaded = False
        self.url_media_loaded = False
        self.setWindowTitle(PLAYER_TITLE)
        self.setGeometry(100, 100, 900, 550)

        self.is_fullscreen = False
        self.is_dragging_slider = False
        self.controls_hide_timer = QTimer()
        self.controls_hide_timer.timeout.connect(self.hide_controls)
        self.mouse_hide_timer = QTimer()
        self.mouse_hide_timer.setSingleShot(True)

        # Main widget
        self.widget = QWidget(self)
        self.setCentralWidget(self.widget)
        self.setAcceptDrops(True)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.widget.setLayout(self.layout)

        # Video area
        self.video_widget = QWidget(self)
        self.video_widget.setStyleSheet("background-color: black;")
        self.video_widget.mousePressEvent = self.on_video_click
        self.layout.addWidget(self.video_widget)

        # Footer: Seek bar + Controls
        self.footer_widget = QWidget(self)
        self.footer_widget.setFixedHeight(75)
        # Use system palette colors for the footer
        palette = self.footer_widget.palette()
        palette.setColor(QPalette.ColorRole.Window, palette.color(QPalette.ColorRole.Base))
        self.footer_widget.setPalette(palette)
        self.footer_widget.setAutoFillBackground(True)
        self.footer_layout = QVBoxLayout()
        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self.footer_layout.setSpacing(0)
        self.footer_widget.setLayout(self.footer_layout)

        # Seek bar
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 100)
        self.footer_layout.addWidget(self.seek_slider)

        # Time display
        self.time_display_layout = QHBoxLayout()
        self.time_display_layout.setContentsMargins(5, 2, 5, 2)
        self.time_display_layout.setSpacing(10)
        
        self.current_time_label = QLabel("00:00:00")
        self.current_time_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        font = QFont()
        font.setPointSize(8)
        self.current_time_label.setFont(font)
        self.time_display_layout.addWidget(self.current_time_label)
        
        self.time_display_layout.addStretch()
        
        self.total_time_label = QLabel("00:00:00 / 00:00:00")
        self.total_time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.total_time_label.setFont(font)
        self.time_display_layout.addWidget(self.total_time_label)
        
        self.footer_layout.addLayout(self.time_display_layout)

        # Controls
        self.controls_widget = QWidget(self)
        self.controls = QHBoxLayout()
        self.controls_widget.setLayout(self.controls)

        self.open_btn = QPushButton("Open")
        self.play_btn = QPushButton("Play")
        self.pause_btn = QPushButton("Pause")
        self.stop_btn = QPushButton("Stop")
        self.open_url_btn = QPushButton("Open URL")
        self.fullscreen_btn = QPushButton("Fullscreen")

        self.controls.addWidget(self.open_btn)
        self.controls.addWidget(self.open_url_btn)
        self.controls.addWidget(self.play_btn)
        self.controls.addWidget(self.pause_btn)
        self.controls.addWidget(self.stop_btn)
        self.controls.addWidget(self.fullscreen_btn)

        self.footer_layout.addWidget(self.controls_widget)
        self.layout.addWidget(self.footer_widget)

        # MPV player
        self.player = self.get_mpv()

        # Timer for updating seek bar
        self.timer = QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_slider)
        self.timer.start()

        # Connections
        self.open_btn.clicked.connect(self.open_file)
        self.open_url_btn.clicked.connect(self.open_url)
        self.play_btn.clicked.connect(self.play)
        self.pause_btn.clicked.connect(self.pause)
        self.stop_btn.clicked.connect(self.stop)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.seek_slider.sliderPressed.connect(self.on_slider_pressed)
        self.seek_slider.sliderReleased.connect(self.on_slider_released)
        self.seek_slider.valueChanged.connect(self.seek_if_dragging)

    def setup_logging(self):
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("demompv.log"),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def get_mpv(self):
        """
        Returns the MPV player instance respective to the OS platform.
        """
        _mpv = None
        if platform.system() == "Windows":
            _mpv = mpv.MPV(
                wid=str(int(self.video_widget.winId())),
                input_default_bindings=True,
                input_vo_keyboard=True,
                hwdec="d3d11va",
                vo="gpu",
                gpu_context="d3d11",   # important for Windows
                d3d11_adapter="NVIDIA",
                profile="high-quality"
            )
        elif platform.system() == "Darwin":  # macOS
            _mpv = mpv.MPV(
                wid=str(int(self.video_widget.winId())),
                input_default_bindings=True,
                input_vo_keyboard=True,
                hwdec="videotoolbox",
                vo="gpu",
                gpu_context="macos",   # important for macOS
                profile="high-quality"
            )
        elif platform.system() == "Linux":
            _mpv = mpv.MPV(
                wid=str(int(self.video_widget.winId())),
                input_default_bindings=True,
                input_vo_keyboard=True,
                hwdec="vulkan",
                vo="gpu",
                vulkan_device="NVIDIA",
                gpu_context="x11egl",   # important for Linux
                profile="high-quality"
            )
        return _mpv


    # -------- Controls --------
    def open_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open Media")
        if file:
            self.stop()  # Stop current playback before opening new file
            self.logger.info(f"Opening file: {file}")
            file_title = str(file)
            try:
                file_title = file.split("/")[-1].split('.')[0]
            except Exception:
                self.logger.warning(f"Could not extract title from file: {file}")
            self.setWindowTitle(f"{PLAYER_TITLE} - {file_title}")
            self.player.play(file)
            self.media_loaded = True
            self.url_media_loaded = False
            # non-blocking way to get media title after it's loaded
            QTimer.singleShot(500, self.set_player_title)

    def open_url(self):
        """Open URL dialog and play media from URL"""
        dialog = OpenURLDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            url = dialog.get_url().strip()
            if url:
                self.logger.info(f"Opening URL: {url}")
                self.stop()
                self.setWindowTitle(f"{PLAYER_TITLE} - {url}")
                self.player.play(url)
                self.media_loaded = True
                self.url_media_loaded = True
                QTimer.singleShot(500, self.set_player_title)

    def get_media_title(self):
        """
        Attempts to retrieve the media title from various metadata keys.
        """
        if self.url_media_loaded:
            # For URLs, we might not have traditional metadata, so we can return the URL or a default title
            return f"Streaming Media{f": {self.player.media_title}" if self.player.media_title else ''}".strip()
        elif self.media_loaded:
            # Common keys for the title
            title_keys = ['icy-title', 'title', 'TITLE', 'name']
            self.logger.debug(self.player.metadata)
            
            for key in title_keys:
                title = self.player.metadata.get(key)
                if title:
                    return title
        
            # If no specific title is found, fall back to the media-title property 
            # which might default to the filename if no tag is present.
            return self.player.media_title or "Title Not Available"
        return PLAYER_TITLE

    def set_player_title(self, title=None):
        if title is None:
            title = self.get_media_title()
        self.setWindowTitle(f"{PLAYER_TITLE} - {title}")


    def play(self):
        self.player.pause = False

    def pause(self):
        self.player.pause = True

    def stop(self):
        self.player.stop()
        self.seek_slider.setValue(0)
        self.current_time_label.setText("00:00:00")
        self.total_time_label.setText("00:00:00 / 00:00:00")
        self.media_loaded = False
        self.setWindowTitle(PLAYER_TITLE)

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.showNormal()
            self.layout.addWidget(self.footer_widget)
            self.layout.setContentsMargins(9, 9, 9, 9)
            self.controls_hide_timer.stop()
            self.footer_widget.show()
            self.show_controls()
        else:
            self.showFullScreen()
            self.layout.removeWidget(self.footer_widget)
            self.footer_widget.setParent(self.widget)
            self.layout.setContentsMargins(0, 0, 0, 0)
            self.show_controls()
            self.controls_hide_timer.start(5000)
        self.is_fullscreen = not self.is_fullscreen
        self.on_resize()

    def on_video_click(self, event):
        """Toggle controls visibility on video click in fullscreen"""
        if self.is_fullscreen:
            if self.footer_widget.isVisible():
                self.hide_controls()
                self.controls_hide_timer.stop()
            else:
                self.show_controls()
                self.controls_hide_timer.start(5000)

    def on_resize(self):
        """Position footer at bottom when in fullscreen"""
        if self.is_fullscreen:
            self.footer_widget.setGeometry(
                0,
                self.widget.height() - self.footer_widget.height(),
                self.widget.width(),
                self.footer_widget.height()
            )

    def resizeEvent(self, event):
        """Handle window resize to reposition footer in fullscreen"""
        super().resizeEvent(event)
        self.on_resize()

    def mouseMoveEvent(self, event):
        if self.is_fullscreen:
            self.show_controls()
            self.controls_hide_timer.start(5000)
        super().mouseMoveEvent(event)

    def show_controls(self):
        """Show footer (slider + controls) with fade in animation"""
        self.footer_widget.show()
        
        opacity_effect = QGraphicsOpacityEffect()
        opacity_effect.setOpacity(0.0)
        self.footer_widget.setGraphicsEffect(opacity_effect)
        
        self.fade_in_animation = QPropertyAnimation(opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(300)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.start()

    def hide_controls(self):
        """Hide footer (slider + controls) with fade out animation"""
        if self.is_fullscreen:
            effect = self.footer_widget.graphicsEffect()
            if effect is None:
                effect = QGraphicsOpacityEffect()
                self.footer_widget.setGraphicsEffect(effect)
            
            self.fade_animation = QPropertyAnimation(effect, b"opacity")
            self.fade_animation.setDuration(1000)
            self.fade_animation.setStartValue(1.0)
            self.fade_animation.setEndValue(0.0)
            self.fade_animation.finished.connect(lambda: self.footer_widget.hide())
            self.fade_animation.start()

    # -------- Seek logic --------
    def format_time(self, seconds):
        """Format seconds to HH:MM:SS format"""
        if seconds is None or seconds < 0:
            return "00:00:00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def update_slider(self):
        try:
            duration = self.player.duration
            position = self.player.time_pos

            if duration and position:
                value = int((position / duration) * 100)
                self.seek_slider.blockSignals(True)
                self.seek_slider.setValue(value)
                self.seek_slider.blockSignals(False)
                
                # Update time display
                current_time_str = self.format_time(position)
                remaining_time = duration - position
                remaining_time_str = self.format_time(remaining_time)
                total_time_str = self.format_time(duration)
                
                self.current_time_label.setText(current_time_str)
                self.total_time_label.setText(f"{remaining_time_str} / {total_time_str}")
        except Exception:
            pass

    def on_slider_pressed(self):
        self.is_dragging_slider = True

    def on_slider_released(self):
        self.is_dragging_slider = False
        self.seek(self.seek_slider.value())

    def seek_if_dragging(self, value):
        """Only seek if user is dragging the slider, not when programmatically updated"""
        if self.is_dragging_slider:
            self.seek(value)

    def seek(self, value):
        try:
            duration = self.player.duration
            if duration:
                new_time = (value / 100) * duration
                self.player.seek(new_time, reference='absolute')
        except Exception:
            pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            # Seek backward by 5 seconds
            try:
                self.player.seek(-5, reference='relative')
            except Exception:
                pass
        elif event.key() == Qt.Key.Key_Right:
            # Seek forward by 5 seconds
            try:
                self.player.seek(5, reference='relative')
            except Exception:
                pass
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        """Accept drag enter events for files"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle dropped files"""
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        if files:
            file = files[0]
            self.logger.info(f"Dropped file: {file}")
            self.stop()
            file_title = str(file)
            try:
                file_title = file.split("/")[-1].split('.')[0]
            except Exception:
                self.logger.warning(f"Could not extract title from file: {file}")
            self.setWindowTitle(f"{PLAYER_TITLE} - {file_title}")
            self.player.play(file)
            self.media_loaded = True
            QTimer.singleShot(500, self.set_player_title)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec())

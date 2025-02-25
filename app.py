import sys
import os
import io
import urllib.parse
from PIL import Image
from PySide6.QtCore import QObject, Signal, QUrl, Qt, QPoint, QRect, QSize, Slot, QDir
from PySide6.QtGui import QGuiApplication, QScreen, QPixmap, QPainter, QColor, QCursor
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QWidget
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

def perform_ocr_with_gemini(image_data, gemini_api_key):
    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        image = Image.open(io.BytesIO(image_data))
        contents = [
            "What text is in this image?",
            image
        ]
        response = model.generate_content(contents)
        extracted_text = response.text
        return extracted_text

    except Exception as e:
        return f"Error during OCR: {e}"


class SnippingTool(QObject):
    screenshotReady = Signal(str)
    ocrResultReady = Signal(str)
    captureStarted = Signal()
    captureEnded = Signal()

    def __init__(self):
        super().__init__()
        self.start_pos = None
        self.end_pos = None
        self.is_snipping = False
        self.overlay_window = None
        self.gemini_api_key = os.environ.get("GOOGLE_API_KEY")

    @Slot()
    def start_capture(self):
        self.is_snipping = True
        self.captureStarted.emit()
        self.start_pos = None
        self.end_pos = None
        self.overlay_window = FullScreenOverlay(self)
        self.overlay_window.showFullScreen()
        QApplication.setOverrideCursor(Qt.CrossCursor)

    @Slot()
    def end_capture(self):
        self.is_snipping = False
        self.captureEnded.emit()
        QApplication.restoreOverrideCursor()
        if self.overlay_window:
            self.overlay_window.close()
            self.overlay_window = None

        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            self.capture_region(rect)

    def mouse_press_event(self, event):
        if self.is_snipping:
            self.start_pos = event.pos()

    def mouse_move_event(self, event):
        if self.is_snipping and self.start_pos:
            self.end_pos = event.pos()
            self.overlay_window.update()

    def mouse_release_event(self, event):
        if self.is_snipping and self.start_pos:
            self.end_pos = event.pos()
            self.end_capture()

    def capture_region(self, rect):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            print("No screen found.")
            return

        pixmap = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
        if pixmap.isNull():
            print("Failed to grab screenshot.")
            return

        temp_file = "screenshot.png"
        pixmap.save(temp_file, "PNG")

        absolute_path = os.path.abspath(temp_file)
        local_path = QDir.toNativeSeparators(absolute_path)

        self.screenshotReady.emit(local_path)

    @Slot(str)
    def process_ocr(self, image_path):
        try:
            path_part = image_path.replace("file:///", "")
            decoded_path = urllib.parse.unquote(path_part)
            with open(decoded_path, "rb") as image_file:
                image_data = image_file.read()

            ocr_result = perform_ocr_with_gemini(image_data, self.gemini_api_key)
            self.ocrResultReady.emit(ocr_result)
        except Exception as e:
            self.ocrResultReady.emit(f"Error processing OCR: {e}")

class FullScreenOverlay(QObject):
    def __init__(self, snipping_tool):
        super().__init__()
        self.snipping_tool = snipping_tool
        self.widget = FullScreenOverlayWidget(snipping_tool)

    def showFullScreen(self):
        self.widget.showFullScreen()

    def close(self):
        self.widget.close()

    def update(self):
        self.widget.update()

class FullScreenOverlayWidget(QWidget):
    def __init__(self, snipping_tool):
        super().__init__()
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowState(Qt.WindowFullScreen)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")
        self.snipping_tool = snipping_tool
        self.start_pos = None
        self.end_pos = None
        self.setCursor(Qt.CrossCursor)

    def mousePressEvent(self, event):
        self.snipping_tool.mouse_press_event(event)
        self.start_pos = event.pos()
        self.update()

    def mouseMoveEvent(self, event):
        self.snipping_tool.mouse_move_event(event)
        self.end_pos = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        self.snipping_tool.mouse_release_event(event)
        self.start_pos = None
        self.end_pos = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setBrush(QColor(0, 0, 0, 128))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

        if self.snipping_tool.start_pos and self.snipping_tool.end_pos:
            selection_rect = QRect(self.snipping_tool.start_pos, self.snipping_tool.end_pos).normalized()
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.drawRect(selection_rect)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    engine = QQmlApplicationEngine()

    snipping_tool = SnippingTool()

    engine.rootContext().setContextProperty("snippingTool", snipping_tool)

    engine.load(QUrl("main.qml"))

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())
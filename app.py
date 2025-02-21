import sys
import os
import io
from PIL import Image
from PySide6.QtCore import QObject, Signal, QUrl, Qt, QPoint, QRect, QSize, Slot
from PySide6.QtGui import QGuiApplication, QScreen, QPixmap, QPainter, QColor, QCursor
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QWidget
import google.generativeai as genai
# --- LLM Integration (Replace with your actual LLM code) ---
def perform_ocr_with_gemini(image_data, gemini_api_key):
    """
    Sends the image data to Gemini Flash 1.5 for OCR.

    Args:
        image_data (bytes): The image data in bytes (e.g., PNG).
        gemini_api_key (str): Your Gemini API key.

    Returns:
        str: The extracted text from the image, or an error message.
    """
    try:
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-2-flash')

        # Prepare the image for Gemini
        image = Image.open(io.BytesIO(image_data))

        # Gemini expects the image as a PIL Image object, not base64.
        # No base64 encoding is needed here.
        contents = [
            "What text is in this image?", # Prompt to guide the model
            image
        ]
        # Generate content
        response = model.generate_content(contents) # Pass the contents array

        # Extract the text from the response
        extracted_text = response.text

        return extracted_text

    except Exception as e:
        return f"Error during OCR: {e}"


class SnippingTool(QObject):
    """Backend logic for the snipping tool."""
    screenshotReady = Signal(str)  # Signal to send the image path to QML
    ocrResultReady = Signal(str)  # Signal to send OCR results to QML
    captureStarted = Signal()
    captureEnded = Signal()

    def __init__(self):
        super().__init__()
        self.start_pos = None
        self.end_pos = None
        self.is_snipping = False  # Flag for the snipping state
        self.overlay_window = None # Reference to the full screen overlay
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY") #  Get the key from environment variables
        print("SnippingTool initialised")  # Verify init is called
        print(f"type(self.start_capture): {type(self.start_capture)}")  # Check the type
        print(f"self.start_capture: {self.start_capture}")  # Inspect the actual object

    @Slot()
    def start_capture(self):
        """Starts the screen capture process."""
        self.is_snipping = True
        self.captureStarted.emit()
        self.start_pos = None  # Reset start position
        self.end_pos = None # Reset end position
        self.overlay_window = FullScreenOverlay(self)  # Create full screen overlay window
        self.overlay_window.showFullScreen() # Shows the full screen overlay
        QApplication.setOverrideCursor(Qt.CrossCursor)  # Change cursor to crosshair

    @Slot()
    def end_capture(self):
        """Ends the capture, processes and saves the screenshot."""
        self.is_snipping = False
        self.captureEnded.emit()
        QApplication.restoreOverrideCursor() # Restore the cursor
        if self.overlay_window:
            self.overlay_window.close() # Closes the overlay window
            self.overlay_window = None

        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            self.capture_region(rect)

    def mouse_press_event(self, event):
        """Handles mouse press events during snipping."""
        if self.is_snipping:
            self.start_pos = event.pos()

    def mouse_move_event(self, event):
        """Handles mouse move events during snipping."""
        if self.is_snipping and self.start_pos:
            self.end_pos = event.pos()
            self.overlay_window.update() # Force redraw of the overlay window.

    def mouse_release_event(self, event):
        """Handles mouse release events during snipping."""
        if self.is_snipping and self.start_pos:
            self.end_pos = event.pos()
            self.end_capture()

    def capture_region(self, rect):
        """Captures the screen region and emits a signal."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            print("No screen found.")
            return

        pixmap = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
        if pixmap.isNull():
            print("Failed to grab screenshot.")
            return

        # Save to a temporary file (optional, for demonstration)
        temp_file = "screenshot.png"  # Or use tempfile.NamedTemporaryFile
        pixmap.save(temp_file, "PNG")  # Save the screenshot

        self.screenshotReady.emit(QUrl.fromLocalFile(os.path.abspath(temp_file)).toString())

    @Slot(str)
    def process_ocr(self, image_path):
        """Processes OCR on the image and emits the result."""
        try:
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()

            ocr_result = perform_ocr_with_gemini(image_data, self.gemini_api_key)
            self.ocrResultReady.emit(ocr_result)
        except Exception as e:
            self.ocrResultReady.emit(f"Error processing OCR: {e}")

class FullScreenOverlay(QObject): # Inherit from QObject
    def __init__(self, snipping_tool):
        super().__init__()
        self.snipping_tool = snipping_tool # Store snipping tool instance
        self.widget = FullScreenOverlayWidget(snipping_tool)  # Create the widget instance

    def showFullScreen(self):
        self.widget.showFullScreen() # Shows the full screen

    def close(self):
        self.widget.close()

    def update(self):
        self.widget.update()

class FullScreenOverlayWidget(QWidget): # Inherit from QWidget
    def __init__(self, snipping_tool):
        super().__init__() # Call to super constructor is needed
        self.setWindowFlag(Qt.FramelessWindowHint) # Remove window borders
        self.setWindowState(Qt.WindowFullScreen) # Make it full screen
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")
        self.snipping_tool = snipping_tool  # Store a reference to the SnippingTool instance
        self.start_pos = None
        self.end_pos = None
        self.setCursor(Qt.CrossCursor)

    def mousePressEvent(self, event):
        self.snipping_tool.mouse_press_event(event)  # Delegate the event
        self.start_pos = event.pos()
        self.update()

    def mouseMoveEvent(self, event):
        self.snipping_tool.mouse_move_event(event)  # Delegate the event
        self.end_pos = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
         self.snipping_tool.mouse_release_event(event)
         self.start_pos = None
         self.end_pos = None

    def paintEvent(self, event):
        print("IM paintevent")
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Explicitly clear the entire widget first
        painter.fillRect(self.rect(), Qt.transparent)

        painter.setBrush(QColor(0, 0, 0, 128))  # Semi-transparent black
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

        if self.snipping_tool.start_pos and self.snipping_tool.end_pos:
            selection_rect = QRect(self.snipping_tool.start_pos, self.snipping_tool.end_pos).normalized()
            painter.setCompositionMode(QPainter.CompositionMode_Clear) # Clear the selection area
            painter.drawRect(selection_rect)


if __name__ == "__main__":
    app = QApplication(sys.argv)  # Use QApplication
    engine = QQmlApplicationEngine()

    snipping_tool = SnippingTool()  # Instantiate the backend

    # Expose the backend object to QML
    engine.rootContext().setContextProperty("snippingTool", snipping_tool)

    # Load the QML file
    engine.load(QUrl("main.qml"))  # Replace with your QML file

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())
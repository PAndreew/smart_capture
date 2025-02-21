import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: mainWindow
    width: 800
    height: 600
    visible: true
    title: "Snipping Tool with OCR"

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        Button {
            id: captureButton
            text: "Capture Screen"
            onClicked: {
                console.log("Capture button clicked!");  // Verify click is registered

                if (snippingTool === null) {
                    console.log("Error: snippingTool is null!"); // Added null check
                } else if (typeof snippingTool === 'undefined') {
                   console.log ("snippingTool is undefined")
                } else if (typeof snippingTool.start_capture !== "function") {
                    console.log("Error: snippingTool.start_capture is not a function!");
                    console.log("Type of snippingTool.start_capture: " + typeof snippingTool.start_capture); // get startCapture type
                    console.log("SnippingTool: " + snippingTool);
                    // Attempt to list properties
                    for (var propertyName in snippingTool) {
                        console.log(propertyName + ": " + snippingTool[propertyName]);
                    }

                } else {
                  console.log("start_capture method is:" + snippingTool.start_capture)
                  console.log ("About to call start capture")
                  snippingTool.start_capture();
                }
            }
            enabled: !snippingTool.is_snipping
        }

        Image {
            id: capturedImage
            source: ""  // Will be populated with the image path
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            Layout.fillHeight: true
            fillMode: Image.PreserveAspectFit
            visible: source !== ""
        }

        Button {
            id: ocrButton
            text: "Process OCR"
            onClicked: {
                snippingTool.process_ocr(capturedImage.source.toString().replace("file://", "")); // Path to file
            }
            enabled: capturedImage.source !== ""
        }

        TextArea {
            id: ocrResult
            Layout.fillWidth: true
            Layout.fillHeight: true
            readOnly: true
            placeholderText: "OCR Result will appear here..."
        }
    }

    Connections {
        target: snippingTool

        function onScreenshotReady(imagePath) {
            capturedImage.source = imagePath;
        }

        function onOcrResultReady(result) {
            ocrResult.text = result;
        }
    }
}
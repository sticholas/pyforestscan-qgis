import QtQuick
import QtWebEngine

Rectangle {
    color: "#202427"
    WebEngineView {
        id: web
        anchors.fill: parent
        url: viewerUrl
        onPermissionRequested: function(permission) { permission.deny(); }
        onNewWindowRequested: function(request) { }
        onJavaScriptConsoleMessage: function(level, message, lineNumber, sourceID) {
            bridge.diagnostic(JSON.stringify({JS_console_messages: {level: level, message: message.slice(0,2000), line: lineNumber}}));
        }
        onLoadingChanged: function(request) {
            if (request.errorCode) bridge.diagnostic(JSON.stringify({WebEngine_errors: {code: request.errorCode, message: request.errorString}}));
        }
        onRenderProcessTerminated: function(terminationStatus, exitCode) {
            bridge.diagnostic(JSON.stringify({
                WebEngine_errors: {kind: "render_process_terminated", status: terminationStatus, exit_code: exitCode},
                error: "Viewer rendering process stopped unexpectedly. Reload Viewer."
            }));
        }
    }
    Connections {
        target: bridge
        function onCommand(payload) {
            var command = JSON.parse(payload);
            if (command.action === "capture") {
                web.runJavaScript("window.captureFrame ? window.captureFrame() : ''",
                                  function(data) { bridge.captured(command.name, data || ""); });
                return;
            }
            web.runJavaScript("window.command && window.command(" + payload + ")");
        }
    }
    Timer {
        interval: 750
        running: true
        repeat: true
        onTriggered: web.runJavaScript("window.snapshot ? JSON.stringify(window.snapshot()) : '{}'",
                                      function(value) { if (value) bridge.telemetry(value); })
    }
}

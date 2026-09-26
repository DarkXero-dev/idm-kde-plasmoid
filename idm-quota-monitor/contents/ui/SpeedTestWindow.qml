import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support

Window {
    id: win

    property string pluginDir: ""

    title: "Internet Speed Test"
    width: 760
    height: 470
    minimumWidth: width
    maximumWidth: width
    minimumHeight: height
    maximumHeight: height

    readonly property string pollCommand: "cat \"${XDG_RUNTIME_DIR:-/tmp}/idm-speedtest.json\" 2>/dev/null"
    readonly property var    idle: ({ value: null, state: "idle", error: "" })

    property string active: ""
    property string phase: "idle"
    property var download: idle
    property var upload: idle
    property var info: ({ ping: null, server: "" })

    function open() {
        show()
        raise()
        requestActivate()
    }

    function setResult(kind, result) {
        if (kind === "download")
            download = result
        else
            upload = result
    }

    function start(kind) {
        active = kind
        phase = "config"
        setResult(kind, { value: null, state: "running", error: "" })
        runner.connectSource("python3 '" + pluginDir + "speed_run.py' " + kind)
        poller.connectSource(pollCommand)
    }

    function apply(reading, final) {
        if (reading.ping !== null)
            info = { ping: reading.ping, server: reading.server || "" }
        phase = reading.phase
        if (final && reading.error)
            setResult(active, { value: null, state: "error", error: reading.error })
        else if (final)
            setResult(active, { value: reading[active], state: "done", error: "" })
        else
            setResult(active, { value: reading.live, state: "running", error: "" })
    }

    function finish(stdout) {
        poller.disconnectSource(pollCommand)
        try {
            apply(JSON.parse(stdout), true)
        } catch (e) {
            setResult(active, { value: null, state: "error", error: "Speed test did not start" })
        }
        active = ""
    }

    function poll(stdout) {
        if (active === "")
            return
        try {
            var reading = JSON.parse(stdout)
            if (reading.phase !== "done" && reading.phase !== "error")
                apply(reading, false)
        } catch (e) {}
    }

    function caption(kind) {
        var result = kind === "download" ? download : upload
        if (result.state === "error")
            return result.error
        if (result.state === "done")
            return "Complete"
        if (result.state !== "running")
            return "Ready"
        return phase === "config" ? "Contacting speedtest.net"
             : phase === "server" ? "Choosing the best server"
             : phase === "ping"   ? "Measuring latency"
             : "Testing " + kind
    }

    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            win.finish(data["stdout"])
        }
    }

    P5Support.DataSource {
        id: poller
        engine: "executable"
        interval: 300
        connectedSources: []
        onNewData: (source, data) => win.poll(data["stdout"])
    }

    Rectangle {
        anchors.fill: parent
        color: Kirigami.Theme.backgroundColor
        Kirigami.Theme.colorSet: Kirigami.Theme.Window
        Kirigami.Theme.inherit: false

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing * 2
            spacing: Kirigami.Units.largeSpacing

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Kirigami.Units.largeSpacing * 2

                SpeedPanel {
                    Layout.fillWidth: true
                    title: "DOWNLOAD"
                    accent: "#22d3ee"
                    value: win.download.value
                    status: win.download.state
                    caption: win.caption("download")
                    canStart: win.active === ""
                    onStartRequested: win.start("download")
                }

                Kirigami.Separator { Layout.fillHeight: true }

                SpeedPanel {
                    Layout.fillWidth: true
                    title: "UPLOAD"
                    accent: "#a855f7"
                    value: win.upload.value
                    status: win.upload.state
                    caption: win.caption("upload")
                    canStart: win.active === ""
                    onStartRequested: win.start("upload")
                }
            }

            PC3.Label {
                Layout.alignment: Qt.AlignHCenter
                visible: win.info.ping !== null
                text: "Ping " + win.info.ping + " ms   Server: " + win.info.server
                font.pixelSize: 12
                opacity: 0.6
            }

            PC3.Button {
                Layout.alignment: Qt.AlignHCenter
                text: "Close"
                icon.name: "window-close"
                onClicked: win.close()
            }
        }
    }
}

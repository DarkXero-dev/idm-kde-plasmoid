import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support

PlasmoidItem {
    id: root

    readonly property string scriptPath: Qt.resolvedUrl("../../fetch_quota.py").toString().replace("file://", "")

    // Per-connection data
    property var adsl: ({ percent: 0, remaining: "", updated: "", error: "" })
    property var lte:  ({ percent: 0, remaining: "", updated: "", error: "" })
    property var adslHistory: []
    property var lteHistory:  []

    property bool loading: false

    readonly property bool configured: Plasmoid.configuration.username !== ""
                                    && Plasmoid.configuration.password !== ""

    readonly property string connChoice: Plasmoid.configuration.connectionChoice

    function pctColor(pct) {
        return pct >= 90 ? "#e74c3c" : pct >= 70 ? "#f39c12" : "#2ecc71"
    }

    preferredRepresentation: compactRepresentation

    // ── Sync credentials to ~/.config/IDMQuota/config.conf ───────────────
    property bool _refreshAfterWrite: false

    P5Support.DataSource {
        id: fileWriter
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            fileWriter.disconnectSource(source)
            if (root._refreshAfterWrite) {
                root._refreshAfterWrite = false
                Qt.callLater(root.runScript)
            }
        }
    }

    function toHex(str) {
        var r = ""
        for (var i = 0; i < str.length; i++)
            r += str.charCodeAt(i).toString(16).padStart(2, "0")
        return r
    }

    function writeConfigFile() {
        if (!configured) return
        var u = toHex(Plasmoid.configuration.username)
        var p = toHex(Plasmoid.configuration.password)
        fileWriter.connectSource("python3 " + scriptPath + " --write-config " + u + " " + p)
    }

    Timer {
        id: credentialsChangedTimer
        interval: 50
        repeat: false
        onTriggered: {
            root._refreshAfterWrite = true
            root.writeConfigFile()
        }
    }

    Connections {
        target: Plasmoid.configuration
        function onUsernameChanged() { credentialsChangedTimer.restart() }
        function onPasswordChanged() { credentialsChangedTimer.restart() }
    }

    Component.onCompleted: writeConfigFile()

    // ── Fetch both connections ────────────────────────────────────────────
    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            runner.disconnectSource(source)
            root.loading = false
            try {
                var d = JSON.parse(data["stdout"])
                if (d.adsl) root.adsl = d.adsl
                if (d.lte)  root.lte  = d.lte
                if (d.adsl_history) root.adslHistory = d.adsl_history
                if (d.lte_history)  root.lteHistory  = d.lte_history
            } catch (e) {
                root.adsl = { percent: 0, remaining: "", updated: "", error: "Parse error" }
                root.lte  = { percent: 0, remaining: "", updated: "", error: "Parse error" }
            }
        }
    }

    function runScript() {
        if (!configured) return
        loading = true
        runner.connectSource("python3 " + scriptPath)
    }

    Timer {
        interval: 900000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.runScript()
    }

    // ── Compact: panel bar with clickable connection toggle ───────────────
    compactRepresentation: MouseArea {
        id: compactArea
        implicitWidth: panelLayout.implicitWidth + Kirigami.Units.largeSpacing * 2
        Layout.minimumWidth: implicitWidth
        Layout.preferredWidth: implicitWidth
        onClicked: root.expanded = !root.expanded

        RowLayout {
            id: panelLayout
            anchors.centerIn: parent
            spacing: 4

            // activeData lives on the RowLayout so all children can use parent.activeData
            readonly property var activeData: root.connChoice === "lte" ? root.lte : root.adsl

            // ── Connection toggle badge ───────────────────────────────────
            Item {
                id: connToggle
                implicitWidth: connLabel.implicitWidth + Kirigami.Units.smallSpacing * 2
                height: 14

                Rectangle {
                    anchors.fill: parent
                    radius: 2
                    color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                                   Kirigami.Theme.highlightColor.g,
                                   Kirigami.Theme.highlightColor.b,
                                   toggleArea.containsMouse ? 0.35 : 0.18)
                    Behavior on color { ColorAnimation { duration: 150 } }
                }

                PC3.Label {
                    id: connLabel
                    anchors.centerIn: parent
                    text: root.connChoice === "lte" ? "LTE" : "ADSL"
                    font.pixelSize: 9
                    font.bold: true
                }

                // Intercepts clicks here — stops propagation to outer MouseArea
                MouseArea {
                    id: toggleArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        Plasmoid.configuration.connectionChoice =
                            (root.connChoice === "lte" ? "adsl" : "lte")
                    }
                }
            }

            // ── Progress bar ──────────────────────────────────────────────
            Item {
                width: 55
                height: 5

                Rectangle {
                    anchors.fill: parent
                    radius: 2
                    color: Qt.rgba(Kirigami.Theme.textColor.r,
                                   Kirigami.Theme.textColor.g,
                                   Kirigami.Theme.textColor.b, 0.15)
                }
                Rectangle {
                    width: !root.configured || panelLayout.activeData.error
                           ? 0
                           : parent.width * Math.min(panelLayout.activeData.percent / 100, 1)
                    height: parent.height
                    radius: 2
                    color: root.loading
                           ? Kirigami.Theme.disabledTextColor
                           : root.pctColor(panelLayout.activeData.percent)
                    Behavior on width { NumberAnimation { duration: 500 } }
                    Behavior on color { ColorAnimation  { duration: 400 } }
                }
            }

            // ── Percentage label ──────────────────────────────────────────
            PC3.Label {
                text: !root.configured                    ? "setup"
                    : root.loading                        ? "…"
                    : panelLayout.activeData.error        ? "err"
                    : panelLayout.activeData.percent.toFixed(1) + "%"
                font.pixelSize: 10
                font.bold: true
                color: !root.configured || panelLayout.activeData.error
                       ? Kirigami.Theme.disabledTextColor
                       : root.loading
                         ? Kirigami.Theme.textColor
                         : root.pctColor(panelLayout.activeData.percent)
            }

            // Trailing gap so widget doesn't crowd its neighbour
            Item { width: Kirigami.Units.smallSpacing }
        }
    }

    // ── Full popup: two tabs ──────────────────────────────────────────────
    fullRepresentation: Item {
        Layout.preferredWidth:  980
        Layout.minimumWidth:    980
        Layout.preferredHeight: Kirigami.Units.gridUnit * 26

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            spacing: 0

            // Tab bar
            PC3.TabBar {
                id: tabBar
                Layout.fillWidth: true
                currentIndex: root.connChoice === "lte" ? 1 : 0

                PC3.TabButton { text: "ADSL" }
                PC3.TabButton { text: "LTE"  }
            }

            // Tab pages
            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: tabBar.currentIndex

                ConnectionTab {
                    data_:    root.adsl
                    history:  root.adslHistory
                    loading:  root.loading
                    pctColor: root.pctColor(root.adsl.percent)
                }
                ConnectionTab {
                    data_:    root.lte
                    history:  root.lteHistory
                    loading:  root.loading
                    pctColor: root.pctColor(root.lte.percent)
                }
            }

            // Footer
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Kirigami.Theme.separatorColor
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.smallSpacing

                PC3.Label {
                    visible: !root.configured
                    text: "⚙ Right-click → Configure to set credentials"
                    font.pixelSize: 10
                    opacity: 0.65
                    Layout.fillWidth: true
                }
                Item { Layout.fillWidth: true; visible: root.configured }

                PC3.Button {
                    text: root.loading ? "Loading…" : "Refresh"
                    icon.name: "view-refresh"
                    enabled: !root.loading && root.configured
                    onClicked: root.runScript()
                }
            }
        }
    }
}

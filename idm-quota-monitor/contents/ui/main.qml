import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support
import "util.js" as Util

PlasmoidItem {
    id: root

    readonly property string pluginDir: decodeURIComponent(Qt.resolvedUrl("../../").toString().replace("file://", ""))
    readonly property int maxShown: 3

    property var services: []
    property string fetchError: ""
    property bool loading: false

    readonly property bool configured: Plasmoid.configuration.username !== ""
                                    && Plasmoid.configuration.password !== ""

    readonly property var selectedIds: {
        try { return JSON.parse(Plasmoid.configuration.selectedServices) } catch (e) { return [] }
    }

    readonly property var names: {
        try { return JSON.parse(Plasmoid.configuration.serviceNames) } catch (e) { return {} }
    }

    readonly property var shown: {
        var picked = services.filter(s => selectedIds.indexOf(s.id) >= 0)
        return (picked.length > 0 ? picked : services).slice(0, maxShown)
    }

    readonly property var active: shown.find(s => s.id === Plasmoid.configuration.activeService) || shown[0] || null

    readonly property string gaugeStyle: Plasmoid.configuration.gaugeStyle

    preferredRepresentation: compactRepresentation
    toolTipMainText: "IDM Quota"
    toolTipSubText: shown.map(s => Util.typeLabel(s.type) + " " + Util.displayName(s, names) + ": "
                                   + (s.error ? "error" : s.percent === null ? "-" : s.percent.toFixed(1) + "%")).join("\n")

    SpeedTestWindow {
        id: speedWindow
        pluginDir: root.pluginDir
    }

    function cycleActive() {
        if (shown.length < 2)
            return
        Plasmoid.configuration.activeService = shown[(shown.indexOf(active) + 1) % shown.length].id
    }

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

    function writeConfigFile() {
        if (!configured) return
        fileWriter.connectSource("python3 '" + pluginDir + "fetch_quota.py' --write-config "
                                 + Util.toHex(Plasmoid.configuration.username) + " "
                                 + Util.toHex(Plasmoid.configuration.password))
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

    // ── Fetch every service ───────────────────────────────────────────────
    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            runner.disconnectSource(source)
            root.loading = false
            try {
                var d = JSON.parse(data["stdout"])
                root.fetchError = d.error || ""
                root.services = d.services || []
            } catch (e) {
                root.fetchError = "Could not read the fetch result"
                root.services = []
            }
        }
    }

    function runScript() {
        if (!configured) return
        loading = true
        runner.connectSource("python3 '" + pluginDir + "fetch_quota.py'")
    }

    Timer {
        interval: 900000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.runScript()
    }

    // ── Compact: panel bar, badge cycles through the shown services ───────
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

            readonly property var  svc:    root.active
            readonly property bool failed: root.configured && !root.loading
                                           && (root.fetchError !== "" || (svc !== null && svc.error))
            readonly property bool hasPct: svc !== null && svc.percent !== null && svc.percent !== undefined

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
                    text: panelLayout.svc ? Util.typeLabel(panelLayout.svc.type) : "IDM"
                    font.pixelSize: 9
                    font.bold: true
                }

                // Intercepts clicks here so the outer MouseArea does not toggle the popup
                MouseArea {
                    id: toggleArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.cycleActive()
                }
            }

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
                    width: !root.configured || panelLayout.failed || !panelLayout.hasPct
                           ? 0
                           : parent.width * Math.min(panelLayout.svc.percent / 100, 1)
                    height: parent.height
                    radius: 2
                    color: root.loading
                           ? Kirigami.Theme.disabledTextColor
                           : Util.pctColor(panelLayout.hasPct ? panelLayout.svc.percent : 0)
                    Behavior on width { NumberAnimation { duration: 500 } }
                    Behavior on color { ColorAnimation  { duration: 400 } }
                }
            }

            PC3.Label {
                text: !root.configured    ? "setup"
                    : root.loading        ? "…"
                    : panelLayout.failed  ? "err"
                    : !panelLayout.hasPct ? "-"
                    : panelLayout.svc.percent.toFixed(1) + "%"
                font.pixelSize: 10
                font.bold: true
                color: !root.configured || panelLayout.failed || !panelLayout.hasPct
                       ? Kirigami.Theme.disabledTextColor
                       : root.loading
                         ? Kirigami.Theme.textColor
                         : Util.pctColor(panelLayout.svc.percent)
            }

            Item { width: Kirigami.Units.smallSpacing }
        }
    }

    // ── Full popup ────────────────────────────────────────────────────────
    fullRepresentation: Popup {
        shown:      root.shown
        names:      root.names
        gaugeStyle: root.gaugeStyle
        loading:    root.loading
        configured: root.configured
        fetchError: root.fetchError
        active:     root.expanded

        onSettingsRequested: Plasmoid.internalAction("configure").trigger()
        onSpeedTestRequested: {
            speedWindow.open()
            root.expanded = false
        }
        onRefreshRequested: root.runScript()
    }
}

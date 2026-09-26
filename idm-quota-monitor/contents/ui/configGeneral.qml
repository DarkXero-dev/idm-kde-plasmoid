import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.kde.plasma.plasma5support as P5Support
import "util.js" as Util

KCM.SimpleKCM {
    id: root

    property alias cfg_username: usernameField.text
    property alias cfg_password: passwordField.text
    property string cfg_selectedServices: "[]"
    property string cfg_serviceNames: "{}"
    property string cfg_gaugeStyle: "speedometer"

    readonly property int maxServices: 3
    readonly property string scriptPath: Qt.resolvedUrl("../../fetch_quota.py").toString().replace("file://", "")
    readonly property var selected: {
        try { return JSON.parse(cfg_selectedServices) } catch (e) { return [] }
    }

    readonly property var names: {
        try { return JSON.parse(cfg_serviceNames) } catch (e) { return {} }
    }

    property var services: []
    property string status: ""
    property bool detecting: false

    function runList() {
        detecting = true
        status = "Detecting services..."
        detector.connectSource("python3 '" + scriptPath + "' --list")
    }

    function detect() {
        detecting = true
        status = "Detecting services..."
        detector.connectSource("python3 '" + scriptPath + "' --write-config "
                               + Util.toHex(usernameField.text) + " " + Util.toHex(passwordField.text))
    }

    function handleList(stdout) {
        detecting = false
        var d
        try {
            d = JSON.parse(stdout)
        } catch (e) {
            status = "Could not read the service list"
            return
        }
        if (d.error) {
            services = []
            status = d.error
            return
        }
        services = d.services
        status = services.length + (services.length === 1 ? " service found" : " services found")
        var ids = services.map(s => s.id)
        var kept = selected.filter(id => ids.indexOf(id) >= 0)
        if (kept.length === 0)
            kept = ids.slice(0, maxServices)
        if (kept.length !== selected.length)
            cfg_selectedServices = JSON.stringify(kept)
    }

    function rename(id, text) {
        var next = Object.assign({}, names)
        if (text.trim() !== "")
            next[id] = text.trim()
        else
            delete next[id]
        cfg_serviceNames = JSON.stringify(next)
    }

    function toggle(id, on) {
        var next = selected.filter(x => x !== id)
        if (on)
            next.push(id)
        cfg_selectedServices = JSON.stringify(next)
    }

    P5Support.DataSource {
        id: detector
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            if (source.indexOf("--write-config") >= 0)
                root.runList()
            else
                root.handleList(data["stdout"])
        }
    }

    Component.onCompleted: Qt.callLater(() => {
        if (usernameField.text !== "")
            runList()
    })

    Kirigami.FormLayout {
        anchors.fill: parent

        QQC2.TextField {
            id: usernameField
            Kirigami.FormData.label: "Username:"
            placeholderText: "IDM login username"
        }

        QQC2.TextField {
            id: passwordField
            Kirigami.FormData.label: "Password:"
            echoMode: TextInput.Password
            placeholderText: "IDM login password"
        }

        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: "Services"
        }

        RowLayout {
            Kirigami.FormData.label: "Detect:"

            QQC2.Button {
                text: "Detect services"
                icon.name: "view-refresh"
                enabled: !root.detecting && usernameField.text !== "" && passwordField.text !== ""
                onClicked: root.detect()
            }

            QQC2.Label {
                text: root.status
                opacity: 0.7
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        ColumnLayout {
            Kirigami.FormData.label: "Show (max " + root.maxServices + "):"
            visible: root.services.length > 0

            Repeater {
                model: root.services

                RowLayout {
                    required property var modelData

                    QQC2.CheckBox {
                        text: Util.typeLabel(modelData.type)
                        checked: root.selected.indexOf(modelData.id) >= 0
                        enabled: checked || root.selected.length < root.maxServices
                        onToggled: root.toggle(modelData.id, checked)
                    }

                    QQC2.TextField {
                        placeholderText: modelData.name
                        text: root.names[modelData.id] || ""
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 12
                        onTextEdited: root.rename(modelData.id, text)
                    }
                }
            }

            QQC2.Label {
                text: "Tick to show. Type a name to rename a service."
                opacity: 0.6
                font.pixelSize: 11
            }
        }

        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: "Appearance"
        }

        QQC2.ComboBox {
            Kirigami.FormData.label: "Usage gauge:"
            model: [
                { text: "Speedometer", value: "speedometer" },
                { text: "Simple",       value: "simple" }
            ]
            textRole: "text"
            valueRole: "value"
            currentIndex: root.cfg_gaugeStyle === "simple" ? 1 : 0
            onActivated: root.cfg_gaugeStyle = currentValue
        }
    }
}

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import "util.js" as Util

ColumnLayout {
    id: panel

    property string title: ""
    property color  accent: "#22d3ee"
    property var    value: null
    property string status: "idle"
    property string caption: ""
    property bool   canStart: true
    signal startRequested()

    readonly property bool running: status === "running"

    property real needle: 0
    Behavior on needle { NumberAnimation { duration: 950; easing.type: Easing.InOutSine } }
    onNeedleChanged: gauge.requestPaint()
    onAccentChanged: gauge.requestPaint()
    onValueChanged:  needle = Util.speedFraction(value)

    spacing: Kirigami.Units.largeSpacing

    PC3.Label {
        Layout.alignment: Qt.AlignHCenter
        text: panel.title
        font.pixelSize: 16
        font.bold: true
        font.letterSpacing: 2
        color: panel.accent
    }

    Item {
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredWidth: 320
        Layout.preferredHeight: 270

        Canvas {
            id: gauge
            anchors.fill: parent

            Component.onCompleted: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)

                var cx = width / 2
                var cy = height / 2 + 4
                var r  = Math.min(cx, cy) - 36
                var start = Math.PI * 0.75
                var sweep = Math.PI * 1.5
                var text  = Kirigami.Theme.textColor
                var angle = start + sweep * panel.needle

                ctx.lineCap = "round"
                ctx.lineWidth = 12
                ctx.beginPath()
                ctx.arc(cx, cy, r, start, start + sweep)
                ctx.strokeStyle = Qt.rgba(text.r, text.g, text.b, 0.10)
                ctx.stroke()

                if (panel.needle > 0.002) {
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, start, angle)
                    ctx.strokeStyle = panel.accent
                    ctx.stroke()
                }

                ctx.font = "11px sans-serif"
                ctx.textAlign = "center"
                ctx.textBaseline = "middle"
                var marks = Util.SPEED_SCALE
                for (var i = 0; i < marks.length; i++) {
                    var a = start + sweep * (i / (marks.length - 1))
                    ctx.beginPath()
                    ctx.moveTo(cx + Math.cos(a) * (r - 16), cy + Math.sin(a) * (r - 16))
                    ctx.lineTo(cx + Math.cos(a) * (r - 8),  cy + Math.sin(a) * (r - 8))
                    ctx.lineWidth = 2
                    ctx.strokeStyle = Qt.rgba(text.r, text.g, text.b, 0.4)
                    ctx.stroke()
                    ctx.fillStyle = Qt.rgba(text.r, text.g, text.b, 0.6)
                    ctx.fillText(marks[i], cx + Math.cos(a) * (r + 24), cy + Math.sin(a) * (r + 24))
                }

                var tip = r - 22
                var glow = Qt.color(panel.accent)
                var glowGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, tip)
                glowGrad.addColorStop(0, Qt.rgba(glow.r, glow.g, glow.b, 0.30))
                glowGrad.addColorStop(1, Qt.rgba(glow.r, glow.g, glow.b, 0))
                ctx.beginPath()
                ctx.moveTo(cx - Math.cos(angle) * 14, cy - Math.sin(angle) * 14)
                ctx.lineTo(cx + Math.cos(angle) * tip, cy + Math.sin(angle) * tip)
                ctx.lineWidth = 10
                ctx.strokeStyle = glowGrad
                ctx.stroke()

                ctx.beginPath()
                ctx.moveTo(cx - Math.cos(angle) * 14, cy - Math.sin(angle) * 14)
                ctx.lineTo(cx + Math.cos(angle) * tip, cy + Math.sin(angle) * tip)
                ctx.lineWidth = 3
                ctx.strokeStyle = panel.accent
                ctx.stroke()

                ctx.beginPath()
                ctx.arc(cx, cy, 8, 0, Math.PI * 2)
                ctx.fillStyle = panel.accent
                ctx.fill()
            }

            Connections {
                target: Kirigami.Theme
                function onTextColorChanged() { gauge.requestPaint() }
            }
        }

        ColumnLayout {
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height / 2 + 44
            spacing: 0

            PC3.Label {
                Layout.alignment: Qt.AlignHCenter
                text: panel.value !== null ? panel.value.toFixed(1) : "-"
                font.pixelSize: 40
                font.bold: true
                color: panel.accent
            }
            PC3.Label {
                Layout.alignment: Qt.AlignHCenter
                text: "Mbps"
                font.pixelSize: 13
                opacity: 0.6
            }
        }
    }

    PC3.Label {
        Layout.fillWidth: true
        text: panel.caption
        font.pixelSize: 13
        opacity: panel.status === "error" ? 1 : 0.75
        color: panel.status === "error" ? "#e74c3c" : Kirigami.Theme.textColor
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
    }

    PC3.Button {
        Layout.alignment: Qt.AlignHCenter
        text: panel.running ? "Testing…" : panel.status === "idle" ? "Start" : "Run again"
        icon.name: "media-playback-start"
        enabled: panel.canStart && !panel.running
        highlighted: panel.status === "idle"
        onClicked: panel.startRequested()
    }
}

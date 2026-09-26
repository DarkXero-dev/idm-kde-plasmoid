import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import "util.js" as Util

Item {
    id: tab

    implicitWidth:  374
    implicitHeight: 270
    clip: true

    property var    svc:        ({})
    property string alias:      ""
    property bool   loading:    false
    property string gaugeStyle: "speedometer"

    property date now: new Date()
    readonly property bool  isSimple: gaugeStyle === "simple"
    readonly property real  gaugeSize: Math.max(120, Math.min(218, height - cardHeader.height - 24))
    readonly property real  simpleWidth: Math.max(180, Math.min(width - 32, 2 * (height - cardHeader.height - stats.implicitHeight - 32)))
    readonly property real  simpleStroke: Math.round(simpleWidth * 0.07)
    readonly property color pctColor: Util.pctColor(svc.percent)
    readonly property var   expiry:   Util.expiryState(svc.expiry_iso, now)

    onLoadingChanged:    gauge.requestPaint()
    onPctColorChanged:   gauge.requestPaint()
    onGaugeStyleChanged: gauge.requestPaint()
    onSvcChanged:        gauge.requestPaint()

    Timer {
        interval: 60000
        running: true
        repeat: true
        onTriggered: tab.now = new Date()
    }

    function textColor(alpha) {
        return Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, alpha)
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 6

        RowLayout {
            id: cardHeader
            Layout.alignment: Qt.AlignHCenter
            spacing: 8

            PC3.Label {
                text: tab.alias !== "" ? tab.alias : Util.typeLabel(svc.type)
                font.pixelSize: 15
                font.bold: true
                font.letterSpacing: 2
                opacity: tab.alias !== "" ? 0.7 : 0.5
                elide: Text.ElideRight
                Layout.maximumWidth: tab.width - 32
            }
            PC3.Label {
                visible: tab.alias === ""
                text: svc.name || ""
                font.pixelSize: 13
                opacity: 0.35
                elide: Text.ElideRight
                Layout.maximumWidth: 170
            }
        }

        GridLayout {
            columns: tab.isSimple ? 1 : 2
            columnSpacing: 16
            rowSpacing: 4
            Layout.alignment: Qt.AlignHCenter

            Canvas {
                id: gauge
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth:  tab.isSimple ? tab.simpleWidth : tab.gaugeSize
                Layout.preferredHeight: tab.isSimple ? tab.simpleWidth / 2 + tab.simpleStroke / 2 + 4 : tab.gaugeSize

                onWidthChanged:  requestPaint()
                onHeightChanged: requestPaint()

                property real pct: svc.error ? 0 : (svc.percent || 0)

                Behavior on pct { NumberAnimation { duration: 800; easing.type: Easing.InOutCubic } }

                onPctChanged:          requestPaint()
                Component.onCompleted: requestPaint()

                function ink() {
                    return tab.loading ? tab.textColor(0.4) : tab.pctColor
                }

                function label() {
                    return tab.loading ? "…" : svc.error ? "ERR" : pct.toFixed(1) + "%"
                }

                function paintSpeedometer(ctx) {
                    var cx         = width  / 2
                    var cy         = height / 2
                    var r          = Math.min(cx, cy) - 15
                    var startAngle = Math.PI * 0.75
                    var fullSweep  = Math.PI * 1.5
                    var endAngle   = startAngle + fullSweep * (pct / 100)

                    for (var i = 0; i <= 10; i++) {
                        var ta      = startAngle + fullSweep * (i / 10)
                        var isMajor = (i % 5 === 0)
                        ctx.beginPath()
                        ctx.moveTo(cx + Math.cos(ta) * (r - (isMajor ? 12 : 6)),
                                   cy + Math.sin(ta) * (r - (isMajor ? 12 : 6)))
                        ctx.lineTo(cx + Math.cos(ta) * (r + 2),
                                   cy + Math.sin(ta) * (r + 2))
                        ctx.lineWidth   = isMajor ? 2 : 1
                        ctx.strokeStyle = tab.textColor(isMajor ? 0.35 : 0.18)
                        ctx.stroke()
                    }

                    ctx.beginPath()
                    ctx.arc(cx, cy, r, startAngle, startAngle + fullSweep)
                    ctx.lineWidth   = 10
                    ctx.strokeStyle = tab.textColor(0.10)
                    ctx.lineCap     = "round"
                    ctx.stroke()

                    if (pct > 0) {
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, startAngle, endAngle)
                        ctx.lineWidth   = 10
                        ctx.strokeStyle = tab.pctColor
                        ctx.stroke()
                    }

                    var needleLen  = r - 18
                    var needleBase = 11
                    var glow = Qt.color(tab.pctColor)
                    var glowGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, needleLen)
                    glowGrad.addColorStop(0, Qt.rgba(glow.r, glow.g, glow.b, 0.25))
                    glowGrad.addColorStop(1, Qt.rgba(glow.r, glow.g, glow.b, 0))
                    ctx.beginPath()
                    ctx.moveTo(cx - Math.cos(endAngle) * needleBase, cy - Math.sin(endAngle) * needleBase)
                    ctx.lineTo(cx + Math.cos(endAngle) * needleLen,  cy + Math.sin(endAngle) * needleLen)
                    ctx.lineWidth   = 8
                    ctx.strokeStyle = glowGrad
                    ctx.stroke()

                    ctx.beginPath()
                    ctx.moveTo(cx - Math.cos(endAngle) * needleBase, cy - Math.sin(endAngle) * needleBase)
                    ctx.lineTo(cx + Math.cos(endAngle) * needleLen,  cy + Math.sin(endAngle) * needleLen)
                    ctx.lineWidth   = 2.5
                    ctx.strokeStyle = ink()
                    ctx.stroke()

                    ctx.beginPath()
                    ctx.arc(cx, cy, 6, 0, Math.PI * 2)
                    ctx.fillStyle = ink()
                    ctx.fill()

                    ctx.fillStyle    = tab.loading ? tab.textColor(0.4) : svc.error ? "#e74c3c" : tab.pctColor
                    ctx.font         = "bold 22px sans-serif"
                    ctx.textAlign    = "center"
                    ctx.textBaseline = "middle"
                    ctx.fillText(label(), cx, cy + r * 0.72)
                }

                function paintSimple(ctx) {
                    var stroke = tab.simpleStroke
                    var cx     = width / 2
                    var cy     = height - stroke / 2 - 2
                    var r      = cx - stroke / 2

                    ctx.lineWidth = stroke
                    ctx.lineCap   = "round"

                    ctx.beginPath()
                    ctx.arc(cx, cy, r, Math.PI, Math.PI * 2)
                    ctx.strokeStyle = tab.textColor(0.10)
                    ctx.stroke()

                    if (pct > 0) {
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, Math.PI, Math.PI + Math.PI * (pct / 100))
                        ctx.strokeStyle = ink()
                        ctx.stroke()
                    }

                    ctx.fillStyle    = tab.loading ? tab.textColor(0.4) : svc.error ? "#e74c3c" : tab.pctColor
                    ctx.font         = "bold " + Math.round(r * 0.34) + "px sans-serif"
                    ctx.textAlign    = "center"
                    ctx.textBaseline = "middle"
                    ctx.fillText(label(), cx, cy - r * 0.3)
                }

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    if (tab.isSimple)
                        paintSimple(ctx)
                    else
                        paintSpeedometer(ctx)
                }

                Connections {
                    target: Kirigami.Theme
                    function onTextColorChanged() { gauge.requestPaint() }
                }
            }

            GridLayout {
                id: stats
                columns: tab.isSimple ? 3 : 1
                columnSpacing: 26
                rowSpacing: 10
                Layout.alignment: tab.isSimple ? Qt.AlignHCenter : Qt.AlignVCenter

                ColumnLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignTop
                    PC3.Label { text: "Remaining"; font.pixelSize: 13; opacity: 0.5 }
                    PC3.Label {
                        text: tab.loading ? "…" : svc.error ? svc.error : (svc.remaining || "-")
                        font.pixelSize: 16; font.bold: true
                        color: svc.error ? "#e74c3c" : Kirigami.Theme.textColor
                        wrapMode: Text.WordWrap
                        Layout.maximumWidth: tab.isSimple ? 110 : 132
                    }
                }

                ColumnLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignTop
                    PC3.Label { text: "Updated"; font.pixelSize: 13; opacity: 0.5 }
                    PC3.Label { text: svc.updated || "-"; font.pixelSize: 16; opacity: 0.85 }
                }

                ColumnLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignTop
                    PC3.Label { text: "Expires In"; font.pixelSize: 13; opacity: 0.5 }
                    PC3.Label {
                        text: tab.expiry.text
                        font.pixelSize: 16; font.bold: true
                        color: tab.expiry.level === "expired" ? "#e74c3c"
                             : tab.expiry.level === "soon"    ? "#f39c12"
                             : Kirigami.Theme.textColor
                    }
                    PC3.Label {
                        visible: tab.expiry.line !== ""
                        text: tab.expiry.line
                        font.pixelSize: 12
                        opacity: 0.7
                    }
                }
            }
        }
    }
}

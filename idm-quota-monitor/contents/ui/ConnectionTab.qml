import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami

Item {
    // ── Public API ────────────────────────────────────────────────────────
    property var    data_:    ({ percent: 0, remaining: "", updated: "", error: "" })
    property var    history:  []
    property bool   loading:  false
    property color  pctColor: "#2ecc71"

    onLoadingChanged:  { gauge.requestPaint(); chart.requestPaint() }
    onPctColorChanged: { gauge.requestPaint(); chart.requestPaint() }

    // ── Layout ────────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing * 2
        spacing: Kirigami.Units.smallSpacing

        // ── Gauge row ─────────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing

            // Arc gauge
            Canvas {
                id: gauge
                width:  110
                height: 110
                Layout.alignment: Qt.AlignVCenter

                property real pct: data_.error ? 0 : (data_.percent || 0)

                Behavior on pct { NumberAnimation { duration: 600; easing.type: Easing.InOutQuad } }

                onPctChanged: requestPaint()
                Component.onCompleted: requestPaint()

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)

                    var cx = width  / 2
                    var cy = height / 2
                    var r  = Math.min(cx, cy) - 8
                    var startAngle = Math.PI * 0.75          // 135°
                    var fullSweep  = Math.PI * 1.5           // 270°
                    var endAngle   = startAngle + fullSweep * (pct / 100)

                    // Track
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, startAngle, startAngle + fullSweep)
                    ctx.lineWidth   = 10
                    ctx.strokeStyle = Qt.rgba(Kirigami.Theme.textColor.r,
                                             Kirigami.Theme.textColor.g,
                                             Kirigami.Theme.textColor.b, 0.12)
                    ctx.lineCap = "round"
                    ctx.stroke()

                    // Filled arc
                    if (pct > 0) {
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, startAngle, endAngle)
                        ctx.lineWidth   = 10
                        ctx.strokeStyle = pctColor
                        ctx.lineCap     = "round"
                        ctx.stroke()
                    }

                    // Center text
                    ctx.fillStyle = loading
                        ? Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.4)
                        : data_.error ? "#e74c3c" : pctColor
                    ctx.font          = "bold 20px sans-serif"
                    ctx.textAlign     = "center"
                    ctx.textBaseline  = "middle"
                    ctx.fillText(
                        loading      ? "…"
                        : data_.error ? "ERR"
                        : pct.toFixed(1) + "%",
                        cx, cy - 6
                    )

                    ctx.fillStyle    = Qt.rgba(Kirigami.Theme.textColor.r,
                                              Kirigami.Theme.textColor.g,
                                              Kirigami.Theme.textColor.b, 0.5)
                    ctx.font         = "11px sans-serif"
                    ctx.fillText("used", cx, cy + 14)
                }

                // Repaint when theme or color changes
                Connections {
                    target: Kirigami.Theme
                    function onTextColorChanged() { gauge.requestPaint() }
                }
            }

            // Stats column
            ColumnLayout {
                Layout.preferredWidth: 120
                Layout.alignment: Qt.AlignVCenter
                spacing: 4

                PC3.Label {
                    text: "Remaining"
                    font.pixelSize: 10
                    opacity: 0.5
                }
                PC3.Label {
                    text: loading          ? "Loading…"
                        : data_.error      ? data_.error
                        : data_.remaining  ? data_.remaining
                        : "—"
                    font.pixelSize: 15
                    font.bold: true
                    color: data_.error ? "#e74c3c" : Kirigami.Theme.textColor
                    wrapMode: Text.WordWrap
                }

                Item { height: 4 }

                PC3.Label {
                    text: "Updated"
                    font.pixelSize: 10
                    opacity: 0.5
                }
                PC3.Label {
                    text: data_.updated ? data_.updated : "—"
                    font.pixelSize: 12
                    opacity: 0.8
                }
            }

            // Logo fills the empty space to the right of the stats
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Image {
                    anchors.centerIn: parent
                    source: Qt.resolvedUrl("../images/logo.png")
                    fillMode: Image.PreserveAspectFit
                    width: Math.min(parent.width - Kirigami.Units.largeSpacing * 2, 180)
                    height: 90
                    opacity: 0.8
                }
            }
        }

        // ── Separator ─────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Kirigami.Theme.separatorColor
            opacity: 0.5
        }

        // ── History chart ─────────────────────────────────────────────────
        PC3.Label {
            text: "24h usage history"
            font.pixelSize: 10
            opacity: 0.5
        }

        Canvas {
            id: chart
            Layout.fillWidth:  true
            Layout.fillHeight: true
            Layout.minimumHeight: 70

            onWidthChanged:  requestPaint()
            onHeightChanged: requestPaint()

            property var pts: history

            onPtsChanged: requestPaint()
            Component.onCompleted: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)

                var data = pts
                if (!data || data.length < 2) {
                    ctx.fillStyle = Qt.rgba(Kirigami.Theme.textColor.r,
                                            Kirigami.Theme.textColor.g,
                                            Kirigami.Theme.textColor.b, 0.25)
                    ctx.font         = "11px sans-serif"
                    ctx.textAlign    = "center"
                    ctx.textBaseline = "middle"
                    ctx.fillText("No history yet", width / 2, height / 2)
                    return
                }

                var pad   = { top: 6, right: 6, bottom: 18, left: 32 }
                var cw    = width  - pad.left - pad.right
                var ch    = height - pad.top  - pad.bottom

                // Y axis: 0–100 % with a bit of padding
                var minV = 0, maxV = 100

                // ── Grid lines ────────────────────────────────────────────
                ctx.lineWidth   = 0.5
                ctx.strokeStyle = Qt.rgba(Kirigami.Theme.textColor.r,
                                         Kirigami.Theme.textColor.g,
                                         Kirigami.Theme.textColor.b, 0.1)
                ctx.fillStyle   = Qt.rgba(Kirigami.Theme.textColor.r,
                                         Kirigami.Theme.textColor.g,
                                         Kirigami.Theme.textColor.b, 0.35)
                ctx.font        = "9px sans-serif"
                ctx.textAlign   = "right"
                ctx.textBaseline = "middle"

                var gridLines = [0, 25, 50, 75, 100]
                for (var g = 0; g < gridLines.length; g++) {
                    var gv = gridLines[g]
                    var gy = pad.top + ch - (gv / 100) * ch
                    ctx.beginPath()
                    ctx.moveTo(pad.left, gy)
                    ctx.lineTo(pad.left + cw, gy)
                    ctx.stroke()
                    ctx.fillText(gv + "%", pad.left - 3, gy)
                }

                // ── Filled area ───────────────────────────────────────────
                var n = data.length

                function xPos(i) { return pad.left + (i / (n - 1)) * cw }
                function yPos(v) { return pad.top  + ch - ((v - minV) / (maxV - minV)) * ch }

                // Gradient fill
                var grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + ch)
                grad.addColorStop(0, Qt.rgba(pctColor.r, pctColor.g, pctColor.b, 0.35))
                grad.addColorStop(1, Qt.rgba(pctColor.r, pctColor.g, pctColor.b, 0.02))

                ctx.beginPath()
                ctx.moveTo(xPos(0), yPos(data[0].pct))
                for (var i = 1; i < n; i++) {
                    // Smooth curve using cardinal spline control points
                    var x0 = xPos(i - 1), y0 = yPos(data[i-1].pct)
                    var x1 = xPos(i),     y1 = yPos(data[i].pct)
                    var cpx = (x0 + x1) / 2
                    ctx.bezierCurveTo(cpx, y0, cpx, y1, x1, y1)
                }
                ctx.lineTo(xPos(n - 1), pad.top + ch)
                ctx.lineTo(xPos(0),     pad.top + ch)
                ctx.closePath()
                ctx.fillStyle = grad
                ctx.fill()

                // Line
                ctx.beginPath()
                ctx.moveTo(xPos(0), yPos(data[0].pct))
                for (var j = 1; j < n; j++) {
                    var ax = xPos(j - 1), ay = yPos(data[j-1].pct)
                    var bx = xPos(j),     by = yPos(data[j].pct)
                    var mc = (ax + bx) / 2
                    ctx.bezierCurveTo(mc, ay, mc, by, bx, by)
                }
                ctx.lineWidth   = 2
                ctx.strokeStyle = pctColor
                ctx.lineJoin    = "round"
                ctx.stroke()

                // Latest dot
                var lx = xPos(n - 1)
                var ly = yPos(data[n - 1].pct)
                ctx.beginPath()
                ctx.arc(lx, ly, 3.5, 0, Math.PI * 2)
                ctx.fillStyle = pctColor
                ctx.fill()

                // ── X-axis time labels ────────────────────────────────────
                ctx.fillStyle    = Qt.rgba(Kirigami.Theme.textColor.r,
                                           Kirigami.Theme.textColor.g,
                                           Kirigami.Theme.textColor.b, 0.4)
                ctx.font         = "9px sans-serif"
                ctx.textAlign    = "center"
                ctx.textBaseline = "top"

                // Show ~4 evenly-spaced time labels
                var labelCount = Math.min(4, n)
                for (var k = 0; k < labelCount; k++) {
                    var idx = Math.round(k * (n - 1) / (labelCount - 1))
                    ctx.fillText(data[idx].t, xPos(idx), pad.top + ch + 4)
                }
            }

            Connections {
                target: Kirigami.Theme
                function onTextColorChanged() { chart.requestPaint() }
            }
        }
    }
}

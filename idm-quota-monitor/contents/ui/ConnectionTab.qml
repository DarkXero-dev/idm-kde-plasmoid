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
            Layout.fillHeight: false
            Layout.preferredHeight: 155
            Layout.alignment: Qt.AlignVCenter
            spacing: 48

            // Gauge + stats grouped tightly together
            RowLayout {
                spacing: 16
                Layout.alignment: Qt.AlignVCenter

            // Arc gauge
            Canvas {
                id: gauge
                width:  150
                height: 150
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
                    ctx.font          = "bold 22px sans-serif"
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
                    ctx.font         = "12px sans-serif"
                    ctx.fillText("used", cx, cy + 15)
                }

                // Repaint when theme or color changes
                Connections {
                    target: Kirigami.Theme
                    function onTextColorChanged() { gauge.requestPaint() }
                }
            }

            // Stats column
            ColumnLayout {
                Layout.preferredWidth: 160
                Layout.alignment: Qt.AlignVCenter
                spacing: 6

                PC3.Label {
                    text: "Remaining"
                    font.pixelSize: 13
                    opacity: 0.5
                }
                PC3.Label {
                    text: loading          ? "Loading…"
                        : data_.error      ? data_.error
                        : data_.remaining  ? data_.remaining
                        : "—"
                    font.pixelSize: 14
                    font.bold: true
                    color: data_.error ? "#e74c3c" : Kirigami.Theme.textColor
                    wrapMode: Text.WordWrap
                }

                Item { height: 6 }

                PC3.Label {
                    text: "Updated"
                    font.pixelSize: 13
                    opacity: 0.5
                }
                PC3.Label {
                    text: data_.updated ? data_.updated : "—"
                    font.pixelSize: 16
                    opacity: 0.8
                }
            }

            } // end gauge+stats RowLayout

            // "Current Provider" fills the space between gauge and logo
            Canvas {
                id: cpLabel
                Layout.fillWidth: true
                Layout.fillHeight: true

                Component.onCompleted: requestPaint()
                onWidthChanged:  requestPaint()
                onHeightChanged: requestPaint()

                Connections {
                    target: orbitronFont
                    function onStatusChanged() { cpLabel.requestPaint() }
                }

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)

                    var grad = ctx.createLinearGradient(0, 0, width, 0)
                    grad.addColorStop(0,   "#3b82f6")
                    grad.addColorStop(1,   "#ef4444")

                    ctx.fillStyle   = grad
                    ctx.globalAlpha = 0.30
                    ctx.font         = "bold 36px '" + orbitronFont.name + "'"
                    ctx.textAlign    = "left"
                    ctx.textBaseline = "middle"
                    ctx.fillText("CURRENT",  20, height / 2 - 22)
                    ctx.fillText("PROVIDER", 20, height / 2 + 22)
                }
            }

            // Logo pinned to right edge
            Image {
                source: Qt.resolvedUrl("../images/logo.png")
                fillMode: Image.PreserveAspectFit
                width:  220
                height: 110
                sourceSize.width:  220
                sourceSize.height: 110
                opacity: 0.8
                Layout.alignment: Qt.AlignVCenter
            }
        }

        // ── Separator ─────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Kirigami.Theme.separatorColor
            opacity: 0.5
        }

        // ── Network animation ──────────────────────────────────────────────
        FontLoader {
            id: orbitronFont
            source: Qt.resolvedUrl("../fonts/Orbitron_Bold.ttf")
        }

        Canvas {
            id: netAnim
            Layout.fillWidth:  true
            Layout.fillHeight: true
            Layout.minimumHeight: 100

            property real tick: 0
            readonly property color nc: "#a855f7"   // purple

            Timer {
                interval: 32
                running:  true
                repeat:   true
                onTriggered: { netAnim.tick += 0.016; netAnim.requestPaint() }
            }

            // HSL (h:0-360, s:0-1, l:0-1) → Qt.rgba
            function hsl(h, s, l, a) {
                h = ((h % 360) + 360) % 360 / 360
                var q = l < 0.5 ? l * (1 + s) : l + s - l * s
                var p = 2 * l - q
                function hue2rgb(t) {
                    if (t < 0) t += 1; if (t > 1) t -= 1
                    if (t < 1/6) return p + (q - p) * 6 * t
                    if (t < 1/2) return q
                    if (t < 2/3) return p + (q - p) * (2/3 - t) * 6
                    return p
                }
                return Qt.rgba(hue2rgb(h + 1/3), hue2rgb(h), hue2rgb(h - 1/3), a)
            }

            // Draw one server rack centered at (cx, cy)
            function drawRack(ctx, cx, cy, phase) {
                var sw = 26, sh = Math.min(height * 0.72, 64)
                var sx = cx - sw / 2
                var sy = cy - sh / 2
                var units = 4
                var pulse = 0.5 + 0.5 * Math.sin(tick * 2.0 + phase)

                // Body fill
                ctx.fillStyle = Qt.rgba(nc.r, nc.g, nc.b, 0.10)
                ctx.fillRect(sx, sy, sw, sh)

                // Body border
                ctx.lineWidth   = 1.5
                ctx.strokeStyle = Qt.rgba(nc.r, nc.g, nc.b, 0.45 + pulse * 0.25)
                ctx.strokeRect(sx, sy, sw, sh)

                // Unit divider lines
                for (var u = 1; u < units; u++) {
                    var uy = sy + (sh / units) * u
                    ctx.beginPath()
                    ctx.moveTo(sx + 2, uy)
                    ctx.lineTo(sx + sw - 2, uy)
                    ctx.lineWidth   = 0.5
                    ctx.strokeStyle = Qt.rgba(nc.r, nc.g, nc.b, 0.22)
                    ctx.stroke()
                }

                // LEDs — one per unit, staggered pulse
                for (var l = 0; l < units; l++) {
                    var ledX  = sx + sw - 6
                    var ledY  = sy + (sh / units) * l + (sh / units) / 2
                    var lp    = 0.5 + 0.5 * Math.sin(tick * 3.5 + l * 1.4 + phase)

                    // LED glow
                    var g = ctx.createRadialGradient(ledX, ledY, 0, ledX, ledY, 6)
                    g.addColorStop(0, Qt.rgba(0.18, 1.0, 0.42, 0.55 * lp))
                    g.addColorStop(1, Qt.rgba(0.18, 1.0, 0.42, 0))
                    ctx.beginPath()
                    ctx.arc(ledX, ledY, 6, 0, Math.PI * 2)
                    ctx.fillStyle = g
                    ctx.fill()

                    // LED dot
                    ctx.beginPath()
                    ctx.arc(ledX, ledY, 2, 0, Math.PI * 2)
                    ctx.fillStyle = Qt.rgba(0.18, 1.0, 0.42, 0.4 + lp * 0.6)
                    ctx.fill()
                }
            }

            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)

                var w = width, h = height
                var cx = w / 2, cy = h / 2

                // Server x positions
                var lx = 22, rx = w - 22

                // ── Draw racks ────────────────────────────────────────────
                drawRack(ctx, lx, cy, 0.0)
                drawRack(ctx, rx, cy, 1.8)

                // ── Network nodes between servers ─────────────────────────
                var nds = [
                    { x: cx * 0.62, y: cy * 0.45 },
                    { x: cx,        y: cy * 1.55  },
                    { x: cx * 1.38, y: cy * 0.45  }
                ]

                // ── Edges ─────────────────────────────────────────────────
                var eds = [
                    { a: { x: lx, y: cy }, b: nds[0], s: 0.16 },
                    { a: { x: lx, y: cy }, b: nds[1], s: 0.12 },
                    { a: nds[0],           b: nds[1],  s: 0.10 },
                    { a: nds[0],           b: nds[2],  s: 0.18 },
                    { a: nds[1],           b: nds[2],  s: 0.14 },
                    { a: nds[2],           b: { x: rx, y: cy }, s: 0.17 },
                    { a: nds[1],           b: { x: rx, y: cy }, s: 0.13 }
                ]

                // Draw edge lines
                for (var e = 0; e < eds.length; e++) {
                    ctx.beginPath()
                    ctx.moveTo(eds[e].a.x, eds[e].a.y)
                    ctx.lineTo(eds[e].b.x, eds[e].b.y)
                    ctx.lineWidth   = 1
                    ctx.strokeStyle = Qt.rgba(nc.r, nc.g, nc.b, 0.20)
                    ctx.stroke()
                }

                // Draw packets
                for (var p = 0; p < eds.length; p++) {
                    for (var pass = 0; pass < 2; pass++) {
                        var t  = ((tick * eds[p].s) + pass * 0.5) % 1.0
                        var px = eds[p].a.x + (eds[p].b.x - eds[p].a.x) * t
                        var py = eds[p].a.y + (eds[p].b.y - eds[p].a.y) * t
                        ctx.beginPath()
                        ctx.arc(px, py, 2, 0, Math.PI * 2)
                        ctx.fillStyle = Qt.rgba(nc.r, nc.g, nc.b, 0.45 + 0.55 * Math.sin(t * Math.PI))
                        ctx.fill()
                    }
                }

                // Draw nodes
                for (var n = 0; n < nds.length; n++) {
                    var nd  = nds[n]
                    var pls = 0.5 + 0.5 * Math.sin(tick * 1.8 + n * 1.2)
                    var gr  = ctx.createRadialGradient(nd.x, nd.y, 0, nd.x, nd.y, 9 + pls * 5)
                    gr.addColorStop(0, Qt.rgba(nc.r, nc.g, nc.b, 0.38 + pls * 0.18))
                    gr.addColorStop(1, Qt.rgba(nc.r, nc.g, nc.b, 0))
                    ctx.beginPath()
                    ctx.arc(nd.x, nd.y, 9 + pls * 5, 0, Math.PI * 2)
                    ctx.fillStyle = gr
                    ctx.fill()
                    ctx.beginPath()
                    ctx.arc(nd.x, nd.y, 3, 0, Math.PI * 2)
                    ctx.fillStyle = Qt.rgba(nc.r, nc.g, nc.b, 0.9)
                    ctx.fill()
                }

                // ── XeroLinux watermark — RGB cycling gradient ────────────
                var wRaw    = 0.5 + 0.5 * Math.sin(tick * 0.9)
                var wEased  = wRaw < 0.5
                              ? 4 * wRaw * wRaw * wRaw
                              : 1 - Math.pow(-2 * wRaw + 2, 3) / 2
                var hueBase = (tick * 35) % 360
                var fAlpha  = 0.09 + wEased * 0.07

                var grad = ctx.createLinearGradient(0, 0, w, 0)
                grad.addColorStop(0.00, hsl(hueBase +   0, 0.95, 0.65, fAlpha))
                grad.addColorStop(0.25, hsl(hueBase +  90, 0.95, 0.65, fAlpha))
                grad.addColorStop(0.50, hsl(hueBase + 180, 0.95, 0.65, fAlpha))
                grad.addColorStop(0.75, hsl(hueBase + 270, 0.95, 0.65, fAlpha))
                grad.addColorStop(1.00, hsl(hueBase + 360, 0.95, 0.65, fAlpha))

                ctx.font         = "bold " + Math.round(h * 0.38) + "px '" + orbitronFont.name + "'"
                ctx.textAlign    = "center"
                ctx.textBaseline = "middle"
                ctx.shadowColor  = hsl(hueBase + 180, 1.0, 0.65, 0.5 * wEased)
                ctx.shadowBlur   = wEased * 14
                ctx.fillStyle    = grad
                ctx.fillText("XeroLinux", cx, cy)
                ctx.shadowBlur   = 0
                ctx.shadowColor  = "transparent"
            }
        }
    }
}

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import "util.js" as Util

// Popup: 1 to 3 service cards, logo between when exactly two
Item {
    id: popup

    property var    shown: []
    property var    names: ({})
    property string gaugeStyle: "speedometer"
    property bool   loading: false
    property bool   configured: true
    property string fetchError: ""
    property bool   active: true

    signal settingsRequested()
    signal speedTestRequested()
    signal refreshRequested()

    Layout.preferredWidth:  popup.shown.length <= 1 ? 420 : popup.shown.length === 2 ? 958 : 1150
    Layout.preferredHeight: mainColumn.implicitHeight + Kirigami.Units.smallSpacing * 2
    Layout.minimumHeight:   Layout.preferredHeight

    ColumnLayout {
        id: mainColumn
        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        spacing: 0

        RowLayout {
            visible: popup.shown.length > 0
            Layout.fillWidth:  true
            Layout.fillHeight: true
            spacing: 0

            ConnectionTab {
                Layout.fillWidth:  true
                Layout.fillHeight: true
                svc:        popup.shown[0] || ({})
                alias:      popup.shown[0] ? (popup.names[popup.shown[0].id] || "") : ""
                loading:    popup.loading
                gaugeStyle: popup.gaugeStyle
            }

            Image {
                visible: popup.shown.length === 2
                Layout.alignment: Qt.AlignVCenter
                source: Qt.resolvedUrl("../images/logo.png")
                fillMode: Image.PreserveAspectFit
                Layout.preferredWidth:  230
                Layout.preferredHeight: 115
                sourceSize.width:  230
                sourceSize.height: 115
                opacity: 0.85
            }

            ConnectionTab {
                visible: popup.shown.length >= 2
                Layout.fillWidth:  true
                Layout.fillHeight: true
                svc:        popup.shown[1] || ({})
                alias:      popup.shown[1] ? (popup.names[popup.shown[1].id] || "") : ""
                loading:    popup.loading
                gaugeStyle: popup.gaugeStyle
            }

            ConnectionTab {
                visible: popup.shown.length >= 3
                Layout.fillWidth:  true
                Layout.fillHeight: true
                svc:        popup.shown[2] || ({})
                alias:      popup.shown[2] ? (popup.names[popup.shown[2].id] || "") : ""
                loading:    popup.loading
                gaugeStyle: popup.gaugeStyle
            }
        }

        PC3.Label {
            visible: popup.shown.length === 0
            Layout.fillWidth:  true
            Layout.fillHeight: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment:   Text.AlignVCenter
            wrapMode: Text.WordWrap
            font.pixelSize: 15
            opacity: 0.7
            color: popup.fetchError !== "" ? "#e74c3c" : Kirigami.Theme.textColor
            text: !popup.configured       ? "Open Settings and enter your IDM login."
                : popup.loading           ? "Loading…"
                : popup.fetchError !== "" ? popup.fetchError
                : "No services selected. Open Settings and tick the services to show."
        }

        // ── Footer ────────────────────────────────────────────────────
        Canvas {
            id: eolBar
            Layout.fillWidth: true
            height: 38

            property real tick: 0

            Timer {
                interval: 50
                running: popup.active
                repeat: true
                onTriggered: { eolBar.tick += 0.025; eolBar.requestPaint() }
            }

            function hsl(h, s, l, a) {
                h = ((h % 360) + 360) % 360 / 360
                var q = l < 0.5 ? l*(1+s) : l+s-l*s
                var p = 2*l - q
                function c(t) {
                    if (t<0) t+=1; if (t>1) t-=1
                    if (t<1/6) return p+(q-p)*6*t
                    if (t<1/2) return q
                    if (t<2/3) return p+(q-p)*(2/3-t)*6
                    return p
                }
                return Qt.rgba(c(h+1/3), c(h), c(h-1/3), a)
            }

            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)

                var cx      = width / 2
                var cy      = height / 2
                var hueBase = (tick * 40) % 360
                var pulse   = 0.5 + 0.5 * Math.sin(tick * 1.8)
                var text    = "~~~~~~~~~~~~  End Of Line  ~~~~~~~~~~~~"

                ctx.font         = "bold 19px sans-serif"
                ctx.textAlign    = "center"
                ctx.textBaseline = "middle"

                for (var g = 3; g >= 1; g--) {
                    ctx.shadowColor = hsl(hueBase + 180, 1.0, 0.65, 0.6 * pulse)
                    ctx.shadowBlur  = g * 11
                    var grad = ctx.createLinearGradient(0, 0, width, 0)
                    grad.addColorStop(0.00, hsl(hueBase +   0, 0.95, 0.65, 0.15))
                    grad.addColorStop(0.25, hsl(hueBase +  90, 0.95, 0.65, 0.15))
                    grad.addColorStop(0.50, hsl(hueBase + 180, 0.95, 0.65, 0.15))
                    grad.addColorStop(0.75, hsl(hueBase + 270, 0.95, 0.65, 0.15))
                    grad.addColorStop(1.00, hsl(hueBase + 360, 0.95, 0.65, 0.15))
                    ctx.fillStyle = grad
                    ctx.fillText(text, cx, cy)
                }

                ctx.shadowBlur  = 14 * pulse
                ctx.shadowColor = hsl(hueBase + 180, 1.0, 0.65, 0.7 * pulse)
                var mainGrad = ctx.createLinearGradient(0, 0, width, 0)
                mainGrad.addColorStop(0.00, hsl(hueBase +   0, 0.95, 0.70, 0.85))
                mainGrad.addColorStop(0.25, hsl(hueBase +  90, 0.95, 0.70, 0.85))
                mainGrad.addColorStop(0.50, hsl(hueBase + 180, 0.95, 0.70, 0.85))
                mainGrad.addColorStop(0.75, hsl(hueBase + 270, 0.95, 0.70, 0.85))
                mainGrad.addColorStop(1.00, hsl(hueBase + 360, 0.95, 0.70, 0.85))
                ctx.fillStyle = mainGrad
                ctx.fillText(text, cx, cy)
                ctx.shadowBlur  = 0
                ctx.shadowColor = "transparent"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing

            PC3.Button {
                text: "Settings"
                icon.name: "configure"
                onClicked: popup.settingsRequested()
            }

            PC3.Button {
                text: "Speed Test"
                icon.name: "utilities-system-monitor"
                onClicked: popup.speedTestRequested()
            }

            Item { Layout.fillWidth: true }

            PC3.Button {
                text: popup.loading ? "Loading…" : "Refresh"
                icon.name: "view-refresh"
                enabled: !popup.loading && popup.configured
                onClicked: popup.refreshRequested()
            }
        }
    }

    Image {
        visible: popup.shown.length === 3
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: Kirigami.Units.largeSpacing
        source: Qt.resolvedUrl("../images/logo.png")
        fillMode: Image.PreserveAspectFit
        width: 56
        height: 28
        sourceSize.width:  112
        sourceSize.height: 56
        opacity: 0.85
    }
}

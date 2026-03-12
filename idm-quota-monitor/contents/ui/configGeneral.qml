import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    id: root

    property alias cfg_username:          usernameField.text
    property alias cfg_password:          passwordField.text
    property string cfg_connectionChoice: "adsl"

    Kirigami.FormLayout {
        anchors.fill: parent

        QQC2.TextField {
            id: usernameField
            Kirigami.FormData.label: "Username:"
            placeholderText: "IDM account username"
        }

        QQC2.TextField {
            id: passwordField
            Kirigami.FormData.label: "Password:"
            echoMode: TextInput.Password
            placeholderText: "IDM account password"
        }

        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: "Connection"
        }

        QQC2.ComboBox {
            id: connectionCombo
            Kirigami.FormData.label: "Show:"
            model: [
                { text: "ADSL", value: "adsl" },
                { text: "LTE",  value: "lte"  }
            ]
            textRole: "text"
            valueRole: "value"
            Component.onCompleted: currentIndex = (cfg_connectionChoice === "lte" ? 1 : 0)
            onActivated: cfg_connectionChoice = currentValue
        }
    }
}

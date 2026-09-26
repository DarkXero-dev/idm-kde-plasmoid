.pragma library

function toHex(str) {
    var enc = encodeURIComponent(str)
    var hex = ""
    for (var i = 0; i < enc.length; i++) {
        if (enc[i] === "%") {
            hex += enc.substr(i + 1, 2).toLowerCase()
            i += 2
        } else {
            hex += enc.charCodeAt(i).toString(16).padStart(2, "0")
        }
    }
    return hex
}

function typeLabel(type) {
    return type === "adsl" ? "ADSL"
         : type === "lte" ? "LTE"
         : type === "fiber" ? "FIBER"
         : "SERVICE"
}

var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

function pad(n) {
    return n < 10 ? "0" + n : "" + n
}

function pctColor(pct) {
    return pct >= 90 ? "#e74c3c" : pct >= 70 ? "#f39c12" : "#2ecc71"
}

function expiryState(iso, now) {
    var m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?$/.exec(iso || "")
    if (!m)
        return { text: "-", line: "", level: "ok" }
    var hasTime = m[4] !== undefined
    var y = +m[1], mo = +m[2] - 1, d = +m[3]
    var hh = hasTime ? +m[4] : 0, mm = hasTime ? +m[5] : 0
    var clock = pad(hh) + ":" + pad(mm)
    var line = d + " " + MONTHS[mo] + " " + y + (hasTime ? " " + clock : "")
    var days = Math.round((new Date(y, mo, d) - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 86400000)
    var expired = hasTime ? new Date(y, mo, d, hh, mm) <= now : days < 0
    if (expired)
        return { text: "Expired", line: line, level: "expired" }
    var text = days === 0 ? (hasTime ? "Today " + clock : "Today") : days + (days === 1 ? " day" : " days")
    return { text: text, line: line, level: days <= 5 ? "soon" : "ok" }
}

function displayName(svc, names) {
    return (svc && (names[svc.id] || svc.name)) || ""
}

var SPEED_SCALE = [0, 5, 10, 25, 50, 100, 250, 500, 1000]

function speedFraction(mbps) {
    if (!mbps || mbps <= 0)
        return 0
    if (mbps >= SPEED_SCALE[SPEED_SCALE.length - 1])
        return 1
    for (var i = 0; i < SPEED_SCALE.length - 1; i++) {
        if (mbps < SPEED_SCALE[i + 1])
            return (i + (mbps - SPEED_SCALE[i]) / (SPEED_SCALE[i + 1] - SPEED_SCALE[i])) / (SPEED_SCALE.length - 1)
    }
}

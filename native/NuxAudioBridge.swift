import AppKit
import ApplicationServices
import Foundation
import ScreenCaptureKit

let bundleIdentifier = "com.nux.audio"

struct Doctor: Codable {
    let accessibilityTrusted: Bool
    let appRunning: Bool
    let windowCount: Int
    let bundleIdentifier: String
}

struct Node: Codable {
    let index: Int
    let role: String
    let title: String
    let description: String
    let value: String
    let identifier: String
    let help: String
    let x: Double
    let y: Double
    let width: Double
    let height: Double
    let actions: [String]
    let selected: Bool?
    let enabled: Bool?
}

struct Snapshot: Codable { let nodes: [Node] }
struct Result: Codable { let ok: Bool; let message: String? }
struct ColorSample: Codable {
    let red: Double
    let green: Double
    let blue: Double
    let alpha: Double
}

enum BridgeFailure: Error, CustomStringConvertible {
    case message(String)
    var description: String {
        switch self { case .message(let text): return text }
    }
}

func emit<T: Encodable>(_ value: T) throws {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    FileHandle.standardOutput.write(try encoder.encode(value))
    FileHandle.standardOutput.write(Data([0x0A]))
}

func app() -> NSRunningApplication? {
    NSRunningApplication.runningApplications(withBundleIdentifier: bundleIdentifier).first
}

func copyAttribute(_ element: AXUIElement, _ name: String) -> AnyObject? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success else { return nil }
    return value
}

func stringAttribute(_ element: AXUIElement, _ name: String) -> String {
    guard let value = copyAttribute(element, name) else { return "" }
    if let string = value as? String { return string }
    if let number = value as? NSNumber { return number.stringValue }
    return String(describing: value)
}

func boolAttribute(_ element: AXUIElement, _ name: String) -> Bool? {
    guard let value = copyAttribute(element, name) else { return nil }
    if let number = value as? NSNumber { return number.boolValue }
    return nil
}

func pointAttribute(_ element: AXUIElement, _ name: String) -> CGPoint {
    guard let raw = copyAttribute(element, name), CFGetTypeID(raw) == AXValueGetTypeID() else { return .zero }
    var result = CGPoint.zero
    AXValueGetValue(raw as! AXValue, .cgPoint, &result)
    return result
}

func sizeAttribute(_ element: AXUIElement, _ name: String) -> CGSize {
    guard let raw = copyAttribute(element, name), CFGetTypeID(raw) == AXValueGetTypeID() else { return .zero }
    var result = CGSize.zero
    AXValueGetValue(raw as! AXValue, .cgSize, &result)
    return result
}

func children(_ element: AXUIElement) -> [AXUIElement] {
    let attributes = [kAXChildrenAttribute, "AXVisibleChildren", "AXChildrenInNavigationOrder", "AXContents"]
    var output: [AXUIElement] = []
    var seen = Set<CFHashCode>()
    for attribute in attributes {
        guard let values = copyAttribute(element, attribute) as? [AXUIElement] else { continue }
        for child in values {
            let key = CFHash(child)
            if seen.insert(key).inserted { output.append(child) }
        }
    }
    return output
}

func rootElement() throws -> AXUIElement {
    guard AXIsProcessTrusted() else { throw BridgeFailure.message("Accessibility permission is required") }
    guard let running = app() else { throw BridgeFailure.message("NUX Audio is not running") }
    let application = AXUIElementCreateApplication(running.processIdentifier)
    guard let windows = copyAttribute(application, kAXWindowsAttribute) as? [AXUIElement],
          let window = windows.max(by: { left, right in
              let a = sizeAttribute(left, kAXSizeAttribute)
              let b = sizeAttribute(right, kAXSizeAttribute)
              return a.width * a.height < b.width * b.height
          }) else {
        throw BridgeFailure.message("NUX Audio window not found")
    }
    return window
}

func flattenedElements() throws -> [AXUIElement] {
    let root = try rootElement()
    var result: [AXUIElement] = []
    var seen = Set<CFHashCode>()
    func visit(_ element: AXUIElement, depth: Int) {
        guard depth <= 30 else { return }
        let key = CFHash(element)
        guard seen.insert(key).inserted else { return }
        result.append(element)
        for child in children(element) { visit(child, depth: depth + 1) }
    }
    visit(root, depth: 0)
    return result
}

func snapshot() throws -> Snapshot {
    let elements = try flattenedElements()
    let nodes = elements.enumerated().map { index, element -> Node in
        let point = pointAttribute(element, kAXPositionAttribute)
        let size = sizeAttribute(element, kAXSizeAttribute)
        let title = stringAttribute(element, kAXTitleAttribute)
        let rawDescription = stringAttribute(element, kAXDescriptionAttribute)
        let description = rawDescription == title ? "" : rawDescription
        var names: CFArray?
        AXUIElementCopyActionNames(element, &names)
        return Node(
            index: index,
            role: stringAttribute(element, kAXRoleAttribute),
            title: title,
            description: description,
            value: stringAttribute(element, kAXValueAttribute),
            identifier: stringAttribute(element, kAXIdentifierAttribute),
            help: stringAttribute(element, kAXHelpAttribute),
            x: point.x, y: point.y, width: size.width, height: size.height,
            actions: (names as? [String]) ?? [],
            selected: boolAttribute(element, kAXSelectedAttribute),
            enabled: boolAttribute(element, kAXEnabledAttribute)
        )
    }
    return Snapshot(nodes: nodes)
}

func element(at text: String) throws -> AXUIElement {
    guard let index = Int(text) else { throw BridgeFailure.message("invalid element index") }
    let elements = try flattenedElements()
    guard elements.indices.contains(index) else { throw BridgeFailure.message("element index out of range") }
    return elements[index]
}

func normalized(_ text: String) -> String {
    text.lowercased().filter { $0.isLetter || $0.isNumber }
}

func element(labeled label: String) throws -> AXUIElement {
    let wanted = normalized(label)
    for attempt in 0..<4 {
        let elements = try flattenedElements()
        let matches = elements.filter { element in
            let text = [
                stringAttribute(element, kAXTitleAttribute),
                stringAttribute(element, kAXDescriptionAttribute),
                stringAttribute(element, kAXValueAttribute),
            ].joined(separator: " ")
            return normalized(text).contains(wanted)
        }
        if let result = matches.min(by: { left, right in
            let l = stringAttribute(left, kAXTitleAttribute).count + stringAttribute(left, kAXDescriptionAttribute).count + stringAttribute(left, kAXValueAttribute).count
            let r = stringAttribute(right, kAXTitleAttribute).count + stringAttribute(right, kAXDescriptionAttribute).count + stringAttribute(right, kAXValueAttribute).count
            return l < r
        }) { return result }
        if attempt < 3 { usleep(120_000) }
    }
    throw BridgeFailure.message("labeled element not found: \(label)")
}

func stabilizedSnapshot() throws -> Snapshot {
    var best = try snapshot()
    for _ in 0..<3 {
        usleep(100_000)
        let candidate = try snapshot()
        if candidate.nodes.count > best.nodes.count { best = candidate }
    }
    return best
}

func click(at point: CGPoint, button: CGMouseButton = .left) throws {
    let downType: CGEventType = button == .right ? .rightMouseDown : .leftMouseDown
    let upType: CGEventType = button == .right ? .rightMouseUp : .leftMouseUp
    guard let down = CGEvent(mouseEventSource: nil, mouseType: downType, mouseCursorPosition: point, mouseButton: button),
          let up = CGEvent(mouseEventSource: nil, mouseType: upType, mouseCursorPosition: point, mouseButton: button) else {
        throw BridgeFailure.message("could not create mouse event")
    }
    CGWarpMouseCursorPosition(point)
    usleep(button == .right ? 120_000 : 20_000)
    down.post(tap: .cghidEventTap)
    usleep(button == .right ? 100_000 : 40_000)
    up.post(tap: .cghidEventTap)
    if button == .right { usleep(120_000) }
}

func scroll(at point: CGPoint, delta: Int, count: Int) throws {
    guard count >= 1 && count <= 100 else { throw BridgeFailure.message("scroll count must be 1-100") }
    CGWarpMouseCursorPosition(point)
    for _ in 0..<count {
        // The Flutter control sometimes consumes only the first event of a
        // sustained burst, especially after reaching a bound. Re-entering the
        // hit-test point makes every event an independent wheel gesture.
        CGWarpMouseCursorPosition(CGPoint(x: point.x + 2, y: point.y))
        CGWarpMouseCursorPosition(point)
        usleep(20_000)
        guard let event = CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 1, wheel1: Int32(delta), wheel2: 0, wheel3: 0) else {
            throw BridgeFailure.message("could not create scroll event")
        }
        event.post(tap: .cghidEventTap)
        // Flutter silently drops wheel steps during sustained moves when they
        // arrive faster than the editor/device round trip. Hardware calibration
        // found 100 ms too aggressive; 120 ms remains inside the bridge's legacy
        // 15-second subprocess budget for a 100-step batch.
        usleep(100_000)
    }
}

func keyPress(_ keyCode: CGKeyCode, flags: CGEventFlags = []) throws {
    guard let down = CGEvent(keyboardEventSource: nil, virtualKey: keyCode, keyDown: true),
          let up = CGEvent(keyboardEventSource: nil, virtualKey: keyCode, keyDown: false) else {
        throw BridgeFailure.message("could not create keyboard event")
    }
    down.flags = flags
    up.flags = flags
    if let pid = app()?.processIdentifier { down.postToPid(pid) }
    else { down.post(tap: .cghidEventTap) }
    usleep(40_000)
    if let pid = app()?.processIdentifier { up.postToPid(pid) }
    else { up.post(tap: .cghidEventTap) }
}

func modifiedKeyPress(_ keyCode: CGKeyCode, command: Bool = false, shift: Bool = false) throws {
    var active: CGEventFlags = []
    func modifier(_ code: CGKeyCode, down: Bool, flags: CGEventFlags) throws {
        guard let event = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: down) else {
            throw BridgeFailure.message("could not create modifier event")
        }
        event.flags = flags
        if let pid = app()?.processIdentifier { event.postToPid(pid) }
        else { event.post(tap: .cghidEventTap) }
        usleep(25_000)
    }
    if command {
        active.insert(.maskCommand)
        try modifier(55, down: true, flags: active)
    }
    if shift {
        active.insert(.maskShift)
        try modifier(56, down: true, flags: active)
    }
    try keyPress(keyCode, flags: active)
    if shift {
        active.remove(.maskShift)
        try modifier(56, down: false, flags: active)
    }
    if command {
        active.remove(.maskCommand)
        try modifier(55, down: false, flags: active)
    }
}

func replaceText(at point: CGPoint, with text: String) throws {
    if let running = app() {
        _ = running.activate(options: [.activateAllWindows])
        usleep(180_000)
    }
    try click(at: point)
    usleep(120_000)
    // The first click may only activate a background Flutter window.
    try click(at: point)
    usleep(80_000)
    // Flutter's macOS text field does not honor AXValue as an editor commit.
    // Select the full line with real navigation keystrokes, then type it.
    try modifiedKeyPress(123, command: true) // Command-Left
    try modifiedKeyPress(124, command: true, shift: true) // Command-Shift-Right
    for character in text {
        let scalar = String(character)
        var units = Array(scalar.utf16)
        guard let down = CGEvent(keyboardEventSource: nil, virtualKey: 0, keyDown: true),
              let up = CGEvent(keyboardEventSource: nil, virtualKey: 0, keyDown: false),
              let pid = app()?.processIdentifier else {
            throw BridgeFailure.message("could not create Unicode text event")
        }
        down.keyboardSetUnicodeString(stringLength: units.count, unicodeString: &units)
        up.keyboardSetUnicodeString(stringLength: units.count, unicodeString: &units)
        down.postToPid(pid)
        up.postToPid(pid)
        usleep(40_000)
    }
    try keyPress(36) // Return commits the editor value to the device.
    usleep(150_000)
}

func drag(from start: CGPoint, to end: CGPoint) throws {
    guard let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: start, mouseButton: .left),
          let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: end, mouseButton: .left) else {
        throw BridgeFailure.message("could not create drag event")
    }
    CGWarpMouseCursorPosition(start)
    down.post(tap: .cghidEventTap)
    // Flutter's LongPressDraggable ignores a single instantaneous mouse jump.
    // Hold long enough to arm it, then emit a short path of drag events.
    usleep(550_000)
    for step in 1...20 {
        let fraction = CGFloat(step) / 20.0
        let point = CGPoint(
            x: start.x + (end.x - start.x) * fraction,
            y: start.y + (end.y - start.y) * fraction
        )
        guard let moved = CGEvent(
            mouseEventSource: nil,
            mouseType: .leftMouseDragged,
            mouseCursorPosition: point,
            mouseButton: .left
        ) else { throw BridgeFailure.message("could not create drag event") }
        moved.post(tap: .cghidEventTap)
        usleep(20_000)
    }
    usleep(100_000)
    up.post(tap: .cghidEventTap)
}

func press(_ element: AXUIElement) throws {
    if AXUIElementPerformAction(element, kAXPressAction as CFString) == .success { return }
    let point = pointAttribute(element, kAXPositionAttribute)
    let size = sizeAttribute(element, kAXSizeAttribute)
    guard size.width > 0 && size.height > 0 else { throw BridgeFailure.message("element cannot be pressed") }
    try click(at: CGPoint(x: point.x + size.width / 2, y: point.y + size.height / 2))
}

func windowPoint(x: CGFloat, y: CGFloat) throws -> CGPoint {
    let window = try rootElement()
    let origin = pointAttribute(window, kAXPositionAttribute)
    return CGPoint(x: origin.x + x, y: origin.y + y)
}

func setValue(_ element: AXUIElement, text: String) throws {
    let role = stringAttribute(element, kAXRoleAttribute)
    let size = sizeAttribute(element, kAXSizeAttribute)
    if role == "AXTextField", size.width > 100 {
        let point = pointAttribute(element, kAXPositionAttribute)
        _ = AXUIElementSetAttributeValue(
            element,
            kAXFocusedAttribute as CFString,
            kCFBooleanTrue
        )
        usleep(100_000)
        try replaceText(
            at: CGPoint(x: point.x + size.width / 2, y: point.y + size.height / 2),
            with: text
        )
        return
    }
    let existing = copyAttribute(element, kAXValueAttribute)
    let value: CFTypeRef
    if existing is NSNumber, let number = Double(text) { value = NSNumber(value: number) }
    else if text.caseInsensitiveCompare("true") == .orderedSame { value = NSNumber(value: true) }
    else if text.caseInsensitiveCompare("false") == .orderedSame { value = NSNumber(value: false) }
    else { value = text as CFString }
    let error = AXUIElementSetAttributeValue(element, kAXValueAttribute as CFString, value)
    guard error == .success else { throw BridgeFailure.message("control does not expose a settable AXValue (AXError \(error.rawValue))") }
    // Flutter text fields update their semantic value immediately but only send
    // the change to the device after AXConfirm (the equivalent of Return).
    _ = AXUIElementPerformAction(element, "AXConfirm" as CFString)
}

func doubleArg(_ text: String) throws -> Double {
    guard let number = Double(text) else { throw BridgeFailure.message("invalid coordinate") }
    return number
}

func sampleScreen(rect: CGRect) async throws -> ColorSample {
    guard #available(macOS 14.0, *) else {
        throw BridgeFailure.message("Console mute read-back requires macOS 14 or newer")
    }
    let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
    guard let window = content.windows.first(where: {
        $0.owningApplication?.bundleIdentifier == bundleIdentifier
    }) else { throw BridgeFailure.message("NUX Audio capture window not found") }
    let configuration = SCStreamConfiguration()
    configuration.width = max(1, Int(window.frame.width.rounded()))
    configuration.height = max(1, Int(window.frame.height.rounded()))
    configuration.showsCursor = false
    let filter = SCContentFilter(desktopIndependentWindow: window)
    let image = try await SCScreenshotManager.captureImage(
        contentFilter: filter,
        configuration: configuration
    )
    let bitmap = NSBitmapImageRep(cgImage: image)
    guard bitmap.pixelsWide > 0, bitmap.pixelsHigh > 0 else {
        throw BridgeFailure.message("screen sample was empty")
    }
    let local = CGRect(
        x: rect.minX - window.frame.minX,
        y: rect.minY - window.frame.minY,
        width: rect.width,
        height: rect.height
    ).intersection(CGRect(x: 0, y: 0, width: bitmap.pixelsWide, height: bitmap.pixelsHigh))
    guard !local.isNull, !local.isEmpty else {
        throw BridgeFailure.message("screen sample lies outside the NUX Audio window")
    }
    var red = 0.0, green = 0.0, blue = 0.0, alpha = 0.0
    var count = 0.0
    for y in Int(local.minY)..<Int(local.maxY) {
        for x in Int(local.minX)..<Int(local.maxX) {
            guard let color = bitmap.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB) else { continue }
            red += color.redComponent
            green += color.greenComponent
            blue += color.blueComponent
            alpha += color.alphaComponent
            count += 1
        }
    }
    guard count > 0 else { throw BridgeFailure.message("screen sample contained no readable pixels") }
    return ColorSample(red: red / count, green: green / count, blue: blue / count, alpha: alpha / count)
}

func run() async throws {
    let args = Array(CommandLine.arguments.dropFirst())
    let command = args.first ?? "doctor"
    switch command {
    case "doctor":
        let running = app()
        var count = 0
        if let running, AXIsProcessTrusted() {
            let application = AXUIElementCreateApplication(running.processIdentifier)
            count = (copyAttribute(application, kAXWindowsAttribute) as? [AXUIElement])?.count ?? 0
        }
        try emit(Doctor(accessibilityTrusted: AXIsProcessTrusted(), appRunning: running != nil, windowCount: count, bundleIdentifier: bundleIdentifier))
    case "request-access":
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        try emit(Result(ok: AXIsProcessTrustedWithOptions(options), message: "Allow Accessibility access in System Settings, then run doctor again."))
    case "activate":
        guard let running = app() else { throw BridgeFailure.message("NUX Audio is not running") }
        try emit(Result(ok: running.activate(options: [.activateAllWindows]), message: nil))
    case "move-window":
        guard args.count == 3,
              let x = Double(args[1]),
              let y = Double(args[2]) else {
            throw BridgeFailure.message("usage: move-window X Y")
        }
        let window = try rootElement()
        var point = CGPoint(x: x, y: y)
        guard let value = AXValueCreate(.cgPoint, &point) else {
            throw BridgeFailure.message("could not create window position")
        }
        let result = AXUIElementSetAttributeValue(
            window,
            kAXPositionAttribute as CFString,
            value
        )
        guard result == .success else {
            throw BridgeFailure.message("could not move NUX Audio window: AX error \(result.rawValue)")
        }
        try emit(Result(ok: true, message: nil))
    case "snapshot", "debug-main":
        try emit(try stabilizedSnapshot())
    case "press-snapshot", "click-snapshot":
        guard args.count == 2 else { throw BridgeFailure.message("usage: press-snapshot INDEX") }
        try press(try element(at: args[1])); try emit(Result(ok: true, message: nil))
    case "press-label":
        guard args.count >= 2 else { throw BridgeFailure.message("usage: press-label LABEL") }
        try press(try element(labeled: args.dropFirst().joined(separator: " ")))
        try emit(Result(ok: true, message: nil))
    case "select-preset":
        guard args.count == 3 else { throw BridgeFailure.message("usage: select-preset CURRENT_INDEX SLOT") }
        try press(try element(at: args[1]))
        usleep(350_000)
        let slot = args[2]
        do { try press(try element(labeled: "U" + slot)) }
        catch { try press(try element(labeled: slot)) }
        usleep(220_000)
        // Flutter occasionally omits the modal footer from a newly-created AX
        // client even though it is visible. The editor window is fixed-size and
        // the preset confirmation button has stable window-relative geometry.
        try click(at: try windowPoint(x: 570, y: 505))
        usleep(700_000)
        try emit(Result(ok: true, message: nil))
    case "select-routing":
        guard args.count == 2, let row = Int(args[1]), (0...2).contains(row) else {
            throw BridgeFailure.message("usage: select-routing ROW(0|1|2)")
        }
        try click(at: try windowPoint(x: 50, y: 186))
        usleep(300_000)
        let y: CGFloat = [205, 242, 279.5][row]
        try click(at: try windowPoint(x: 116.5, y: y))
        usleep(450_000)
        try emit(Result(ok: true, message: nil))
    case "add-module":
        guard args.count == 4 else { throw BridgeFailure.message("usage: add-module SLOT_X SLOT_Y CATEGORY") }
        let slot = CGPoint(x: try doubleArg(args[1]), y: try doubleArg(args[2]))
        let category = args[3]
        try click(at: slot)
        // Routing changes rebuild the selected-slot panel; its central ADD+
        // affordance can appear several frames after the slot highlight.
        usleep(500_000)
        try click(at: try windowPoint(x: 460, y: 338))
        // Wait for the modal scale animation; clicks during its first frames are
        // delivered to the underlying editor instead of the category list.
        usleep(800_000)
        // Flutter does not reliably publish a new route's children to a second
        // AX client. Category geometry is stable in NUX Audio 1.1.x, so this
        // transaction deliberately avoids modal semantics altogether.
        let upperRows: [String: CGFloat] = [
            "GATE": 229, "CMP": 278, "EFX": 328, "AMP": 377,
            "IR": 426, "EQ": 476, "DLY": 525,
        ]
        let lowerRows: [String: CGFloat] = [
            "RVB": 367, "S/R": 417, "WAH": 466, "MOD": 516, "PL": 566,
        ]
        if let y = upperRows[category] {
            try click(at: try windowPoint(x: 232, y: y))
        } else if let y = lowerRows[category] {
            let scrollPoint = try windowPoint(x: 232, y: 525)
            try scroll(at: scrollPoint, delta: -1, count: 4)
            // The Flutter list continues its animated offset briefly after the
            // synthetic wheel events; clicking early lands one row above.
            usleep(650_000)
            try click(at: try windowPoint(x: 232, y: y))
        } else {
            throw BridgeFailure.message("unsupported module category: \(category)")
        }
        usleep(650_000)
        // The button's vertical position depends on the selected model artwork.
        // Do not depend on the lazily-published modal AX tree here: every add is
        // verified by the Python driver against the resulting chain block.
        let addYByCategory: [String: CGFloat] = [
            "AMP": 443, "IR": 452, "S/R": 439, "MOD": 432,
        ]
        let addY = addYByCategory[category] ?? 470
        try click(at: try windowPoint(x: 545, y: addY))
        usleep(600_000)
        try emit(Result(ok: true, message: nil))
    case "set-snapshot":
        guard args.count >= 3 else { throw BridgeFailure.message("usage: set-snapshot INDEX VALUE") }
        let text = args.dropFirst(2).joined(separator: " ")
        var target = try element(at: args[1])
        // Flutter's flattened semantics order can change between the Python
        // snapshot process and this mutation process. A nonnumeric value meant
        // for the preset-name field must be resolved again atomically here.
        let targetRole = stringAttribute(target, kAXRoleAttribute)
        let targetSize = sizeAttribute(target, kAXSizeAttribute)
        if Double(text) == nil,
           !["true", "false"].contains(text.lowercased()),
           (targetRole != "AXTextField" || targetSize.width < 100) {
            let fields = try flattenedElements().filter {
                stringAttribute($0, kAXRoleAttribute) == "AXTextField"
                    && sizeAttribute($0, kAXSizeAttribute).width > 100
            }
            if let widest = fields.max(by: {
                sizeAttribute($0, kAXSizeAttribute).width < sizeAttribute($1, kAXSizeAttribute).width
            }) { target = widest }
        }
        try setValue(target, text: text)
        try emit(Result(ok: true, message: nil))
    case "click-screen":
        guard args.count == 3 else { throw BridgeFailure.message("usage: click-screen X Y") }
        try click(at: CGPoint(x: try doubleArg(args[1]), y: try doubleArg(args[2])))
        // Flutter modal/tab routes animate after the click; callers snapshot
        // immediately, so keep the transaction open until semantics settle.
        usleep(300_000)
        try emit(Result(ok: true, message: nil))
    case "right-click-screen":
        guard args.count == 3 else { throw BridgeFailure.message("usage: right-click-screen X Y") }
        try click(
            at: CGPoint(x: try doubleArg(args[1]), y: try doubleArg(args[2])),
            button: .right
        )
        try emit(Result(ok: true, message: nil))
    case "delete-at":
        guard args.count == 3 else { throw BridgeFailure.message("usage: delete-at X Y") }
        let point = CGPoint(x: try doubleArg(args[1]), y: try doubleArg(args[2]))
        try click(at: point, button: .right)
        usleep(350_000)
        try click(at: CGPoint(x: point.x + 36, y: point.y + 131))
        usleep(300_000)
        try emit(Result(ok: true, message: nil))
    case "select-module-at":
        guard args.count >= 4 else {
            throw BridgeFailure.message("usage: select-module-at X Y LABEL")
        }
        let point = CGPoint(x: try doubleArg(args[1]), y: try doubleArg(args[2]))
        // Opening and dismissing the block context menu forces Flutter to
        // publish a lazily-painted chain block to this AX client.
        try click(at: point, button: .right)
        usleep(180_000)
        try keyPress(53)
        usleep(180_000)
        try press(try element(labeled: args.dropFirst(3).joined(separator: " ")))
        usleep(300_000)
        try emit(Result(ok: true, message: nil))
    case "scroll-screen":
        guard args.count == 5, let direction = Int(args[3]), let count = Int(args[4]), [-1, 1].contains(direction) else {
            throw BridgeFailure.message("usage: scroll-screen X Y DIRECTION(-1|1) COUNT")
        }
        try scroll(at: CGPoint(x: try doubleArg(args[1]), y: try doubleArg(args[2])), delta: direction, count: count)
        try emit(Result(ok: true, message: nil))
    case "key":
        guard args.count == 2 else { throw BridgeFailure.message("usage: key escape|return") }
        let codes: [String: CGKeyCode] = ["escape": 53, "return": 36]
        guard let code = codes[args[1].lowercased()] else { throw BridgeFailure.message("supported keys: escape, return") }
        try keyPress(code)
        try emit(Result(ok: true, message: nil))
    case "drag-screen":
        guard args.count == 5 else { throw BridgeFailure.message("usage: drag-screen X1 Y1 X2 Y2") }
        try drag(
            from: CGPoint(x: try doubleArg(args[1]), y: try doubleArg(args[2])),
            to: CGPoint(x: try doubleArg(args[3]), y: try doubleArg(args[4]))
        )
    case "sample-screen":
        guard args.count == 5 else { throw BridgeFailure.message("usage: sample-screen X Y WIDTH HEIGHT") }
        try emit(try await sampleScreen(rect: CGRect(
            x: try doubleArg(args[1]), y: try doubleArg(args[2]),
            width: try doubleArg(args[3]), height: try doubleArg(args[4])
        )))
        try emit(Result(ok: true, message: nil))
    default:
        throw BridgeFailure.message("unknown command: \(command)")
    }
}

Task {
    do {
        try await run()
        exit(0)
    } catch {
        FileHandle.standardError.write(Data("\(error)\n".utf8))
        exit(1)
    }
}
RunLoop.main.run()

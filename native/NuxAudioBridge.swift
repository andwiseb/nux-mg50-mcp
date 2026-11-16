import AppKit
import ApplicationServices
import Foundation

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
    let x: Double
    let y: Double
    let width: Double
    let height: Double
    let actions: [String]
}

struct Snapshot: Codable { let nodes: [Node] }
struct Result: Codable { let ok: Bool; let message: String? }

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
        var names: CFArray?
        AXUIElementCopyActionNames(element, &names)
        return Node(
            index: index,
            role: stringAttribute(element, kAXRoleAttribute),
            title: stringAttribute(element, kAXTitleAttribute),
            description: stringAttribute(element, kAXDescriptionAttribute),
            value: stringAttribute(element, kAXValueAttribute),
            x: point.x, y: point.y, width: size.width, height: size.height,
            actions: (names as? [String]) ?? []
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
    let elements = try flattenedElements()
    let matches = elements.filter { element in
        let text = [
            stringAttribute(element, kAXTitleAttribute),
            stringAttribute(element, kAXDescriptionAttribute),
            stringAttribute(element, kAXValueAttribute),
        ].joined(separator: " ")
        return normalized(text).contains(wanted)
    }
    guard let result = matches.min(by: { left, right in
        let l = stringAttribute(left, kAXTitleAttribute).count + stringAttribute(left, kAXDescriptionAttribute).count + stringAttribute(left, kAXValueAttribute).count
        let r = stringAttribute(right, kAXTitleAttribute).count + stringAttribute(right, kAXDescriptionAttribute).count + stringAttribute(right, kAXValueAttribute).count
        return l < r
    }) else { throw BridgeFailure.message("labeled element not found: \(label)") }
    return result
}

func click(at point: CGPoint) throws {
    guard let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left),
          let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left) else {
        throw BridgeFailure.message("could not create mouse event")
    }
    down.post(tap: .cghidEventTap)
    usleep(40_000)
    up.post(tap: .cghidEventTap)
}

func scroll(at point: CGPoint, delta: Int, count: Int) throws {
    guard count >= 1 && count <= 100 else { throw BridgeFailure.message("scroll count must be 1-100") }
    CGWarpMouseCursorPosition(point)
    for _ in 0..<count {
        guard let event = CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 1, wheel1: Int32(delta), wheel2: 0, wheel3: 0) else {
            throw BridgeFailure.message("could not create scroll event")
        }
        event.post(tap: .cghidEventTap)
        usleep(12_000)
    }
}

func keyPress(_ keyCode: CGKeyCode) throws {
    guard let down = CGEvent(keyboardEventSource: nil, virtualKey: keyCode, keyDown: true),
          let up = CGEvent(keyboardEventSource: nil, virtualKey: keyCode, keyDown: false) else {
        throw BridgeFailure.message("could not create keyboard event")
    }
    down.post(tap: .cghidEventTap)
    usleep(40_000)
    up.post(tap: .cghidEventTap)
}

func drag(from start: CGPoint, to end: CGPoint) throws {
    guard let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: start, mouseButton: .left),
          let moved = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDragged, mouseCursorPosition: end, mouseButton: .left),
          let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: end, mouseButton: .left) else {
        throw BridgeFailure.message("could not create drag event")
    }
    CGWarpMouseCursorPosition(start)
    down.post(tap: .cghidEventTap)
    usleep(120_000)
    moved.post(tap: .cghidEventTap)
    usleep(120_000)
    up.post(tap: .cghidEventTap)
}

func press(_ element: AXUIElement) throws {
    if AXUIElementPerformAction(element, kAXPressAction as CFString) == .success { return }
    let point = pointAttribute(element, kAXPositionAttribute)
    let size = sizeAttribute(element, kAXSizeAttribute)
    guard size.width > 0 && size.height > 0 else { throw BridgeFailure.message("element cannot be pressed") }
    try click(at: CGPoint(x: point.x + size.width / 2, y: point.y + size.height / 2))
}

func setValue(_ element: AXUIElement, text: String) throws {
    let existing = copyAttribute(element, kAXValueAttribute)
    let value: CFTypeRef
    if existing is NSNumber, let number = Double(text) { value = NSNumber(value: number) }
    else if text.caseInsensitiveCompare("true") == .orderedSame { value = NSNumber(value: true) }
    else if text.caseInsensitiveCompare("false") == .orderedSame { value = NSNumber(value: false) }
    else { value = text as CFString }
    let error = AXUIElementSetAttributeValue(element, kAXValueAttribute as CFString, value)
    guard error == .success else { throw BridgeFailure.message("control does not expose a settable AXValue (AXError \(error.rawValue))") }
}

func doubleArg(_ text: String) throws -> Double {
    guard let number = Double(text) else { throw BridgeFailure.message("invalid coordinate") }
    return number
}

func run() throws {
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
    case "snapshot", "debug-main":
        try emit(try snapshot())
    case "press-snapshot", "click-snapshot":
        guard args.count == 2 else { throw BridgeFailure.message("usage: press-snapshot INDEX") }
        try press(try element(at: args[1])); try emit(Result(ok: true, message: nil))
    case "press-label":
        guard args.count >= 2 else { throw BridgeFailure.message("usage: press-label LABEL") }
        try press(try element(labeled: args.dropFirst().joined(separator: " ")))
        try emit(Result(ok: true, message: nil))
    case "set-snapshot":
        guard args.count >= 3 else { throw BridgeFailure.message("usage: set-snapshot INDEX VALUE") }
        try setValue(try element(at: args[1]), text: args.dropFirst(2).joined(separator: " "))
        try emit(Result(ok: true, message: nil))
    case "click-screen":
        guard args.count == 3 else { throw BridgeFailure.message("usage: click-screen X Y") }
        try click(at: CGPoint(x: try doubleArg(args[1]), y: try doubleArg(args[2])))
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
        try emit(Result(ok: true, message: nil))
    default:
        throw BridgeFailure.message("unknown command: \(command)")
    }
}

do { try run() }
catch {
    FileHandle.standardError.write(Data("\(error)\n".utf8))
    exit(1)
}

import AppKit

/// One in-flight operation; an undo token can only undo the exact latest history event.
final class QuickActionController: NSObject {
  private var event: String?
  private var busy = false
  private var toast: NSPanel?
  private var timer: Timer?
  var canUndo: Bool { event != nil && !busy }

  func perform(action: String, code: String, word: String) {
    guard !busy else { return }
    run(["--json", action, code, word]) { result in
      self.event = result["event"] as? String
      let term = String(word.prefix(24)) + (word.count > 24 ? "…" : "")
      let label: String
      switch action {
      case "block_code": label = "已仅在 \(code) 下隐藏「\(term)」"
      case "block": label = "已在所有拼音下隐藏「\(term)」"
      case "pin": label = "已置顶「\(term)」"
      case "unpin": label = "已取消置顶「\(term)」"
      default: label = "已降低「\(term)」优先级"
      }
      self.notify(label + " · 下次输入生效", undo: true)
    }
  }

  @objc func undo() {
    guard let token = event, !busy else { return }
    run(["--undo-json", token]) { _ in
      self.event = nil
      self.notify("已撤销候选调整 · 下次输入生效")
    }
  }

  private func run(_ args: [String], completion: @escaping ([String: Any]) -> Void) {
    busy = true
    toast?.orderOut(nil)
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
    // The settings helper was renamed KongFlow设置.app in 0.31; the old path broke every candidate adjustment.
    let script = SquirrelApplicationDelegate.managerFolder.appendingPathComponent("quick.py")
    process.arguments = ["-B", script.path] + args
    var environment = ProcessInfo.processInfo.environment
    environment["KONGIME_RIME"] = SquirrelApp.userDir.path
    process.environment = environment
    let output = Pipe(), errors = Pipe()
    process.standardOutput = output; process.standardError = errors
    process.terminationHandler = { process in
      let data = output.fileHandleForReading.readDataToEndOfFile()
      let error = String(data: errors.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? "操作失败，请重试"
      DispatchQueue.main.async {
        self.busy = false
        if process.terminationStatus == 0, let result = try? JSONSerialization.jsonObject(with: data) as? [String: Any], result["ok"] as? Bool == true {
          completion(result)
        } else {
          if args.first == "--undo-json" { self.event = nil }
          self.notify(error.trimmingCharacters(in: .whitespacesAndNewlines))
        }
      }
    }
    do { try process.run() } catch { busy = false; notify("无法保存候选调整：" + error.localizedDescription) }
  }

  func notify(_ message: String, undo: Bool = false) {
    timer?.invalidate(); toast?.orderOut(nil)
    let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 420, height: 76), styleMask: [.nonactivatingPanel, .hudWindow], backing: .buffered, defer: false)
    panel.title = "KongFlow 提示"
    panel.level = .floating; panel.hidesOnDeactivate = false
    panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
    let background = NSVisualEffectView(frame: panel.contentView!.bounds)
    background.material = .hudWindow; background.state = .active
    let label = NSTextField(wrappingLabelWithString: message)
    label.frame = NSRect(x: 16, y: 13, width: undo ? 314 : 388, height: 50)
    label.maximumNumberOfLines = 3; label.font = .systemFont(ofSize: 13)
    background.addSubview(label)
    if undo {
      let button = NSButton(title: "撤销", target: self, action: #selector(self.undo))
      button.frame = NSRect(x: 338, y: 24, width: 68, height: 28)
      button.setAccessibilityLabel("撤销这次候选调整")
      background.addSubview(button)
    }
    panel.contentView = background
    let screen = NSScreen.screens.first(where: { $0.frame.contains(NSEvent.mouseLocation) }) ?? NSScreen.main
    if let frame = screen?.visibleFrame { panel.setFrameOrigin(NSPoint(x: frame.maxX - 436, y: frame.maxY - 92)) }
    toast = panel; panel.orderFrontRegardless()
    timer = Timer.scheduledTimer(withTimeInterval: undo ? 8 : 5, repeats: false) { [weak self] _ in self?.toast?.orderOut(nil) }
  }
}

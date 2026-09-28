import Foundation

/// Only the persistent pause preference survives process restart. No input is stored.
final class LearningPause {
  static let shared = LearningPause(defaults: UserDefaults(suiteName: "local.kongime.learning-pause")!)
  private let defaults: UserDefaults
  private var sessionPaused = false
  init(defaults: UserDefaults) { self.defaults = defaults }
  var mode: String { defaults.bool(forKey: "paused") ? "persistent" : (sessionPaused ? "session" : "off") }
  var paused: Bool { mode != "off" }
  func statusTitle(learningEnabled: Bool?, pauseSupported: Bool) -> String {
    guard let enabled = learningEnabled else { return "词频学习：状态待确认" }
    if !enabled { return "词频学习：总开关已关闭" }
    if paused && !pauseSupported { return "词频学习：暂停未生效，请应用配置" }
    switch mode {
    case "persistent": return "词频学习：已暂停，需手动恢复"
    case "session": return "词频学习：已暂停，本次退出后恢复"
    default: return "词频学习：学习中"
    }
  }
  func set(_ mode: String) {
    guard ["off", "session", "persistent"].contains(mode) else { return }
    defaults.set(mode == "persistent", forKey: "paused")
    sessionPaused = mode == "session"
  }
}

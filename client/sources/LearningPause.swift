import Foundation

/// Only the persistent pause preference survives process restart. No input is stored.
final class LearningPause {
  static let shared = LearningPause(defaults: UserDefaults(suiteName: "local.kongime.learning-pause")!)
  private let defaults: UserDefaults
  private var sessionPaused = false
  init(defaults: UserDefaults) { self.defaults = defaults }
  var mode: String { defaults.bool(forKey: "paused") ? "persistent" : (sessionPaused ? "session" : "off") }
  var paused: Bool { mode != "off" }
  func set(_ mode: String) {
    guard ["off", "session", "persistent"].contains(mode) else { return }
    defaults.set(mode == "persistent", forKey: "paused")
    sessionPaused = mode == "session"
  }
}

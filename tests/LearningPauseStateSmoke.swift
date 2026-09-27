import Foundation
@main struct Test {
 static func main() {
  let name = "local.kongime.test." + UUID().uuidString
  let defaults = UserDefaults(suiteName: name)!
  defer { defaults.removePersistentDomain(forName: name) }
  let pause = LearningPause(defaults: defaults)
  precondition(!pause.paused)
  pause.set("session"); precondition(pause.mode == "session")
  precondition(!LearningPause(defaults: defaults).paused)
  pause.set("persistent"); precondition(LearningPause(defaults: defaults).mode == "persistent")
  pause.set("session"); precondition(!LearningPause(defaults: defaults).paused)
  pause.set("off"); precondition(!pause.paused)
  pause.set("invalid"); precondition(!pause.paused)
  print("PASS pause persistence, process session expiry, resume, invalid mode")
 }
}

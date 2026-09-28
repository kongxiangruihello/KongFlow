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
  precondition(pause.statusTitle(learningEnabled: true, pauseSupported: true) == "词频学习：学习中")
  pause.set("session")
  precondition(pause.statusTitle(learningEnabled: true, pauseSupported: true) == "词频学习：已暂停，本次退出后恢复")
  precondition(pause.statusTitle(learningEnabled: true, pauseSupported: false).contains("暂停未生效"))
  pause.set("persistent")
  precondition(pause.statusTitle(learningEnabled: true, pauseSupported: true) == "词频学习：已暂停，需手动恢复")
  precondition(pause.statusTitle(learningEnabled: false, pauseSupported: true) == "词频学习：总开关已关闭")
  precondition(pause.statusTitle(learningEnabled: nil, pauseSupported: true) == "词频学习：状态待确认")
  pause.set("off")
  precondition(pause.statusTitle(learningEnabled: false, pauseSupported: true) == "词频学习：总开关已关闭")
  print("PASS pause persistence, session expiry, resume, disabled/unknown configuration, all status labels")
 }
}

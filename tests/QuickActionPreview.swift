// Isolated UI harness for the production quick action / undo controller.
import AppKit
final class SquirrelApp { static let userDir = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("kongime28-quick-preview") }
final class Preview: NSObject, NSApplicationDelegate {
 let actions = QuickActionController()
 var window: NSWindow!
 func applicationDidFinishLaunching(_ notification: Notification) {
  window = NSWindow(contentRect: NSRect(x: 200,y: 250,width: 420,height: 140),styleMask: [.titled,.closable],backing:.buffered,defer:false)
  window.title = "KongIME 0.28 · 隔离测试"
  let button = NSButton(title: "测试仅在 nh 下隐藏「你好」",target:self,action:#selector(test))
  button.frame = NSRect(x:30,y:65,width:360,height:40); window.contentView!.addSubview(button)
  let label = NSTextField(labelWithString:"仅使用临时测试词库，不修改个人数据")
  label.frame=NSRect(x:30,y:25,width:360,height:24);window.contentView!.addSubview(label)
  window.center();window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
 }
 @objc func test() { window.orderOut(nil); actions.perform(action:"block_code",code:"nh",word:"你好") }
}
@main struct Main {
 static func main() { let app=NSApplication.shared;let delegate=Preview();app.delegate=delegate;app.setActivationPolicy(.regular);app.run() }
}

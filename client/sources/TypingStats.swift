import Foundation

/// 本地输入统计：只记录每天上屏的字数、汉字数和上屏次数，不记录任何文字内容。
/// 写入 KongFlow 设置的数据目录 typing-stats.json；设置里可关闭（kongime/stats）。
final class TypingStats {
  static let shared = TypingStats()
  private struct Counts { var chars = 0, han = 0, commits = 0 }
  private var pending: [String: Counts] = [:]
  private var timer: Timer?
  private static let keepDays = 400

  private static let dayFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.dateFormat = "yyyy-MM-dd"
    return formatter
  }()

  var url: URL {
    let base = ProcessInfo.processInfo.environment["QINGYAN_DATA"].map { URL(fileURLWithPath: $0) }
      ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/KongIME/manager")
    return base.appendingPathComponent("typing-stats.json")
  }

  static func hanCount(_ text: String) -> Int {
    text.unicodeScalars.filter { (0x3400...0x9FFF).contains($0.value) || (0x20000...0x323AF).contains($0.value) }.count
  }

  func record(_ text: String) {
    guard !text.isEmpty else { return }
    let day = Self.dayFormatter.string(from: Date())
    var counts = pending[day] ?? Counts()
    counts.chars += text.count
    counts.han += Self.hanCount(text)
    counts.commits += 1
    pending[day] = counts
    if timer == nil {
      timer = Timer.scheduledTimer(withTimeInterval: 30, repeats: false) { [weak self] _ in self?.flush() }
    }
  }

  struct Summary { var today = 0, week = 0, month = 0, total = 0, todayHan = 0, todayCommits = 0, days = 0 }

  /// 今日、近 7 日、近 30 日与累计上屏字数（已写入文件的加上尚未写入的）。
  func summary(now: Date = Date()) -> Summary {
    var days = ((try? Data(contentsOf: url)).flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any])?["days"] as? [String: [String: Int]] ?? [:]
    for (day, counts) in pending {
      var entry = days[day] ?? [:]
      entry["chars", default: 0] += counts.chars
      entry["han", default: 0] += counts.han
      entry["commits", default: 0] += counts.commits
      days[day] = entry
    }
    let calendar = Calendar.current
    let start = calendar.startOfDay(for: now)
    var result = Summary()
    result.days = days.count
    for (day, entry) in days {
      guard let date = Self.dayFormatter.date(from: day) else { continue }
      let chars = entry["chars"] ?? 0
      let age = calendar.dateComponents([.day], from: calendar.startOfDay(for: date), to: start).day ?? Int.max
      result.total += chars
      if age < 30 { result.month += chars }
      if age < 7 { result.week += chars }
      if age == 0 {
        result.today += chars
        result.todayHan += entry["han"] ?? 0
        result.todayCommits += entry["commits"] ?? 0
      }
    }
    return result
  }

  func flush() {
    timer?.invalidate()
    timer = nil
    guard !pending.isEmpty else { return }
    var root = ((try? Data(contentsOf: url)).flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any]) ?? [:]
    var days = root["days"] as? [String: [String: Int]] ?? [:]
    for (day, counts) in pending {
      var entry = days[day] ?? [:]
      entry["chars", default: 0] += counts.chars
      entry["han", default: 0] += counts.han
      entry["commits", default: 0] += counts.commits
      days[day] = entry
    }
    for day in days.keys.sorted().dropLast(Self.keepDays) { days.removeValue(forKey: day) }
    root["version"] = 1
    root["days"] = days
    pending.removeAll()
    do {
      try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
      let data = try JSONSerialization.data(withJSONObject: root, options: [.sortedKeys])
      try data.write(to: url, options: .atomic)
    } catch {
      // Statistics are optional; never interrupt typing because of them.
    }
  }
}

import Foundation

enum PunctuationPairs {
  static let chinese = ["(": "（）", "[": "【】", "{": "｛｝", "<": "《》", "\"": "“”", "'": "‘’"]
  static let english = ["(": "()", "[": "[]", "{": "{}", "\"": "\"\"", "'": "''"]
  /// 学术标点：直角引号「」『』（设置 → 引号样式）。
  static let chineseCorner = chinese.merging(["\"": "「」", "'": "『』"]) { $1 }
  /// Pairs typed with < while inside an open 《 (书名号嵌套).
  static let nestedTitle = "〈〉"

  static func table(ascii: Bool, corner: Bool) -> [String: String] {
    ascii ? english : (corner ? chineseCorner : chinese)
  }
  static func pair(for key: String, ascii: Bool, previous: String, corner: Bool = false, insideTitle: Bool = false) -> String? {
    // Preserve contractions and possessives such as don't and user's.
    if key == "'", let c = previous.last, c.isASCII && (c.isLetter || c.isNumber) { return nil }
    if !ascii && key == "<" && insideTitle { return nestedTitle }
    return table(ascii: ascii, corner: corner)[key]
  }
  static func isEmptyPair(_ text: String, ascii: Bool) -> Bool {
    if ascii { return english.values.contains(text) }
    return chinese.values.contains(text) || chineseCorner.values.contains(text) || text == nestedTitle
  }
  static func closing(for key: String, ascii: Bool) -> String? {
    closings(for: key, ascii: ascii).first
  }
  /// Every closing mark the key may skip over (both quote styles, and 〉 for nested titles).
  static func closings(for key: String, ascii: Bool) -> [String] {
    guard let opening = [")": "(", "]": "[", "}": "{", ">": "<", "\"": "\"", "'": "'"][key] else { return [] }
    var result: [String] = []
    for table in ascii ? [english] : [chinese, chineseCorner] {
      if let mark = table[opening]?.last.map(String.init), !result.contains(mark) { result.append(mark) }
    }
    if !ascii && key == ">" { result.append("〉") }
    return result
  }
  /// True when the text before the caret has an unclosed 《.
  static func insideTitle(_ before: String) -> Bool {
    var depth = 0
    for ch in before {
      if ch == "《" { depth += 1 } else if ch == "》" { depth = max(0, depth - 1) }
    }
    return depth > 0
  }
  // A single nonempty replacement lets the host undo the pair/wrap as one edit.
  // Empty marked text moves the caret in document-access clients without key synthesis.
  static func move(to location: Int, replace: (String, NSRange) -> Void, locate: (NSRange) -> Void) {
    locate(NSRange(location: location, length: 0))
    replace("", NSRange(location: NSNotFound, length: 0))
  }
  static func wrap(_ pair: String, text: String, range: NSRange, replace: (String, NSRange) -> Void, locate: (NSRange) -> Void) {
    guard let first = pair.first, let last = pair.last else { return }
    replace(String(first) + text + String(last), range)
    move(to: range.location + String(first).utf16.count + text.utf16.count, replace: replace, locate: locate)
  }
  static func insert(_ pair: String, at location: Int, replace: (String, NSRange) -> Void, locate: (NSRange) -> Void) {
    wrap(pair, text: "", range: NSRange(location: location, length: 0), replace: replace, locate: locate)
  }
}

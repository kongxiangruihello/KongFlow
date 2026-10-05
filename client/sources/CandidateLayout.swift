import Foundation
import CoreGraphics

/// Pure geometry for the candidate window (no AppKit, no text engine state).
///
/// Coordinates are flipped: y grows downward from the window's top-left corner.
/// The window is sized to exactly `size`, so everything the layout places is visible;
/// there is no scroll view and nothing is computed from a previous layout.
struct CandidateLayout: Equatable {
  struct Metrics: Equatable {
    /// Space between the window edge and the content.
    var inset = CGSize(width: 10, height: 8)
    /// Space between a candidate's text and its highlight box.
    var itemPadding = CGSize(width: 6, height: 3)
    /// Horizontal gap between highlight boxes on one row (linear layout).
    var itemSpacing: CGFloat = 4
    /// Vertical gap between rows.
    var lineSpacing: CGFloat = 2
    /// Height of the footer strip (更多 / 收起, 全文); 0 hides it.
    var footerHeight: CGFloat = 0
    /// Smallest window width, e.g. to fit the footer buttons.
    var minWidth: CGFloat = 44
  }

  /// Window size.
  var size: CGSize = .zero
  /// Text rectangle of the preedit line, if shown.
  var preeditFrame: CGRect?
  /// Highlight-box rectangle of each candidate; its text sits inside, inset by `itemPadding`.
  var itemFrames: [CGRect] = []
  /// Footer strip at the bottom of the window, if shown.
  var footerFrame: CGRect?

  /// - Parameters:
  ///   - preedit: measured size of the preedit text, or nil when it is shown inline.
  ///   - items: measured text size of each candidate.
  ///   - maxContentWidth: widest a row may be (linear layout wraps beyond it).
  ///   - linear: true for candidates in a row that wraps; false for one per row.
  static func make(preedit: CGSize?, items: [CGSize], maxContentWidth: CGFloat, linear: Bool, metrics m: Metrics) -> CandidateLayout {
    var layout = CandidateLayout()
    layout.itemFrames = Array(repeating: .zero, count: items.count)
    let limit = max(maxContentWidth, 1)
    var y = m.inset.height
    var contentWidth: CGFloat = 0
    var placedLine = false

    if let preedit {
      layout.preeditFrame = CGRect(x: m.inset.width + m.itemPadding.width, y: y + m.itemPadding.height,
                                   width: preedit.width, height: preedit.height)
      contentWidth = preedit.width + 2 * m.itemPadding.width
      y += preedit.height + 2 * m.itemPadding.height + m.lineSpacing
      placedLine = true
    }

    func box(_ i: Int) -> CGSize {
      CGSize(width: ceil(items[i].width) + 2 * m.itemPadding.width, height: ceil(items[i].height) + 2 * m.itemPadding.height)
    }

    var row: [Int] = []
    var rowWidth: CGFloat = 0
    for i in items.indices {
      let size = box(i)
      if !row.isEmpty && (!linear || rowWidth + m.itemSpacing + size.width > limit) {
        let height = row.map { box($0).height }.max() ?? 0
        for j in row { layout.itemFrames[j].origin.y = y + (height - layout.itemFrames[j].height) / 2 }
        y += height + m.lineSpacing
        row = []
        rowWidth = 0
      }
      let x = row.isEmpty ? 0 : rowWidth + m.itemSpacing
      layout.itemFrames[i] = CGRect(x: m.inset.width + x, y: 0, width: size.width, height: size.height)
      rowWidth = x + size.width
      contentWidth = max(contentWidth, rowWidth)
      row.append(i)
      placedLine = true
    }
    if !row.isEmpty {
      let height = row.map { box($0).height }.max() ?? 0
      for j in row { layout.itemFrames[j].origin.y = y + (height - layout.itemFrames[j].height) / 2 }
      y += height + m.lineSpacing
    }
    if placedLine { y -= m.lineSpacing }
    y += m.inset.height

    let width = ceil(max(m.minWidth, contentWidth + 2 * m.inset.width))
    if m.footerHeight > 0 {
      layout.footerFrame = CGRect(x: 0, y: y, width: width, height: m.footerHeight)
      y += m.footerHeight
    }
    layout.size = CGSize(width: width, height: ceil(y))
    return layout
  }

  /// Index of the candidate whose highlight box contains `point`.
  func index(at point: CGPoint) -> Int? {
    itemFrames.firstIndex { $0.contains(point) }
  }
}

// Pure layout checks for the 0.34 candidate window (no AppKit, no Rime).
// Build: xcrun swiftc client/sources/CandidateLayout.swift tests/CandidateLayoutSmoke.swift -o /tmp/layout-smoke
import Foundation
import CoreGraphics

@main struct CandidateLayoutSmoke {
  static func check(_ layout: CandidateLayout, items: Int, maxContent: CGFloat, m: CandidateLayout.Metrics, linear: Bool) {
    let bodyBottom = layout.footerFrame?.minY ?? layout.size.height
    precondition(layout.itemFrames.count == items)
    for (i, f) in layout.itemFrames.enumerated() {
      // Everything placed is inside the window and above the footer: nothing can be clipped.
      precondition(f.minX >= m.inset.width - 0.01 && f.maxX <= layout.size.width - m.inset.width + 0.01, "item \(i) outside width")
      precondition(f.minY >= m.inset.height - 0.01 && f.maxY <= bodyBottom - m.inset.height + 0.01, "item \(i) outside height")
      precondition(layout.index(at: CGPoint(x: f.midX, y: f.midY)) == i, "hit test \(i)")
      for (j, g) in layout.itemFrames.enumerated() where j > i { precondition(!f.intersects(g), "items \(i) and \(j) overlap") }
    }
    if let footer = layout.footerFrame {
      precondition(abs(footer.maxY - layout.size.height) < 0.01 && footer.width == layout.size.width)
    }
    if !linear {
      for i in 1..<max(1, items) { precondition(layout.itemFrames[i].minY >= layout.itemFrames[i - 1].maxY, "stacked rows") }
    } else {
      // A row only exceeds the limit when it holds a single, too-wide candidate.
      let rows = Dictionary(grouping: layout.itemFrames, by: { $0.midY.rounded() })
      for row in rows.values where row.count > 1 {
        let width = (row.map(\.maxX).max() ?? 0) - (row.map(\.minX).min() ?? 0)
        precondition(width <= maxContent + 0.01, "row wider than limit")
      }
    }
    precondition(layout.size.width >= m.minWidth)
  }

  static func main() {
    var count = 0
    let widths: [CGFloat] = [28, 46, 64, 90, 140, 420, 900]
    for linear in [true, false] {
      for footer in [0.0, 26.0] as [CGFloat] {
        for maxContent in [180.0, 420.0, 900.0] as [CGFloat] {
          for n in [0, 1, 5, 9, 12, 18, 36] {
            var m = CandidateLayout.Metrics(); m.footerHeight = footer; m.minWidth = footer > 0 ? 140 : 44
            let items = (0..<n).map { CGSize(width: widths[$0 % widths.count], height: $0 % 3 == 0 ? 22 : 18) }
            for preedit in [nil, CGSize(width: 60, height: 18)] as [CGSize?] {
              let layout = CandidateLayout.make(preedit: preedit, items: items, maxContentWidth: maxContent, linear: linear, metrics: m)
              check(layout, items: n, maxContent: maxContent, m: m, linear: linear)
              if let p = layout.preeditFrame, let first = layout.itemFrames.first { precondition(p.maxY <= first.minY) }
              count += 1
            }
          }
        }
      }
    }
    // 展开 → 收起: the collapsed window is computed from scratch and is the same as a fresh one.
    var m = CandidateLayout.Metrics(); m.footerHeight = 26; m.minWidth = 140
    let nine = (0..<9).map { _ in CGSize(width: 64, height: 22) }
    let eighteen = (0..<18).map { _ in CGSize(width: 64, height: 22) }
    let fresh = CandidateLayout.make(preedit: nil, items: nine, maxContentWidth: 420, linear: true, metrics: m)
    let expanded = CandidateLayout.make(preedit: nil, items: eighteen, maxContentWidth: 420, linear: true, metrics: m)
    let collapsed = CandidateLayout.make(preedit: nil, items: nine, maxContentWidth: 420, linear: true, metrics: m)
    precondition(expanded.size.height > fresh.size.height && collapsed == fresh)
    print("PASS: \(count) candidate layouts, plus expand/collapse equality")
  }
}

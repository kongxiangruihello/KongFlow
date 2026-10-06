//
//  SquirrelPanel.swift
//  KongFlow candidate window
//
//  Rewritten for KongFlow 0.34. The previous window stacked a scroll view, a TextKit 2
//  text view, a shape mask built from the dirty rect and a separate footer; when the
//  candidate count changed in place (展开／收起) those layers could disagree and the
//  window showed a clipped or shifted box. This version measures every string, computes
//  the whole geometry with CandidateLayout, sizes the window to exactly that geometry,
//  and draws background, highlight and text in one pass of one view.
//

import AppKit

/// Draws the candidate window from a finished CandidateLayout. Holds no layout state of its own.
final class CandidateView: NSView {
  var layout = CandidateLayout()
  var theme = SquirrelTheme()
  var preeditText: NSAttributedString?
  var itemTexts: [NSAttributedString] = []
  var highlightedItemTexts: [NSAttributedString] = []
  var highlighted = -1
  var itemPadding = CGSize.zero

  override var isFlipped: Bool { true }
  override var isOpaque: Bool { false }

  override func draw(_ dirtyRect: NSRect) {
    // Always draw the whole window from the layout, whatever part AppKit asks for.
    NSColor.clear.setFill()
    bounds.fill()
    let radius = min(theme.cornerRadius, bounds.height / 2, bounds.width / 2)
    let background = NSBezierPath(roundedRect: bounds, xRadius: radius, yRadius: radius)
    theme.backgroundColor.setFill()
    background.fill()
    if let border = theme.borderColor, theme.borderLineWidth > 0 {
      let inset = theme.borderLineWidth / 2
      let edge = NSBezierPath(roundedRect: bounds.insetBy(dx: inset, dy: inset), xRadius: max(0, radius - inset), yRadius: max(0, radius - inset))
      edge.lineWidth = theme.borderLineWidth
      border.setStroke()
      edge.stroke()
    }

    let boxRadius = theme.hilitedCornerRadius > 0 ? min(theme.hilitedCornerRadius, 8) : 5
    for (i, frame) in layout.itemFrames.enumerated() {
      let color = i == highlighted ? theme.highlightedBackColor : theme.candidateBackColor
      if let color {
        color.setFill()
        NSBezierPath(roundedRect: frame, xRadius: boxRadius, yRadius: boxRadius).fill()
      }
    }
    if let preeditText, let frame = layout.preeditFrame {
      preeditText.draw(with: frame, options: [.usesLineFragmentOrigin], context: nil)
    }
    for (i, frame) in layout.itemFrames.enumerated() {
      let texts = i == highlighted ? highlightedItemTexts : itemTexts
      guard texts.indices.contains(i) else { continue }
      texts[i].draw(with: frame.insetBy(dx: itemPadding.width, dy: itemPadding.height), options: [.usesLineFragmentOrigin], context: nil)
    }
  }
}

final class SquirrelPanel: NSPanel {
  private let view = CandidateView()
  private let expansionButton = NSButton()
  private let detailButton = NSButton()
  private let detailScroll = NSScrollView()
  private let detailText = NSTextView()
  private var detailOpen = false
  var inputController: SquirrelInputController?

  var position: NSRect
  private var screenRect: NSRect = .zero

  private var lightTheme = SquirrelTheme()
  private var darkTheme = SquirrelTheme()
  private var currentTheme: SquirrelTheme {
    let dark = NSApp.effectiveAppearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua
    return dark && darkTheme.available ? darkTheme : lightTheme
  }

  private var statusMessage: String = ""
  private var statusTimer: Timer?

  private var preedit: String = ""
  private var selRange: NSRange = .empty
  private var caretPos: Int = 0
  private var candidates: [String] = .init()
  private var comments: [String] = .init()
  private var labels: [String] = .init()
  private var index: Int = 0
  private var cursorIndex: Int = 0
  private var scrollDirection: CGVector = .zero
  private var scrollTime: Date = .distantPast
  private var page: Int = 0
  private var lastPage: Bool = true

  private static let footerHeight: CGFloat = 26
  private static let detailHeight: CGFloat = 120

  init(position: NSRect) {
    self.position = position
    super.init(contentRect: position, styleMask: .nonactivatingPanel, backing: .buffered, defer: true)
    self.level = .init(Int(CGShieldingWindowLevel()))
    self.hasShadow = true
    self.isOpaque = false
    self.backgroundColor = .clear
    let contentView = NSView()
    contentView.addSubview(view)
    expansionButton.isBordered = false
    expansionButton.bezelStyle = .inline
    expansionButton.target = self
    expansionButton.action = #selector(toggleExpansion)
    contentView.addSubview(expansionButton)
    detailButton.isBordered = false
    detailButton.bezelStyle = .inline
    detailButton.target = self
    detailButton.action = #selector(toggleCandidateDetail)
    detailButton.toolTip = "查看／收起高亮候选全文（Control＋Return）"
    detailButton.setAccessibilityLabel("查看高亮候选全文")
    contentView.addSubview(detailButton)
    detailText.isEditable = false
    detailText.isSelectable = false
    detailText.drawsBackground = false
    detailText.font = .systemFont(ofSize: 14)
    detailText.textContainerInset = NSSize(width: 8, height: 8)
    detailText.isVerticallyResizable = true
    detailText.autoresizingMask = [.width]
    detailText.textContainer?.widthTracksTextView = true
    detailScroll.documentView = detailText
    detailScroll.drawsBackground = false
    detailScroll.hasVerticalScroller = true
    detailScroll.autohidesScrollers = true
    contentView.addSubview(detailScroll)
    self.contentView = contentView
  }

  // Toggle on the next run-loop turn so the window is not resized inside the button's click handling.
  @objc private func toggleExpansion() {
    DispatchQueue.main.async { [weak self] in self?.inputController?.toggleExpansion() }
  }
  @objc @discardableResult func toggleCandidateDetail() -> Bool {
    guard candidates.indices.contains(cursorIndex), candidates[cursorIndex].count > 28 else { return false }
    detailOpen.toggle()
    render()
    return true
  }
  /// Kept for the input controller; every render now starts from a fresh layout.
  func resetForRelayout() {}

  @objc private func quickCandidateAction(_ item: NSMenuItem) {
    guard let value = item.representedObject as? [String: String], let word = value["word"], let code = value["code"], let action = value["action"] else { return }
    if action == "phrase-new" || action == "phrase-edit" {
      inputController?.openCandidatePhrase(word: word, code: code, comment: value["comment"] ?? "", action: action == "phrase-edit" ? "edit" : "new")
    } else { inputController?.adjustQuickCandidate(word: word, code: code, action: action) }
  }

  var linear: Bool { currentTheme.linear }
  /// Vertical text is not supported by the KongFlow window; candidates are always horizontal text.
  var vertical: Bool { false }
  var inlinePreedit: Bool { currentTheme.inlinePreedit }
  var inlineCandidate: Bool { currentTheme.inlineCandidate }

  private func pointInView() -> NSPoint {
    view.convert(convertPoint(fromScreen: NSEvent.mouseLocation), from: nil)
  }
  private func candidateIndex(at point: NSPoint) -> Int? {
    guard let i = view.layout.index(at: point), i < candidates.count else { return nil }
    return i
  }

  // swiftlint:disable:next cyclomatic_complexity
  override func sendEvent(_ event: NSEvent) {
    let point = contentView!.convert(convertPoint(fromScreen: NSEvent.mouseLocation), from: nil)
    let controls: [NSView] = [expansionButton, detailButton, detailScroll]
    for control in controls where !control.isHidden && control.frame.contains(point) {
      super.sendEvent(event); return
    }
    switch event.type {
    case .rightMouseDown:
      guard let candidateIndex = candidateIndex(at: pointInView()),
            let code = inputController?.quickInput(candidateIndex: candidateIndex) else { return }
      let menu = NSMenu(); menu.autoenablesItems = false
      for (title, action) in [("置顶", "pin"), ("取消置顶", "unpin"), ("降低优先级", "lower"), ("仅在当前拼音下隐藏", "block_code"), ("所有拼音下隐藏", "block")] {
        let item = NSMenuItem(title: title, action: #selector(quickCandidateAction(_:)), keyEquivalent: "")
        item.isEnabled = action.hasPrefix("block") || inputController?.quickReorderingAvailable(candidateIndex: candidateIndex) == true
        item.target = self; item.representedObject = ["word": candidates[candidateIndex], "code": code, "action": action]; menu.addItem(item)
      }
      menu.addItem(.separator())
      var phraseActions = [("保存为短语…", "phrase-new")]
      let comment = comments.indices.contains(candidateIndex) ? comments[candidateIndex] : ""
      if inputController?.hasCandidatePhrase(word: candidates[candidateIndex], code: code, comment: comment) == true { phraseActions.append(("编辑对应短语…", "phrase-edit")) }
      for (title, action) in phraseActions {
        let item = NSMenuItem(title: title, action: #selector(quickCandidateAction(_:)), keyEquivalent: "")
        item.target = self; item.representedObject = ["word": candidates[candidateIndex], "code": code, "comment": comment, "action": action]
        item.isEnabled = candidates[candidateIndex].count <= 500
        menu.addItem(item)
      }
      // The panel sits at the shielding window level, far above pop-up menus, so the menu used to
      // open underneath the candidates. Drop the panel just below menus while it is open
      // (popUp returns when the menu closes), then restore it.
      let savedLevel = level
      level = NSWindow.Level(rawValue: NSWindow.Level.popUpMenu.rawValue - 1)
      menu.popUp(positioning: nil, at: NSEvent.mouseLocation, in: nil)
      level = savedLevel
      return
    case .leftMouseDown:
      if let i = candidateIndex(at: pointInView()) { index = i }
    case .leftMouseUp:
      if let i = candidateIndex(at: pointInView()), i == index {
        _ = inputController?.selectCandidate(i)
      }
    case .mouseEntered:
      acceptsMouseMovedEvents = true
    case .mouseExited:
      acceptsMouseMovedEvents = false
      if cursorIndex != index { setHighlight(index) }
    case .mouseMoved:
      if let i = candidateIndex(at: pointInView()), i != cursorIndex { setHighlight(i) }
    case .scrollWheel:
      handleScroll(event)
    default:
      break
    }
    super.sendEvent(event)
  }

  private func handleScroll(_ event: NSEvent) {
    if event.phase == .began {
      scrollDirection = .zero
    } else if event.phase == .ended || (event.phase == .init(rawValue: 0) && event.momentumPhase != .init(rawValue: 0)) {
      if abs(scrollDirection.dx) > abs(scrollDirection.dy) && abs(scrollDirection.dx) > 10 {
        _ = inputController?.page(up: scrollDirection.dx < 0 ? false : true)
      } else if abs(scrollDirection.dx) < abs(scrollDirection.dy) && abs(scrollDirection.dy) > 10 {
        _ = inputController?.page(up: scrollDirection.dy > 0)
      }
      scrollDirection = .zero
    } else if event.phase == .init(rawValue: 0) && event.momentumPhase == .init(rawValue: 0) {
      if scrollTime.timeIntervalSinceNow < -1 { scrollDirection = .zero }
      scrollTime = .now
      if (scrollDirection.dy >= 0 && event.scrollingDeltaY > 0) || (scrollDirection.dy <= 0 && event.scrollingDeltaY < 0) {
        scrollDirection.dy += event.scrollingDeltaY
      } else {
        scrollDirection = .zero
      }
      if abs(scrollDirection.dy) > 10 {
        _ = inputController?.page(up: scrollDirection.dy > 0)
        scrollDirection = .zero
      }
    } else {
      scrollDirection.dx += event.scrollingDeltaX
      scrollDirection.dy += event.scrollingDeltaY
    }
  }

  /// Mouse hover only moves the highlight; geometry does not change, so no relayout.
  private func setHighlight(_ i: Int) {
    cursorIndex = i
    view.highlighted = i
    view.needsDisplay = true
  }

  func hide() {
    detailOpen = false
    statusTimer?.invalidate()
    statusTimer = nil
    orderOut(nil)
  }

  // swiftlint:disable:next function_parameter_count
  func update(preedit: String, selRange: NSRange, caretPos: Int, candidates: [String], comments: [String], labels: [String], highlighted index: Int, page: Int, lastPage: Bool, update: Bool) {
    if update {
      if self.candidates != candidates { detailOpen = false }
      self.preedit = preedit
      self.selRange = selRange
      self.caretPos = caretPos
      self.candidates = candidates
      self.comments = comments
      self.labels = labels
      self.index = index
      self.page = page
      self.lastPage = lastPage
    }
    cursorIndex = index

    if !candidates.isEmpty || !preedit.isEmpty {
      statusMessage = ""
      statusTimer?.invalidate()
      statusTimer = nil
      render()
    } else if !statusMessage.isEmpty {
      show(status: statusMessage)
      statusMessage = ""
    } else if statusTimer == nil {
      hide()
    }
  }

  func updateStatus(long longMessage: String, short shortMessage: String) {
    switch currentTheme.statusMessageType {
    case .mix:
      statusMessage = shortMessage.isEmpty ? longMessage : shortMessage
    case .long:
      statusMessage = longMessage
    case .short:
      if !shortMessage.isEmpty {
        statusMessage = shortMessage
      } else if let initial = longMessage.first {
        statusMessage = String(initial)
      } else {
        statusMessage = ""
      }
    }
  }

  func load(config: SquirrelConfig, forDarkMode isDark: Bool) {
    let theme = SquirrelTheme()
    theme.load(config: config, dark: isDark)
    if isDark { darkTheme = theme } else { lightTheme = theme }
  }

  // MARK: - Building and placing the window

  private func candidateText(_ i: Int, highlighted: Bool, theme: SquirrelTheme) -> NSAttributedString {
    let attrs = highlighted ? theme.highlightedAttrs : theme.attrs
    let labelAttrs = highlighted ? theme.labelHighlightedAttrs : theme.labelAttrs
    let commentAttrs = highlighted ? theme.commentHighlightedAttrs : theme.commentAttrs
    let label: String
    if !theme.candidateFormat.contains("[label]") {
      label = ""
    } else if labels.count > 1 && i < labels.count {
      label = labels[i]
    } else if labels.count == 1 && i < labels[0].count {
      label = String(labels[0][labels[0].index(labels[0].startIndex, offsetBy: i)])
    } else {
      label = "\(i + 1)"
    }
    let full = candidates[i].precomposedStringWithCanonicalMapping
    let candidate = full.count > 28 ? String(full.prefix(28)) + "…" : full
    let comment = comments.indices.contains(i) ? comments[i].precomposedStringWithCanonicalMapping : ""
    let templateLabel = ["日期", "时间", "落款", "模板"].contains(comment)
    let format = templateLabel && !theme.candidateFormat.contains("[comment]") ? theme.candidateFormat + " [comment]" : theme.candidateFormat

    // Walk the format once, giving each part its own attributes.
    let text = NSMutableAttributedString()
    var rest = Substring(format)
    let tokens: [(String, String, [NSAttributedString.Key: Any])] = [("[label]", label, labelAttrs), ("[candidate]", candidate, attrs), ("[comment]", comment, commentAttrs)]
    while !rest.isEmpty {
      if let match = tokens.first(where: { rest.hasPrefix($0.0) }) {
        text.append(NSAttributedString(string: match.1, attributes: match.2))
        rest = rest.dropFirst(match.0.count)
      } else {
        text.append(NSAttributedString(string: String(rest.first!), attributes: labelAttrs))
        rest = rest.dropFirst()
      }
    }
    // Trim spaces left by an empty comment so the highlight box hugs the text.
    while text.length > 0 && text.string.hasSuffix(" ") { text.deleteCharacters(in: NSRange(location: text.length - 1, length: 1)) }
    return text
  }

  private func measure(_ text: NSAttributedString, maxWidth: CGFloat) -> CGSize {
    let rect = text.boundingRect(with: NSSize(width: maxWidth, height: 10_000), options: [.usesLineFragmentOrigin], context: nil)
    return CGSize(width: ceil(rect.width), height: ceil(rect.height))
  }

  private func currentScreen() {
    let screens = NSScreen.screens
    if let i = CandidateGeometry.screenIndex(anchor: position, frames: screens.map { $0.frame }) {
      screenRect = screens[i].visibleFrame
    } else {
      screenRect = NSRect(x: 0, y: 0, width: 1024, height: 768)
    }
  }

  private func render() {
    currentScreen()
    let theme = currentTheme
    appearance = theme.native || darkTheme.available ? NSApp.effectiveAppearance : NSAppearance(named: .aqua)

    let showExpansion = !candidates.isEmpty && inputController?.expansionAvailable == true
    let showDetail = candidates.indices.contains(cursorIndex) && candidates[cursorIndex].count > 28
    let footer = showExpansion || showDetail
    let detailHeight: CGFloat = showDetail && detailOpen ? Self.detailHeight : 0

    var metrics = CandidateLayout.Metrics()
    metrics.inset = CGSize(width: max(8, theme.borderWidth + 2), height: max(6, theme.borderHeight + 2))
    metrics.lineSpacing = max(2, theme.linespace)
    metrics.footerHeight = footer ? Self.footerHeight : 0
    metrics.minWidth = showDetail ? 280 : (showExpansion ? 140 : 44)
    // 候选疏密（设置 → 候选外观）。
    switch NSApp.squirrelAppDelegate.config?.getString("kongime/density") ?? "standard" {
    case "compact":
      metrics.itemPadding = CGSize(width: 4, height: 2)
      metrics.itemSpacing = 2
      metrics.lineSpacing = 1
      metrics.inset = CGSize(width: max(6, metrics.inset.width - 3), height: max(4, metrics.inset.height - 2))
    case "loose":
      metrics.itemPadding = CGSize(width: 8, height: 5)
      metrics.itemSpacing = 8
      metrics.lineSpacing += 4
      metrics.inset = CGSize(width: metrics.inset.width + 4, height: metrics.inset.height + 3)
    default:
      break
    }

    var preeditText: NSAttributedString?
    if !preedit.isEmpty {
      let text = NSMutableAttributedString(string: preedit, attributes: theme.preeditAttrs)
      if selRange.location != NSNotFound && NSMaxRange(selRange) <= text.length {
        text.addAttributes(theme.preeditHighlightedAttrs, range: selRange)
      }
      preeditText = text
    }
    let normal = candidates.indices.map { candidateText($0, highlighted: false, theme: theme) }
    let highlightedTexts = candidates.indices.map { candidateText($0, highlighted: true, theme: theme) }

    // Prefer a third of the screen; widen when the window would not fit above or below the line.
    let gap = inputController?.candidateGap(default: theme.candidateGap) ?? theme.candidateGap
    let room = max(position.minY - screenRect.minY, screenRect.maxY - position.maxY) - gap - detailHeight
    let scale = theme.font.pointSize / 12
    var layout = CandidateLayout()
    for ratio in [min(1, 1.0 / 3 + scale / 12), 0.6, 0.95] {
      let maxContent = screenRect.width * ratio - metrics.inset.width * 2
      let itemLimit = maxContent - metrics.itemPadding.width * 2
      let sizes = zip(normal, highlightedTexts).map { pair -> CGSize in
        let a = measure(pair.0, maxWidth: itemLimit), b = measure(pair.1, maxWidth: itemLimit)
        return CGSize(width: max(a.width, b.width), height: max(a.height, b.height))
      }
      layout = CandidateLayout.make(preedit: preeditText.map { measure($0, maxWidth: itemLimit) }, items: sizes,
                                    maxContentWidth: maxContent, linear: theme.linear, metrics: metrics)
      if layout.size.height <= room { break }
    }

    view.layout = layout
    view.theme = theme
    view.preeditText = preeditText
    view.itemTexts = normal
    view.highlightedItemTexts = highlightedTexts
    view.itemPadding = metrics.itemPadding
    view.highlighted = cursorIndex

    var frame = NSRect(x: position.minX, y: 0, width: layout.size.width, height: layout.size.height + detailHeight)
    frame = CandidateGeometry.avoidingLine(frame, anchor: position, in: screenRect, gap: gap)
    setFrame(frame, display: false)

    // Content view is not flipped: y = 0 is the bottom. The candidate view sits on top,
    // the detail text (when open) below it.
    let content = contentView!
    view.frame = NSRect(x: 0, y: frame.height - layout.size.height, width: frame.width, height: layout.size.height)
    layoutFooter(layout: layout, showExpansion: showExpansion, showDetail: showDetail, theme: theme)
    detailScroll.isHidden = detailHeight == 0
    detailScroll.frame = NSRect(x: 0, y: 0, width: frame.width, height: min(detailHeight, max(0, frame.height - layout.size.height)))
    if !detailScroll.isHidden {
      detailScroll.wantsLayer = true
      detailScroll.layer?.backgroundColor = theme.backgroundColor.cgColor
      detailScroll.layer?.cornerRadius = min(theme.cornerRadius, 8)
      detailText.string = candidates[cursorIndex]
      detailText.setAccessibilityValue(candidates[cursorIndex])
      detailText.frame.size.width = detailScroll.contentSize.width
      detailText.sizeToFit()
    }
    content.needsDisplay = true
    view.needsDisplay = true
    alphaValue = theme.alpha
    orderFront(nil)
    display()
    invalidateShadow()
  }

  private func layoutFooter(layout: CandidateLayout, showExpansion: Bool, showDetail: Bool, theme: SquirrelTheme) {
    guard let footer = layout.footerFrame else {
      expansionButton.isHidden = true
      detailButton.isHidden = true
      return
    }
    let color = (theme.labelHighlightedAttrs[.foregroundColor] as? NSColor) ?? .secondaryLabelColor
    let font = NSFont.systemFont(ofSize: 13, weight: .medium)
    // Footer frame is in the candidate view's flipped space; convert to the content view.
    let footerY = view.frame.minY + (layout.size.height - footer.maxY)
    let open = inputController?.expansionIsOpen == true
    let shortcut = inputController?.expansionShortcutLabel ?? "Tab"
    expansionButton.isHidden = !showExpansion
    expansionButton.attributedTitle = NSAttributedString(string: open ? "收起 ▴" : "更多 ▾", attributes: [.foregroundColor: color, .font: font])
    expansionButton.toolTip = (open ? "收起候选" : "展开更多候选") + "（" + shortcut + "）"
    expansionButton.setAccessibilityLabel(expansionButton.toolTip)
    let width = ceil(expansionButton.attributedTitle.size().width) + 16
    expansionButton.frame = NSRect(x: max(0, footer.width - width - 8), y: footerY, width: width, height: footer.height)
    detailButton.isHidden = !showDetail
    detailButton.attributedTitle = NSAttributedString(string: detailOpen ? "收起全文" : "全文", attributes: [.foregroundColor: color, .font: font])
    detailButton.frame = NSRect(x: 8, y: footerY, width: ceil(detailButton.attributedTitle.size().width) + 16, height: footer.height)
  }

  func show(status message: String) {
    let theme = currentTheme
    currentScreen()
    let text = NSAttributedString(string: message, attributes: theme.attrs)
    var metrics = CandidateLayout.Metrics()
    metrics.inset = CGSize(width: max(8, theme.borderWidth + 2), height: max(6, theme.borderHeight + 2))
    let size = measure(text, maxWidth: screenRect.width / 3)
    let layout = CandidateLayout.make(preedit: nil, items: [size], maxContentWidth: screenRect.width / 3, linear: true, metrics: metrics)
    view.layout = layout
    view.theme = theme
    view.preeditText = nil
    view.itemTexts = [text]
    view.highlightedItemTexts = [text]
    view.itemPadding = metrics.itemPadding
    view.highlighted = -1
    expansionButton.isHidden = true
    detailButton.isHidden = true
    detailScroll.isHidden = true
    let gap = inputController?.candidateGap(default: theme.candidateGap) ?? theme.candidateGap
    let frame = CandidateGeometry.avoidingLine(NSRect(origin: .zero, size: layout.size).offsetBy(dx: position.minX, dy: 0), anchor: position, in: screenRect, gap: gap)
    setFrame(frame, display: false)
    view.frame = NSRect(origin: .zero, size: frame.size)
    view.needsDisplay = true
    alphaValue = theme.alpha
    orderFront(nil)
    display()
    invalidateShadow()

    statusTimer?.invalidate()
    statusTimer = Timer.scheduledTimer(withTimeInterval: SquirrelTheme.showStatusDuration, repeats: false) { [weak self] _ in
      self?.hide()
    }
  }
}

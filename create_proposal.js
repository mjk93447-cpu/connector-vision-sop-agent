"use strict";
const pptxgen = require("pptxgenjs");

// ─── DESIGN TOKENS ────────────────────────────────────────────────────────────
const C = {
  samsung:   "1428A0",
  samsungDk: "0D1F80",
  sdnBlue:   "1565C0",
  sdvGreen:  "1B7A3E",
  sdnRow:    "DBEAFE",
  sdvRow:    "DCFCE7",
  white:     "FFFFFF",
  dark:      "1A1A2E",
  muted:     "64748B",
  headerBg:  "F0F4FF",
  redHdr:    "C0392B",
  orange:    "E67E22",
  yellow:    "FFC107",
  lightBlue: "EBF5FF",
  lightGrn:  "F0FFF4",
  cream:     "FFF8E1",
  f5:        "F5F5F5",
  bright:    "0D6EFD",
  okFill:    "E8F5E9",
  okText:    "166534",
  errFill:   "FEE2E2",
  errText:   "991B1B",
};
const makeShadow = () => ({ type: "outer", blur: 6, offset: 2, color: "000000", opacity: 0.12 });

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10" × 5.625"

// ─── HELPERS ──────────────────────────────────────────────────────────────────
function addHeaderBand(slide) {
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 1.0, fill: { color: C.headerBg }, line: { color: C.headerBg } });
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.14, h: 5.625, fill: { color: C.samsung }, line: { color: C.samsung } });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 1 — COVER (표지)
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.white };

  // Samsung blue top block
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 1.36, fill: { color: C.samsung }, line: { color: C.samsung } });
  // Darker left accent bar (depth effect)
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.16, h: 5.625, fill: { color: C.samsungDk }, line: { color: C.samsungDk } });
  // Thin separator below header
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 1.36, w: 10, h: 0.06, fill: { color: "C8D8F0" }, line: { color: "C8D8F0" } });

  // Header text
  s.addText("SAMSUNG Display", {
    x: 0.36, y: 0.2, w: 6.5, h: 0.44, fontSize: 22, bold: true, color: C.white, fontFace: "Arial Black", margin: 0,
  });
  s.addText("Manufacturing Process Innovation  ·  Project Proposal", {
    x: 0.36, y: 0.7, w: 7.5, h: 0.28, fontSize: 10.5, color: "A8C4FF", fontFace: "Calibri", margin: 0,
  });
  s.addText("CONFIDENTIAL", {
    x: 7.0, y: 0.74, w: 2.8, h: 0.26, fontSize: 9, bold: true, color: "6888CC", fontFace: "Calibri", align: "right", margin: 0,
  });

  // Project label (small, spaced)
  s.addText("AI  SOP  AGENT", {
    x: 0.5, y: 1.62, w: 5, h: 0.28, fontSize: 10, bold: true, color: C.muted, charSpacing: 5, fontFace: "Calibri", margin: 0,
  });

  // Thin blue divider line
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.96, w: 9, h: 0.05, fill: { color: C.samsung }, line: { color: C.samsung } });

  // Main titles
  s.addText("Automated SOP Execution", {
    x: 0.5, y: 2.06, w: 9.2, h: 0.72, fontSize: 38, bold: true, fontFace: "Arial Black", color: C.samsung, margin: 0,
  });
  s.addText("for Production Line Efficiency", {
    x: 0.5, y: 2.8, w: 9.2, h: 0.52, fontSize: 22, bold: true, fontFace: "Arial Black", color: "3A5AD0", margin: 0,
  });

  // Description
  s.addText("Reducing 30+ hrs / line / month of repetitive SOP execution through AI-driven automation.", {
    x: 0.5, y: 3.42, w: 8.8, h: 0.28, fontSize: 12, color: C.muted, fontFace: "Calibri", margin: 0,
  });
  s.addText("On-site validation pilot proposal  ·  SDN (India)  ·  SDV (Vietnam)", {
    x: 0.5, y: 3.72, w: 8.8, h: 0.26, fontSize: 12, color: C.muted, fontFace: "Calibri", margin: 0,
  });

  // Bottom info strip
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 4.6, w: 10, h: 1.0, fill: { color: C.headerBg }, line: { color: C.headerBg } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 4.6, w: 10, h: 0.05, fill: { color: C.samsung }, line: { color: C.samsung } });

  const infoItems = [
    { label: "TARGET SITE",    value: "SDN India  ·  SDV Vietnam" },
    { label: "PROJECT PHASE",  value: "Pilot Registration" },
    { label: "PREPARED",       value: "2026 Q2" },
  ];
  infoItems.forEach((item, i) => {
    const x = 0.9 + i * 3.0;
    s.addText(item.label, { x, y: 4.7, w: 2.7, h: 0.22, fontSize: 8, bold: true, color: C.muted, charSpacing: 1, fontFace: "Calibri", align: "center", margin: 0 });
    s.addText(item.value,  { x, y: 4.94, w: 2.7, h: 0.28, fontSize: 12, bold: true, color: C.dark, fontFace: "Calibri", align: "center", margin: 0 });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 3.8, y: 4.76, w: 0.05, h: 0.56, fill: { color: "C0D0E8" }, line: { color: "C0D0E8" } });
  s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 4.76, w: 0.05, h: 0.56, fill: { color: "C0D0E8" }, line: { color: "C0D0E8" } });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 2 — PROJECT SUMMARY TABLE (프로젝트 요약표)
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  addHeaderBand(s);

  s.addText("02 / 09", { x: 8.8, y: 0.08, w: 1.0, h: 0.2, fontSize: 9, color: C.muted, align: "right" });
  s.addText("Project Summary", {
    x: 0.5, y: 0.08, w: 8, h: 0.52, fontSize: 22, bold: true, fontFace: "Arial Black", color: C.samsung, margin: 0,
  });
  s.addText("AI SOP Agent  —  Automated SOP Execution System  ·  On-Site Validation Pilot Proposal", {
    x: 0.5, y: 0.66, w: 9.0, h: 0.26, fontSize: 10.5, color: C.muted, fontFace: "Calibri", margin: 0,
  });

  // Summary table (10 rows, alternating Samsung blue / dark navy left label)
  const sumRows = [
    { label: "Project Name",     value: "AI SOP Agent — Automated SOP Execution System for Production Line SOPs",                                                       alt: true  },
    { label: "Division / Site",  value: "SDN — Samsung Display India  ·  SDV — Samsung Display Vietnam",                                                               alt: false },
    { label: "Objective",        value: "Eliminate manual, repetitive SOP execution time; automatically generate audit logs at every step",                             alt: true  },
    { label: "Background",       value: "SDN 7 lines × 30 hrs/mo = 210 hrs/mo  ·  SDV ~150 lines ≈ 4,500 hrs/mo  →  labor cost $897K+/yr (1 SOP type only)",          alt: false },
    { label: "Pilot Scope",      value: "SDN — 1 production line, 1 SOP type, ~3 months  →  Measure execution time vs. manual baseline",                              alt: true  },
    { label: "Deployment Path",  value: "Phase 1: SDN 1-line pilot  →  Phase 2: SDN full expansion (14 lines)  →  Phase 3: SDV planning (data-driven)",               alt: false },
    { label: "Expected ROI",     value: "1 SOP type: $897K/yr  ·  3 types: $2.7M/yr  ·  10 types: ~$9M/yr  (SDN 14L + SDV 180L, labor reallocation only)",            alt: true,  highlight: true },
    { label: "Resources Needed", value: "Project registration  ·  Pilot line access (1 line)  ·  PC installation permission  ·  IE engineer ~20% part-time",           alt: false },
    { label: "Build Status",     value: "646 automated tests · 92%+ code coverage · Fully offline · Runs on existing line PC — ready for pilot deployment",            alt: true  },
    { label: "Approval Request", value: "✅  Approve project registration  +  Grant pilot line access  (bounded, reversible commitment)",                              alt: false, highlight: true },
  ];

  const tableData = sumRows.map(r => {
    const lFill = r.alt ? C.samsung : "0D2A6E";
    const vFill = r.highlight ? "D6E8FF" : (r.alt ? C.lightBlue : C.white);
    const vColor = r.highlight ? C.samsung : C.dark;
    return [
      { text: r.label, options: { fill: { color: lFill }, bold: true, color: C.white, fontSize: 10, valign: "middle" } },
      { text: r.value, options: { fill: { color: vFill }, color: vColor, fontSize: 10, bold: !!r.highlight, valign: "middle" } },
    ];
  });
  s.addTable(tableData, { x: 0.3, y: 1.04, w: 9.4, colW: [1.9, 7.5], rowH: 0.42, border: { pt: 0.5, color: "C8D8F0" } });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 3 — THE PROBLEM (unified bright theme)
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  addHeaderBand(s);

  s.addText("03 / 09", { x: 8.8, y: 0.08, w: 1.0, h: 0.2, fontSize: 9, color: C.muted, align: "right" });
  s.addText("30 Hours.  Every Line.  Every Month.", {
    x: 0.5, y: 0.1, w: 9.1, h: 0.56,
    fontSize: 28, bold: true, fontFace: "Arial Black", color: C.samsung, align: "left", margin: 0,
  });
  s.addText("Repetitive SOP execution is consuming qualified engineer time at every model change.", {
    x: 0.5, y: 0.72, w: 9.0, h: 0.26,
    fontSize: 11, color: C.muted, fontFace: "Calibri", align: "left", margin: 0,
  });

  // ── LEFT: Timeline label
  s.addText("MODEL CHANGE DAY  —  ENGINEER TIMELINE", {
    x: 0.5, y: 1.1, w: 5.2, h: 0.24,
    fontSize: 9, bold: true, color: C.samsung, charSpacing: 2, fontFace: "Calibri", margin: 0,
  });

  // Timeline bars (colored fills, white text inside — works on white bg)
  const bars = [
    { y: 1.38, w: 4.8, fill: C.samsung,  alpha: 0,  label: "08:00    SOP sequence begins — Step 1 / 40" },
    { y: 1.86, w: 4.0, fill: C.sdnBlue,  alpha: 0,  label: "09:30    Step 18 / 40 — focus begins to fade" },
    { y: 2.34, w: 3.2, fill: "1E5FB0",   alpha: 25, label: "10:45    Step 31 / 40 — 4th line today" },
    { y: 2.82, w: 2.4, fill: "2878CC",   alpha: 40, label: "11:30    Done? (Step 37 or 38?)" },
  ];
  bars.forEach(b => {
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y: b.y, w: b.w, h: 0.38,
      fill: { color: b.fill, transparency: b.alpha }, line: { color: b.fill, transparency: b.alpha },
    });
    s.addText(b.label, { x: 0.62, y: b.y + 0.05, w: b.w - 0.2, h: 0.28, fontSize: 10, color: C.white, fontFace: "Calibri", margin: 0 });
  });
  s.addText("← ~30 hrs / line / month on fixed-script tasks", {
    x: 0.5, y: 3.28, w: 5.0, h: 0.28,
    fontSize: 11, italic: true, color: C.muted, fontFace: "Calibri", margin: 0,
  });

  // ── RIGHT: 3 stat boxes (light blue on white bg)
  const boxes = [
    { y: 1.1,  icon: "⏱", big: "30 hrs",    sub: "per line / per month",                  iconBg: C.samsung },
    { y: 2.18, icon: "⚠", big: "Inevitable", sub: "Human error at scale",                  iconBg: C.redHdr  },
    { y: 3.26, icon: "📋", big: "Incomplete", sub: "Audit records — written after the fact", iconBg: "5D6D7E" },
  ];
  boxes.forEach(b => {
    s.addShape(pres.shapes.RECTANGLE, {
      x: 5.9, y: b.y, w: 3.7, h: 0.95,
      fill: { color: C.lightBlue }, line: { color: C.samsung, pt: 1.5 }, shadow: makeShadow(),
    });
    s.addShape(pres.shapes.OVAL, { x: 6.0, y: b.y + 0.22, w: 0.42, h: 0.42, fill: { color: b.iconBg }, line: { color: b.iconBg } });
    s.addText(b.icon, { x: 6.0, y: b.y + 0.22, w: 0.42, h: 0.42, fontSize: 14, align: "center", valign: "middle", margin: 0 });
    s.addText(b.big, { x: 6.52, y: b.y + 0.06, w: 2.95, h: 0.42, fontSize: 22, bold: true, color: C.samsung, fontFace: "Calibri", margin: 0 });
    s.addText(b.sub, { x: 6.52, y: b.y + 0.5,  w: 2.95, h: 0.36, fontSize: 9.5, color: C.dark, fontFace: "Calibri", margin: 0 });
  });

  // ── Bottom hero callout (Samsung blue bar — strong on white)
  s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 4.6, w: 9.2, h: 0.78, fill: { color: C.samsung }, line: { color: C.samsung } });
  s.addText("SDN (India):  7 lines  =  210 hrs / month    |    SDV (Vietnam):  ~150 lines  =  4,500 hrs / month", {
    x: 0.4, y: 4.6, w: 9.2, h: 0.78,
    fontSize: 13, bold: true, color: C.white, fontFace: "Calibri", align: "center", valign: "middle", margin: 0,
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 4 — WHAT IT DOES
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  addHeaderBand(s);

  s.addText("04 / 09", { x: 8.8, y: 0.08, w: 1.0, h: 0.2, fontSize: 9, color: C.muted, align: "right" });
  s.addText("Reads the Screen.  Follows the SOP.  Logs Every Step.", {
    x: 0.5, y: 0.08, w: 9.1, h: 0.72,
    fontSize: 24, bold: true, fontFace: "Arial Black", color: C.samsung, align: "left", margin: 0,
  });
  s.addText("Runs on the existing line PC — fully offline, no new hardware required.", {
    x: 0.5, y: 0.76, w: 9.0, h: 0.24,
    fontSize: 11, color: C.muted, fontFace: "Calibri", margin: 0,
  });

  // ── Human box (left)
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 4.2, h: 1.98, fill: { color: "FFF5F5" }, line: { color: "E0C0C0", pt: 1 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 4.2, h: 0.34, fill: { color: C.redHdr }, line: { color: C.redHdr } });
  s.addText("👤   HUMAN ENGINEER", { x: 0.55, y: 1.07, w: 4.1, h: 0.3, fontSize: 11, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });

  const humanSteps = [
    "👁   Look at the screen",
    "🧠   Remember which step",
    "✋   Click / type",
    "🤔   Did I do step 23?",
    "📝   Fill in log sheet  (later, from memory)",
  ];
  humanSteps.forEach((t, i) => {
    const bg = i % 2 === 0 ? "FFF0F0" : "FFF5F5";
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.39 + i * 0.3, w: 4.2, h: 0.3, fill: { color: bg }, line: { color: bg } });
    s.addText(t, { x: 0.6, y: 1.41 + i * 0.3, w: 4.0, h: 0.26, fontSize: 10.5, color: C.dark, fontFace: "Calibri", margin: 0 });
  });
  s.addText("Risk: fatigue  ·  pressure  ·  context switching", {
    x: 0.55, y: 2.88, w: 4.1, h: 0.22, fontSize: 9, italic: true, color: C.redHdr, fontFace: "Calibri", margin: 0,
  });

  // Arrow
  s.addText("▶", { x: 4.78, y: 1.75, w: 0.44, h: 0.4, fontSize: 22, bold: true, color: C.samsung, align: "center", margin: 0 });

  // ── Agent box (right)
  s.addShape(pres.shapes.RECTANGLE, { x: 5.3, y: 1.05, w: 4.2, h: 1.98, fill: { color: "F2FFF5" }, line: { color: "B0D8C0", pt: 1 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 5.3, y: 1.05, w: 4.2, h: 0.34, fill: { color: C.sdvGreen }, line: { color: C.sdvGreen } });
  s.addText("🤖   AI SOP AGENT", { x: 5.35, y: 1.07, w: 4.1, h: 0.3, fontSize: 11, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });

  const agentSteps = [
    "👁   Vision AI reads screen state",
    "🧠   LLM selects next SOP step",
    "✋   Automated input executes",
    "✅   Screen state verified",
    "📸   Timestamp + screenshot logged",
  ];
  agentSteps.forEach((t, i) => {
    const bg = i % 2 === 0 ? "E8FFF0" : "F2FFF5";
    s.addShape(pres.shapes.RECTANGLE, { x: 5.3, y: 1.39 + i * 0.3, w: 4.2, h: 0.3, fill: { color: bg }, line: { color: bg } });
    s.addText(t, { x: 5.4, y: 1.41 + i * 0.3, w: 4.0, h: 0.26, fontSize: 10.5, color: C.dark, fontFace: "Calibri", margin: 0 });
  });
  s.addText("Result: identical every time, zero logging overhead", {
    x: 5.35, y: 2.88, w: 4.1, h: 0.22, fontSize: 9, italic: true, color: C.sdvGreen, fontFace: "Calibri", margin: 0,
  });

  // ── 4-box architecture
  s.addText("HOW IT WORKS", {
    x: 0.5, y: 3.18, w: 4.0, h: 0.24, fontSize: 9, bold: true, color: C.samsung, charSpacing: 3, fontFace: "Calibri", margin: 0,
  });

  const archBoxes = [
    { x: 0.5,  fill: C.sdnBlue,  icon: "👁",  title: "EYES",  body1: "Computer Vision",  body2: "Detects buttons,",  body3: "menus, fields" },
    { x: 2.9,  fill: C.samsung,  icon: "🧠",  title: "BRAIN", body1: "Local AI  (LLM)",  body2: "Offline — zero",    body3: "data sent out" },
    { x: 5.3,  fill: C.bright,   icon: "✋",  title: "HANDS", body1: "Automated Input",  body2: "Keyboard & mouse,", body3: "state-verified" },
    { x: 7.7,  fill: C.orange,   icon: "📋",  title: "LOG",   body1: "Auto-generated",   body2: "Timestamp + shot",  body3: "every step" },
  ];
  archBoxes.forEach((b, i) => {
    s.addShape(pres.shapes.RECTANGLE, { x: b.x, y: 3.46, w: 2.1, h: 1.88, fill: { color: C.lightBlue }, line: { color: "C8D8F0", pt: 1 }, shadow: makeShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: b.x, y: 3.46, w: 2.1, h: 0.38, fill: { color: b.fill }, line: { color: b.fill } });
    s.addText(`${b.icon}  ${b.title}`, { x: b.x + 0.05, y: 3.48, w: 2.0, h: 0.34, fontSize: 11, bold: true, color: C.white, fontFace: "Calibri", align: "center", margin: 0 });
    s.addText(b.body1, { x: b.x + 0.05, y: 3.9,  w: 2.0, h: 0.28, fontSize: 11, bold: true, color: C.dark, fontFace: "Calibri", align: "center", margin: 0 });
    s.addText(b.body2, { x: b.x + 0.05, y: 4.2,  w: 2.0, h: 0.24, fontSize: 9.5, color: C.muted, fontFace: "Calibri", align: "center", margin: 0 });
    s.addText(b.body3, { x: b.x + 0.05, y: 4.44, w: 2.0, h: 0.24, fontSize: 9.5, color: C.muted, fontFace: "Calibri", align: "center", margin: 0 });
    if (i < 3) {
      s.addShape(pres.shapes.RECTANGLE, { x: b.x + 2.12, y: 3.88, w: 0.16, h: 0.08, fill: { color: "BDBDBD" }, line: { color: "BDBDBD" } });
    }
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 5 — RUNNING COST
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  addHeaderBand(s);

  s.addText("05 / 09", { x: 8.8, y: 0.08, w: 1.0, h: 0.2, fontSize: 9, color: C.muted, align: "right" });
  s.addText("Every Line Added Extends This Cost Forward — Indefinitely", {
    x: 0.5, y: 0.1, w: 9.0, h: 0.58,
    fontSize: 24, bold: true, fontFace: "Arial Black", color: C.samsung, margin: 0,
  });
  s.addText("2025 fully-loaded labor estimates  (salary + benefits + overhead)  ·  Sources: SalaryExpert India, Manpower VN Salary Guide 2025", {
    x: 0.5, y: 0.72, w: 9.0, h: 0.24,
    fontSize: 9.5, color: C.muted, fontFace: "Calibri", margin: 0,
  });

  // ── Rate basis dark box (intentional contrast on white bg)
  s.addShape(pres.shapes.RECTANGLE, { x: 0.2, y: 1.02, w: 2.55, h: 3.58, fill: { color: "0D1B2A" }, line: { color: "0D1B2A" }, shadow: makeShadow() });

  const rateLines = [
    { t: "RATE  BASIS",    sz: 9,  bold: true, color: "7AAABB", spacing: 3 },
    { t: "",               sz: 6 },
    { t: "🇮🇳  SDN  India",  sz: 11, bold: true, color: C.white },
    { t: "$11 / hr",       sz: 26, bold: true, color: "60AAFF" },
    { t: "fully loaded",   sz: 9,  color: "AABBCC" },
    { t: "",               sz: 5 },
    { t: "SalaryExpert India 2025", sz: 7.5, color: "778899" },
    { t: "Glassdoor Samsung India", sz: 7.5, color: "778899" },
    { t: "",               sz: 8 },
    { t: "🇻🇳  SDV  Vietnam", sz: 11, bold: true, color: C.white },
    { t: "$13 / hr",       sz: 26, bold: true, color: "50D890" },
    { t: "fully loaded",   sz: 9,  color: "AABBCC" },
    { t: "",               sz: 5 },
    { t: "Manpower VN 2025 +",     sz: 7.5, color: "778899" },
    { t: "Samsung employer adj.",  sz: 7.5, color: "778899" },
    { t: "",               sz: 8 },
    { t: "* salary + benefits",    sz: 7,  color: "556677" },
    { t: "  + employer overhead",  sz: 7,  color: "556677" },
  ];
  let ry = 1.1;
  rateLines.forEach(l => {
    if (!l.t) { ry += (l.sz || 6) / 72; return; }
    s.addText(l.t, {
      x: 0.3, y: ry, w: 2.35, h: (l.sz || 10) / 72 + 0.08,
      fontSize: l.sz || 10, bold: l.bold || false, color: l.color || C.white,
      fontFace: "Calibri", charSpacing: l.spacing || 0, margin: 0,
    });
    ry += (l.sz || 10) / 72 + 0.1;
  });

  // ── SDN Table
  const sdnData = [
    [
      { text: "🇮🇳  SDN — INDIA", options: { bold: true, color: C.white, fill: { color: C.sdnBlue }, fontSize: 10.5 } },
      { text: "7 Lines  (Now)", options: { bold: true, color: C.white, fill: { color: C.sdnBlue }, fontSize: 10.5, align: "center" } },
      { text: "14 Lines  (Expansion)", options: { bold: true, color: C.white, fill: { color: C.sdnBlue }, fontSize: 10.5, align: "center" } },
    ],
    [
      { text: "Hours / month", options: { fill: { color: C.sdnRow }, fontSize: 10 } },
      { text: "210 hrs", options: { fill: { color: C.sdnRow }, fontSize: 10, align: "center" } },
      { text: "420 hrs", options: { fill: { color: C.sdnRow }, fontSize: 10, align: "center" } },
    ],
    [
      { text: "Cost / month", options: { fill: { color: C.white }, fontSize: 10 } },
      { text: "$2,310", options: { fill: { color: C.white }, bold: true, color: C.sdnBlue, fontSize: 11, align: "center" } },
      { text: "$4,620", options: { fill: { color: C.white }, bold: true, color: C.sdnBlue, fontSize: 11, align: "center" } },
    ],
    [
      { text: "Cost / year", options: { fill: { color: C.sdnRow }, bold: true, fontSize: 10.5 } },
      { text: "$27,720", options: { fill: { color: C.sdnRow }, bold: true, fontSize: 11.5, align: "center" } },
      { text: "$55,440", options: { fill: { color: C.sdnRow }, bold: true, fontSize: 11.5, align: "center" } },
    ],
    [
      { text: "Error exposure", options: { fill: { color: C.white }, fontSize: 10 } },
      { text: "14–28 / mo", options: { fill: { color: C.white }, fontSize: 10, align: "center" } },
      { text: "28–56 / mo", options: { fill: { color: C.white }, fontSize: 10, align: "center" } },
    ],
  ];
  s.addTable(sdnData, { x: 2.9, y: 1.02, w: 6.9, colW: [2.5, 2.2, 2.2], rowH: 0.3, border: { pt: 0.5, color: "D0D8E8" } });

  // ── SDV Table
  const sdvData = [
    [
      { text: "🇻🇳  SDV — VIETNAM  (est. 120–180 lines *)", options: { bold: true, color: C.white, fill: { color: C.sdvGreen }, fontSize: 10.5 } },
      { text: "120 Lines", options: { bold: true, color: C.white, fill: { color: C.sdvGreen }, fontSize: 10.5, align: "center" } },
      { text: "180 Lines", options: { bold: true, color: C.white, fill: { color: C.sdvGreen }, fontSize: 10.5, align: "center" } },
    ],
    [
      { text: "Hours / month", options: { fill: { color: C.sdvRow }, fontSize: 10 } },
      { text: "3,600 hrs", options: { fill: { color: C.sdvRow }, fontSize: 10, align: "center" } },
      { text: "5,400 hrs", options: { fill: { color: C.sdvRow }, fontSize: 10, align: "center" } },
    ],
    [
      { text: "Cost / month", options: { fill: { color: C.white }, fontSize: 10 } },
      { text: "$46,800", options: { fill: { color: C.white }, bold: true, color: C.sdvGreen, fontSize: 11, align: "center" } },
      { text: "$70,200", options: { fill: { color: C.white }, bold: true, color: C.sdvGreen, fontSize: 11, align: "center" } },
    ],
    [
      { text: "Cost / year", options: { fill: { color: C.sdvRow }, bold: true, fontSize: 10.5 } },
      { text: "$561,600", options: { fill: { color: C.sdvRow }, bold: true, fontSize: 11.5, align: "center" } },
      { text: "$842,400", options: { fill: { color: C.sdvRow }, bold: true, fontSize: 11.5, align: "center" } },
    ],
    [
      { text: "Error exposure", options: { fill: { color: C.white }, fontSize: 10 } },
      { text: "240–480 / mo", options: { fill: { color: C.white }, fontSize: 10, align: "center" } },
      { text: "360–720 / mo", options: { fill: { color: C.white }, fontSize: 10, align: "center" } },
    ],
  ];
  s.addTable(sdvData, { x: 2.9, y: 2.63, w: 6.9, colW: [2.5, 2.2, 2.2], rowH: 0.3, border: { pt: 0.5, color: "C0D8C0" } });

  s.addText("* SDV line count estimated from public capacity data: Digitimes Dec 2025, KED Global Sep 2024. Exact internal count not disclosed.", {
    x: 2.9, y: 4.27, w: 6.9, h: 0.22, fontSize: 7.5, color: "AAAAAA", fontFace: "Calibri", italic: true, margin: 0,
  });

  // ── Annual cost callout boxes
  s.addText("ANNUAL AVOIDABLE COST  (1 SOP type, labor only)", {
    x: 2.9, y: 4.52, w: 6.9, h: 0.22, fontSize: 8, bold: true, color: C.muted, charSpacing: 2, fontFace: "Calibri", margin: 0,
  });
  const annualBoxes = [
    { x: 2.9,  color: C.sdnBlue,  label: "SDN  7L",  val: "$27,720 / yr" },
    { x: 4.65, color: "1E88E5",   label: "SDN 14L",  val: "$55,440 / yr" },
    { x: 6.4,  color: C.sdvGreen, label: "SDV 120L", val: "$561,600 / yr" },
    { x: 8.15, color: "2E7D32",   label: "SDV 180L", val: "$842,400 / yr" },
  ];
  annualBoxes.forEach(b => {
    s.addShape(pres.shapes.RECTANGLE, { x: b.x, y: 4.76, w: 1.65, h: 0.72, fill: { color: b.color }, line: { color: b.color }, shadow: makeShadow() });
    s.addText(b.label, { x: b.x + 0.05, y: 4.79, w: 1.55, h: 0.22, fontSize: 8.5, bold: true, color: C.white, fontFace: "Calibri", align: "center", margin: 0 });
    s.addText(b.val,   { x: b.x + 0.05, y: 5.01, w: 1.55, h: 0.28, fontSize: 10,  bold: true, color: C.white, fontFace: "Calibri", align: "center", margin: 0 });
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 6 — WHAT WE GAIN
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  addHeaderBand(s);

  s.addText("06 / 09", { x: 8.8, y: 0.08, w: 1.0, h: 0.2, fontSize: 9, color: C.muted, align: "right" });
  s.addText("Savings Scale With Lines.  Value Multiplies With SOP Coverage.", {
    x: 0.5, y: 0.1, w: 9.0, h: 0.58,
    fontSize: 23, bold: true, fontFace: "Arial Black", color: C.samsung, margin: 0,
  });
  s.addText("Labor reallocation value only — excludes error correction cost and audit compliance savings.", {
    x: 0.5, y: 0.72, w: 9.0, h: 0.24, fontSize: 10, color: C.muted, fontFace: "Calibri", margin: 0,
  });

  // ── Left savings table
  const savData = [
    [
      { text: "ANNUAL SAVINGS — 1 SOP TYPE", options: { bold: true, color: C.white, fill: { color: C.samsung }, fontSize: 10, colspan: 2 } },
    ],
    [
      { text: "Scenario", options: { bold: true, color: C.muted, fill: { color: "EEF2FF" }, fontSize: 9.5 } },
      { text: "/ Year", options: { bold: true, color: C.muted, fill: { color: "EEF2FF" }, fontSize: 9.5, align: "center" } },
    ],
    [
      { text: "🇮🇳  SDN   7 lines", options: { fill: { color: C.sdnRow }, fontSize: 10 } },
      { text: "$27,720", options: { fill: { color: C.sdnRow }, fontSize: 10, align: "center" } },
    ],
    [
      { text: "🇮🇳  SDN  14 lines", options: { fill: { color: C.white }, fontSize: 10 } },
      { text: "$55,440", options: { fill: { color: C.white }, fontSize: 10, align: "center" } },
    ],
    [
      { text: "🇻🇳  SDV 120 lines", options: { fill: { color: C.sdvRow }, fontSize: 10 } },
      { text: "$561,600", options: { fill: { color: C.sdvRow }, fontSize: 10, align: "center" } },
    ],
    [
      { text: "🇻🇳  SDV 180 lines", options: { fill: { color: "C8EDDA" }, fontSize: 10 } },
      { text: "$842,400", options: { fill: { color: "C8EDDA" }, fontSize: 10, align: "center" } },
    ],
    [
      { text: "★  SDN 14 + SDV 180", options: { bold: true, color: C.white, fill: { color: C.samsung }, fontSize: 11 } },
      { text: "$897,840", options: { bold: true, color: C.white, fill: { color: C.samsung }, fontSize: 13, align: "center" } },
    ],
  ];
  s.addTable(savData, { x: 0.3, y: 1.0, w: 4.4, colW: [2.7, 1.7], rowH: 0.3, border: { pt: 0.5, color: "D0D8F0" } });

  // ── Right: SOP multiplier line chart
  s.addChart(pres.charts.LINE,
    [{ name: "Combined Annual Value ($)", labels: ["1 SOP", "3 SOPs", "5 SOPs", "10 SOPs"], values: [897840, 2693520, 4489200, 8978400] }],
    {
      x: 4.9, y: 1.0, w: 4.85, h: 3.05,
      lineSize: 3, lineSmooth: true,
      chartColors: [C.samsung],
      chartArea: { fill: { color: "F8FAFF" }, roundedCorners: true },
      catAxisLabelColor: C.muted, valAxisLabelColor: C.muted,
      valGridLine: { color: "E2E8F0", size: 0.5 }, catGridLine: { style: "none" },
      showValue: true, dataLabelColor: C.samsung, dataLabelFontSize: 9,
      showLegend: false,
      showTitle: true, title: "Combined Annual Value  (SDN 14L + SDV 180L)", titleFontSize: 9, titleColor: C.muted,
      valAxisLabelFormatCode: '"$"0.0,,"M"',
    }
  );

  // Callout box
  s.addShape(pres.shapes.RECTANGLE, { x: 4.9, y: 4.12, w: 4.85, h: 0.62, fill: { color: "FFFBEA" }, line: { color: C.yellow, pt: 1.5 } });
  s.addText([
    { text: "Adding 1 SOP type", options: { bold: true, color: C.dark } },
    { text: " = 2–4 hrs of IE engineer time     ", options: { color: C.dark } },
    { text: "Return at 10-type scale ≈ $900K / year", options: { bold: true, color: C.samsung } },
  ], { x: 4.9, y: 4.12, w: 4.85, h: 0.62, fontSize: 10.5, fontFace: "Calibri", align: "center", valign: "middle", margin: 4 });

  // ── Bottom 3 benefit boxes
  const benfBoxes = [
    { x: 0.3,  bg: C.lightBlue, border: C.sdnBlue,  icon: "📊", title: "AUDIT DATA",        body: "Auto-generated real-time logs", tc: C.sdnBlue  },
    { x: 1.82, bg: C.lightGrn,  border: C.sdvGreen, icon: "➕", title: "ZERO MARGINAL COST", body: "New SOP = 1 JSON file",         tc: C.sdvGreen },
    { x: 3.34, bg: C.cream,     border: C.orange,   icon: "🔄", title: "SELF-UPGRADING",     body: "Swap model file = better AI",   tc: C.orange   },
  ];
  benfBoxes.forEach(b => {
    s.addShape(pres.shapes.RECTANGLE, { x: b.x, y: 4.08, w: 1.44, h: 1.28, fill: { color: b.bg }, line: { color: b.border, pt: 1.5 } });
    s.addText(b.icon,  { x: b.x,        y: 4.14, w: 1.44, h: 0.35, fontSize: 18, align: "center", margin: 0 });
    s.addText(b.title, { x: b.x + 0.05, y: 4.5,  w: 1.34, h: 0.26, fontSize: 8.5, bold: true, color: b.tc, fontFace: "Calibri", align: "center", margin: 0 });
    s.addText(b.body,  { x: b.x + 0.05, y: 4.76, w: 1.34, h: 0.38, fontSize: 8,   color: C.dark, fontFace: "Calibri", align: "center", margin: 0 });
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 7 — DEVELOPMENT STATUS
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  addHeaderBand(s);

  s.addText("07 / 09", { x: 8.8, y: 0.08, w: 1.0, h: 0.2, fontSize: 9, color: C.muted, align: "right" });
  s.addText("Core System Is Built and Tested.  Next Step: On-Site Validation.", {
    x: 0.5, y: 0.1, w: 9.0, h: 0.58,
    fontSize: 23, bold: true, fontFace: "Arial Black", color: C.samsung, margin: 0,
  });
  s.addText("646 automated tests passing at 92%+ code coverage — production-grade engineering discipline.", {
    x: 0.5, y: 0.72, w: 9.0, h: 0.24, fontSize: 10, color: C.muted, fontFace: "Calibri", margin: 0,
  });

  // ── Left checklist
  s.addText("BUILD STATUS", {
    x: 0.3, y: 1.0, w: 4.3, h: 0.24, fontSize: 9, bold: true, color: C.samsung, charSpacing: 3, fontFace: "Calibri", margin: 0,
  });

  const checkRows = [
    { done: true,  t: "Vision layer — tested on line PC UIs" },
    { done: true,  t: "LLM reasoning — offline, no cloud" },
    { done: true,  t: "40-step SOP execution" },
    { done: true,  t: "Automated control  (state-verified)" },
    { done: true,  t: "Audit log — timestamp + screenshot" },
    { done: true,  t: "646 tests / 92%+ coverage" },
    { done: false, t: "Pilot line deployment" },
    { done: false, t: "On-site KPI measurement" },
  ];
  checkRows.forEach((r, i) => {
    const bg = r.done ? "F0FFF4" : "FFFDE7";
    const mark = r.done ? "✅" : "⬜";
    s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 1.28 + i * 0.26, w: 4.3, h: 0.25, fill: { color: bg }, line: { color: bg } });
    s.addText(mark, { x: 0.32, y: 1.3 + i * 0.26, w: 0.32, h: 0.22, fontSize: 10, margin: 0 });
    s.addText(r.t,  { x: 0.68, y: 1.3 + i * 0.26, w: 3.88, h: 0.22, fontSize: 9.5, color: C.dark, fontFace: "Calibri", margin: 0 });
  });

  // ── Right roadmap
  s.addText("DEPLOYMENT PATH", {
    x: 5.0, y: 1.0, w: 4.7, h: 0.24, fontSize: 9, bold: true, color: C.samsung, charSpacing: 3, fontFace: "Calibri", margin: 0,
  });

  const milestones = [
    { x: 5.0,  bg: C.samsung, tc: C.white, label: "NOW",    body1: "Approval",     body2: "" },
    { x: 6.27, bg: C.sdnRow,  tc: C.dark,  label: "M 1–3",  body1: "SDN Pilot",    body2: "1 line" },
    { x: 7.54, bg: C.sdnRow,  tc: C.dark,  label: "M 4–6",  body1: "SDN Expand",   body2: "7→14 + SOP×2" },
    { x: 8.81, bg: C.sdvRow,  tc: C.dark,  label: "M 7–12", body1: "SDV Planning", body2: "Data-driven" },
  ];
  milestones.forEach((m, i) => {
    s.addShape(pres.shapes.RECTANGLE, { x: m.x, y: 1.28, w: 1.15, h: 0.92, fill: { color: m.bg }, line: { color: "C0C8D8", pt: 0.5 }, shadow: makeShadow() });
    s.addText(m.label, { x: m.x, y: 1.3,  w: 1.15, h: 0.28, fontSize: 10.5, bold: true, color: m.tc, fontFace: "Calibri", align: "center", margin: 0 });
    s.addText(m.body1, { x: m.x, y: 1.58, w: 1.15, h: 0.24, fontSize: 9.5,  color: m.tc, fontFace: "Calibri", align: "center", margin: 0 });
    if (m.body2) {
      s.addText(m.body2, { x: m.x, y: 1.82, w: 1.15, h: 0.22, fontSize: 8.5, color: m.tc === C.dark ? C.muted : "BBCCEE", fontFace: "Calibri", align: "center", margin: 0 });
    }
    if (i < 3) {
      s.addText("→", { x: m.x + 1.17, y: 1.55, w: 0.08, h: 0.3, fontSize: 14, bold: true, color: C.muted, align: "center", margin: 0 });
    }
  });
  s.addText("First measurable results: ~2–3 months after pilot line deployment", {
    x: 5.0, y: 2.28, w: 4.7, h: 0.24, fontSize: 9.5, italic: true, color: C.muted, fontFace: "Calibri", margin: 0,
  });

  // ── "WHY IT WON'T BECOME OBSOLETE" table
  s.addText("WHY IT WON'T BECOME OBSOLETE", {
    x: 0.3, y: 3.46, w: 9.4, h: 0.24, fontSize: 9, bold: true, color: C.samsung, charSpacing: 3, fontFace: "Calibri", margin: 0,
  });

  const obsData = [
    [
      { text: "WHAT CHANGES", options: { bold: true, color: C.white, fill: { color: C.samsung }, fontSize: 10, align: "center" } },
      { text: "HOW IT ADAPTS", options: { bold: true, color: C.white, fill: { color: C.samsung }, fontSize: 10, align: "center" } },
      { text: "EFFORT", options: { bold: true, color: C.white, fill: { color: C.samsung }, fontSize: 10, align: "center" } },
    ],
    [
      { text: "SOP procedure content changes", options: { fill: { color: C.f5 }, fontSize: 10 } },
      { text: "Edit JSON definition file — no code change", options: { fill: { color: C.f5 }, fontSize: 10 } },
      { text: "IE engineer ~2 hrs", options: { fill: { color: C.f5 }, fontSize: 10, align: "center" } },
    ],
    [
      { text: "Line PC software UI updated", options: { fill: { color: C.white }, fontSize: 10 } },
      { text: "Retrain vision model on new screenshots", options: { fill: { color: C.white }, fontSize: 10 } },
      { text: "Vision team ~1 week", options: { fill: { color: C.white }, fontSize: 10, align: "center" } },
    ],
    [
      { text: "Better AI model available", options: { fill: { color: C.f5 }, fontSize: 10 } },
      { text: "Replace model file — performance improves automatically", options: { fill: { color: C.f5 }, fontSize: 10 } },
      { text: "IT admin ~1 day", options: { fill: { color: C.f5 }, fontSize: 10, align: "center" } },
    ],
  ];
  s.addTable(obsData, { x: 0.3, y: 3.74, w: 9.4, colW: [2.9, 4.3, 2.2], rowH: 0.25, border: { pt: 0.5, color: "D0D8F0" } });

  // Tech stack callout
  s.addShape(pres.shapes.RECTANGLE, { x: 0.3, y: 4.77, w: 9.4, h: 0.74, fill: { color: "F0F4FF" }, line: { color: "C8D4F0", pt: 1 } });
  s.addText("TECH STACK", { x: 0.45, y: 4.82, w: 1.5, h: 0.2, fontSize: 8, bold: true, color: C.samsung, charSpacing: 2, fontFace: "Calibri", margin: 0 });
  const techItems = [
    "Vision: YOLO26x  (custom-trained, offline)",
    "LLM: IBM Granite Vision  (local, Ollama)",
    "OCR: WinRT / EasyOCR  (auto-fallback)",
    "GUI: PyQt6  (7-tab monitoring dashboard)",
  ];
  techItems.forEach((t, i) => {
    const col = i < 2 ? 0.45 : 5.2;
    const row = i % 2;
    s.addText("· " + t, { x: col, y: 4.99 + row * 0.22, w: 4.5, h: 0.22, fontSize: 9, color: C.dark, fontFace: "Calibri", margin: 0 });
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 8 — THE ASK (unified bright theme)
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  addHeaderBand(s);

  s.addText("08 / 09", { x: 8.8, y: 0.08, w: 1.0, h: 0.2, fontSize: 9, color: C.muted, align: "right" });
  s.addText("Approval to Begin On-Site Validation", {
    x: 0.5, y: 0.08, w: 9.1, h: 0.56,
    fontSize: 26, bold: true, fontFace: "Arial Black", color: C.samsung, margin: 0,
  });
  s.addText("Requesting project registration + pilot line access to generate real performance data", {
    x: 0.5, y: 0.7, w: 9.0, h: 0.26, fontSize: 11, color: C.muted, fontFace: "Calibri", margin: 0,
  });

  // ── Left: 4 request cards (light blue fill on white bg)
  const cards = [
    { icon: "📋", title: "Project Registration",          sub: "Budget tracking & resource allocation" },
    { icon: "🏭", title: "Pilot Line — SDN, 1 Line",      sub: "Real production environment data" },
    { icon: "💻", title: "PC Installation Permission",    sub: "Single endpoint, existing hardware" },
    { icon: "👷", title: "IE Engineer  (part-time ~20%)", sub: "SOP formalization for pilot scope" },
  ];
  cards.forEach((c, i) => {
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.3, y: 1.18 + i * 0.76, w: 4.65, h: 0.70,
      fill: { color: C.lightBlue }, line: { color: C.samsung, pt: 1.5 }, shadow: makeShadow(),
    });
    s.addText(c.icon,  { x: 0.4,  y: 1.23 + i * 0.76, w: 0.48, h: 0.44, fontSize: 20, align: "center", margin: 0 });
    s.addText(c.title, { x: 0.95, y: 1.22 + i * 0.76, w: 3.8,  h: 0.28, fontSize: 12, bold: true, color: C.dark, fontFace: "Calibri", margin: 0 });
    s.addText(c.sub,   { x: 0.95, y: 1.50 + i * 0.76, w: 3.8,  h: 0.22, fontSize: 9.5, color: C.muted, fontFace: "Calibri", margin: 0 });
  });

  // ── Right: Decision matrix (light-themed for bright bg)
  const decData = [
    [
      { text: "", options: { fill: { color: C.samsung }, bold: true, color: C.white, fontSize: 10 } },
      { text: "PROCEED  ✓", options: { fill: { color: C.samsung }, bold: true, color: C.white, fontSize: 10, align: "center" } },
      { text: "DEFER  ✗", options: { fill: { color: C.samsung }, bold: true, color: C.white, fontSize: 10, align: "center" } },
    ],
    [
      { text: "Near-term", options: { fill: { color: C.lightBlue }, bold: true, color: C.dark, fontSize: 9.5 } },
      { text: "Pilot effort on 1 line", options: { fill: { color: C.okFill }, color: C.okText, fontSize: 9.5 } },
      { text: "No disruption", options: { fill: { color: C.errFill }, color: C.errText, fontSize: 9.5 } },
    ],
    [
      { text: "Medium-term", options: { fill: { color: C.lightBlue }, bold: true, color: C.dark, fontSize: 9.5 } },
      { text: "Data for scale decision", options: { fill: { color: C.okFill }, color: C.okText, fontSize: 9.5 } },
      { text: "Current cost continues", options: { fill: { color: C.errFill }, color: C.errText, fontSize: 9.5 } },
    ],
    [
      { text: "Long-term", options: { fill: { color: C.lightBlue }, bold: true, color: C.dark, fontSize: 9.5 } },
      { text: "SDV path + compounding SOP value", options: { fill: { color: C.okFill }, color: C.okText, fontSize: 9.5 } },
      { text: "Each new line extends cost baseline", options: { fill: { color: C.errFill }, color: C.errText, fontSize: 9.5 } },
    ],
  ];
  s.addTable(decData, { x: 5.1, y: 1.18, w: 4.65, colW: [1.3, 1.7, 1.65], rowH: 0.42, border: { pt: 0.5, color: "C8D8F0" } });

  s.addText("Proceeding: bounded, reversible commitment", { x: 5.1, y: 2.9, w: 4.65, h: 0.24, fontSize: 9, bold: true, color: C.okText, fontFace: "Calibri", margin: 0 });
  s.addText("Deferring: open-ended cost, compounding", { x: 5.1, y: 3.14, w: 4.65, h: 0.24, fontSize: 9, bold: true, color: C.errText, fontFace: "Calibri", margin: 0 });

  // Output boxes in right column below decision matrix notes
  const outBoxes = [
    { icon: "⏱", title: "Time Saved",       body: "Per cycle vs. manual baseline" },
    { icon: "📸", title: "Execution Record", body: "Step-by-step with screenshots" },
    { icon: "📊", title: "Auto Audit Log",   body: "Zero human logging effort" },
  ];
  outBoxes.forEach((b, i) => {
    const bx = 5.1 + i * 1.55;
    s.addShape(pres.shapes.RECTANGLE, {
      x: bx, y: 3.45, w: 1.45, h: 0.96,
      fill: { color: C.lightBlue }, line: { color: C.samsung, pt: 0.8 },
    });
    s.addText(b.icon,  { x: bx, y: 3.52, w: 1.45, h: 0.30, fontSize: 18, align: "center", margin: 0 });
    s.addText(b.title, { x: bx, y: 3.82, w: 1.45, h: 0.24, fontSize: 10, bold: true, color: C.dark, fontFace: "Calibri", align: "center", margin: 0 });
    s.addText(b.body,  { x: bx, y: 4.06, w: 1.45, h: 0.28, fontSize: 8.5, color: C.muted, fontFace: "Calibri", align: "center", margin: 0 });
  });

  // Bottom Samsung blue bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 4.5, w: 10, h: 1.12, fill: { color: C.samsung }, line: { color: C.samsung } });
  s.addText("The system is ready. One line and a deployment window is all that is needed to generate the data for the next decision.", {
    x: 0.3, y: 4.5, w: 9.4, h: 1.12,
    fontSize: 13, color: C.white, fontFace: "Calibri", align: "center", valign: "middle", italic: true, margin: 12,
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 9 — CLOSING (뒷지)
// ═══════════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.white };

  // Samsung blue top band (mirrors cover)
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 1.08, fill: { color: C.samsung }, line: { color: C.samsung } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.16, h: 5.625, fill: { color: C.samsungDk }, line: { color: C.samsungDk } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 1.08, w: 10, h: 0.06, fill: { color: "C8D8F0" }, line: { color: "C8D8F0" } });

  s.addText("SAMSUNG Display", { x: 0.36, y: 0.18, w: 5, h: 0.36, fontSize: 16, bold: true, color: C.white, fontFace: "Arial Black", margin: 0 });
  s.addText("Manufacturing Process Innovation", { x: 0.36, y: 0.6, w: 5.5, h: 0.26, fontSize: 10, color: "A8C4FF", fontFace: "Calibri", margin: 0 });
  s.addText("09 / 09", { x: 8.5, y: 0.2, w: 1.3, h: 0.26, fontSize: 9, color: "8899CC", align: "right", fontFace: "Calibri", margin: 0 });

  // Large "Thank You"
  s.addText("Thank You", {
    x: 0.5, y: 1.38, w: 9, h: 1.0, fontSize: 60, bold: true, fontFace: "Arial Black",
    color: C.samsung, align: "center", margin: 0,
  });
  s.addText("Questions  ·  Discussion  ·  Next Steps", {
    x: 0.5, y: 2.46, w: 9, h: 0.36, fontSize: 16, color: C.muted, fontFace: "Calibri", align: "center", margin: 0,
  });

  // Thin divider
  s.addShape(pres.shapes.RECTANGLE, { x: 2.0, y: 2.96, w: 6, h: 0.04, fill: { color: "C8D8F0" }, line: { color: "C8D8F0" } });

  // Next steps
  const steps = [
    "📋  Route project registration → Manufacturing Engineering team lead",
    "🏭  Assign pilot line → Coordinate with SDN production line supervisor",
    "💻  PC access permission → IT ticket + department manager approval",
  ];
  steps.forEach((st, i) => {
    s.addText(st, { x: 1.5, y: 3.14 + i * 0.32, w: 7, h: 0.28, fontSize: 11, color: C.dark, fontFace: "Calibri", align: "center", margin: 0 });
  });

  // Bottom info strip (mirrors cover)
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.06, w: 10, h: 0.56, fill: { color: C.headerBg }, line: { color: C.headerBg } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.06, w: 10, h: 0.05, fill: { color: C.samsung }, line: { color: C.samsung } });
  s.addText("SAMSUNG Display  ·  Manufacturing Engineering  ·  AI SOP Agent Proposal  ·  Confidential  ·  2026 Q2", {
    x: 0.5, y: 5.14, w: 9, h: 0.28, fontSize: 8.5, color: C.muted, fontFace: "Calibri", align: "center", margin: 0,
  });
}

// ─── WRITE FILE ───────────────────────────────────────────────────────────────
pres.writeFile({ fileName: "AI_SOP_Agent_Proposal.pptx" })
  .then(() => console.log("✅  AI_SOP_Agent_Proposal.pptx written successfully."))
  .catch(e => { console.error("❌  Error:", e); process.exit(1); });

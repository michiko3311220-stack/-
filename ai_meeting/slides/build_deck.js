// AI会議デモの紹介スライドを作る。
//   node ai_meeting/slides/build_deck.js [meeting.json] [出力.pptx]
// 予算のグラフ・表は meeting.json の budget から作る。見どころの引用は見本の議事録から選んでいるので、
// 実際の実行結果に差し替えるときは、見どころ（7〜9枚目）の引用も書き換える。
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const SRC = process.argv[2] || path.join(__dirname, "..", "sample_output", "meeting.json");
const OUT = process.argv[3] || path.join(__dirname, "ai_meeting_demo.pptx");
const { budget, plan } = JSON.parse(fs.readFileSync(SRC, "utf8"));

const FONT = "Noto Sans JP";
const COL = {
  navy: "1F2A44", ink: "222831", muted: "5F6B7A", line: "D9DEE5", bg: "FAFAFA", card: "FFFFFF",
  tint: "EEF1F6", coral: "E8574B", gold: "F2B544", white: "FFFFFF",
};
// 参加者（丸の中の1文字と色）。req は施策費の要望額（億円）
const ROLES = [
  { ch: "企", name: "経営企画部", color: "1F2A44", req: null, kpi: "全社目標から逆算して優先順位をつける" },
  { ch: "ユ", name: "ユーザー獲得部", color: "E8574B", req: 1.8, kpi: "登録団体 2.4万→2.9万" },
  { ch: "サ", name: "サポーター獲得部", color: "F2B544", req: 1.8, kpi: "サポーター 50万→57万人、解約率 3.5→3.0%" },
  { ch: "C", name: "カスタマーサポート部", color: "2A9D8F", req: 1.0, kpi: "最初の返信 20時間→6時間" },
  { ch: "開", name: "開発部", color: "6C5CE7", req: 2.0, kpi: "決済の障害 年4回→1回以下" },
  { ch: "人", name: "人事部", color: "3E8E41", req: 0.5, kpi: "アルバイト離職率 45→25%" },
  { ch: "経", name: "経理・財務部", color: "7A8597", req: 0.4, kpi: "原価率 50→48%" },
];
const role = (name) => ROLES.find((r) => name.startsWith(r.name)) || ROLES[6];
const fmt = (v) => v.toFixed(2).replace(/0$/, "");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.title = "AI会議デモ";
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };

pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: COL.bg },
  objects: [
    { text: { text: "AI会議デモ｜株式会社みらいエール（架空の会社）",
              options: { x: 0.5, y: 5.2, w: 6, h: 0.3, fontFace: FONT, fontSize: 9, color: COL.muted, margin: 0 } } },
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9, h: 0.85, fontFace: FONT,
                                fontSize: 24, bold: true, color: COL.ink, valign: "top", align: "left", margin: 0 },
                     text: "" } },
  ],
  slideNumber: { x: 9.1, y: 5.2, w: 0.4, h: 0.3, fontFace: FONT, fontSize: 9, color: COL.muted, align: "right" },
});
pres.defineSlideMaster({ title: "DARK", background: { color: COL.navy } });

const T = (slide, text, o) => slide.addText(text, { fontFace: FONT, color: COL.ink, margin: 0, isTextBox: true, ...o });
const circle = (slide, x, y, d, r, size) => {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: r.color }, line: { color: r.color } });
  T(slide, r.ch, { x, y, w: d, h: d, align: "center", valign: "middle", bold: true, color: COL.white, fontSize: size || 14 });
};
const card = (slide, x, y, w, h, fill) => slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
  x, y, w, h, rectRadius: 0.08, fill: { color: fill || COL.card }, line: { color: COL.line, width: 0.75 } });
const content = (title) => {
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText(title, { placeholder: "title" });
  return s;
};
const quote = (slide, x, y, w, h, r, text, size) => {
  card(slide, x, y, w, h);
  circle(slide, x + 0.2, y + 0.2, 0.42, r, 12);
  T(slide, r.name, { x: x + 0.72, y: y + 0.2, w: w - 0.9, h: 0.42, fontSize: 11, bold: true, color: COL.muted, valign: "middle" });
  T(slide, `「${text}」`, { x: x + 0.2, y: y + 0.75, w: w - 0.4, h: h - 0.9, fontSize: size || 14, valign: "top", lineSpacingMultiple: 1.2 });
};
const arrowR = (s, x, y) => s.addShape(pres.shapes.RIGHT_ARROW, { x, y, w: 0.22, h: 0.24, fill: { color: COL.line }, line: { color: COL.line } });
const table = (s, rows, o, size) => s.addTable(rows.map((r, i) => r.map((c, j) => ({
  text: String(c),
  options: { fontFace: FONT, fontSize: size || 12, color: COL.ink, bold: i === 0 || (r[0] === "営業利益"),
             align: j === 0 ? "left" : "right", valign: "middle",
             fill: { color: i === 0 ? COL.tint : (r[0] === "営業利益" ? "FDECEA" : COL.card) },
             border: [{ type: "none" }, { type: "none" }, { pt: 0.75, color: COL.line }, { type: "none" }] },
}))), { margin: [0.04, 0.12, 0.04, 0.12], ...o });

// 1. 表紙 ------------------------------------------------------------------
{
  const s = pres.addSlide({ masterName: "DARK" });
  T(s, "AI会議デモ", { x: 0.7, y: 0.8, w: 8, h: 0.4, fontSize: 14, bold: true, color: COL.gold });
  T(s, "7人のAIに、来期の予算を\n決めてもらった", { x: 0.7, y: 1.3, w: 8.6, h: 1.6, fontSize: 36, bold: true, color: COL.white, lineSpacingMultiple: 1.1 });
  T(s, "売上1.2倍に向けて、各部がKPIを掲げて予算を主張。Googleドライブの資料をもとに、役割を分けたAIが話し合って配分を決めるまで",
    { x: 0.7, y: 3.0, w: 8.4, h: 0.75, fontSize: 14, color: "C9D1DE" });
  ROLES.forEach((r, i) => circle(s, 0.7 + i * 0.62, 4.15, 0.48, r, 14));
  s.addNotes("部署ごとに役割を分けたAIに会議をさせ、来期の施策予算を決めてもらったデモです。会社は架空です。");
}

// 2. 前提 ------------------------------------------------------------------
{
  const s = content("前提：来期は売上1.2倍、営業利益10億円をめざす");
  card(s, 0.5, 1.3, 3.5, 3.6, COL.tint);
  T(s, "会社（架空）", { x: 0.75, y: 1.45, w: 3.0, h: 0.35, fontSize: 12, bold: true, color: COL.muted });
  T(s, "団体とサポーターをつなぐCtoC応援アプリ", { x: 0.75, y: 1.8, w: 3.0, h: 0.6, fontSize: 14, bold: true });
  T(s, [
    { text: "従業員130名（社員60名・アルバイト70名）", options: { breakLine: true } },
    { text: "流通額 月20億円 × 手数料15% ＝ 売上 月3億円", options: { breakLine: true } },
    { text: "団体に渡る応援金は預り金で、売上にも費用にも入らない", options: { color: COL.muted } },
  ], { x: 0.75, y: 2.5, w: 3.05, h: 2.2, fontSize: 12, valign: "top", paraSpaceAfter: 8 });
  table(s, [
    ["単位：億円", "今期", "来期の目標"],
    ["売上", "36.0", "43.2"],
    ["原価", "18.0", "21.6"],
    ["固定費（人件費・家賃など）", "6.6", "6.6"],
    ["施策費（各部が取り合う）", "3.0", "5.0"],
    ["営業利益", "8.4", "10.0"],
  ], { x: 4.3, y: 1.3, w: 5.2, colW: [2.6, 1.2, 1.4], rowH: 0.42 });
  T(s, "来期の施策費の枠＝売上 − 原価 − 固定費 − 営業利益の目標。原価を下げれば、その分だけ枠が広がる",
    { x: 4.3, y: 4.0, w: 5.2, h: 0.8, fontSize: 11.5, color: COL.muted, valign: "top" });
  s.addNotes("月の売上3億円、年間36億円の会社です。原価率50%、営業利益率23%。来期は売上を1.2倍にしつつ営業利益10億円を守るので、各部が使える施策費は5億円になります。");
}

// 3. 仕組み ------------------------------------------------------------------
{
  const s = content("各部署のAIは、自分の部署の資料だけを読んで発言する");
  const boxes = [
    ["ドライブ", "全社方針と6部署のKPI・予算要望（7つのドキュメント）"],
    ["AI ×7", "全社方針と自部署の資料だけを読む。他部署の資料は見えない"],
    ["議事録", "発言が積み上がり、次の人はそれを読んでから話す"],
    ["予算案", "決まった形式で出力し、合計と営業利益はプログラムで検算"],
  ];
  const w = 2.0, gap = 0.33, y = 1.45, h = 2.35;
  boxes.forEach(([head, body], i) => {
    const x = 0.5 + i * (w + gap);
    card(s, x, y, w, h);
    T(s, String(i + 1), { x: x + 0.2, y: y + 0.2, w: 0.5, h: 0.4, fontSize: 20, bold: true, color: COL.coral });
    T(s, head, { x: x + 0.2, y: y + 0.65, w: w - 0.3, h: 0.45, fontSize: 16, bold: true });
    T(s, body, { x: x + 0.2, y: y + 1.15, w: w - 0.3, h: 1.1, fontSize: 12, color: COL.muted, valign: "top", lineSpacingMultiple: 1.15 });
    if (i < boxes.length - 1) arrowR(s, x + w + 0.06, y + h / 2 - 0.12);
  });
  card(s, 0.5, 4.1, 9, 0.75, COL.tint);
  circle(s, 0.7, 4.24, 0.46, ROLES[0], 13);
  T(s, "進行役の経営企画部だけは、全部署から提出された資料を受け取っている",
    { x: 1.35, y: 4.1, w: 7.9, h: 0.75, fontSize: 13, valign: "middle" });
  s.addNotes("ポイントは情報の分け方です。各部署のAIには自分の部署の資料しか渡していないので、ほかの部署の事情は会議の発言から知るしかありません。");
}

// 4. 参加者とKPI ------------------------------------------------------------------
{
  const s = content("各部がKPIを掲げ、必要な施策費を主張する");
  const w = 2.07, h = 1.65, gx = 0.24;
  ROLES.forEach((r, i) => {
    const row = i < 4 ? 0 : 1, col = i < 4 ? i : i - 4;
    const x = 0.5 + col * (w + gx) + (row ? (w + gx) / 2 : 0), y = 1.3 + row * (h + 0.25);
    card(s, x, y, w, h);
    circle(s, x + 0.18, y + 0.18, 0.46, r, 14);
    T(s, r.req == null ? "進行役" : `要望 ${r.req.toFixed(1)}億円`, { x: x + 0.75, y: y + 0.18, w: w - 0.85, h: 0.46, fontSize: 12, bold: true, color: r.req == null ? COL.coral : COL.muted, valign: "middle" });
    T(s, r.name, { x: x + 0.18, y: y + 0.75, w: w - 0.25, h: 0.35, fontSize: r.name.length > 8 ? 11.5 : 13, bold: true });
    T(s, r.req == null ? r.kpi : `KPI：${r.kpi}`, { x: x + 0.18, y: y + 1.1, w: w - 0.3, h: 0.5, fontSize: 10.5, color: COL.muted, valign: "top" });
  });
  s.addNotes("事業部はユーザー獲得・サポーター獲得・カスタマーサポートの3つ。ユーザーはアプリに登録する活動団体、サポーターは団体を月額で応援する人です。");
}

// 5. お題 ------------------------------------------------------------------
{
  const s = content("お題：要望7.5億円に対し、施策費の枠は5.0億円");
  T(s, "−2.5億円", { x: 0.5, y: 1.6, w: 3.6, h: 1.1, fontSize: 54, bold: true, color: COL.coral });
  T(s, "会議で詰める金額", { x: 0.5, y: 2.7, w: 3.6, h: 0.4, fontSize: 14, bold: true });
  T(s, [
    { text: "要望の合計　7.5億円", options: { breakLine: true } },
    { text: "施策費の枠　5.0億円", options: { breakLine: true } },
    { text: "原価を下げれば枠は広がる。削るだけでなく、原価を下げる案も出せるかがカギ", options: { color: COL.muted, fontSize: 11 } },
  ], { x: 0.5, y: 3.25, w: 3.6, h: 1.5, fontSize: 13, valign: "top", paraSpaceAfter: 4 });
  const depts = ROLES.slice(1);
  s.addChart(pres.charts.BAR, [{ name: "要望額（億円）", labels: depts.map((r) => r.name), values: depts.map((r) => r.req) }], {
    x: 4.5, y: 1.3, w: 5.0, h: 3.6, barDir: "bar", catAxisOrientation: "maxMin",
    chartColors: [COL.navy], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0",
    dataLabelColor: COL.ink, dataLabelFontSize: 11, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: COL.ink, catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    showTitle: true, title: "部署ごとの施策費の要望（億円）", titleFontSize: 12, titleColor: COL.muted, titleFontFace: "+mn-lt",
  });
  s.addNotes("各部ともKPIを達成するために今期より多くの施策費を求めていて、合計すると枠を2.5億円超えます。");
}

// 6. 会議の流れ ------------------------------------------------------------------
{
  const s = content("会議は4つの段階、17回の発言で進んだ");
  const steps = [
    ["要望説明", "6部署が順に、KPIと\n必要な施策費を説明", "7回"],
    ["論点整理", "進行役が論点を3つに絞り、\n部署を名指しで投げかけ", "1回"],
    ["調整", "各部が金額つきの譲歩案と、\nKPIへの影響を出す", "6回"],
    ["確認・まとめ", "経理が営業利益を確認。\n配分案を表にして閉会", "3回＋配分案"],
  ];
  const w = 2.07, gap = 0.24;
  s.addShape(pres.shapes.LINE, { x: 0.9, y: 1.73, w: 8.1, h: 0, line: { color: COL.line, width: 2 } });
  steps.forEach(([head, body, n], i) => {
    const x = 0.5 + i * (w + gap);
    s.addShape(pres.shapes.OVAL, { x: x + 0.15, y: 1.45, w: 0.56, h: 0.56, fill: { color: COL.coral }, line: { color: COL.coral } });
    T(s, String(i + 1), { x: x + 0.15, y: 1.45, w: 0.56, h: 0.56, align: "center", valign: "middle", fontSize: 16, bold: true, color: COL.white });
    T(s, head, { x, y: 2.2, w, h: 0.45, fontSize: 16, bold: true });
    T(s, body, { x, y: 2.65, w, h: 0.9, fontSize: 12, color: COL.muted, valign: "top", lineSpacingMultiple: 1.15 });
    T(s, n, { x, y: 3.55, w, h: 0.35, fontSize: 12, bold: true, color: COL.navy });
  });
  card(s, 0.5, 4.05, 9, 0.85, COL.tint);
  T(s, [
    { text: "進行役が出した3つの論点：", options: { bold: true } },
    { text: "①原価を下げて枠を広げる　②「集める」と「続けてもらう」の配分　③削った場合のKPIへの影響" },
  ], { x: 0.75, y: 4.05, w: 8.5, h: 0.85, fontSize: 12.5, valign: "middle" });
  T(s, "※ 掲載している発言は見本の実行結果です", { x: 6.2, y: 5.2, w: 2.8, h: 0.3, fontSize: 9, color: COL.muted, align: "right" });
  s.addNotes("1人1回ずつではなく、論点整理を挟んで2周しています。2周目は、ほかの部署の発言を聞いたうえでの譲歩案になります。");
}

// 7〜9. 見どころ ------------------------------------------------------------------
{
  const s = content("見どころ①：別々の部署の数字がつながった");
  quote(s, 0.5, 1.3, 4.35, 1.8, role("サポーター獲得部"), "いま毎月約1.7万人が解約していて、理由の2位は問い合わせ対応の遅さです");
  quote(s, 5.15, 1.3, 4.35, 1.8, role("カスタマーサポート部"), "返信が24時間を超えたサポーターは、その後3ヶ月の解約率が通常の2倍です");
  s.addShape(pres.shapes.DOWN_ARROW, { x: 4.8, y: 3.17, w: 0.4, h: 0.3, fill: { color: COL.line }, line: { color: COL.line } });
  quote(s, 0.5, 3.55, 9.0, 1.3, role("経営企画部"), "解約理由と返信の遅さがつながっている以上、まず続けてもらう側を守りたい");
  s.addNotes("2つのAIはお互いの資料を見ていません。発言を聞いて、解約とサポート対応のつながりに会議の中で気づいています。");
}
{
  const s = content("見どころ②：原価を下げて、枠を0.85億円広げた");
  quote(s, 0.5, 1.3, 5.6, 1.8, role("経理・財務部"), "他の決済会社から3.2%の見積もりが出ています。開発部さんの決済基盤の切り替えが前提ですが、10月から移れれば来期だけで約0.6億円です", 13);
  quote(s, 0.5, 3.25, 5.6, 1.6, role("カスタマーサポート部"), "チャットボットが7月に動けば、アルバイト10名の増員はやめます。原価が0.25億円下がるので、その分を枠に戻せます", 12.5);
  card(s, 6.4, 1.3, 3.1, 3.55, COL.tint);
  T(s, "+0.85億円", { x: 6.55, y: 1.6, w: 2.8, h: 0.8, fontSize: 32, bold: true, color: COL.coral, align: "center" });
  T(s, "施策費の枠 5.0 → 5.85億円", { x: 6.55, y: 2.4, w: 2.8, h: 0.4, fontSize: 12.5, bold: true, align: "center" });
  T(s, [
    { text: "決済手数料 3.6%→3.2%：−0.6億円", options: { breakLine: true } },
    { text: "アルバイト増員の取りやめ：−0.25億円", options: { breakLine: true } },
    { text: "どちらも開発部の作業（決済の切り替え・チャットボット連携）が前提", options: { color: COL.muted } },
  ], { x: 6.65, y: 3.0, w: 2.65, h: 1.7, fontSize: 10.5, valign: "top", paraSpaceAfter: 4 });
  s.addNotes("経理の手数料の話とCSの増員の話が、どちらも開発部の作業につながっていました。進行役がそれを論点にして、削る以外の打ち手が出ています。");
}
{
  const s = content("見どころ③：広告を削り、自治体連携に回した");
  const steps = [
    ["当初のKPI", "2.9万団体", COL.navy],
    ["ネット広告 −0.5億円", "−1,250団体", COL.coral],
    ["自治体連携 +0.1億円", "+500団体", "3E8E41"],
    ["修正後のKPI", "約2.8万団体", COL.navy],
  ];
  const w = 2.07, gap = 0.24;
  steps.forEach(([label, val, c], i) => {
    const x = 0.5 + i * (w + gap);
    card(s, x, 1.35, w, 1.55);
    T(s, label, { x: x + 0.15, y: 1.5, w: w - 0.3, h: 0.4, fontSize: 12, bold: true, color: COL.muted });
    T(s, val, { x: x + 0.15, y: 1.95, w: w - 0.3, h: 0.7, fontSize: 19, bold: true, color: c });
  });
  quote(s, 0.5, 3.15, 9.0, 1.7, role("ユーザー獲得部"),
    "ネット広告の獲得費用は1団体4万円に上がっていますが、自治体連携は2万円で定着率も高い。広告を削る代わりに、自治体連携を0.1億円上乗せさせてください");
  s.addNotes("広告を0.5億円削っても、団体数の減少は約750団体に抑えています。");
}

// 10. 結果 ------------------------------------------------------------------
{
  const chk = budget.total_check;
  const s = content(`結果：施策費${fmt(chk.computed)}億円で、営業利益${fmt(chk.operating_profit)}億円を守った`);
  const short = (n) => n.replace("カスタマーサポート部", "CS").replace("経理・財務部", "経理").replace(/部$/, "");
  const labels = budget.items.map((i) => short(i.department));
  s.addChart(pres.charts.BAR, [
    { name: "要望額", labels, values: budget.items.map((i) => i.requested) },
    { name: "配分額", labels, values: budget.items.map((i) => i.allocated) },
  ], {
    x: 0.4, y: 1.2, w: 5.6, h: 3.8, barDir: "col", barGapWidthPct: 60,
    chartColors: [COL.line, COL.navy], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0#",
    dataLabelColor: COL.ink, dataLabelFontSize: 9, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: COL.ink, catAxisLabelFontSize: 9, catAxisLabelFontFace: "+mn-lt", catAxisLabelRotate: 0,
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "t", legendFontSize: 10, legendFontFace: "+mn-lt", legendColor: COL.muted,
    showTitle: true, title: "施策費（億円）", titleFontSize: 11, titleColor: COL.muted, titleFontFace: "+mn-lt",
  });
  table(s, [
    ["来期（億円）", ""],
    ["売上", fmt(plan.revenue)],
    ["原価", fmt(budget.cost_of_sales)],
    ["固定費", fmt(plan.fixed_sga)],
    ["施策費", fmt(chk.computed)],
    ["営業利益", fmt(chk.operating_profit)],
  ], { x: 6.2, y: 1.3, w: 3.3, colW: [1.9, 1.4], rowH: 0.38 }, 11.5);
  T(s, [
    { text: `原価は基準${fmt(plan.base_cost)}から${fmt(plan.base_cost - budget.cost_of_sales)}下げた`, options: { breakLine: true } },
    { text: `施策費のうち予備費${fmt(budget.reserve)}：${budget.reserve_condition}` },
  ], { x: 6.2, y: 3.75, w: 3.3, h: 1.2, fontSize: 10, color: COL.muted, valign: "top", paraSpaceAfter: 4 });
  s.addNotes(budget.summary);
}

// 11. 決まったこと・宿題 ------------------------------------------------------------------
{
  const s = content("決まったことと、次回までの宿題");
  card(s, 0.5, 1.3, 4.35, 3.6);
  T(s, "決まったこと", { x: 0.75, y: 1.45, w: 3.9, h: 0.4, fontSize: 15, bold: true, color: COL.navy });
  T(s, budget.decisions.map((d, i, a) => ({ text: d, options: { bullet: true, breakLine: i < a.length - 1 } })),
    { x: 0.75, y: 1.95, w: 3.9, h: 2.8, fontSize: 12, valign: "top", paraSpaceAfter: 6 });
  card(s, 5.15, 1.3, 4.35, 3.6);
  T(s, "宿題", { x: 5.4, y: 1.45, w: 3.9, h: 0.4, fontSize: 15, bold: true, color: COL.navy });
  budget.action_items.slice(0, 4).forEach((a, i) => {
    const y = 1.95 + i * 0.7;
    circle(s, 5.4, y, 0.42, role(a.owner), 12);
    T(s, [{ text: a.owner, options: { bold: true, breakLine: true } }, { text: a.task, options: { color: COL.muted } }],
      { x: 5.95, y: y - 0.05, w: 3.4, h: 0.6, fontSize: 11, valign: "top" });
  });
  s.addNotes("最後に、進行役が決定事項と宿題を整理して会議を締めています。");
}

// 12. わかったこと ------------------------------------------------------------------
{
  const s = content("やってみてわかったこと：つなぐのは得意、決めるのは人");
  const items = [
    ["よかった", "部署をまたぐつながりを見つける", "解約と返信の遅さ、手数料と決済の切り替えなど、別々の資料にある数字を会議の中で結びつけた", "3E8E41"],
    ["よかった", "KPIへの影響まで話す", "削るときに「何団体減るか」「何人減るか」を各部が数字で示すので、判断の根拠が残る", "3E8E41"],
    ["よかった", "検算はプログラムで", "AIの足し算をそのまま信じず、合計と営業利益をプログラムで確かめている", "3E8E41"],
    ["注意", "資料にないことは知らない", "市場の変化や社内の事情は、資料に書かない限り議論に入らない", COL.coral],
    ["注意", "最後に決めるのは人", "配分案は「たたき台」。会議の前の準備や論点出しに使うのが向いている", COL.coral],
  ];
  const w = 1.66, gap = 0.17;
  items.forEach(([tag, head, body, c], i) => {
    const x = 0.5 + i * (w + gap);
    card(s, x, 1.3, w, 3.2);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.15, y: 1.45, w: 0.85, h: 0.32, rectRadius: 0.08, fill: { color: c }, line: { color: c } });
    T(s, tag, { x: x + 0.15, y: 1.45, w: 0.85, h: 0.32, fontSize: 10, bold: true, color: COL.white, align: "center", valign: "middle" });
    T(s, head, { x: x + 0.15, y: 1.95, w: w - 0.3, h: 0.85, fontSize: 13, bold: true, valign: "top" });
    T(s, body, { x: x + 0.15, y: 2.85, w: w - 0.3, h: 1.55, fontSize: 10.5, color: COL.muted, valign: "top" });
  });
}

// 13. 次の一歩 ------------------------------------------------------------------
{
  const s = pres.addSlide({ masterName: "DARK" });
  T(s, "次は、自分たちの資料で", { x: 0.7, y: 0.8, w: 8.6, h: 0.9, fontSize: 32, bold: true, color: COL.white });
  const steps = [
    ["資料を置く", "Googleドライブに、全社方針と部署ごとのKPI・予算要望のドキュメントを入れる"],
    ["議題を決める", "予算配分のほか、採用計画、新サービスの優先順位、来期のKPIなど"],
    ["実行する", "GitHub の画面からボタンで実行。数分で議事録と配分案ができる"],
  ];
  steps.forEach(([head, body], i) => {
    const y = 1.95 + i * 1.0;
    s.addShape(pres.shapes.OVAL, { x: 0.7, y, w: 0.6, h: 0.6, fill: { color: COL.gold }, line: { color: COL.gold } });
    T(s, String(i + 1), { x: 0.7, y, w: 0.6, h: 0.6, align: "center", valign: "middle", fontSize: 18, bold: true, color: COL.navy });
    T(s, head, { x: 1.55, y: y - 0.05, w: 7.6, h: 0.38, fontSize: 16, bold: true, color: COL.white });
    T(s, body, { x: 1.55, y: y + 0.33, w: 7.6, h: 0.4, fontSize: 12.5, color: "C9D1DE" });
  });
}

pres.writeFile({ fileName: OUT }).then((f) => console.log("wrote", f));

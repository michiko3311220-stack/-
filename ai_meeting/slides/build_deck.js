// AI会議デモの紹介スライドを作る。
//   node ai_meeting/slides/build_deck.js [meeting.json] [出力.pptx]
// 予算のグラフ・表は meeting.json の budget から作る。見どころの引用は見本の議事録から選んでいるので、
// 実際の実行結果に差し替えるときは HIGHLIGHTS も書き換える。
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const SRC = process.argv[2] || path.join(__dirname, "..", "sample_output", "meeting.json");
const OUT = process.argv[3] || path.join(__dirname, "ai_meeting_demo.pptx");
const { budget } = JSON.parse(fs.readFileSync(SRC, "utf8"));

const FONT = "Noto Sans JP";
const COL = {
  navy: "1F2A44", ink: "222831", muted: "5F6B7A", line: "D9DEE5", bg: "FAFAFA", card: "FFFFFF",
  tint: "EEF1F6", coral: "E8574B", gold: "F2B544", white: "FFFFFF",
};
// 参加者（丸の中の1文字と色）
const ROLES = [
  { ch: "企", name: "経営企画部", color: "1F2A44", req: null, stance: "進行役。全社目標から逆算して優先順位をつける" },
  { ch: "ユ", name: "ユーザー獲得部", color: "E8574B", req: 4.2, stance: "団体の新規登録を増やしたい" },
  { ch: "サ", name: "サポーター獲得部", color: "F2B544", req: 3.0, stance: "解約率4.5%を下げたい" },
  { ch: "C", name: "カスタマーサポート部", color: "2A9D8F", req: 1.6, stance: "返信26時間の現場を立て直したい" },
  { ch: "開", name: "開発部", color: "6C5CE7", req: 5.2, stance: "決済基盤の刷新は譲れない" },
  { ch: "人", name: "人事部", color: "3E8E41", req: 1.5, stance: "採れる人数に合わせるべき" },
  { ch: "経", name: "経理・財務部", color: "7A8597", req: 2.0, stance: "黒字化の約束を守りたい" },
];
const role = (name) => ROLES.find((r) => name.startsWith(r.name.replace("（管理部門）", ""))) || ROLES[6];

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
const quote = (slide, x, y, w, h, r, text) => {
  card(slide, x, y, w, h);
  circle(slide, x + 0.2, y + 0.2, 0.42, r, 12);
  T(slide, r.name, { x: x + 0.72, y: y + 0.2, w: w - 0.9, h: 0.42, fontSize: 11, bold: true, color: COL.muted, valign: "middle" });
  T(slide, `「${text}」`, { x: x + 0.2, y: y + 0.75, w: w - 0.4, h: h - 0.9, fontSize: 14, valign: "top", lineSpacingMultiple: 1.2 });
};

// 1. 表紙 ------------------------------------------------------------------
{
  const s = pres.addSlide({ masterName: "DARK" });
  T(s, "AI会議デモ", { x: 0.7, y: 0.8, w: 8, h: 0.4, fontSize: 14, bold: true, color: COL.gold });
  T(s, "7人のAIに、来年度の予算を\n決めてもらった", { x: 0.7, y: 1.3, w: 8.6, h: 1.6, fontSize: 36, bold: true, color: COL.white, lineSpacingMultiple: 1.1 });
  T(s, "部署ごとの課題と目標をGoogleドライブに置き、役割を分けたAIが話し合って予算案をまとめるまで",
    { x: 0.7, y: 3.0, w: 8.4, h: 0.7, fontSize: 14, color: "C9D1DE" });
  ROLES.forEach((r, i) => circle(s, 0.7 + i * 0.62, 4.15, 0.48, r, 14));
  s.addNotes("部署ごとに役割を分けたAIに会議をさせ、来年度の予算案を作ってもらったデモです。会社は架空です。");
}

// 2. 仕組み ------------------------------------------------------------------
{
  const s = content("各部署のAIは、自分の部署の資料だけを読んで発言する");
  const boxes = [
    ["ドライブ", "全社方針と6部署の課題・目標・予算要望（7つのドキュメント）"],
    ["AI ×7", "全社方針と自部署の資料だけを読む。他部署の資料は見えない"],
    ["議事録", "発言が積み上がり、次の人はそれを読んでから話す"],
    ["予算案", "決まった形式で出力し、合計はプログラムで検算"],
  ];
  const w = 2.0, gap = 0.33, y = 1.45, h = 2.35;
  boxes.forEach(([head, body], i) => {
    const x = 0.5 + i * (w + gap);
    card(s, x, y, w, h);
    T(s, String(i + 1), { x: x + 0.2, y: y + 0.2, w: 0.5, h: 0.4, fontSize: 20, bold: true, color: COL.coral });
    T(s, head, { x: x + 0.2, y: y + 0.65, w: w - 0.3, h: 0.45, fontSize: 16, bold: true });
    T(s, body, { x: x + 0.2, y: y + 1.15, w: w - 0.3, h: 1.1, fontSize: 12, color: COL.muted, valign: "top", lineSpacingMultiple: 1.15 });
    if (i < boxes.length - 1)
      s.addShape(pres.shapes.RIGHT_ARROW, { x: x + w + 0.06, y: y + h / 2 - 0.12, w: 0.22, h: 0.24, fill: { color: COL.line }, line: { color: COL.line } });
  });
  card(s, 0.5, 4.1, 9, 0.75, COL.tint);
  circle(s, 0.7, 4.24, 0.46, ROLES[0], 13);
  T(s, "進行役の経営企画部だけは、全部署から提出された資料を受け取っている",
    { x: 1.35, y: 4.1, w: 7.9, h: 0.75, fontSize: 13, valign: "middle" });
  s.addNotes("ポイントは情報の分け方です。各部署のAIには自分の部署の資料しか渡していないので、ほかの部署の事情は会議の発言から知るしかありません。");
}

// 3. 参加者 ------------------------------------------------------------------
{
  const s = content("進行役と6つの部署が、それぞれの立場で話す");
  const w = 2.07, h = 1.65, gx = 0.24;
  ROLES.forEach((r, i) => {
    const row = i < 4 ? 0 : 1, col = i < 4 ? i : i - 4;
    const x = 0.5 + col * (w + gx) + (row ? (w + gx) / 2 : 0), y = 1.3 + row * (h + 0.25);
    card(s, x, y, w, h);
    circle(s, x + 0.18, y + 0.18, 0.46, r, 14);
    T(s, r.req == null ? "進行役" : `要望 ${r.req.toFixed(1)}億円`, { x: x + 0.75, y: y + 0.18, w: w - 0.85, h: 0.46, fontSize: 12, bold: true, color: r.req == null ? COL.coral : COL.muted, valign: "middle" });
    T(s, r.name, { x: x + 0.18, y: y + 0.75, w: w - 0.25, h: 0.35, fontSize: r.name.length > 8 ? 11.5 : 13, bold: true });
    T(s, r.stance, { x: x + 0.18, y: y + 1.1, w: w - 0.3, h: 0.5, fontSize: 10.5, color: COL.muted, valign: "top" });
  });
  s.addNotes("事業部はユーザー獲得・サポーター獲得・カスタマーサポートの3つ。ユーザーはアプリに登録する活動団体、サポーターは団体を月額で応援する人です。");
}

// 4. お題 ------------------------------------------------------------------
{
  const s = content("お題：要望の合計は17.5億円。上限より2.5億円多い");
  T(s, "−2.5億円", { x: 0.5, y: 1.6, w: 3.6, h: 1.1, fontSize: 54, bold: true, color: COL.coral });
  T(s, "会議で詰める金額", { x: 0.5, y: 2.7, w: 3.6, h: 0.4, fontSize: 14, bold: true });
  T(s, [
    { text: "要望の合計　17.5億円", options: { breakLine: true } },
    { text: "予算の上限　15.0億円", options: { breakLine: true } },
    { text: "上限は、売上が見込み16.5億円でも黒字を守るための線", options: { color: COL.muted, fontSize: 11 } },
  ], { x: 0.5, y: 3.25, w: 3.6, h: 1.4, fontSize: 13, valign: "top", paraSpaceAfter: 4 });
  const depts = ROLES.slice(1);
  s.addChart(pres.charts.BAR, [{ name: "要望額（億円）", labels: depts.map((r) => r.name), values: depts.map((r) => r.req) }], {
    x: 4.5, y: 1.3, w: 5.0, h: 3.6, barDir: "bar", catAxisOrientation: "maxMin",
    chartColors: [COL.navy], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0",
    dataLabelColor: COL.ink, dataLabelFontSize: 11, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: COL.ink, catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    showTitle: true, title: "部署ごとの要望額（億円）", titleFontSize: 12, titleColor: COL.muted, titleFontFace: "+mn-lt",
  });
  s.addNotes("各部の要望は前年より増えていて、合計すると上限を2.5億円超えます。金融機関からの借入は黒字化が条件なので、上限は動かせません。");
}

// 5. 会議の流れ ------------------------------------------------------------------
{
  const s = content("会議は4つの段階、17回の発言で進んだ");
  const steps = [
    ["要望説明", "6部署が順に、要望額と\nいちばん大事な施策を説明", "7回"],
    ["論点整理", "進行役が論点を3つに絞り、\n部署を名指しで投げかけ", "1回"],
    ["調整", "各部が金額つきの譲歩案と、\n他部署への条件を出す", "6回"],
    ["確認・まとめ", "進行役の案を経理が確認。\n予算案を表にして閉会", "3回＋予算案"],
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
    { text: "①「集める」と「続けてもらう」のどちらにお金を置くか　②開発の順番　③採れる人数に合わせた増員" },
  ], { x: 0.75, y: 4.05, w: 8.5, h: 0.85, fontSize: 12.5, valign: "middle" });
  T(s, "※ 掲載している発言は見本の実行結果です", { x: 6.2, y: 5.2, w: 2.8, h: 0.3, fontSize: 9, color: COL.muted, align: "right" });
  s.addNotes("1人1回ずつではなく、論点整理を挟んで2周しています。2周目は、ほかの部署の発言を聞いたうえでの譲歩案になります。");
}

// 6〜8. 見どころ ------------------------------------------------------------------
{
  const s = content("見どころ①：別々の部署の数字がつながった");
  quote(s, 0.5, 1.3, 4.35, 1.8, role("サポーター獲得部"), "集めても抜けていく、穴の空いたバケツの状態です。解約理由の2位は問い合わせの返事が遅いことです");
  quote(s, 5.15, 1.3, 4.35, 1.8, role("カスタマーサポート部"), "返信が24時間を超えたサポーターは、その後3ヶ月の解約率が通常の2.1倍です");
  s.addShape(pres.shapes.DOWN_ARROW, { x: 4.8, y: 3.17, w: 0.4, h: 0.3, fill: { color: COL.line }, line: { color: COL.line } });
  quote(s, 0.5, 3.55, 9.0, 1.3, role("経営企画部"), "まず穴をふさぐ側を厚くしたい。広告やキャンペーンをどこまで絞れるかを考えてほしい");
  s.addNotes("2つのAIはお互いの資料を見ていません。発言を聞いて、解約とサポート対応のつながりに会議の中で気づいています。");
}
{
  const s = content("見どころ②：人事部の一言で、開発部が増員を減らした");
  quote(s, 0.5, 1.3, 5.6, 1.8, role("人事部"), "今年はエンジニア10名の計画に対して4名しか採れていません。来年8名は難しく、5〜6名が現実的な線です");
  quote(s, 0.5, 3.3, 5.6, 1.5, role("開発部"), "採れない人の分の予算を積んでも使えないので、ここは素直に下げます");
  card(s, 6.4, 1.3, 3.1, 3.5, COL.tint);
  T(s, "−0.3億円", { x: 6.6, y: 1.7, w: 2.7, h: 0.9, fontSize: 36, bold: true, color: COL.coral, align: "center" });
  T(s, "開発部の増員 8名→5名", { x: 6.6, y: 2.6, w: 2.7, h: 0.4, fontSize: 13, bold: true, align: "center" });
  T(s, "あわせて採用計画は25名→19名に。カスタマーサポート部は、チャットボットを入れる代わりに増員を6名→3名に",
    { x: 6.65, y: 3.1, w: 2.6, h: 1.5, fontSize: 11, color: COL.muted, valign: "top" });
  s.addNotes("各部の要望は増員が前提でしたが、採用の実績を持っているのは人事部だけです。部署をまたいだ現実の確認が、無理のない削減につながりました。");
}
{
  const s = content("見どころ③：広告を削っても、団体数の目標はほぼ守った");
  const steps = [
    ["当初の目標", "5,000団体", COL.navy],
    ["ネット広告 −1.5億円", "−450団体", COL.coral],
    ["自治体連携 +0.2億円", "+250団体", "3E8E41"],
    ["修正後の目標", "4,800団体", COL.navy],
  ];
  const w = 2.07, gap = 0.24;
  steps.forEach(([label, val, c], i) => {
    const x = 0.5 + i * (w + gap);
    card(s, x, 1.35, w, 1.55);
    T(s, label, { x: x + 0.15, y: 1.5, w: w - 0.3, h: 0.4, fontSize: 12, bold: true, color: COL.muted });
    T(s, val, { x: x + 0.15, y: 1.95, w: w - 0.3, h: 0.7, fontSize: 24, bold: true, color: c });
  });
  quote(s, 0.5, 3.15, 9.0, 1.7, role("ユーザー獲得部"),
    "ネット広告の獲得費用は1団体33万円に上がりましたが、自治体と組めば8万円で、定着率も高い。広告を削る代わりに、自治体連携を0.2億円上乗せさせてください");
  s.addNotes("同じ団体を集めるのに、ネット広告は自治体連携の約4倍の費用がかかります。効率の悪いお金を削って、効率の良いところに寄せた調整です。");
}

// 9. 結果 ------------------------------------------------------------------
{
  const total = budget.total_check ? budget.total_check.computed : budget.total;
  const s = content(`結果：合計${total.toFixed(2)}億円。上限内で予算案がまとまった`);
  const short = (n) => n.replace("経理・財務部（管理部門）", "管理部門").replace("カスタマーサポート部", "CS").replace(/部$/, "");
  const labels = budget.items.map((i) => short(i.department));
  s.addChart(pres.charts.BAR, [
    { name: "要望額", labels, values: budget.items.map((i) => i.requested) },
    { name: "配分額", labels, values: budget.items.map((i) => i.allocated) },
  ], {
    x: 0.4, y: 1.2, w: 5.9, h: 3.8, barDir: "col", barGapWidthPct: 60,
    chartColors: [COL.line, COL.navy], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0#",
    dataLabelColor: COL.ink, dataLabelFontSize: 9, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: COL.ink, catAxisLabelFontSize: 9, catAxisLabelFontFace: "+mn-lt", catAxisLabelRotate: 0,
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "t", legendFontSize: 10, legendFontFace: "+mn-lt", legendColor: COL.muted,
  });
  card(s, 6.6, 1.3, 2.9, 3.6, COL.tint);
  T(s, `${total.toFixed(2)}億円`, { x: 6.8, y: 1.5, w: 2.5, h: 0.75, fontSize: 30, bold: true, color: COL.navy });
  T(s, `上限 15.0億円以内（要望から −${(17.5 - total).toFixed(2)}億円）`, { x: 6.8, y: 2.25, w: 2.5, h: 0.5, fontSize: 11, color: COL.muted });
  T(s, `うち予備費 ${budget.reserve.toFixed(1)}億円`, { x: 6.8, y: 2.9, w: 2.5, h: 0.35, fontSize: 13, bold: true, color: COL.coral });
  T(s, budget.reserve_condition, { x: 6.8, y: 3.25, w: 2.5, h: 1.5, fontSize: 11, color: COL.ink, valign: "top" });
  s.addNotes(budget.summary);
}

// 10. 決まったこと・宿題 ------------------------------------------------------------------
{
  const s = content("決まったことと、次回までの宿題");
  const col = (x, head, items) => {
    card(s, x, 1.3, 4.35, 3.6);
    T(s, head, { x: x + 0.25, y: 1.45, w: 3.9, h: 0.4, fontSize: 15, bold: true, color: COL.navy });
    return items;
  };
  col(0.5, "決まったこと", null);
  T(s, budget.decisions.map((d, i, a) => ({ text: d, options: { bullet: true, breakLine: i < a.length - 1 } })),
    { x: 0.75, y: 1.95, w: 3.9, h: 2.8, fontSize: 12, valign: "top", paraSpaceAfter: 6 });
  col(5.15, "宿題", null);
  budget.action_items.slice(0, 4).forEach((a, i) => {
    const y = 1.95 + i * 0.7;
    circle(s, 5.4, y, 0.42, role(a.owner), 12);
    T(s, [{ text: a.owner, options: { bold: true, breakLine: true } }, { text: a.task, options: { color: COL.muted } }],
      { x: 5.95, y: y - 0.05, w: 3.4, h: 0.6, fontSize: 11, valign: "top" });
  });
  s.addNotes("最後に、進行役が決定事項と宿題を整理して会議を締めています。");
}

// 11. わかったこと ------------------------------------------------------------------
{
  const s = content("やってみてわかったこと：つなぐのは得意、決めるのは人");
  const items = [
    ["よかった", "部署をまたぐつながりを見つける", "解約とサポート対応、増員と採用実績など、別々の資料にある数字を会議の中で結びつけた", "3E8E41"],
    ["よかった", "根拠つきで議論が残る", "全員が資料の数字を挙げて話すので、なぜその金額になったかを後から追える", "3E8E41"],
    ["よかった", "検算はプログラムで", "AIの足し算をそのまま信じず、合計と上限をプログラムで確かめている", "3E8E41"],
    ["注意", "資料にないことは知らない", "市場の変化や社内の事情は、資料に書かない限り議論に入らない", COL.coral],
    ["注意", "最後に決めるのは人", "予算案は「たたき台」。会議の前の準備や論点出しに使うのが向いている", COL.coral],
  ];
  const w = 1.66, gap = 0.17;
  items.forEach(([tag, head, body, c], i) => {
    const x = 0.5 + i * (w + gap);
    card(s, x, 1.3, w, 3.2);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.15, y: 1.45, w: 0.85, h: 0.32, rectRadius: 0.08, fill: { color: c }, line: { color: c } });
    T(s, tag, { x: x + 0.15, y: 1.45, w: 0.85, h: 0.32, fontSize: 10, bold: true, color: COL.white, align: "center", valign: "middle" });
    T(s, head, { x: x + 0.15, y: 1.95, w: w - 0.3, h: 0.85, fontSize: 13, bold: true, valign: "top" });
    T(s, body, { x: x + 0.15, y: 2.85, w: w - 0.3, h: 1.9, fontSize: 10.5, color: COL.muted, valign: "top" });
  });
}

// 12. 次の一歩 ------------------------------------------------------------------
{
  const s = pres.addSlide({ masterName: "DARK" });
  T(s, "次は、自分たちの資料で", { x: 0.7, y: 0.8, w: 8.6, h: 0.9, fontSize: 32, bold: true, color: COL.white });
  const steps = [
    ["資料を置く", "Googleドライブのフォルダに、部署ごとの課題・目標を書いたドキュメントを入れる"],
    ["議題を決める", "予算案のほか、採用計画、新サービスの優先順位、来期のKPIなど"],
    ["実行する", "GitHub の画面からボタンで実行。数分で議事録と予算案ができる"],
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

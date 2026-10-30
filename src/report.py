"""更新ごとの「買いの注目点」レポートを作る。

全銘柄の値動きを俯瞰し、テクニカルな傾向（底値圏での反発・売られすぎ・出来高急増など）を
理由つきで書き出す。ニュースなどの材料は見ていないので、理由はすべて値動きから説明できる範囲に限る。
"""
import gspread
import numpy as np
import pandas as pd

REPORT_SHEET = "レポート"
REPORT_KEEP_ROWS = 1500  # シートに残す過去レポートの行数

MARKET_LABEL = {"JP": "日本株", "US": "米国株など", "ALL": "全市場"}


def rsi(close: pd.Series, days: int) -> float:
    diff = close.diff().iloc[-days:]
    gain, loss = diff.clip(lower=0).mean(), -diff.clip(upper=0).mean()
    if len(diff) < days or pd.isna(gain):
        return np.nan
    if loss == 0:
        return 100.0
    return round(100 - 100 / (1 + gain / loss), 1)


def compute_features(history: pd.DataFrame, summary: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """summary に、レポート判定用の指標（RSI・移動平均乖離・出来高倍率・クロス）を足す。"""
    days = settings["report"]["rsi_days"]
    rows = []
    for ticker, hist in history.sort_values("date").groupby("ticker"):
        close = hist["close"].reset_index(drop=True)
        volume = hist["volume"].astype(float).reset_index(drop=True)
        if len(close) < 26:
            continue
        ma5, ma25 = close.rolling(5).mean(), close.rolling(25).mean()
        avg_vol = volume.iloc[-21:-1].mean()
        rows.append({
            "ティッカー": ticker,
            "RSI": rsi(close, days),
            "25日線乖離(%)": round((close.iloc[-1] / ma25.iloc[-1] - 1) * 100, 2),
            "出来高倍率": round(volume.iloc[-1] / avg_vol, 2) if avg_vol > 0 else np.nan,
            "ゴールデンクロス": bool(ma5.iloc[-2] <= ma25.iloc[-2] and ma5.iloc[-1] > ma25.iloc[-1]),
        })
    features = summary.merge(pd.DataFrame(rows), on="ティッカー", how="left")
    seg_avg = features[features["区分"] != ""].groupby(["グループ", "区分"])["5日騰落(%)"].mean()
    features["区分5日平均(%)"] = [
        seg_avg.get((g, s), np.nan) if s else np.nan for g, s in zip(features["グループ"], features["区分"])
    ]
    return features


def find_signals(f: pd.Series, cfg: dict, zone_pct: float) -> list[str]:
    """1銘柄について、当てはまる「買いの注目点」を理由の文章で返す。"""
    reasons = []
    gap_low, change = f["安値からの乖離(%)"], f["前日比(%)"]
    if gap_low <= zone_pct and change > 0:
        reasons.append(f"52週安値（{f['52週安値']:,}）から+{gap_low:.1f}%の位置で、当日{change:+.1f}%反発。"
                       "底値圏で買いが入り始めた可能性")
    if f["RSI"] <= cfg["rsi_oversold"]:
        reasons.append(f"RSI(14)が{f['RSI']:.0f}：短期的に売られすぎの水準。反発が起きやすい")
    if f["25日線乖離(%)"] <= cfg["ma_gap_pct"]:
        reasons.append(f"25日移動平均を{f['25日線乖離(%)']:.1f}%下回る：下げすぎで平均への戻りが起きやすい")
    if f["出来高倍率"] >= cfg["volume_ratio"] and change >= cfg["volume_up_pct"]:
        reasons.append(f"出来高が20日平均の{f['出来高倍率']:.1f}倍で{change:+.1f}%上昇：まとまった買いが入っている")
    if f["ゴールデンクロス"]:
        reasons.append("5日移動平均が25日移動平均を上抜け（ゴールデンクロス）：下落から上昇への転換サイン")
    if f["区分5日平均(%)"] <= cfg["segment_weak_pct"] and f["5日騰落(%)"] >= cfg["segment_strong_pct"]:
        reasons.append(f"区分全体が5日で{f['区分5日平均(%)']:.1f}%の中、{f['5日騰落(%)']:+.1f}%：競合より強い")
    return reasons


def _label(row, labels: dict) -> str:
    group = labels.get(row["グループ"], row["グループ"])
    return f"{group}｜{row['区分']}" if row["区分"] else group


def build_report(features: pd.DataFrame, settings: dict, market: str, as_of: str) -> str:
    """レポート本文（Markdown。スプレッドシートにもそのまま1行ずつ書く）を作る。"""
    cfg, labels = settings["report"], settings.get("group_labels", {})
    zone = settings["bottom"]["zone_pct"]
    df = features[features["最新終値"].notna()].copy()
    lines = [f"# 株価レポート {as_of}（{MARKET_LABEL.get(market, market)}の更新）", ""]

    # 全体の様子
    up, down = (df["前日比(%)"] > 0).sum(), (df["前日比(%)"] < 0).sum()
    lines += ["## 全体の様子", f"- 対象 {len(df)} 銘柄：上昇 {up} / 下落 {down}"]
    groups = df.groupby("グループ", sort=False)["前日比(%)"].mean()
    lines.append("- グループ平均の前日比：" + "、".join(
        f"{labels.get(g, g)} {v:+.1f}%" for g, v in groups.items()))
    seg = df[df["区分"] != ""].groupby(["グループ", "区分"], sort=False)["5日騰落(%)"].mean().sort_values()
    if 0 < len(seg) < 6:
        lines.append("- 区分ごとの5日騰落：" + "、".join(f"{s} {v:+.1f}%" for (_, s), v in seg[::-1].items()))
    elif len(seg):
        worst, best = seg.head(3), seg.tail(3)[::-1]
        lines.append("- 5日間で強い区分：" + "、".join(f"{s} {v:+.1f}%" for (_, s), v in best.items()))
        lines.append("- 5日間で弱い区分：" + "、".join(f"{s} {v:+.1f}%" for (_, s), v in worst.items()))
    lines.append("")

    # 買いの注目点
    picks = []
    for _, f in df.iterrows():
        if f["底値シグナル"] == "底値更新":
            continue  # 安値を更新中の銘柄は「注意」に回す（売られすぎでも下げ止まりを確認できていない）
        reasons = find_signals(f, cfg, zone)
        if reasons:
            picks.append((len(reasons), f, reasons))
    picks.sort(key=lambda p: (-p[0], p[1]["安値からの乖離(%)"]))
    lines.append("## 買いの注目点")
    if not picks:
        lines += ["- 本日は、買いの注目に当たる傾向は見つかりませんでした。", ""]
    else:
        lines.append("サインが多い順（★の数＝当てはまったサインの数）")
        for n, f, reasons in picks[: cfg["max_items"]]:
            lines.append(f"- {'★' * n} {f['銘柄名']}（{_label(f, labels)}）終値 {f['最新終値']:,}・前日比 {f['前日比(%)']:+.1f}%")
            lines += [f"  - {r}" for r in reasons]
        if len(picks) > cfg["max_items"]:
            lines.append(f"- ほか {len(picks) - cfg['max_items']} 銘柄")
        lines.append("")

    # 注意（下げ止まっていない）
    falling = df[(df["底値シグナル"] == "底値更新")]
    if len(falling):
        lines.append("## 注意：まだ下げ止まっていない銘柄")
        lines.append("52週安値を更新中。底を確認するまで（反発や出来高の増加が出るまで）待つのが無難")
        lines += [f"- {f['銘柄名']}（{_label(f, labels)}）前日比 {f['前日比(%)']:+.1f}%・25日 {f['25日騰落(%)']:+.1f}%"
                  f"・RSI {f['RSI']:.0f}" for _, f in falling.iterrows()]
        lines.append("")

    lines.append("※値動きだけから機械的に判定しています。ニュースや業績は考慮していません。投資判断はご自身で。")
    return "\n".join(lines)


def write_report_sheet(book: gspread.Spreadsheet, text: str) -> None:
    """レポートシートの先頭に今回分を足す（過去分は下に残す）。"""
    try:
        ws = book.worksheet(REPORT_SHEET)
        old = [r[0] if r else "" for r in ws.get_values("A:A")]
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=REPORT_SHEET, rows=100, cols=1)
        old = []
    new = text.split("\n") + ["", "―" * 20, ""]
    if old and old[0] == new[0] and new[-2] in old:
        # 同じ日・同じ市場のレポートを作り直したとき（通知の再送など）は、前の分を置き換える
        old = old[old.index(new[-2]) + 2:]
    rows = [[line] for line in (new + old)[:REPORT_KEEP_ROWS]]
    ws.clear()
    ws.resize(rows=len(rows), cols=1)
    ws.update(rows, "A1", value_input_option="RAW")
    book.batch_update({"requests": [
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 0,
                                                 "endIndex": 1}, "properties": {"pixelSize": 360}, "fields": "pixelSize"}},
        {"repeatCell": {"range": {"sheetId": ws.id, "startColumnIndex": 0, "endColumnIndex": 1},
                        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "textFormat": {"fontSize": 10}}},
                        "fields": "userEnteredFormat.wrapStrategy,userEnteredFormat.textFormat.fontSize"}},
    ]})

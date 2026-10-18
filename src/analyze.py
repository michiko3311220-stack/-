"""summary / segments シートの中身を計算する（スプレッドシートには依存しない）。"""
import numpy as np
import pandas as pd

SUMMARY_COLUMNS = [
    "グループ", "区分", "ティッカー", "銘柄名", "市場", "日付", "最新終値",
    "前日比(%)", "5日騰落(%)", "25日騰落(%)", "52週安値", "52週高値",
    "安値からの乖離(%)", "高値からの下落(%)", "トレンド", "底値シグナル", "備考",
]

SEGMENT_COLUMNS = [
    "グループ", "区分", "ティッカー", "銘柄名", "前日比(%)", "5日騰落(%)",
    "25日騰落(%)", "安値からの乖離(%)", "トレンド", "底値シグナル",
]


def _pct(now: float, before: float) -> float:
    if before is None or np.isnan(before) or before == 0:
        return np.nan
    return round((now / before - 1) * 100, 2)


def _back(series: pd.Series, n: int) -> float:
    return series.iloc[-1 - n] if len(series) > n else np.nan


def trend(close: pd.Series, short: int, long: int) -> str:
    if len(close) < long:
        return ""
    last = close.iloc[-1]
    ma_s = close.iloc[-short:].mean()
    ma_l = close.iloc[-long:].mean()
    if last > ma_s > ma_l:
        return "上昇"
    if last < ma_s < ma_l:
        return "下落"
    return "横ばい"


def bottom_signal(close: pd.Series, change_5d: float, zone_pct: float, approach_pct: float) -> str:
    last = close.iloc[-1]
    if len(close) > 1 and last < close.iloc[:-1].min():
        return "底値更新"
    gap = (last / close.min() - 1) * 100
    if gap <= zone_pct:
        return "底値圏"
    if gap <= approach_pct and change_5d < 0:
        return "接近中"
    return ""


def summarize_one(close: pd.Series, settings: dict) -> dict:
    """1銘柄分の終値（日付昇順）から summary の数値列を計算する。"""
    bottom, tr = settings["bottom"], settings["trend"]
    window = close.iloc[-bottom["lookback_days"]:]
    last = close.iloc[-1]
    change_5d = _pct(last, _back(close, 5))
    low, high = window.min(), window.max()
    return {
        "最新終値": round(float(last), 2),
        "前日比(%)": _pct(last, _back(close, 1)),
        "5日騰落(%)": change_5d,
        "25日騰落(%)": _pct(last, _back(close, 25)),
        "52週安値": round(float(low), 2),
        "52週高値": round(float(high), 2),
        "安値からの乖離(%)": _pct(last, low),
        "高値からの下落(%)": _pct(last, high),
        "トレンド": trend(close, tr["short_ma"], tr["long_ma"]),
        "底値シグナル": bottom_signal(window, change_5d, bottom["zone_pct"], bottom["approach_pct"]),
    }


def build_summary(prices: pd.DataFrame, meta: pd.DataFrame, settings: dict,
                  failed: list[str] = ()) -> pd.DataFrame:
    """tickers.yaml の並び順（グループ → 区分）のまま 1行 = 1銘柄 の summary を作る。

    計算には `close` を使う。Yahoo の Close は株式分割調整済みで、
    配当調整の入る Adj Close より実際の株価に近いため。
    """
    rows = []
    for m in meta.itertuples(index=False):
        row = {"グループ": m.group, "区分": m.segment, "ティッカー": m.ticker,
               "銘柄名": m.name, "市場": m.market, "備考": ""}
        hist = prices[prices["ticker"] == m.ticker].sort_values("date")
        if hist.empty:
            row["備考"] = "取得失敗" if m.ticker in failed else "データなし"
        else:
            row["日付"] = hist["date"].iloc[-1]
            row.update(summarize_one(hist["close"].reset_index(drop=True), settings))
        rows.append(row)
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def build_segments(summary: pd.DataFrame) -> pd.DataFrame:
    """区分のある銘柄を区分ごとに並べ、各区分の最後に平均行を入れる。"""
    df = summary[summary["区分"] != ""]
    numeric = ["前日比(%)", "5日騰落(%)", "25日騰落(%)", "安値からの乖離(%)"]
    blocks = []
    for (group, segment), block in df.groupby(["グループ", "区分"], sort=False):
        blocks.append(block[SEGMENT_COLUMNS])
        avg = {"グループ": group, "区分": segment, "ティッカー": "", "銘柄名": "【区分平均】"}
        avg.update({c: round(block[c].astype(float).mean(), 2) for c in numeric})
        blocks.append(pd.DataFrame([avg], columns=SEGMENT_COLUMNS))
    if not blocks:
        return pd.DataFrame(columns=SEGMENT_COLUMNS)
    return pd.concat(blocks, ignore_index=True)

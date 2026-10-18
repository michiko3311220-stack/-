import numpy as np
import pandas as pd

from src import analyze
from src.config import load_settings, load_tickers
from src.fetch import normalize
from src.sheets import PRICES_SHEET_COLUMNS, _to_values, merge_prices

SETTINGS = load_settings()


def _prices(ticker, closes):
    dates = pd.bdate_range("2026-01-01", periods=len(closes)).strftime("%Y-%m-%d")
    return pd.DataFrame({"date": dates, "ticker": ticker, "close": closes,
                         "adj_close": closes, "volume": 100})


def test_tickers_yaml_is_valid():
    meta = load_tickers()
    assert meta["ticker"].is_unique
    assert set(meta["market"]) <= {"JP", "US", "KR"}
    assert (meta.loc[meta["group"] == "ai", "segment"] != "").all()


def test_trend_up_and_down():
    up = pd.Series(np.arange(1, 31, dtype=float))
    assert analyze.trend(up, 5, 25) == "上昇"
    assert analyze.trend(up[::-1].reset_index(drop=True), 5, 25) == "下落"
    assert analyze.trend(up[:10], 5, 25) == ""


def test_bottom_signals():
    s = SETTINGS["bottom"]
    assert analyze.bottom_signal(pd.Series([100, 90, 80.0]), -5, s["zone_pct"], s["approach_pct"]) == "底値更新"
    assert analyze.bottom_signal(pd.Series([80, 100, 83.0]), -5, s["zone_pct"], s["approach_pct"]) == "底値圏"
    assert analyze.bottom_signal(pd.Series([80, 100, 87.0]), -5, s["zone_pct"], s["approach_pct"]) == "接近中"
    assert analyze.bottom_signal(pd.Series([80, 100, 87.0]), 3, s["zone_pct"], s["approach_pct"]) == ""
    assert analyze.bottom_signal(pd.Series([80, 100, 99.0]), -5, s["zone_pct"], s["approach_pct"]) == ""


def test_summary_and_segments():
    meta = pd.DataFrame([
        {"ticker": "AAA", "name": "A", "group": "ai", "segment": "GPU", "market": "US"},
        {"ticker": "BBB", "name": "B", "group": "ai", "segment": "GPU", "market": "US"},
        {"ticker": "CCC", "name": "C", "group": "ai", "segment": "GPU", "market": "US"},
    ])
    prices = pd.concat([_prices("AAA", list(range(100, 130))),
                        _prices("BBB", list(range(130, 100, -1)))])
    summary = analyze.build_summary(prices, meta, SETTINGS, failed=["CCC"])
    a = summary.set_index("ティッカー").loc["AAA"]
    assert a["最新終値"] == 129
    assert a["前日比(%)"] == round((129 / 128 - 1) * 100, 2)
    assert a["トレンド"] == "上昇"
    b = summary.set_index("ティッカー").loc["BBB"]
    assert b["底値シグナル"] == "底値更新"
    assert summary.set_index("ティッカー").loc["CCC", "備考"] == "取得失敗"

    seg = analyze.build_segments(summary)
    assert seg.iloc[-1]["銘柄名"] == "【区分平均】"
    assert seg.iloc[-1]["前日比(%)"] == round((a["前日比(%)"] + b["前日比(%)"]) / 2, 2)


def test_normalize_multiindex():
    idx = pd.to_datetime(["2026-10-15", "2026-10-16"])
    cols = pd.MultiIndex.from_product([["8035.T", "NVDA"], ["Close", "Adj Close", "Volume"]])
    raw = pd.DataFrame([[1, 1, 10, np.nan, np.nan, np.nan], [2, 2, 20, 5, 5, 50]], index=idx, columns=cols)
    out = normalize(raw, ["8035.T", "NVDA", "MISSING"])
    assert len(out[out.ticker == "8035.T"]) == 2
    assert out[out.ticker == "NVDA"]["date"].tolist() == ["2026-10-16"]


def test_merge_prices_upserts():
    meta = pd.DataFrame([{"ticker": "AAA", "name": "A", "group": "ai", "segment": "GPU", "market": "US"}])
    existing = merge_prices(pd.DataFrame(columns=PRICES_SHEET_COLUMNS), _prices("AAA", [1.0, 2.0]), meta)
    update = _prices("AAA", [1.0, 9.0, 3.0])
    merged = merge_prices(existing, update, meta)
    assert len(merged) == 3
    assert merged["close"].tolist() == [1.0, 9.0, 3.0]
    assert merged["name"].unique().tolist() == ["A"]


def test_to_values_handles_nan():
    values = _to_values(pd.DataFrame({"a": [1.5, np.nan], "b": ["x", None]}))
    assert values == [["a", "b"], [1.5, "x"], ["", ""]]

import numpy as np
import pandas as pd

from src import analyze, report
from src.config import load_settings

SETTINGS = load_settings()
META = pd.DataFrame([
    {"ticker": "AAA", "name": "反発株", "group": "ai", "segment": "GPU", "market": "US"},
    {"ticker": "BBB", "name": "下落株", "group": "ai", "segment": "GPU", "market": "US"},
    {"ticker": "CCC", "name": "逆行高", "group": "ai", "segment": "GPU", "market": "US"},
    {"ticker": "DDD", "name": "平凡株", "group": "power", "segment": "", "market": "US"},
])


def _hist(ticker, closes, volumes=None):
    dates = pd.bdate_range("2026-01-01", periods=len(closes)).strftime("%Y-%m-%d")
    volumes = volumes if volumes is not None else [100] * len(closes)
    return pd.DataFrame({"date": dates, "ticker": ticker, "close": closes, "adj_close": closes, "volume": volumes})


def _history():
    falling = list(np.linspace(200, 100, 40))
    return pd.concat([
        # 長く下げて安値圏から、出来高を伴って反発
        _hist("AAA", falling + [104.0], [100] * 40 + [500]),
        # 安値を更新し続ける
        _hist("BBB", falling + [85.0]),
        # 区分が下げる中、上昇
        _hist("CCC", [100.0] * 35 + [101, 102, 103, 104, 105, 106]),
        _hist("DDD", [100.0, 101.0] * 20 + [100.5]),
    ])


def _features():
    history = _history()
    summary = analyze.build_summary(history, META, SETTINGS)
    return report.compute_features(history, summary, SETTINGS)


def test_rsi():
    assert report.rsi(pd.Series(np.arange(30, dtype=float)), 14) == 100.0
    assert report.rsi(pd.Series(np.arange(30, 0, -1, dtype=float)), 14) == 0.0
    assert np.isnan(report.rsi(pd.Series([1.0, 2.0]), 14))


def test_features():
    f = _features().set_index("ティッカー")
    assert f.loc["AAA", "出来高倍率"] == 5.0
    assert f.loc["BBB", "RSI"] < 30
    assert f.loc["CCC", "区分5日平均(%)"] < 0
    assert np.isnan(f.loc["DDD", "区分5日平均(%)"])


def test_signals():
    f = _features().set_index("ティッカー")
    cfg, zone = SETTINGS["report"], SETTINGS["bottom"]["zone_pct"]
    aaa = report.find_signals(f.loc["AAA"], cfg, zone)
    assert any("反発" in r for r in aaa) and any("出来高" in r for r in aaa)
    assert not any("52週安値" in r for r in report.find_signals(f.loc["BBB"], cfg, zone))
    assert any("競合より強い" in r for r in report.find_signals(f.loc["CCC"], cfg, zone))
    assert report.find_signals(f.loc["DDD"], cfg, zone) == []


def test_build_report():
    text = report.build_report(_features(), SETTINGS, "US", "2026-02-26")
    assert text.startswith("# 株価レポート 2026-02-26（米国株などの更新）")
    assert "★" in text and "反発株" in text
    assert "## 注意：まだ下げ止まっていない銘柄" in text
    lines = text.split("\n")
    caution = lines[lines.index("## 注意：まだ下げ止まっていない銘柄"):]
    assert any("下落株" in l for l in caution)
    assert not any("下落株" in l for l in lines[:lines.index("## 注意：まだ下げ止まっていない銘柄")])
    picks = lines[lines.index("## 買いの注目点"):]
    assert picks.index(next(l for l in picks if "反発株" in l)) < picks.index(next(l for l in picks if "逆行高" in l))


def test_build_report_without_signals():
    f = _features()
    text = report.build_report(f[f["ティッカー"] == "DDD"], SETTINGS, "JP", "2026-02-26")
    assert "買いの注目に当たる傾向は見つかりませんでした" in text


class _FakeWs:
    id = 1

    def __init__(self, rows):
        self.rows = rows

    def get_values(self, _):
        return [[r] if r else [] for r in self.rows]

    def clear(self):
        self.rows = []

    def resize(self, **_):
        pass

    def update(self, rows, *_, **__):
        self.rows = [r[0] for r in rows]


class _FakeBook:
    def __init__(self, ws):
        self.ws = ws

    def worksheet(self, _):
        return self.ws

    def batch_update(self, _):
        pass


def test_write_report_sheet_prepends_and_replaces_same_report():
    book = _FakeBook(_FakeWs([]))
    report.write_report_sheet(book, "# 株価レポート 10/29\n- a")
    report.write_report_sheet(book, "# 株価レポート 10/30\n- b")
    assert book.ws.rows[0] == "# 株価レポート 10/30" and "# 株価レポート 10/29" in book.ws.rows
    # 同じレポートの作り直しは置き換え（重複させない）
    report.write_report_sheet(book, "# 株価レポート 10/30\n- c")
    assert book.ws.rows.count("# 株価レポート 10/30") == 1
    assert "- c" in book.ws.rows and "- b" not in book.ws.rows
    assert "# 株価レポート 10/29" in book.ws.rows

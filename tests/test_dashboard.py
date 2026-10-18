import numpy as np
import pandas as pd

from src import analyze, dashboard
from src.config import load_settings

SETTINGS = load_settings()
META = pd.DataFrame([
    {"ticker": "8035.T", "name": "東京エレクトロン", "group": "ai", "segment": "前工程装置", "market": "JP"},
    {"ticker": "AMAT", "name": "Applied Materials", "group": "ai", "segment": "前工程装置", "market": "US"},
    {"ticker": "9501.T", "name": "東京電力HD", "group": "power", "segment": "大手電力", "market": "JP"},
])


def _history():
    rows = []
    for i, d in enumerate(pd.bdate_range("2026-01-01", periods=40).strftime("%Y-%m-%d")):
        rows.append({"date": d, "ticker": "8035.T", "close": 100.0 + i})
        if i % 5 != 0:  # 米国だけ休場の日がある想定
            rows.append({"date": d, "ticker": "AMAT", "close": 200.0 - i})
    return pd.DataFrame(rows)


def test_chart_data_is_indexed_and_filled():
    data = dashboard.build_chart_data(_history(), META, days=30)
    assert list(data.columns) == ["日付", "8035.T", "AMAT", "9501.T"]
    assert len(data) == 30
    assert data["8035.T"].iloc[0] == 100
    assert not data["AMAT"].isna().any()  # 休場日は前日値で埋まる
    assert data["9501.T"].isna().all()    # データ無しの銘柄も列は残る


def test_range_position():
    assert dashboard.range_position(150, 100, 200) == 0.5
    assert dashboard.range_position(100, 100, 100) == 0.5
    assert np.isnan(dashboard.range_position(np.nan, 100, 200))


def test_dashboard_rows():
    history = _history()
    summary = analyze.build_summary(history, META, SETTINGS, failed=["9501.T"])
    rows, sections = dashboard.build_dashboard_rows(
        summary, META, SETTINGS["group_labels"], dates=[f"2026-09-{d:02d}" for d in range(1, 31)],
        spark_days=20)
    assert rows[0][5] == "3ヶ月の値動き（9/11〜9/30）"
    assert sections == [1, 4]
    assert rows[1][0] == "■ AI関連｜前工程装置"
    tel = rows[2]
    assert tel[1] == "8035"
    assert tel[5] == '=SPARKLINE(chart_data!B12:B31,{"charttype","line";"color","#d93025";"linewidth",2})'
    assert tel[6].startswith("=SPARKLINE({1.000,0.000}")
    failed = rows[5]
    assert failed[5] == "" and failed[9] == "取得失敗"
    assert all(len(r) == len(dashboard.DASHBOARD_HEADER) for r in rows)

"""日次処理のエントリポイント。

    python -m src.main --market JP|US|ALL
"""
import argparse
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src import analyze, dashboard, report, sheets
from src.config import load_settings, load_tickers
from src.fetch import drop_incomplete, fetch_history

log = logging.getLogger(__name__)


def target_tickers(meta, market: str) -> list[str]:
    if market == "ALL":
        return meta["ticker"].tolist()
    # 韓国は日本と同じ時間帯に引けるので JP の実行で扱う
    asia = meta["market"].isin(["JP", "KR"])
    if market == "JP":
        return meta.loc[asia, "ticker"].tolist()
    return meta.loc[~asia, "ticker"].tolist()


def run(market: str, report_out: str | None = None, force_report: bool = False) -> None:
    meta = load_tickers()
    settings = load_settings()

    # 52週の計算に1年分が要るので、毎回全銘柄の1年分を取得する
    history, failed = fetch_history(meta["ticker"].tolist(), settings["fetch"]["backfill_period"])
    history = drop_incomplete(history, dict(zip(meta["ticker"], meta["market"])), datetime.now(timezone.utc))

    book = sheets.open_spreadsheet()
    prices_ws = sheets.get_or_create(book, "prices")
    existing = sheets.read_prices(prices_ws)

    # 対象市場の直近分を upsert。履歴に無い銘柄（初回・新規追加）は1年分まるごと入れる
    targets = set(target_tickers(meta, market))
    known = set(existing["ticker"])
    since = (date.today() - timedelta(days=settings["fetch"]["recent_days"] * 2)).isoformat()
    in_target = history["ticker"].isin(targets)
    is_new = ~history["ticker"].isin(known)
    to_write = history[in_target & (is_new | (history["date"] >= since))]
    # 対象市場に新しい取引日が入ったか（休場日や予備時刻の再実行ではレポートを出さない）
    prev_latest = existing.loc[existing["ticker"].isin(targets), "date"].max()
    new_latest = history.loc[in_target, "date"].max()
    has_new_day = pd.notna(new_latest) and (pd.isna(prev_latest) or new_latest > prev_latest)
    merged = sheets.merge_prices(existing, to_write, meta)
    sheets.write_frame(prices_ws, merged)
    log.info("prices: %d 行を upsert（合計 %d 行）", len(to_write), len(merged))

    summary = analyze.build_summary(history, meta, settings, failed)
    sheets.write_frame(sheets.get_or_create(book, "summary"), summary)
    sheets.write_frame(sheets.get_or_create(book, "segments"), analyze.build_segments(summary))
    log.info("summary / segments を更新（失敗 %d 銘柄）", len(failed))

    if has_new_day or force_report:
        features = report.compute_features(history, summary, settings)
        text = report.build_report(features[features["ティッカー"].isin(targets)], settings, market, new_latest)
        report.write_report_sheet(book, text)
        if report_out:
            Path(report_out).write_text(text, encoding="utf-8")
        log.info("レポートを作成（%s）", new_latest)
    else:
        log.info("対象市場に新しい取引日がないため、レポートは作りません")

    dashboard.write_all(book, history, meta, summary, settings)
    log.info("ダッシュボード / 区分別グラフ を更新")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["JP", "US", "ALL"], default="ALL")
    parser.add_argument("--report-out", help="レポート本文を書き出すファイル（通知用）")
    parser.add_argument("--force-report", action="store_true", help="新しい取引日がなくてもレポートを作る")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(args.market, args.report_out, args.force_report)


if __name__ == "__main__":
    main()

"""日次処理のエントリポイント。

    python -m src.main --market JP|US|ALL
"""
import argparse
import logging
from datetime import date, timedelta

from src import analyze, sheets
from src.config import load_settings, load_tickers
from src.fetch import fetch_history

log = logging.getLogger(__name__)


def target_tickers(meta, market: str) -> list[str]:
    if market == "ALL":
        return meta["ticker"].tolist()
    if market == "JP":
        return meta.loc[meta["market"] == "JP", "ticker"].tolist()
    return meta.loc[meta["market"] != "JP", "ticker"].tolist()  # US = 海外すべて


def run(market: str) -> None:
    meta = load_tickers()
    settings = load_settings()

    # 52週の計算に1年分が要るので、毎回全銘柄の1年分を取得する
    history, failed = fetch_history(meta["ticker"].tolist(), settings["fetch"]["backfill_period"])

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
    merged = sheets.merge_prices(existing, to_write, meta)
    sheets.write_frame(prices_ws, merged)
    log.info("prices: %d 行を upsert（合計 %d 行）", len(to_write), len(merged))

    summary = analyze.build_summary(history, meta, settings, failed)
    sheets.write_frame(sheets.get_or_create(book, "summary"), summary)
    sheets.write_frame(sheets.get_or_create(book, "segments"), analyze.build_segments(summary))
    log.info("summary / segments を更新（失敗 %d 銘柄）", len(failed))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["JP", "US", "ALL"], default="ALL")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(args.market)


if __name__ == "__main__":
    main()

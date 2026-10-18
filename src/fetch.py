"""yfinance から日足を取得し、縦持ちの DataFrame に整形する。"""
import logging
import time

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

PRICE_COLUMNS = ["date", "ticker", "close", "adj_close", "volume"]


def normalize(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """yf.download(group_by="ticker") の結果を date, ticker, close, adj_close, volume に変換する。"""
    frames = []
    for ticker in tickers:
        if isinstance(raw.columns, pd.MultiIndex):
            if ticker not in raw.columns.get_level_values(0):
                continue
            df = raw[ticker]
        else:
            df = raw
        df = df.dropna(subset=["Close"])
        if df.empty:
            continue
        frames.append(pd.DataFrame({
            "date": pd.to_datetime(df.index).strftime("%Y-%m-%d"),
            "ticker": ticker,
            "close": df["Close"].to_numpy(),
            "adj_close": df["Adj Close"].to_numpy() if "Adj Close" in df else df["Close"].to_numpy(),
            "volume": df["Volume"].to_numpy() if "Volume" in df else 0,
        }))
    if not frames:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def _download(tickers: list[str], period: str) -> pd.DataFrame:
    raw = yf.download(
        tickers,
        period=period,
        interval="1d",
        auto_adjust=False,
        group_by="ticker",
        threads=False,  # 並列だと yfinance のキャッシュDBがロックすることがある
        progress=False,
    )
    return normalize(raw, tickers)


def fetch_history(tickers: list[str], period: str = "1y", retries: int = 1) -> tuple[pd.DataFrame, list[str]]:
    """日足を一括取得する。取れなかった銘柄は retries 回まで取り直す。
    戻り値は (価格データ, 取得できなかった銘柄)。"""
    prices = _download(tickers, period)
    failed = sorted(set(tickers) - set(prices["ticker"]))
    for _ in range(retries):
        if not failed:
            break
        time.sleep(5)
        prices = pd.concat([prices, _download(failed, period)], ignore_index=True)
        failed = sorted(set(tickers) - set(prices["ticker"]))
    if failed:
        log.warning("取得できなかった銘柄: %s", ", ".join(failed))
    return prices, failed

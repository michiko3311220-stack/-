"""Google スプレッドシートの読み書き。"""
import json
import os

import gspread
import numpy as np
import pandas as pd

from src.config import META_COLUMNS
from src.fetch import PRICE_COLUMNS

PRICES_SHEET_COLUMNS = ["date", "ticker", "name", "group", "segment", "market",
                        "close", "adj_close", "volume"]


def open_spreadsheet(id_env: str = "SPREADSHEET_ID") -> gspread.Spreadsheet | None:
    """環境変数 GCP_SA_KEY（JSON 文字列）と id_env のスプレッドシートIDで接続する。
    id_env が未設定なら None（スマホ用ファイルなど任意のものに使う）。"""
    key = os.environ.get(id_env)
    if not key:
        return None
    client = gspread.service_account_from_dict(json.loads(os.environ["GCP_SA_KEY"]))
    return client.open_by_key(key)


def get_or_create(book: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    try:
        return book.worksheet(title)
    except gspread.WorksheetNotFound:
        return book.add_worksheet(title=title, rows=100, cols=20)


def read_prices(ws: gspread.Worksheet) -> pd.DataFrame:
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=PRICES_SHEET_COLUMNS)
    df = pd.DataFrame(records)
    df["date"] = df["date"].astype(str)
    df["ticker"] = df["ticker"].astype(str)
    return df[PRICES_SHEET_COLUMNS]


def merge_prices(existing: pd.DataFrame, new: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """(date, ticker) をキーに upsert する。新しい側の値を優先。"""
    new = new[PRICE_COLUMNS].merge(meta[META_COLUMNS], on="ticker", how="left")
    merged = pd.concat([existing[PRICES_SHEET_COLUMNS], new[PRICES_SHEET_COLUMNS]], ignore_index=True)
    merged = merged.drop_duplicates(["date", "ticker"], keep="last")
    return merged.sort_values(["date", "ticker"]).reset_index(drop=True)


def _to_values(df: pd.DataFrame) -> list[list]:
    clean = df.astype(object).where(pd.notna(df), "")
    rows = [[v.item() if isinstance(v, np.generic) else v for v in row]
            for row in clean.itertuples(index=False)]
    return [list(df.columns)] + rows


def write_frame(ws: gspread.Worksheet, df: pd.DataFrame) -> None:
    """シートを丸ごと書き換える。"""
    values = _to_values(df)
    ws.clear()
    ws.resize(rows=max(len(values), 2), cols=max(len(df.columns), 1))
    ws.update(values, "A1", value_input_option="RAW")
    ws.freeze(rows=1)

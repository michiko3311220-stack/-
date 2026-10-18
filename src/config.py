"""config/ 配下の YAML を読み込む。"""
from pathlib import Path

import pandas as pd
import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

META_COLUMNS = ["ticker", "name", "group", "segment", "market"]


def load_tickers(path: Path = CONFIG_DIR / "tickers.yaml") -> pd.DataFrame:
    """監視銘柄を 1行 = 1銘柄 の DataFrame で返す（active: false は除外）。"""
    groups = yaml.safe_load(path.read_text(encoding="utf-8"))["groups"]
    rows = []
    for group, items in groups.items():
        for item in items:
            if item.get("active", True) is False:
                continue
            rows.append({
                "ticker": str(item["ticker"]),
                "name": item["name"],
                "group": group,
                "segment": item.get("segment", ""),
                "market": item["market"],
            })
    meta = pd.DataFrame(rows, columns=META_COLUMNS)
    # 同じ銘柄が複数グループにある場合は最初のグループを採用
    return meta.drop_duplicates("ticker").reset_index(drop=True)


def load_settings(path: Path = CONFIG_DIR / "settings.yaml") -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))

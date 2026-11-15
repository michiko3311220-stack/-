"""freee の予算インポート用の雛形CSVに、AI会議で確定した予算を書き込む。

使い方:
    python ai_meeting/freee/fill_freee_template.py 雛形.csv [出力.csv]

freee の形式（ヘルプ「予算金額をインポートする（一括登録）」より）:
- 雛形は freee の［予算設定（経営プランニング）］→［インポート］→［CSVインポート］でダウンロードする
- 1行目は「予算階層｜年度（例 2027）｜月（例 202704 … 202803）」。書き換え不可。行・列の追加も不可
- 1列目は予算の階層を「//」でつないだ名前（例：販売管理費//広告宣伝費//ユーザー獲得部）。途中の階層の行や
  「その他」の行も並ぶ。書き換え不可
- 2行目以降・2列目以降に金額（数字か空欄）を入れる。空欄のセルは反映されない（0にしたいときは 0）

このスクリプトは、1列目の階層に「部門名」と「勘定科目名」の両方が含まれる行のうち、一番下の行
（子の行がない行。部門の下にさらに階層があるときは、その「その他」の行）に、月別金額と年額（月の合計）を書き込む。
書き込んだ行の親にあたる途中の階層の行は、ダウンロード時の値で上書きしないよう空欄にする。文字コード（Shift_JIS / UTF-8）と改行は雛形に合わせて出力する。
"""
import csv
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_budget_csv import ITEMS, OKU, spread  # noqa: E402

def budget_by_dept_account():
    """(部門, 勘定科目) ごとの月別金額（会計年度順、円）。"""
    out = defaultdict(lambda: [0] * 12)
    for dept, account, _item, oku, months in ITEMS:
        for i, v in enumerate(spread(round(oku * OKU), months)):
            out[(dept, account)][i] += v
    return out


FISCAL_YEAR = 2027
YEAR_MONTHS = [(2027, m) for m in range(4, 13)] + [(2028, m) for m in range(1, 4)]


def classify(header):
    """見出しを ("year", 年) / ("month", (年, 月)) / None に分ける。freee は 2027 / 202704 の形。"""
    h = re.sub(r"\s", "", header)
    if re.fullmatch(r"\d{4}(年度)?", h):
        return ("year", int(h[:4]))
    m = re.fullmatch(r"(\d{4})[/\-.年]?(\d{1,2})月?", h)
    if m and 1 <= int(m.group(2)) <= 12:
        return ("month", (int(m.group(1)), int(m.group(2))))
    return None


def read_template(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp932"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        sys.exit("雛形の文字コードを読み取れませんでした（UTF-8 か Shift_JIS のCSVにしてください）")
    newline = "\r\n" if "\r\n" in text else "\n"
    return list(csv.reader(io.StringIO(text))), enc, newline


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_name(src.stem + "_記入済み.csv")
    rows, enc, newline = read_template(src)
    header = rows[0]
    cols, year_col = {}, None  # 列番号 -> 会計年度の何か月目か / 年度の列
    for c, h in enumerate(header[1:], start=1):
        k = classify(h)
        if k and k[0] == "year":
            if k[1] != FISCAL_YEAR:
                sys.exit(f"雛形の年度が {k[1]} です。{FISCAL_YEAR}年度の雛形をダウンロードしてください")
            year_col = c
        elif k and k[0] == "month":
            if k[1] not in YEAR_MONTHS:
                sys.exit(f"{FISCAL_YEAR}年度（2027年4月〜2028年3月）にない月の列があります：{h}")
            cols[c] = YEAR_MONTHS.index(k[1])
    if len(cols) != 12:
        sys.exit(f"月の列を12個読み取れませんでした（読めた列：{[header[c] for c in cols]}）。雛形の1行目を見せてください")

    paths = [r[0].strip() for r in rows[1:] if r]
    def is_leaf(path):
        return not any(q.startswith(path + "//") for q in paths)

    budget = budget_by_dept_account()
    used = set()
    filled_paths = set()
    filled = 0
    for r in rows[1:]:
        if not r:
            continue
        path = r[0].strip()
        parts = [p.strip() for p in path.split("//")]
        hits = [k for k in budget if k[0] in parts and k[1] in parts]
        if len(hits) != 1:
            continue
        key = hits[0]
        if not is_leaf(path):
            continue  # 途中の階層。下の行に書く
        # 部門と勘定科目より下に階層があるときは、その「その他」の行だけに書く
        below = parts[max(parts.index(key[0]), parts.index(key[1])) + 1:]
        if below and below != ["その他"]:
            continue
        if key in used:
            print(f"注意：{key} に当たる行が雛形に複数あります。後の行が freee で優先されます：{r[0]}")
        used.add(key)
        while len(r) < len(header):
            r.append("")
        for c, i in cols.items():
            r[c] = str(budget[key][i])
        if year_col is not None:
            r[year_col] = str(sum(budget[key]))
        filled += 1
        filled_paths.add(path)

    # 書き込んだ行の親（途中の階層）の行は空欄にして、ダウンロード時の値で上書きしないようにする
    written = [r[0].strip() for r in rows[1:] if r and r[0].strip() in filled_paths]
    cleared = 0
    for r in rows[1:]:
        if r and any(w.startswith(r[0].strip() + "//") for w in written):
            for c in [*cols, *([year_col] if year_col is not None else [])]:
                if c < len(r):
                    r[c] = ""
            cleared += 1

    missing = [k for k in budget if k not in used]
    with open(dst, "w", encoding=enc, newline="") as f:
        csv.writer(f, lineterminator=newline).writerows(rows)

    total = sum(sum(budget[k]) for k in used)
    print(f"書き込んだ行：{filled}　金額の合計：{total:,}円（確定予算 {5 * OKU:,}円）")
    print(f"空欄にした親の行：{cleared}")
    if missing:
        print("雛形に見つからなかった組み合わせ（freee の階層や勘定科目名を確認してください）：")
        for d, a in missing:
            print(f"  {d} // {a}：{sum(budget[(d, a)]):,}円")
    print("出力：", dst)


if __name__ == "__main__":
    main()

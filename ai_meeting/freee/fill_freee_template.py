"""freee の予算インポート用の雛形CSVに、AI会議で確定した予算を書き込む。

使い方:
    python ai_meeting/freee/fill_freee_template.py 雛形.csv [出力.csv]

freee の形式（ヘルプ「予算金額をインポートする（一括登録）」より）:
- 雛形は freee の［予算設定（経営プランニング）］→［インポート］→［CSVインポート］でダウンロードする
- 1列目は予算の階層を「//」でつないだ名前（例：ユーザー獲得部//広告宣伝費）。書き換え不可
- 1行目は年度・月の見出し。書き換え不可。行・列の追加も不可
- 2行目以降・2列目以降に金額（数字か空欄）を入れる。空欄はセットされない

このスクリプトは、1列目の階層に「部門名」と「勘定科目名」の両方が含まれる行に、
その組み合わせの月別金額を書き込む。年度の合計列は空欄のままにする（月の金額だけをセットする）。
文字コード（Shift_JIS / UTF-8）と改行は雛形に合わせて出力する。
"""
import csv
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_budget_csv import ITEMS, OKU, spread  # noqa: E402

# 会計年度は4月始まり。見出しから月を読み取れた列に、その月の金額を入れる
FISCAL = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]


def budget_by_dept_account():
    """(部門, 勘定科目) ごとの月別金額（会計年度順、円）。"""
    out = defaultdict(lambda: [0] * 12)
    for dept, account, _item, oku, months in ITEMS:
        for i, v in enumerate(spread(round(oku * OKU), months)):
            out[(dept, account)][i] += v
    return out


def month_of(header):
    """見出しから月（1〜12）を読む。年度の列などは None。"""
    h = header.strip()
    if "年度" in h:
        return None
    m = re.search(r"(?:\d{4}\s*[/\-.年]\s*)?(\d{1,2})\s*月?$", h)
    if m and 1 <= int(m.group(1)) <= 12:
        return int(m.group(1))
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
    cols = {}  # 列番号 -> 会計年度の何か月目か
    for c, h in enumerate(header[1:], start=1):
        m = month_of(h)
        if m is not None:
            cols[c] = FISCAL.index(m)
    if len(cols) != 12:
        sys.exit(f"月の列を12個読み取れませんでした（読めた列：{[header[c] for c in cols]}）。雛形の1行目を見せてください")

    budget = budget_by_dept_account()
    used = set()
    filled = 0
    for r in rows[1:]:
        if not r:
            continue
        parts = [p.strip() for p in r[0].split("//")]
        hits = [k for k in budget if k[0] in parts and k[1] in parts]
        if len(hits) != 1:
            continue
        key = hits[0]
        if key in used:
            print(f"注意：{key} に当たる行が雛形に複数あります。後の行が freee で優先されます：{r[0]}")
        used.add(key)
        while len(r) < len(header):
            r.append("")
        for c, i in cols.items():
            r[c] = str(budget[key][i])
        filled += 1

    missing = [k for k in budget if k not in used]
    with open(dst, "w", encoding=enc, newline="") as f:
        csv.writer(f, lineterminator=newline).writerows(rows)

    total = sum(sum(budget[k]) for k in used)
    print(f"書き込んだ行：{filled}　金額の合計：{total:,}円（確定予算 {5 * OKU:,}円）")
    if missing:
        print("雛形に見つからなかった組み合わせ（freee の階層や勘定科目名を確認してください）：")
        for d, a in missing:
            print(f"  {d} // {a}：{sum(budget[(d, a)]):,}円")
    print("出力：", dst)


if __name__ == "__main__":
    main()

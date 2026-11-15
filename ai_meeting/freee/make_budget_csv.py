"""AI会議（ライブ実行1）の確定予算の一覧（部門×勘定科目×月）。

ここで出すCSVは確認用の一覧で、freee にはそのまま取り込めない。freee に取り込むときは、
freee からダウンロードした雛形に fill_freee_template.py で金額を書き込む。

列：部門, 勘定科目, 施策, 4月..3月（円）, 合計
- 部門別の内訳と月の配り方は、議事録で決まっていない部分を仮に置いている（ITEMS のコメント参照）
- 予備費0.6億円は10月の決済移行を確認してから使う条件付きのため、確定予算には入れていない
- freee の正式なテンプレートの列名に合わせて、HEADER と出力の並びを直して使う
"""
import csv
from pathlib import Path

OKU = 100_000_000
MONTHS = ["4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月", "1月", "2月", "3月"]
ALL, H1 = range(12), range(6)   # 通年 / 上期（4〜9月）

# (部門, 勘定科目, 施策, 金額[億円], 計上する月)
ITEMS = [
    # ユーザー獲得部 1.15：議事録は合計のみ。要望1.5（広告0.6・自治体0.6・立ち上げ0.3）から広告で0.35減らしたと仮定
    ("ユーザー獲得部", "広告宣伝費", "ネット広告", 0.25, ALL),
    ("ユーザー獲得部", "販売促進費", "自治体・協会との連携", 0.60, ALL),
    ("ユーザー獲得部", "外注費", "新規団体の立ち上げ支援", 0.30, ALL),
    # サポーター獲得部 1.2：要望1.5（キャンペーン0.6・継続0.5・講座0.4）からキャンペーンで0.3減らしたと仮定
    ("サポーター獲得部", "広告宣伝費", "獲得キャンペーン・SNS広告", 0.30, ALL),
    ("サポーター獲得部", "販売促進費", "継続施策（活動報告・限定イベント）", 0.50, ALL),
    ("サポーター獲得部", "販売促進費", "団体向け発信講座", 0.40, ALL),
    # カスタマーサポート部 0.85（議事録どおり）。チャットボットは連携（4〜6月）に合わせて上期に計上と仮定
    ("カスタマーサポート部", "外注費", "AIチャットボット導入・FAQ刷新", 0.60, H1),
    ("カスタマーサポート部", "支払手数料", "問い合わせ管理ツール", 0.25, ALL),
    # 開発部 1.1：決済基盤の切り替えのみ（上期中に完了）。ギフト・サーバー構成は予備費側
    ("開発部", "外注費", "決済基盤の切り替え", 1.10, H1),
    # 人事部 0.4（議事録どおり）
    ("人事部", "採用教育費", "採用費", 0.15, ALL),
    ("人事部", "採用教育費", "研修・マニュアル整備・評価のしくみ", 0.25, ALL),
    # 経理・財務部 0.3（会計ツール0.15・交渉監査0.15と仮定）
    ("経理・財務部", "支払手数料", "会計・請求ツール（段階導入）", 0.15, ALL),
    ("経理・財務部", "支払報酬", "決済会社との交渉・監査対応", 0.15, ALL),
]

def spread(yen, months):
    """月に均等に配り、端数は最後の月で合わせる。"""
    months = list(months)
    base = yen // len(months)
    out = [0] * 12
    for m in months:
        out[m] = base
    out[months[-1]] += yen - base * len(months)
    return out

def main():
  rows = []
  for dept, account, item, oku, months in ITEMS:
      yen = round(oku * OKU)
      m = spread(yen, months)
      assert sum(m) == yen
      rows.append([dept, account, item, *m, yen])

  total = sum(r[-1] for r in rows)
  assert total == 5 * OKU, total
  HEADER = ["部門", "勘定科目", "施策", *MONTHS, "合計"]
  here = Path(__file__).resolve().parent
  for name, enc in [("freee_予算_2027年度_下書き_utf8.csv", "utf-8-sig"), ("freee_予算_2027年度_下書き_sjis.csv", "cp932")]:
      with open(here / name, "w", newline="", encoding=enc) as f:
          w = csv.writer(f)
          w.writerow(HEADER)
          w.writerows(rows)
  print("合計", f"{total:,}円", "行数", len(rows))
  by = {}
  for r in rows: by[r[0]] = by.get(r[0], 0) + r[-1]
  for k, v in by.items(): print(k, f"{v/OKU:.2f}億円")


if __name__ == "__main__":
    main()

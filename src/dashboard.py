"""見る用のシート（ダッシュボード・区分別グラフ）を作る。

- chart_data   : 日付 × 銘柄 の横持ち。期間の初日を100とした指数（グラフの元データ）
- chart_close  : 日付 × 銘柄 の横持ち。1年分の終値（個別チャートの元データ）
- ダッシュボード : 1行 = 1銘柄。SPARKLINE で値動きと52週レンジの位置を表示
- 区分別グラフ   : 区分ごとに競合の指数を1枚の折れ線グラフで比較
- 個別チャート   : プルダウンで選んだ銘柄の1年チャート（月の目盛り・52週安値/高値の線つき）
- スマホ        : スマホ縦画面の幅に収まる 個別チャート + 4列の一覧
"""
import gspread
import numpy as np
import pandas as pd
from gspread.utils import rowcol_to_a1

from src.sheets import _to_values

DATA_SHEET = "chart_data"
CLOSE_SHEET = "chart_close"
# 個別チャートの数式が範囲外参照にならないよう、chart_close はこの大きさ以上を保つ
CLOSE_ROWS, CLOSE_COLS = 400, 200
CLOSE_LAST_COL = rowcol_to_a1(1, CLOSE_COLS).rstrip("1")
SINGLE_SHEET = "個別チャート"
DASHBOARD_SHEET = "ダッシュボード"
CHARTS_SHEET = "区分別グラフ"
MOBILE_SHEET = "スマホ"

DASHBOARD_HEADER = ["銘柄名", "コード", "終値", "前日比(%)", "25日騰落(%)", "3ヶ月の値動き",
                    "52週の位置（安値◀▶高値）", "安値から(%)", "トレンド", "底値シグナル", "日付"]

# 日本の株価表示に合わせて 上昇=赤 / 下落=青
UP, DOWN, FLAT = "#d93025", "#1a73e8", "#9aa0a6"
TREND_COLOR = {"上昇": UP, "下落": DOWN}
SIGNAL_BG = {"底値更新": "#f4cccc", "底値圏": "#fce5cd", "接近中": "#fff2cc"}
SECTION_BG = "#e8eaed"


def build_close_wide(history: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """終値を 日付 × 銘柄 の横持ちにする。

    日本と米国で休場日が違うため、欠けた日は前日の値で埋める。
    列は meta の順。データの無い銘柄も空列として残す（列位置をずらさないため）。
    """
    wide = (history.pivot_table(index="date", columns="ticker", values="close")
            .sort_index().ffill())
    return wide.reindex(columns=meta["ticker"])


def build_chart_data(history: pd.DataFrame, meta: pd.DataFrame, days: int) -> pd.DataFrame:
    """直近 days 営業日の終値を、各銘柄の初日を100とした指数にする。"""
    wide = build_close_wide(history, meta).iloc[-days:]
    base = wide.bfill().iloc[0]
    index = (wide / base * 100).round(2)
    index.insert(0, "日付", index.index)
    return index.reset_index(drop=True)


def range_position(close: float, low: float, high: float) -> float:
    """52週の安値=0、高値=1 としたときの現在位置。"""
    if any(pd.isna(v) for v in (close, low, high)):
        return np.nan
    if high <= low:
        return 0.5
    return float(min(max((close - low) / (high - low), 0), 1))


def _sparkline(col: int, first_row: int, last_row: int, color: str) -> str:
    rng = f"{DATA_SHEET}!{rowcol_to_a1(first_row, col)}:{rowcol_to_a1(last_row, col)}"
    return f'=SPARKLINE({rng},{{"charttype","line";"color","{color}";"linewidth",2}})'


def _range_bar(pos: float) -> str:
    if pd.isna(pos):
        return ""
    return (f'=SPARKLINE({{{pos:.3f},{1 - pos:.3f}}},'
            f'{{"charttype","bar";"color1","#5f6368";"color2","#e0e0e0";"max",1}})')


def _md(d: str) -> str:
    return f"{int(d[5:7])}/{int(d[8:10])}"


def build_dashboard_rows(summary: pd.DataFrame, meta: pd.DataFrame, labels: dict,
                         dates: list[str], spark_days: int) -> tuple[list[list], list[int]]:
    """ダッシュボードの行（数式入り）と、見出し行の行番号（0始まり）を返す。

    dates は chart_data の日付列（ヘッダー除く）。
    """
    col_of = {t: i + 2 for i, t in enumerate(meta["ticker"])}  # chart_data の列番号（A=日付）
    last = len(dates) + 1
    first = max(2, last - spark_days + 1)
    header = list(DASHBOARD_HEADER)
    if dates:
        header[5] = f"{header[5]}（{_md(dates[first - 2])}〜{_md(dates[-1])}）"
    rows, sections = [header], []
    current = None
    for s in summary.to_dict("records"):
        key = (s["グループ"], s["区分"])
        if key != current:
            current = key
            title = labels.get(s["グループ"], s["グループ"]) + (f"｜{s['区分']}" if s["区分"] else "")
            sections.append(len(rows))
            rows.append([f"■ {title}"] + [""] * (len(DASHBOARD_HEADER) - 1))
        close = s["最新終値"]
        spark = "" if pd.isna(close) else _sparkline(
            col_of[s["ティッカー"]], first, last, TREND_COLOR.get(s["トレンド"], FLAT))
        pos = range_position(close, s["52週安値"], s["52週高値"])
        rows.append([
            s["銘柄名"], s["ティッカー"].removesuffix(".T"), close, s["前日比(%)"], s["25日騰落(%)"],
            spark, _range_bar(pos), s["安値からの乖離(%)"], s["トレンド"],
            s["備考"] if pd.isna(close) else s["底値シグナル"], s["日付"],
        ])
    clean = [["" if (isinstance(v, float) and np.isnan(v)) else v for v in r] for r in rows]
    return clean, sections


def _recreate(book: gspread.Spreadsheet, title: str, index: int, rows: int, cols: int) -> gspread.Worksheet:
    """書式・条件付き書式・グラフを毎回作り直すため、シートごと作り直す。"""
    try:
        book.del_worksheet(book.worksheet(title))
    except gspread.WorksheetNotFound:
        pass
    return book.add_worksheet(title=title, rows=rows, cols=cols, index=index)


def _grid(sheet_id, r0, r1, c0, c1) -> dict:
    return {"sheetId": sheet_id, "startRowIndex": r0, "endRowIndex": r1,
            "startColumnIndex": c0, "endColumnIndex": c1}


def _text_rule(sheet_id, col, n_rows, text, bg) -> dict:
    return {"addConditionalFormatRule": {"index": 0, "rule": {
        "ranges": [_grid(sheet_id, 1, n_rows, col, col + 1)],
        "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": text}]},
                        "format": {"backgroundColor": _rgb(bg), "textFormat": {"bold": True}}}}}}


def _sign_rule(sheet_id, col, n_rows, kind, color) -> dict:
    return {"addConditionalFormatRule": {"index": 0, "rule": {
        "ranges": [_grid(sheet_id, 1, n_rows, col, col + 1)],
        "booleanRule": {"condition": {"type": kind, "values": [{"userEnteredValue": "0"}]},
                        "format": {"textFormat": {"foregroundColor": _rgb(color)}}}}}}


def _rgb(hex_color: str) -> dict:
    h = hex_color.lstrip("#")
    return {k: int(h[i:i + 2], 16) / 255 for k, i in zip(("red", "green", "blue"), (0, 2, 4))}


def _width(sheet_id, c0, c1, px) -> dict:
    return {"updateDimensionProperties": {
        "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": c0, "endIndex": c1},
        "properties": {"pixelSize": px}, "fields": "pixelSize"}}


def write_dashboard(book, summary, meta, labels, dates, spark_days) -> None:
    rows, sections = build_dashboard_rows(summary, meta, labels, dates, spark_days)
    ws = _recreate(book, DASHBOARD_SHEET, 0, len(rows) + 5, len(DASHBOARD_HEADER))
    ws.update(rows, "A1", value_input_option="USER_ENTERED")
    sid, n, ncol = ws.id, len(rows), len(DASHBOARD_HEADER)
    bold = {"textFormat": {"bold": True}}
    requests = [
        # 見出し行を横に結合するため、列は固定しない（固定列をまたぐ結合はできない）
        {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {
            "frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {"range": _grid(sid, 0, 1, 0, ncol), "cell": {"userEnteredFormat": {
            **bold, "backgroundColor": _rgb("#202124"), "horizontalAlignment": "CENTER",
            "textFormat": {"bold": True, "foregroundColor": _rgb("#ffffff")}}},
            "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)"}},
        {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 1, "endIndex": n},
                                       "properties": {"pixelSize": 40}, "fields": "pixelSize"}},
        _width(sid, 0, 1, 170), _width(sid, 1, 5, 80), _width(sid, 5, 6, 320),
        _width(sid, 6, 7, 170), _width(sid, 7, 11, 85),
        _sign_rule(sid, 3, n, "NUMBER_GREATER", UP), _sign_rule(sid, 3, n, "NUMBER_LESS", DOWN),
        _sign_rule(sid, 4, n, "NUMBER_GREATER", UP), _sign_rule(sid, 4, n, "NUMBER_LESS", DOWN),
        *[_text_rule(sid, 9, n, text, bg) for text, bg in SIGNAL_BG.items()],
    ]
    for r in sections:
        requests += [
            {"mergeCells": {"range": _grid(sid, r, r + 1, 0, ncol), "mergeType": "MERGE_ALL"}},
            {"repeatCell": {"range": _grid(sid, r, r + 1, 0, ncol), "cell": {"userEnteredFormat": {
                **bold, "backgroundColor": _rgb(SECTION_BG)}},
                "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
        ]
    book.batch_update({"requests": requests})


def _segment_blocks(meta: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame]]:
    return [(g, seg, b) for (g, seg), b in meta[meta["segment"] != ""].groupby(["group", "segment"], sort=False)]


def _segment_chart(meta: pd.DataFrame, block: pd.DataFrame, title: str, data_sheet_id: int, n_rows: int,
                   axis_title: str, anchor: tuple[int, int, int], size: tuple[int, int], legend: str) -> dict:
    """1区分の競合の指数を重ねた折れ線グラフ。anchor は (sheetId, 行, 列)。"""
    col_of = {t: i + 1 for i, t in enumerate(meta["ticker"])}  # chart_data の列（0始まり、A=日付）
    series = [{"series": {"sourceRange": {"sources": [_grid(data_sheet_id, 0, n_rows, col_of[t], col_of[t] + 1)]}},
               "targetAxis": "LEFT_AXIS"} for t in block["ticker"]]
    sid, row, col = anchor
    return {"addChart": {"chart": {
        "spec": {
            "title": title,
            "basicChart": {
                "chartType": "LINE",
                "legendPosition": legend,
                "headerCount": 1,
                "axis": [{"position": "BOTTOM_AXIS"}, {"position": "LEFT_AXIS", "title": axis_title}],
                "domains": [{"domain": {"sourceRange": {"sources": [_grid(data_sheet_id, 0, n_rows, 0, 1)]}}}],
                "series": series,
            },
        },
        "position": {"overlayPosition": {"anchorCell": {"sheetId": sid, "rowIndex": row, "columnIndex": col},
                                         "widthPixels": size[0], "heightPixels": size[1]}},
    }}}


def write_charts(book, chart_data: pd.DataFrame, meta: pd.DataFrame, labels: dict,
                 data_sheet_id: int, chart_days: int) -> None:
    """区分（segment）ごとに、競合の指数を重ねた折れ線グラフを作る（2列に並べる）。"""
    blocks = _segment_blocks(meta)
    ws = _recreate(book, CHARTS_SHEET, 1, 20 * ((len(blocks) + 1) // 2) + 5, 16)
    months = round(chart_days / 21)
    ws.update([[f"各区分の競合比較：{months}ヶ月前の終値を100とした推移（上にあるほど値上がり）"]], "A1")
    requests = [
        _segment_chart(meta, block, f"{labels.get(g, g)}｜{seg}", data_sheet_id, len(chart_data) + 1,
                       f"{months}ヶ月前=100", (ws.id, 2 + 19 * (i // 2), 8 * (i % 2)), (620, 360),
                       "RIGHT_LEGEND")
        for i, (g, seg, block) in enumerate(blocks)
    ]
    book.batch_update({"requests": requests})


def _write_wide(book, title: str, header: list[str], frame: pd.DataFrame, input_option: str,
                min_rows: int = 0, min_cols: int = 0) -> gspread.Worksheet:
    """横持ちデータのシートを上書きする（シート自体は消さないので、参照する数式やグラフは壊れない）。"""
    values = [header] + _to_values(frame)[1:]
    try:
        ws = book.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=title, rows=10, cols=10)
    ws.clear()
    ws.resize(rows=max(len(values), min_rows), cols=max(len(header), min_cols))
    ws.update(values, "A1", value_input_option=input_option)
    return ws


def _single_chart_values(select_cell: str, first_col: int) -> list[list]:
    """select_cell で選んだ銘柄の列を chart_close から引いてくる4列（日付・終値・52週安値・52週高値）。"""
    src = f"{CLOSE_SHEET}!$B$1:${CLOSE_LAST_COL}$1"
    c = rowcol_to_a1(1, first_col + 1).rstrip("1")  # 終値の列（日付の右隣）
    return [["日付", f"={select_cell}", "52週安値", "52週高値"], [
        f"=ARRAYFORMULA({CLOSE_SHEET}!A2:A{CLOSE_ROWS})",
        f"=INDEX({CLOSE_SHEET}!B2:{CLOSE_LAST_COL}{CLOSE_ROWS},0,MATCH({select_cell},{src},0))",
        f'=ARRAYFORMULA(IF({c}2:{c}="","",MIN({c}2:{c})))',
        f'=ARRAYFORMULA(IF({c}2:{c}="","",MAX({c}2:{c})))',
    ]]


def _single_chart_requests(sid: int, select: tuple[int, int], data_col: int, anchor: tuple[int, int],
                           size: tuple[int, int]) -> list[dict]:
    """プルダウン（select の位置）と、data_col から4列のデータを使う折れ線グラフを作るリクエスト。"""
    gray = {"red": 0.6, "green": 0.6, "blue": 0.6}
    col = lambda c: _grid(sid, 0, CLOSE_ROWS, c, c + 1)  # noqa: E731
    series = [
        {"series": {"sourceRange": {"sources": [col(data_col + 1)]}}, "targetAxis": "LEFT_AXIS",
         "color": _rgb("#1a73e8"), "lineStyle": {"width": 2}},
        *[{"series": {"sourceRange": {"sources": [col(c)]}}, "targetAxis": "LEFT_AXIS",
           "color": gray, "lineStyle": {"width": 1, "type": "MEDIUM_DASHED"}} for c in (data_col + 2, data_col + 3)],
    ]
    r, c = select
    return [
        {"setDataValidation": {"range": _grid(sid, r, r + 1, c, c + 1), "rule": {
            "condition": {"type": "ONE_OF_RANGE",
                          "values": [{"userEnteredValue": f"={CLOSE_SHEET}!$B$1:${CLOSE_LAST_COL}$1"}]},
            "showCustomUi": True, "strict": True}}},
        {"addChart": {"chart": {
            "spec": {"basicChart": {
                "chartType": "LINE",
                "legendPosition": "TOP_LEGEND",
                "headerCount": 1,
                "axis": [{"position": "BOTTOM_AXIS"},
                         {"position": "LEFT_AXIS", "title": "終値"}],
                "domains": [{"domain": {"sourceRange": {"sources": [col(data_col)]}}}],
                "series": series,
            }},
            "position": {"overlayPosition": {"anchorCell": {"sheetId": sid, "rowIndex": anchor[0],
                                                            "columnIndex": anchor[1]},
                                             "widthPixels": size[0], "heightPixels": size[1]}},
        }}},
    ]


def write_single_chart(book, default_name: str) -> None:
    """個別チャートのシートを作る。選んだ銘柄が毎日リセットされないよう、既にあれば作り直さない。

    レイアウトを変えたときは、スプレッドシート上でこのシートを削除すれば次回作り直される。
    """
    try:
        book.worksheet(SINGLE_SHEET).batch_clear(["A2"])  # 以前の「スマホに戻る」リンクを消す
        return
    except gspread.WorksheetNotFound:
        pass
    ws = book.add_worksheet(title=SINGLE_SHEET, rows=CLOSE_ROWS + 5, cols=14, index=3)
    ws.update([
        ["銘柄を選択 ▶", default_name, "", "↓ 1年分の終値（グレーの点線が52週の安値・高値）"],
    ], "A1", value_input_option="USER_ENTERED")
    ws.update(_single_chart_values("$B$1", 11), "K1", value_input_option="USER_ENTERED")  # グラフの元データ（K〜N列）
    sid = ws.id
    book.batch_update({"requests": [
        {"repeatCell": {"range": _grid(sid, 0, 1, 0, 2), "cell": {"userEnteredFormat": {
            "textFormat": {"bold": True, "fontSize": 12}, "backgroundColor": _rgb("#fff2cc")}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
        _width(sid, 1, 2, 220),
        *_single_chart_requests(sid, (0, 1), 10, (2, 0), (960, 480)),
    ]})


# スマホ用シートのレイアウト（行・列は0始まり）
#   0行目: 一覧の見出し（固定） / その下: 一覧 / さらに下: 区分別グラフを縦に並べる
# スマホアプリではセル内リンクで別シートに飛べないため、見たいものを1シートに縦に並べている
MOBILE_HEADER = ["銘柄", "前日比", "3ヶ月", "底値"]
MOBILE_WIDTHS = [118, 58, 118, 62]       # 合計 356px（スマホ縦画面に収まる幅）
MOBILE_SEGMENT_ROWS = 14                 # 区分別グラフ1枚あたりの行数


def build_mobile_rows(summary: pd.DataFrame, meta: pd.DataFrame, labels: dict,
                      dates: list[str], spark_days: int) -> tuple[list[list], list[int]]:
    """スマホ用の一覧（見出し行つき）と、区分見出し行の位置（一覧内、0始まり）を返す。"""
    rows, sections = build_dashboard_rows(summary, meta, labels, dates, spark_days)
    out = [MOBILE_HEADER]
    for i, r in enumerate(rows[1:], start=1):
        out.append([r[0], "", "", ""] if i in sections else [r[0], r[3], r[5], r[9]])
    return out, sections


def write_mobile(book, summary, meta, labels, dates, spark_days,
                 chart_data: pd.DataFrame, data_sheet_id: int, chart_days: int) -> None:
    """スマホで見る用のシート（一覧 + 区分別グラフ）。毎日作り直す。"""
    rows, sections = build_mobile_rows(summary, meta, labels, dates, spark_days)
    blocks = _segment_blocks(meta)
    seg_title_row = len(rows) + 1
    ws = _recreate(book, MOBILE_SHEET, 0, seg_title_row + 1 + MOBILE_SEGMENT_ROWS * len(blocks) + 5,
                   len(MOBILE_HEADER))
    months = round(chart_days / 21)
    ws.update(rows, "A1", value_input_option="USER_ENTERED")
    ws.update([[f"■ 区分別グラフ（{months}ヶ月前=100、上ほど値上がり）"]], rowcol_to_a1(seg_title_row + 1, 1))

    sid, top, ncol = ws.id, 0, len(MOBILE_HEADER)
    end = top + len(rows)
    small = {"textFormat": {"fontSize": 9}}
    requests = [
        # 見出しはスクロールしても見えるよう固定
        {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                                   "fields": "gridProperties.frozenRowCount"}},
        *[_width(sid, i, i + 1, w) for i, w in enumerate(MOBILE_WIDTHS)],
        {"repeatCell": {"range": _grid(sid, top, end, 0, ncol), "cell": {"userEnteredFormat": {
            **small, "wrapStrategy": "WRAP", "verticalAlignment": "MIDDLE"}},
            "fields": "userEnteredFormat(textFormat,wrapStrategy,verticalAlignment)"}},
        {"repeatCell": {"range": _grid(sid, top, top + 1, 0, ncol), "cell": {"userEnteredFormat": {
            "textFormat": {"bold": True, "fontSize": 9, "foregroundColor": _rgb("#ffffff")},
            "backgroundColor": _rgb("#202124"), "horizontalAlignment": "CENTER"}},
            "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)"}},
        {"repeatCell": {"range": _grid(sid, top + 1, end, 1, 2), "cell": {"userEnteredFormat": {
            "numberFormat": {"type": "NUMBER", "pattern": '+0.0"%";-0.0"%";0.0"%"'}}},
            "fields": "userEnteredFormat.numberFormat"}},
        {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS",
                                                 "startIndex": top + 1, "endIndex": end},
                                       "properties": {"pixelSize": 34}, "fields": "pixelSize"}},
        _sign_rule(sid, 1, end, "NUMBER_GREATER", UP), _sign_rule(sid, 1, end, "NUMBER_LESS", DOWN),
        *[_text_rule(sid, 3, end, text, bg) for text, bg in SIGNAL_BG.items()],
    ]
    requests += [
        {"mergeCells": {"range": _grid(sid, seg_title_row, seg_title_row + 1, 0, ncol), "mergeType": "MERGE_ALL"}},
        {"repeatCell": {"range": _grid(sid, seg_title_row, seg_title_row + 1, 0, ncol), "cell": {"userEnteredFormat": {
            "textFormat": {"bold": True, "foregroundColor": _rgb("#ffffff")}, "backgroundColor": _rgb("#202124")}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
    ]
    requests += [
        _segment_chart(meta, block, f"{labels.get(g, g)}｜{seg}", data_sheet_id, len(chart_data) + 1,
                       f"{months}ヶ月前=100", (sid, seg_title_row + 1 + MOBILE_SEGMENT_ROWS * i, 0),
                       (sum(MOBILE_WIDTHS), 21 * MOBILE_SEGMENT_ROWS - 8), "BOTTOM_LEGEND")
        for i, (g, seg, block) in enumerate(blocks)
    ]
    for r in sections:
        requests += [
            {"mergeCells": {"range": _grid(sid, top + r, top + r + 1, 0, ncol), "mergeType": "MERGE_ALL"}},
            {"repeatCell": {"range": _grid(sid, top + r, top + r + 1, 0, ncol), "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True, "fontSize": 9}, "backgroundColor": _rgb(SECTION_BG)}},
                "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
        ]
    book.batch_update({"requests": requests})


def write_all(book: gspread.Spreadsheet, history: pd.DataFrame, meta: pd.DataFrame,
              summary: pd.DataFrame, settings: dict, mobile_book: gspread.Spreadsheet | None = None) -> None:
    """見る用のシートを書く。mobile_book があれば スマホ シートはそちら（軽いファイル）に書き、
    本体からは消す。本体は履歴やグラフが多く、スマホアプリでは重くて開けないため。"""
    view, labels = settings["view"], settings.get("group_labels", {})
    names = meta["name"].tolist()  # グラフの凡例・プルダウンに銘柄名を出す

    data = build_chart_data(history, meta, view["chart_days"])
    data_ws = _write_wide(book, DATA_SHEET, ["日付"] + names, data, "RAW")

    close = build_close_wide(history, meta)
    close.insert(0, "日付", close.index)
    # 日付として認識させる（個別チャートの横軸に月の目盛りを出すため）
    _write_wide(book, CLOSE_SHEET, ["日付"] + names, close.reset_index(drop=True), "USER_ENTERED",
                min_rows=CLOSE_ROWS, min_cols=CLOSE_COLS)

    dates = data["日付"].tolist()
    write_dashboard(book, summary, meta, labels, dates, view["sparkline_days"])
    write_charts(book, data, meta, labels, data_ws.id, view["chart_days"])
    write_single_chart(book, default_name=names[0])

    if mobile_book is None:
        write_mobile(book, summary, meta, labels, dates, view["sparkline_days"],
                     chart_data=data, data_sheet_id=data_ws.id, chart_days=view["chart_days"])
    else:
        # SPARKLINE やグラフは同じファイル内のデータしか参照できないので、元データも複製する
        mobile_data_ws = _write_wide(mobile_book, DATA_SHEET, ["日付"] + names, data, "RAW")
        write_mobile(mobile_book, summary, meta, labels, dates, view["sparkline_days"],
                     chart_data=data, data_sheet_id=mobile_data_ws.id, chart_days=view["chart_days"])
        _delete_sheets(mobile_book, ["シート1", "Sheet1"])  # 新規作成時の空シート
        _delete_sheets(book, [MOBILE_SHEET])
    reorder_tabs(book, TAB_ORDER)


def _delete_sheets(book: gspread.Spreadsheet, titles: list[str]) -> None:
    for ws in book.worksheets():
        if ws.title in titles:
            book.del_worksheet(ws)


# 下のタブの並び（左から）。見る用のシートを左に寄せる（無いシートは飛ばす）
TAB_ORDER = [MOBILE_SHEET, CHARTS_SHEET, SINGLE_SHEET, DASHBOARD_SHEET]


def reorder_tabs(book: gspread.Spreadsheet, order: list[str]) -> None:
    by_title = {ws.title: ws.id for ws in book.worksheets()}
    requests = [{"updateSheetProperties": {"properties": {"sheetId": by_title[t], "index": i}, "fields": "index"}}
                for i, t in enumerate(t for t in order if t in by_title)]
    book.batch_update({"requests": requests})

"""部署ごとに役割を分けたAIが、資料をもとに会議をして予算案をまとめるデモ。

使い方:
    # 同梱のサンプル資料（sample_docs/）で会議する
    python ai_meeting/meeting.py

    # Googleドライブのフォルダにある資料で会議する（サービスアカウントにフォルダを共有しておく）
    python ai_meeting/meeting.py --drive-folder <フォルダID>

    # 議題を変える
    python ai_meeting/meeting.py --topic "来年度の採用計画を決める"

仕組み:
    - 各部署のAIは「全社方針」と「自分の部署の資料」だけを読む（他部署の資料は見えない）
    - 進行役（経営企画部）は全部署の資料を受け取っている
    - 発言は全員が共有する議事録に積み上がり、次の発言者はそれを読んで話す
    - 最後に進行役が予算案を決まった形式（JSON）で出す
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import anthropic
import yaml

HERE = Path(__file__).resolve().parent
MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


# --------------------------------------------------------------------------- 資料の読み込み

def load_local_docs(folder: Path) -> dict[str, str]:
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(folder.glob("*.md"))}


def load_drive_docs(folder_id: str) -> dict[str, str]:
    """Googleドライブのフォルダ内の Google ドキュメントを Markdown として読む。

    認証はサービスアカウント（環境変数 GCP_SA_KEY に JSON 文字列、
    または GOOGLE_APPLICATION_CREDENTIALS に JSON ファイルのパス）。
    """
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    if os.environ.get("GCP_SA_KEY"):
        creds = service_account.Credentials.from_service_account_info(
            json.loads(os.environ["GCP_SA_KEY"]), scopes=scopes)
    else:
        creds = service_account.Credentials.from_service_account_file(
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=scopes)
    session = AuthorizedSession(creds)

    docs: dict[str, str] = {}
    page_token = None
    while True:
        res = session.get("https://www.googleapis.com/drive/v3/files", params={
            "q": f"'{folder_id}' in parents and trashed = false "
                 "and mimeType = 'application/vnd.google-apps.document'",
            "fields": "nextPageToken, files(id, name)",
            "pageSize": 100,
            **({"pageToken": page_token} if page_token else {}),
        })
        res.raise_for_status()
        body = res.json()
        for f in body.get("files", []):
            exp = session.get(f"https://www.googleapis.com/drive/v3/files/{f['id']}/export",
                              params={"mimeType": "text/markdown"})
            exp.raise_for_status()
            docs[f["name"]] = exp.content.decode("utf-8")
        page_token = body.get("nextPageToken")
        if not page_token:
            return docs


# --------------------------------------------------------------------------- 参加者

@dataclass
class Member:
    key: str
    name: str
    icon: str
    persona: str
    materials: str  # このAIが読める資料

    def system_prompt(self, topic: str, is_facilitator: bool) -> str:
        role = ("あなたはこの会議の進行役です。" if is_facilitator
                else "あなたは自分の部署の代表として会議に出ています。")
        return f"""あなたは架空の会社「株式会社みらいエール」の{self.name}の責任者です。{role}
人物像：{self.persona}

会議の議題：{topic}

# 話し方のルール
- 会議での発言として、です・ます調の話し言葉で話す。見出し・箇条書き・表は使わない
- 1回の発言は200〜350字。結論を先に言う
- 数字は、下の資料にあるものか、会議でほかの人が言ったものだけを使う。資料にない数字を作らない
- ほかの人の発言に触れるときは「〇〇部さんの〜」と名前を出す
- 自分の部署の立場で話すが、全社の黒字化という目標は共有している
- 発言の先頭に自分の部署名や「：」は付けない

# あなたが持っている資料
{self.materials}
"""


def build_members(roles: dict, docs: dict[str, str]) -> tuple[Member, list[Member]]:
    company = docs[roles["company_doc"]]
    depts = []
    for d in roles["departments"]:
        if d["doc"] not in docs:
            sys.exit(f"資料が見つかりません: {d['doc']}（読み込めた資料: {', '.join(docs)}）")
        depts.append(Member(d["key"], d["name"], d["icon"], d["persona"],
                            f"## 全社方針\n{company}\n\n## 自部署の資料\n{docs[d['doc']]}"))
    f = roles["facilitator"]
    all_docs = "\n\n".join(f"## {name}\n{text}" for name, text in docs.items())
    facilitator = Member(f["key"], f["name"], f["icon"], f["persona"],
                         f"（各部から提出された資料がすべて手元にあります）\n\n{all_docs}")
    return facilitator, depts


# --------------------------------------------------------------------------- 会議の進行

BUDGET_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "予算案の考え方を2〜3文で"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "department": {"type": "string"},
                    "requested": {"type": "number", "description": "要望額（億円）"},
                    "allocated": {"type": "number", "description": "配分額（億円）"},
                    "changes": {"type": "string", "description": "要望から何をどう変えたか。1文"},
                },
                "required": ["department", "requested", "allocated", "changes"],
                "additionalProperties": False,
            },
        },
        "reserve": {"type": "number", "description": "下期の条件付き予備費（億円）。無ければ0"},
        "reserve_condition": {"type": "string", "description": "予備費を出す条件。無ければ空文字"},
        "total": {"type": "number", "description": "配分額の合計＋予備費（億円）"},
        "decisions": {"type": "array", "items": {"type": "string"}, "description": "決まったこと"},
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "task": {"type": "string"},
                    "due": {"type": "string"},
                },
                "required": ["owner", "task", "due"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "items", "reserve", "reserve_condition", "total",
                 "decisions", "action_items"],
    "additionalProperties": False,
}


class Meeting:
    def __init__(self, client: anthropic.Anthropic, topic: str, cap: float,
                 facilitator: Member, depts: list[Member]):
        self.client = client
        self.topic = topic
        self.cap = cap
        self.facilitator = facilitator
        self.depts = depts
        self.log: list[dict] = []  # {"phase", "speaker", "icon", "text"}

    # ---- 1回の発言
    def transcript_text(self) -> str:
        if not self.log:
            return "（まだ発言はありません）"
        return "\n\n".join(f"【{e['speaker']}】{e['text']}" for e in self.log)

    def speak(self, member: Member, phase: str, instruction: str) -> str:
        is_fac = member is self.facilitator
        user = f"# ここまでの議事録\n{self.transcript_text()}\n\n# 今のあなたの番\n{instruction}"
        print(f"\n{member.icon} {member.name}  〔{phase}〕\n", flush=True)
        with self.client.beta.messages.stream(
            model=MODEL,
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "medium"},
            cache_control={"type": "ephemeral"},
            system=member.system_prompt(self.topic, is_fac),
            messages=[{"role": "user", "content": user}],
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
            msg = stream.get_final_message()
        print(flush=True)
        if msg.stop_reason == "refusal":
            raise RuntimeError(f"{member.name} の発言が拒否されました: {msg.stop_details}")
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        self.log.append({"phase": phase, "speaker": member.name, "icon": member.icon, "text": text})
        return text

    def finance(self) -> Member:
        return next(d for d in self.depts if d.key == "finance")

    # ---- 会議全体
    def run(self) -> dict:
        names = "、".join(d.name for d in self.depts)
        self.speak(self.facilitator, "開会",
                   f"会議を始めてください。参加者は{names}です。議題、予算の上限（{self.cap}億円）、"
                   "進め方（①各部の要望説明 ②論点整理と調整 ③予算案のとりまとめ）を短く伝え、"
                   "最初の部署に説明をお願いしてください。")

        for d in self.depts:
            if d.key == "finance":
                instr = ("管理部門の要望を説明したうえで、ここまでの各部の要望を合計すると上限を"
                         "どれだけ超えるかを指摘し、経理・財務部としての調整の考え方を述べてください。")
            else:
                instr = ("自部署の来年度の予算要望を説明してください。要望額、いちばん大事な施策と"
                         "その効果、他部署にお願いしたいことがあればそれも。")
            self.speak(d, "要望説明", instr)

        self.speak(self.facilitator, "論点整理",
                   "各部の説明を受けて、論点を2〜3個に絞って示してください。部署どうしの依存関係"
                   "（ある部の施策が別の部の成果を左右するもの）に注目し、"
                   "どの部にどんな譲歩や工夫を考えてほしいかを、部署名を挙げて具体的に投げかけてください。")

        for d in self.depts:
            self.speak(d, "調整",
                       "進行役の投げかけとほかの部の発言を受けて、自部署として出せる調整案を"
                       "金額つきで示してください。削る代わりに条件や他部署への頼みがあれば言ってください。"
                       "ほかの部の案に賛成・懸念があれば一言触れてください。")

        self.speak(self.facilitator, "調整案",
                   f"ここまでの調整案をもとに、部署ごとの配分額と合計（上限{self.cap}億円以内）を"
                   "口頭で示してください。下期の条件付き予備費を置くかどうかも決めてください。")

        self.speak(self.finance(), "確認",
                   "進行役の調整案を、合計が上限以内か、黒字化の見込みに無理がないかの観点で確認し、"
                   "了承するか、条件をつけて了承するかを述べてください。")

        budget = self.final_budget()
        self.speak(self.facilitator, "閉会",
                   "予算案が固まりました。決まったことと、次回までの宿題を短くまとめて会議を締めてください。")
        return budget

    def final_budget(self) -> dict:
        print(f"\n{self.facilitator.icon} {self.facilitator.name}  〔予算案の作成〕\n", flush=True)
        prompt = (f"# 議事録\n{self.transcript_text()}\n\n"
                  "# 依頼\n会議で合意した内容を予算案にまとめてください。"
                  "部署は議事録に出てきた順に、要望額は各部の資料の値、配分額は会議で合意した値を使う。"
                  f"total は配分額の合計＋予備費で、{self.cap}億円以内にすること。金額の単位は億円。")
        with self.client.beta.messages.stream(
            model=MODEL,
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "high",
                           "format": {"type": "json_schema", "schema": BUDGET_SCHEMA}},
            system=self.facilitator.system_prompt(self.topic, True),
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            msg = stream.get_final_message()
        if msg.stop_reason == "refusal":
            raise RuntimeError(f"予算案の作成が拒否されました: {msg.stop_details}")
        budget = json.loads(next(b.text for b in msg.content if b.type == "text"))

        # AIの足し算を鵜呑みにしない
        computed = round(sum(i["allocated"] for i in budget["items"]) + budget["reserve"], 2)
        budget["total_check"] = {"computed": computed, "matches": abs(computed - budget["total"]) < 0.005,
                                 "within_cap": computed <= self.cap + 1e-9}
        print(budget_markdown(budget, self.cap))
        return budget


# --------------------------------------------------------------------------- 出力

def budget_markdown(b: dict, cap: float) -> str:
    rows = ["| 部署 | 要望額 | 配分額 | 増減 | 調整の内容 |", "|---|---:|---:|---:|---|"]
    for i in b["items"]:
        diff = i["allocated"] - i["requested"]
        rows.append(f"| {i['department']} | {i['requested']:.2f} | {i['allocated']:.2f} | "
                    f"{diff:+.2f} | {i['changes']} |")
    req = sum(i["requested"] for i in b["items"])
    alloc = sum(i["allocated"] for i in b["items"])
    if b["reserve"]:
        rows.append(f"| 予備費（下期・条件付き） | – | {b['reserve']:.2f} | | {b['reserve_condition']} |")
    rows.append(f"| **合計** | **{req:.2f}** | **{alloc + b['reserve']:.2f}** | | 上限 {cap:.1f}億円 |")
    chk = b["total_check"]
    note = "" if chk["matches"] and chk["within_cap"] else \
        f"\n\n> ⚠ 合計の確認：計算上 {chk['computed']}億円（AIの記載 {b['total']}億円、上限内: {chk['within_cap']}）"
    out = [f"## 2027年度 予算案（単位：億円）\n\n{b['summary']}\n", "\n".join(rows) + note,
           "\n### 決まったこと", *[f"- {d}" for d in b["decisions"]],
           "\n### 宿題", *[f"- {a['owner']}：{a['task']}（{a['due']}）" for a in b["action_items"]]]
    return "\n".join(out)


def transcript_markdown(m: Meeting) -> str:
    lines = [f"# AI会議 議事録\n\n- 議題：{m.topic}\n- 日時：{datetime.now():%Y-%m-%d %H:%M}\n"
             f"- 参加：{m.facilitator.name}（進行）、" + "、".join(d.name for d in m.depts) + "\n"]
    phase = None
    for e in m.log:
        if e["phase"] != phase:
            phase = e["phase"]
            lines.append(f"\n## {phase}\n")
        lines.append(f"**{e['icon']} {e['speaker']}**\n\n{e['text']}\n")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topic", default="2027年度の部門予算案を決める")
    ap.add_argument("--drive-folder", help="資料を置いた Google ドライブのフォルダID")
    ap.add_argument("--docs", type=Path, default=HERE / "sample_docs", help="ローカルの資料フォルダ")
    ap.add_argument("--roles", type=Path, default=HERE / "roles.yaml")
    ap.add_argument("--out", type=Path, default=HERE / "output")
    args = ap.parse_args()

    roles = yaml.safe_load(args.roles.read_text(encoding="utf-8"))
    docs = load_drive_docs(args.drive_folder) if args.drive_folder else load_local_docs(args.docs)
    facilitator, depts = build_members(roles, docs)

    meeting = Meeting(anthropic.Anthropic(), args.topic, roles["budget_cap"], facilitator, depts)
    budget = meeting.run()

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "transcript.md").write_text(transcript_markdown(meeting), encoding="utf-8")
    (args.out / "budget.md").write_text(budget_markdown(budget, roles["budget_cap"]), encoding="utf-8")
    (args.out / "meeting.json").write_text(
        json.dumps({"topic": args.topic, "log": meeting.log, "budget": budget},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n保存しました: {args.out}/transcript.md, budget.md, meeting.json")


if __name__ == "__main__":
    main()

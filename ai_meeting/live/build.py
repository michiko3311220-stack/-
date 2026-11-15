"""live/template.html に資料・役割・見本を埋め込んで live/ai_meeting_live.html を作る。"""
import json
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
roles = yaml.safe_load((ROOT / "roles.yaml").read_text(encoding="utf-8"))
docs = {p.stem: p.read_text(encoding="utf-8") for p in sorted((ROOT / "sample_docs").glob("*.md"))}
sample = json.loads((ROOT / "sample_output" / "meeting.json").read_text(encoding="utf-8"))
LOOK = {"planning": ("企", "1F2A44"), "user": ("ユ", "E8574B"), "supporter": ("サ", "D99A1E"),
        "cs": ("C", "2A9D8F"), "dev": ("開", "6C5CE7"), "hr": ("人", "3E8E41"), "finance": ("経", "7A8597")}
f = roles["facilitator"]
people = [{"key": f["key"], "name": f["name"], "persona": f["persona"], "fac": True,
           "ch": LOOK[f["key"]][0], "color": LOOK[f["key"]][1]}]
for d in roles["departments"]:
    people.append({"key": d["key"], "name": d["name"], "persona": d["persona"], "doc": d["doc"],
                   "ch": LOOK[d["key"]][0], "color": LOOK[d["key"]][1]})
data = {
    "topic": sample["topic"], "plan": roles["plan"], "companyDoc": roles["company_doc"],
    "driveFolder": "1UTI3QL3yDEe8uXnlq4YkMb5GWxiMXIbG",
    "docs": docs, "roles": people, "sampleLog": sample["log"], "sampleBudget": sample["budget"],
}
blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
html = (HERE / "template.html").read_text(encoding="utf-8").replace("__DATA__", blob)
(HERE / "ai_meeting_live.html").write_text(html, encoding="utf-8")
print("wrote", HERE / "ai_meeting_live.html", len(html))

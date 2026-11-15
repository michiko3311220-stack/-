# AI会議デモ

部署ごとに役割を分けたAIが、Googleドライブの資料（各部署の課題・目標・予算要望）をもとに会議をして、
来年度の予算案をまとめるデモです。会社「株式会社みらいエール」は架空です。

## 仕組み

- 参加者は `roles.yaml` で決める。進行役（経営企画部）と6部署（ユーザー獲得・サポーター獲得・カスタマーサポート・開発・人事・経理財務）
- 各部署のAIが読めるのは「全社方針」と「自分の部署の資料」だけ。進行役だけは全部署の資料を持っている
- 発言は全員で共有する議事録に積み上がり、次の発言者はそれを読んでから話す
- 流れ：開会 → 要望説明（6部署）→ 論点整理 → 調整（6部署）→ 調整案 → 経理の確認 → 予算案（JSON）→ 閉会
- 予算案の合計はプログラムで検算する（AIの足し算をそのまま信じない）
- モデルは `claude-opus-5-5`。断られた場合に別のモデルで再実行する設定（`fallbacks: "default"`）を入れている

## 実行のしかた

### GitHub Actions（おすすめ）
1. リポジトリの Secrets に `ANTHROPIC_API_KEY` を登録する
2. Googleドライブの資料を使う場合は、既存のサービスアカウント（`GCP_SA_KEY`）のメールアドレスに
   資料フォルダを「閲覧者」で共有し、GCP プロジェクトで Google Drive API を有効にする
3. Actions → `ai-meeting` → Run workflow。議題とフォルダIDを入れて実行する
   （フォルダIDを空にすると `sample_docs/` を使う）
4. 実行ページの Summary に予算案と議事録が表示され、`ai-meeting-output` に
   `transcript.md` / `budget.md` / `meeting.json` が保存される

`workflow_dispatch` はデフォルトブランチにあるワークフローしか動かないため、先にこのブランチをマージする。

### 手元で
```bash
pip install -r ai_meeting/requirements.txt
export ANTHROPIC_API_KEY=...
python ai_meeting/meeting.py                        # sample_docs/ で会議
python ai_meeting/meeting.py --drive-folder <ID>    # ドライブの資料で会議
python ai_meeting/meeting.py --topic "来年度の採用計画を決める"
```

## ファイル

| パス | 内容 |
|---|---|
| `meeting.py` | 会議を動かす本体 |
| `roles.yaml` | 参加者の役割・人物像・読む資料・予算の上限 |
| `sample_docs/` | 架空の会社の資料（ドライブに置いたものと同じ内容） |
| `sample_output/` | 見本の議事録と予算案。Claude Code がプログラムと同じ進め方と資料で書いたもので、実際のAPI実行の結果ではない |
| `slides/build_deck.js` | 紹介スライド（.pptx）を作るスクリプト。予算のグラフは `meeting.json` から作る |
| `slides/ai_meeting_demo.pptx` | できあがったスライド（Googleスライドにも変換済み） |

スライドを実際の実行結果で作り直すとき：
```bash
npm install pptxgenjs
node ai_meeting/slides/build_deck.js ai_meeting/output/meeting.json
```
見どころのスライド（6〜8枚目）の引用は見本の議事録から選んでいるので、実際の結果に合わせて書き換える。

## 資料の書き方のコツ
- 数字を具体的に書く（AIは資料にない数字を使わないように指示している）
- 「譲れない点」「削れる点」「他部署へのお願い」を書いておくと、調整の議論が具体的になる
- 部署どうしがつながる事実（例：返信が遅いと解約率が2.1倍）を入れると、部署をまたいだ議論が起きやすい

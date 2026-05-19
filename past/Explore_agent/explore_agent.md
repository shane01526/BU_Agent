# explore_agent

## 1. 背景與動機 (Background)

各 BU 在被金控要求「導入 AI」時，常見三種起點：

| 起點 | BU 狀態 | 既有 agent 是否能 handle |
| --- | --- | --- |
| (i) **明確構想** | 「我想做產險 NL01008 店面照片風險評估」 | ✅ Consult_agent 直接接 |
| (ii) **模糊構想** | 「我想做點 AI 但不確定細節」 | ✅ Consult_agent —— 章節訪談第 1 題即觸發動機 / keystone case 等 archetype 題（見 `Consult_agent/consult_agent.md` Appendix H 章節題庫補強） |
| (iii) **無構想** | 「上面要我們導入 AI，但我不知道要在哪個環節用」 | ❌ 卡在 Pre-flight modal，連 slash command 都打不出來 |

**Explore_agent 補齊起點 (iii)**：在 BU 還沒有 AI 工具構想時，透過結構化探索對話，從 BU 的日常工作中挖出 **3 個候選 AI 工具方向**；BU 選一個之後**自動接給 Consult_agent**進入正式 BRD 草擬流程，不需重答 metadata。

> Diff_agent / Consult_agent / Explore_agent 三姊妹專案的職責分工：
> - **Explore**：0 → 候選方向（Discovery）
> - **Consult**：候選方向 → BRD v1.0（Creation）
> - **Diff**：BRD v1.0 → BRD v1.1+（Update）

---

## 2. 目標 (Goals & Non-Goals)

### 2.1 Goals

- **G1**：不要求 BU 預先有 AI 構想 —— 入口僅需 BU 別與一兩句現況描述。
- **G2**：透過 5–8 題結構化探索題，挖出 BU 部門的 **重複性 / 痛苦 / 規則化 / 規模** 等可被 AI 切入的訊號。
- **G3**：用 5 維度 **AI 適用度 rubric**（規則重複度 / 資料可得性 / 後果可逆性 / 規模 ROI / 現有解空缺）對候選方向打分，輸出 **top 3 候選**。
- **G4**：與 Consult_agent **零摩擦 hand-off** —— BU 選定一個 candidate 後，Consult_agent pre-flight 自動帶入（`bu` / `process_target` / `project_type` / `one_line_goal` 等），BU 只需確認 / 微調。
- **G5**：與 Diff / Consult 共用同一個 Slack bot 帳號 / 同一個 Postgres / 同一份 OAuth schema（雖 Explore 本身不寫 Doc，`oauth_tokens` 表共用以利未來擴展）。

### 2.2 Non-Goals

- ❌ **不寫 BRD**：Explore 只輸出 candidate JSON，完整 BRD 由 Consult_agent 接手。
- ❌ **不做技術選型**：不討論用哪個 VLM / LLM / RAG；那是 AI 科 / CD 科職責。
- ❌ **不做組織層級 AI roadmap**：本 agent 是 BU SME 個人對話，不替整個部門 / 公司規劃 AI 戰略。
- ❌ **不算實際 ROI 金額**：rubric 只到「規模等級」(1–5)，不算實際省下多少錢。
- ❌ **不持續學習 / cross-BU 推薦**：每場探索獨立；不從歷史推薦「銀行 BU 該做 X」。
- ❌ **不替 BU 決策**：agent 永遠是「列出候選 + 評分」，最終選擇權在 BU；agent 不會自動把 top-1 直接送 Consult。

---

## 3. 使用者與情境 (Users & Use Cases)

### 3.1 目標使用者

| 角色 | 類別 | 互動模式 | 主要訴求 |
| --- | --- | --- | --- |
| **BU SME** | 主要（輸入 + 輸出） | Slack 自然語言對話 | 我想用 AI，但不知道要在哪個環節用 |
| **BA** | 次要（監督） | 收到候選清單後 review | 確保候選方向合理、避開無 AI 必要的需求 |
| **AI 科 / CD 科** | 觀察者 | （可選）review 候選清單做技術早期 feasibility | 提早識別不可行候選，避免後續 BRD 白走 |

### 3.2 Agent 服務目標

> 一句話：**讓「想用 AI 但不知道從哪用」的 BU 透過對話找到 3 個候選方向，並順暢接入 Consult_agent 進 BRD 流程。**

由此推導兩條設計準則：

1. **對 BU 友善**：入口零門檻（不需 metadata），題目偏口語，每題附「Why we ask」透明化。
2. **對下游 Consult_agent 友善**：candidate 格式直接對齊 Consult pre-flight 8 欄，hand-off 零摩擦。

### 3.3 BU 端使用情境

**ES-1（BU 完全沒構想）**

壽險 BU 主管接到金控指示「今年要導入 AI 工具」。BU SME 完全不知道要做什麼。在 Slack 輸入 `/brd-explore`，Explore_agent 不要求任何 metadata，直接從「你部門最近 4 週做最多的工作是什麼」開始問。經 6 題探索，agent 收斂出 3 個候選方向（理賠文件 OCR、保戶來電意圖分類、續保提醒分流），BU 看完評分後選定「續保提醒分流」（高規則重複度 + 高資料可得性 + 高後果可逆性）→ 自動帶入 Consult_agent。

**ES-2（BU 有大致範圍但細節空白）**

銀行 BU 知道「想做點跟授信有關的 AI」但不知具體切哪段。在 Slack 輸入 `/brd-explore 想做授信流程的 AI`。Explore_agent 把 raw text 當 hint，題目聚焦在授信流程（收件 / 初審 / 風控 / 撥款 / 後管），收斂出 3 個候選（收件文件 OCR、授信評分、撥款後異常偵測）。

**ES-3（候選都不滿意，二輪探索）**

產險 BU 看完 3 個候選後覺得「都不太對」，點「重新探索」。Explore_agent 把第一輪答案標為 cold，從不同角度切入（改問跨系統手抄、客戶溝通、報表整理），產出第二輪 3 個候選；最多 2 輪後若仍不滿意 → @ BA 接手對焦。

### 3.4 不適用情境 (Out-of-scope)

- ❌ BU **明確知道要做 X**（對應 Consult_agent US-1）：直接走 `/brd-new`，不必經 Explore。
- ❌ 想做的事**完全不適合 AI**（例：「請 AI 替我們開會」「請 AI 重組組織」）：rubric 會打低分，agent 回 "本次探索沒有合適 AI 候選"，建議 (a) 改用 RPA / SOP 數位化；(b) 重新跟 BA 對焦需求。
- ❌ 想做的事**屬於 IT infra / cybersecurity**（非 BU 業務需求）：agent redirect 至 IT 部門。

### 3.5 與 Consult / Diff 三姊妹的關係

| 面向 | Explore | Consult | Diff |
| --- | --- | --- | --- |
| 生命週期 | 0 → 候選方向 | 候選方向 → BRD v1.0 | BRD v1.0 → v1.1+ |
| 入口 slash | `/brd-explore` | `/brd-new`（含 `--from-exploration`） | `/brd-update` |
| 主要輸出 | candidates JSON | BRD Doc + summary.json | suggesting edits |
| Doc 互動 | ❌ 不寫 | ✅ 寫 final | ✅ 寫 suggesting |
| 共用元件 | bot / Postgres / oauth_tokens | bot / Postgres / oauth_tokens / Doc API | bot / Postgres / oauth_tokens / Doc API |
| Hand-off | → Consult（deep link） | → Diff（Doc 共用） | (loop) |

**端對端 BU 旅程：**

```
[BU 想用 AI 但沒構想]
   ↓ /brd-explore
[Explore_agent 找出 3 候選]
   ↓ BU 選 1 個 → hand-off
[Consult_agent 寫 BRD v1.0]
   ↓ BA 加會議錄音
[Diff_agent 增量更新 v1.1+]
```

### 3.6 Hand-off 至 Consult_agent

BU 選定 candidate 後 Explore_agent：

1. 寫入 `explorations` 表（含 candidate full payload + `selected_candidate_idx`）
2. 在 Slack 發 hand-off 訊息（含 deep-link button）：
   ```
   ✅ 已選定：續保提醒分流
   下一步將進入 Consult_agent 進行 BRD 草擬
                    [▶ 進入 Consult_agent]
   ```
3. BU 點按鈕 → 觸發 `/brd-new --from-exploration ex_01HW...`
4. Consult_agent `collect_metadata` node 偵測 `--from-exploration` flag，從 `explorations` 表讀 candidate 並把 pre-flight modal **8 欄全部預先填好**（包含 `one_line_goal` 由 Explore 起草，BU 可微調）
5. BU 確認 modal → 直接進章節訪談（原本要回答的 metadata 已備齊；anchor case 由「需求背景」第 2 題 keystone 收集，見 Consult §4.2 F-2.2.4）

> **Consult_agent 端需要的小改動**：`consultations` 表新增 `from_exploration_id` 欄位；`collect_metadata` node 加 5 行 fast-path（詳 Appendix E）。

### 3.7 功能分層 (Feature Tiering)

MVP 範圍 = Tier 1。

| Tier | 功能 |
| --- | --- |
| **1** | `/brd-explore` 入口；極簡 modal（bu + role brief）；探索題庫對話；5 維度 rubric 評分；top 3 candidate 呈現；Hand-off deep link 至 Consult；**Session 管理**（啟動位置守則 + 自動建 thread + thread-aware auto-resume + interrupt footer 暫存提示，F-5.1 / F-5.4 / F-3.1） |
| **2** | 「重新探索」二輪流程；`not_recommended` 列表附原因；條件題（EX-6/7/8）trigger 邏輯 |
| **3**（V2） | LLM-aware 動態題目重排（依答案調整後續題）；跨 BU 候選借鏡（壽險看得到產險已做過的方向）；**App Home Dashboard**（Consult + Explore 統一視覺入口、quick-action 按鈕，F-5.5） |

---

## 4. 功能需求 (Functional Requirements)

### 4.1 輸入 (Input)

- **F-1.1 Slash command**：
   - `/brd-explore` — 純探索（無預設方向）
   - `/brd-explore <一句話描述>` — 帶 raw text hint（如：「想做授信相關 AI」）；hint 不限縮探索範圍，僅作為 LLM 重排題目順序的訊號
   - `/brd-explore-resume <exploration_id>` — 接續中斷的探索
   - `/brd-explore-list` — 列出當前使用者進行中 / 已完成的探索

- **F-1.2 簡易 Pre-flight**（**只 2 欄**，跟 Consult 的 8 欄 modal 區別開來）：
   - `bu` (產險 / 壽險 / 銀行 / 證券) — 必填 enum
   - `current_role_brief` (free text < 100 字：你目前主要負責什麼工作) — 必填，作為探索題的 anchor

   **設計理由**：BU 連工具方向都沒有時，多問一欄都是門檻；2 欄是「能讓 agent 開始問問題」的最低資訊量。

### 4.2 處理 Pipeline

- **F-2.1 探索題庫載入**（`load_questions` node）：
   - 從 `explore_configs/<bu>.yaml` 載入該 BU 的探索題序列（5 必選 + 3 條件題；見 Appendix A）
   - 若 `raw_input_text` 存在，LLM 重排題目順序（與 hint 相關度高的題目前移），但不刪題
   - 新 BU onboard 不改 graph code，只加 `explore_configs/<新 BU>.yaml`

- **F-2.2 探索題對話**（`discovery_loop` sub-loop）：
   1. **Ask sub-node**：一次一題，`interrupt()` 等 BU 回應；訊息含進度（`[探索] 3/6`）+ Why we ask + Skip 按鈕
   2. **Probe sub-node**：偵測模糊 / 過短回答 → 自動 follow-up（同 Consult §4.2 F-2.2.2 答覆品質守門機制；vague_keywords + min_length 雙條件）
   3. **Cumulate**：答案累積進 `state.discovery_responses`

   **答覆品質守門**：
   - 連續 3 題答 < 10 字 或 全 Skip → agent 主動建議「先離線整理工作清單再回來」
   - 條件題（EX-6/7/8）依 `trigger_condition` 動態啟用，不滿足 → 自動跳過

- **F-2.3 痛點 cluster**（`cluster_pain_points` node）：
   探索完成後，LLM 用 `with_structured_output` 對所有答案做 clustering：
   - 把同性質的痛點合併（例：「對保文件手抄」+「核保文件手抄」 → 「跨流程手抄文件」）
   - 輸出 N 個 candidate clusters（通常 3–7），每個 cluster 含 label / summary / source_responses

- **F-2.4 AI 適用度評分**（`score_candidates` node）：
   對每個 cluster 用 5 維度 rubric 打分（見 Appendix B）：

   | 維度 | 高分意義 |
   | --- | --- |
   | `rule_repetition` 規則重複度 | 有清楚 SOP / 規則表 → 5 ；憑直覺 → 1 |
   | `data_availability` 資料可得性 | 已系統化 → 5 ；紙本 / 散落 → 1 |
   | `reversibility` 後果可逆性 | 僅輔助分流 → 5 ；不可逆執行 → 1 |
   | `scale` 規模 ROI | 每月 500+ 件 → 5 ；< 10 件 → 1 |
   | `existing_solution_gap` 現有解空缺 | 完全人工 → 5 ；已有工具運作良好 → 1 |

   **threshold**：總分 ≥ 15 / 25 進 top 3；12–14 列 `not_recommended` 附「重新探索後可能合適」；< 12 標 not suitable，建議 RPA / SOP 數位化。

- **F-2.5 預測 Consult metadata**（`predict_consult_fields` node）：
   對 top 3 每個 candidate，LLM 預測 Consult_agent pre-flight 該填的 8 欄：
   - `process_target` / `project_type` / `policy_code` / `execution_mode` / `result_type` / `integration_systems` / `one_line_goal_draft`

   `project_type` 從該 BU `template_configs/<bu>/preflight.yaml#project_types` 選一（受限選項 → LLM `with_structured_output` 確保合法值）。

- **F-2.6 候選呈現 + 選擇**（`present_in_slack` + `await_selection` node）：
   發 top 3 candidate 訊息（含 5 維度評分 + reasoning + 預估規模）；
   `interrupt()` 等 BU 點按鈕：`[▶ 選此候選]` × 3 + `[全部不滿意，重新探索]` + `[放棄]`。

- **F-2.7 Hand-off**（`handoff_to_consult` node）：
   寫入 `explorations.selected_candidate_idx` + `selected_at`；發 Slack hand-off 訊息（見 §3.6）；不直接呼叫 Consult graph，而是發 deep link 讓 BU 主動觸發（保留決策權給 BU）。

### 4.3 對話呈現 (Conversation Presentation)

- **F-3.1 探索題訊息格式**（每題）：
   - 進度 + 題號（`[探索] 3 / 6 · EX-3 抱怨集中地`）
   - 題目本身（口語化，避免術語）
   - 一行 `💡 Why we ask:` 透明化問題目的
   - `[Skip this question]` 按鈕
   - **底部 footer（每則 interrupt 訊息固定）**：
      - 「💾 進度已自動暫存 · session: `<slug>`」（提示 BU 不必擔心丟失進度）
      - 「想開另一個 session？到 `#brd-consultation` 主層打 `/brd-new` 或 `/brd-explore`」（給 BU 心理上「可以平行開新 session」許可）

- **F-3.2 候選呈現訊息**（top 3 一則訊息）：
   每個 candidate 含：
   - 排名 emoji（🥇🥈🥉）+ 標題（LLM 命名）
   - 一句話定位
   - 5 維度評分（文字呈現，例：`⭐⭐⭐⭐ (21/25)` + 5 行 dimension-by-dimension）
   - 為什麼適合 AI（2–3 條 reasoning，每條對應一個高分維度）
   - 預估規模（每週 / 每月 N 件）
   - `[▶ 選此候選]` 按鈕

   訊息底部固定按鈕：`[全部不滿意，重新探索]` / `[放棄，先離線討論]`。

- **F-3.3 Hand-off 訊息**：選定後一則訊息列出已預填的 Consult metadata + `[▶ 進入 Consult_agent]` deep link 按鈕（見 §3.6）。

### 4.4 輸出 (Candidate JSON)

`explorations.result_json` 為 agent 主要輸出（見 Appendix C 完整範例）。Top-level keys：

```
{
  exploration_id, bu, current_role_brief, raw_input_text,
  discovery_responses,        # { "EX-1": "...", ... }
  pain_clusters,              # cluster_pain 輸出
  candidates,                 # top 3，含 ai_suitability + predicted_consult_fields
  not_recommended,            # 未進 top 3 的 cluster + reason
  selected_candidate_idx,     # BU 選擇
  selected_at,
  handed_off_to_consultation_id,  # 後續 Consult 寫回
  status,
  generated_at
}
```

### 4.5 Slack Bot 互動

- **F-5.1 Slash command 與啟動位置**：
   - **指令清單**：見 F-1.1（`/brd-explore` / `/brd-explore-resume` / `/brd-explore-list`）
   - **啟動位置規範**：
      - `/brd-explore` **必須在 channel 主層**（如 `#brd-consultation`）**或 BU 與 bot 的 DM** 觸發
      - 若 BU 在現有 thread 內打 `/brd-explore` → bot 回 **ephemeral 訊息**「請到 channel 主層開新 session（避免與該 thread 既有 session 混淆）」並 reject
      - **設計理由**：thread 內既有 active session 會啟用 thread-aware auto-resume（F-5.4 Layer 1）；slash 啟動行為與 prose 接續行為必須清楚分流
   - **每個 session = 一個獨立 thread**：
      - 收到 `/brd-explore` 後，bot **主動在 channel 主層建立一則 parent message**（含 session slug + 「探索開場」介紹）→ 後續探索題訊息 / 候選呈現 / hand-off 訊息 **全部在該 parent message 的 thread 下展開**
      - `explorations.slack_thread_ts` 儲存此 thread_ts，作為 `exploration_id` 的 1:1 反查鍵（§8.1）
      - **多 session 並存**：BU 可同時有多個 active thread；同 channel 視覺上清楚分離，**不會多出聊天室**
   - **同 BU active session 上限**：`explorations` + `consultations` `status='in_progress'` 加總 ≤ 3；超過時 `/brd-explore` reject 並列出進行中清單
- **F-5.2 OAuth**：共用 `oauth_tokens` 表（本 agent 不使用 Google API；保留共用以利未來擴展，例如將候選清單存到 Drive 給 BA review）。
- **F-5.3 互動 UI**（Slack Block Kit）：
   - 簡易 modal（bu + role brief）
   - 探索題訊息（thread message + Skip 按鈕 + footer 暫存提示，見 F-3.1）
   - 候選呈現訊息（3 candidate cards + 4 顆按鈕）
   - Hand-off 訊息（含 deep link button）
- **F-5.4 中斷 / 續寫（兩層 resume 機制）**：
   - **Layer 1（主路徑）— Thread-aware auto-resume**：
      - BU 直接回到原 thread 發任何訊息 → bot 從 `slack_thread_ts` 反查 `exploration_id` → 自動還原 LangGraph state 並接續對應 node
      - **零 slash command、零 ID 輸入**；適用 BU 找得回原 thread（最常見情境）
   - **Layer 2（fallback）— `/brd-explore-resume <exploration_id>`**：
      - 適用：BU 找不到原 thread（換 channel / 換 device / 距離太久滾出視窗）
      - 流程：先打 `/brd-explore-list` 列出進行中 session（顯示 slug 而非 UUID）→ 複製 `<exploration_id>` → `/brd-explore-resume <id>`
      - **僅作為 fallback**，不是主要 resume 路徑
   - **State 持久化**：PostgresSaver checkpointer 保存所有 graph state；任一 interrupt 點皆可斷後續寫
   - **歧義處理**：BU 在 Explore 結束 hand-off 後，原 thread 的 `slack_thread_ts` 重綁到新建的 `consultation_id`；同一 thread 任一時刻只能綁一個 active session
   - **被動提醒**：候選呈現後若 BU 沒回應 → 24 小時後 reminder
- **F-5.5 App Home Dashboard（V2，Tier 3）**：
   - Slack App Home tab 顯示 BU 的所有 active / completed sessions（Consult + Explore 合併呈現）
   - 卡片內容：session slug、status、進度（探索題答了幾題 / 是否已產出候選）、上次活動時間、`[▶ 繼續]` / `[⚙ 詳情]` 按鈕
   - 頂端固定兩顆 quick-action 按鈕：`[+ 新諮詢]`（觸發 `/brd-new`）、`[+ 新探索]`（觸發 `/brd-explore`）
   - **延後到 V2 的理由**：MVP 階段 Slack 內建「Threads」左側欄已能覆蓋大多回找需求；App Home 是強化體驗
   - **實作 hint**：透過 Slack `app_home_opened` event + `views.publish` API；Consult 與 Explore 共用此 view（同 bot 帳號）

---

## 5. 系統架構 (Architecture)

```
                      ┌─────────────┐
   Slack User ──────▶ │  Slack Bot  │ ←─── 共用 bot 帳號
                      │ (slack-bolt)│      (Diff / Consult / Explore 三 agent 共用)
                      └──────┬──────┘
                             │ /brd-explore [raw text?]
                             ▼
   ╔═════════════════ LangGraph App (Explore) ══════════════════╗
   ║                                                            ║
   ║   ┌─────────────────┐                                      ║
   ║   │collect_context  │ (簡易 modal: bu + current_role_brief) ║
   ║   └────┬────────────┘                                      ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │load_questions   │ (依 bu 載 yaml + raw_text hint 重排)  ║
   ║   └────┬────────────┘                                      ║
   ║        ▼                                                   ║
   ║   ┌──────────────────────────────────────┐                 ║
   ║   │ discovery_loop (5 必選 + 3 條件題)   │                  ║
   ║   │   ┌──────────┐                       │                 ║
   ║   │   │ask       │ ← interrupt() 等 BU   │                 ║
   ║   │   └────┬─────┘                       │                 ║
   ║   │        ▼                              │                ║
   ║   │   ┌──────────┐                       │                 ║
   ║   │   │probe     │ (模糊 / 過短偵測 →    │                  ║
   ║   │   └────┬─────┘  自動 follow-up)      │                 ║
   ║   └───────────────────────────────────────┘                ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │cluster_pain     │ (LLM 把答案 cluster 成痛點集合)        ║
   ║   └────┬────────────┘                                      ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │score_candidates │ (5 維度 rubric, top 3)                ║
   ║   └────┬────────────┘                                      ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │predict_consult  │ (LLM 預測 Consult pre-flight 8 欄)    ║
   ║   └────┬────────────┘                                      ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │present_in_slack │ (發 top 3 候選訊息)                   ║
   ║   └────┬────────────┘                                      ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │await_selection  │ ← interrupt() 等 BU 點按鈕            ║
   ║   └────┬────────────┘   (選/重探索/放棄)                    ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │handoff_to_      │ (寫 selected_candidate_idx,           ║
   ║   │  consult        │  發 deep link 給 Consult)            ║
   ║   └────┬────────────┘                                      ║
   ║        ▼                                                   ║
   ║      END                                                   ║
   ║                                                            ║
   ║   checkpointer = PostgresSaver (HITL resume)               ║
   ╚════════════════════════════════════════════════════════════╝
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
  ┌──────────┐      ┌──────────────┐    ┌──────────────────┐
  │Explore   │      │Postgres      │    │Consult_agent     │
  │Configs   │      │(explorations │    │(共用 oauth_tokens;│
  │(YAML)    │      │ + oauth_     │    │ 由 Explore 透過  │
  │          │      │   tokens *)  │    │ deep link 觸發)  │
  └──────────┘      └──────────────┘    └──────────────────┘
                          * 共用 Diff / Consult / Explore
```

### 5.1 Components

- **Slack Bot (`slack-bolt`)**：共用 bot 帳號；新增 `/brd-explore` slash command 路由至本 graph。
- **LangGraph App (Explore)**：核心 pipeline，**8 個 main node + 1 個 sub-loop（內含 2 sub-nodes）**：
   1. `collect_context` —— 簡易 modal 收 bu + current_role_brief
   2. `load_questions` —— 依 bu 載入 `explore_configs/<bu>.yaml`；若有 raw text 則 LLM 重排題目順序
   3. **`discovery_loop`（sub-loop）** —— `ask` + `probe` 兩個 sub-nodes 對 5 必選 + 3 條件題逐題執行；以 `interrupt()` 等 Slack 端 BU 回應
   4. `cluster_pain_points` —— LLM `with_structured_output` 把答案 cluster
   5. `score_candidates` —— 5 維度 rubric 打分，輸出 top 3 + not_recommended
   6. `predict_consult_fields` —— LLM 對 top 3 預測 Consult pre-flight 8 欄
   7. `present_in_slack` —— 發 top 3 候選訊息
   8. `await_selection` —— `interrupt()` 等 BU 點按鈕（選 / 重探索 / 放棄）
   9. `handoff_to_consult` —— 寫 `selected_candidate_idx`，發 deep link 訊息
- **Explore Configs**：`explore_configs/<bu>.yaml` 每 BU 一份探索題庫；`explore_configs/scoring_rubric.yaml` 全 BU 共用評分 rubric；新 BU onboard 不改 graph code。
- **Checkpointer (PostgresSaver)**：探索可能跨多日（BU 想離線再回來），HITL resume 為核心需求。
- **Storage**：
   - Explore configs：repo 內 `explore_configs/`
   - LangGraph state + business 表（`explorations`）：Postgres，與 Diff / Consult 同 database
   - 候選清單本體：Postgres `explorations.result_json`（不寫 Doc）

---

## 6. 技術選型 (Tech Stack)

| 層次 | 選項 | 與 Consult_agent 對齊 |
| --- | --- | --- |
| Pipeline 框架 | LangGraph + `langchain-core`（state machine + PostgresSaver + `interrupt()`） | ✅ |
| LLM | Gemini 2.5 Pro（`langchain-google-genai`）；`with_structured_output` 用於 cluster / score / predict | ✅ |
| Checkpointer | PostgresSaver（必須持久化；探索可能跨多日） | ✅ |
| Backend | FastAPI + Postgres | ✅ |
| Slack SDK | `slack-bolt` (Python)；共用 bot 帳號 | ✅ |
| Doc Ops | （本 agent 不寫 Doc） | N/A |
| OAuth | `google-auth` + `google-auth-oauthlib`；共用 `oauth_tokens` 表 | ✅ |
| 探索題庫設定 | YAML（`explore_configs/<bu>.yaml`） | 新增（鏡像 Consult `template_configs/`） |
| 評分 rubric | YAML（`explore_configs/scoring_rubric.yaml`，全 BU 共用） | 新增 |
| Observability | stdout log（dev / 內測）→ structured log（V1） | ✅ |
| Deploy | 本機 dev（uvicorn + ngrok）→ Cathay 內網（V1） | ✅ |

---

## 7. 核心使用者流程 (User Flow)

```
1. BU 在 Slack 輸入：
   /brd-explore
   (純探索；也可 /brd-explore 想做授信相關 AI 帶 hint)

2. Bot 跳極簡 modal (2 欄):
   • BU 別                 [壽險 ▾]
   • 你目前主要負責什麼工作  [_________________]
                            (例：處理保戶來電、續保通知、
                             理賠文件初審等)

3. BU 提交 → Agent 載入 explore_configs/壽險.yaml 探索題庫

4. discovery_loop 逐題詢問 (5 必選 + 3 條件，以下示例 EX-1):

   ┌──────────────────────────────────────────────┐
   │ [探索] 1 / 6  ·  EX-1 重複性                  │
   │                                              │
   │ Q: 你部門「最近 4 週，每週至少做 3 次以上」    │
   │    的工作是什麼？(列 2-3 件)                  │
   │                                              │
   │ 💡 Why: 找出可被自動化的高頻工作              │
   │                                              │
   │              [Skip this question]            │
   └──────────────────────────────────────────────┘

   BU: 「續保通知 (每月 200+ 件)、理賠文件初審 (每週 30 件)、
        客服 email 回信」
   → 進下一題

5. (略 EX-2 ~ EX-6 流程類似;若答案抽象, 自動觸發 EX-7「免費實習生」題)

6. cluster_pain → 把答案 cluster 成 4 個痛點:
   - 續保提醒手動排序
   - 理賠文件跨系統手抄
   - 客服 email 重複回覆
   - 跨保單系統對帳

7. score_candidates → 5 維度評分,輸出 top 3:

   ┌──────────────────────────────────────────────┐
   │ 🎯 為你找到 3 個候選 AI 工具方向              │
   │                                              │
   │ 🥇 1. 續保提醒分流 AI                         │
   │    定位: 自動分類保戶為「主動續保 / 需提醒 /  │
   │           高流失風險」,排序客服外撥順序        │
   │    評分: ⭐⭐⭐⭐  (21 / 25)                    │
   │    • 規則重複: 4 (有清楚保單到期判斷邏輯)    │
   │    • 資料可得: 5 (保單系統可取)               │
   │    • 後果可逆: 5 (僅排序,不真的取消保單)    │
   │    • 規模 ROI: 4 (每月 200+ 件)              │
   │    • 解決空缺: 3 (現用 Excel 人工排序)       │
   │    規模: 約每月 200 件                       │
   │                  [▶ 選此候選]                │
   │ ─────────────────────────────────            │
   │ 🥈 2. 理賠文件 OCR + 初審                    │
   │    ... (同格式)                              │
   │                  [▶ 選此候選]                │
   │ ─────────────────────────────────            │
   │ 🥉 3. 客服 email 意圖分類                    │
   │    ... (同格式)                              │
   │                  [▶ 選此候選]                │
   │                                              │
   │ ❎ 未進 top 3:                                │
   │   • 跨保單系統對帳 (13/25, 規則太雜)          │
   │                                              │
   │  [全部不滿意,重新探索]  [放棄,先離線討論]     │
   └──────────────────────────────────────────────┘

8. BU 點「▶ 選此候選 (續保提醒分流 AI)」

9. handoff_to_consult:
   • 寫 explorations.selected_candidate_idx = 0
   • Bot 在 thread 回:

   ┌──────────────────────────────────────────────┐
   │ ✅ 已選定: 續保提醒分流 AI                     │
   │                                              │
   │ 將進入 Consult_agent 進行正式 BRD 草擬;       │
   │ 你不需重新填寫 metadata —— 我已預先帶入:     │
   │   • BU: 壽險                                 │
   │   • 處理對象: 結構化資料                      │
   │   • 專案類型: 流程評估                        │
   │   • 執行模式: 批次                            │
   │   • 預期結果: 分數 + 自然語言說明              │
   │   • 介接系統: 保單系統                        │
   │   • 一句話業務目標: (已草擬,可微調)         │
   │                                              │
   │              [▶ 進入 Consult_agent]          │
   └──────────────────────────────────────────────┘

10. BU 點按鈕 → 觸發 /brd-new --from-exploration ex_01HW...
    → Consult_agent collect_metadata 從 explorations 表讀 candidate
    → modal 8 欄全預填,BU 確認 / 微調 → 進章節訪談
       (anchor case 由「需求背景」Q2 keystone 收集)

11. (跨 session) BU 想接續未完成的探索:
    /brd-explore-resume ex_01HW...
    → 從 PostgresSaver 還原 state, 從中斷處接續
```

---

## 8. 資料模型 (Data Model)

兩層：**business 表**由我們設計、**LangGraph checkpoint 表**由 PostgresSaver 自動建立。

### 8.1 Business 表（自管）

```sql
explorations
  id (uuid, PK)             -- 同時當 LangGraph thread_id
  slug                      -- 友善別名 e.g. explore-壽險-20260505-01;
                            --   unique per (initiated_by);對外顯示用
                            --   (F-5.1 / F-5.4 Layer 2 替代 UUID)
  slack_thread_ts           -- Slack thread timestamp;與 id 1:1 反查
                            --   (F-5.4 Layer 1 thread-aware auto-resume)
  initiated_by (slack_user_id)
  bu                        -- 產險 / 壽險 / 銀行 / 證券
  current_role_brief        -- BU 自填的工作描述 (modal 第 2 欄)
  raw_input_text            -- /brd-explore <raw text>; nullable
  discovery_responses       -- jsonb; { "EX-1": "...", "EX-2": "...", ... }
  pain_clusters             -- jsonb; cluster_pain_points 輸出
  candidates                -- jsonb; top 3 candidates 完整 payload (含 ai_suitability + predicted_consult_fields)
  not_recommended           -- jsonb; 未進 top 3 的 cluster + reason
  selected_candidate_idx    -- int | null;BU 點選的 candidate 在 candidates 中的位置
  selected_at               -- timestamp | null
  handed_off_to_consultation_id  -- uuid | null;hand-off 後 Consult 端的 consultation_id (由 Consult 寫回)
  status                    -- in_progress | candidates_ready | selected | handed_off | abandoned | re_exploring
  re_exploration_count      -- int;預設 0;每次「重新探索」+1;max 2
  created_at
  updated_at

oauth_tokens                -- 與 Diff / Consult 共用同一張表 (Explore 暫不使用,保留 schema)
  ...
```

### 8.2 LangGraph state schema（in-memory，TypedDict）

```python
class ExploreAgentState(TypedDict):
    exploration_id: str
    slack_user_id: str
    # Input
    bu: Literal["產險", "壽險", "銀行", "證券"]
    current_role_brief: str
    raw_input_text: str | None
    # Discovery
    explore_questions: list[ExploreQuestion]   # 載入的探索題序列(可能經 raw_text hint 重排)
    current_question_idx: int
    discovery_responses: dict[str, str]        # question_id -> answer
    # Cluster + Score
    pain_clusters: list[PainCluster]
    candidates: list[Candidate]                # top 3
    not_recommended: list[NotRecommended]
    # Selection
    selected_candidate_idx: int | None
    re_exploration_count: int                  # 預設 0
    handed_off_at: str | None
```

### 8.3 LangGraph checkpoint 表

由 `PostgresSaver.create_tables(conn)` 自動建立（同 Consult_agent §8.3）。**Explore_agent 必須使用 PostgresSaver**，因為探索可能跨多日中斷續寫（BU 想離線整理工作清單再回來）。

---

## 9. Appendix

### A. 範例 探索題庫 YAML（壽險）

`explore_configs/壽險.yaml`：

```yaml
bu: 壽險
total_questions: 5_mandatory + 3_conditional
estimated_minutes: [10, 12]

questions:

  # ─── 必選 5 題 ──────────────────────

  - id: EX-1
    archetype: 重複性
    mandatory: true
    question: |
      你部門「最近 4 週,每週至少做 3 次以上」的工作是什麼?
      (列 2-3 件)
    why_we_ask: 找出可被自動化的高頻工作
    follow_up:
      vague_keywords: [大概, 通常, 應該, 各種]
      probe: 你說的「{vague_phrase}」具體是什麼工作?上週做過嗎?
      min_length: 20

  - id: EX-2
    archetype: 痛苦度
    mandatory: true
    question: |
      上週你 / 同事「最後悔花時間」在哪件事?為什麼後悔?
      (覺得浪費時間 / 重複勞動 / 跨系統手抄 / 沒貢獻 任一即可)
    why_we_ask: 把高頻工作再過濾,留下 BU 真的想擺脫的部分

  - id: EX-3
    archetype: 抱怨集中地
    mandatory: true
    question: |
      同事最常「抱怨」的工作環節是哪個?
      (連續性卡住 / 重複勞動 / 跨系統手抄 / 等待外部回覆 / ...)
    why_we_ask: 痛點彙整;BU 自己未必抱怨,但別人抱怨可能是盲點

  - id: EX-4
    archetype: SOP 化程度
    mandatory: true
    depends_on: [EX-1, EX-2, EX-3]
    question: |
      你前面提到的工作中,有沒有「明確 SOP / 規則表」可以照著做?
      還是大部分憑經驗判斷?
      (請對每件工作分別回答)
    why_we_ask: AI 適用度核心訊號 —— 規則化越高越適合

  - id: EX-5
    archetype: 資料形式
    mandatory: true
    question: |
      處理上述工作時,主要看什麼資料?
      (Excel / 系統截圖 / 紙本 / Email / 圖片 / 影片 / 其他)
      資料平常存在哪?(系統 / 個人 PC / 共享資料夾 / 紙本)
    why_we_ask: 評估資料可得性;系統存的 > 散落的 > 紙本

  # ─── 條件 3 題 ──────────────────────

  - id: EX-6
    archetype: 規模 / 後果
    mandatory: false
    trigger_condition: 任一 EX-1 ~ EX-3 答案具體到「件數」可推估
    question: |
      就 EX-1 提到的工作,平均每件耗時多久?做錯的話會怎樣?
      可以重來嗎?還是會立刻產生損失 / 客訴?
    why_we_ask: 規模 + 後果可逆性 = ROI 與 guardrail 強度

  - id: EX-7
    archetype: 假想題 (open-ended)
    mandatory: false
    trigger_condition: EX-1 ~ EX-5 答案過於抽象 (LLM 判斷)
    question: |
      想像一個「免費實習生」加入你部門,他可以做任何重複工作:
      你會請他做什麼?排第一的是哪件?
    why_we_ask: 抽象 BU 的具體化探針;通常能逼出真正想自動化的事

  - id: EX-8
    archetype: 跨部門參考
    mandatory: false
    trigger_condition: 已收集 ≥ 3 件具體工作
    question: |
      你聽過其他部門做什麼 AI 工具?有沒有覺得
      「我們部門也應該做這個 / 類似這個」?
    why_we_ask: 跨 BU 借鏡;有時 BU 自己想不到,看到別人做就懂

# ─── BU 體驗保護 ──────────────────────

ux_guardrails:
  total_time_budget_minutes: 12
  early_exit_allowed_from: EX-5    # 必選 5 題答完即可進 cluster
  resume_friendly: true            # 任一題答到一半皆可 resume
  abort_signal: 連續 3 題 < 10 字 → 主動建議「先離線整理再回來」
```

> 產險 / 銀行 / 證券各有獨立 `explore_configs/<bu>.yaml`；題目骨架相同，但範例 / 措辭可依 BU 文化客製。新 BU onboard 只新增此檔。

### B. AI 適用度評分 rubric

`explore_configs/scoring_rubric.yaml`（跨 BU 通用）：

```yaml
# 由 score_candidates node 餵給 LLM 做 structured scoring
# 每維度 1-5,總分 25;依 thresholds 分流

dimensions:

  rule_repetition:
    label: 規則重複度
    description: 該工作的判斷規則是否清楚、可教給新人
    scale:
      5: 有清楚 SOP / 規則表 / decision tree
      4: 大致原則明確,少數例外
      3: 有原則但需經驗判斷
      2: 主要憑經驗,只有大方向
      1: 完全憑直覺,沒有可教的規則

  data_availability:
    label: 資料可得性
    description: 處理該工作所需的資料是否已系統化、可程式化讀取
    scale:
      5: 已在系統 (可程式化 query)
      4: 在系統但需多次跨表 join
      3: 散落在 Excel / Email
      2: 紙本 + 個人 PC
      1: 完全沒留紀錄

  reversibility:
    label: 後果可逆性
    description: AI 出錯後是否可撤回 / 重做,還是不可逆
    scale:
      5: 僅輔助 / 分流,不直接執行 (如排序、提醒、預審)
      4: 有人工複核關卡
      3: 出錯有補救空間但會多花成本
      2: 出錯後能補但會有客訴
      1: 一旦執行不可逆 (直接放款 / 出單 / 對外發送)

  scale:
    label: 規模 / ROI 等級
    description: 每月案件量 × 平均耗時
    scale:
      5: 每月 500+ 件 或 每件 > 30 分鐘
      4: 每月 100-500 件
      3: 每月 30-100 件
      2: 每月 10-30 件
      1: 每月 < 10 件

  existing_solution_gap:
    label: 現有解空缺
    description: 是否已有工具,以及現有工具不足之處
    scale:
      5: 完全人工,無任何工具
      4: 用 Excel / 簡單 script,品質不穩
      3: 有商用工具但功能不足
      2: 有工具運作 OK,只想優化邊角
      1: 已有工具運作良好,無明顯缺口

thresholds:
  recommended: 15      # >= 15 / 25 進 top 3
  borderline: 12       # 12-14 列 not_recommended,附「重新探索後可能合適」
  not_suitable: 11     # <= 11 標 not suitable for AI;建議 RPA / SOP 數位化

candidate_selection_rule: |
  按總分 desc 排序;同分時按 reversibility desc 再排序
  (越可逆的方案風險越低,優先推薦)

scoring_prompt_template: |
  你是 AI 適用度評估專家。針對以下痛點 cluster:

  Cluster: {cluster_label}
  Summary: {cluster_summary}
  Source responses: {source_responses}

  請依 5 維度 rubric 各打 1-5 分,並給出每維度的 1 句 reasoning。
  輸出 structured JSON 包含: rule_repetition, data_availability,
  reversibility, scale, existing_solution_gap, total, reasoning[]。
```

### C. 範例 Candidate JSON

`explorations.result_json` 完整範例：

```json
{
  "exploration_id": "ex_01HW123ABC",
  "bu": "壽險",
  "current_role_brief": "處理續保通知、理賠文件初審、客服 email 回覆",
  "raw_input_text": null,
  "discovery_responses": {
    "EX-1": "續保通知 (每月 200+ 件)、理賠文件初審 (每週 30 件)、客服 email 回信",
    "EX-2": "續保通知 — 每月用 Excel 排優先序很煩",
    "EX-3": "理賠文件每件要在 5 個系統間複製貼上欄位",
    "EX-4": "續保有 SOP;理賠文件初審有規則表;email 回信看心情",
    "EX-5": "續保 — 保單系統可取;理賠 — 紙本掃描 PDF;email — Outlook"
  },
  "pain_clusters": [
    {
      "id": "cluster_1",
      "label": "續保提醒手動排序",
      "summary": "每月 200+ 件續保需人工依保單到期 / 客戶價值排優先序",
      "source_responses": ["EX-1", "EX-2", "EX-4", "EX-5"]
    },
    {
      "id": "cluster_2",
      "label": "理賠文件跨系統手抄",
      "summary": "每週 30 件理賠需在 5 個系統間複製欄位",
      "source_responses": ["EX-1", "EX-3"]
    },
    {
      "id": "cluster_3",
      "label": "客服 email 重複回覆",
      "summary": "客服 email 內容多重複,但目前無分類 / 範本系統",
      "source_responses": ["EX-1", "EX-4", "EX-5"]
    },
    {
      "id": "cluster_4",
      "label": "跨保單系統資料對帳",
      "summary": "(略,未進 top 3)",
      "source_responses": ["EX-3"]
    }
  ],
  "candidates": [
    {
      "rank": 1,
      "cluster_id": "cluster_1",
      "title": "續保提醒分流 AI",
      "one_line_goal_draft": "自動分類保戶為「主動續保 / 需提醒 / 高流失風險」三類,輸出客服外撥優先序清單",
      "ai_suitability": {
        "rule_repetition": 4,
        "data_availability": 5,
        "reversibility": 5,
        "scale": 4,
        "existing_solution_gap": 3,
        "total": 21
      },
      "reasoning": [
        "rule_repetition 4: BU 已有清楚 SOP",
        "data_availability 5: 保單系統可直接取數",
        "reversibility 5: 僅排序輸出,不會直接取消保單",
        "scale 4: 每月 200+ 件",
        "existing_solution_gap 3: 目前 Excel 人工排序,有改善空間"
      ],
      "estimated_scale": "每月 200 件",
      "predicted_consult_fields": {
        "process_target": "結構化資料",
        "project_type": "流程評估",
        "policy_code": null,
        "execution_mode": "batch",
        "result_type": "score_plus_nl",
        "integration_systems": ["保單系統"],
        "one_line_goal": "自動分類保戶為「主動續保 / 需提醒 / 高流失風險」三類,輸出客服外撥優先序清單"
      }
    },
    {
      "rank": 2,
      "cluster_id": "cluster_2",
      "title": "理賠文件 OCR + 初審",
      "one_line_goal_draft": "對理賠紙本掃描 PDF 做 OCR,自動填入 5 個系統的對應欄位,人工複核確認",
      "ai_suitability": {
        "rule_repetition": 4,
        "data_availability": 3,
        "reversibility": 4,
        "scale": 3,
        "existing_solution_gap": 5,
        "total": 19
      },
      "reasoning": ["..."],
      "estimated_scale": "每週 30 件",
      "predicted_consult_fields": {
        "process_target": "圖片",
        "project_type": "文件辨識",
        "policy_code": null,
        "execution_mode": "near_realtime",
        "result_type": "nl_summary",
        "integration_systems": ["理賠系統", "核保平台"],
        "one_line_goal": "對理賠紙本掃描 PDF 做 OCR..."
      }
    },
    {
      "rank": 3,
      "cluster_id": "cluster_3",
      "title": "客服 email 意圖分類",
      "ai_suitability": {
        "rule_repetition": 2,
        "data_availability": 4,
        "reversibility": 5,
        "scale": 3,
        "existing_solution_gap": 5,
        "total": 19
      },
      "...": "(略)"
    }
  ],
  "not_recommended": [
    {
      "cluster_id": "cluster_4",
      "label": "跨保單系統資料對帳",
      "total_score": 13,
      "reason": "rule_repetition 偏低 (規則複雜) + scale 不明確;建議重新探索後再評估;此題可能更適合 RPA"
    }
  ],
  "selected_candidate_idx": 0,
  "selected_at": "2026-05-04T11:20:00+08:00",
  "handed_off_to_consultation_id": null,
  "re_exploration_count": 0,
  "status": "selected",
  "generated_at": "2026-05-04T11:18:00+08:00"
}
```

### D. 範例 Slack 訊息

**D-1 探索開場**

```
🎯 開始 AI 工具探索

我會問你 5-8 題,從你部門的日常工作中找出最適合用 AI 的 3 個方向。
全程預估 10-12 分鐘,可隨時 /brd-explore-resume 中斷續寫。

第一題在下面 ↓
```

**D-2 候選呈現**（簡化版）

```
🎯 為你找到 3 個候選 AI 工具方向

🥇 1. 續保提醒分流 AI               ⭐⭐⭐⭐ (21/25)
   定位: 自動分類保戶為三類,排序客服外撥順序
   高分項: 資料可得 5 / 後果可逆 5 / 規模 4
   規模: 每月 200 件
                              [▶ 選此候選]
─────────────────────────────────
🥈 2. 理賠文件 OCR + 初審            ⭐⭐⭐⭐ (19/25)
   ...
                              [▶ 選此候選]
─────────────────────────────────
🥉 3. 客服 email 意圖分類            ⭐⭐⭐⭐ (19/25)
   ...
                              [▶ 選此候選]

❎ 未進 top 3:
   • 跨保單系統對帳 (13/25, 規則太雜,建議改用 RPA)

[全部不滿意,重新探索]   [放棄,先離線討論]
```

**D-3 Hand-off 訊息**

```
✅ 已選定: 續保提醒分流 AI

將進入 Consult_agent 進行正式 BRD 草擬;
你不需重新填寫 metadata —— 我已預先帶入:
  • BU: 壽險
  • 處理對象: 結構化資料
  • 專案類型: 流程評估
  • 執行模式: 批次
  • 預期結果: 分數 + 自然語言說明
  • 介接系統: 保單系統
  • 一句話業務目標: (已草擬,可微調)

預估 Consult 流程約 30-40 分鐘 (5 章節訪談)

                  [▶ 進入 Consult_agent]
```

### E. Hand-off Payload 規格 (Explore → Consult)

**Slack button action**：

候選訊息上的 `[▶ 進入 Consult_agent]` 按鈕：

```json
{
  "type": "button",
  "text": {"type": "plain_text", "text": "▶ 進入 Consult_agent"},
  "style": "primary",
  "action_id": "handoff_to_consult",
  "value": "ex_01HW123ABC"
}
```

Slack bot 收到 `handoff_to_consult` action → 內部呼叫 `/brd-new --from-exploration ex_01HW123ABC` 觸發 Consult graph。

**Consult_agent collect_metadata 需要的 fast-path 改動**：

```python
# Consult_agent: collect_metadata node
def collect_metadata(state: ConsultAgentState) -> ConsultAgentState:
    if state.get("from_exploration_id"):
        # Fast-path: 從 explorations 表讀 candidate
        exploration = db.execute(
            "SELECT bu, candidates, selected_candidate_idx "
            "FROM explorations WHERE id = :id",
            {"id": state["from_exploration_id"]}
        ).fetchone()
        selected = exploration.candidates[exploration.selected_candidate_idx]
        fields = selected["predicted_consult_fields"]

        # 預填 8 欄 (modal 仍會跳給 BU 確認 / 微調,非強制接受)
        state["bu"] = exploration.bu
        state["process_target"] = fields["process_target"]
        state["project_type"] = fields["project_type"]
        state["policy_code"] = fields.get("policy_code")
        state["execution_mode"] = fields["execution_mode"]
        state["result_type"] = fields["result_type"]
        state["integration_systems"] = fields["integration_systems"]
        state["one_line_goal"] = fields["one_line_goal"]

        # 仍跳 modal 讓 BU 確認 / 微調
        modal_payload = build_preflight_modal(state, prefilled=True)
        slack.views_open(modal_payload)
    else:
        # 原本的 collect_metadata 流程
        ...

    return state
```

**Consult_agent business 表新增欄位**：

```sql
ALTER TABLE consultations
  ADD COLUMN from_exploration_id uuid NULL
  REFERENCES explorations(id);
```

**雙向追蹤**：

- Consult 寫回 `explorations.handed_off_to_consultation_id`（讓 Explore 知道後續去向）
- Consult 自身保留 `consultations.from_exploration_id`（讓未來 audit 能追到上游探索）

---

*— End of PRD v0.1 —*

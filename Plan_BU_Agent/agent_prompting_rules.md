# BU Agent — Agent 提問規則 (Prompting Rules)

> 版本：v0.2
> 撰寫日期：2026-05-14
> 範圍：Explore mode + Consult mode 的所有 agent → BU 提問與內容生成邏輯
> 對應實作：`backend/app/graph/` (LangGraph nodes + Jinja2 prompts + YAML 模板)
> 用途：當 BU 體感「agent 怎麼會這樣問？」、「為什麼章節這樣填？」時,直接看本文找出規則來源與調整入口

---

## 0. TL;DR

- **每一句 agent 的話都不是 LLM 自由發揮**;走「**模板 seed + LLM 改寫**」的混合鏈路
- **Seed 從哪來**:Explore 走 `question_bank.yaml`(5 階段題庫)、Consult 走 `templates/<bu>_<project_type>.yaml`(BU 別 + 任務型別模板的 `questions`)
- **LLM 怎麼用 Seed**:Seed 進 prompt 當 reference,LLM 依當下對話歷史改寫成貼合 BU 內容的提問
- **規則限制**:每輪 1 題、最多 2 題;BU 連 2 輪否定 → cold exit;Consult 章節若連續答不出 → 提議 flag_for_ba_review
- **要調 agent 行為**:90% 改 prompt `.j2` 或 YAML seed,10% 才需要動 node 程式碼

---

## 1. 整體 prompt 鏈路圖

```
              ┌────────────────────────────────────────────────────────┐
              │                    Explore mode                         │
              │                                                         │
   BU 開場 ──▶│  discovery_loop                                          │
              │   ├─ 讀 question_bank.yaml stage N seed                  │
              │   ├─ render(system_explore.j2)                           │
              │   ├─ render(explore_question.j2 + recent_history)        │
              │   └─ Gemini stream → SSE agent_reply_delta               │
              │                                                         │
   BU 回答 ──▶│  extract_signals                                         │
              │   ├─ render(extract_signals.j2 + bu_text)                │
              │   └─ Gemini structured → list[PainSignal]                │
              │  ↓                                                       │
              │  cluster_pain_points (no-op pass-through)                │
              │  ↓                                                       │
              │  score_candidates                                        │
              │   ├─ render(score_candidates.j2 + pain_signals)          │
              │   └─ Gemini structured → list[CandidateDirection]        │
              │  ↓                                                       │
              │  converge_check                                          │
              │   ├─ heuristic: stage++ / cold detect                   │
              │   └─ ready_to_handoff?                                   │
              │                                                         │
   stage 5  ─▶│  emit_dual_output                                        │
   + selected │   ├─ deterministic JSON (structured)                     │
              │   └─ render(emit_paragraph.j2) → Gemini stream → 段落    │
              └─────────────────────────────┬───────────────────────────┘
                                            │ handoff_ready
              ┌─────────────────────────────▼───────────────────────────┐
              │                   Consult mode                          │
              │                                                         │
              │  load_template_node                                     │
              │   └─ 載 templates/<bu>_<project_type>.yaml              │
              │  ↓                                                       │
              │  auto_fill_outline                                       │
              │   ├─ render(auto_fill_outline.j2 + paragraph + sections)│
              │   └─ Gemini structured → list[SectionDraft]              │
              │   → SSE outline_ready                                   │
              │  ↓                                                       │
              │  section_loop  (對 needs_round2 章節)                    │
              │   ├─ 讀 templates 該章節 questions                       │
              │   ├─ render(section_question.j2 + section_draft + seed) │
              │   └─ Gemini stream → SSE agent_reply_delta              │
              │                                                         │
   BU 回答 ──▶│  _integrate_bu_answer_to_section (service 層)           │
              │   ├─ render(apply_section_answer.j2 + draft + answer)   │
              │   └─ Gemini stream → 章節新 draft                       │
              │   → SSE section_updated                                 │
              │                                                         │
              │  quality_gate (送 BA 前)                                │
              │   ├─ render(quality_gate.j2 + sections)                 │
              │   └─ Gemini structured → list[Conflict]                 │
              │   → SSE conflict_detected (有衝突時)                    │
              │  ↓                                                       │
              │  build_deliverables (deterministic)                     │
              └─────────────────────────────────────────────────────────┘
```

---

## 2. Explore mode 提問規則

### 2.1 五階段題庫 (`question_bank.yaml`)

| 階段 | 名稱 | 意圖 | max_rounds | seed 範例 |
| --- | --- | --- | --- | --- |
| 1 | 發散 (divergence) | 從 BU 工作日常 surface context | 2 | 「聊聊你日常工作的樣子——每天 / 每週你花最多時間在哪些事情上?」<br>「哪些事情是你做得很熟、但同事或新人常做錯的?」 |
| 2 | 脈絡建立 (context) | 抓 pain signals + 量能 + 資料可得性 | 3 | 「剛剛提到的流程裡,最耗時或最容易出錯的環節是哪裡?一個月發生幾次?」<br>「這件事如果做錯,下游要花多少成本去救?可不可以回頭修正?」<br>「目前處理這件事會看哪些資料 / 系統?是文字、表格還是圖像?」 |
| 3 | 收斂 (convergence) | 把候選方向收斂到 ≤ 3 | 2 | 「聽下來有幾件事都在重複出現;如果只能先處理一件,你會選哪一件?為什麼?」<br>「這幾個候選方向中,你覺得哪個最有感 / 最痛?」 |
| 4 | Challenge | stress-test 最上位候選 (reversibility / ROI / gap) | 2 | 「如果這個 AI 給錯答案會怎樣?最糟的情況是什麼?」<br>「目前這個問題你們是怎麼做的?如果沒有 AI 會多花多少力氣?」 |
| 5 | 交接準備 (handoff prep) | 引導 BU 明確選定一個方向 | 2 | 「聽起來方向差不多了;你想先從哪一個開始?」<br>「我把我聽到的整理成一段,你看看跟你想的一樣嗎?」 |

**階段推進機制**(`converge_check` 節點):
- 每完成一輪對話 stage += 1,上限為 5
- 階段 5 + BU 已點選候選卡片 → 設 `ready_to_handoff = True`
- 連續 2 輪 BU 回應含關鍵詞「不太對」「不對」「沒想法」「no」→ 標 `mode = cold`,終止對話

### 2.2 Agent 提問實際流程

每輪 `discovery_loop` 節點執行:

1. **讀 stage 與 seed**:依 state.stage 從 question_bank 取對應 stage seed list,輪流挑一條
2. **組 system prompt**(`system_explore.j2`):
   - 灌入 BU 別、SME 角色、當前階段意圖
   - 強調風格規則:Give-then-Ask、每輪 1 題最多 2 題、不替 BU 決策、繁體中文 + 必要英文術語
3. **組 user prompt**(`explore_question.j2`):
   - 最近 8 輪對話歷史
   - 當前候選方向(若已有)
   - 該階段 seed 題目(僅供參考,可改寫)
4. **Gemini stream 產出**:題目長度限制 ≤ 60 字
5. **fallback**:LLM 回空字串時退回 stage seed 第一條
6. SSE `agent_reply_delta` / `agent_reply_done` 推給前端

### 2.3 Pain signals 抽取規則

`extract_signals.j2`:
- BU 最新一段話 < 8 字 / 純寒暄 → 回空 list
- 抽 0-3 條 signal,每條 < 80 字
- `source: "bu_explicit"`(BU 明說) 或 `"agent_reframe"`(LLM paraphrase)
- `tags: 0-3 個短標籤`
- 失敗時 fallback:把 BU 全段當一條 `bu_explicit` signal

### 2.4 候選方向評分規則

`score_candidates.j2` — 5 維 rubric:

| 維度 | 定義 | 給分依據 |
| --- | --- | --- |
| `rule_repeat` | 規則可重複度 | BU 流程是否高度重複、可規則化 |
| `data_avail` | 資料可得性 | 訓練 / 推論資料是否現成 |
| `reversibility` | 可事後覆核度 | AI 答錯能不能補救、有沒有 audit |
| `scale_roi` | 規模 ROI | 每月處理量 × 節省工時 |
| `gap` | 既有 gap 大小 | 目前無人 / 工具不足的程度 |

**輸出規則**:
- 候選數量 1–3 個
- `direction` 用「動詞 + 流程目標 + 任務類型」格式,例:`理賠文件型別自動分類`
- `project_type` 必須是 `分類 / 抽取 / 摘要 / 生成 / QA / 排序 / 異常偵測` 之一
- 分數 1-5 整數,prompt 強調**保守給分**(沒明說的不要打 5)
- 失敗時 fallback:依 BU 別給固定 preset(產險:理賠文件分類 + 核保 QA;壽險:風險標記)

### 2.5 雙輸出規則

`emit_dual_output` 節點產兩份東西:

**(A) Structured JSON** — deterministic 組裝(不走 LLM):
- `exploration_id`、`bu`、`sme_role`
- `candidates` 全清單
- `selected_candidate` (rank)
- `predicted_consult_fields`:bu / process_target / project_type / one_line_goal
- `trace`:完整對話歷史

**(B) Paragraph** — LLM 寫(`emit_paragraph.j2`):
- 200–400 字的需求描述
- 涵蓋 4 點:BU 想解決的問題、AI 切入位置、預期 IO 形式、BU 已認可 vs agent 推斷的部分
- 字數守門:< 80 或 > 600 退回 deterministic 模板

---

## 3. Consult mode 提問規則

### 3.1 BRD 章節模板

`backend/app/graph/consult/templates/` 下三份:

| 檔案 | BU | project_type | 用途 |
| --- | --- | --- | --- |
| `default.yaml` | `*` | `*` | fallback;找不到精準匹配時用 |
| `產險_分類.yaml` | 產險 | 分類 | 例如理賠文件型別自動分類 |
| `壽險_分類.yaml` | 壽險 | 分類 | 例如保戶通訊內容風險標記 |

每份模板包含 9 個章節(BU 章 5 + AI 科 2 + CD 科 2),欄位 schema:

```yaml
sections:
  - id: sec_xxx
    title: 章節標題
    owner: bu | ai_team | cd_team
    default_status: auto_filled | needs_round2 | placeholder
    extract_from_explore: [pain_signals, process_target, ...]   # auto_fill 時 LLM 取材 hint
    questions:                                                   # section_loop 提問 seed
      - 問題 1
      - 問題 2
```

**狀態語意**:
- `auto_filled`:Explore 已挖到足夠資訊,LLM 能自動填初稿,BU 確認即可
- `needs_round2`:Explore 沒涵蓋,需要 Consult Step 2 訪談
- `placeholder`:屬 AI 科 / CD 科填寫,本階段固定文字「(由 AI 科 / CD 科後續補充)」

### 3.2 Step 1 自動填章節 (`auto_fill_outline`)

`auto_fill_outline.j2` 的規則:

| Status | 處理 |
| --- | --- |
| `auto_filled` | 寫 150-300 字具體初稿,引用 pain signals + process_target 名詞 |
| `needs_round2` | 寫 50-100 字提示性 placeholder,指出第 2 輪要釐清什麼 |
| `placeholder` | 固定回「(由 AI 科 / CD 科後續補充)」,不展開 |

**輸入 context**:候選方向、one_line_goal、pain signals、Explore 雙輸出段落、章節清單(含 `extract_from_explore` hint)

**fallback**:LLM 失敗或回空時,依章節 id 用 heuristic 模板填。

### 3.3 Step 2 章節訪談 (`section_loop`)

每次 BU 送訊息後,`section_loop` 對當前 `needs_round2` 章節提一道問題:

`section_question.j2` 規則:
- 一句話、≤ 60 字
- 開頭不加「請問」「想了解」客套
- 直接從 template seed 改寫(seed 進 prompt 當 reference)
- **連續答不出 2 次的退場機制**:當 `rounds_so_far ≥ 2` 且 BU 上輪明顯答不出來,LLM 改成「這部分要不要先 flag 給 BA?」

**章節輪換**:
- BU 對該章節 Accept / Skip / Flag → `current_section_idx` 跳到下一個 needs_round2
- 全部完成 → 觸發 `quality_gate`

### 3.4 BU 回答整合 (`apply_section_answer`)

BU 在對話區送出回答後,`_integrate_bu_answer_to_section` service 用 LLM 把答覆 merge 進章節 draft:

`apply_section_answer.j2` 規則:
1. 保留章節主結構(段落、清單格式),BU 答覆融入合適位置
2. 保留 BU 講過的具體名詞、量化資訊(數字、流程名、規則名);不要泛化
3. 不加導語、結論、追問、Markdown heading
4. 長度控制 200-450 字
5. 用書面語(BRD 風格),不留口語助詞
6. 直接輸出整合後章節文字

**fallback**:LLM 失敗或新內容 < 30 字,退回「原 draft + [BU 補充] 原話」拼接,確保資訊不丟。

完成後 publish `section_updated` SSE → 前端右側對應章節即時更新。

### 3.5 跨章節一致性檢查 (`quality_gate`)

送 BA 前 LLM 跑一次 `quality_gate.j2`:
- **只**回報「明確矛盾」(例:章節 A 說「全自動」、章節 B 說「需 100% 人工複核」)
- 缺漏 / 不夠細不算矛盾
- `placeholder` 與 `flagged_for_ba` 章節跳過(避免干擾判斷)
- LLM 失敗時 pass(不擋送 BA)
- 有衝突時 publish `conflict_detected` SSE → 前端跳 alert 列出 `section_ids` + 衝突描述

---

## 4. 系統級 prompt 規則(寫死在 system prompt)

### 4.1 `system_explore.j2`

每輪 Explore 提問都會帶上的恆定規則:

- 角色:國泰金控內部 AI 顧問
- 對話對象:BU 部門 SME(灌入當前 BU 別、SME 角色)
- 語言:繁體中文 + 必要英文術語
- 風格:Give-then-Ask(先 surface 一條觀察,再問至多一題)
- **不替 BU 做決策**;只丟選項、讓 BU 選
- 每輪 1 題最多 2 題;不要連珠炮
- 不在 Explore mode 寫 BRD 章節
- BU 連 2 輪「都不太對 / 沒想法」→ 不硬塞,直接收尾
- 第二人稱「你」對話,不要過度禮貌

### 4.2 `system_consult.j2`

Consult Step 2 用,但目前 section_loop 沒主動掛 system prompt(只在 user prompt 裡 inline 規則);系統 prompt 保留供未來真正多輪對話用。

規則內容:
- 已選定方向(灌入 candidate.direction)
- 對話對象 BU 部門 SME
- 輸出風格:章節文字可直接放進 BRD,不加「好的」「以下是」雜訊
- 只針對 needs_round2 章節提問,auto_filled 章節由 BU 自己 Accept / Refine
- 每次只問**一個章節、一道問題**
- BU 答不出不硬逼,可建議 `flag_for_ba_review`
- 答覆要包含具體業務名詞,不能只是泛泛而談

---

## 5. 控制變因與調整入口

### 5.1 我想調這些東西 → 改哪個檔

| 想調整 | 改這個檔 | 範例 |
| --- | --- | --- |
| Explore 5 階段題目 / 順序 | `question_bank.yaml` | 改 stage 2 加一條「資料量級」問題 |
| 階段最大輪數 / 推進條件 | `explore/nodes.py::converge_check` | cold 偵測關鍵詞、stage 跳轉邏輯 |
| Explore agent 提問風格 / 長度 | `prompts/explore_question.j2` + `system_explore.j2` | 改 ≤ 60 字限制、改 Give-then-Ask 規則 |
| 候選評分 5 維定義 / 給分嚴格度 | `prompts/score_candidates.j2` | 改 rubric 描述、改「保守給分」措辭 |
| 雙輸出段落字數 / 結構 | `prompts/emit_paragraph.j2` | 改 200-400 字限制、改涵蓋的 4 點 |
| 加新 BU / 任務組合的章節 | `templates/<bu>_<type>.yaml` | 新建 `銀行_抽取.yaml` |
| 章節 status 預設值(哪些 auto_filled / needs_round2) | 同上 yaml 內 `default_status` | 把「需求背景」從 auto_filled 改 needs_round2 |
| 章節訪談題庫 | 同上 yaml 內 `questions` | 加新章節題或改順序 |
| Step 1 自動填章節風格 / 長度 | `prompts/auto_fill_outline.j2` | 改 150-300 字限制 |
| Step 2 章節提問風格 | `prompts/section_question.j2` | 改 ≤ 60 字、改開頭客套規則 |
| BU 回答整合風格 | `prompts/apply_section_answer.j2` | 改 200-450 字限制、改保留具體名詞規則 |
| Quality gate 嚴格度 | `prompts/quality_gate.j2` | 加更多衝突類型、改「明確矛盾」定義 |

### 5.2 加新 BU 或新任務型別

最快路徑(不動程式碼):

1. 複製 `templates/default.yaml` → `templates/<bu>_<project_type>.yaml`
2. 改檔頭 `template_id / bu / project_type`
3. 客製每個 sections 的 `default_status` 與 `questions`
4. **不需要重啟 backend**(下一個 session create 時 `template_loader._cache` 還會生效;若要立即清空 cache,重啟 backend container)

如果該組合的候選方向有特殊偏好(LLM 評分時),要同時加進 `_heuristic_candidates_fallback`(`explore/nodes.py`)以保證 LLM 失敗時有合理 fallback。

---

## 6. Fallback 策略總覽

每個用 LLM 的節點都有 fallback,確保 LLM 失敗 / 超時 / 違反 schema 時 UI 不會卡死:

| 節點 | LLM 失敗時 fallback |
| --- | --- |
| `discovery_loop` | 退回 stage seed 第一條 |
| `extract_signals` | 把 BU 全段當一條 `bu_explicit` signal |
| `score_candidates` | 依 BU 別給 preset(產險 = 理賠文件分類 + 核保 QA;壽險 = 風險標記) |
| `emit_dual_output` paragraph | 字數越界退 deterministic 模板拼接 |
| `auto_fill_outline` | 依章節 id 用 heuristic 模板填 |
| `section_loop` | 退回 template seed 第一條 |
| `_integrate_bu_answer_to_section` | 「原 draft + [BU 補充] 原話」拼接 |
| `quality_gate` | pass(不擋送 BA) |

---

## 7. 觀測點

要看 agent 為什麼這樣問,排查順序:

1. 開瀏覽器 Console 看 SSE event(`[SSE] event agent_reply_delta` 等)
2. `docker logs bu_agent_backend --tail 60` 看節點是否 LLM 失敗(grep `llm_failed`)
3. 看當前 stage(SessionPage 頂部 `stage N`)與 mode 是否符合預期
4. 若疑為 prompt 不對,讀對應 `.j2` 檔,確認 stage / candidates / pain_signals 等變數有正確灌入

debug 用的 prompt 渲染快照(若需要)可在 node 裡加 `log.info("rendered_prompt", text=user[:500])`。

---

## 10. 產業知識卡(Knowledge Card)

> v0.2 加入。Static knowledge layer,讓 agent 提問與寫作有 BU 業務脈絡,
> 不再像通用顧問。對應實作:`backend/app/graph/shared/knowledge/`、`knowledge_loader.py`、
> `prompts/_knowledge_card.j2`。

### 10.1 為什麼要

之前所有 prompt 只有 `bu` 一字(產險/壽險/...),agent 不知道產險系統叫什麼、
有哪些既有 AI 工具、哪些事不能寫進 BRD。提問因此偏向通用顧問風格。

知識卡解決這個問題:把 BU 不變的業務脈絡寫進 YAML,每個 LLM 呼叫透過 `system prompt` 灌入。

### 10.2 知識卡 schema(`knowledge_loader.py::KnowledgeCard`)

| 欄位 | 用途 |
| --- | --- |
| `glossary` | L1 業務術語對照(縮寫 → 全名 + 註解) |
| `process_overview` | L2 該 BU 主要業務流程概觀(自由文字) |
| `typical_pain_patterns` | L2 常見痛點 pattern 清單 |
| `volume_hints` | L2.5 規模 / 量能參考(月均件數等) |
| `cathay_ai_inventory` | L3 Cathay 內部已建 AI / RPA / 工具(score 階段判斷重用 / gap 用) |
| `taboos` | 法遵 / 合規地雷(agent 偵測到 BU 提到時主動提醒) |
| `preferred_solution_classes` | 該 BU 偏好的解類型(影響 ai_necessity 判斷) |
| `avoided_solution_classes` | 該 BU 避免的解類型 |
| `past_brd_lessons` | 過去 BRD 經驗教訓 |

### 10.3 注入哪些 prompt

不是全部 prompt 都灌,只灌 4 個 high-leverage 點:

| Prompt | 為什麼注入 |
| --- | --- |
| `system_explore.j2` | 每輪 Explore 提問都帶 → agent 提問會引用業務術語、量能、現有工具 |
| `system_consult.j2` | Consult 階段每次寫章節都帶 → BRD 章節可引用具體流程 |
| `score_candidates.j2` | 評分時看 cathay_ai_inventory 避免重做、看 preferred 校正 ai_necessity |
| `auto_fill_outline.j2` | 自動填章節時引用 inventory + 流程脈絡 |

`extract_signals.j2` / `emit_paragraph.j2` / `section_question.j2` / `apply_section_answer.j2`
等不灌,因為它們的 input 已經是 BU 講過的話,加 kc 邊際效益小但 token 翻倍。

### 10.4 BU 別新增 / 修改流程

新增一個 BU 的知識卡(例:銀行已有 stub,要補實際內容):

1. 編輯 `backend/app/graph/shared/knowledge/<bu>.yaml`
2. 用 `[TODO:核實]` 標需要實際 confirm 的欄位,給 BU 窗口 review
3. **重啟 backend container**(或在 backend container 內呼叫
   `from app.graph.shared.knowledge_loader import clear_cache; clear_cache()`)以清 LRU cache
4. 開新 session 用該 BU 測,看 agent 提問有沒有引用知識卡內容

當 backend 找不到 `<bu>.yaml` 或檔案內容空 → 自動 fallback 到 `default.yaml`,
不會炸,但 agent 行為會退化為通用顧問。

### 10.5 撰寫規範

- **保持精簡**:每張卡控制在 < 1500 字(灌進 system prompt 後 token 不爆 + cache hit 容易)
- **去敏第一**:不留具體保戶 / 客戶 / 標的物 PII,違規欄位寫 `[GENERIC]` 或刪掉
- **誠實標 TODO**:不確定的欄位用 `[TODO:核實]` 開頭,別寫死估計值騙 LLM
- **版本化**:每次更新改 `version` 與 `last_updated`,git commit 寫清楚什麼變了
- **owner 必填**:`contact` 欄位寫該 BU 知識卡 owner 聯絡資訊,review 時找得到人

### 10.6 後續擴充路徑(M5+)

目前是 static knowledge card(L1-L3 的 small / medium 內容)。
如果 BU 反饋「agent 看起來知道很多但案例還是太少」,下一階段考慮:

- **Dynamic RAG**:把 L4 過去 BRD 案例庫 embed 進 pgvector,只在 `auto_fill_outline`
  / `score_candidates` 兩個 batch 節點 retrieve,不在 streaming 節點跑(避免拖慢 first token)
- **AI Inventory 自動同步**:從 AI 科 model registry pull `cathay_ai_inventory`,
  不再靠手動編輯 YAML

詳見 §11(與其他文件)末尾的後續討論。

---

## 11. 與其他文件的關係

- `bu_agent_overview.md` §4.1.3 規範 Explore 對話節奏(5 階段);本文 §2 是其工程實作對應
- `bu_agent_technical_design.md` §3.5 規範 prompt 組織原則;本文 §1 提供完整鏈路圖
- `bu_agent_user_stories_and_flow.md` Epic B / Epic E 是使用者體感面;本文是 agent 內部行為面
- 舊 `BU_Agent_v2_題庫.md` 是 v0.x 階段題庫雛形,Explore 5 階段已吸收進 `question_bank.yaml` 並由本文取代

---

## 12. 變更紀錄

| 版本 | 日期 | 變更 |
| --- | --- | --- |
| v0.1 | 2026-05-14 | 初版,對齊 M4 Gemini 接入後的提問鏈路 |
| v0.2 | 2026-05-14 | 加 §10 產業知識卡(Knowledge Card)章節;對應 M4-E 知識注入機制 |

---

*— End of Agent Prompting Rules v0.2 —*

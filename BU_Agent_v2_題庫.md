# BU Agent v2 題庫

> **定位**：發想者 + 整理者混合 agent
> **User**：BU 單位（不是 BA）
> **目標**：在 30 分鐘內幫 BU 從模糊想法產出一份可送進 BA 的需求初稿，同時主動 surface BU 沒想到的 AI 機會

---

## 一、設計原則

這份題庫的設計建立在以下幾個原則上，閱讀題目時請對照這些原則理解每一題的取捨。

**1. 對話節奏：每輪 1 題、最多 2 題**
BA 訪談可以連珠炮提問，但 agent 對 BU 是日常工具，BU 隨時可以關掉視窗。不要讓 BU 感覺「我來找 agent 幫忙，怎麼變成被考試」。

**2. Give-then-Ask：先給後問**
每輪 agent 要先 surface 一些有用的東西（過去案例、相似系統、可能的方向），再問下一題。降低 BU 的認知負擔，也建立信任。

**3. 強迫具體例子，不問抽象意見**
「描述一個典型 case 跟一個最棘手的 case」遠比「你覺得這件事複雜嗎」有用。抽象描述抽不出 features。

**4. Reframe 要溫和，不能打臉 BU**
當 agent 看到比 BU 提的方向更值得做的機會時，**不要說**「B 比 A 好」，要說「順著你描述的流程，我注意到 B、C 可能也有空間，不確定有沒有戳到你也想做的事？」把主導權留給 BU。

**5. 信任建立：早期 demo 出 domain 知識**
前幾輪 agent 就要展示自己懂產險、懂這個 BU 單位（依靠 RAG 內部知識庫）。題庫中標記為 `[domain]` 的題目就是這個用途——同時是 elicitation 也是 trust building。

**6. 完成感：每次對話都要有產出**
即使只是「目前我們聊到的內容整理」，BU 才會覺得這 30 分鐘有價值。Agent 要能在任何時點 checkpoint。

---

## 二、四個分析任務（Agent 內部）

題庫中的每題都會標註它服務哪個分析任務。這四個分析任務是 agent **內部**要做的工作，不是 BU 看得到的：

- **任務 1**：這個需求是否真的適合 AI Agent？
- **任務 2**：這個需求對應到 BU 工作流程的哪一段？
- **任務 3**：哪些地方必須留人為介入？
- **任務 4**：從工作流程中找出 BU 沒想到的 AI 機會

---

## 三、題庫（按對話階段組織）

### 階段 1：發散 / 建立信任（前 5 分鐘）

目的：讓 BU 講出真實的痛點，同時讓 agent 蒐集足夠的脈絡。**這個階段不要急著聚焦**，BU 還沒進入狀況就被收斂會反感。

| # | 題目 | Signal | 任務 | Agent 後續推論 |
|---|---|---|---|---|
| 1.1 | 描述上週讓你最煩的一個工作場景，當時你在做什麼？ | pain anchor、具體事件 | 1, 2 | 從事件抽出工作流程的起點 |
| 1.2 | 你這週花最多時間在哪件事上？哪一段最讓你想放棄？ | time allocation、bottleneck | 1, 2 | volume + 痛點疊加，找最值得做的方向 |
| 1.3 | 你跟同事抱怨最多次的工作流程是什麼？ | recurring pain | 1, 4 | 抱怨內容通常是流程問題或工具缺口 |
| 1.4 | 如果有一個「神奇按鈕」，按下去就解決你某個煩惱，會是哪個？ | aspiration（軟性版本） | 4 | 抓 BU 的願景，但不被他的解法綁架 |
| 1.5 | 你最希望花更多時間做的事是什麼？最不想做的是什麼？ | value perception | 4 | 高/低價值工作的 BU 自評，反推自動化機會 |
| 1.6 | 最近有沒有看到哪個工具，或同事的做法，讓你覺得「我們也應該這樣」？ | reference anchor | 4 | 用 BU 已知的東西當 anchor，而不是丟一堆 AI 名詞 |

---

### 階段 2：脈絡建立（接下來 5–10 分鐘）

目的：建出工作流程的 stage diagram，並 surface 系統 / 資料 / 法規限制。**Agent 此時要主動 retrieve 內部知識庫**，把相關過去案例、系統地圖、法規限制丟給 BU 參考。

| # | 題目 | Signal | 任務 | Agent 後續推論 |
|---|---|---|---|---|
| 2.1 | 從這個任務「開始」到「結束」之間有幾個步驟？依時間順序列出來。 | workflow shape | 2 | 建 stage diagram 的骨架 |
| 2.2 | 哪一步的 input 是從別人 / 別的部門 / 別的系統來的？以什麼形式？ | upstream dependency | 2, 3 | 找 handoff 點與資料來源 |
| 2.3 | 你完成後交給誰？以什麼形式？對方拿去做什麼？ | downstream consumer | 2 | 找 handoff 點與下游影響範圍 |
| 2.4 | 這幾步裡，哪一步**最花時間**？哪一步**最常卡住**？卡住的原因是什麼？ | bottleneck | 1, 2, 4 | bottleneck 通常是最值得做的施力點 |
| 2.5 | 哪些步驟在系統裡做、哪些在 Excel、哪些用 mail / Teams 溝通？ | system/manual breakdown | 2, 4 | manual 的部分通常有自動化空間 |
| 2.6 | 在這個任務開始之前，你需要等什麼條件 / 什麼人 / 什麼資料？ | trigger condition | 2 | 確認 trigger 是 event-driven 還是 schedule-driven |
| 2.7 | 這個工作每天 / 每週做幾次？每次大概花多久？ | volume | 1 | volume 太低不值得自動化 |
| 2.8 | 這個任務跟核保 / 理賠 / 業務 / 客服哪個流程連動？ | cross-functional | 2 | 確認是否為越界需求、要拉哪些單位進來 |
| 2.9 | `[domain]` 我看到你提到 XX 系統，那個系統的 YY 模組去年才剛改版過，你的需求是基於改版前還是改版後的版本？ | system context + trust | 2 | 動態題：依 RAG 結果產生，同時建立信任 |
| 2.10 | `[domain]` 產險的 ZZ 流程通常會有 A、B 兩種做法，你們單位是哪一種？ | domain context + trust | 2 | 動態題：用 domain 知識讓 BU 知道 agent 不是亂問 |

---

### 階段 3：收斂 / 結構化（接下來 10–15 分鐘）

目的：抽出判斷可行性需要的特徵——variability、judgment density、evaluability、rule sufficiency。**這個階段是任務 1 的主戰場**。

| # | 題目 | Signal | 任務 | Agent 後續推論 |
|---|---|---|---|---|
| 3.1 | 描述一個「典型 case」跟一個「最棘手的 case」，差別在哪？ | variability | 1 | 差別小 → RPA 就夠；差別大 → agent 才有價值 |
| 3.2 | 同樣的 input，不同同事做出來的 output 會不會不一樣？哪裡不一樣？ | judgment density | 1, 3 | 差異大表示有判斷空間，可能是 AI assist 而非 full auto |
| 3.3 | 主管怎麼看你做得好不好？看哪些東西？ | evaluability（軟性版） | 1 | 沒驗收標準的任務做了也收不了尾，要 flag 給 BA |
| 3.4 | 你怎麼判斷一份 output 是「好」的？能各舉一個好跟爛的例子嗎？ | evaluability + 具體例子 | 1 | 拿到具體例子才能設計評估指標 |
| 3.5 | 這個任務有 SOP 或檢查清單嗎？如果嚴格按 SOP 走，能搞定大部分 case 嗎？哪些 case 是 SOP 沒寫的？ | rule sufficiency | 1 | SOP 完整 → 規則引擎；SOP 蓋不到的 case 才是 AI 的施力點 |
| 3.6 | 這件事新人多久能上手？卡在哪？ | judgment density（軟性版） | 1, 3 | 上手慢通常表示 tacit knowledge 多，AI 要小心處理 |
| 3.7 | 完成一次需要查 / 整合幾個來源的資訊？來源是文件、系統、還是人？ | tool use complexity | 1, 4 | 多 source 整合是 agent 的強項 |
| 3.8 | 客戶 / 業務員 / 主管問你「為什麼是這個結果」時，你怎麼解釋？ | explainability | 3 | 需要解釋的場景，AI 必須能 trace reasoning |
| 3.9 | 如果 output 錯了，誰會發現？多久發現？修正成本多高？ | error tolerance | 1, 3 | 高錯誤成本 → 需要 human review，不能全自動化 |
| 3.10 | 這個流程有沒有碰到拒保、理賠金額、保單條款解釋、客訴處理？ | high-stakes decision | 3 | 命中任一項都要標記為 human-only 或 AI-assist-only |
| 3.11 | 過去有沒有「系統 / Excel 算的結果最後被人推翻」的 case？什麼情境？ | edge case pattern | 3 | 這些 case 是未來「AI 信心不足要 escalate」的設計依據 |
| 3.12 | 這件事做錯，誰會被叫去說明？公司最大可能損失多少？ | accountability | 3 | 責任落在誰決定 human-in-the-loop 設計 |
| 3.13 | 如果這件事完全交給電腦做，你自己會擔心什麼？你的主管 / 稽核 / 法遵會擔心什麼？ | trust boundary | 3 | 直接抓出 BU 自己心裡的底線 |
| 3.14 | 哪些步驟是法規或內控規定**必須**有人簽核的？為什麼？ | regulatory gate | 3 | 法規邊界是硬限制，agent 不能跨 |

---

### 階段 4：Challenge / Reframe（接下來 5–10 分鐘）

目的：**這是這個 agent 的差異化價值**。Agent 在這階段做兩件事：
1. 用 BU 的描述去 pattern match AI capability，找出 BU 沒想到的機會（任務 4）
2. 強迫 BU 做取捨、surface 風險

| # | 題目 | Signal | 任務 | Agent 後續推論 |
|---|---|---|---|---|
| 4.1 | 你想到的解法，過去有沒有人試過？結果怎樣？ | past attempts | 1, 4 | 避免重蹈覆轍，也保護 BU |
| 4.2 | 假設這個工具上線了，三個月後最可能讓你想關掉它的原因是什麼？ | failure foresight | 1, 3 | 前瞻性風險，BU 自己講出來的最有效 |
| 4.3 | 由你親自驗收，會看哪三件事？ | acceptance criteria | 1 | 強迫 BU 想驗收標準，補 evaluability 的洞 |
| 4.4 | 你期待這個工具像哪個你已經在用的東西？ | expectation anchor | 4 | 抓 BU 的期待參考點，避免後面期待落差 |
| 4.5 | 如果一開始只能做 30%，你最希望那 30% 是哪部分？ | MVP forced choice | 1, 4 | 強迫 MVP 思維，避免 scope creep |
| 4.6 | 你剛剛提到 A、B、C 三件事，如果**只能做一件**，會選哪個？為什麼？ | priority forced choice | 1 | 強迫排序比讓他自己排有效 |
| 4.7 | 三個月後你會用什麼指標判斷這個東西做成功了？ | success metric | 1 | 沒指標的需求做了沒辦法收尾 |
| 4.8 | 這幾個需求中，哪一個是「現在不做以後就做不了」？哪一個是「永遠都可以等」？ | urgency forced choice | 1 | 緊迫性排序，影響 BA 階段的 scope 設定 |
| 4.9 | **`[reframe]`** 順著你描述的流程，我注意到 [B 機會] 可能也有空間——具體是 [pattern match 結果]，你覺得有沒有戳到你也想做的事？ | reframe（軟性） | 4 | 動態題：agent 主動丟出沒想到的方向，但留主導權給 BU |
| 4.10 | **`[reframe]`** 你原本提的是 A，我也看到 B、C 兩個方向。要保留原本的 A、改成 B、還是 A+B 都做？ | explicit choice | 4 | **必須**讓 BU 做明確選擇，不能 agent 默默改方向 |

---

### 階段 5：交接準備（最後 5 分鐘）

目的：產出 BA 看得懂的格式。這個階段 agent 不是在 elicit，是在 verify——把整理好的內容 echo 回去讓 BU 確認。

| # | 題目 | Signal | 任務 | Agent 後續推論 |
|---|---|---|---|---|
| 5.1 | 我把你剛剛說的整理成 user story：「身為 X，我想要 Y，這樣才能 Z」——順序對嗎？ | verify | — | 結構化驗證 |
| 5.2 | 我幫你寫了三條驗收標準，哪一條跟你想的不一樣？ | verify acceptance | — | 驗證 evaluability |
| 5.3 | 我預期 BA 會問你這幾個問題（ROI、跟 X 系統的關係、失敗時 fallback），你想先回答哪一個？ | gap detection | — | 補 BA 階段一定會問的洞 |
| 5.4 | 我整理出來的 open questions 有 N 個，哪幾個你能回答、哪幾個需要找其他人？ | gap detection | — | 標記出 BU 答不出來、需要外部 input 的部分 |
| 5.5 | 這份初稿有沒有什麼是你**不希望** BA 看到 / 容易被誤解的地方？ | political safety | — | 保護 BU，避免溝通誤會 |

---

## 四、跨階段配套機制（必須在 MVP 就做進去）

這些不是題目，是 agent 系統層必須設計的機制。沒有這些，發想型 agent 在組織裡會變成「踢皮球工具」——出問題時所有人都說「是 agent 建議的」。

### 機制 1：Trace 完整保留

Agent 必須完整保留以下資訊，附在交給 BA 的文件後面：

- BU 原本想做什麼（A）
- Agent 在哪一輪、根據什麼 signal 建議了什麼（B）
- BU 是否、何時、為什麼採納或拒絕了 agent 的建議
- 整段對話的 timestamp

**目的**：責任歸屬清楚。如果 B 做失敗，要能追溯是 agent 主動建議、BU 同意的決策路徑。

### 機制 2：Agent 主張的視覺標記

Agent 提的方向 reframe 必須在最終文件中**顯眼地標記**出來，跟 BU 自己提的需求視覺上分開。建議用：

- `💡 Agent 建議考慮的方向`：agent 主動 surface 的機會
- `📌 BU 原始需求`：BU 自己提的
- `✅ BU 確認採納`：經過 BU 明確選擇後納入的方向

**目的**：BA 一眼能看出哪些是 agent 主張的，方便獨立判斷。

### 機制 3：BU 必須「明確同意」才採納

Agent 不能默默把 reframe 後的方向寫進需求文件。每次 reframe 後必須有一輪明確選擇（題目 4.10），BU 沒回答之前文件停留在原本的 A。

**目的**：避免「agent 自己改了 BU 也沒注意」這種糟糕情境。

### 機制 4：Information Completeness 追蹤

Agent 內部要 track 自己對四個分析任務各自蒐集了多少 signal。例如：

- 任務 1 需要 7 個 signal，目前蒐集了 5 個 → 下一題往剩下 2 個方向問
- 任務 3 需要 7 個 signal，目前蒐集了 2 個 → 該往風險 / 法規方向問

**目的**：避免 agent 在某些方向問太細、其他方向沒問到。也讓 agent 知道什麼時候可以收斂進入階段 5。

### 機制 5：Checkpoint 與接續

任何時點 BU 想中斷，agent 都要能：

1. 產出當下的「目前整理」
2. 標記目前在哪個階段、還缺哪些資訊
3. 下次接續時，先 echo 上次摘要再繼續

**目的**：30 分鐘是設計目標，但實務上 BU 不會一次聊完。

---

## 五、使用指引

### 給開發團隊

1. **題目不是腳本，是 toolkit**。Agent 應該根據前一輪 BU 的回應動態選下一題，不是按表操課。每個階段選 3-5 題用，不需要每題都問。

2. **`[domain]` 標記的題目依賴 RAG**。沒有子公司知識庫之前，這幾題會退化成通用題目，agent 的信任建立會打折。建議 MVP 階段先用 mock 知識庫驗證 flow，再投入建知識庫的成本。

3. **`[reframe]` 標記的題目是動態生成的**。Agent 必須先做完 pattern match 才知道要丟什麼出來。這部分需要單獨的 prompt / chain 設計。

4. **任務 4 的 pattern match 需要的 mapping 表**：

| BU 描述的特徵 | 對應的 AI 能力 |
|---|---|
| 重複做一樣的動作 | RPA / structured automation |
| 同一份資訊要謄到不同地方 | extraction + structured output |
| 看一段文字判斷類別 / 找出某個欄位 | LLM classification, NER |
| 把幾個 source 的資料拼起來看 | RAG / agentic retrieval |
| 要把專業內容講給非專業聽，或寫摘要 | LLM generation |
| 反覆被問同樣問題 | RAG / knowledge agent |
| 老師傅才會做、新人要看老人 demo | flag — 可能是 ML 機會也可能是 explainability 黑洞 |

### 給 BU（對話前的引導）

Agent 開場時應該讓 BU 知道：

- 這次對話大概 30 分鐘
- 結束時會有一份初稿，BU 可以決定是否送到 BA
- BU 隨時可以中斷、下次接續
- Agent 會根據 BU 的描述主動建議方向，BU 可以接受、修改、或否決
- 對話內容會完整保留，給 BA 後續參考

### 給 BA / AI 治理單位

這個 agent 的定位是**發想者 + 整理者**，不是取代 BA。Agent 會：

- 幫 BA 把 BU 的模糊想法整理成半成品
- 主動 surface BU 沒想到的 AI 機會（這是 agent 最有差異化價值的地方）
- 但**不**做最終的 scope 決定、技術選型、資源評估——這些仍然是 BA 的工作

如果 agent 提的方向 reframe 在 BA 看來不合理，BA 可以直接退回——機制 2 的視覺標記讓這件事容易做到。

---

## 附錄 A：題目對應分析任務的覆蓋矩陣

| 階段 | 任務 1（適合性） | 任務 2（流程定位） | 任務 3（人為介入） | 任務 4（沒想到的機會） |
|---|---|---|---|---|
| 1 發散 | 1.1, 1.2 | 1.1, 1.2 | — | 1.3, 1.4, 1.5, 1.6 |
| 2 脈絡建立 | 2.4, 2.7 | 2.1–2.10 | 2.2 | 2.4, 2.5 |
| 3 收斂 | 3.1–3.7, 3.9 | — | 3.2, 3.6, 3.8–3.14 | 3.7 |
| 4 Challenge | 4.1, 4.3, 4.5–4.8 | — | 4.1, 4.2 | 4.5, 4.9, 4.10 |
| 5 交接 | — | — | — | — |

如果某個任務在某階段是 — ，表示該階段不適合做這個任務的 signal 採集。例如階段 5 是 verify 不是 elicit，所以四個任務都不再採集新 signal。

---

## 附錄 B：v1 → v2 的主要變更紀錄

供開發團隊理解設計演變：

1. **Framing 改變**：從「BA 工具」改為「BU 工具」。Agent 直接服務 BU，但結果交給 BA。

2. **新增階段 1（發散 / 建立信任）**：v1 直接從工作流程梳理開始，對 BU 太冷。

3. **新增 `[domain]` 動態題**：依賴 RAG 內部知識庫產生，同時做 elicitation 和 trust building。

4. **新增 `[reframe]` 動態題**：取代 v1 中那些「BU 答不出來」的 AI 能力題。Agent 自己做 pattern match，再用軟性方式提給 BU。

5. **拿掉的題目**：「對應的 AI 能力是什麼」「ROI 估算」「技術成熟度」——這些 BU 答不出來，是 agent 內部要做的判斷。

6. **改寫的題目**：把「judgment density」「explainability requirement」「accountability」這類分析師語言改成 BU 友善版本。

7. **新增配套機制**：trace 保留、視覺標記、明確同意、completeness 追蹤、checkpoint。這些 v1 沒提到，但發想型 agent 沒這些會出組織政治問題。

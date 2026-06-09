# WoOW Snippet Builder x HA IoT 深度整合 — 設計文件

> **日期**: 2026-06-09
> **目的**: 讓 WoOW Snippet Builder 的 4 種前端元件能完整呈現 Home Assistant 的 entities / devices / groups / history 資料
> **方案**: (A) 白名單擴充 — 最小改動，最大覆蓋

---

## 1. 整合團隊 — 7 位專家

| # | 角色 | 職責 | Agent 類型 |
|---|------|------|-----------|
| 1 | **Odoo 資料建置及流程測試專家** | 安裝模組、同步 HA 資料、建立 snippet filter records、在 Website Editor 拖放元件驗證全流程 | general-purpose |
| 2 | **程式碼修復專家** | 根據錯誤分析修改 Python/JS/XML 程式碼 | general-purpose |
| 3 | **錯誤解析專家** | 讀取 Odoo logs、Playwright 截圖、Console errors，定位 root cause | code-analyzer |
| 4 | **Home Assistant 系統專家** | 驗證 HA 連線、API 回應、entity 資料完整性，確保 HA→Odoo 同步正確 | general-purpose (ha-mcp) |
| 5 | **前端整合測試專家** | 在 Website 前端用 Playwright 驗證 4 種 snippet 能否正確渲染 HA 資料 | general-purpose |
| 6 | **資料對照與覆蓋率專家** | 交叉比對 HA 117 entities / 23 domains 是否全面覆蓋，確保每種 snippet 都測過每種 HA 資料類型 | general-purpose |
| 7 | **獨立評分專家** | 每輪迭代後獨立打分 (≥90 通過) | general-purpose |

---

## 2. 評分標準 (100 分制，≥90 通過)

| 項目 | 分數 | 評分細節 |
|------|------|----------|
| **A. 白名單與 API 連通** | 15 | 4 個 HA model 都出現在 /woow_snippet/available_models；model_fields 回傳正確欄位 |
| **B. Stat Card 正確性** | 15 | 6 種 operation (count/sum/avg/min/max/count_distinct) × 4 個 model 能正確計算；4 種 sub_type 都能渲染 |
| **C. Chart 正確性** | 15 | bar/pie/line/doughnut/radar 至少各 1 個 HA 資料圖表能正確渲染；group_by 分組正確 |
| **D. Data Table 正確性** | 15 | 4 個 model 各至少 1 個 table 能分頁、排序、搜尋；欄位值與 HA 實際數據一致 |
| **E. Dynamic Content 正確性** | 15 | 至少 3 種 template (card/list/hero) 用 snippet filter 呈現 HA entity 資料 |
| **F. 資料覆蓋率** | 10 | entities 四大類 (entities/devices/groups/history) 都有被至少一種 snippet 呈現 |
| **G. 錯誤容忍度** | 10 | 前端無 JS console error；API 無 500 error；Odoo log 無 traceback |
| **H. 文件品質** | 5 | README 有整合說明；程式碼有必要註解 |

---

## 3. 技術方案：白名單擴充

### 3.1 需要修改的檔案

#### `woow_snippet_builder/controllers/main.py`

在 `_DEFAULT_ALLOWED_MODELS` 新增 4 個 HA model：

```python
_DEFAULT_ALLOWED_MODELS = {
    # ... existing models ...
    # Home Assistant IoT models
    'ha.entity',
    'ha.device',
    'ha.entity.group',
    'ha.entity.history',
}
```

#### 潛在問題與對策

| 問題 | 原因 | 對策 |
|------|------|------|
| HA model 不存在於 request.env | odoo_ha_addon 模組未安裝 | `_validate_model()` 已有 "model does not exist" 檢查，安全降級 |
| ha.entity.history 的 num_state 是 computed/stored | read_group 需要 stored 欄位 | num_state 已經是 `store=True`，可以直接用 |
| ha.entity 的 attributes 是 Json 欄位 | data_table 的 field 過濾器會跳過 properties 類型 | Json ≠ properties，但可能需要特殊處理顯示 |
| 多 instance 場景 | ha.entity 有 ha_instance_id 外鍵 | 用 domain 過濾即可：`[('ha_instance_id', '=', X)]` |
| sudo() 安全性 | 公開 API 用 sudo() 讀取 HA 資料 | HA 資料本身是從 HA sync 來的非敏感狀態資料，可接受 |

### 3.2 Snippet Filter 資料建置 (Dynamic Content 用)

需要建立 `ir.filters` + `website.snippet.filter` records：

```
Filter 1: HA Entities — model=ha.entity, fields=entity_id,name,domain,entity_state
Filter 2: HA Entities (Sensors) — model=ha.entity, domain=[('domain','=','sensor')]
Filter 3: HA Entities (Switches) — model=ha.entity, domain=[('domain','=','switch')]
Filter 4: HA Devices — model=ha.device, fields=name,manufacturer,model
Filter 5: HA Entity Groups — model=ha.entity.group, fields=name,entity_count,description
Filter 6: HA History (Recent) — model=ha.entity.history, fields=entity_state,last_changed
```

### 3.3 各 Snippet × 各 HA Model 測試矩陣

```
                    ha.entity    ha.device    ha.entity.group    ha.entity.history
Stat Card           ✓ count      ✓ count      ✓ count            ✓ count/avg(num_state)
  - by domain       ✓ group_by   ✓ group_by   —                  ✓ group_by entity
  - progress        ✓            ✓            ✓                  ✓
  - trend           ✓            —            —                  ✓
  - threshold       ✓            ✓            ✓                  ✓

Chart
  - bar             ✓ domain     ✓ manufacturer ✓ entity_count   ✓ num_state
  - pie             ✓ domain     ✓ manufacturer —                —
  - line            —            —            —                  ✓ time series
  - gauge           ✓ count/target ✓ count    ✓ count            ✓ avg

Data Table          ✓ full       ✓ full       ✓ full             ✓ full
  - search          ✓            ✓            ✓                  ✓
  - sort            ✓            ✓            ✓                  ✓
  - pagination      ✓            ✓            ✓                  ✓

Dynamic Content     ✓ card/list  ✓ card/list  ✓ card/list        ✓ timeline
```

---

## 4. 環境準備

### 目標環境：port 9105 (odoo-websitesnippet)

在現有 snippet builder instance 上安裝 `odoo_ha_addon` 模組：

1. 掛載 HA addon 原始碼到 container 的 addons 路徑
2. 更新模組列表
3. 安裝 `odoo_ha_addon`
4. 設定 HA instance 連線：
   - URL: `https://woowtech-ha.woowtech.io`
   - Token: `eyJhbGci...SSqhk`
5. 執行完整同步 (entities + devices + areas)
6. 驗證 117 entities 正確匯入

### 替代方案：啟動 odoo-haiot (port 9077)

如果 9105 安裝 HA addon 有困難，可以：
1. 啟動 `odoo-haiot-web` + `odoo-haiot-db`
2. 在 9077 上安裝 `woow_snippet_builder`
3. 同樣的測試流程

---

## 5. 迭代流程

```
Round N:
  ┌─────────────────────────────────────────────┐
  │ Phase 1: 建置 & 測試 (並行)                  │
  │  ├─ Agent 1 (Odoo 流程): 建資料、拖元件測試   │
  │  ├─ Agent 4 (HA 專家): 驗證 HA 同步完整性     │
  │  └─ Agent 5 (前端): Playwright 截圖驗證       │
  ├─────────────────────────────────────────────┤
  │ Phase 2: 錯誤收集                            │
  │  └─ Agent 3 (錯誤解析): 分析所有 log/截圖     │
  ├─────────────────────────────────────────────┤
  │ Phase 3: 修復 (並行)                         │
  │  ├─ Agent 2 (程式碼修復): 改 Python/JS/XML    │
  │  └─ Agent 6 (覆蓋率): 找遺漏的測試場景        │
  ├─────────────────────────────────────────────┤
  │ Phase 4: 評分                               │
  │  └─ Agent 7 (獨立評分): 打分，≥90 → PASS      │
  └─────────────────────────────────────────────┘
         │ PASS → 完成
         │ FAIL → Round N+1 (帶入上輪的錯誤清單)
```

---

## 6. 第一輪實施步驟

### Step 1: 環境準備
- [ ] 確認 odoo-websitesnippet (9105) 可用
- [ ] 掛載 odoo_ha_addon 到 9105 container
- [ ] 安裝 odoo_ha_addon 模組
- [ ] 設定 HA instance 連線並同步資料

### Step 2: 白名單擴充
- [ ] 修改 `controllers/main.py` 加入 4 個 HA model
- [ ] 驗證 `/woow_snippet/available_models` 回傳 HA models
- [ ] 驗證 `/woow_snippet/model_fields` 回傳各 model 欄位

### Step 3: Snippet Filter 建置
- [ ] 建立 6+ 個 ir.filters records (covering 4 HA models)
- [ ] 建立對應的 website.snippet.filter records
- [ ] 驗證 Dynamic Content snippet 可選到這些 filters

### Step 4: 逐一測試 4 種 Snippet
- [ ] Stat Card × 4 models × 4 sub_types
- [ ] Chart × 4 models × 5 chart_types
- [ ] Data Table × 4 models (search/sort/pagination)
- [ ] Dynamic Content × 4 models × 6 templates

### Step 5: 錯誤修復迭代
- [ ] 收集所有錯誤 (log + console + 截圖)
- [ ] 分析 root cause
- [ ] 修復程式碼
- [ ] 重新測試

### Step 6: 獨立評分
- [ ] 按 8 項標準打分
- [ ] ≥90 → PASS, commit & push
- [ ] <90 → 回到 Step 5

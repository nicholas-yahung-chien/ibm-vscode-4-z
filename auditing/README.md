# VS Code Extensions Audit (Windows MVP)

以 **PowerShell** 在 Windows 上稽核 VS Code 擴充套件：
- 來源：Open VSX（可改私有 Open VSX）
- 產出：CycloneDX SBOM（Syft）、弱點掃描（Grype + OSV-Scanner）、License（取 package.json）
- 政策：`policy.yml`
- 清單：`extensions.allowlist`

## 功能概述

本安全稽核系統提供三個方面的安全檢查：

1. **VS Code 擴充功能** - 檢查授權條款和漏洞
2. **PyPI 套件** - 檢查 Python 套件的漏洞
3. **工具軟體** - 檢查 tools.yml 中有 CPE 設定的工具漏洞

## 本機使用

### 1. 安裝必要工具

- **Node.js**，並執行 `npm i -g ovsx`
- **Python 3**
- **Python 依賴模組**：
  ```bash
  pip install pyyaml requests
  ```
- **下載並放入 PATH**：
  - Syft（Windows）
  - Grype（Windows）
  - OSV-Scanner（Windows）

### 2. 設定配置檔案

#### policy.yml
設定安全政策和閾值：
```yaml
license:
  allow:
    - MIT
    - Apache-2.0
    - BSD-2-Clause
    # ... 其他允許的授權條款
  deny:
    - AGPL-3.0
    - SSPL-1.0
    # ... 其他拒絕的授權條款
vulnerability:
  max_cvss: 8.0  # 最大允許的 CVSS 分數
```

#### tools.yml
為需要掃描的工具設定 CPE 名稱：
```yaml
vscode:
  version: "1.101.0"
  cpe_name: "cpe:2.3:a:microsoft:visual_studio_code:-:*:*:*:*:*:*:*"
  # ... 其他設定

python:
  version: "3.13.3"
  cpe_name: "cpe:2.3:a:python:python:-:*:*:*:*:*:*:*"
  # ... 其他設定
```

### 3. 執行掃描

```bash
cd auditing/scripts
python scan.py
```

或使用 PowerShell：
```powershell
python scripts/scan.py
```

## 掃描功能詳解

### VS Code 擴充功能掃描

- **授權條款檢查**：從 package.json 中提取授權條款，與 policy.yml 中的允許/拒絕清單比較
- **漏洞掃描**：使用 Grype 和 OSV-Scanner 檢查擴充功能的漏洞
- **SBOM 生成**：使用 Syft 生成 CycloneDX 格式的軟體物料清單

### PyPI 套件掃描

掃描 `pywhls` 目錄下的所有 `.whl` 檔案：

- **自動解析**：從 wheel 檔案名稱中提取套件名稱和版本
- **OSV API 查詢**：使用 Google OSV API 查詢套件的漏洞資訊
- **CVSS 分析**：分析漏洞的 CVSS 分數，找出高風險漏洞
- **政策比較**：與設定的 CVSS 閾值進行比較

#### 支援的 Wheel 格式
- `ansible_core-2.19.0-py3-none-any.whl`
- `black-25.1.0-cp313-cp313-win_amd64.whl`
- `cryptography-45.0.6-cp311-abi3-win_amd64.whl`

### 工具軟體掃描

掃描 `tools.yml` 中有 `cpe_name` 設定的工具：

- **CPE 版本替換**：自動將 CPE 名稱中的版本 placeholder (`-`) 替換為實際版本號
- **NVD API 查詢**：使用 NIST National Vulnerability Database API 查詢 CVE 漏洞
- **CVSS 分數分析**：分析漏洞的 CVSS 分數，找出最高分數和超過閾值的漏洞
- **政策比較**：與 `policy.yml` 中設定的最大 CVSS 容許度進行比較

#### 範例 CPE 轉換
```
輸入: cpe:2.3:a:microsoft:visual_studio_code:-:*:*:*:*:*:*:* 和版本 "1.101.0"
輸出: cpe:2.3:a:microsoft:visual_studio_code:1.101.0:*:*:*:*:*:*:*
```

## 輸出報告

### 主摘要報告 (summary.md)
包含所有掃描結果的摘要：
- 擴充功能掃描結果
- PyPI 套件掃描結果
- 工具掃描結果
- 問題摘要和統計

### 詳細報告
- **擴充功能報告**：每個擴充功能的詳細掃描結果
- **PyPI 摘要報告** (pypi_summary.md)：PyPI 套件的掃描結果
- **工具摘要報告** (tools_summary.md)：工具的掃描結果

### 報告範例

#### 主摘要報告
```markdown
# VS Code 擴充功能安全稽核報告

## 掃描範圍

本稽核包含以下三個方面的安全檢查：

1. **VS Code 擴充功能** - 檢查授權條款和漏洞
2. **PyPI 套件** - 檢查 Python 套件的漏洞
3. **工具軟體** - 檢查 tools.yml 中有 CPE 設定的工具漏洞

## 問題摘要

### 工具漏洞問題

以下工具存在高風險漏洞 (CVSS 分數超過允許閾值)：

- python@3.13.3: 1 個漏洞 >= CVSS 8.0
```

#### 工具詳細報告
```markdown
# 工具安全掃描報告

| 工具名稱 | 版本 | CPE 名稱 | 最高 CVSS | 高風險漏洞數量 | 狀態 |
|---|---|---|---|---|---|
| python | 3.13.3 | `cpe:2.3:a:python:python:-:*:*:*:*:*:*:*` | 8.8 | 1 | ⚠️ 發現 1 個高風險漏洞 (最高 CVSS: 8.8) |

## 詳細漏洞資訊

### python@3.13.3

**CPE:** `cpe:2.3:a:python:python:3.13.3:*:*:*:*:*:*:*`

**最高 CVSS 分數:** 8.8

**高風險漏洞數量:** 1

**漏洞列表:**

- CVE-2020-29396 (CVSS: 8.8) - A sandboxing issue in Odoo Community...
```

## 掃描流程

1. **載入配置**：讀取 policy.yml、extensions.yml 和 tools.yml
2. **擴充功能掃描**：
   - 下載擴充功能
   - 檢查授權條款
   - 生成 SBOM
   - 執行漏洞掃描
3. **PyPI 套件掃描**：
   - 解析 wheel 檔案
   - 查詢 OSV API
   - 分析漏洞
4. **工具掃描**：
   - 篩選有 CPE 設定的工具
   - 替換版本號
   - 查詢 NVD API
   - 分析漏洞
5. **報告生成**：生成詳細的 Markdown 報告

## 錯誤處理

- **API 查詢失敗**：記錄錯誤但繼續處理其他項目
- **配置載入失敗**：記錄錯誤並跳過相關掃描
- **網路連線問題**：自動重試並記錄錯誤
- **檔案解析錯誤**：記錄錯誤並繼續處理其他檔案

## 依賴項目

- `requests`：HTTP API 查詢
- `yaml`：YAML 配置檔案解析
- `pathlib`：路徑處理

## 注意事項

1. **網路連線**：需要連線到以下 API：
   - Open VSX Registry
   - Google OSV API (https://api.osv.dev)
   - NVD API (https://services.nvd.nist.gov)
2. **API 限制**：各 API 有請求頻率限制，掃描可能需要一些時間
3. **CPE 格式**：確保 CPE 名稱格式正確，版本 placeholder 為 `-`
4. **版本匹配**：某些工具的版本號可能需要特殊處理才能與 CVE 資料庫匹配

## 範例輸出

執行掃描後，您會看到類似以下的輸出：

```
=== 開始掃描工具 ===
[2025-08-22 13:56:52] 掃描工具: vscode@1.101.0 (CPE: cpe:2.3:a:microsoft:visual_studio_code:-:*:*:*:*:*:*:*)
[2025-08-22 13:56:54] 掃描工具: python@3.13.3 (CPE: cpe:2.3:a:python:python:-:*:*:*:*:*:*:*)
...
工具摘要報告已生成: ../reports/tools_summary.md
發現 1 個工具漏洞問題
```

## 更新記錄

- **v1.0.0**：初始版本，支援基本的擴充功能掃描
- **v1.1.0**：新增 PyPI 套件掃描功能
- **v1.2.0**：新增工具軟體掃描功能
- 整合 NVD API 查詢
- 支援 CPE 版本替換
- 生成詳細的 Markdown 報告

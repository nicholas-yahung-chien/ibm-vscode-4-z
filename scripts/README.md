# VSCode4z 腳本工具集

IBM VSCode for Z Development Environment 的腳本工具集，提供完整的開發環境建置、安裝、設定和管理功能。

## 📋 腳本功能說明

### 🔧 核心腳本

| 腳本檔案 | 用途 | 主要功能 |
|---------|------|----------|
| `build.py` | 專案建置 | 自動化打包和發布流程，生成完整版和精簡版壓縮檔 |
| `download.py` | 資源下載 | 下載 VSCode 擴充功能、Python 套件和工具包 |
| `install.py` | 環境安裝 | 完整的 VSCode4z 開發環境安裝和設定 |
| `workspace.py` | 工作區設定 | 設定 Zowe 連線參數和工作區配置 |
| `assistant.py` | AI 助手設定 | 設定 Watsonx Assistant 和 AI 模型參數 |
| `uninstall.py` | 環境卸載 | 清理已安裝的開發環境 |

### 🛠️ 工具腳本

| 腳本檔案 | 用途 | 主要功能 |
|---------|------|----------|
| `configs.py` | 配置管理 | 載入和管理各種 YAML 設定檔 |

### 📁 工具模組

| 目錄 | 用途 | 包含模組 |
|------|------|----------|
| `utils/` | 工具函式 | `path_utils.py`, `file_utils.py`, `message_utils.py` |
| `configs/` | 設定檔 | 各種 YAML 配置檔案 |

## 🚀 執行前準備

### 1. Python 環境要求

- **Python 版本**: 3.7 或以上
- **作業系統**: Windows 10/11

### 2. 安裝必要的外部模組

```bash
# 安裝核心依賴模組
pip install pyyaml requests pyminizip

# 安裝可選模組（用於建立 Windows 快捷方式）
pip install pywin32

# 安裝建置工具（僅用於 build.py）
pip install pyinstaller
```

### 3. 依賴模組說明

| 模組 | 用途 | 是否必需 |
|------|------|----------|
| `pyyaml` | 讀取 YAML 設定檔 | ✅ 必需 |
| `requests` | HTTP 檔案下載 | ✅ 必需 |
| `pyminizip` | 檔案壓縮功能 | ✅ 必需 |
| `pywin32` | Windows 快捷方式建立 | ⚪ 可選 |
| `pyinstaller` | Python 腳本打包 | ⚪ 僅 build.py 需要 |

## 📖 使用方式

### 1. 完整環境建置流程

```bash
# 1. 下載所需資源
python download.py --workspace <工作區路徑>

# 2. 建置專案（包含打包執行檔）
python build.py --version <版本號>

# 3. 安裝開發環境
python install.py

# 4. 設定工作區
python workspace.py

# 5. 設定 AI 助手（可選）
python assistant.py
```

### 2. 個別腳本使用

#### 下載資源
```bash
python download.py --workspace <工作區路徑>
```

#### 建置專案
```bash
python build.py --version 2.7.0
```

#### 安裝環境
```bash
python install.py
# 或自動執行模式
python install.py -y
```

#### 設定工作區
```bash
python workspace.py
# 或指定工作區
python workspace.py --workspace <工作區路徑>
```

#### 設定 AI 助手
```bash
python assistant.py
```

#### 卸載環境
```bash
python uninstall.py
# 或自動執行模式
python uninstall.py -y
```

## ⚙️ 設定檔說明

腳本使用以下 YAML 設定檔：

| 設定檔 | 用途 | 說明 |
|--------|------|------|
| `configs/tools.yml` | 工具包配置 | 定義需要下載的工具包 |
| `configs/pip.yml` | Python 套件配置 | 定義需要安裝的 Python 套件 |
| `configs/extensions.yml` | 擴充功能配置 | 定義需要安裝的 VSCode 擴充功能 |
| `configs/init.yml` | 初始化配置 | 定義環境初始化參數 |
| `configs/build.yml` | 建置配置 | 定義建置流程參數 |
| `configs/workspace.yml` | 工作區配置 | 定義 Zowe 連線參數（可選） |

## 🔧 故障排除

### 常見問題

1. **模組找不到錯誤**
   ```bash
   # 確保已安裝所有必要模組
   pip install pyyaml requests pyminizip
   ```

2. **權限錯誤**
   - 以系統管理員身分執行 PowerShell
   - 確保對目標目錄有寫入權限

3. **網路連線問題**
   - 檢查網路連線
   - 確認防火牆設定
   - 檢查代理伺服器設定

4. **檔案被鎖定**
   - 關閉相關程式（VSCode、終端機等）
   - 重新啟動電腦

### 日誌和除錯

- 所有腳本都會顯示詳細的執行日誌
- 錯誤訊息會明確指出問題所在
- 可使用 `-y` 參數跳過確認步驟進行自動執行

## 📞 支援

如有問題，請參考：
- 專案文件：`../README.md`
- 設定檔範例：`configs/` 目錄
- 錯誤日誌：執行時的輸出訊息

---

**開發單位**: IBM Taiwan Technology Expert Labs  
**版本**: 2.7.0  
**日期**: 2025/08/19

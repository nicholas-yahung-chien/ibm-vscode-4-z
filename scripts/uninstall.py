#!/usr/bin/env python3
"""
IBM VSCode for Z Development Environment Setup Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 2.6.0
日期: 2025/01/13

說明:
根據先前工具對應的資料夾路徑，
將這些目錄中除了 .zip 檔案以外的所有檔案與子目錄全部刪除，
達到清除（uninstall）已展開區域的目的。

工具對應的資料夾路徑如下：
    - vscode: <腳本所在目錄>/vscode
    - jdk21: <腳本所在目錄>/java
    - workspace: <腳本所在目錄>/workspace
    - python: <腳本所在目錄>/python
    - extensions: <腳本所在目錄>/extensions

使用方式:
只有副檔名為 ".zip" 的檔案會被保留，其它所有檔案與子目錄都會被清除。

更新記錄:
- v2.6.0: 優化檔案鎖定檢測和進程終止功能，改善刪除流程
- v2.5.0: 新增檔案鎖定檢測和進程終止功能，改善刪除流程
- v2.4.11: 優化檔案清理邏輯，提升刪除效能
- v2.3.0: 重構檔案處理功能，改善錯誤處理
- v2.2.1: 初始版本，提供基本的卸載功能
"""

import os
import argparse
import glob
import shutil
import subprocess
import time
from pathlib import Path
from utils.file_utils import cleanup_directory_except
from utils.path_utils import compose_folder_path, get_script_dir

# 導入我們的設定檔工具模組
from configs import (
    load_tools_config
)

# -------------------------------
#  功能函式
# -------------------------------
def restore_backup(workspace_dir):
    """
    檢查 workspace 目錄內是否有 zowe.config.backup_*.json 備份檔，
    若有，則將最新的備份檔還原為 zowe.config.json，並刪除該備份檔。
    """
    backup_files = glob.glob(os.path.join(workspace_dir, "zowe.config.backup_*.json"))
    
    if not backup_files:
        print("未找到 zowe.config.json 的備份檔，跳過還原動作。")
        return
    
    # 依照檔案名稱排序，確保取最新的備份檔
    backup_files.sort(reverse=True)
    latest_backup = backup_files[0]
    
    config_path = os.path.join(workspace_dir, "zowe.config.json")
    
    try:
        # 還原備份檔
        shutil.copy(latest_backup, config_path)
        print(f"已還原 {latest_backup} 為 {config_path}")
        
        # 刪除備份檔
        os.remove(latest_backup)
        print(f"已刪除備份檔：{latest_backup}")
    except Exception as e:
        print(f"還原過程發生錯誤：{e}")

# -------------------------------
# 主流程
# -------------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(description="Install script with optional auto-confirmation.")
    parser.add_argument("-y", "--yes", action="store_true", help="自動執行所有步驟，不須等待使用者確認。")
    parser.add_argument("--workspace", type=str, help="指定工作區目錄，預設為腳本檔所在路徑。")
    return parser.parse_args()

def main():
    args = parse_arguments()
    # 若使用者有指定 --workspace 則使用該目錄，否則預設為 script_dir
    workspace = Path(args.workspace).resolve() if args.workspace else get_script_dir()
    os.chdir(workspace)
    print("目前工作目錄設定為：", workspace)
    
    # 載入 tools.yml 設定檔
    tools = load_tools_config()
    
    print("=== Uninstall 開始 ===\n")
    
    # 逐一清理每個工具所在的資料夾，本動作將保留資料夾中所有 .zip 檔，其它內容皆清除
    for tool_name, config in tools.items():
        print(f"清理 [{tool_name}] 目錄：{config['dir']}")
        cleanup_directory_except(compose_folder_path(workspace, config["dir"]), f".{config['type']}")
    
    # 執行備份檔還原
    workspace_dir = os.path.join(workspace, "workspace")
    restore_backup(workspace_dir)
    
    print("=== Uninstall 完成 ===")
    input("按 Enter 鍵結束程式：")


if __name__ == "__main__":
    main()
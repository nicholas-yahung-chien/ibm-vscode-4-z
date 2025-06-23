#!/usr/bin/env python3
"""
程式名稱: uninstall.py
開發單位: IBM Expert Labs
開發人員: nicholas.yahung.chien@ibm.com
日期: 2025/06/20
版本: 2.2.1

說明:
根據先前工具對應的資料夾路徑，
將這些目錄中除了 .zip 檔案以外的所有檔案與子目錄全部刪除，
達到清除（uninstall）已展開區域的目的。

工具對應的資料夾路徑如下：
    - vscode: <腳本所在目錄>/vscode
    - jdk21: <腳本所在目錄>/java
    - workspace: <腳本所在目錄>/workspace

使用方式:
只有副檔名為 ".zip" 的檔案會被保留，其它所有檔案與子目錄都會被清除。
"""

import os
import sys
import argparse
import glob
import shutil
import yaml
import re
from pathlib import Path
from file_utils import cleanup_directory_except

# -------------------------------
#  功能函式
# -------------------------------
def get_script_dir():
    """
    若被 PyInstaller 打包，則使用 sys.executable 的目錄作為腳本所在目錄；
    否則使用 __file__ 的目錄。
    """
    # 取得腳本所在目錄（考慮是否為 PyInstaller 打包）
    if getattr(sys, 'frozen', False):
        # 取得 .exe 執行檔所在路徑
        return Path(sys.executable).parent.resolve()
    else:
        # 取得 .py 腳本所在路徑
        return Path(__file__).parent.resolve()

def load_tools_config(scripts_dir):
    """
    載入 tools.yml 設定檔，並回傳工具包資訊。
    """
    tools_yml_path = os.path.join(scripts_dir, "tools.yml")
    if not os.path.exists(tools_yml_path):
        sys.exit(f"找不到設定檔: {tools_yml_path}")
    with open(tools_yml_path, "r", encoding="utf-8") as f:
        tools = yaml.safe_load(f)
    return tools

def update_java_dirs(java_root_dir, tools_dic):
    """
    遍歷 java_root_dir 內所有子資料夾，以 "java{資料夾名稱}" 為 key 更新 tools_dic，
    並設定相應的搜尋 pattern（例如：*jdk*{版本}*.zip）。
    """
    if not os.path.exists(java_root_dir):
        print(f"找不到 java 目錄：{java_root_dir}")
        return tools_dic
    for folder in os.listdir(java_root_dir):
        folder_path = os.path.join(java_root_dir, folder)
        if os.path.isdir(folder_path):
            key = f"java{folder}"
            pattern = f"*jdk*{folder}*.zip"
            tools_dic[key] = {
                "dir": folder_path,
                "pattern": pattern
            }
            print(f"已更新工具包路徑：新增 {key}")
    return tools_dic

def extract_extension_from_pattern(pattern):
    """
    從傳入的 pattern 字串中提取尾端副檔名。
    
    例如：
      - "VSCode*.zip" 會回傳 ".zip"
      - "*node*.exe" 會回傳 ".exe"
    
    若找不到副檔名則回傳空字串。
    """
    match = re.search(r'(\.[\.\w]+)$', pattern)
    if match:
        return match.group(1)
    else:
        return ""

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
    tools = load_tools_config(os.path.join(workspace, "scripts"))
    # 更新 java 相關工具包路徑
    tools = update_java_dirs(os.path.join(workspace, "java"), tools)
    
    print("=== Uninstall 開始 ===\n")
    
    # 逐一清理每個工具所在的資料夾，本動作將保留資料夾中所有 .zip 檔，其它內容皆清除
    for tool_name, tool_path in tools.items():
        print(f"清理 [{tool_name}] 目錄：{tool_path['dir']}")
        cleanup_directory_except(tool_path["dir"], extract_extension_from_pattern(tool_path["pattern"]))
    
    # 執行備份檔還原
    workspace_dir = os.path.join(workspace, "workspace")
    restore_backup(workspace_dir)
    
    print("=== Uninstall 完成 ===")
    input("按 Enter 鍵結束程式：")


if __name__ == "__main__":
    main()
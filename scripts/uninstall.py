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
import glob
import shutil
from pathlib import Path
from file_utils import cleanup_directory

def update_java_dirs(java_root_dir, tools_dic):
    if not os.path.exists(java_root_dir):
        # 沒有 java 目錄就直接傳原本的 tools
        print(f"找不到 java 目錄：{java_root_dir}")
        return tools_dic
    # 遍歷所有子目錄
    for folder in os.listdir(java_root_dir):
        folder_path = os.path.join(java_root_dir, folder)
        if os.path.isdir(folder_path):
            # 更新 tools 字典，組成的 key 為 "java" + 資料夾名稱
            key = f"java{folder}"
            tools_dic[key] = {
                "dir": folder_path,
                "except": "zip"
            }
            print(f"已更新工具包路徑：新增 {key}")
    return tools_dic

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
    parser.add_argument("--workspace", type="str", help="指定工作區目錄，預設為腳本檔所在路徑。"
    return parser.parse_args()

def main(args):
    # 取得腳本所在目錄（考慮是否為 PyInstaller 打包）
    if getattr(sys, 'frozen', False):
        # 取得 .exe 執行檔所在路徑
        script_dir = Path(sys.executable).parent.resolve()
    else:
        # 取得 .py 腳本所在路徑
        script_dir = Path(__file__).parent.resolve()
    # 若使用者有指定 --workspace 則使用該目錄，否則預設為 script_dir
    workspace = Path(args.workspace).resolve() if args.workspace else script_dir
    os.chdir(workspace)
    print("目前工作目錄設定為：", workspace)
    
    # 定義工具對應的目錄（相對於腳本所在目錄）
    tools = {
        "vscode": {"dir": os.path.join(workspace, "vscode"), "except": "zip" },
        "python": {"dir": os.path.join(workspace, "python"), "except": "zip" },
        "node": {"dir": os.path.join(workspace, "node"), "except": "zip" },
        "git": {"dir": os.path.join(workspace, "git"), "except": "7z.exe" },
        "zowe": {"dir": os.path.join(workspace, "zowe-cli"), "except": "zip" },
    }
    tools = update_java_dirs(os.path.join(workspace, "java"), tools)
    
    print("=== Uninstall 開始 ===\n")
    
    # 逐一清理每個工具所在的資料夾，本動作將保留資料夾中所有 .zip 檔，其它內容皆清除
    for tool_name, tool_path in tools.items():
        print(f"清理 [{tool_name}] 目錄：{tool_path["dir"]}")
        cleanup_directory(tool_path["dir"], tool_path["except"])
    
    # 執行備份檔還原
    workspace_dir = os.path.join(workspace, "workspace")
    restore_backup(workspace_dir)
    
    print("=== Uninstall 完成 ===")
    input("按 Enter 鍵結束程式：")


if __name__ == "__main__":
    args = parse_arguments()
    main(args)
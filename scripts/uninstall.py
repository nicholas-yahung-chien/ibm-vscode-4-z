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

def cleanup_directory(target_dir, except_pattern):
    """
    清除指定目錄中所有非 .<except_pattern> 檔的項目，包括所有檔案與子目錄。
    只保留副檔名為 .<except_pattern> 的檔案。
    """
    if not os.path.exists(target_dir):
        print(f"目錄不存在：{target_dir}")
        return

    print(f"開始清理目錄：{target_dir}")
    for entry in os.listdir(target_dir):
        full_path = os.path.join(target_dir, entry)
        # 如果是檔案，且副檔名不是 .<except_pattern>（忽略大小寫），則刪除該檔案
        if os.path.isfile(full_path):
            if not entry.lower().endswith(f".{except_pattern}"):
                try:
                    os.remove(full_path)
                    print(f"已刪除檔案: {full_path}")
                except Exception as e:
                    print(f"刪除檔案 {full_path} 發生錯誤: {e}")
        # 如果是目錄，則直接遞迴刪除整個目錄
        elif os.path.isdir(full_path):
            try:
                shutil.rmtree(full_path)
                print(f"已遞迴刪除目錄: {full_path}")
            except Exception as e:
                print(f"刪除目錄 {full_path} 發生錯誤: {e}")
    print(f"目錄清理完成：{target_dir}\n")

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

def main():
    # 取得腳本所在的工作目錄
    if getattr(sys, 'frozen', False):  # 檢查是不是被 PyInstaller 打包成 .exe
        # 取得 .exe 執行檔所在路徑
        script_dir = Path(sys.executable).parent.resolve()
    else:
        # 取得 .py 腳本所在路徑
        script_dir = Path(__file__).parent.resolve()
    # script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 定義工具對應的目錄（相對於腳本所在目錄）
    tools = {
        "vscode": {"dir": os.path.join(script_dir, "vscode"), "except": "zip" },
        "java": {"dir": os.path.join(script_dir, "java"), "except": "zip" },
        "python": {"dir": os.path.join(script_dir, "python"), "except": "zip" },
        "node": {"dir": os.path.join(script_dir, "node"), "except": "zip" },
        "git": {"dir": os.path.join(script_dir, "git"), "except": "7z.exe" },
        "zowe": {"dir": os.path.join(script_dir, "zowe-cli"), "except": "zip" },
    }
    
    print("=== Uninstall 開始 ===\n")
    
    # 逐一清理每個工具所在的資料夾，本動作將保留資料夾中所有 .zip 檔，其它內容皆清除
    for tool_name, tool_path in tools.items():
        print(f"清理 [{tool_name}] 目錄：{tool_path["dir"]}")
        cleanup_directory(tool_path["dir"], tool_path["except"])
    
    # 執行備份檔還原
    workspace_dir = os.path.join(script_dir, "workspace")
    restore_backup(workspace_dir)
    
    print("=== Uninstall 完成 ===")
    input("按 Enter 鍵結束程式：")


if __name__ == "__main__":
    main()

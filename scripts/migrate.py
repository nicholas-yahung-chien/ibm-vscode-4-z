#!/usr/bin/env python3
"""
IBM VSCode for Z Development Environment Migration Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 1.0.1
日期: 2026/01/12

說明:
1. 讀取 install_info.json 取得舊的安裝路徑資訊。
2. 偵測目前的工作區路徑。
3. 掃描並更新所有相關設定檔（VSCode 設定、code.cmd 等）中的路徑。
4. 更新 install_info.json 為新的路徑資訊。
"""

import os
import sys
import json
import argparse
import re
import glob
import sqlite3
from pathlib import Path
from urllib.parse import quote

# 添加 scripts 目錄到 sys.path 以便導入 utils 和 configs
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from utils.path_utils import get_script_dir, escape_backslashes, compose_folder_path
from utils.file_utils import replace_in_file

def main():
    print("開始執行遷移腳本...\n")
    
    # 1. 決定工作區路徑
    parser = argparse.ArgumentParser(description="Migrate VSCode4z environment paths.")
    parser.add_argument("--workspace", type=str, help="指定工作區目錄，預設為腳本檔所在路徑的上層。")
    args = parser.parse_args()
    
    if args.workspace:
        workspace = Path(args.workspace).resolve()
    else:
        workspace = Path(get_script_dir()).parent.resolve()
    
    print(f"目前工作區路徑: {workspace}")

    # 2. 讀取 install_info.json
    info_path = os.path.join(workspace, "install_info.json")
    if not os.path.exists(info_path):
        print(f"錯誤：找不到安裝資訊檔 {info_path}。無法執行遷移。")
        sys.exit(1)
        
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            old_info = json.load(f)
    except Exception as e:
        print(f"錯誤：讀取安裝資訊檔失敗：{e}")
        sys.exit(1)
        
    old_workspace = old_info.get("workspace")
    old_qbsworkspace = old_info.get("qbsworkspace")
    old_workspaceuri = old_info.get("workspaceuri")
    vscode_dirname = old_info.get("vscode_dirname")

    if not all([old_workspace, old_qbsworkspace, old_workspaceuri, vscode_dirname]):
        print("錯誤：install_info.json 內容不完整，缺少必要欄位。")
        sys.exit(1)
        
    print(f"舊工作區路徑: {old_workspace}")
    
    # 3. 計算新路徑資訊
    new_workspace_str = str(workspace)
    
    if old_workspace == new_workspace_str:
        print("新舊路徑相同，無須遷移。")
        return

    # new_qbsworkspace 代表「JSON 檔中的字面值路徑」（雙反斜線，例如 C:\\Users）
    # replace_in_file 會以純文字寫入 replacement，因此不需要為 re.sub replacement 規則做額外跳脫
    new_qbsworkspace = escape_backslashes(new_workspace_str)
    
    # 計算 URI
    raw_workspace_uri = workspace.as_uri()
    # 將除了開頭 file:// 以外的部份進行 uri escape
    # 保留 Path.as_uri() 既有的 percent-encoding（%E4...），避免雙重 escape 變成 %25E4...
    new_workspaceuri = "file://" + quote(raw_workspace_uri[7:], safe="/%")
    
    vscode_dir = compose_folder_path(workspace, vscode_dirname)
    print(f"VSCode 目錄: {vscode_dir}")
    
    # 4. 執行取代作業
    print("\n開始更新設定檔...")
    
    # 準備取代的參數
    # 注意：replace_in_file 內部用 regex 做「搜尋」，但 replacement 以純文字寫入，不會再解析 \u/\1 等序列
    
    # URI 取代 (最精確，優先執行)
    # URI 通常不含反斜線，直接使用
    
    # JSON 路徑取代 (雙反斜線 C:\\Foo)
    # 舊版 install_info.json 可能存的是「四反斜線」(C:\\\\Foo)；新版則存「雙反斜線」(C:\\Foo)
    # 目標檔案內容通常為「雙反斜線」(C:\\Foo)
    if "\\\\\\\\" in old_qbsworkspace:
        # 4 -> 2
        old_json_path_val = old_qbsworkspace.replace("\\\\\\\\", "\\\\")
    else:
        # already 2
        old_json_path_val = old_qbsworkspace
    
    # Raw 路徑取代 (單反斜線 C:\Foo)，用於 code.cmd
    new_workspace_raw = new_workspace_str

    # (a) settings.json
    settings_path = os.path.join(vscode_dir, "data", "user-data", "User", "settings.json")
    if os.path.exists(settings_path):
        # 取代 URI
        replace_in_file(settings_path, "(?i)" + re.escape(old_workspaceuri), new_workspaceuri)
        # 取代 JSON 路徑 (包含 Java Home 等設定)
        replace_in_file(settings_path, "(?i)" + re.escape(old_json_path_val), new_qbsworkspace)
    
    # (b) languagepacks.json
    lp_path = os.path.join(vscode_dir, "data", "user-data", "languagepacks.json")
    if os.path.exists(lp_path):
         replace_in_file(lp_path, "(?i)" + re.escape(old_json_path_val), new_qbsworkspace)

    # (c) storage.json
    storage_path = os.path.join(vscode_dir, "data", "user-data", "User", "globalStorage", "storage.json")
    if os.path.exists(storage_path):
        replace_in_file(storage_path, "(?i)" + re.escape(old_workspaceuri), new_workspaceuri)
        replace_in_file(storage_path, "(?i)" + re.escape(old_json_path_val), new_qbsworkspace)

    # (d) workspace.json (多個)
    ws_storage_dir = os.path.join(vscode_dir, "data", "user-data", "User", "workspaceStorage")
    if os.path.exists(ws_storage_dir):
        workspace_files = glob.glob(os.path.join(ws_storage_dir, "*", "workspace.json"))
        for ws_file in workspace_files:
            replace_in_file(ws_file, "(?i)" + re.escape(old_workspaceuri), new_workspaceuri)

    # (e) state.vscdb (SQLite)
    state_db_path = os.path.join(vscode_dir, "data", "user-data", "User", "globalStorage", "state.vscdb")
    if os.path.exists(state_db_path):
        print(f"更新資料庫: {state_db_path}")
        try:
            conn = sqlite3.connect(state_db_path)
            cursor = conn.cursor()
            sql_query = "UPDATE ItemTable SET value = REPLACE(value, ?, ?) WHERE key LIKE '%recentlyOpenedPathsList%';"
            cursor.execute(sql_query, (old_workspaceuri, new_workspaceuri))
            conn.commit()
            print(f"state.vscdb 更新完成 (受影響列數: {cursor.rowcount})")
            conn.close()
        except Exception as e:
            print(f"state.vscdb 更新失敗: {e}")
            
    # (f) code.cmd (批次檔，使用 Raw 路徑)
    code_cmd_path = os.path.join(vscode_dir, "bin", "code.cmd")
    if os.path.exists(code_cmd_path):
        # 取代 Raw 路徑
        replace_in_file(code_cmd_path, "(?i)" + re.escape(old_workspace), new_workspace_raw)

    # 5. 更新 install_info.json
    print("\n更新 install_info.json...")
    new_info = {
        "workspace": new_workspace_str,
        "qbsworkspace": new_qbsworkspace,
        "workspaceuri": new_workspaceuri,
        "vscode_dirname": vscode_dirname
    }
    try:
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(new_info, f, indent=4, ensure_ascii=False)
        print("install_info.json 更新完成。")
    except Exception as e:
        print(f"更新 install_info.json 失敗: {e}")
        
    print("\n遷移作業完成。")

if __name__ == "__main__":
    main()


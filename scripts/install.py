#!/usr/bin/env python3
"""
IBM VSCode for Z Development Environment Setup Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 2.7.6
日期: 2026/01/12

說明:
1. 於各指定資料夾中尋找符合條件的工具檔案（Zip/7z/Exe 等）。
2. 解壓與配置工具包至指定目錄。
3. 安裝 Node.js 相關套件（使用離線快取）。
4. 遷移與修正 VSCode 設定檔中的路徑參數。
5. 建立 VSCode 的啟動捷徑與環境變數設定。
6. 安裝外部下載的 VSCode 擴充功能 (.vsix)。
7. 安裝預設的 VSCode 擴充功能 (Bootstrap)。
8. 設定擴充功能的 JSON Schema 路徑。
9. 紀錄本次安裝的路徑資訊至 install_info.json。
10. 安裝 fonts 目錄下的字型檔案至系統（使用者層級）。
11. 清理安裝過程產生的暫存目錄與檔案。

更新記錄:
- v2.7.6: 更新版本/日期資訊，並同步文件說明
- v2.7.1: 重新編排安裝步驟順序，新增安裝資訊紀錄功能，移除過時流程
- v2.7.0: 新增系統編碼設定功能，允許使用者自訂檔案編碼
- v2.6.0: 優化檔案鎖定檢測和進程終止功能，改善安裝和卸載流程
- v2.5.0: 新增 VSCode 擴充功能安裝後的進程清理機制，避免檔案被鎖定
- v2.4.11: 優化 Zowe-Cli 安裝流程，改善 npm 命令執行
- v2.3.0: 重構檔案處理邏輯，提升壓縮和檔案管理效能
- v2.2.1: 初始版本，提供完整的 VSCode4z 開發環境安裝功能
"""

import os
import argparse
import re
import json
import subprocess
import sys
import sqlite3
import shutil
import ctypes
from urllib.parse import quote
from pathlib import Path
from utils.path_utils import compose_folder_path, escape_backslashes, get_script_dir
from utils.file_utils import safe_rmtree, replace_in_file

# 若要建立 Windows 快捷方式，需要 pywin32 模組
try:
    import win32com.client
except ImportError:
    win32com = None

# 導入我們的互動工具模組
from utils.message_utils import (
    pause_if_needed,
    confirm_step,
    run_with_spinner
)
# 導入我們的路徑工具模組
from utils.path_utils import (
    get_latest_file,
    get_all_files_reversed_sorted,
    find_real_directory,
    find_home_path,
    find_target_file_path,
    find_target_file_path_by_pattern
)
# 導入我們的檔案工具模組
from utils.file_utils import (
    extract_zip_with_spinner,
    copy_contents_to_with_spinner,
    move_contents_up
)
# 導入我們的設定檔工具模組
from configs import (
    load_tools_config,
    load_pip_config,
    load_init_config,
    load_extensions_config,
    load_install_config,
    load_npm_config
)

# -------------------------------
#  功能函式
# -------------------------------
def extract_major_version(version_text):
    """
    從 version_text 中擷取版本號序列，並僅回傳第一組（major 部分）。
    例如：'javaJDK11.0.18' 會回傳 '11'。
    """
    match = re.search(r'\d+(?:\.\d+)*', version_text)
    if match:
        full_version = match.group()
        return full_version.split(".")[0]
    return None

def vscode_cmd_insertion(file_path, insertions):
    """在 VSCode 的批次檔中讀取 'setlocal' 行後插入額外環境設定語法。"""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if not inserted and line.strip().lower() == "setlocal":
            new_lines.extend(insertions)
            inserted = True
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

# -------------------------------
# 以下定義各階段流程（利用 decorator 包裝）
# -------------------------------

@confirm_step("【步驟 1】檢查工具包：請確認所有必要工具已經下載")
def phase1_check_tools(workspace, auto_continue=False):
    print("檢查工具包...\n")
    
    # 載入 tools.yml 設定檔
    tools = load_tools_config()
    
    # 取得工具包檔案
    tool_files = {}
    for tool, info in tools.items():
        tool_file = get_latest_file(
            compose_folder_path(workspace, info["dir"]),
            f"{info['pattern']}.{info['type']}"
        )
        tool_files[tool] = tool_file
        print(f"{tool}：{tool_file}")
        if tool_file == "":
            print(f"{tool} 不存在，請確認後再執行。")
            sys.exit(1)
    print("檢查工具包完成。\n")
    return tools, tool_files

@confirm_step("【步驟 2】解壓工具包：請確認解壓前準備")
def phase2_extract_packages(tools, tool_files, workspace, auto_continue=False):
    for tool, info in tools.items():
        # 解壓縮 zip 類型工具包
        if info["zip_type"] == "zip":
            dest_dir = compose_folder_path(workspace, info["dir"])
            zip_path = os.path.join(dest_dir, tool_files[tool])
            extract_zip_with_spinner(zip_path, dest_dir)
            move_contents_up(dest_dir, find_real_directory(dest_dir, f".{info['type']}"))
            # 解壓完成後刪除原始壓縮檔
            try:
                os.remove(zip_path)
                print(f"已刪除原始檔案：{os.path.basename(zip_path)}")
            except OSError as e:
                print(f"刪除原始檔案失敗：{e}")

        # 解壓縮 7z 類型自解工具包
        if info["zip_type"] == "7z":
            dest_dir = compose_folder_path(workspace, info["dir"])
            exe_path = os.path.join(dest_dir, tool_files[tool])
            try:
                run_with_spinner(
                    [exe_path, "-y", f"-o{dest_dir}"],
                    f"解壓縮 {tool}",
                    cwd=dest_dir
                )
                # 解壓完成後刪除原始安裝檔
                try:
                    os.remove(exe_path)
                    print(f"已刪除原始檔案：{os.path.basename(exe_path)}")
                except OSError as e:
                    print(f"刪除原始檔案失敗：{e}")
            except subprocess.CalledProcessError as e:
                print(f"解壓縮 {tool} 失敗，錯誤代碼：{e.returncode}")
                if e.stderr:
                    print(f"錯誤訊息：{e.stderr}")

        # 解壓縮 exe 類型自解工具包
        if info["zip_type"] == "exe":
            dest_dir = compose_folder_path(workspace, info["dir"])
            exe_path = os.path.join(dest_dir, tool_files[tool])
            try:
                run_with_spinner(
                    [exe_path, "/S", "-y", f"-o{dest_dir}"],
                    f"解壓縮 {tool}",
                    cwd=dest_dir
                )
                # 解壓完成後刪除原始安裝檔
                try:
                    os.remove(exe_path)
                    print(f"已刪除原始檔案：{os.path.basename(exe_path)}")
                except OSError as e:
                    print(f"刪除原始檔案失敗：{e}")
            except subprocess.CalledProcessError as e:
                print(f"解壓縮 {tool} 失敗，錯誤代碼：{e.returncode}")
                if e.stderr:
                    print(f"錯誤訊息：{e.stderr}")
    
        # 處理 nonzip 類型工具包（僅重命名檔案）
        if info["zip_type"] == "nonzip":
            dest_dir = compose_folder_path(workspace, info["dir"])
            source_file = os.path.join(dest_dir, tool_files[tool])
            
            # 檢查來源檔案是否存在
            if not os.path.exists(source_file):
                print(f"警告：{tool} 的來源檔案 {source_file} 不存在，跳過重命名。")
                continue
            
            # 根據 home_path_of 進行檔案重命名
            if "home_path_of" in info and info["home_path_of"]:
                for target_name in info["home_path_of"]:
                    target_path = os.path.join(dest_dir, target_name)
                    try:
                        if os.path.exists(target_path):
                            os.remove(target_path)
                            print(f"已刪除既有的 {target_name}")
                        
                        os.rename(source_file, target_path)
                        print(f"已將 {os.path.basename(source_file)} 重命名為 {target_name}")
                    except OSError as e:
                        print(f"重命名 {tool} 檔案失敗：{e}")
            else:
                print(f"警告：{tool} 未設定 home_path_of，跳過重命名。")
    
    # 取得 JAVA_HOME 相關路徑（取倒序排序第一個項目）
    java_versions = sorted([key for key in tools if key.startswith("java")], reverse=True)
    java_home_path = compose_folder_path(workspace, tools[java_versions[0]]["dir"])
    
    print("解壓工具包完成。\n")
    return java_home_path, java_versions

@confirm_step("【步驟 3】安裝 Node.js 套件（離線快取）")
def phase3_install_nodejs_modules(tools, workspace, auto_continue=False):
    # 載入 npm.yml 設定檔
    npm = load_npm_config()

    node_home = compose_folder_path(workspace, tools["nodejs"]["dir"])
    npm_cmd = os.path.join(node_home, "npm.cmd")
    npm_cache_dir = os.path.join(workspace, "npm-cache")

    # 針對 npm.yml 中列出的所有套件，使用離線快取安裝（需事先由 download.py 填充快取）
    for scope, pkgs in npm.items():
        for entry in pkgs:
            for name, version in entry.items():
                pkg_spec = f"@{scope}/{name}@{version}" if scope != "global" else f"{name}@{version}"
                print(f"準備離線安裝 {pkg_spec}...")
                try:
                    run_with_spinner(
                        [
                            npm_cmd,
                            "install",
                            "-g",
                            "--offline",
                            "--no-fund",
                            "--no-audit",
                            "--no-optional",
                            "--omit=optional",
                            f"--cache={npm_cache_dir}",
                            pkg_spec
                        ],
                        f"安裝 {pkg_spec}",
                        cwd=node_home,
                        timeout=300
                    )
                    print(f"安裝 {pkg_spec} 完成。")
                except subprocess.CalledProcessError as e:
                    print(f"安裝 {pkg_spec} 失敗，錯誤代碼：{e.returncode}")
                    if e.stderr:
                        print(f"錯誤訊息：{e.stderr}")
    print("離線安裝 Node.js 套件完成。\n")

@confirm_step("【步驟 4】路徑設定遷移：請確認設定檔修改")
def phase4_path_migration(tools, java_home_path, workspace, auto_continue=False, install_config=None):
    # 產生轉義字串與 URI
    # 這裡要寫入 settings.json 等 JSON 檔案中的「字面值」路徑（需雙反斜線）。
    # replace_in_file 會以純文字寫入 replacement（不再經過 re.sub replacement 跳脫解析），
    # 因此不需要也不應該做「給 re.sub 用」的額外跳脫。
    qbsworkspace = escape_backslashes(f"{workspace}")
    raw_workspace_uri = Path(workspace).as_uri()
    # 將除了開頭 file:// 以外的部份進行 uri escape (例如將 : escape 為 %3a)
    # 注意：Path.as_uri() 已經會對非 ASCII 字元做 percent-encoding（例如 %E4%B8%AD）。
    # 這裡我們只需要把 Windows 磁碟機的 ':' 這類字元補上 escape，並且要保留既有的 '%'，
    # 避免形成 %25E4... 的「雙重 escape」而導致後續比對/替換失敗。
    workspaceuri = "file://" + quote(raw_workspace_uri[7:], safe="/%")
    
    # 複製 VSCode 設定結構
    source_from = os.path.join(workspace, "data")
    copy_to = os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "data")
    copy_contents_to_with_spinner(source_from, copy_to)
    
    # 修改 VSCode 設定檔內容
    vscode_settings_path = os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "data", "user-data", "User", "settings.json")
    replace_in_file(vscode_settings_path, r"_WORKSPACE_", qbsworkspace)
    replace_in_file(vscode_settings_path, r"_WORKSPACEURI_", workspaceuri)
    replace_in_file(vscode_settings_path, r"_JAVAHOME_", escape_backslashes(java_home_path))

    # 修改 languagepacks.json 設定檔內容
    languagepacks_path = os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "data", "user-data", "languagepacks.json")
    replace_in_file(languagepacks_path, r"_WORKSPACE_", qbsworkspace)

    # 修改 storage.json 設定檔內容
    storage_json_path = os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "data", "user-data", "User", "globalStorage", "storage.json")
    replace_in_file(storage_json_path, r"_WORKSPACEURI_", workspaceuri)
    replace_in_file(storage_json_path, r"_WORKSPACE_", qbsworkspace)

    # 修改 workspace.json 設定檔內容
    workspace_json_path = os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "data", "user-data", "User", "workspaceStorage", "ab8bd8309b497ec75a1a2fb86885ba5f", "workspace.json")
    replace_in_file(workspace_json_path, r"_WORKSPACEURI_", workspaceuri)

    # 修改 state.vscdb 資料庫內容
    state_db_path = os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "data", "user-data", "User", "globalStorage", "state.vscdb")
    if os.path.exists(state_db_path):
        print(f"更新 state.vscdb: {state_db_path}")
        try:
            conn = sqlite3.connect(state_db_path)
            cursor = conn.cursor()
            
            # 執行 SQL 更新指令
            sql_query = "UPDATE ItemTable SET value = REPLACE(value, '_WORKSPACEURI_', ?) WHERE key LIKE '%recentlyOpenedPathsList%';"
            cursor.execute(sql_query, (workspaceuri,))
            
            conn.commit()
            print(f"state.vscdb 更新完成 (受影響列數: {cursor.rowcount})")
            conn.close()
        except sqlite3.Error as e:
            print(f"state.vscdb 更新失敗: {e}")
    else:
        print(f"警告：找不到 state.vscdb 檔案 ({state_db_path})，跳過資料庫更新。")

    # 組成 java runtime 清單（僅取 major 版本）
    java_versions = sorted([key for key in tools if key.startswith("java")], reverse=True)
    java_runtimes = []
    for key in java_versions:
        major_version = extract_major_version(key)
        java_runtimes.append({
            "name": f"JavaSE-{major_version}",
            "path": escape_backslashes(compose_folder_path(workspace, tools[key]["dir"]))
        })
    runtime_json = ",\n        ".join(json.dumps(entry) for entry in java_runtimes)
    replace_in_file(vscode_settings_path, r"\"_JAVA_RUNTIMES_\"", runtime_json)
    
    # 設定系統編碼
    print("設定系統編碼...")
    default_encoding = "CP937"
    
    # 優先從設定檔讀取系統編碼
    if install_config and install_config.get("system_encoding"):
        system_encoding = install_config["system_encoding"]
        print(f"從設定檔讀取編碼：{system_encoding}")
    elif auto_continue:
        system_encoding = default_encoding
        print(f"使用預設編碼：{system_encoding}")
    else:
        system_encoding = input(f"請輸入系統編碼 (預設 {default_encoding}): ").strip()
        if not system_encoding:
            system_encoding = default_encoding
            print(f"使用預設編碼：{system_encoding}")
    
    # 替換設定檔中的編碼變數
    replace_in_file(vscode_settings_path, r"_DEFAULT_ENCODING_", system_encoding)
    
    print("路徑設定遷移完成。\n")
    return

@confirm_step("【步驟 5】建立 VSCode 快捷方式：請確認建立捷徑")
def phase5_create_shortcut(tools, java_home_path, workspace, auto_continue=False):        
    vscmd = os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "bin", "code.cmd")
    vscmd_home = os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "bin")
    vsc_home = compose_folder_path(workspace, tools["vscode"]["dir"])
    
    # 拼湊要插入於批次檔中的環境設定語法
    tool_home_paths = []
    for tool, info in tools.items():
        if info["add_home_path_to_env"]:
            for executable in info["home_path_of"]:
                if tool == "python":
                    home_path = find_home_path(os.path.join(compose_folder_path(workspace, info["dir"]), "venv", "Scripts"), executable)
                else:
                    home_path = find_home_path(compose_folder_path(workspace, info["dir"]), executable)
                if home_path:
                    tool_home_paths.append(home_path)
    insertions = [
        'powershell -Command "Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope CurrentUser -Force"\n',
        'set "PATH={};%PATH%"\n'.format(
            ";".join(tool_home_paths)
        ),
        'set "JAVA_HOME={}"\n'.format(java_home_path)
    ]
    vscode_cmd_insertion(vscmd, insertions)
    print("已插入臨時 PATH 與 JAVA_HOME 設定於 VSCode 啟動檔中。")

    print("快捷方式建立完成。\n")
    return

@confirm_step("【步驟 6】安裝下載的擴充功能包：請確認安裝從 OpenVSX 或 VSCode Marketplace 下載的擴充功能包")
def phase6_install_extensions(tools, workspace, auto_continue=False):
    # 載入 extensions.yml 設定檔
    extensions = load_extensions_config()
    for publisher, _ in extensions.items():
        group_folder = os.path.join(workspace, "extensions")
        all_group_extensions = get_all_files_reversed_sorted(group_folder, f"{publisher}*.vsix")
        for extension in all_group_extensions:
            print(f"準備安裝 {os.path.basename(extension)}...")
            try:
                run_with_spinner(
                    [os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "bin", "code.cmd"),
                        "--install-extension", extension],
                    f"安裝 {os.path.basename(extension)}",
                    cwd=os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "bin"),
                    timeout=300  # 5分鐘超時
                )
                print(f"安裝 {os.path.basename(extension)} 完成。")
                # 安裝完畢後強制結束 VSCode 相關進程
                for proc in ["Code.exe", "code.exe", "code.cmd"]:
                    subprocess.run(["taskkill", "/IM", proc, "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                print(f"安裝 {os.path.basename(extension)} 失敗，錯誤代碼：{e.returncode}")
                if e.stderr:
                    print(f"錯誤訊息：{e.stderr}")
    print("下載的擴充功能包安裝完成。\n")
    return

@confirm_step("【步驟 7】安裝預設擴充功能包：請確認移動 Bootstrap 目錄以安裝預先包裹的擴充功能包")
def phase7_install_extensions_by_move(tools, workspace, auto_continue=False):
    """
    通過將整個 bootstrap 目錄移動到 VSCode 目錄中來實現自動安裝預先包裹的擴充功能包。
    這些擴充功能包是預先包裹在安裝包中、無法透過 OpenVSX 或 VSCode Marketplace 下載得到的預設擴充功能包。
    這種方法讓 VSCode 在第一次啟動時自動安裝所有預設擴充功能包。
    """
    bootstrap_source = os.path.join(workspace, "bootstrap")
    bootstrap_dest = os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "bootstrap")
    
    # 檢查來源目錄是否存在
    if not os.path.exists(bootstrap_source):
        print(f"警告：Bootstrap 目錄 {bootstrap_source} 不存在，跳過移動操作。")
        return
    
    # 檢查目標目錄是否已存在
    if os.path.exists(bootstrap_dest):
        print(f"目標目錄 {bootstrap_dest} 已存在，先刪除既有目錄...")
        try:
            safe_rmtree(bootstrap_dest)
            print("已刪除既有的 Bootstrap 目錄。")
        except Exception as e:
            print(f"刪除既有目錄失敗：{e}")
            return
    
    # 移動 Bootstrap 目錄
    try:
        print(f"正在移動 Bootstrap 目錄...")
        print(f"來源：{bootstrap_source}")
        print(f"目標：{bootstrap_dest}")
        
        # 確保目標目錄的父目錄存在
        os.makedirs(os.path.dirname(bootstrap_dest), exist_ok=True)
        
        # 移動目錄
        os.rename(bootstrap_source, bootstrap_dest)
        print("Bootstrap 目錄移動完成。")
        print("VSCode 將在第一次啟動時自動安裝所有預設擴充功能包。\n")
        
    except Exception as e:
        print(f"移動 Bootstrap 目錄失敗：{e}")
        return

@confirm_step("【步驟 8】設定 Schema 路徑：請確認設定擴充功能 Schema 路徑")
def phase8_set_schemas(tools, workspace, auto_continue=False):
    print("設定 Schema 路徑...\n")
    vscode_settings_path = os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "data", "user-data", "User", "settings.json")

    # 修改 Zapp 設定檔路徑
    zapp_schema_path = find_target_file_path_by_pattern(
        compose_folder_path(workspace, "vscode"), "zapp-schema*.json")
    if zapp_schema_path:
        raw_zapp_schema_uri = Path(zapp_schema_path).resolve().as_uri()
        zapp_schema_uri = "file://" + quote(raw_zapp_schema_uri[7:], safe="/%")
        replace_in_file(vscode_settings_path, r"_ZAPP_SCHEMA_URI_", zapp_schema_uri)
    else:
        print("找不到 zapp-schema-*.json，請確認後再執行。")
        sys.exit(1)
    
    # 修改 Zcodeformat 設定檔路徑
    zcodeformat_schema_path = find_target_file_path_by_pattern(
        compose_folder_path(workspace, "vscode"), "zcodeformat-schema*.json")
    if zcodeformat_schema_path:
        raw_zcodeformat_schema_uri = Path(zcodeformat_schema_path).resolve().as_uri()
        zcodeformat_schema_uri = "file://" + quote(raw_zcodeformat_schema_uri[7:], safe="/%")
        replace_in_file(vscode_settings_path, r"_ZCODE_FORMAT_SCHEMA_URI_", zcodeformat_schema_uri)
    else:
        print("找不到 zcodeformat-schema-*.json，請確認後再執行。")
        sys.exit(1)

    # 修改 Continue 設定檔路徑
    continue_config_schema_path = find_target_file_path_by_pattern(
        compose_folder_path(workspace, "workspace"), "config-yaml-schema*.json")
    if continue_config_schema_path:
        raw_continue_config_schema_uri = Path(continue_config_schema_path).resolve().as_uri()
        continue_config_schema_uri = "file://" + quote(raw_continue_config_schema_uri[7:], safe="/%")
        replace_in_file(vscode_settings_path, r"_CONTINUE_CONFIG_SCHEMA_URI_", continue_config_schema_uri)
    else:
        print("找不到 config-yaml-schema-*.json，請確認後再執行。")
        sys.exit(1)
        
    print("Schema 路徑設定完成。\n")
    return

@confirm_step("【步驟 9】紀錄安裝資訊：請確認儲存路徑設定檔")
def phase9_save_install_info(tools, workspace, auto_continue=False):
    print("紀錄安裝資訊...\n")
    
    # 產生轉義字串與 URI
    # qbsworkspace 代表「JSON 檔中的字面值路徑」（雙反斜線）
    qbsworkspace = escape_backslashes(f"{workspace}")
    raw_workspace_uri = Path(workspace).as_uri()
    # 將除了開頭 file:// 以外的部份進行 uri escape (例如將 : escape 為 %3a)
    workspaceuri = "file://" + quote(raw_workspace_uri[7:], safe="/%")
    
    info_data = {
        "workspace": str(workspace),
        "qbsworkspace": qbsworkspace,
        "workspaceuri": workspaceuri,
        "vscode_dirname": tools["vscode"]["dir"]
    }
    
    info_path = os.path.join(workspace, "install_info.json")
    try:
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info_data, f, indent=4, ensure_ascii=False)
        print(f"已建立安裝資訊檔：{info_path}")
    except Exception as e:
        print(f"建立安裝資訊檔失敗：{e}")
        
    print("紀錄安裝資訊完成。\n")
    return

@confirm_step("【步驟 10】安裝字型：請確認安裝 fonts 目錄下的字型檔案")
def phase10_install_fonts(workspace, auto_continue=False):
    """
    安裝工作區 fonts 目錄下的字型檔案至 Windows 使用者層級字型目錄。

    - 目標目錄：%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts
    - 登錄位置：HKCU\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts

    說明：
    - 使用者層級安裝通常不需要系統管理員權限，較適合離線/企業環境的一鍵安裝流程。
    - 安裝後會嘗試發送 WM_FONTCHANGE，讓系統/應用程式更快感知字型更新。
    """
    if sys.platform != "win32":
        print("目前僅支援 Windows 平台的字型安裝，跳過。\n")
        return

    fonts_src_dir = os.path.join(workspace, "fonts")
    if not os.path.exists(fonts_src_dir):
        print(f"找不到 fonts 目錄：{fonts_src_dir}，跳過字型安裝。\n")
        return

    font_files = []
    for name in os.listdir(fonts_src_dir):
        if name.lower().endswith((".ttf", ".otf", ".ttc", ".otc")):
            font_files.append(os.path.join(fonts_src_dir, name))

    if not font_files:
        print(f"fonts 目錄中未找到可安裝的字型檔案：{fonts_src_dir}，跳過。\n")
        return

    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if not local_appdata:
        print("無法取得 LOCALAPPDATA，跳過字型安裝。\n")
        return

    try:
        import winreg
    except ImportError:
        print("缺少 winreg 模組（非 Windows Python 環境？），跳過字型安裝。\n")
        return

    # 優先嘗試系統層級安裝（需要系統管理員權限）；否則改用使用者層級安裝
    try:
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        is_admin = False

    reg_path = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
    if is_admin:
        target_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        reg_root = winreg.HKEY_LOCAL_MACHINE
        print("偵測到系統管理員權限：將以系統層級安裝字型。")
    else:
        target_dir = os.path.join(local_appdata, "Microsoft", "Windows", "Fonts")
        reg_root = winreg.HKEY_CURRENT_USER
        print("未偵測到系統管理員權限：將以使用者層級安裝字型。")

    os.makedirs(target_dir, exist_ok=True)
    installed_count = 0
    skipped_count = 0

    try:
        with winreg.OpenKey(reg_root, reg_path, 0, winreg.KEY_SET_VALUE) as key:
            for src in font_files:
                filename = os.path.basename(src)
                stem = Path(filename).stem
                ext = Path(filename).suffix.lower()

                dest = os.path.join(target_dir, filename)

                # 若目的檔已存在且大小一致，視為已安裝
                if os.path.exists(dest):
                    try:
                        if os.path.getsize(dest) == os.path.getsize(src):
                            skipped_count += 1
                        else:
                            shutil.copy2(src, dest)
                            installed_count += 1
                    except OSError:
                        # 任何檔案層級錯誤都先略過，不中斷整體流程
                        print(f"複製字型失敗（跳過）：{filename}")
                        continue
                else:
                    try:
                        shutil.copy2(src, dest)
                        installed_count += 1
                    except OSError:
                        print(f"複製字型失敗（跳過）：{filename}")
                        continue

                # 設定登錄：值資料使用完整路徑（使用者層級字型安裝常見作法）
                if ext in (".otf", ".otc"):
                    value_name = f"{stem} (OpenType)"
                else:
                    value_name = f"{stem} (TrueType)"

                try:
                    # 系統層級安裝：登錄值通常使用檔名；使用者層級安裝：使用完整路徑較常見
                    reg_value = filename if is_admin else dest
                    winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, reg_value)
                except OSError:
                    print(f"寫入登錄失敗（跳過）：{value_name}")
                    continue
    except OSError as e:
        print(f"開啟/寫入字型登錄失敗：{e}\n")
        return

    # 嘗試通知系統字型已更新（不保證所有環境都允許/需要）
    try:
        HWND_BROADCAST = 0xFFFF
        WM_FONTCHANGE = 0x001D
        SMTO_ABORTIFHUNG = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0, SMTO_ABORTIFHUNG, 1000, None)
    except Exception:
        pass

    print(f"字型安裝完成：新增/更新 {installed_count} 個，略過 {skipped_count} 個。\n")
    return

@confirm_step("【步驟 11】清理安裝檔：請確認刪除安裝暫存目錄")
def phase11_cleanup(workspace, auto_continue=False):
    print("清理安裝暫存目錄...\n")
    
    # 定義要清理的目錄清單
    cleanup_targets = ["bootstrap", "data", "extensions", "npm-cache", "scripts"]
    
    for target in cleanup_targets:
        target_path = os.path.join(workspace, target)
        if os.path.exists(target_path):
            try:
                safe_rmtree(target_path)
                print(f"已刪除目錄：{target}")
            except Exception as e:
                print(f"刪除目錄 {target} 失敗：{e}")
        else:
            print(f"目錄 {target} 已不存在，跳過。")
            
    print("清理動作完成。\n")
    return

# -------------------------------
# 主流程
# -------------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(description="Install script with optional auto-confirmation.")
    parser.add_argument("-y", "--yes", dest="yes", action="store_true", help="自動執行所有步驟 (預設值)")
    parser.add_argument("-i", "--interactive", dest="yes", action="store_false", help="手動確認每個步驟")
    parser.set_defaults(yes=True)
    parser.add_argument("--workspace", type=str, help="指定工作區目錄，預設為腳本檔所在路徑。")
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    # 檢查是否存在 install.yml 設定檔
    install_config = load_install_config()
    if install_config:
        print("發現 install.yml 設定檔，將使用設定檔中的參數。")
        # 從設定檔中讀取參數，覆蓋命令列參數
        if install_config.get("auto_continue", False):
            args.yes = True
        if install_config.get("workspace", ""):
            args.workspace = install_config["workspace"]
    else:
        print("未發現 install.yml 設定檔，將使用命令列參數或預設值。")
    
    # 若使用者有指定 --workspace 則使用該目錄，否則預設為 script_dir 的上層
    workspace = Path(args.workspace).resolve() if args.workspace else Path(get_script_dir()).parent.resolve()
    os.chdir(workspace)
    print("目前工作目錄設定為：", workspace)
    
    # 執行各階段流程
    tools, tool_files = phase1_check_tools(workspace, auto_continue=args.yes)
    java_home_path, _ = phase2_extract_packages(tools, tool_files, workspace, auto_continue=args.yes)
    phase3_install_nodejs_modules(tools, workspace, auto_continue=args.yes)
    phase4_path_migration(tools, java_home_path, workspace, auto_continue=args.yes, install_config=install_config)
    
    # 建立 VSCode 快捷方式（會調整 code.cmd 環境設定）
    phase5_create_shortcut(tools, java_home_path, workspace, auto_continue=args.yes)

    # 擴充功能包安裝：執行兩種安裝方式（需在 code.cmd 完成調整後）
    # 方法1：使用 code.cmd 命令逐一安裝從 OpenVSX 或 VSCode Marketplace 下載的擴充功能包
    phase6_install_extensions(tools, workspace, auto_continue=args.yes)
    # 方法2：移動 bootstrap 目錄到 VSCode 目錄（安裝預先包裹在安裝包中的預設擴充功能包）
    phase7_install_extensions_by_move(tools, workspace, auto_continue=args.yes)
    
    # 設定 Schema 路徑 (需在擴充功能安裝後執行)
    phase8_set_schemas(tools, workspace, auto_continue=args.yes)

    # 紀錄安裝資訊
    phase9_save_install_info(tools, workspace, auto_continue=args.yes)

    # 安裝字型（fonts 目錄）
    phase10_install_fonts(workspace, auto_continue=args.yes)
    
    # 清理安裝暫存目錄
    phase11_cleanup(workspace, auto_continue=args.yes)
    
    print("腳本執行結束。")
    
    # 檢查是否需要在結束時暫停
    pause_at_end = True
    if install_config and "advanced" in install_config:
        pause_at_end = install_config["advanced"].get("pause_at_end", True)
    
    pause_if_needed("按下 Enter 鍵後關閉程式", auto_continue=not pause_at_end or args.yes)

if __name__ == "__main__":
    main()
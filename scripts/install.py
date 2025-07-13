#!/usr/bin/env python3
"""
IBM VSCode for Z Development Environment Setup Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 2.6.0
日期: 2025/01/13

說明:
1. 於各指定資料夾中尋找符合條件的 Zip 檔（依修改時間排序取最新檔案）。
2. 驗證工具（VSCode、Jdk21 等）的檔案是否存在，若不存在則顯示錯誤後結束程式。
3. 執行解壓動作，各工具的 Zip 檔解壓到相應目錄中；若產生嵌套資料夾則將其中內容搬移上層後刪除該空目錄。
4. 安裝 Zowe-Cli Core 模組
5. 安裝 Zowe-Cli Plugin 模組
6. 建立 python venv 虛擬環境
7. 安裝 python 套件包
8. 根據目前工作區（即腳本所在路徑）修改設定檔中的路徑參數（含轉義與 URI 部分）。
9. 安裝 VSCode 擴充功能包（包含檔案鎖定處理機制）
10. 建立 VSCode 的 Windows 快捷方式（若無 win32com 則略過）。

更新記錄:
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
from pathlib import Path
from urllib.parse import quote
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
    load_extensions_config
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
        tool_file = get_latest_file(compose_folder_path(workspace, info["dir"]), f"{info["pattern"]}.{info["type"]}")
        tool_files[tool] = tool_file
        print(f"{tool}：{tool_file}")
        if tool_file == "":
            print(f"{tool} 不存在，請確認後再執行。")
            sys.exit(1)
    print("檢查工具包完成。\n")
    return tools, tool_files

@confirm_step("【步驟 2】解壓工具包：請確認解壓前準備")
def phase2_extract_packages(tools, tool_files, workspace, auto_continue=False):
    # 解壓縮 zip 類型工具包
    for tool, info in tools.items():
        if info["type"] == "zip":
            dest_dir = compose_folder_path(workspace, info["dir"])
            zip_path = os.path.join(dest_dir, tool_files[tool])
            extract_zip_with_spinner(zip_path, dest_dir)
            move_contents_up(dest_dir, find_real_directory(dest_dir, f".{info['type']}"))
    
    # 解壓縮 exe 類型自解工具包
    for tool, info in tools.items():
        if info["type"] == "exe":
            dest_dir = compose_folder_path(workspace, info["dir"])
            exe_path = os.path.join(dest_dir, tool_files[tool])
            try:
                run_with_spinner(
                    [exe_path, "/S", "-y", f"-o{dest_dir}"],
                    f"解壓縮 {tool}",
                    cwd=dest_dir
                )
            except subprocess.CalledProcessError as e:
                print(f"解壓縮 {tool} 失敗，錯誤代碼：{e.returncode}")
                if e.stderr:
                    print(f"錯誤訊息：{e.stderr}")
    
    # 取得 JAVA_HOME 相關路徑（取倒序排序第一個項目）
    java_versions = sorted([key for key in tools if key.startswith("java")], reverse=True)
    java_home_path = compose_folder_path(workspace, tools[java_versions[0]]["dir"])
    
    print("解壓工具包完成。\n")
    return java_home_path, java_versions

@confirm_step("【步驟 3】安裝 Zowe-Cli：請確認安裝前設定")
def phase3_install_zowe(tools, workspace, auto_continue=False):
    # 安裝 Zowe-Cli Core 模組
    zowe_core_modules = get_all_files_reversed_sorted(compose_folder_path(workspace, tools["zowe-core"]["dir"]), "*.tgz")
    for zowe_module in zowe_core_modules:
        print(f"準備安裝 {os.path.basename(zowe_module)}...")
        try:
            run_with_spinner(
                [os.path.join(compose_folder_path(workspace, tools["nodejs"]["dir"]), "npm.cmd"),
                    "install", "-g", "--prefer-offline", "--prefer-online",
                    "--no-fund", "--no-audit", os.path.join(compose_folder_path(workspace, tools["zowe-core"]["dir"]), zowe_module)],
                f"安裝 {os.path.basename(zowe_module)}",
                cwd=compose_folder_path(workspace, tools["nodejs"]["dir"]),
                timeout=600  # 10分鐘超時
            )
            print(f"安裝 {os.path.basename(zowe_module)} 完成。")
        except subprocess.CalledProcessError as e:
            print(f"安裝 {os.path.basename(zowe_module)} 失敗，錯誤代碼：{e.returncode}")
            if e.stderr:
                print(f"錯誤訊息：{e.stderr}")
    
    # 安裝 Zowe-Cli Plugin 模組
    zowe_plugin_modules = get_all_files_reversed_sorted(compose_folder_path(workspace, tools["zowe-plugin"]["dir"]), "*.tgz")
    for zowe_module in zowe_plugin_modules:
        print(f"準備安裝 {os.path.basename(zowe_module)}...")
        try:
            run_with_spinner(
                [os.path.join(compose_folder_path(workspace, tools["nodejs"]["dir"]), "npm.cmd"),
                    "install", "-g", "--prefer-offline", "--prefer-online",
                    "--no-fund", "--no-audit", os.path.join(compose_folder_path(workspace, tools["zowe-plugin"]["dir"]), zowe_module)],
                f"安裝 {os.path.basename(zowe_module)}",
                cwd=compose_folder_path(workspace, tools["nodejs"]["dir"]),
                timeout=600  # 10分鐘超時
            )
            print(f"安裝 {os.path.basename(zowe_module)} 完成。")
        except subprocess.CalledProcessError as e:
            print(f"安裝 {os.path.basename(zowe_module)} 失敗，錯誤代碼：{e.returncode}")
            if e.stderr:
                print(f"錯誤訊息：{e.stderr}")
    print("安裝 Zowe-Cli 完成。\n")

@confirm_step("【步驟 4】安裝 python 套件包")
def phase4_install_python_modules(tools, workspace, auto_continue=False):
    # 載入 pip.yml 設定檔
    pip = load_pip_config()
    # 建立 python venv 虛擬環境
    print("建立 python venv 虛擬環境...")
    python_home_path = find_home_path(compose_folder_path(workspace, tools["python"]["dir"]), "python.exe")
    python_venv_path = os.path.join(compose_folder_path(workspace, tools["python"]["dir"]), "venv")
    if python_home_path:
        try:
            run_with_spinner(
                [os.path.join(python_home_path, "python.exe"), "-m", "venv", python_venv_path],
                "建立 Python 虛擬環境",
            )
        except subprocess.CalledProcessError:
            print("建立虛擬環境失敗，請確認後再執行。")
            sys.exit(1)
    else:
        print("找不到 python.exe，請確認後再執行。")
        sys.exit(1)
    print("python venv 虛擬環境已建立於：", python_venv_path)
    
    # 安裝 python 套件包
    print("安裝 python 套件包...")
    venv_python_home_path = find_home_path(python_venv_path, "python.exe")
    if venv_python_home_path:
        for whl in pip["whls"]:
            print(f"準備安裝 {whl}...")
            try:
                run_with_spinner(
                    [os.path.join(venv_python_home_path, "python.exe"), "-m", "pip", "install",
                        "--no-input", "--disable-pip-version-check", "--no-cache-dir",
                        "--no-index", f"--find-links={os.path.join(workspace, 'pywhls')}", whl],
                    f"安裝 {whl}",
                    timeout=300  # 5分鐘超時
                )
                print(f"安裝 {whl} 完成。")
            except subprocess.TimeoutExpired:
                print(f"{whl} 安裝超時，但可能已成功安裝。")
            except subprocess.CalledProcessError as e:
                print(f"{whl} 安裝失敗，錯誤代碼：{e.returncode}")
                if e.stderr:
                    print(f"錯誤訊息：{e.stderr}")
                # 繼續安裝其他套件，不中斷整個流程
    else:
        print("找不到虛擬環境的 Python，請確認後再執行。")
        sys.exit(1)
    print("安裝 python 套件包完成。\n")

@confirm_step("【步驟 5】路徑設定遷移：請確認設定檔修改")
def phase5_path_migration(tools, java_home_path, workspace, auto_continue=False):
    # 產生轉義字串與 URI
    qbsworkspace = escape_backslashes(f"{workspace}", for_regex=True)
    workspaceuri = quote(Path(workspace).as_uri())
    
    # 複製 VSCode 設定結構
    source_from = os.path.join(workspace, "data")
    copy_to = os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "data")
    copy_contents_to_with_spinner(source_from, copy_to)
    
    # 修改 VSCode 設定檔內容
    vscode_settings_path = os.path.join(compose_folder_path(workspace, tools["vscode"]["dir"]), "data", "user-data", "User", "settings.json")
    replace_in_file(vscode_settings_path, r"_WORKSPACE_", qbsworkspace)
    replace_in_file(vscode_settings_path, r"_WORKSPACEURI_", workspaceuri)
    replace_in_file(vscode_settings_path, r"_JAVAHOME_", escape_backslashes(java_home_path, for_regex=True))
    
    # 修改 Python 虛擬環境路徑
    python_venv_path = os.path.join(compose_folder_path(workspace, tools["python"]["dir"]), "venv")
    python_venv_exec_path = os.path.join(compose_folder_path(workspace, tools["python"]["dir"]), "venv", "Scripts", "python.exe")
    replace_in_file(vscode_settings_path, r"_PYTHON_VENV_HOME_", escape_backslashes(python_venv_path, for_regex=True))
    replace_in_file(vscode_settings_path, r"_PYTHON_VENV_EXEC_", escape_backslashes(python_venv_exec_path, for_regex=True))
    
    # 修改 Zapp 設定檔路徑
    zapp_schema_path = find_target_file_path_by_pattern(
        compose_folder_path(workspace, "workspace"), "zapp-schema*.json")
    if zapp_schema_path:
        zapp_schema_uri = quote(Path(zapp_schema_path).resolve().as_uri())
        replace_in_file(vscode_settings_path, r"_ZAPP_SCHEMA_URI_", zapp_schema_uri)
    else:
        print("找不到 zapp-schema-*.json，請確認後再執行。")
        sys.exit(1)
    
    # 修改 Zcodeformat 設定檔路徑
    zcodeformat_schema_path = find_target_file_path_by_pattern(
        compose_folder_path(workspace, "workspace"), "zcodeformat-schema*.json")
    if zcodeformat_schema_path:
        zcodeformat_schema_uri = quote(Path(zcodeformat_schema_path).resolve().as_uri())
        replace_in_file(vscode_settings_path, r"_ZCODE_FORMAT_SCHEMA_URI_", zcodeformat_schema_uri)
    else:
        print("找不到 zcodeformat-schema-*.json，請確認後再執行。")
        sys.exit(1)
    
    # 組成 java runtime 清單（僅取 major 版本）
    java_versions = sorted([key for key in tools if key.startswith("java")], reverse=True)
    java_runtimes = []
    for key in java_versions:
        major_version = extract_major_version(key)
        java_runtimes.append({
            "name": f"JavaSE-{major_version}",
            "path": escape_backslashes(compose_folder_path(workspace, tools[key]["dir"]))
        })
    runtime_json = ",\n".join(json.dumps(entry) for entry in java_runtimes)
    replace_in_file(vscode_settings_path, r"\"_JAVA_RUNTIMES_\"", runtime_json)
    
    print("路徑設定遷移完成。\n")
    return

@confirm_step("【步驟 6】安裝 VSCode 擴充功能包：請確認安裝擴充功能包")
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
    print("擴充功能包安裝完成。\n")
    return

@confirm_step("【步驟 7】建立 VSCode 快捷方式：請確認建立捷徑")
def phase7_create_shortcut(tools, java_home_path, workspace, auto_continue=False):
    shortcut_path = os.path.join(workspace, "VSCode.lnk")
    if os.path.exists(shortcut_path):
        os.remove(shortcut_path)
        print("已刪除既有的 VSCode.lnk 快捷方式。")
        
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
    
    # 載入 init.yml 設定檔
    init_config = load_init_config()
    if win32com is not None:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(shortcut_path)
        shortcut.TargetPath = vscmd
        shortcut.Arguments = " ".join([os.path.join(workspace, "workspace", init_config["default"]["workspace"]), f"--locale={init_config['default']['locale']}"])
        shortcut.WorkingDirectory = vscmd_home
        shortcut.IconLocation = os.path.join(vsc_home, "Code.exe") + ",0"
        shortcut.Save()
        print("VSCode 快捷方式建立成功。")
    else:
        print("無 win32com 模組，無法建立 Windows 快捷方式。")
    print("快捷方式建立完成。\n")
    return

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
    
    # 執行各階段流程
    tools, tool_files = phase1_check_tools(workspace, auto_continue=args.yes)
    java_home_path, _ = phase2_extract_packages(tools, tool_files, workspace, auto_continue=args.yes)
    phase3_install_zowe(tools, workspace, auto_continue=args.yes)
    phase4_install_python_modules(tools, workspace, auto_continue=args.yes)
    phase5_path_migration(tools, java_home_path, workspace, auto_continue=args.yes)
    phase6_install_extensions(tools, workspace, auto_continue=args.yes)
    phase7_create_shortcut(tools, java_home_path, workspace, auto_continue=args.yes)
    
    print("腳本執行結束。")
    pause_if_needed("按下 Enter 鍵後關閉程式", auto_continue=args.yes)

if __name__ == "__main__":
    main()
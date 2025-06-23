#!/usr/bin/env python3
"""
程式名稱: install.py
開發單位: IBM Expert Labs
開發人員: nicholas.yahung.chien@ibm.com
日期: 2025/06/20
版本: 2.2.1

說明:
1. 於各指定資料夾中尋找符合條件的 Zip 檔（依修改時間排序取最新檔案）。
2. 驗證工具（VSCode、Jdk21 等）的檔案是否存在，若不存在則顯示錯誤後結束程式。
3. 執行解壓動作，各工具的 Zip 檔解壓到相應目錄中；若產生嵌套資料夾則將其中內容搬移上層後刪除該空目錄。
4. 根據目前工作區（即腳本所在路徑）修改設定檔中的路徑參數（含轉義與 URI 部分）。
5. 刪除工具安裝過程中殘留的臨時檔案。
6. 利用 COM 介面建立 VSCode 的 Windows 快捷方式（若無 win32com 則略過）。
"""

import os
import sys
import argparse
import re
import json
import subprocess
from pathlib import Path
from urllib.parse import quote

# 若要建立 Windows 快捷方式，需要 pywin32 模組
try:
    import win32com.client
except ImportError:
    win32com = None

# 導入我們的互動工具模組
from message_utils import (
    pause_if_needed,
    confirm_step
)
# 導入我們的路徑工具模組
from path_utils import (
    get_latest_file,
    get_all_files_reversed_sorted,
    find_real_directory,
    find_home_path
)
# 導入我們的檔案工具模組
from file_utils import (
    extract_zip_with_spinner,
    copy_contents_to_with_spinner,
    move_contents_up
)

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
            tools_dic[key] = {"dir": folder_path, "pattern": pattern}
            print(f"已更新工具包路徑：新增 {key}")
    return tools_dic

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

def escape_backslashes(path: str, for_regex: bool = False) -> str:
    """
    將 Windows 路徑中的反斜線轉為程式碼中需要的跳脫字元格式。
    """
    if for_regex:
        # 若 for_regex 為 True，則將路徑中的反斜線轉為跳脫字元格式，並將單反斜線轉為雙反斜線
        return escape_backslashes(path.replace("\\", "\\\\"))
    else:
        return path.replace("\\", "\\\\")

def replace_in_file(file_path, pattern, replacement):
    """讀取 file_path，利用正規表達式替換 pattern 為 replacement，並覆蓋回原檔案。"""
    print(f"於檔案 {file_path} 中進行字串取代 ...")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(pattern, replacement, content)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("取代完成。")

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
    
    tools = {
        "vscode": {"dir": os.path.join(workspace, "vscode"), "pattern": "VSCode*.zip"},
        "python": {"dir": os.path.join(workspace, "python"), "pattern": "*python*.zip"},
        "nodejs": {"dir": os.path.join(workspace, "node"), "pattern": "*node*.zip"},
        "git": {"dir": os.path.join(workspace, "git"), "pattern": "PortableGit*.exe"},
        "zowe-core": {"dir": os.path.join(workspace, "zowe-cli"), "pattern": "zowe*package*.zip"},
        "zowe-plugin": {"dir": os.path.join(workspace, "zowe-cli"), "pattern": "zowe*plugins*.zip"}
    }
    tools = update_java_dirs(os.path.join(workspace, "java"), tools)
    
    tool_files = {}
    for tool, info in tools.items():
        zip_file = get_latest_file(info["dir"], info["pattern"])
        tool_files[tool] = zip_file
        print(f"{tool}：{zip_file}")
        if zip_file == "":
            print(f"{tool} 不存在，請確認後再執行。")
            sys.exit(1)
    print("檢查工具包完成。\n")
    return tools, tool_files

@confirm_step("【步驟 2】解壓工具包：請確認解壓前準備")
def phase2_extract_packages(tools, tool_files, workspace, auto_continue=False):
    # VSCode 解壓
    vscode_zip_path = os.path.join(tools["vscode"]["dir"], tool_files["vscode"])
    extract_zip_with_spinner(vscode_zip_path, tools["vscode"]["dir"])
    move_contents_up(tools["vscode"]["dir"], find_real_directory(tools["vscode"]["dir"], ".zip"))
    
    # Java 解壓
    for key, info in tools.items():
        if key.startswith("java"):
            java_zip_path = os.path.join(info["dir"], tool_files[key])
            extract_zip_with_spinner(java_zip_path, info["dir"])
            move_contents_up(info["dir"], find_real_directory(info["dir"], ".zip"))
    
    # 取得 JAVA_HOME 相關路徑（取倒序排序第一個項目）
    java_versions = sorted([key for key in tools if key.startswith("java")], reverse=True)
    java_home_path = tools[java_versions[0]]["dir"]
    
    # Python 解壓
    python_zip_path = os.path.join(tools["python"]["dir"], tool_files["python"])
    extract_zip_with_spinner(python_zip_path, tools["python"]["dir"])
    move_contents_up(tools["python"]["dir"], find_real_directory(tools["python"]["dir"], ".zip"))
    
    # Node 解壓
    nodejs_zip_path = os.path.join(tools["nodejs"]["dir"], tool_files["nodejs"])
    extract_zip_with_spinner(nodejs_zip_path, tools["nodejs"]["dir"])
    move_contents_up(tools["nodejs"]["dir"], find_real_directory(tools["nodejs"]["dir"], ".zip"))
    
    # Git 解壓
    git_selfzip_path = os.path.join(tools["git"]["dir"], tool_files["git"])
    print(f"解壓縮：{git_selfzip_path}\n到目錄：{tools['git']['dir']}")
    subprocess.run([git_selfzip_path, "-y", f"-o{tools['git']['dir']}"], cwd=tools["git"]["dir"])
    
    # Zowe 解壓
    for key in ["zowe-core", "zowe-plugin"]:
        zip_path = os.path.join(tools[key]["dir"], tool_files[key])
        extract_zip_with_spinner(zip_path, tools[key]["dir"])
        move_contents_up(tools[key]["dir"], find_real_directory(tools[key]["dir"], ".zip"))
    
    print("解壓工具包完成。\n")
    return java_home_path, java_versions

@confirm_step("【步驟 3】安裝 Zowe-Cli：請確認安裝前設定")
def phase3_install_zowe(tools, workspace, auto_continue=False):
    all_zowe_modules = get_all_files_reversed_sorted(tools["zowe-core"]["dir"], "*.tgz")
    for zowe_module in all_zowe_modules:
        print(f"\n開始安裝 {os.path.basename(zowe_module)} ...\n")
        subprocess.run([os.path.join(tools["nodejs"]["dir"], "npm.cmd"),
                        "install", "-g", "--prefer-offline", "--prefer-online",
                        "--no-fund", "--no-audit", zowe_module],
                       cwd=tools["nodejs"]["dir"])
    print("安裝 Zowe-Cli 完成。\n")

@confirm_step("【步驟 4】路徑設定遷移：請確認設定檔修改")
def phase4_path_migration(tools, java_home_path, workspace, auto_continue=False):
    # 產生轉義字串與 URI
    qbsworkspace = escape_backslashes(f"{workspace}", for_regex=True)
    workspaceuri = quote(workspace.as_uri())
    
    # 複製 VSCode 設定結構
    source_from = os.path.join(workspace, "data")
    copy_to = os.path.join(workspace, "vscode", "data")
    copy_contents_to_with_spinner(source_from, copy_to)
    
    # 修改 VSCode 設定檔內容
    vscode_settings_path = os.path.join(workspace, "vscode", "data", "user-data", "User", "settings.json")
    replace_in_file(vscode_settings_path, r"_WORKSPACE_", qbsworkspace)
    replace_in_file(vscode_settings_path, r"_WORKSPACEURI_", workspaceuri)
    replace_in_file(vscode_settings_path, r"_JAVAHOME_", escape_backslashes(java_home_path, for_regex=True))
    
    # 組成 java runtime 清單（僅取 major 版本）
    java_versions = sorted([key for key in tools if key.startswith("java")], reverse=True)
    java_runtimes = []
    for key in java_versions:
        major_version = extract_major_version(key)
        java_runtimes.append({
            "name": f"JavaSE-{major_version}",
            "path": escape_backslashes(tools[key]["dir"])
        })
    runtime_json = ",\n".join(json.dumps(entry) for entry in java_runtimes)
    replace_in_file(vscode_settings_path, r"_JAVARUNTIMES_", runtime_json)
    
    print("路徑設定遷移完成。\n")
    return

@confirm_step("【步驟 5】安裝 VSCode 擴充功能包：請確認安裝擴充功能包")
def phase5_install_extensions(workspace, auto_continue=False):
    extension_groups = ['ms-ceintl', 'redhat', 'ibm', 'broadcommfd', 'zowe']
    for group in extension_groups:
        group_folder = os.path.join(workspace, "extensions")
        all_group_extensions = get_all_files_reversed_sorted(group_folder, f"{group}*.vsix")
        for extension in all_group_extensions:
            print(f"\n開始安裝 {os.path.basename(extension)} ...\n")
            subprocess.run([os.path.join(workspace, "vscode", "bin", "code.cmd"),
                            "--install-extension", extension],
                           cwd=os.path.join(workspace, "vscode", "bin"))
    print("擴充功能包安裝完成。\n")
    return

@confirm_step("【步驟 6】建立 VSCode 快捷方式：請確認建立捷徑")
def phase6_create_shortcut(tools, java_home_path, workspace, auto_continue=False):
    shortcut_path = os.path.join(workspace, "VSCode.lnk")
    if os.path.exists(shortcut_path):
        os.remove(shortcut_path)
        print("已刪除既有的 VSCode.lnk 快捷方式。")
        
    vscmd = os.path.join(workspace, "vscode", "bin", "code.cmd")
    vscmd_home = os.path.join(workspace, "vscode", "bin")
    vsc_home = os.path.join(workspace, "vscode")
    
    # 拼湊要插入於批次檔中的環境設定語法
    # ※ 注意此處各路徑會依照雙反斜線轉義
    python_home = find_home_path(tools["python"]["dir"], "python.exe")
    node_home = find_home_path(tools["nodejs"]["dir"], "node.exe")
    git_cmd_path = os.path.join(tools["git"]["dir"], "cmd")
    insertions = [
        'powershell -Command "Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope CurrentUser -Force"\n',
        'set "PATH={};{};{};{};%PATH%"\n'.format(
            escape_backslashes(java_home_path),
            escape_backslashes(python_home) if python_home else "",
            escape_backslashes(node_home) if node_home else "",
            escape_backslashes(git_cmd_path)
        ),
        'set "JAVA_HOME={}"\n'.format(escape_backslashes(java_home_path))
    ]
    vscode_cmd_insertion(vscmd, insertions)
    print("已插入臨時 PATH 與 JAVA_HOME 設定於 VSCode 啟動檔中。")
    
    if win32com is not None:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(shortcut_path)
        shortcut.TargetPath = vscmd
        shortcut.Arguments = " ".join([os.path.join(workspace, "workspace"), "--locale=zh-tw"])
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
    parser.add_argument("--workspace", type="str", help="指定工作區目錄，預設為腳本檔所在路徑。")
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
    phase4_path_migration(tools, java_home_path, workspace, auto_continue=args.yes)
    phase5_install_extensions(workspace, auto_continue=args.yes)
    phase6_create_shortcut(tools, java_home_path, workspace, auto_continue=args.yes)
    
    print("腳本執行結束。")
    pause_if_needed("按下 Enter 鍵後關閉程式", auto_continue=args.yes)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
程式名稱: install.py
開發單位: IBM Expert Labs
開發人員: nicholas.yahung.chien@ibm.com
日期: 2025/06/20
版本: 2.2.1

說明:
1. 於各指定資料夾中尋找符合條件的 Zip 檔（依修改時間排序取最新檔案）。
2. 驗證工具（VSCode、Jdk21）的 Zip 檔是否存在，
   若不存在則顯示錯誤後結束程式。
3. 執行解壓動作，各個工具的 Zip 檔解壓到相應目錄中；對於解壓後產生「嵌套資料夾」的工具，
   將把裡面的檔案移回上一層，並移除該空資料夾。
4. 進行路徑設定的調整，根據目前工作區（即腳本所在路徑）生成兩組經過轉義的字串，
   並用正規表達式 VSCode 設定檔中的「_WORKSPACE_」標。
5. 刪除工作目錄中以 sed 開頭的檔案（清理殘留工具）。
6. 建立 VSCode 的 Windows 快捷方式，利用 COM 介面產生 .lnk 檔案（若電腦無 win32com 模組則跳過此部份）。

使用方式:
使用前請確認 Python 執行環境中有必要的模組（若要建立快捷方式需要有 pywin32 模組）。
"""

import os
import sys
import time
import threading
import glob
import zipfile
import shutil
import re
import subprocess
from pathlib import Path
from urllib.parse import quote

# 若要建立 Windows 快捷方式，需要 win32com 模組（通常屬於 pywin32 套件）
try:
    import win32com.client
except ImportError:
    win32com = None

def press_enter(message):
    """顯示訊息並等待使用者按下 Enter"""
    input(message)

def get_latest_file(directory, pattern):
    """
    在指定目錄中，尋找與 pattern 相符的檔案，
    以修改時間排序取得最新一個檔案。
    若找不到，回傳空字串。
    """
    search_path = os.path.join(directory, pattern)
    matched_files = glob.glob(search_path)
    if not matched_files:
        return ""
    # 依時間由新到舊排序，取第一筆
    matched_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    return os.path.basename(matched_files[0])

def get_all_files_reversed_sorted(directory, pattern):
    """
    在指定目錄中，尋找與 pattern 相符的檔案，
    以名稱倒序排序取得。
    若找不到，回傳空字串。
    """
    search_path = os.path.join(directory, pattern)
    matched_files = glob.glob(search_path)
    if not matched_files:
        return []
    # 依名稱由字典順序大到小排序
    matched_files.sort(key=lambda f: os.path.basename(f), reverse=True)
    return matched_files

def find_real_directory(start_path):
    """
    從指定起始目錄開始，遞迴搜尋子目錄，直到找到一個資料夾內
    除了 .zip 檔案與其他子資料夾外，還存在其他類型的檔案。
    
    若找到符合條件的目錄，則返回該路徑；若未找到則返回 None。
    """
    for root, dirs, files in os.walk(start_path):
        # 過濾掉所有 .zip 檔案，只檢查其他類型的檔案
        non_zip_files = [f for f in files if not f.lower().endswith(".zip")]
        
        # 若該目錄內包含非 .zip 的檔案，則回傳該目錄路徑
        if non_zip_files:
            return root
    # 若遍歷整個目錄樹後仍無符合條件的目錄，返回 None
    return None

def find_home_path(start_path, target_file):
    """
    從指定起始目錄開始，遞迴搜尋子目錄，直到找到一個資料夾內
    存在符合 target_file 的檔案。
    
    若找到符合條件的目錄，則返回該路徑；若未找到則返回 None。
    """
    for root, dirs, files in os.walk(start_path):
        # 只檢查 target_file 檔案
        has_target = [f for f in files if f.lower() == target_file.lower()]
        
        # 若該目錄內包含 target_file 檔案，則回傳該目錄路徑
        if has_target:
            return root
    # 若遍歷整個目錄樹後仍無符合條件的目錄，返回 None
    return None

def spinner(stop_event, msg_startup, msg_running, msg_complete):
    """
    此函式在背景中持續印出旋轉圖示，以顯示「正在進行中」的狀態，
    當 stop_event 被設定後，停止運行。
    """
    spinner_chars = "|/-\\"
    idx = 0
    print(f"{msg_startup}", end='\n', flush=True)
    while not stop_event.is_set():
        print(f"{msg_running}... " + spinner_chars[idx % len(spinner_chars)], end='\r', flush=True)
        idx += 1
        time.sleep(0.2)
    # 當完成時，清除同一行的訊息並顯示完成訊息
    sys.stdout.write("\r" + f"{msg_complete}！        \n")
    sys.stdout.flush()

def extract_zip_with_spinner(zip_path, extract_to):
    """
    此函式使用 zipfile 模組解壓縮，並在解壓縮期間開啟 spinner 線程，
    告訴使用者解壓縮程序仍在進行。
    """
    # 建立一個事件，讓 spinner 能在解壓縮結束時被通知停止
    stop_event = threading.Event()
    
    # 啟動 spinner 背景執行緒
    spinner_thread = threading.Thread(target=spinner, args=(stop_event,f"解壓縮：{zip_path}\n到目錄：{extract_to}","解壓縮中","解壓縮完成"))
    spinner_thread.start()
    
    # 進行解壓縮（這是一個 blocking 的動作）
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(path=extract_to)
    
    # 解壓縮完成，設定事件讓 spinner 停止
    stop_event.set()
    spinner_thread.join()

def move_contents_up(parent_dir, target_dir):
    """
    檢查 parent_dir 底下是否有符合 target_dir 的子資料夾（通常為解壓後產生的嵌套資料夾），
    若存在，將其內容搬移到 parent_dir，並刪除該子資料夾。
    """
    search_path = os.path.join(parent_dir, target_dir)
    if parent_dir == search_path:
        return
    dirs = glob.glob(search_path)
    if not dirs:
        return
    # 依時間由新到舊排序，取最新的一個資料夾
    dirs.sort(key=lambda d: os.path.getmtime(d), reverse=True)
    bogus_folder = dirs[0]
    for item in os.listdir(bogus_folder):
        source_path = os.path.join(bogus_folder, item)
        dest_path = os.path.join(parent_dir, item)
        shutil.move(source_path, dest_path)
    os.rmdir(bogus_folder)
    print(f"已將 {bogus_folder} 的內容\n搬移至 {parent_dir} 並刪除該資料夾。")

def copy_contents_to_with_spinner(source_dir, destination_dir):
    """
    此函式使用 shutil 模組將 source_dir 目錄整個複製為 destination_dir 目錄，
    並在複製期間開啟 spinner 線程，告訴使用者複製程序仍在進行。
    """
    # 建立一個事件，讓 spinner 能在複製結束時被通知停止
    stop_event = threading.Event()
    
    # 啟動 spinner 背景執行緒
    spinner_thread = threading.Thread(target=spinner, args=(stop_event,f"複製：{source_dir}\n到目錄：{destination_dir}","複製中","複製完成"))
    spinner_thread.start()
    
    # 進行複製（這是一個 blocking 的動作）
    try:
        shutil.copytree(source_dir, destination_dir)
    except Exception as e:
        print("複製過程中發生錯誤：", e)
    
    # 複製完成，設定事件讓 spinner 停止
    stop_event.set()
    spinner_thread.join()

def replace_in_file(file_path, pattern, replacement):
    """
    讀取 file_path 檔案內容，以 regex 方式替換符合 pattern 的部分，
    替換為 replacement 字串，且直接覆蓋原檔案內容。
    """
    print(f"於檔案 {file_path} 中進行字串取代...")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    new_content = re.sub(pattern, replacement, content)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("取代完成。")

def vscode_cmd_insertion(file_path, insertions):
    # 讀取原始內容
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        # 當讀到 setlocal 那一行時，立即插入額外設定
        if not inserted and line.strip().lower() == "setlocal":
            new_lines.extend(insertions)
            inserted = True
            
    # 寫回修改後的內容
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def main():
    # 取得腳本所在目錄（== %~dp0）
    if getattr(sys, 'frozen', False):  # 檢查是不是被 PyInstaller 打包成 .exe
        # 取得 .exe 執行檔所在路徑
        script_dir = Path(sys.executable).parent.resolve()
    else:
        # 取得 .py 腳本所在路徑
        script_dir = Path(__file__).parent.resolve()
    #script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print("目前工作目錄切換為：", script_dir)
    print()

    # === 第1階段：檢查工具包 ===
    # workspace 為腳本所在的路徑
    workspace = script_dir
    print("工作區目錄：", workspace)
    print("檢查工具包...\n")
    
    # 各工具對應的資料夾及 Zip 檔案搜尋條件
    tools = {
        "vscode": {"dir": os.path.join(script_dir, "vscode"), "pattern": "VSCode*.zip"},
        "java21": {"dir": os.path.join(script_dir, "java"), "pattern": "*jdk*21*.zip"},
        "python": {"dir": os.path.join(script_dir, "python"), "pattern": "*python*.zip"},
        "nodejs": {"dir": os.path.join(script_dir, "node"), "pattern": "*node*.zip"},
        "git": {"dir": os.path.join(script_dir, "git"), "pattern": "PortableGit*.exe"},
        "zowe-core": {"dir": os.path.join(script_dir, "zowe-cli"), "pattern": "zowe*package*.zip"},
        "zowe-plugin": {"dir": os.path.join(script_dir, "zowe-cli"), "pattern": "zowe*plugins*.zip"},
    }
    
    tool_files = {}
    for tool, info in tools.items():
        zip_file = get_latest_file(info["dir"], info["pattern"])
        tool_files[tool] = zip_file
        print(f"{tool}：{zip_file}")
        if zip_file == "":
            print(f"{tool} 不存在，請確認後再執行。")
            sys.exit(1)
    
    print("檢查工具包完成。\n")
    press_enter("準備解壓工具包…按下 Enter 鍵開始。\n")
    
    # === 第2階段：解壓工具包 ===
    # workspace 為腳本所在的路徑
    workspace = script_dir
    print("工作區目錄：", workspace)
    
    # VSCode 解壓
    vscode_zip_path = os.path.join(tools["vscode"]["dir"], tool_files["vscode"])
    extract_zip_with_spinner(vscode_zip_path, tools["vscode"]["dir"])
    move_contents_up(tools["vscode"]["dir"], find_real_directory(tools["vscode"]["dir"]))
    print()
    
    # Java 21 解壓
    java21_zip_path = os.path.join(tools["java21"]["dir"], tool_files["java21"])
    extract_zip_with_spinner(java21_zip_path, tools["java21"]["dir"])
    move_contents_up(tools["java21"]["dir"], find_real_directory(tools["java21"]["dir"]))
    print()
    
    # Python 解壓
    python_zip_path = os.path.join(tools["python"]["dir"], tool_files["python"])
    extract_zip_with_spinner(python_zip_path, tools["python"]["dir"])
    move_contents_up(tools["python"]["dir"], find_real_directory(tools["python"]["dir"]))
    print()
    
    # Node 解壓
    nodejs_zip_path = os.path.join(tools["nodejs"]["dir"], tool_files["nodejs"])
    extract_zip_with_spinner(nodejs_zip_path, tools["nodejs"]["dir"])
    move_contents_up(tools["nodejs"]["dir"], find_real_directory(tools["nodejs"]["dir"]))
    print()
    
    # Git 解壓
    git_selfzip_path = os.path.join(tools["git"]["dir"], tool_files["git"])
    print(f"解壓縮：{git_selfzip_path}\n到目錄：{tools["git"]["dir"]}")
    subprocess.run([git_selfzip_path, "-y", f"-o{tools["git"]["dir"]}"], cwd=tools["git"]["dir"])
    print()
    
    # Zowe 解壓
    zowe_core_zip_path = os.path.join(tools["zowe-core"]["dir"], tool_files["zowe-core"])
    extract_zip_with_spinner(zowe_core_zip_path, tools["zowe-core"]["dir"])
    move_contents_up(tools["zowe-core"]["dir"], find_real_directory(tools["zowe-core"]["dir"]))
    print()
    
    zowe_plugins_zip_path = os.path.join(tools["zowe-plugin"]["dir"], tool_files["zowe-plugin"])
    extract_zip_with_spinner(zowe_plugins_zip_path, tools["zowe-plugin"]["dir"])
    move_contents_up(tools["zowe-plugin"]["dir"], find_real_directory(tools["zowe-plugin"]["dir"]))
    print()
    
    print("解壓工具包完成。\n")
    press_enter("準備安裝Zowe-Cli工具…按下 Enter 鍵開始。\n")
    
    # === 第3階段：安裝Zowe指令列環境工具 ===
    # workspace 為腳本所在的路徑
    workspace = script_dir
    print("工作區目錄：", workspace)
    
    # 安裝 Zowe-Cli
    all_zowe_modules = get_all_files_reversed_sorted(tools["zowe-core"]["dir"], "*.tgz")
    for zowe_module in all_zowe_modules:
        print(f"\n開始安裝 {os.path.basename(zowe_module)} ...\n")
        subprocess.run([os.path.join(tools["nodejs"]["dir"], "npm.cmd"), "install", "-g", "--prefer-offline", "--prefer-online", "--no-fund", "--no-audit", zowe_module], cwd=tools["nodejs"]["dir"])
    
    print("安裝Zowe-Cli完成。\n")
    press_enter("準備進行路徑設定遷移…按下 Enter 鍵開始。\n")
    
    # === 第4階段：路徑設定遷移 ===
    # workspace 為腳本所在的路徑
    workspace = script_dir
    print("工作區目錄：", workspace)
    
    # 依據原批次檔指令，對 workspace 做字元轉義處理
    # qbsworkspace：將 "\" 轉成 "\\\\"
    qbsworkspace = f"{workspace}".replace("\\", "\\\\\\\\")
    # workspaceuri：將目錄路徑轉成以 "file://" 開頭的 uri 路徑
    workspaceuri = quote(workspace.as_uri())
    
    # 複製整個 VSCode 可攜式設定目錄結構
    print("複製設定目錄結構。\n")
    source_from = os.path.join(workspace, "data")
    copy_to = os.path.join(workspace, "vscode", "data")
    copy_contents_to_with_spinner(source_from, copy_to)
    
    print("修改安裝路徑設定。\n")
    # 針對 VSCode 的 settings.json 進行取代
    vscode_settings_path = os.path.join(workspace, "vscode", "data", "user-data", "User", "settings.json")
    pattern_vscode = r"_WORKSPACE_"
    replace_in_file(vscode_settings_path, pattern_vscode, qbsworkspace)
    pattern_vscode_uri = r"_WORKSPACEURI_"
    replace_in_file(vscode_settings_path, pattern_vscode_uri, workspaceuri)
    
    print("\n路徑遷移完成。\n")
    press_enter("準備安裝 VSCode IBM Z 擴充功能包…按下 Enter 鍵開始。\n")
    
    # === 第5階段：安裝 IBM Z 開發工具擴充功能包 ===
    # 安裝 VSCode 擴充功能包
    print("安裝擴充功能包。\n")
    extension_groups = ['ms-ceintl', 'redhat', 'ibm', 'broadcommfd', 'zowe']
    for group in extension_groups:
        all_group_extensions = get_all_files_reversed_sorted(os.path.join(workspace, "extensions"), f"{group}*.vsix")
        for extension in all_group_extensions:
            print(f"\n開始安裝 {os.path.basename(extension)} ...\n")
            subprocess.run([os.path.join(workspace, "vscode", "bin", "code.cmd"), "--install-extension", extension], cwd=os.path.join(workspace, "vscode", "bin"))
    
    print("\n擴充功能包安裝完成。\n")
    press_enter("準備建立 VSCode 快捷方式…按下 Enter 鍵開始。\n")
    
    # === 第6階段：建立 VSCode 快捷方式 ===
    # workspace 為腳本所在的路徑
    workspace = script_dir
    print("工作區目錄：", workspace)
    
    shortcut_path = os.path.join(workspace, "VSCode.lnk")
    # 如果已存在同名快捷方式，先刪除它
    if os.path.exists(shortcut_path):
        os.remove(shortcut_path)
        print("既有的 VSCode.lnk 已被刪除。")
    
    # 設定相關路徑
    vscmd = os.path.join(workspace, "vscode", "bin", "code.cmd")
    vscmd_home = os.path.join(workspace, "vscode", "bin")
    vsc_home = os.path.join(workspace, "vscode")
    
    # 要插入的環境變數設定語法
    insertions = [
        f"powershell -Command {'"'}Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope CurrentUser -Force{'"'}\n",
        f"set {'"'}{'PATH='}"
        + f"{os.path.join(tools["java21"]["dir"], "bin").replace("\\", "\\\\")}"
        + f"{';'}{find_home_path(tools["python"]["dir"], "python.exe").replace("\\", "\\\\")}"
        + f"{';'}{find_home_path(tools["python"]["dir"], "pip.exe").replace("\\", "\\\\")}"
        + f"{';'}{find_home_path(tools["nodejs"]["dir"], "node.exe").replace("\\", "\\\\")}"
        + f"{';'}{os.path.join(tools["git"]["dir"], "cmd").replace("\\", "\\\\")}"
        + f"{';%PATH%'}{'"'}\n",
        f"set {'"'}{'JAVA_HOME='}{tools["java21"]["dir"].replace("\\", "\\\\")}{'"'}\n"
    ]
    
    vscode_cmd_insertion(vscmd, insertions)
    print("更新完成，已插入 PATH 與 JAVA_HOME 的暫時性環境變數設定。")
    
    # 利用 COM 介面建立 Windows 快捷方式
    if win32com is not None:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(shortcut_path)
        shortcut.TargetPath = vscmd
        shortcut.WorkingDirectory = vscmd_home
        # 設定圖示所在：vsc_home\Code.exe,0
        shortcut.IconLocation = os.path.join(vsc_home, "Code.exe") + ",0"
        shortcut.Save()
        print("VSCode 快捷方式建立成功。")
    else:
        print("無 win32com 模組，無法建立 Windows 快捷方式。")
    
    print("\n快捷方式建立完成。\n")
    
    print("腳本執行結束。")
    press_enter("按下 Enter 後結束程式。\n")
    
if __name__ == "__main__":
    main()

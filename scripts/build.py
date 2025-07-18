#!/usr/bin/env python3
"""
IBM VSCode for Z Development Environment Setup Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 2.6.0
日期: 2025/01/13

說明:
VSCode4z 專案建置腳本，用於自動化打包和發布流程。

使用方式:
  指定版本編號必填，例如:
      python build.py --version 1.2.3
  可選擇透過 --workspace 指定工作區目錄，若未指定則以腳本所在路徑作為 workspace。

流程說明:
  1. 取得 build.py 腳本所在目錄（考量是否打包為 .exe）。
  2. 根據參數設定工作區（workspace）。
  3. 執行 scripts/download.py，並傳入 --workspace 參數。
  4. 使用 pyinstaller --onefile 打包 scripts 下的 install.py、workspace.py 與 uninstall.py。
  5. 將 scripts/dist 中的 .exe 複製到 workspace 目錄下。
  6. 刪除 scripts 目錄中除 .py 與 .yml 以外的所有檔案及目錄。
  7. 最後將 workspace 目錄下的所有內容打包為 VSCode4z-<version>.zip。

更新記錄:
- v2.6.0: 優化建置流程，改善配置載入和檔案管理
- v2.5.0: 優化檔案壓縮邏輯，改善檔案收集和排除模式處理
- v2.4.11: 重構壓縮功能，使用 pyminizip 提升效能
- v2.3.0: 新增檔案排除功能，改善打包流程
- v2.2.1: 初始版本，提供基本的建置和打包功能
"""

import os
import sys
import argparse
import subprocess
import shutil
import pyminizip
import glob
import fnmatch
from pathlib import Path
from configs import load_build_config
from utils.path_utils import get_script_dir

# -------------------------------
#  功能函式
# -------------------------------
def run_download_py(workspace, scripts_dir):
    """
    執行 scripts 目錄下的 download.py，並傳入 --workspace 參數。
    """
    download_py = os.path.join(scripts_dir, "download.py")
    if not os.path.exists(download_py):
        sys.exit(f"找不到 {download_py}")
    # 使用目前的 Python 執行環境呼叫 download.py
    cmd = [sys.executable, str(download_py), "--workspace", str(workspace)]
    print(f"執行下載腳本: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit("download.py 執行失敗，請確認錯誤訊息。")

def build_executables(scripts_dir):
    """
    分別對 scripts 目錄下的 install.py、workspace.py 與 uninstall.py 執行 pyinstaller --onefile 打包。
    """
    for script in ["install.py", "workspace.py", "uninstall.py"]:
        print(f"開始打包 {script}...")
        result = subprocess.run(
            ["pyinstaller", "--onefile", script],
            cwd=scripts_dir
        )
        if result.returncode != 0:
            sys.exit(f"打包 {script} 失敗。")

def copy_exes_to_workspace(scripts_dir, workspace):
    """
    將 scripts 目錄下 dist 資料夾內的所有 .exe 檔案複製到 workspace 中。
    """
    dist_dir = os.path.join(scripts_dir, "dist")
    if not os.path.exists(dist_dir):
        sys.exit("找不到打包後的 dist 目錄")
    for exe_file in glob.glob(os.path.join(dist_dir, "*.exe")):
        dest = os.path.join(workspace, os.path.basename(exe_file))
        print(f"複製 {os.path.basename(exe_file)} 到 {workspace}")
        shutil.copy(exe_file, dest)

def clean_scripts_directory(scripts_dir):
    """
    刪除 scripts 目錄下，除 .py 和 configs、utils 目錄以外的所有檔案與目錄。
    """
    for item in os.listdir(scripts_dir):
        # 若是檔案且副檔名不是 .py
        if os.path.isfile(os.path.join(scripts_dir, item)) and not item.lower().endswith(".py"):
            print(f"刪除檔案: {item}")
            os.remove(os.path.join(scripts_dir, item))
        # 若是目錄，保留 configs 和 utils 目錄，刪除其他目錄
        elif os.path.isdir(os.path.join(scripts_dir, item)):
            if item in ["configs", "utils"]:
                print(f"保留目錄: {item}")
            else:
                print(f"刪除目錄: {item}")
                shutil.rmtree(os.path.join(scripts_dir, item))

def gather_files(root_dir, exclude_dirs=None, exclude_files=None):
    """
    遞迴遍歷 root_dir，蒐集所有要壓縮的檔案及其相對路徑，
    並根據 exclude_patterns 排除符合條件的目錄及檔案。
    
    :param root_dir: 要壓縮的來源目錄（字串或 Path 皆可）
    :param exclude_dirs: 要排除的目錄名稱模式清單，例如 [".git"]
    :param exclude_files: 要排除的檔案名稱模式清單，例如 ["*.tmp"]
    :return: 兩個清單 (file_abs_paths, prefix_rel_paths)
         file_abs_paths：每個檔案的絕對路徑
         prefix_rel_paths：在 zip 中的相對存放路徑（以 root_dir 為根）
    """
    file_abs_paths = []
    prefix_rel_paths = []
    
    if exclude_dirs is None:
        exclude_dirs = []
    if exclude_files is None:
        exclude_files = []

    for root, dirs, files in os.walk(root_dir):
        # 排除那些目錄（直接在 dirs 中作過濾，以避免往下遍歷這些資料夾）
        dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pat) for pat in exclude_dirs)]
        
        for file in files:
            # 若檔案名稱符合任何排除模式，則略過
            if any(fnmatch.fnmatch(file, pat) for pat in exclude_files):
                continue
            file_abs_paths.append(os.path.join(root, file))
            prefix_rel_paths.append("" if os.path.relpath(root, start=root_dir) == "." else os.path.relpath(root, start=root_dir))
            
    return file_abs_paths, prefix_rel_paths

def compress_directory(root_dir, output_zip, exclude_dirs=None, exclude_files=None):
    """
    利用 pyminizip 將 root_dir 目錄下（排除指定檔案/目錄後）的檔案壓縮成 output_zip。
    
    :param root_dir: 要壓縮的來源目錄
    :param output_zip: 輸出 zip 檔案完整路徑（例如 "D:/output.zip"）
    :param compression_level: 壓縮等級 (0~9)
    :param exclude_patterns: 要排除的檔案或目錄模式清單（例如 [".git", "*.tmp"]）
    """
    file_abs_paths, prefix_rel_paths = gather_files(root_dir, exclude_dirs, exclude_files)
    if not file_abs_paths:
        print("沒有檔案需要壓縮！")
        return
    for file, prefix in zip(file_abs_paths, prefix_rel_paths):
        print(prefix, file)

    try:
        print(f"開始壓縮：{os.path.basename(output_zip)}")
        pyminizip.compress_multiple(file_abs_paths, prefix_rel_paths, output_zip, None, 5)
        print(f"壓縮成功，輸出檔案：{output_zip}")
    except Exception as e:
        print("壓縮失敗：", e)

# -------------------------------
# 主流程
# -------------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(description="Build script for VSCode4z package.")
    parser.add_argument("--version", help="指定版本編號，例如 1.2.3，若未指定則使用 build.yml 中的版本")
    parser.add_argument("--workspace", type=str, help="指定工作區目錄，預設為腳本所在目錄")
    return parser.parse_args()

def main():
    args = parse_arguments()
    version = args.version
    
    # 若使用者有指定 --workspace 則使用該目錄，否則預設為 script_dir
    workspace = Path(args.workspace).resolve() if args.workspace else get_script_dir()
    os.chdir(workspace)
    print("目前工作目錄設定為：", workspace)
    
    # 取得 scripts 目錄，預期其在 build.py 所在目錄下的 scripts 子目錄
    scripts_dir = os.path.join(workspace, "scripts")
    if not os.path.exists(scripts_dir):
        sys.exit(f"找不到 scripts 目錄：{scripts_dir}")

    # 載入 build.yml 設定檔
    build_config = load_build_config()

    # 1. 執行 download.py 並傳入 --workspace
    run_download_py(workspace, scripts_dir)
    
    # 2. 利用 pyinstaller 分別打包 install.py、workspace.py 與 uninstall.py 為單一執行檔
    build_executables(scripts_dir)
    
    # 3. 將 scripts/dist 底下的 .exe 複製到 workspace 目錄
    copy_exes_to_workspace(scripts_dir, workspace)
    
    # 4. 刪除 scripts 目錄下除了 *.py 與 *.yml 以外的其他檔案與目錄
    clean_scripts_directory(scripts_dir)
    
    # 5. 將 workspace 目錄下的所有檔案與子目錄打包成壓縮檔
    compress_directory(workspace, os.path.join(workspace, f"{build_config['release']['name']}-{build_config['release']['version']}.zip"), exclude_dirs=build_config['release']['exclude_dirs'], exclude_files=build_config['release']['exclude_files'])

if __name__ == "__main__":
    main()
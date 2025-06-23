#!/usr/bin/env python3
"""
build.py
========

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
    刪除 scripts 目錄下，除 .py 和 .yml 以外的所有檔案與目錄。
    """
    for item in os.listdir(scripts_dir):
        # 若是檔案且副檔名不是 .py 與 .yml
        if os.path.isfile(os.path.join(scripts_dir, item)) and not item.lower().endswith((".py", ".yml")):
            print(f"刪除檔案: {item}")
            os.remove(os.path.join(scripts_dir, item))
        # 若是目錄，全部刪除
        elif os.path.isdir(os.path.join(scripts_dir, item)):
            print(f"刪除目錄: {item}")
            shutil.rmtree(os.path.join(scripts_dir, item))

def gather_files(root_dir, exclude_patterns=None):
    """
    遞迴遍歷 root_dir，蒐集所有要壓縮的檔案及其相對路徑，
    並根據 exclude_patterns 排除符合條件的目錄及檔案。
    
    :param root_dir: 要壓縮的來源目錄（字串或 Path 皆可）
    :param exclude_patterns: 要排除的名稱模式清單，例如 [".git", "*.tmp"]
    :return: 兩個清單 (file_paths, arc_names)
         file_paths：每個檔案的絕對路徑
         arc_names：在 zip 中的相對存放路徑（以 root_dir 為根）
    """
    file_paths = []
    arc_names = []
    
    if exclude_patterns is None:
        exclude_patterns = []
    
    for root, dirs, files in os.walk(root_dir):
        # 排除那些目錄（直接在 dirs 中作過濾，以避免往下遍歷這些資料夾）
        dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pat) for pat in exclude_patterns)]
        
        for file in files:
            # 若檔案名稱符合任何排除模式，則略過
            if any(fnmatch.fnmatch(file, pat) for pat in exclude_patterns):
                continue
            abs_path = os.path.join(root, file)
            # 利用 os.path.relpath 計算相對於 source_dir 的路徑
            rel_path = os.path.relpath(abs_path, start=root_dir)
            file_paths.append(abs_path)
            arc_names.append(rel_path)
            
    return file_paths, arc_names

def compress_directory(root_dir, output_zip, compression_level=5, exclude_patterns=None):
    """
    利用 pyminizip 將 root_dir 目錄下（排除指定檔案/目錄後）的檔案壓縮成 output_zip。
    
    :param root_dir: 要壓縮的來源目錄
    :param output_zip: 輸出 zip 檔案完整路徑（例如 "D:/output.zip"）
    :param compression_level: 壓縮等級 (0~9)
    :param exclude_patterns: 要排除的檔案或目錄模式清單（例如 [".git", "*.tmp"]）
    """
    file_paths, arc_names = gather_files(root_dir, exclude_patterns)
    if not file_paths:
        print("沒有檔案需要壓縮！")
        return

    try:
        pyminizip.compress_multiple(file_paths, arc_names, output_zip, None, compression_level)
        print(f"壓縮成功，輸出檔案：{output_zip}")
    except Exception as e:
        print("壓縮失敗：", e)

# -------------------------------
# 主流程
# -------------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(description="Build script for VSCode4z package.")
    parser.add_argument("--version", required=True, help="指定版本編號，例如 1.2.3")
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

    # 1. 執行 download.py 並傳入 --workspace
    run_download_py(workspace, scripts_dir)
    
    # 2. 利用 pyinstaller 分別打包 install.py、workspace.py 與 uninstall.py 為單一執行檔
    build_executables(scripts_dir)
    
    # 3. 將 scripts/dist 底下的 .exe 複製到 workspace 目錄
    copy_exes_to_workspace(scripts_dir, workspace)
    
    # 4. 刪除 scripts 目錄下除了 *.py 與 *.yml 以外的其他檔案與目錄
    clean_scripts_directory(scripts_dir)
    
    # 5. 將 workspace 目錄下的所有檔案與子目錄打包成壓縮檔
    compress_directory(workspace, os.path.join(workspace, f"VSCode4z-{version}.zip"), exclude_patterns=[".git"])

if __name__ == "__main__":
    main()
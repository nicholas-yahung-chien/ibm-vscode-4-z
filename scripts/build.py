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
import py7zr
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

def compress_directory(source_dir, archive_file_path, exclude_patterns=None):
    """
    壓縮整個 source_dir 目錄到 archive_file_path 壓縮檔中，
    並排除掉與 exclude_patterns 相關的檔案或目錄。

    :param source_dir: 要壓縮的目錄（絕對路徑或相對路徑）
    :param archive_file_path: 輸出壓縮檔路徑，例如 "output.7z"
    :param exclude_patterns: 一個字串清單，代表要排除掉的檔案或目錄名稱模式（例如 [".git", "*.tmp"]）
    """
    if exclude_patterns is None:
        exclude_patterns = []

    # 建立一個 7z 壓縮檔
    print(f"開始壓縮：{os.path.basename(archive_file_path)}")
    with py7zr.SevenZipFile(archive_file_path, 'w') as archive:
        # 使用 os.walk 來遞迴遍歷 source_dir 目錄
        for root, dirs, files in os.walk(source_dir):
            # 根據排除模式過濾掉不需要的子目錄
            # 修改 dirs[:] 會影響到 os.walk 的後續遞迴
            dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pat) for pat in exclude_patterns)]

            # 處理檔案：同樣若檔案名稱符合任何排除模式，則略過
            for file in files:
                if any(fnmatch.fnmatch(file, pat) for pat in exclude_patterns):
                    continue
                full_path = os.path.join(root, file)
                # 相對於 source_dir 的路徑，這樣在壓縮檔中才不會包含絕對路徑
                arcname = os.path.relpath(full_path, source_dir)
                archive.write(full_path, arcname=arcname)
    print(f"完成壓縮：{os.path.basename(archive_file_path)}")

def zip_directory_exclude(root_dir, version, exclude_dirs=None):
    """
    將 workspace 目錄下的所有檔案與子目錄打包成一份 VSCode4z-<version>.zip。
    並可排除位於 exclude_dirs 清單中的目錄名稱（例如：['.git']）。
    壓縮檔將存放在 workspace 目錄下。
    """
    if exclude_dirs is None:
        exclude_dirs = []
    zip_filepath = os.path.join(root_dir, f"VSCode4z-{version}.7z")
    print(f"開始壓縮：{os.path.basename(zip_filepath)}")
    with py7zr.SevenZipFile(zip_filepath, 'w') as archive:
        archive.writeall(root_dir, arcname=os.path.basename(root_dir))
    print(f"壓縮完成：{os.path.basename(zip_filepath)}")

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
    compress_directory(workspace, os.path.join(workspace, f"VSCode4z-{version}.7z"), exclude_patterns=[".git"])

if __name__ == "__main__":
    main()
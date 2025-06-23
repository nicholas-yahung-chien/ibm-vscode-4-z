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
import zipfile
import glob
from pathlib import Path

def parse_arguments():
    parser = argparse.ArgumentParser(description="Build script for VSCode4z package.")
    parser.add_argument("--version", required=True, help="指定版本編號，例如 1.2.3")
    parser.add_argument("--workspace", type=str, help="指定工作區目錄，預設為腳本所在目錄")
    return parser.parse_args()

def get_script_dir():
    """
    若被 PyInstaller 打包，則使用 sys.executable 的目錄作為腳本所在目錄；
    否則使用 __file__ 的目錄。
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.resolve()
    else:
        return Path(__file__).parent.resolve()

def run_download_py(workspace: Path, scripts_dir: Path):
    """
    執行 scripts 目錄下的 download.py，並傳入 --workspace 參數。
    """
    download_py = scripts_dir / "download.py"
    if not download_py.exists():
        sys.exit(f"找不到 {download_py}")
    # 使用目前的 Python 執行環境呼叫 download.py
    cmd = [sys.executable, str(download_py), "--workspace", str(workspace)]
    print(f"執行下載腳本: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit("download.py 執行失敗，請確認錯誤訊息。")

def build_executables(scripts_dir: Path):
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

def copy_exes_to_workspace(scripts_dir: Path, workspace: Path):
    """
    將 scripts 目錄下 dist 資料夾內的所有 .exe 檔案複製到 workspace 中。
    """
    dist_dir = scripts_dir / "dist"
    if not dist_dir.exists():
        sys.exit("找不到打包後的 dist 目錄")
    for exe_file in dist_dir.glob("*.exe"):
        dest = workspace / exe_file.name
        print(f"複製 {exe_file.name} 到 {workspace}")
        shutil.copy(exe_file, dest)

def clean_scripts_directory(scripts_dir: Path):
    """
    刪除 scripts 目錄下，除 .py 和 .yml 以外的所有檔案與目錄。
    """
    for item in scripts_dir.iterdir():
        # 若是檔案且副檔名不是 .py 與 .yml
        if item.is_file() and item.suffix.lower() not in [".py", ".yml"]:
            print(f"刪除檔案: {item.name}")
            item.unlink()
        # 若是目錄，全部刪除
        elif item.is_dir():
            print(f"刪除目錄: {item.name}")
            shutil.rmtree(item)

def zip_workspace(workspace: Path, version: str):
    """
    將 workspace 目錄下的所有檔案與子目錄打包成一份 VSCode4z-<version>.zip。
    壓縮檔將存放在 workspace 目錄下。
    """
    zip_name = workspace / f"VSCode4z-{version}.zip"
    print(f"開始建立壓縮檔: {zip_name}")
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(workspace):
            for file in files:
                file_path = Path(root) / file
                # 為了在 zip 中保留相對路徑，計算相對於 workspace 的路徑
                relative_path = file_path.relative_to(workspace)
                zipf.write(file_path, arcname=str(relative_path))
    print(f"壓縮檔建立完成: {zip_name}")

def main():
    args = parse_arguments()
    version = args.version
    
    # 取得 build.py 腳本所在目錄
    script_dir = get_script_dir()
    print(f"建置腳本所在目錄: {script_dir}")
    
    # 若使用者有透過 --workspace 指定，則使用該目錄，否則預設為 script_dir
    workspace = Path(args.workspace).resolve() if args.workspace else script_dir
    print(f"使用的工作區: {workspace}")
    
    # 取得 scripts 目錄，預期其在 build.py 所在目錄下的 scripts 子目錄
    scripts_dir = script_dir / "scripts"
    if not scripts_dir.exists():
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
    zip_workspace(workspace, version)

if __name__ == "__main__":
    main()
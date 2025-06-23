#!/usr/bin/env python3
"""
程式名稱: download.py
開發單位: IBM Expert Labs
開發人員: nicholas.yahung.chien@ibm.com
日期: 2025/06/20
版本: 2.2.1

說明:
1. 根據 extensions.yml 清單下載 VSCode 擴充功能包

使用方式:
使用前請確認 Python 執行環境中有必要的模組。
"""

import os
import sys
import argparse
import fnmatch
from urllib.parse import urlparse
import re
import requests
import yaml
from pathlib import Path
from file_utils import cleanup_directory_match

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

def load_extensions_config(scripts_dir):
    """
    載入 extensions.yml 設定檔，並回傳擴充功能包資訊。
    """
    extensions_yml_path = os.path.join(scripts_dir, "extensions.yml")
    if not os.path.exists(extensions_yml_path):
        sys.exit(f"找不到設定檔: {extensions_yml_path}")
    with open(extensions_yml_path, "r", encoding="utf-8") as f:
        extensions = yaml.safe_load(f)
    return extensions

def determine_filename(response, pattern, default_filename):
    """
    根據下載的 HTTP response、pattern 與 default_filename 決定下載檔案的檔名，優先順序如下：
      1. 如果有 Content-Disposition，則以其中的 filename 為主。
      2. 如果下載連結（最終 response.url）的最後檔名符合 pattern，則以該檔案名稱為主。
      3. 否則，根據 default_filename 預設檔名。
    """
    # 優先順序 1：檢查 Content-Disposition
    content_disposition = response.headers.get("Content-Disposition", "")
    if content_disposition:
        match = re.search(r'filename="?([^";]+)"?', content_disposition)
        if match:
            filename = match.group(1)
            print(f"根據 Content-Disposition 取得檔名：{filename}")
            return filename
    
    # 優先順序 2：根據 response.url 取得最後部分檔名，並檢查是否符合 pattern
    parsed = urlparse(response.url)
    tail_filename = os.path.basename(parsed.path)
    if tail_filename and fnmatch.fnmatch(tail_filename, pattern):
        print(f"根據連結尾端檔名符合 pattern，取得檔名：{tail_filename}")
        return tail_filename

    # 優先順序 3：回傳根據 pattern 與 version 組合出的預設檔名
    print(f"使用預設規則產生檔名：{default_filename}")
    return default_filename

def download_file(url, dest_directory, filename_pattern, possible_filename):
    """
    根據 URL 下載檔案，並根據 response header 中的 Content-Disposition 設定檔案名稱，
    若找不到檔名則使用 URL 的最後一段作為檔案名稱。在儲存前若檔案已存在，則先刪除。
    """
    try:
        response = requests.get(url)
        if response.status_code == 200:
            # 決定檔案名稱
            filename = determine_filename(response, filename_pattern, possible_filename)
            # 組合下載目的地的完整路徑
            dest_path = os.path.join(dest_directory, filename)
            
            # 如果檔案已存在，就先刪除
            cleanup_directory_match(dest_directory, filename)
            
            # 寫入檔案
            with open(dest_path, "wb") as f:
                f.write(response.content)
            print(f"下載成功，檔案已儲存為: {dest_path}")
        else:
            print(f"下載失敗：{url} (HTTP 狀態：{response.status_code})")
    except Exception as e:
        print(f"下載過程中發生錯誤：{e}")

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
    
    # 載入 extensions.yml 設定檔
    extensions = load_extensions_config(os.path.join(workspace, "scripts"))
        
    # 根據設定檔逐一下載 vsix 檔案
    for publisher, ext_list in extensions.items():
        for ext_dict in ext_list:
            # 這裡假設每個元素都是只有一筆 {extension: version} 的字典
            for ext_name, version in ext_dict.items():
                # 組成下載 URL
                url = (
                    f"https://marketplace.visualstudio.com/_apis/public/gallery/publishers/"
                    f"{publisher}/vsextensions/{ext_name}/{version}/vspackage"
                )
                print(f"開始下載：{url}")
                # 產生檔案名稱，例如 ibm.zopendebug-5.4.0.vsix
                file_name = f"{publisher}.{ext_name}-{version}.vsix"
                download_file(url, os.path.join(workspace, "extensions"), "*.vsix", file_name)

if __name__ == "__main__":
    main()

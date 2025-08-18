#!/usr/bin/env python3
"""
IBM VSCode for Z Development Environment Setup Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 2.6.0
日期: 2025/01/13

說明:
1. 根據 extensions.yml 清單下載 VSCode 擴充功能包
2. 根據 pip.yml 清單下載 pip 套件
3. 根據 tools.yml 清單下載工具包

使用方式:
使用前請確認 Python 執行環境中有必要的模組。

更新記錄:
- v2.6.0: 優化下載流程，改善配置載入和檔案管理
- v2.5.0: 優化檔案下載邏輯，改善檔案名稱決定機制
- v2.4.11: 重構下載流程，提升檔案管理效能
- v2.3.0: 新增檔案清理功能，改善下載流程
- v2.2.1: 初始版本，提供基本的檔案下載功能
"""

import os
import argparse
import fnmatch
from urllib.parse import urlparse
import re
import requests
from pathlib import Path
from utils.file_utils import cleanup_directory_match
from utils.path_utils import compose_folder_path, get_script_dir
import subprocess

# 導入我們的設定檔工具模組
from configs import (
    load_tools_config,
    load_pip_config,
    load_extensions_config
)

DEFAULT_OVSX_REGISTRY = "https://open-vsx.org"

# -------------------------------
#  功能函式
# -------------------------------
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

def download_file(url, dest_directory, filename_pattern, default_filename=""):
    """
    根據 URL 下載檔案，並根據 response header 中的 Content-Disposition 設定檔案名稱，
    若找不到檔名則使用 URL 的最後一段作為檔案名稱。在儲存前若檔案已存在，則先刪除。
    """
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            # 決定檔案名稱
            filename = determine_filename(response, filename_pattern, default_filename)
            # 組合下載目的地的完整路徑
            dest_path = os.path.join(dest_directory, filename)
            
            # 如果檔案已存在，就先刪除
            if os.path.exists(os.path.join(dest_directory, filename)):
                os.remove(os.path.join(dest_directory, filename))
            
            # 寫入檔案
            with open(dest_path, "wb") as f:
                f.write(response.content)
            print(f"下載成功，檔案已儲存為: {dest_path}")
            return True
        else:
            print(f"下載失敗：{url} (HTTP 狀態：{response.status_code})")
            return False
    except Exception as e:
        print(f"下載過程中發生錯誤：{e}")
        return False


def vsix_url_openvsx(base, publisher, ext_name, version):
    base = base.rstrip('/')
    return f"{base}/api/{publisher}/{ext_name}/{version}/file/{publisher}.{ext_name}-{version}.vsix"


def download_vsix_with_sources(publisher, ext_name, version, dest_directory, registry_base):
    """依序嘗試：本地 OpenVSX -> 遠端 OpenVSX -> VS Code Marketplace。"""
    desired_filename = f"{publisher}.{ext_name}-{version}.vsix"
    pattern = "*.vsix"

    # 1) 若使用者指定了自訂 registry，先嘗試該 registry
    used_local = registry_base and registry_base.rstrip('/') != DEFAULT_OVSX_REGISTRY
    if used_local:
        url_local = vsix_url_openvsx(registry_base, publisher, ext_name, version)
        print(f"嘗試從本地 OpenVSX 下載：{url_local}")
        if download_file(url_local, dest_directory, pattern, desired_filename):
            return True
        print("本地 OpenVSX 下載失敗，改用遠端 OpenVSX。")

    # 2) 遠端 OpenVSX
    url_remote = vsix_url_openvsx(DEFAULT_OVSX_REGISTRY, publisher, ext_name, version)
    print(f"嘗試從遠端 OpenVSX 下載：{url_remote}")
    if download_file(url_remote, dest_directory, pattern, desired_filename):
        return True
    print("遠端 OpenVSX 下載失敗，改用 VS Code Marketplace。")

    # 3) VS Code Marketplace（原本邏輯）
    url_marketplace = (
        f"https://marketplace.visualstudio.com/_apis/public/gallery/publishers/"
        f"{publisher}/vsextensions/{ext_name}/{version}/vspackage"
    )
    print(f"嘗試從 Marketplace 下載：{url_marketplace}")
    return download_file(url_marketplace, dest_directory, pattern, desired_filename)

# -------------------------------
# 主流程
# -------------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(description="Install script with optional auto-confirmation.")
    parser.add_argument("-y", "--yes", action="store_true", help="自動執行所有步驟，不須等待使用者確認。")
    parser.add_argument("--workspace", type=str, help="指定工作區目錄，預設為腳本檔所在路徑。")
    parser.add_argument(
        "--ovsx-registry",
        type=str,
        default=DEFAULT_OVSX_REGISTRY,
        help="OpenVSX Registry base URL。若提供自訂（例如本地端），將優先嘗試該來源；未提供則預設使用遠端。"
    )
    return parser.parse_args()

def main():
    args = parse_arguments()
    # 若使用者有指定 --workspace 則使用該目錄，否則預設為 script_dir 的上層
    workspace = Path(args.workspace).resolve() if args.workspace else Path(get_script_dir()).parent.resolve()
    os.chdir(workspace)
    print("目前工作目錄設定為：", workspace)

    # 載入 tools.yml 設定檔
    tools = load_tools_config()
    
    # 載入 extensions.yml 設定檔
    extensions = load_extensions_config()

    # 載入 pip.yml 設定檔
    pip = load_pip_config()
        
    # 根據設定檔逐一下載 vsix 檔案
    cleanup_directory_match(os.path.join(workspace, "extensions"), "*.vsix")
    for publisher, ext_list in extensions.items():
        for ext_dict in ext_list:
            # 這裡假設每個元素都是只有一筆 {extension: version} 的字典
            for ext_name, version in ext_dict.items():
                print(f"開始下載 {publisher}.{ext_name}@{version}")
                ok = download_vsix_with_sources(publisher, ext_name, version, os.path.join(workspace, "extensions"), args.ovsx_registry)
                if not ok:
                    print(f"❌ 下載失敗：{publisher}.{ext_name}@{version}")
                else:
                    print(f"✅ 下載完成：{publisher}.{ext_name}@{version}")
    
    # 下載 pip 套件
    cleanup_directory_match(os.path.join(workspace, "pywhls"), "*.whl")
    subprocess.run(["pip", "download", *(pip["whls"]), "--dest", os.path.join(workspace, "pywhls")])

    # 針對每個有連結設定的工具進行下載
    for tool, config in tools.items():
        print(f"\n下載工具：{tool}")
        link = config["source"]
        print(f"開始下載：{link}")
        # 設定預設檔名 (若無法從下載連結決定)，例如 "python_3.13.3.0.zip"
        filename_pattern = f"{config['pattern']}.{config['type']}"
        default_filename = filename_pattern.replace('*', '')
        # 將 dir 拆解後用 os.path.join 組合
        dest_directory = compose_folder_path(workspace, config["dir"])
        cleanup_directory_match(dest_directory, f"*.{config['type']}")
        download_file(link, dest_directory, filename_pattern, default_filename)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
IBM VSCode for Z Development Environment Setup Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 2.9.0
日期: 2025/11/26

說明:
1. 根據 extensions.yml 清單下載 VSCode 擴充功能包
2. 根據 pip.yml 清單下載 pip 套件
3. 根據 npm.yml 清單下載 npm 套件
4. 根據 tools.yml 清單下載工具包

使用方式:
使用前請確認 Python 執行環境中有必要的模組。

更新記錄:
- v2.9.0: 參考 install.py 架構，將下載流程分割為數個階段 (Phase)，並加入確認步驟
- v2.8.1: 完善平台特定下載支援，為 OpenVSX 和 VS Code Marketplace 都添加 win32-x64 平台優先下載邏輯，使用安全的 URL 構建方式
- v2.8.0: 新增平台特定下載支援，確保 VS Code Marketplace 下載時指定 win32-x64 平台版本
- v2.7.0: 改善 OpenVSX 下載邏輯，檢測 HTML 網頁回應並自動切換至 VS Code Marketplace
- v2.6.0: 優化下載流程，改善配置載入和檔案管理
- v2.5.0: 優化檔案下載邏輯，改善檔案名稱決定機制
- v2.4.11: 重構下載流程，提升檔案管理效能
- v2.3.0: 新增檔案清理功能，改善下載流程
- v2.2.1: 初始版本，提供基本的檔案下載功能
"""

import os
import argparse
import fnmatch
import functools
from urllib.parse import urlparse, urlencode
import re
import requests
from pathlib import Path
from utils.file_utils import cleanup_directory_match
from utils.path_utils import compose_folder_path, get_script_dir
import subprocess
import shutil
import sys
import time
import threading

# 導入我們的設定檔工具模組
from configs import (
    load_tools_config,
    load_pip_config,
    load_extensions_config,
    load_npm_config
)

# 導入我們的互動工具模組
from utils.message_utils import (
    pause_if_needed
)

DEFAULT_OVSX_REGISTRY = "https://open-vsx.org"

# -------------------------------
#  進度顯示類別
# -------------------------------
class Spinner:
    """簡單的 spinner 動畫類別"""
    def __init__(self, message="下載中"):
        self.message = message
        self.spinner_chars = "|/-\\"
        self.running = False
        self.thread = None
        
    def start(self):
        """開始顯示 spinner"""
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self):
        """停止顯示 spinner"""
        self.running = False
        if self.thread:
            self.thread.join()
        # 清除 spinner 行
        sys.stdout.write('\r' + ' ' * (len(self.message) + 10) + '\r')
        sys.stdout.flush()
        
    def _spin(self):
        """spinner 動畫循環"""
        i = 0
        while self.running:
            sys.stdout.write(f'\r{self.message} {self.spinner_chars[i % len(self.spinner_chars)]}')
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1

def format_size(size_bytes):
    """格式化檔案大小顯示"""
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f} {size_names[i]}"

def clear_progress_line():
    """清空當前行並回到行首"""
    sys.stdout.write('\r' + ' ' * 100 + '\r')
    sys.stdout.flush()

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
    spinner = None
    try:
        # 使用更詳細的 timeout 設定：(連接超時, 讀取超時)
        # 連接超時：30秒，讀取超時：60秒（1分鐘）
        print(f"開始下載：{url}")
        spinner = Spinner("連接中")
        spinner.start()
        
        response = requests.get(url, timeout=(30, 60), stream=True)
        spinner.stop()
        
        if response.status_code == 200:
            # 檢查下載內容是否為 HTML 網頁而非實際檔案
            content_type = response.headers.get('Content-Type', '').lower()
            
            # 先讀取一小部分內容來檢查是否為 HTML
            first_chunk = next(response.iter_content(chunk_size=1000), b'')
            content_start = first_chunk.decode('utf-8', errors='ignore').lower()
            
            # 如果內容類型是 HTML 或內容包含 HTML 標籤，則認為是網頁而非檔案
            if ('text/html' in content_type or 
                '<!doctype html>' in content_start or 
                '<html' in content_start or
                '<title>' in content_start):
                print(f"下載內容為 HTML 網頁，非實際檔案：{url}")
                return False
            
            # 決定檔案名稱
            filename = determine_filename(response, filename_pattern, default_filename)
            # 組合下載目的地的完整路徑
            dest_path = os.path.join(dest_directory, filename)
            
            # 如果檔案已存在，就先刪除
            if os.path.exists(os.path.join(dest_directory, filename)):
                os.remove(os.path.join(dest_directory, filename))
            
            # 獲取檔案總大小（如果可用）
            total_size = response.headers.get('content-length')
            if total_size:
                total_size = int(total_size)
            else:
                total_size = None
            
            # 使用流式下載，避免大文件一次性載入記憶體
            downloaded_size = 0
            with open(dest_path, "wb") as f:
                # 先寫入已讀取的第一個 chunk
                f.write(first_chunk)
                downloaded_size += len(first_chunk)
                
                # 顯示初始進度
                clear_progress_line()
                if total_size:
                    progress = (downloaded_size / total_size) * 100
                    sys.stdout.write(f"下載進度: {progress:.1f}% ({format_size(downloaded_size)}/{format_size(total_size)})")
                else:
                    sys.stdout.write(f"已下載: {format_size(downloaded_size)}")
                sys.stdout.flush()
                
                # 繼續下載剩餘內容
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # 過濾掉 keep-alive 的空 chunk
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 更新進度顯示
                        clear_progress_line()
                        if total_size:
                            progress = (downloaded_size / total_size) * 100
                            sys.stdout.write(f"下載進度: {progress:.1f}% ({format_size(downloaded_size)}/{format_size(total_size)})")
                        else:
                            sys.stdout.write(f"已下載: {format_size(downloaded_size)}")
                        sys.stdout.flush()
            
            print()  # 換行
            print(f"下載成功，檔案已儲存為: {dest_path}")
            return True
        else:
            print(f"下載失敗：{url} (HTTP 狀態：{response.status_code})")
            return False
    except requests.exceptions.Timeout:
        if spinner:
            spinner.stop()
        print(f"下載逾時：{url}")
        return False
    except requests.exceptions.ConnectionError:
        if spinner:
            spinner.stop()
        print(f"連接錯誤：{url}")
        return False
    except KeyboardInterrupt:
        if spinner:
            spinner.stop()
        print(f"下載被用戶中斷：{url}")
        return False
    except Exception as e:
        if spinner:
            spinner.stop()
        print(f"下載過程中發生錯誤：{e}")
        return False


def vsix_url_openvsx(base, publisher, ext_name, version, platform=None):
    """構建 OpenVSX 的 VSIX 下載 URL，支援平台特定版本"""
    base = base.rstrip('/')
    if platform:
        # 嘗試平台特定的檔案名稱
        return f"{base}/api/{publisher}/{ext_name}/{version}/file/{publisher}.{ext_name}-{version}-{platform}.vsix"
    else:
        # 預設的通用版本
        return f"{base}/api/{publisher}/{ext_name}/{version}/file/{publisher}.{ext_name}-{version}.vsix"


def download_vsix_with_sources(publisher, ext_name, version, dest_directory, registry_base):
    """依序嘗試：本地 OpenVSX (平台特定) -> 本地 OpenVSX (通用) -> 遠端 OpenVSX (平台特定) -> 遠端 OpenVSX (通用) -> VS Code Marketplace (平台特定) -> VS Code Marketplace (通用)。"""
    desired_filename = f"{publisher}.{ext_name}-{version}.vsix"
    pattern = "*.vsix"
    target_platform = "win32-x64"

    # 1) 若使用者指定了自訂 registry，先嘗試該 registry 的平台特定版本
    used_local = registry_base and registry_base.rstrip('/') != DEFAULT_OVSX_REGISTRY
    if used_local:
        # 嘗試平台特定版本
        url_local_platform = vsix_url_openvsx(registry_base, publisher, ext_name, version, target_platform)
        print(f"嘗試從本地 OpenVSX 下載（{target_platform} 平台）：{url_local_platform}")
        if download_file(url_local_platform, dest_directory, pattern, desired_filename):
            return True
        
        # 嘗試通用版本
        url_local = vsix_url_openvsx(registry_base, publisher, ext_name, version)
        print(f"嘗試從本地 OpenVSX 下載（通用版本）：{url_local}")
        if download_file(url_local, dest_directory, pattern, desired_filename):
            return True
        print("本地 OpenVSX 下載失敗（逾時或返回網頁），改用遠端 OpenVSX。")

    # 2) 遠端 OpenVSX - 先嘗試平台特定版本
    url_remote_platform = vsix_url_openvsx(DEFAULT_OVSX_REGISTRY, publisher, ext_name, version, target_platform)
    print(f"嘗試從遠端 OpenVSX 下載（{target_platform} 平台）：{url_remote_platform}")
    if download_file(url_remote_platform, dest_directory, pattern, desired_filename):
        return True
    
    # 嘗試通用版本
    url_remote = vsix_url_openvsx(DEFAULT_OVSX_REGISTRY, publisher, ext_name, version)
    print(f"嘗試從遠端 OpenVSX 下載（通用版本）：{url_remote}")
    if download_file(url_remote, dest_directory, pattern, desired_filename):
        return True
    print("遠端 OpenVSX 下載失敗（逾時或返回網頁），改用 VS Code Marketplace。")

    # 3) VS Code Marketplace - 先嘗試平台特定版本
    marketplace_base = f"https://marketplace.visualstudio.com/_apis/public/gallery/publishers/{publisher}/vsextensions/{ext_name}/{version}/vspackage"
    marketplace_params = {"targetPlatform": target_platform}
    url_marketplace_platform = f"{marketplace_base}?{urlencode(marketplace_params)}"
    print(f"嘗試從 VS Code Marketplace 下載（{target_platform} 平台）：{url_marketplace_platform}")
    if download_file(url_marketplace_platform, dest_directory, pattern, desired_filename):
        return True
    
    # 最後嘗試通用版本
    print(f"嘗試從 VS Code Marketplace 下載（通用版本）：{marketplace_base}")
    return download_file(marketplace_base, dest_directory, pattern, desired_filename)

# -------------------------------
# 以下定義各階段流程（利用 decorator 包裝）
# -------------------------------

def confirm_phase(message):
    """
    decorator：在執行被裝飾的函式前詢問使用者是否執行，
    輸入 Y/y/Enter 執行，輸入 N/n 跳過。
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, auto_continue=False, **kwargs):
            if auto_continue:
                print(f"{message}（已自動繼續）。\n")
                return func(*args, auto_continue=auto_continue, **kwargs)
            
            while True:
                choice = input(f"{message} [Y/n]? ").strip().lower()
                if choice in ('', 'y', 'yes'):
                    return func(*args, auto_continue=auto_continue, **kwargs)
                elif choice in ('n', 'no'):
                    print("使用者選擇跳過此步驟。\n")
                    return
                else:
                    print("請輸入 Y (執行) 或 n (跳過)。")
        return wrapper
    return decorator

@confirm_phase("【步驟 1】下載 VSCode 擴充功能包：是否下載 extensions.yml 中的擴充功能")
def phase1_download_extensions(extensions, workspace, ovsx_registry, auto_continue=False):
    # 根據設定檔逐一下載 vsix 檔案
    cleanup_directory_match(os.path.join(workspace, "extensions"), "*.vsix")
    for publisher, ext_list in extensions.items():
        for ext_dict in ext_list:
            # 這裡假設每個元素都是只有一筆 {extension: version} 的字典
            for ext_name, version in ext_dict.items():
                print(f"開始下載 {publisher}.{ext_name}@{version}")
                ok = download_vsix_with_sources(publisher, ext_name, version, os.path.join(workspace, "extensions"), ovsx_registry)
                if not ok:
                    print(f"❌ 下載失敗：{publisher}.{ext_name}@{version}")
                else:
                    print(f"✅ 下載完成：{publisher}.{ext_name}@{version}")
    print("VSCode 擴充功能包下載完成。\n")

@confirm_phase("【步驟 2】下載 Python 套件：是否下載 pip.yml 中的套件")
def phase2_download_pip_packages(pip, workspace, auto_continue=False):
    # 下載 pip 套件
    cleanup_directory_match(os.path.join(workspace, "pywhls"), "*.whl")
    try:
        subprocess.run(["pip", "download", *(pip["whls"]), "--dest", os.path.join(workspace, "pywhls")], check=True)
        print("Python 套件下載完成。\n")
    except subprocess.CalledProcessError as e:
        print(f"Python 套件下載失敗: {e}")

@confirm_phase("【步驟 3】下載 Node.js 套件：是否下載 npm.yml 中的套件")
def phase3_download_npm_packages(npm, workspace, auto_continue=False):
    # 下載 npm 套件離線快取（放置於 workspace\npm-cache）
    cleanup_directory_match(os.path.join(workspace, "npm-cache"), "*")
    npm_cache_dir = os.path.join(workspace, "npm-cache")
    os.makedirs(npm_cache_dir, exist_ok=True)

    # 解析系統中的 npm 可執行檔位置
    npm_cmd = shutil.which("npm") or (shutil.which("npm.cmd") if os.name == "nt" else None)
    if not npm_cmd:
        print("找不到 npm 可執行檔，請確認已安裝並且在 PATH。")
        return

    # 建立臨時安裝目錄，避免污染工具目錄
    npm_tmp_dir = os.path.join(npm_cache_dir, "npm-tmp")
    os.makedirs(npm_tmp_dir, exist_ok=True)

    # 逐一針對 npm.yml 中的群組與套件版本執行 npm install 以填充快取
    for scope, pkgs in npm.items():
        for entry in pkgs:
            # entry 為 {name: version}
            for name, version in entry.items():
                pkg_spec = f"@{scope}/{name}@{version}" if scope != "global" else f"{name}@{version}"
                print(f"準備快取 npm 套件：{pkg_spec}")
                try:
                    # 使用 --cache 指向 workspace\npm-cache，--prefer-online 以確保從線上抓取並寫入快取
                    subprocess.run([
                        npm_cmd,
                        "install",
                        "--no-fund",
                        "--no-audit",
                        "--no-save",
                        "--no-package-lock",
                        "--prefer-online",
                        f"--cache={npm_cache_dir}",
                        pkg_spec
                    ], cwd=npm_tmp_dir, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"快取 {pkg_spec} 發生錯誤：{e}")
                except Exception as e:
                    print(f"快取 {pkg_spec} 發生未預期錯誤：{e}")

    # 下載完成後，刪除臨時安裝目錄
    try:
        shutil.rmtree(npm_tmp_dir, ignore_errors=True)
    except Exception:
        pass
    print("Node.js 套件下載完成。\n")

@confirm_phase("【步驟 4】下載工具包：是否下載 tools.yml 中的工具")
def phase4_download_tools(tools, workspace, auto_continue=False):
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
    print("工具包下載完成。\n")

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

    # 載入工具設定檔
    tools = load_tools_config()
    # 載入擴充功能設定檔
    extensions = load_extensions_config()
    # 載入 pip 設定檔
    pip = load_pip_config()
    # 載入 npm 設定檔
    npm = load_npm_config()
        
    # 1. 下載擴充功能
    if extensions:
        phase1_download_extensions(extensions, workspace, args.ovsx_registry, auto_continue=args.yes)
    else:
        print("跳過擴充功能下載步驟（因未載入設定檔）。")
    
    # 2. 下載 PIP 套件
    if pip:
        phase2_download_pip_packages(pip, workspace, auto_continue=args.yes)
    else:
        print("跳過 Python 套件下載步驟（因未載入設定檔）。")
    
    # 3. 下載 NPM 套件
    if npm:
        phase3_download_npm_packages(npm, workspace, auto_continue=args.yes)
    else:
        print("跳過 Node.js 套件下載步驟（因未載入設定檔）。")
    
    # 4. 下載其他工具
    if tools:
        phase4_download_tools(tools, workspace, auto_continue=args.yes)
    else:
        print("跳過工具包下載步驟（因未載入設定檔）。")

    print("所有下載任務完成。")

if __name__ == "__main__":
    main()

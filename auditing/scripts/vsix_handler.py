#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VSIX 處理模組
包含 VSIX 檔案的下載、解壓縮和搜尋功能
"""

import glob
import os
import shutil
import zipfile
from utils import log, run, require_bin


def find_local_vsix(publisher_ext: str, version: str, extensions_dir: str) -> str:
    """在擴充功能目錄中尋找本地 VSIX 檔案。"""
    # 嘗試不同的命名模式以進行靈活匹配
    patterns = [
        # 先嘗試完全匹配
        f"{publisher_ext}-{version}.vsix",
        f"{publisher_ext.replace('.', '_')}-{version}.vsix",
        f"{publisher_ext}@{version}.vsix",
        
        # 靈活模式，允許版本號和 .vsix 之間有任何字元
        f"{publisher_ext}-{version}*.vsix",
        f"{publisher_ext.replace('.', '_')}-{version}*.vsix",
        f"{publisher_ext}@{version}*.vsix",
        
        # 同時嘗試將發布者名稱中的點替換為底線
        f"{publisher_ext.replace('.', '_')}-{version}*.vsix",
        f"{publisher_ext.replace('.', '_')}@{version}*.vsix",
        
        # 嘗試不同的分隔符模式
        f"{publisher_ext}_{version}*.vsix",
        f"{publisher_ext.replace('.', '_')}_{version}*.vsix",
    ]
    
    for pattern in patterns:
        # 使用 glob 尋找符合模式的檔案
        search_pattern = os.path.join(extensions_dir, pattern)
        matching_files = glob.glob(search_pattern)
        
        if matching_files:
            # 回傳第一個匹配項
            return matching_files[0]
    
    # 如果沒有模式匹配，嘗試更靈活的搜尋
    # 尋找包含發布者名稱和版本號的檔案
    try:
        for filename in os.listdir(extensions_dir):
            if filename.endswith('.vsix'):
                # 檢查檔案名是否同時包含發布者名稱和版本號
                publisher_clean = publisher_ext.replace('.', '_')
                if (publisher_ext in filename or publisher_clean in filename) and version in filename:
                    return os.path.join(extensions_dir, filename)
    except Exception as e:
        log(f"警告: 靈活 VSIX 搜尋期間發生錯誤: {e}")
    
    return None


def vsix_url_openvsx(publisher: str, ext: str, version: str, registry_base: str) -> str:
    """生成 OpenVSX 的 VSIX 下載 URL。"""
    # https://open-vsx.org/api/{publisher}/{extension}/{version}/file/{publisher}.{extension}-{version}.vsix
    base = registry_base.rstrip("/")
    return f"{base}/api/{publisher}/{ext}/{version}/file/{publisher}.{ext}-{version}.vsix"


def download_vsix_http(publisher_ext: str, version: str, out_path: str, registry_base: str, requests_module) -> bool:
    """使用 HTTP 下載 VSIX 檔案。"""
    if requests_module is None:
        return False
    publisher, ext = publisher_ext.split(".", 1)
    url = vsix_url_openvsx(publisher, ext, version, registry_base)
    log(f"嘗試 HTTP 下載: {url}")
    try:
        with requests_module.get(url, stream=True, timeout=60) as r:
            if r.status_code != 200:
                log(f"HTTP 下載失敗: HTTP {r.status_code}")
                return False
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as e:
        log(f"HTTP 下載錯誤: {e}")
        return False


def download_vsix_ovsx(publisher_ext: str, version: str, out_path: str, registry_base: str, bin_ovsx: str) -> None:
    """使用 npx ovsx 下載 VSIX 檔案。"""
    # npx ovsx get publisher.extension --version X --registryUrl ... -o path
    cmd = f'{bin_ovsx} get {publisher_ext} --version {version} --registryUrl {registry_base} --out "{out_path}"'
    run(cmd, check=True)


def unzip_vsix(vsix_path: str, dest_dir: str) -> None:
    """解壓縮 VSIX 檔案。"""
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    
    # 檢查檔案是否為有效的 ZIP 檔案
    try:
        with zipfile.ZipFile(vsix_path, "r") as zf:
            zf.extractall(dest_dir)
    except zipfile.BadZipFile:
        # 檢查是否為 HTML 錯誤頁面
        with open(vsix_path, "r", encoding="utf-8") as f:
            content = f.read(1000)  # 讀取前 1000 個字元
            if "<!DOCTYPE html>" in content or "<html" in content:
                raise RuntimeError(f"下載的檔案是 HTML 頁面，而非 VSIX 檔案。擴充功能可能在 OpenVSX 上不存在或需要認證。")
            else:
                raise RuntimeError(f"下載的檔案不是有效的 ZIP 檔案: {vsix_path}")


def find_package_json(ext_dir: str) -> str:
    """在 VSIX 中尋找 package.json 檔案。"""
    p1 = os.path.join(ext_dir, "extension", "package.json")
    p2 = os.path.join(ext_dir, "package.json")
    if os.path.exists(p1):
        return p1
    if os.path.exists(p2):
        return p2
    raise FileNotFoundError("在 VSIX 中找不到 package.json 檔案。")

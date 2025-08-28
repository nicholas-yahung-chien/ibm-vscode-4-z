#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工具函式模組
包含日誌、命令執行、檔案操作等基礎工具函式
"""

import hashlib
import os
import shutil
import subprocess
import time


def log(msg: str) -> None:
    """輸出帶時間戳的日誌訊息。"""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def run(cmd, capture=False, check=True, text=True):
    """執行命令；回傳 (代碼, 標準輸出)。"""
    if isinstance(cmd, str):
        shell = True
    else:
        shell = False
    
    # 確保 Windows 相容性的正確編碼
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    
    proc = subprocess.run(cmd, shell=shell, capture_output=capture, text=text, 
                         encoding='utf-8', errors='replace', env=env)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, proc.stdout, proc.stderr)
    return proc.returncode, (proc.stdout if capture else "")


def require_bin(name: str) -> None:
    """確保二進制檔案在 PATH 中或作為絕對路徑可用。"""
    # 檢查是否為絕對路徑
    if os.path.isabs(name):
        if not os.path.exists(name):
            raise RuntimeError(f"缺少二進制檔案: {name}")
        return
    
    # 檢查是否在 PATH 中
    if shutil.which(name.split()[0]) is None:
        raise RuntimeError(f"缺少二進制檔案: {name}")


def sha256_file(path) -> str:
    """計算檔案的 SHA256 雜湊值。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dirs(*dirs):
    """確保必要目錄存在。"""
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)


def clean_dirs(*dirs):
    """清理目錄：刪除現有目錄並重新建立。"""
    for dir_path in dirs:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                log(f"已刪除目錄: {dir_path}")
            except Exception as e:
                log(f"刪除目錄 {dir_path} 時發生錯誤: {e}")
        # 重新建立目錄
        os.makedirs(dir_path, exist_ok=True)

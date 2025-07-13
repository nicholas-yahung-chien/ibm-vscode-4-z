#!/usr/bin/env python3
"""
IBM VSCode for Z Development Environment Setup Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 2.6.0
日期: 2025/01/13

說明:
1. 提供 escape_backslashes 函式，將 Windows 路徑中的反斜線轉為程式碼中需要的跳脫字元格式。
2. 提供 get_script_dir 函式，取得腳本所在目錄。
3. 提供 compose_folder_path 函式，組合 workspace 與 path_parts 成為完整路徑。
4. 提供 get_latest_file 函式，在指定目錄中尋找與 pattern 相符的檔案，並根據修改時間由新至舊排序，回傳最新檔案名稱。
5. 提供 get_all_files_reversed_sorted 函式，回傳指定目錄中所有符合 pattern 的檔案清單，依名稱字典序倒序排列。
6. 提供 find_real_directory 函式，從起始資料夾向下遞迴搜尋，直到某資料夾中包含非 target_pattern 檔案，則視為「實體目錄」並回傳該路徑。
7. 提供 find_target_file_path_by_pattern 函式，從起始資料夾向下遞迴搜尋，找到某一個包含 target_pattern 的資料夾則回傳其路徑。
8. 提供 find_home_path 函式，從起始資料夾向下遞迴搜尋，找到某一個包含 target_file 的資料夾則回傳其路徑。
9. 提供 find_target_file_path 函式，從起始資料夾向下遞迴搜尋，找到某一個包含 target_file 的資料夾則回傳其路徑。

更新記錄:
- v2.6.0: 優化路徑處理邏輯，改善目錄結構處理
- v2.5.0: 優化路徑處理邏輯，改善目錄結構處理
- v2.4.11: 重構路徑管理功能，提升路徑解析效能
- v2.3.0: 新增路徑驗證功能，改善路徑處理安全性
- v2.2.1: 初始版本，提供基本的路徑操作功能
"""

import fnmatch
import os
import glob
import sys
from pathlib import Path

def escape_backslashes(path: str, for_regex: bool = False) -> str:
    """
    將 Windows 路徑中的反斜線轉為程式碼中需要的跳脫字元格式。
    """
    if for_regex:
        # 若 for_regex 為 True，則將路徑中的反斜線轉為跳脫字元格式，並將單反斜線轉為雙反斜線
        return escape_backslashes(path.replace("\\", "\\\\"))
    else:
        return path.replace("\\", "\\\\")

def get_script_dir():
    """
    若被 PyInstaller 打包，則使用 sys.executable 的目錄的上層作為腳本所在目錄；
    否則使用 __file__ 的目錄的上層。
    """
    # 取得腳本所在目錄（考慮是否為 PyInstaller 打包）
    if getattr(sys, 'frozen', False):
        # 取得 .exe 執行檔所在路徑的上層
        return Path(sys.executable).parent.parent.resolve()
    else:
        # 取得 .py 腳本所在路徑的上層
        return Path(__file__).parent.parent.resolve()

def compose_folder_path(workspace, sub_folder_path):
    """
    組合 workspace 與 path_parts 成為完整路徑。
    """
    return os.path.join(workspace, *(sub_folder_path.replace("\\", "/").split("/")))

def get_latest_file(directory, pattern):
    """
    在指定目錄中尋找與 pattern 相符的檔案，並根據修改時間由新至舊排序，回傳最新檔案名稱。
    找不到則回傳空字串。
    """
    search_path = os.path.join(directory, pattern)
    matched_files = glob.glob(search_path)
    if not matched_files:
        return ""
    matched_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    return os.path.basename(matched_files[0])

def get_all_files_reversed_sorted(directory, pattern):
    """
    回傳指定目錄中所有符合 pattern 的檔案清單，依名稱字典序倒序排列。
    找不到則回傳空 list。
    """
    search_path = os.path.join(directory, pattern)
    matched_files = glob.glob(search_path)
    if not matched_files:
        return []
    matched_files.sort(key=lambda f: os.path.basename(f), reverse=True)
    return matched_files

def find_real_directory(start_path, target_pattern):
    """
    從起始資料夾向下遞迴搜尋，直到某資料夾中包含非 target_pattern 檔案，則視為「實體目錄」並回傳該路徑。
    找不到則回傳 None。
    """
    for root, _, files in os.walk(os.path.abspath(start_path)):
        non_target_files = [f for f in files if not f.lower().endswith(target_pattern)]
        if non_target_files:
            return root
    return None

def find_target_file_path_by_pattern(start_path, target_pattern):
    """
    從起始資料夾向下遞迴搜尋，找到某一個包含 target_pattern 的資料夾則回傳其路徑。
    找不到則回傳 None。
    """
    for root, _, files in os.walk(os.path.abspath(start_path)):
        for file in files:
            if fnmatch.fnmatch(file, target_pattern):
                return os.path.join(root, file)
    return None

def find_home_path(start_path, target_file):
    """
    從起始資料夾向下遞迴搜尋，找到某一個包含 target_file 的資料夾則回傳其路徑。
    找不到則回傳 None。
    """
    for root, _, files in os.walk(os.path.abspath(start_path)):
        if any(f.lower() == target_file.lower() for f in files):
            return root
    return None

def find_target_file_path(start_path, target_file):
    """
    從起始資料夾向下遞迴搜尋，找到某一個包含 target_file 的資料夾則回傳其路徑。
    找不到則回傳 None。
    """
    for root, _, files in os.walk(os.path.abspath(start_path)):
        if any(f.lower() == target_file.lower() for f in files):
            return os.path.join(root, target_file)
    return None
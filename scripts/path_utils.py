#!/usr/bin/env python3
"""
程式名稱: path_utils.py
開發單位: IBM Expert Labs
開發人員: nicholas.yahung.chien@ibm.com
日期: 2025/06/20
版本: 2.2.1

說明:
1. 在指定目錄中尋找與 pattern 相符的檔案，並根據修改時間由新至舊排序，回傳最新檔案名稱。
2. 回傳指定目錄中所有符合 pattern 的檔案清單，依名稱字典序倒序排列。
3. 從起始資料夾向下遞迴搜尋，直到某資料夾中包含非 target_pattern 檔案，則視為「實體目錄」並回傳該路徑。
4. 從起始資料夾向下遞迴搜尋，找到某一個包含 target_file 的資料夾則回傳其路徑。
"""

import os
import glob

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

def find_home_path(start_path, target_file):
    """
    從起始資料夾向下遞迴搜尋，找到某一個包含 target_file 的資料夾則回傳其路徑。
    找不到則回傳 None。
    """
    for root, _, files in os.walk(os.path.abspath(start_path)):
        if any(f.lower() == target_file.lower() for f in files):
            return root
    return None
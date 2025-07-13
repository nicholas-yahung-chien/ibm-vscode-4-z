#!/usr/bin/env python3
"""
IBM VSCode for Z Development Environment Setup Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 2.6.0
日期: 2025/01/13

說明:
1. 提供 spinner 線程顯示訊息。
2. 提供解壓縮 zip 檔案的 spinner 線程。
3. 提供將資料夾內容複製至另一個資料夾的 spinner 線程。
4. 將資料夾內容搬移至另一個資料夾。
5. 清除資料夾中所有非指定副檔名檔案。
6. 提供檔案鎖定檢測和進程終止功能。
7. 提供安全的檔案和目錄刪除功能。

更新記錄:
- v2.6.0: 優化檔案鎖定檢測和進程終止功能，改善檔案操作流程
- v2.5.0: 新增檔案鎖定檢測和進程終止功能，改善刪除流程
- v2.4.11: 優化檔案處理邏輯，提升操作效能
- v2.3.0: 重構檔案管理功能，改善錯誤處理
- v2.2.1: 初始版本，提供基本的檔案操作功能
"""

import os
import shutil
import zipfile
import time
import sys
import threading
import glob
import fnmatch
import re

def spinner(stop_event, msg_startup, msg_running, msg_complete):
    """
    利用 spinner 線程顯示訊息。
    """
    spinner_chars = "|/-\\"
    idx = 0
    print(msg_startup, flush=True)
    while not stop_event.is_set():
        print(f"{msg_running}... {spinner_chars[idx % len(spinner_chars)]}", end='\r', flush=True)
        idx += 1
        time.sleep(0.2)
    sys.stdout.write("\r" + f"{msg_complete}！        \n")
    sys.stdout.flush()

def extract_zip_with_spinner(zip_path, extract_to):
    """
    利用 spinner 線程解壓縮 zip_path 至 extract_to 目錄中。
    """
    stop_event = threading.Event()
    spinner_thread = threading.Thread(
        target=spinner,
        args=(
            stop_event,
            f"開始解壓縮：{zip_path}\n目標：{extract_to}",
            "解壓縮中",
            "解壓縮完成"
        )
    )
    spinner_thread.start()
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(path=os.path.abspath(extract_to))
    stop_event.set()
    spinner_thread.join()

def copy_contents_to_with_spinner(source_dir, destination_dir):
    """
    利用 spinner 線程將 source_dir 複製至 destination_dir。
    """
    stop_event = threading.Event()
    spinner_thread = threading.Thread(
        target=spinner,
        args=(
            stop_event,
            f"開始複製：{source_dir}\n目標：{destination_dir}",
            "複製中",
            "複製完成"
        )
    )
    spinner_thread.start()
    try:
        shutil.copytree(os.path.abspath(source_dir), os.path.abspath(destination_dir))
    except Exception as e:
        print("複製過程中發生錯誤：", e)
    stop_event.set()
    spinner_thread.join()

def move_contents_up(parent_dir, target_dir):
    """
    若 parent_dir 底下存在符合 target_dir 的子資料夾（通常為解壓後嵌套的資料夾），
    則將其內容搬移到 parent_dir 中並刪除此空資料夾。
    """
    search_path = os.path.join(parent_dir, "" if not target_dir else os.path.basename(target_dir))
    if parent_dir == search_path:
        return
    dirs = glob.glob(search_path)
    if not dirs:
        return
    dirs.sort(key=lambda d: os.path.getmtime(d), reverse=True)
    bogus_folder = dirs[0]
    for item in os.listdir(bogus_folder):
        shutil.move(os.path.join(bogus_folder, item), os.path.join(os.path.abspath(parent_dir), item))
    os.rmdir(bogus_folder)
    print(f"已將 {bogus_folder} 中的內容搬移至 {parent_dir} 並刪除該資料夾。")

def safe_rmtree(path, retries=3, delay=1):
    """
    遞迴刪除目錄，若刪除失敗則重試。
    增加檔案權限檢查和更詳細的錯誤處理。
    """
    # 否則使用基本版本
    for attempt in range(retries):
        try:
            # 檢查目錄是否存在
            if not os.path.exists(path):
                print(f"目錄不存在，跳過刪除：{path}")
                return
            
            # 嘗試刪除目錄
            shutil.rmtree(path)
            print(f"成功刪除目錄：{path}")
            return
        except PermissionError as e:
            print(f"刪除目錄 {path} 發生權限錯誤 (嘗試 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                print(f"等待 {delay} 秒後重試...")
                time.sleep(delay)
            else:
                print(f"刪除目錄 {path} 失敗，已重試 {retries} 次。")
                print("建議：")
                print("1. 確認沒有其他程式正在使用該目錄中的檔案")
                print("2. 使用 --force-kill 參數終止相關進程")
                print("3. 手動關閉可能使用該目錄的應用程式")
        except OSError as e:
            print(f"刪除目錄 {path} 發生系統錯誤 (嘗試 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                print(f"等待 {delay} 秒後重試...")
                time.sleep(delay)
            else:
                print(f"刪除目錄 {path} 失敗，已重試 {retries} 次。")
        except Exception as e:
            print(f"刪除目錄 {path} 發生未知錯誤 (嘗試 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                print(f"等待 {delay} 秒後重試...")
                time.sleep(delay)
            else:
                print(f"刪除目錄 {path} 失敗，已重試 {retries} 次。")
    
    print(f"刪除目錄 {path} 最終失敗，已重試 {retries} 次。")

def safe_remove_file(file_path, retries=3):
    """
    安全地刪除檔案，包括處理檔案鎖定問題
    
    Args:
        file_path (str): 檔案路徑
        retries (int): 最大重試次數
        
    Returns:
        bool: 是否成功刪除
    """    
    for attempt in range(retries):
        try:
            if not os.path.exists(file_path):
                print(f"檔案不存在，跳過刪除：{file_path}")
                return True
            
            os.remove(file_path)
            print(f"成功刪除檔案：{file_path}")
            return True
            
        except PermissionError as e:
            print(f"刪除檔案 {file_path} 發生權限錯誤 (嘗試 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                print(f"等待 1 秒後重試...")
                time.sleep(1)
            else:
                print(f"刪除檔案 {file_path} 失敗，已重試 {retries} 次。")
                print("建議：")
                print("1. 確認沒有其他程式正在使用該檔案")
                print("2. 手動關閉可能使用該檔案的應用程式")
        except OSError as e:
            print(f"刪除檔案 {file_path} 發生系統錯誤 (嘗試 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(1)
        except Exception as e:
            print(f"刪除檔案 {file_path} 發生未知錯誤 (嘗試 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(1)
    
    print(f"刪除檔案 {file_path} 最終失敗，已重試 {retries} 次。")
    return False

def cleanup_directory_except(target_dir, except_pattern):
    """
    清除指定目錄中所有非 .<except_pattern> 檔的項目，包括所有檔案與子目錄。
    只保留副檔名為 .<except_pattern> 的檔案。
    使用增強的檔案刪除功能來處理鎖定問題。
    """
    if not os.path.exists(target_dir):
        print(f"目錄不存在：{target_dir}")
        return

    print(f"開始清理目錄：{target_dir}")
    for entry in os.listdir(target_dir):
        full_path = os.path.join(target_dir, entry)
        # 如果是檔案，且副檔名不是 <except_pattern>（忽略大小寫），則刪除該檔案
        if os.path.isfile(full_path):
            if not entry.lower().endswith(f"{except_pattern}"):
                if not safe_remove_file(full_path):
                    print(f"無法刪除檔案: {full_path}")
                else:
                    print(f"已刪除檔案: {full_path}")
        # 如果是目錄，則直接遞迴刪除整個目錄
        elif os.path.isdir(full_path):
            if not safe_rmtree(full_path):
                print(f"無法刪除目錄: {full_path}")
            else:
                print(f"已遞迴刪除目錄: {full_path}")
    print(f"目錄清理完成：{target_dir}\n")

def cleanup_directory_match(target_dir, pattern):
    """
    清除指定目錄中所有符合 .<pattern> 檔案的項目。
    """
    if not os.path.exists(target_dir):
        print(f"目錄不存在：{target_dir}")
        return
    
    print(f"開始清理目錄：{target_dir}")
    for entry in os.listdir(target_dir):
        full_path = os.path.join(target_dir, entry)
        # 如果是檔案，且副檔名符合 <pattern>（忽略大小寫），則刪除該檔案
        if os.path.isfile(full_path):
            if fnmatch.fnmatch(os.path.basename(full_path), pattern):
                if not safe_remove_file(full_path):
                    print(f"無法刪除檔案: {full_path}")
                else:
                    print(f"已刪除檔案: {full_path}")
    print(f"目錄清理完成：{target_dir}\n")

def replace_in_file(file_path, pattern, replacement):
    """讀取 file_path，利用正規表達式替換 pattern 為 replacement，並覆蓋回原檔案。"""
    print(f"於檔案 {file_path} 中進行字串取代 ...")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(pattern, replacement, content)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("取代完成。")
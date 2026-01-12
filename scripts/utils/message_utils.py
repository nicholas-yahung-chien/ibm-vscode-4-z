#!/usr/bin/env python3
"""
IBM VSCode for Z Development Environment Setup Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 2.6.0
日期: 2025/01/13

說明:
1. 顯示訊息等待使用者按下 Enter，若 auto_continue 為 True，則僅印出訊息後自動繼續。
2. 提供 decorator：在執行被裝飾的函式前顯示待確認訊息，並依 auto_continue 參數決定是否需要等待使用者確認。
3. 提供 spinner 執行 subprocess.run，在執行期間顯示等待訊息。
4. 提供使用者互動和進度顯示功能。

更新記錄:
- v2.6.0: 優化使用者介面，改善進度顯示和錯誤處理
- v2.5.0: 優化使用者介面，改善進度顯示和錯誤處理
- v2.4.11: 重構訊息處理邏輯，提升使用者體驗
- v2.3.0: 新增進度顯示功能，改善使用者互動
- v2.2.1: 初始版本，提供基本的訊息顯示功能
"""

import functools
import subprocess
import sys
import threading
import time

def run_with_spinner(cmd, description, env=None, cwd=None, timeout=None):
    """
    使用 spinner 執行 subprocess.run，在執行期間顯示等待訊息。
    
    Args:
        cmd: 要執行的命令列表
        description: 顯示的描述訊息
        env: 環境變數
        cwd: 工作目錄
        timeout: 超時時間
    
    Returns:
        subprocess.CompletedProcess 物件
    """
    stop_event = threading.Event()
    
    def spinner_thread():
        spinner_chars = "|/-\\"
        idx = 0
        print(f"開始執行：{description}")
        while not stop_event.is_set():
            print(f"執行中... {spinner_chars[idx % len(spinner_chars)]}", end='\r', flush=True)
            idx += 1
            time.sleep(0.2)
        sys.stdout.write("\r" + f"執行完成！{' ' * 20}\n")
        sys.stdout.flush()
    
    # 啟動 spinner 線程
    spinner_thread_obj = threading.Thread(target=spinner_thread)
    spinner_thread_obj.start()
    
    try:
        # 執行命令
        result = subprocess.run(
            cmd,
            text=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=cwd,
            timeout=timeout
        )
        return result
    except subprocess.CalledProcessError as e:
        # 停止 spinner 並顯示錯誤
        stop_event.set()
        spinner_thread_obj.join()
        print(f"執行失敗：{description}")
        print(f"錯誤代碼：{e.returncode}")
        if e.stdout:
            print(f"標準輸出：{e.stdout}")
        if e.stderr:
            print(f"錯誤輸出：{e.stderr}")
        raise
    except subprocess.TimeoutExpired as e:
        # 停止 spinner 並顯示超時錯誤
        stop_event.set()
        spinner_thread_obj.join()
        print(f"執行超時：{description}")
        raise
    finally:
        # 確保 spinner 停止
        stop_event.set()
        spinner_thread_obj.join()

def pause_if_needed(message, auto_continue=False):
    """顯示訊息等待使用者按下 Enter，若 auto_continue 為 True，則僅印出訊息後自動繼續"""
    if auto_continue:
        print(f"{message}（已自動繼續）。\n")
    else:
        input(f"{message}（請按下 Enter 鍵繼續）。\n")

def confirm_step(message):
    """
    decorator：在執行被裝飾的函式前顯示待確認訊息，
    並依 auto_continue 參數決定是否需要等待使用者確認。
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, auto_continue=False, **kwargs):
            pause_if_needed(message, auto_continue=auto_continue)
            return func(*args, auto_continue=auto_continue, **kwargs)
        return wrapper
    return decorator
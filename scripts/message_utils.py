#!/usr/bin/env python3
"""
程式名稱: message_utils.py
開發單位: IBM Expert Labs
開發人員: nicholas.yahung.chien@ibm.com
日期: 2025/06/20
版本: 2.2.1

說明:
1. 顯示訊息等待使用者按下 Enter，若 auto_continue 為 True，則僅印出訊息後自動繼續。
2. 提供 decorator：在執行被裝飾的函式前顯示待確認訊息，並依 auto_continue 參數決定是否需要等待使用者確認。
"""

import functools

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
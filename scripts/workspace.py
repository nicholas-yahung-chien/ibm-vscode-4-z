#!/usr/bin/env python3
"""
IBM VSCode for Z Development Environment Setup Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 2.6.0
日期: 2025/01/13

說明:
透過指令列依序要求使用者輸入環境參數，內容包括：
  1. 伺服器位置，存入變數 host。
  2. 帳號名稱，存入變數 user。
  3. 密碼，存入變數 password。
  4. 顯示選單讓使用者設定連線參數，其選項包括：
      1. 設定 zosmf：要求輸入連線 port，存入 zosmf_port。
      2. 設定 tso：要求輸入 tso 連線編碼，存入 tso_codepage。
      3. 設定 ssh：要求輸入 ssh 連線 port，存入 ssh_port。
      4. 設定 ftp：要求輸入 ftp 連線 port，存入 ftp_port。
      5. 設定 rse：依序要求輸入 rse 連線 port和連線編碼，存入 rse_port 與 rse_encoding。
      6. 設定 debug：要求輸入 zOpenDebug 連線 port，存入 debug_port。
      7. 結束 workspace 設定：離開選單並開始更新 workspace/zowe.config.json 檔案內容。

使用方式:
  - 用 host 取代檔案內所有 _HOST_ 字樣
  - 用 user 取代 _USER_
  - 用 password 取代 _PASSWORD_
  - 用 zosmf_port 取代 _ZOSMF_PORT_
  - 用 tso_codepage 取代 _TSO_CODEPAGE_
  - 用 ssh_port 取代 _SSH_PORT_
  - 用 ftp_port 取代 _FTP_PORT_
  - 用 rse_port 取代 _RSE_PORT_
  - 用 rse_encoding 取代 _RSE_ENCODING_
  - 用 debug_port 取代 _DEBUG_PORT_

更新記錄:
- v2.6.0: 優化使用者介面，改善參數驗證和錯誤處理
- v2.5.0: 優化使用者介面，改善參數驗證和錯誤處理
- v2.4.11: 重構設定流程，提升使用者體驗
- v2.3.0: 新增備份功能，改善設定檔管理
- v2.2.0: 初始版本，提供基本的 workspace 設定功能
"""

import os
import sys
import argparse
import shutil
import datetime
import getpass
from pathlib import Path
from utils.path_utils import get_script_dir
from utils.file_utils import replace_in_file

# -------------------------------
#  功能函式
# -------------------------------
def prompt_with_default(prompt_text, default_value):
    """
    顯示提示文字，若使用者沒有輸入，則回傳預設值
    """
    inp = input(prompt_text).strip()
    return inp if inp else default_value

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
    
    # 1. 請求使用者輸入基本參數：伺服器位置、帳號名稱、密碼
    host = input("請輸入伺服器位置: ").strip()
    # 檢查是否有任何輸入為空
    if not host:
        print("\n錯誤：所有基本參數皆必須輸入，請重新執行並提供完整資訊。")
        sys.exit(1)
    user = input("請輸入帳號名稱: ").strip()
    # 檢查是否有任何輸入為空
    if not user:
        print("\n錯誤：所有基本參數皆必須輸入，請重新執行並提供完整資訊。")
        sys.exit(1)
    password = getpass.getpass("請輸入密碼: ").strip()
    # 檢查是否有任何輸入為空
    if not password:
        print("\n錯誤：所有基本參數皆必須輸入，請重新執行並提供完整資訊。")
        sys.exit(1)
    
    # 設定連線參數變數（初始值為 None，後續根據選單更新）
    properties = {
        "zosmf": {"port": 443},
        "tso": {"codepage": 1047},
        "ssh": {"port": 22},
        "ftp": {"port": 21},
        "rse": {"port": 6800, "encoding": "IBM-937"},
        "debug": {"port": 8143}
    }
    
    # 4. 顯示選單，依使用者選擇設定連線參數
    while True:
        print("\n請選擇設定項目：")
        print("  1. 設定 zosmf")
        print("  2. 設定 tso")
        print("  3. 設定 ssh")
        print("  4. 設定 ftp")
        print("  5. 設定 rse")
        print("  6. 設定 debug")
        print("  7. 結束 workspace 設定")
        
        choice = input("請輸入選項 (1-7): ").strip()
        
        if choice == "1":
            # 設定 zosmf
            properties["zosmf"]["port"] = prompt_with_default(
                f"請輸入 zosmf 連線 port (預設 {properties['zosmf']['port']}): ",
                properties["zosmf"]["port"])
        elif choice == "2":
            # 設定 tso
            properties["tso"]["codepage"] = prompt_with_default(
                f"請輸入 tso 連線 codepage (預設 {properties['tso']['codepage']}): ",
                properties["tso"]["codepage"])
        elif choice == "3":
            # 設定 ssh
            properties["ssh"]["port"] = prompt_with_default(
                f"請輸入 ssh 連線 port (預設 {properties['ssh']['port']}): ",
                properties["ssh"]["port"])
        elif choice == "4":
            # 設定 ftp
            properties["ftp"]["port"] = prompt_with_default(
                f"請輸入 ftp 連線 port (預設 {properties['ftp']['port']}): ",
                properties["ftp"]["port"])
        elif choice == "5":
            # 設定 rse
            properties["rse"]["port"] = prompt_with_default(
                f"請輸入 rse 連線 port (預設 {properties['rse']['port']}): ",
                properties["rse"]["port"])
            properties["rse"]["encoding"] = prompt_with_default(
                f"請輸入 rse 連線 encoding (預設 {properties['rse']['encoding']}): ",
                properties["rse"]["encoding"])
        elif choice == "6":
            # 設定 debug
            properties["debug"]["port"] = prompt_with_default(
                f"請輸入 zOpenDebug 連線 port (預設 {properties['debug']['port']}): ",
                properties["debug"]["port"])
        elif choice == "7":
            # 離開選單，開始進行 zowe.config.json 檔案內容的修改
            break
        else:
            print("無效選項，請重新選擇。")
    
    # 最後更新檔案：workspace/zowe.config.json
    config_path = os.path.join(workspace, "workspace", "zowe.config.json")
    if not os.path.exists(config_path):
        print("找不到設定檔案：", config_path)
        sys.exit(1)
        
    # 取得目前時間戳記，用於命名備份檔案
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(workspace, "workspace", f"zowe.config.backup_{timestamp}.json")
    
    # 執行備份
    shutil.copy(config_path, backup_path)
    
    print(f"備份完成：{backup_path}")
    
    # 根據使用者輸入值與預設值進行替換
    replace_in_file(config_path, r"_HOST_", f"{host}")
    replace_in_file(config_path, r"_USER_", f"{user}")
    replace_in_file(config_path, r"_PASSWORD_", f"{password}")
    
    replace_in_file(config_path, r"\"_ZOSMF_PORT_\"", f"{properties['zosmf']['port']}")
    replace_in_file(config_path, r"_TSO_CODEPAGE_", f"{properties['tso']['codepage']}")
    replace_in_file(config_path, r"\"_SSH_PORT_\"", f"{properties['ssh']['port']}")
    replace_in_file(config_path, r"\"_FTP_PORT_\"", f"{properties['ftp']['port']}")
    replace_in_file(config_path, r"\"_RSE_PORT_\"", f"{properties['rse']['port']}")
    replace_in_file(config_path, r"_RSE_ENCODING_", f"{properties['rse']['encoding']}")
    replace_in_file(config_path, r"\"_DEBUG_PORT_\"", f"{properties['debug']['port']}")
    
    print("\nzowe.config.json 已成功更新！")

if __name__ == "__main__":
    main()
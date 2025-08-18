#!/usr/bin/env python3
"""
IBM Watsonx Assistant Configuration Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 1.0.0
日期: 2025/01/13

說明:
透過指令列依序要求使用者輸入 Watsonx Assistant 設定參數，內容包括：
  1. 選擇 AI 模型，從預定義的清單中選擇。
  2. 輸入 API Key Token。
  3. 輸入 API Base URL。
  4. 輸入 Project ID。
  5. 更新 workspace/.continue/assistants/config.yaml 檔案內容。

使用方式:
  - 用選擇的模型顯示名稱取代檔案內所有 _MODEL_DISPLAY_NAME_ 字樣
  - 用選擇的模型名稱取代 _MODEL_NAME_
  - 用 api_key 取代 _API_KEY_TOKEN_
  - 用 api_base 取代 _API_BASE_URL_
  - 用 project_id 取代 _PROJECT_ID_

更新記錄:
- v1.0.0: 初始版本，提供基本的 Watsonx Assistant 設定功能
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
#  預定義的模型清單
# -------------------------------
MODEL_OPTIONS = [
    {
        "display_name": "Granite 3.0 8b Instruct",
        "model_name": "ibm/granite-3-8b-instruct",
        "description": "IBM Granite 3.0 8B 指令模型"
    },
    {
        "display_name": "Granite 3.0 2b Instruct", 
        "model_name": "ibm/granite-3-2b-instruct",
        "description": "IBM Granite 3.0 2B 指令模型"
    },
    {
        "display_name": "Granite Code 3b",
        "model_name": "ibm/granite-code-3b", 
        "description": "IBM Granite Code 3B 程式碼模型"
    },
    {
        "display_name": "Granite Code 8b",
        "model_name": "ibm/granite-code-8b",
        "description": "IBM Granite Code 8B 程式碼模型"
    },
    {
        "display_name": "Granite Code 20b",
        "model_name": "ibm/granite-code-20b",
        "description": "IBM Granite Code 20B 程式碼模型"
    },
    {
        "display_name": "Granite Code 34b",
        "model_name": "ibm/granite-code-34b",
        "description": "IBM Granite Code 34B 程式碼模型"
    },
    {
        "display_name": "Granite Chat 13b",
        "model_name": "ibm/granite-chat-13b",
        "description": "IBM Granite Chat 13B 對話模型"
    },
    {
        "display_name": "Mistral Large",
        "model_name": "mistralai/Mistral-Large-Instruct-2411",
        "description": "Mistral AI 大型指令模型"
    },
    {
        "display_name": "Llama 3.1",
        "model_name": "meta-llama/Llama-3.1-8B-Instruct",
        "description": "Meta Llama 3.1 8B 指令模型"
    }
]

# -------------------------------
#  功能函式
# -------------------------------
def prompt_with_default(prompt_text, default_value):
    """
    顯示提示文字，若使用者沒有輸入，則回傳預設值
    """
    inp = input(prompt_text).strip()
    return inp if inp else default_value

def display_model_selection():
    """
    顯示模型選擇選單
    """
    print("\n可用的 AI 模型選項：")
    print("=" * 60)
    
    for i, model in enumerate(MODEL_OPTIONS, 1):
        default_mark = " *預設" if i == 1 else ""
        print(f"  {i}. {model['display_name']} ({model['model_name']}){default_mark}")
        print(f"     {model['description']}")
        print()
    
    while True:
        try:
            choice = input("請選擇模型 (1-9): ").strip()
            choice_num = int(choice)
            if 1 <= choice_num <= len(MODEL_OPTIONS):
                return MODEL_OPTIONS[choice_num - 1]
            else:
                print(f"請輸入 1-{len(MODEL_OPTIONS)} 之間的數字")
        except ValueError:
            print("請輸入有效的數字")

def display_help_info():
    """
    顯示取得各項資訊的指引
    """
    print("\n" + "=" * 60)
    print("取得設定資訊的指引：")
    print("=" * 60)
    print("1. API Key Token:")
    print("   - 登入 IBM Cloud 控制台")
    print("   - 前往 Watsonx.ai 服務")
    print("   - 在 API Keys 區段建立新的 API Key")
    print("   - 複製 API Key 值")
    print()
    print("2. API Base URL:")
    print("   - 預設值: https://us-south.ml.cloud.ibm.com")
    print("   - 或根據您的 IBM Cloud 地區調整:")
    print("     - 美國南部: https://us-south.ml.cloud.ibm.com")
    print("     - 歐洲: https://eu-de.ml.cloud.ibm.com")
    print("     - 亞太地區: https://au-syd.ml.cloud.ibm.com")
    print()
    print("3. Project ID:")
    print("   - 登入 IBM Cloud 控制台")
    print("   - 前往 Watsonx.ai 服務")
    print("   - 在 Projects 區段建立或選擇專案")
    print("   - 複製專案 ID (通常為 GUID 格式)")
    print("=" * 60)

# -------------------------------
# 主流程
# -------------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(description="Watsonx Assistant configuration script with optional auto-confirmation.")
    parser.add_argument("-y", "--yes", action="store_true", help="自動執行所有步驟，不須等待使用者確認。")
    parser.add_argument("--workspace", type=str, help="指定工作區目錄，預設為腳本檔所在路徑。")
    return parser.parse_args()

def main():
    args = parse_arguments()
    # 若使用者有指定 --workspace 則使用該目錄，否則預設為 script_dir 的上層
    workspace = Path(args.workspace).resolve() if args.workspace else Path(get_script_dir()).parent.resolve()
    os.chdir(workspace)
    print("目前工作目錄設定為：", workspace)
    
    # 顯示指引資訊
    display_help_info()
    
    # 1. 選擇 AI 模型
    print("\n步驟 1: 選擇 AI 模型")
    selected_model = display_model_selection()
    print(f"已選擇: {selected_model['display_name']}")
    
    # 2. 輸入 API Key Token
    print("\n步驟 2: 輸入 API Key Token")
    api_key = getpass.getpass("請輸入 API Key Token: ").strip()
    if not api_key:
        print("\n錯誤：API Key Token 為必填項目，請重新執行並提供完整資訊。")
        sys.exit(1)
    
    # 3. 輸入 API Base URL
    print("\n步驟 3: 輸入 API Base URL")
    default_api_base = "https://us-south.ml.cloud.ibm.com"
    api_base = prompt_with_default(
        f"請輸入 API Base URL (預設 {default_api_base}): ",
        default_api_base
    )
    
    # 4. 輸入 Project ID
    print("\n步驟 4: 輸入 Project ID")
    project_id = input("請輸入 Project ID: ").strip()
    if not project_id:
        print("\n錯誤：Project ID 為必填項目，請重新執行並提供完整資訊。")
        sys.exit(1)
    
    # 5. 更新設定檔案
    config_path = os.path.join(workspace, "workspace", ".continue", "assistants", "config.yaml")
    if not os.path.exists(config_path):
        print("找不到設定檔案：", config_path)
        sys.exit(1)
        
    # 取得目前時間戳記，用於命名備份檔案
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(workspace, "workspace", ".continue", "assistants", f"config.backup_{timestamp}.yaml")
    
    # 確保備份目錄存在
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    
    # 執行備份
    shutil.copy(config_path, backup_path)
    print(f"備份完成：{backup_path}")
    
    # 根據使用者輸入值進行替換
    replace_in_file(config_path, r"_MODEL_DISPLAY_NAME_", selected_model['display_name'])
    replace_in_file(config_path, r"_MODEL_NAME_", selected_model['model_name'])
    replace_in_file(config_path, r"_API_KEY_TOKEN_", api_key)
    replace_in_file(config_path, r"_API_BASE_URL_", api_base)
    replace_in_file(config_path, r"_PROJECT_ID_", project_id)
    
    print("\nconfig.yaml 已成功更新！")
    print(f"已設定模型: {selected_model['display_name']}")
    print(f"API Base URL: {api_base}")
    print(f"Project ID: {project_id}")

if __name__ == "__main__":
    main()

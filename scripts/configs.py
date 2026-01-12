#!/usr/bin/env python3
"""
IBM VSCode for Z Development Environment Setup Script
開發單位: IBM Taiwan Technology Expert Labs
版本: 2.6.1
日期: 2026/01/12

說明:
1. 載入 tools.yml 設定檔，並回傳工具包資訊。
2. 載入 pip.yml 設定檔，並回傳 pip 資訊。
3. 載入 init.yml 設定檔，並回傳初始化資訊。
4. 載入 extensions.yml 設定檔，並回傳擴充功能包資訊。
5. 載入 build.yml 設定檔，並回傳建置資訊。

更新記錄:
- v2.6.1: 更新版本/日期資訊（metadata）
- v2.6.0: 優化設定檔載入邏輯，改善配置管理
- v2.5.0: 新增 build.yml 設定檔載入功能
- v2.4.11: 優化設定檔載入邏輯，改善錯誤處理
- v2.3.0: 重構設定檔管理，提升載入效能
- v2.2.1: 初始版本，提供基本的設定檔載入功能
"""

import os
import sys
import yaml
from utils.path_utils import get_script_dir

def load_tools_config():
    """
    載入 tools.yml 設定檔，並回傳工具包資訊。
    """
    tools_yml_path = os.path.join(get_script_dir(), "configs", "tools.yml")
    if not os.path.exists(tools_yml_path):
        print(f"找不到設定檔: {tools_yml_path}，將跳過相關步驟。")
        return None
    with open(tools_yml_path, "r", encoding="utf-8") as f:
        tools = yaml.safe_load(f)
    return tools

def load_pip_config():
    """
    載入 pip.yml 設定檔，並回傳 pip 資訊。
    """
    pip_yml_path = os.path.join(get_script_dir(), "configs", "pip.yml")
    if not os.path.exists(pip_yml_path):
        print(f"找不到設定檔: {pip_yml_path}，將跳過相關步驟。")
        return None
    with open(pip_yml_path, "r", encoding="utf-8") as f:
        pip = yaml.safe_load(f)
    return pip

def load_init_config():
    """
    載入 init.yml 設定檔，並回傳初始化資訊。
    """
    init_yml_path = os.path.join(get_script_dir(), "configs", "init.yml")
    if not os.path.exists(init_yml_path):
        print(f"找不到設定檔: {init_yml_path}，將跳過相關步驟。")
        return None
    with open(init_yml_path, "r", encoding="utf-8") as f:
        init_config = yaml.safe_load(f)
    return init_config

def load_extensions_config():
    """
    載入 extensions.yml 設定檔，並回傳擴充功能包資訊。
    """
    extensions_yml_path = os.path.join(get_script_dir(), "configs", "extensions.yml")
    if not os.path.exists(extensions_yml_path):
        print(f"找不到設定檔: {extensions_yml_path}，將跳過相關步驟。")
        return None
    with open(extensions_yml_path, "r", encoding="utf-8") as f:
        extensions = yaml.safe_load(f)
    return extensions

def load_npm_config():
    """
    載入 npm.yml 設定檔，並回傳 npm 套件資訊。
    """
    npm_yml_path = os.path.join(get_script_dir(), "configs", "npm.yml")
    if not os.path.exists(npm_yml_path):
        print(f"找不到設定檔: {npm_yml_path}，將跳過相關步驟。")
        return None
    with open(npm_yml_path, "r", encoding="utf-8") as f:
        npm = yaml.safe_load(f)
    return npm

def load_build_config():
    """
    載入 build.yml 設定檔，並回傳設定資訊。
    """
    build_yml_path = os.path.join(get_script_dir(), "configs", "build.yml")
    if not os.path.exists(build_yml_path):
        print(f"找不到設定檔: {build_yml_path}，將跳過相關步驟。")
        return None
    with open(build_yml_path, "r", encoding="utf-8") as f:
        build_config = yaml.safe_load(f)
    return build_config

def load_install_config():
    """
    載入 install.yml 設定檔，並回傳安裝設定資訊。
    若設定檔不存在，則回傳 None。
    """
    install_yml_path = os.path.join(get_script_dir(), "configs", "install.yml")
    try:
        if not os.path.exists(install_yml_path):
            return None
        with open(install_yml_path, "r", encoding="utf-8") as f:
            install_config = yaml.safe_load(f)
        print(f"已載入設定檔案：{install_yml_path}")
        return install_config
    except FileNotFoundError:
        print(f"找不到設定檔案：{install_yml_path}")
        return None
    except yaml.YAMLError as e:
        print(f"YAML 檔案格式錯誤：{e}")
        return None
    except Exception as e:
        print(f"載入設定檔時發生錯誤：{e}")
        return None

def load_workspace_config():
    """
    載入 workspace.yml 設定檔，並回傳安裝設定資訊。
    若設定檔不存在，則回傳 None。
    """
    workspace_yml_path = os.path.join(get_script_dir(), "configs", "workspace.yml")
    try:
        if not os.path.exists(workspace_yml_path):
            return None
        with open(workspace_yml_path, 'r', encoding='utf-8') as f:
            workspace_config = yaml.safe_load(f)
        print(f"已載入設定檔案：{workspace_yml_path}")
        return workspace_config
    except FileNotFoundError:
        print(f"找不到設定檔案：{workspace_yml_path}")
        return None
    except yaml.YAMLError as e:
        print(f"YAML 檔案格式錯誤：{e}")
        return None
    except Exception as e:
        print(f"載入設定檔案時發生錯誤：{e}")
        return None

def load_assistant_config():
    """
    載入 assistant.yml 設定檔，並回傳 Watsonx Assistant 設定資訊。
    若設定檔不存在，則回傳 None。
    """
    assistant_yml_path = os.path.join(get_script_dir(), "configs", "assistant.yml")
    try:
        if not os.path.exists(assistant_yml_path):
            return None
        with open(assistant_yml_path, 'r', encoding='utf-8') as f:
            assistant_config = yaml.safe_load(f)
        print(f"已載入設定檔案：{assistant_yml_path}")
        return assistant_config
    except FileNotFoundError:
        print(f"找不到設定檔案：{assistant_yml_path}")
        return None
    except yaml.YAMLError as e:
        print(f"YAML 檔案格式錯誤：{e}")
        return None
    except Exception as e:
        print(f"載入設定檔案時發生錯誤：{e}")
        return None
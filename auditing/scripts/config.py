#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置讀取模組
包含政策設定和擴充功能設定的讀取功能
"""

import yaml
from utils import log


def read_policy(policy_path):
    """讀取政策設定檔。"""
    with open(policy_path, "r", encoding="utf-8") as f:
        y = yaml.safe_load(f) or {}
    allow = (y.get("license", {}) or {}).get("allow", []) or []
    deny = (y.get("license", {}) or {}).get("deny", []) or []
    max_cvss = (y.get("vulnerability", {}) or {}).get("max_cvss", 7.0)
    try:
        max_cvss = float(max_cvss)
    except Exception:
        max_cvss = 7.0
    return allow, deny, max_cvss


def read_extensions_config(config_path):
    """從 YAML 檔案讀取擴充功能設定。"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    
    extensions = []
    for publisher, ext_list in config.items():
        for ext_item in ext_list:
            # 處理字串和字典格式
            if isinstance(ext_item, dict):
                for ext_name, version in ext_item.items():
                    extensions.append(("openvsx", f"{publisher}.{ext_name}", version))
            elif isinstance(ext_item, str):
                # 處理簡單字串格式（如需要）
                log(f"警告: 擴充功能設定中的意外字串格式: {ext_item}")
    
    return extensions

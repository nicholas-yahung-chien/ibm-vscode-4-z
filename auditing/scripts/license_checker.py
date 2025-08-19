#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
授權條款檢查模組
包含授權條款檢查和偵測功能
"""

import re
import os
from utils import log


def license_check(license_str: str, allow_list, deny_list) -> str:
    """檢查授權條款是否符合政策。"""
    # 標準化授權字串
    license_str = license_str.strip()
    
    # 先檢查完全匹配
    if license_str in deny_list:
        return "deny"
    if license_str in allow_list:
        return "allow"
    
    # 處理特殊情況
    if license_str.startswith("SEE LICENSE IN"):
        # 這通常表示授權條款在單獨的檔案中，通常是 MIT 或類似授權
        # 我們應該已經在 scan_one 中處理過這個，但以防萬一
        return "allow"  # 假設它是可接受的，除非明確拒絕
    
    if license_str in ["UNKNOWN", "Proprietary", "Commercial"]:
        return "deny"  # 未知授權條款預設被拒絕
    
    # 轉換為小寫以進行不區分大小寫的比較
    license_lower = license_str.lower()
    
    # 標準化常見授權條款變體
    # 將空格替換為連字號以符合常見模式
    normalized_license = license_lower
    normalized_license = normalized_license.replace("apache 2.0", "apache-2.0")
    normalized_license = normalized_license.replace("apache 2", "apache-2.0")
    normalized_license = normalized_license.replace("bsd 3-clause", "bsd-3-clause")
    normalized_license = normalized_license.replace("bsd 2-clause", "bsd-2-clause")
    normalized_license = normalized_license.replace("epl 2.0", "epl-2.0")
    normalized_license = normalized_license.replace("epl 1.0", "epl-1.0")
    normalized_license = normalized_license.replace("gpl 3.0", "gpl-3.0")
    normalized_license = normalized_license.replace("gpl 2.0", "gpl-2.0")
    normalized_license = normalized_license.replace("mpl 2.0", "mpl-2.0")
    
    # 移除常見後綴，如 "(see LICENSE.txt)", "(see LICENSE)" 等
    normalized_license = re.sub(r'\s*\(see\s+[^)]+\)', '', normalized_license)
    normalized_license = re.sub(r'\s*\([^)]*license[^)]*\)', '', normalized_license)
    
    # 檢查標準化授權條款是否在允許清單中
    for allowed in allow_list:
        allowed_lower = allowed.lower()
        if normalized_license == allowed_lower:
            return "allow"
        # 同時檢查標準化授權條款是否包含允許的授權條款
        if allowed_lower in normalized_license:
            return "allow"
    
    # 檢查標準化授權條款是否在拒絕清單中
    for denied in deny_list:
        denied_lower = denied.lower()
        if normalized_license == denied_lower:
            return "deny"
        # 同時檢查標準化授權條款是否包含拒絕的授權條款
        if denied_lower in normalized_license:
            return "deny"
    
    # 分割成單字並建立集合以進行高效查詢
    license_words = set(license_lower.split())
    
    # 檢查是否有任何允許的授權條款作為完整單字包含（不區分大小寫）
    for allowed in allow_list:
        allowed_lower = allowed.lower()
        # 先檢查完全匹配
        if license_lower == allowed_lower:
            return "allow"
        # 檢查允許的授權條款是否為存在於授權字串中的單一單字
        if allowed_lower in license_words:
            return "allow"
        # 檢查允許的授權條款是否包含多個單字且全部存在
        allowed_words = allowed_lower.split()
        if len(allowed_words) > 1 and all(word in license_words for word in allowed_words):
            return "allow"
        # 檢查允許的授權條款是否包含連字號（如 "EPL-2.0"）
        if "-" in allowed_lower and allowed_lower in license_lower:
            # 對於帶連字號的授權條款，檢查它們是否作為整體出現在授權字串中
            # 這處理像 "This is EPL-2.0 licensed" 中的 "EPL-2.0" 這樣的情況
            return "allow"
    
    # 檢查是否有任何拒絕的授權條款作為完整單字包含（不區分大小寫）
    for denied in deny_list:
        denied_lower = denied.lower()
        # 先檢查完全匹配
        if license_lower == denied_lower:
            return "deny"
        # 檢查拒絕的授權條款是否為存在於授權字串中的單一單字
        if denied_lower in license_words:
            return "deny"
        # 檢查拒絕的授權條款是否包含多個單字且全部存在
        denied_words = denied_lower.split()
        if len(denied_words) > 1 and all(word in license_words for word in denied_words):
            return "deny"
        # 檢查拒絕的授權條款是否包含連字號
        if "-" in denied_lower and denied_lower in license_lower:
            return "deny"
    
    # 如果我們有允許清單且授權條款不在其中，則拒絕
    if allow_list:
        return "deny"
    
    # 如果沒有允許清單，允許除明確拒絕外的所有內容
    return "allow"


def find_license_in_directory(ext_dir: str) -> str:
    """在擴充功能目錄中尋找並讀取授權檔案。"""
    # 要搜尋的常見授權檔案名稱
    license_files = [
        "LICENSE.txt",
        "LICENSE.md", 
        "LICENSE",
        "license.txt",
        "license.md",
        "license"
    ]
    
    # 在擴充功能目錄及其子目錄中搜尋
    search_dirs = [
        ext_dir,
        os.path.join(ext_dir, "extension"),
        os.path.join(ext_dir, ".."),
        os.path.join(ext_dir, "extension", "..")
    ]
    
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue
            
        for license_file in license_files:
            license_path = os.path.join(search_dir, license_file)
            if os.path.exists(license_path):
                try:
                    with open(license_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if len(content) > 0:
                            log(f"找到授權檔案: {license_path}")
                            return content
                except Exception as e:
                    log(f"警告: 無法讀取授權檔案 {license_path}: {e}")
    
    return None


def read_license_file(ext_dir: str, license_ref: str) -> str:
    """從參考檔案讀取授權內容。"""
    if not license_ref.startswith("SEE LICENSE IN "):
        return None
    
    # 從 "SEE LICENSE IN filename" 中提取檔案名
    filename = license_ref[15:].strip()
    
    # 嘗試不同的可能位置
    possible_paths = [
        os.path.join(ext_dir, filename),
        os.path.join(ext_dir, "extension", filename),
        os.path.join(ext_dir, "..", filename),
        os.path.join(ext_dir, "extension", "..", filename),
        # 同時嘗試常見變體
        os.path.join(ext_dir, filename + ".txt"),
        os.path.join(ext_dir, filename + ".md"),
        os.path.join(ext_dir, "extension", filename + ".txt"),
        os.path.join(ext_dir, "extension", filename + ".md"),
        # 如果檔案名有副檔名，嘗試不帶副檔名
        os.path.join(ext_dir, filename.split('.')[0]),
        os.path.join(ext_dir, "extension", filename.split('.')[0])
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    # 回傳整個檔案內容以進行授權條款偵測
                    if len(content) > 0:
                        return content
            except Exception as e:
                log(f"警告: 無法讀取授權檔案 {path}: {e}")
    
    return None


def detect_license_from_content(content: str) -> str:
    """從授權檔案內容偵測授權條款類型。"""
    content_upper = content.upper()
    
    # 將內容分割成單字以進行完整單字匹配
    content_words = set(content_upper.split())

    # 偵測到的授權條款
    detected_license = "UNKNOWN"
    
    # 常見授權條款模式 - 先檢查更具體的模式
    # 使用完整單字匹配以避免誤判
    
    # 檢查 Eclipse Public License（優先於 GPL）
    if "ECLIPSE" in content_words and "PUBLIC" in content_words and "LICENSE" in content_words:
        # 檢查內容中的版本 2（不僅僅是作為單獨的單字）
        if "VERSION" in content_words and ("2" in content_words or "V.2" in content_upper or "VERSION 2" in content_upper) or "EPL-2" in content_words:
            detected_license = "EPL-2.0"
        else:
            detected_license = "EPL-1.0"
    
    # 檢查 GNU General Public License
    elif "GNU" in content_words and "GENERAL" in content_words and "PUBLIC" in content_words and "LICENSE" in content_words:
        if "VERSION" in content_words and "3" in content_words or "GPL-3" in content_words:
            detected_license = "GPL-3.0"
        elif "VERSION" in content_words and "2" in content_words or "GPL-2" in content_words:
            detected_license = "GPL-2.0"
        else:
            detected_license = "GPL"
    
    # 檢查 BSD 授權條款
    elif "BSD" in content_words and "LICENSE" in content_words:
        if "3-CLAUSE" in content_words or "3" in content_words:
            detected_license = "BSD-3-Clause"
        elif "2-CLAUSE" in content_words or "2" in content_words:
            detected_license = "BSD-2-Clause"
        else:
            detected_license = "BSD-3-Clause"  # 如果未指定，預設為 3-clause
    
    # 檢查 Apache License
    elif "APACHE" in content_words and "LICENSE" in content_words:
        detected_license = "Apache-2.0"
    
    # 檢查 MIT License
    elif "MIT" in content_words and "LICENSE" in content_words:
        detected_license = "MIT"
    
    # 檢查 Mozilla Public License
    elif "MOZILLA" in content_words and "PUBLIC" in content_words and "LICENSE" in content_words:
        detected_license = "MPL-2.0"
    
    # 檢查 ISC License
    elif "ISC" in content_words and "LICENSE" in content_words:
        detected_license = "ISC"
    
    # 回退：檢查常見授權條款縮寫作為完整單字
    elif "GPL-3.0" in content_words:
        detected_license = "GPL-3.0"
    elif "GPL-2.0" in content_words:
        detected_license = "GPL-2.0"
    elif "GPL" in content_words:
        detected_license = "GPL"
    elif "EPL-2.0" in content_words:
        detected_license = "EPL-2.0"
    elif "EPL-1.0" in content_words:
        detected_license = "EPL-1.0"
    elif "EPL" in content_words:
        detected_license = "EPL-1.0"
    elif "BSD-3-CLAUSE" in content_words:
        detected_license = "BSD-3-Clause"
    elif "BSD-2-CLAUSE" in content_words:
        detected_license = "BSD-2-Clause"
    elif "APACHE-2.0" in content_words:
        detected_license = "Apache-2.0"
    elif "MPL-2.0" in content_words:
        detected_license = "MPL-2.0"
    
    # 私有合作授權條款通常有更廣泛的範圍
    # 檢查 Broadcom
    if "BROADCOM" in content_words:
        detected_license = "Broadcom"
    
    # 檢查 IBM
    elif "IBM" in content_words:
        detected_license = "IBM"

    # 檢查 Microsoft
    elif "MICROSOFT" in content_words:
        detected_license = "Microsoft"

    # 其他情況
    if detected_license == "UNKNOWN":
        # 對於未知授權條款，嘗試提取有意義的識別符
        # 在前幾行中尋找常見模式
        lines = content.split('\n')
        for line in lines[:5]:  # 檢查前 5 行
            line = line.strip()
            if line and len(line) > 10 and len(line) < 100:
                # 從第一個有意義的行回傳合理的識別符
                detected_license = line[:80] + "..." if len(line) > 80 else line
        
        # 如果沒有找到有意義的行，回傳截斷版本
        if len(content) > 100:
            detected_license = content[:100] + "..."
        else:
            detected_license = content
    
    return detected_license

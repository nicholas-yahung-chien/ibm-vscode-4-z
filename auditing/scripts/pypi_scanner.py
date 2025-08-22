#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyPI 套件掃描模組
使用 OSV API 檢查 PyPI 套件的安全漏洞
"""

import json
import os
import re
import requests
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from utils import log


def extract_package_info_from_whl(whl_path: str) -> Optional[Tuple[str, str]]:
    """
    從 .whl 檔案名稱中提取套件名稱和版本
    
    例如: 
    - ansible_core-2.19.0-py3-none-any.whl -> (ansible_core, 2.19.0)
    - black-25.1.0-cp313-cp313-win_amd64.whl -> (black, 25.1.0)
    - cryptography-45.0.6-cp311-abi3-win_amd64.whl -> (cryptography, 45.0.6)
    """
    filename = os.path.basename(whl_path)
    
    # 移除 .whl 副檔名
    if not filename.endswith('.whl'):
        return None
    
    name_with_version = filename[:-4]  # 移除 .whl
    
    # 使用更精確的正則表達式來處理各種 wheel 檔案格式
    # 主要格式：package_name-version-python_tag-abi_tag-platform
    # 版本號可能包含多個連字符，如 25.1.0, 45.0.6 等
    
    # 正則表達式說明：
    # ^(.+?)- : 匹配套件名稱（非貪婪匹配，到第一個連字符為止）
    # (\d+(?:\.\d+)*) : 匹配版本號（只匹配數字和點號，如 25.1.0）
    # (?:-py\d+(?:\.py\d+)?)? : 可選的 Python 標籤（如 py3, py2.py3）
    # (?:-none)? : 可選的 none 標籤
    # (?:-any)? : 可選的 any 標籤
    # (?:-cp\d+)? : 可選的 cp 標籤（如 cp313）
    # (?:-abi\d+)? : 可選的 abi 標籤（如 abi3）
    # (?:-win_amd64)? : 可選的平台標籤（如 win_amd64）
    # $ : 字串結尾
    
    # 主要模式：精確匹配版本號（只包含數字和點號）
    pattern = r'^(.+?)-(\d+(?:\.\d+)*)(?:-py\d+(?:\.py\d+)?)?(?:-none)?(?:-any)?(?:-cp\d+)?(?:-abi\d+)?(?:-win_amd64)?$'
    match = re.match(pattern, name_with_version)
    
    if match:
        package_name = match.group(1)
        version = match.group(2)
        return (package_name, version)
    
    # 如果主要模式失敗，嘗試更寬鬆的模式
    # 這個模式會匹配到第一個看起來像版本號的部分
    fallback_pattern = r'^(.+?)-(\d+(?:\.\d+)*)'
    fallback_match = re.match(fallback_pattern, name_with_version)
    
    if fallback_match:
        package_name = fallback_match.group(1)
        version = fallback_match.group(2)
        log(f"使用備用模式解析: {filename} -> ({package_name}, {version})")
        return (package_name, version)
    
    log(f"無法解析套件資訊: {filename}")
    return None


def query_osv_api(package_name: str, version: str) -> Dict:
    """
    使用 OSV API 查詢套件的漏洞資訊
    
    API 端點: https://api.osv.dev/v1/query
    """
    api_url = "https://api.osv.dev/v1/query"
    
    # 構建查詢參數
    query_data = {
        "package": {
            "name": package_name,
            "ecosystem": "PyPI"
        },
        "version": version
    }
    
    try:
        response = requests.post(api_url, json=query_data, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log(f"OSV API 查詢失敗 ({package_name}@{version}): {e}")
        return {"vulns": []}


def analyze_vulnerabilities(vulns_data: Dict, max_cvss: float) -> Tuple[List[str], float]:
    """
    分析漏洞資料，返回 CVE 列表和最高 CVSS 分數
    """
    cve_list = []
    max_cvss_score = 0.0
    
    vulns = vulns_data.get("vulns", [])
    
    for vuln in vulns:
        # 提取 CVE ID
        vuln_id = vuln.get("id", "")
        if vuln_id.startswith("CVE-"):
            cve_list.append(vuln_id)
        
        # 提取 CVSS 分數
        cvss_data = vuln.get("cvss", {})
        if isinstance(cvss_data, dict):
            score = cvss_data.get("score", 0.0)
            try:
                score = float(score)
                max_cvss_score = max(max_cvss_score, score)
            except (ValueError, TypeError):
                pass
        elif isinstance(cvss_data, list) and cvss_data:
            # 如果是列表，取第一個元素的分數
            first_cvss = cvss_data[0]
            if isinstance(first_cvss, dict):
                score = first_cvss.get("score", 0.0)
                try:
                    score = float(score)
                    max_cvss_score = max(max_cvss_score, score)
                except (ValueError, TypeError):
                    pass
    
    return cve_list, max_cvss_score


def scan_pypi_package(whl_path: str, max_cvss: float) -> Dict:
    """
    掃描單一 PyPI 套件
    
    返回:
    {
        "package_name": str,
        "version": str,
        "cve_list": List[str],
        "max_cvss_score": float,
        "high_vulnerabilities": int,
        "status": str
    }
    """
    # 提取套件資訊
    package_info = extract_package_info_from_whl(whl_path)
    if not package_info:
        return {
            "package_name": os.path.basename(whl_path),
            "version": "unknown",
            "cve_list": [],
            "max_cvss_score": 0.0,
            "high_vulnerabilities": 0,
            "status": "無法解析套件名稱"
        }
    
    package_name, version = package_info
    
    # 查詢 OSV API
    vulns_data = query_osv_api(package_name, version)
    
    # 分析漏洞
    cve_list, max_cvss_score = analyze_vulnerabilities(vulns_data, max_cvss)
    
    # 計算高風險漏洞數量
    high_vulnerabilities = sum(1 for score in [max_cvss_score] if score >= max_cvss)
    
    # 判斷狀態
    if high_vulnerabilities > 0:
        status = "漏洞風險過高"
    else:
        status = "通過"
    
    return {
        "package_name": package_name,
        "version": version,
        "cve_list": cve_list,
        "max_cvss_score": max_cvss_score,
        "high_vulnerabilities": high_vulnerabilities,
        "status": status
    }


def scan_pypi_directory(pywhls_dir: str, max_cvss: float) -> List[Dict]:
    """
    掃描 pywhls 目錄下的所有 .whl 檔案
    
    返回掃描結果列表
    """
    results = []
    pywhls_path = Path(pywhls_dir)
    
    if not pywhls_path.exists():
        log(f"警告: pywhls 目錄不存在: {pywhls_dir}")
        return results
    
    # 找到所有 .whl 檔案
    whl_files = list(pywhls_path.glob("*.whl"))
    
    if not whl_files:
        log(f"警告: 在 {pywhls_dir} 中未找到 .whl 檔案")
        return results
    
    log(f"開始掃描 {len(whl_files)} 個 PyPI 套件...")
    
    for whl_file in whl_files:
        try:
            result = scan_pypi_package(str(whl_file), max_cvss)
            results.append(result)
            
            # 記錄掃描結果
            if result["high_vulnerabilities"] > 0:
                log(f"⚠️  {result['package_name']}@{result['version']}: {result['high_vulnerabilities']} 個高風險漏洞 (CVSS: {result['max_cvss_score']:.1f})")
            else:
                log(f"✅ {result['package_name']}@{result['version']}: 通過檢查")
                
        except Exception as e:
            log(f"掃描 {whl_file.name} 時發生錯誤: {e}")
            results.append({
                "package_name": whl_file.name,
                "version": "unknown",
                "cve_list": [],
                "max_cvss_score": 0.0,
                "high_vulnerabilities": 0,
                "status": f"掃描錯誤: {e}"
            })
    
    return results


def write_pypi_summary(results: List[Dict], report_dir: str) -> str:
    """
    生成 PyPI 套件掃描摘要報告
    
    返回摘要檔案路徑
    """
    summary_file = os.path.join(report_dir, "pypi_summary.md")
    
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("# PyPI 套件安全稽核報告\n\n")
        f.write("| 套件名稱 | 版本 | 稽核結果 | 最高 CVSS 分數 | CVE 項目 |\n")
        f.write("|---|---|---|---|---|\n")
        
        for result in results:
            package_name = result["package_name"]
            version = result["version"]
            status = result["status"]
            max_cvss = result["max_cvss_score"]
            cve_list = result["cve_list"]
            
            # 格式化 CVE 列表
            cve_str = ", ".join(cve_list) if cve_list else "-"
            
            # 格式化 CVSS 分數
            cvss_str = f"{max_cvss:.1f}" if max_cvss > 0 else "-"
            
            f.write(f"| `{package_name}` | `{version}` | **{status}** | {cvss_str} | {cve_str} |\n")
    
    return summary_file

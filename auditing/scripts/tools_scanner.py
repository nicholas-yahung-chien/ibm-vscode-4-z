#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工具掃描模組
使用 NVD API 檢查 tools.yml 中有 cpe_name 設定的軟體的安全漏洞
"""

import json
import os
import re
import requests
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from utils import log


def load_tools_config(tools_config_path: str) -> Dict:
    """
    載入 tools.yml 設定檔
    """
    try:
        with open(tools_config_path, "r", encoding="utf-8") as f:
            import yaml
            return yaml.safe_load(f)
    except Exception as e:
        log(f"載入 tools.yml 失敗: {e}")
        return {}


def extract_cpe_with_version(cpe_name: str, version: str) -> str:
    """
    將 CPE 名稱中的版本 placeholder 替換為實際版本
    
    例如:
    - cpe:2.3:a:microsoft:visual_studio_code:-:*:*:*:*:*:*:* 和版本 "1.101.0"
    - 結果: cpe:2.3:a:microsoft:visual_studio_code:1.101.0:*:*:*:*:*:*:*
    """
    # 將版本 placeholder (-) 替換為實際版本
    return cpe_name.replace(":-:", f":{version}:")


def query_nvd_api(cpe_name: str) -> Dict:
    """
    使用 NVD API 查詢 CPE 的漏洞資訊
    
    API 端點: https://services.nvd.nist.gov/rest/json/cves/2.0
    """
    api_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    
    # 構建查詢參數
    params = {
        "cpeName": cpe_name,
        "resultsPerPage": 2000  # 取得最多結果
    }
    
    try:
        response = requests.get(api_url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log(f"NVD API 查詢失敗 ({cpe_name}): {e}")
        return {"vulnerabilities": []}


def analyze_cve_vulnerabilities(vulns_data: Dict, max_cvss: float) -> Tuple[List[str], float, int]:
    """
    分析 CVE 漏洞資料，找出最高 CVSS 分數和超過閾值的漏洞數量
    
    回傳: (高風險漏洞列表, 最高 CVSS 分數, 高風險漏洞數量)
    """
    high_vulns = []
    max_cvss_score = 0.0
    high_count = 0
    
    if "vulnerabilities" not in vulns_data:
        return high_vulns, max_cvss_score, high_count
    
    for vuln in vulns_data["vulnerabilities"]:
        cve = vuln.get("cve", {})
        cve_id = cve.get("id", "UNKNOWN")
        
        # 取得 CVSS 分數
        cvss_score = 0.0
        metrics = cve.get("metrics", {})
        
        # 優先使用 CVSS v3.1
        if "cvssMetricV31" in metrics and metrics["cvssMetricV31"]:
            cvss_score = metrics["cvssMetricV31"][0].get("cvssData", {}).get("baseScore", 0.0)
        elif "cvssMetricV30" in metrics and metrics["cvssMetricV30"]:
            cvss_score = metrics["cvssMetricV30"][0].get("cvssData", {}).get("baseScore", 0.0)
        elif "cvssMetricV2" in metrics and metrics["cvssMetricV2"]:
            cvss_score = metrics["cvssMetricV2"][0].get("cvssData", {}).get("baseScore", 0.0)
        
        # 更新最高分數
        if cvss_score > max_cvss_score:
            max_cvss_score = cvss_score
        
        # 檢查是否超過閾值
        if cvss_score >= max_cvss:
            high_count += 1
            description = cve.get("descriptions", [{}])[0].get("value", "無描述")
            high_vulns.append(f"{cve_id} (CVSS: {cvss_score:.1f}) - {description}")
    
    return high_vulns, max_cvss_score, high_count


def scan_tools_with_cpe(tools_config: Dict, max_cvss: float) -> List[Dict]:
    """
    掃描 tools.yml 中有 cpe_name 設定的工具
    
    回傳: 掃描結果列表
    """
    results = []
    
    for tool_name, tool_config in tools_config.items():
        if not isinstance(tool_config, dict):
            continue
            
        cpe_name = tool_config.get("cpe_name")
        version = tool_config.get("version")
        
        if not cpe_name or not version:
            continue
        
        log(f"掃描工具: {tool_name}@{version} (CPE: {cpe_name})")
        
        try:
            # 替換版本號
            full_cpe = extract_cpe_with_version(cpe_name, version)
            
            # 查詢 NVD API
            vulns_data = query_nvd_api(full_cpe)
            
            # 分析漏洞
            high_vulns, max_cvss_score, high_count = analyze_cve_vulnerabilities(vulns_data, max_cvss)
            
            # 判斷狀態
            if high_count > 0:
                status = f"發現 {high_count} 個高風險漏洞 (最高 CVSS: {max_cvss_score:.1f})"
            else:
                status = f"通過檢查 (最高 CVSS: {max_cvss_score:.1f})"
            
            result = {
                "tool_name": tool_name,
                "version": version,
                "cpe_name": cpe_name,
                "full_cpe": full_cpe,
                "max_cvss_score": max_cvss_score,
                "high_vulnerabilities": high_count,
                "high_vulns_list": high_vulns,
                "status": status,
                "total_vulns": len(vulns_data.get("vulnerabilities", []))
            }
            
            results.append(result)
            
        except Exception as e:
            log(f"掃描工具 {tool_name} 時發生錯誤: {e}")
            results.append({
                "tool_name": tool_name,
                "version": version,
                "cpe_name": cpe_name,
                "full_cpe": extract_cpe_with_version(cpe_name, version) if cpe_name and version else "",
                "max_cvss_score": 0.0,
                "high_vulnerabilities": 0,
                "high_vulns_list": [],
                "status": f"掃描錯誤: {e}",
                "total_vulns": 0
            })
    
    return results


def write_tools_summary(tools_results: List[Dict], report_dir: str) -> str:
    """
    生成工具掃描摘要報告
    
    回傳: 報告檔案路徑
    """
    summary_file = os.path.join(report_dir, "tools_summary.md")
    
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("# 工具安全掃描報告\n\n")
        f.write("| 工具名稱 | 版本 | CPE 名稱 | 最高 CVSS | 高風險漏洞數量 | 狀態 |\n")
        f.write("|---|---|---|---|---|---|\n")
        
        for result in tools_results:
            tool_name = result["tool_name"]
            version = result["version"]
            cpe_name = result["cpe_name"]
            max_cvss = result["max_cvss_score"]
            high_count = result["high_vulnerabilities"]
            status = result["status"]
            
            # 格式化狀態顯示
            if "掃描錯誤" in status:
                status_display = f"❌ {status}"
            elif high_count > 0:
                status_display = f"⚠️ {status}"
            else:
                status_display = f"✅ {status}"
            
            f.write(f"| {tool_name} | {version} | `{cpe_name}` | {max_cvss:.1f} | {high_count} | {status_display} |\n")
        
        f.write("\n## 詳細漏洞資訊\n\n")
        
        for result in tools_results:
            if result["high_vulns_list"]:
                f.write(f"### {result['tool_name']}@{result['version']}\n\n")
                f.write(f"**CPE:** `{result['full_cpe']}`\n\n")
                f.write(f"**最高 CVSS 分數:** {result['max_cvss_score']:.1f}\n\n")
                f.write(f"**高風險漏洞數量:** {result['high_vulnerabilities']}\n\n")
                f.write("**漏洞列表:**\n\n")
                
                for vuln in result["high_vulns_list"]:
                    f.write(f"- {vuln}\n")
                
                f.write("\n")
    
    return summary_file

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
報告生成模組
包含摘要報告和詳細報告的生成功能
"""

import os
import textwrap
from utils import log


def write_summary_row(summary_md: str, pubext: str, version: str, license_str: str, result: str, high: int, sha: str):
    """寫入摘要報告的一行。"""
    row = f"| `{pubext}@{version}` | `{license_str}` | **{result}** | {high if high is not None else '-'} | `{sha or '-'}` |\n"
    with open(summary_md, "a", encoding="utf-8") as f:
        f.write(row)


def write_summary_header(summary_md: str, max_cvss: float):
    """寫入摘要報告的標題。"""
    with open(summary_md, "w", encoding="utf-8") as f:
        f.write("# VS Code 擴充功能安全稽核報告\n\n")
        f.write(f"| 擴充功能 | 授權條款 | 稽核結果 | 高風險漏洞數量 (CVSS≥{max_cvss}) | SHA256 雜湊值 |\n")
        f.write("|---|---|---|---|---|\n")


def write_summary_footer(summary_md: str, license_issues: list, vuln_issues: list, error_issues: list):
    """寫入摘要報告的頁尾。"""
    with open(summary_md, "a", encoding="utf-8") as f:
        f.write("\n## 問題摘要\n\n")
        
        if license_issues:
            f.write("### 授權條款問題\n\n")
            f.write("以下擴充功能的授權條款不符合政策要求：\n\n")
            for issue in license_issues:
                f.write(f"- {issue}\n")
            f.write("\n")
        
        if vuln_issues:
            f.write("### 漏洞問題\n\n")
            f.write("以下擴充功能存在高風險漏洞 (CVSS 分數超過允許閾值)：\n\n")
            for issue in vuln_issues:
                f.write(f"- {issue}\n")
            f.write("\n")
        
        if error_issues:
            f.write("### 處理錯誤\n\n")
            f.write("以下擴充功能在處理過程中發生錯誤：\n\n")
            for issue in error_issues:
                f.write(f"- {issue}\n")
            f.write("\n")
        
        if not license_issues and not vuln_issues and not error_issues:
            f.write("✅ **稽核成功** - 所有擴充功能都通過了安全檢查，未發現任何問題。\n\n")
        else:
            total_issues = len(license_issues) + len(vuln_issues) + len(error_issues)
            f.write(f"⚠️  **稽核結果摘要** - 總共發現 {total_issues} 個問題：\n")
            f.write(f"- 授權條款問題：{len(license_issues)} 個\n")
            f.write(f"- 漏洞問題：{len(vuln_issues)} 個\n")
            f.write(f"- 處理錯誤：{len(error_issues)} 個\n\n")


def write_extension_summary(ext_report_dir: str, name: str, license_str: str, sbom: str, grype: str, osv: str, sha: str, high: int, max_cvss: float):
    """寫入擴充功能的摘要檔案。"""
    summary_txt = textwrap.dedent(f"""\
    extension: {name}
    license: {license_str}
    sbom: {os.path.basename(sbom)}
    grype: {os.path.basename(grype)}
    osv: {os.path.basename(osv)}
    sha256: {sha}
    high_or_equal_cvss_{str(max_cvss).replace('.', '_')}: {high}
    """)
    with open(os.path.join(ext_report_dir, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary_txt)


def write_result_file(ext_report_dir: str, result: str, details: str = ""):
    """寫入結果檔案。"""
    content = f"{result}\n"
    if details:
        content += f"{details}\n"
    with open(os.path.join(ext_report_dir, "result.txt"), "w", encoding="utf-8") as f:
        f.write(content)


def write_license_file(ext_report_dir: str, license_str: str):
    """寫入授權條款檔案。"""
    with open(os.path.join(ext_report_dir, "license.txt"), "w", encoding="utf-8") as f:
        f.write(str(license_str) + "\n")


def write_sha256_file(ext_report_dir: str, sha: str):
    """寫入 SHA256 檔案。"""
    with open(os.path.join(ext_report_dir, "sha256.txt"), "w", encoding="utf-8") as f:
        f.write(sha + "\n")

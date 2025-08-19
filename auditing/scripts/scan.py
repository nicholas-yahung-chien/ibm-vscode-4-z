#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VS Code 擴充功能安全稽核腳本
開發單位: IBM Taiwan Technology Expert Labs
版本: 1.0.0
日期: 2025/01/13

說明:
此腳本用於對 VS Code 擴充功能進行安全稽核，包括：
1. 授權條款檢查
2. 漏洞掃描
3. 軟體物料清單 (SBOM) 生成
4. 安全報告生成

使用方式:
python scan.py [--root <專案根目錄>] [--ovsx-registry <OpenVSX 註冊表 URL>]
"""

import argparse
import os
import sys
from pathlib import Path

# 導入模組化功能
from utils import log, ensure_dirs, require_bin
from config import read_policy, read_extensions_config
from extension_scanner import scan_one_extension
from report_generator import (
    write_summary_header,
    write_summary_row,
    write_summary_footer
)

# ---------- 預設值與路徑設定 ----------
ROOT_DIR = Path(__file__).resolve().parent.parent
WORK_DIR = os.path.join(ROOT_DIR, "work")
DIST_DIR = os.path.join(ROOT_DIR, "dist")
REPORT_DIR = os.path.join(ROOT_DIR, "reports")
EXTENSIONS_DIR = os.path.join(ROOT_DIR.parent, "extensions")
EXTENSIONS_CONFIG = os.path.join(ROOT_DIR.parent, "scripts", "configs", "extensions.yml")
POLICY = os.path.join(ROOT_DIR, "policy.yml")

# 預設 OpenVSX 註冊表；可透過命令列參數覆寫
DEFAULT_OVSX_REGISTRY = "https://open-vsx.org"
ENV_OVSX_REGISTRY = DEFAULT_OVSX_REGISTRY
BIN_SYFT = os.environ.get("SYFT_BIN", os.path.join(ROOT_DIR, "tools", "syft.exe"))
BIN_GRYPE = os.environ.get("GRYPE_BIN", os.path.join(ROOT_DIR, "tools", "grype.exe"))
BIN_OSV = os.environ.get("OSV_BIN", os.path.join(ROOT_DIR, "tools", "osv-scanner.exe"))
BIN_OVSX = os.environ.get("OVSX_BIN", "npx ovsx")

EXIT_OK = 0
EXIT_LICENSE_DENY = 42
EXIT_VULN_DENY = 43

# 嘗試導入 requests 模組
try:
    import requests
except Exception as e:
    print("::warning::'requests' 未安裝；將回退使用 'npx ovsx' 進行下載。", file=sys.stderr)
    requests = None


def main():
    parser = argparse.ArgumentParser(description="VS Code 擴充功能安全稽核 (Python MVP)")
    parser.add_argument("--root", default=str(ROOT_DIR), help="專案根目錄 (包含 policy.yml, extensions.yml)")
    parser.add_argument(
        "--ovsx-registry",
        default=DEFAULT_OVSX_REGISTRY,
        help="OpenVSX 註冊表基礎 URL。如果未提供，使用遠端預設值。"
    )
    args = parser.parse_args()

    # 從命令列覆寫註冊表
    global ENV_OVSX_REGISTRY
    ENV_OVSX_REGISTRY = args.ovsx_registry.rstrip("/") or DEFAULT_OVSX_REGISTRY

    ensure_dirs(WORK_DIR, DIST_DIR, REPORT_DIR)

    # 必要工具
    require_bin("python")  # 此直譯器
    # 僅在 HTTP 下載未使用或失敗時才需要 Node/npm
    # 外部掃描器：
    require_bin(BIN_SYFT)
    require_bin(BIN_GRYPE)
    require_bin(BIN_OSV)

    allow_licenses, deny_licenses, max_cvss = read_policy(POLICY)
    log(f"允許的授權條款: {', '.join(allow_licenses) if allow_licenses else '(任何)'}")
    log(f"拒絕的授權條款: {', '.join(deny_licenses) if deny_licenses else '(無)'}")
    log(f"允許的最大 CVSS: {max_cvss}")

    summary_md = os.path.join(REPORT_DIR, "summary.md")
    write_summary_header(summary_md, max_cvss)
    
    # 追蹤問題以進行摘要
    license_issues = []
    vuln_issues = []
    error_issues = []

    overall_rc = 0

    # 從 YAML 設定檔讀取擴充功能
    extensions = read_extensions_config(EXTENSIONS_CONFIG)
    log(f"從 {EXTENSIONS_CONFIG} 載入了 {len(extensions)} 個擴充功能")

    for source, pubext, version in extensions:
        try:
            rc = scan_one_extension(
                source=source,
                pubext=pubext,
                version=version,
                allow_licenses=allow_licenses,
                deny_licenses=deny_licenses,
                max_cvss=max_cvss,
                work_dir=WORK_DIR,
                dist_dir=DIST_DIR,
                report_dir=REPORT_DIR,
                extensions_dir=EXTENSIONS_DIR,
                registry_base=ENV_OVSX_REGISTRY,
                bin_ovsx=BIN_OVSX,
                bin_syft=BIN_SYFT,
                bin_grype=BIN_GRYPE,
                bin_osv=BIN_OSV,
                requests_module=requests
            )
        except Exception as e:
            log(f"處理 {pubext}@{version} 時發生錯誤: {e}")
            rc = 1
            error_issues.append(f"{pubext}@{version}: {e}")

        slug = f"{pubext.replace('.', '_')}-{version}"
        ext_report_dir = os.path.join(REPORT_DIR, slug)
        
        license_str = "-"
        lic_file = os.path.join(ext_report_dir, "license.txt")
        if os.path.exists(lic_file):
            with open(lic_file, "r", encoding="utf-8") as f:
                license_str = f.read().strip() or "-"

        sha = "-"
        sha_file = os.path.join(ext_report_dir, "sha256.txt")
        if os.path.exists(sha_file):
            with open(sha_file, "r", encoding="utf-8") as f:
                sha = f.read().strip() or "-"

        high = "-"
        sum_file = os.path.join(ext_report_dir, "summary.txt")
        if os.path.exists(sum_file):
            with open(sum_file, "r", encoding="utf-8") as f:
                for l in f.read().splitlines():
                    if l.startswith("high_or_equal_cvss_"):
                        high = l.split(":", 1)[1].strip()
                        break

        if rc == EXIT_OK:
            result = "PASS"
        elif rc == EXIT_LICENSE_DENY:
            result = "LICENSE_DENY"
            license_issues.append(f"{pubext}@{version}: {license_str}")
        elif rc == EXIT_VULN_DENY:
            result = "VULN_DENY"
            vuln_issues.append(f"{pubext}@{version}: {high} 個漏洞 >= CVSS {max_cvss}")
        else:
            result = "ERROR"

        write_summary_row(summary_md, pubext, version, license_str, result, None if high == "-" else int(high), sha)

        # 追蹤最嚴重的問題以獲得整體結果
        if rc != 0 and overall_rc == 0:
            overall_rc = rc

    # 在報告中加入問題摘要
    write_summary_footer(summary_md, license_issues, vuln_issues, error_issues)

    # 記錄摘要
    if license_issues:
        log(f"發現 {len(license_issues)} 個授權條款問題")
    if vuln_issues:
        log(f"發現 {len(vuln_issues)} 個漏洞問題")
    if error_issues:
        log(f"發現 {len(error_issues)} 個處理錯誤")
    
    log(f"整體結果代碼: {overall_rc}")
    log(f"報告生成於: {REPORT_DIR}")
    sys.exit(overall_rc)


if __name__ == "__main__":
    main()

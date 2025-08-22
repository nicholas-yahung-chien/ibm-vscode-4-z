#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
擴充功能掃描器模組
包含單一擴充功能的完整掃描流程
"""

import json
import os
import shutil
from utils import log, sha256_file, require_bin
from config import read_policy
from license_checker import (
    license_check, 
    find_license_in_directory, 
    read_license_file, 
    detect_license_from_content
)
from vsix_handler import (
    find_local_vsix,
    download_vsix_http,
    download_vsix_ovsx,
    unzip_vsix,
    find_package_json
)
from security_scanner import (
    syft_sbom,
    grype_scan_sbom,
    osv_scan_tree,
    count_high_from_grype
)
from report_generator import (
    write_extension_summary,
    write_result_file,
    write_license_file,
    write_sha256_file
)


def scan_one_extension(
    source: str, 
    pubext: str, 
    version: str, 
    allow_licenses: list, 
    deny_licenses: list, 
    max_cvss: float,
    work_dir: str,
    dist_dir: str,
    report_dir: str,
    extensions_dir: str,
    registry_base: str,
    bin_ovsx: str,
    bin_syft: str,
    bin_grype: str,
    bin_osv: str,
    requests_module
) -> int:
    """掃描單一擴充功能。"""
    name = f"{pubext}@{version}"
    slug = f"{pubext.replace('.', '_')}-{version}"
    out_dir = os.path.join(work_dir, slug)
    ext_dir = os.path.join(out_dir, "ext")
    vsix = os.path.join(dist_dir, f"{slug}.vsix")
    
    # 建立擴充功能專用的報告目錄
    ext_report_dir = os.path.join(report_dir, slug)
    os.makedirs(ext_report_dir, exist_ok=True)

    log(f"=== 處理中: {name} ({source}) ===")
    os.makedirs(out_dir, exist_ok=True)

    # 先檢查本地 VSIX
    local_vsix = find_local_vsix(pubext, version, extensions_dir)
    if local_vsix:
        log(f"找到本地 VSIX: {local_vsix}")
        # 將本地檔案複製到 dist 目錄
        shutil.copy2(local_vsix, vsix)
        log(f"已複製本地 VSIX 到: {vsix}")
    else:
        # 如果本地找不到，從 OpenVSX 下載
        if source != "openvsx":
            raise RuntimeError(f"未知來源: {source} (支援: openvsx)")

        log(f"未找到本地 VSIX，從 OpenVSX 下載中...")
        ok = False
        if requests_module is not None:
            ok = download_vsix_http(pubext, version, vsix, registry_base, requests_module)
        if not ok:
            # 回退到 npx ovsx
            require_bin(bin_ovsx)
            download_vsix_ovsx(pubext, version, vsix, registry_base, bin_ovsx)

    # SHA256
    sha = sha256_file(vsix)
    write_sha256_file(ext_report_dir, sha)

    # 解壓縮
    unzip_vsix(vsix, ext_dir)

    # 授權條款（MVP: package.json 授權條款）
    pkg = find_package_json(ext_dir)
    try:
        with open(pkg, "r", encoding="utf-8") as f:
            pkg_json = json.loads(f.read())
    except Exception as e:
        raise RuntimeError(f"解析 {pkg} 失敗: {e}")
    
    license_str = pkg_json.get("license") or "UNKNOWN"
    
    # 處理 "SEE * IN *" 格式
    if isinstance(license_str, str) \
        and license_str.upper().startswith("SEE") \
        and " IN " in license_str:
        log(f"找到授權條款參考: {license_str}")
        
        # 解析格式：SEE [LICENSE or LICENSE_TYPE] IN [filename]
        # 例如：SEE LICENSE IN LICENSE.md
        parts = license_str.split(" IN ")
        if len(parts) == 2:
            # 提取授權類型（去掉開頭的 "SEE "）
            license_type = parts[0][4:].strip()  # 移除 "SEE "
            filename = parts[1].strip()
            
            log(f"解析授權類型: {license_type}, 檔案: {filename}")
            
            # 嘗試讀取授權檔案
            license_content = read_license_file(ext_dir, f"SEE LICENSE IN {filename}")
            if license_content:
                detected_license = detect_license_from_content(license_content)
                log(f"授權內容偵測到: {detected_license}")
                license_str = detected_license
            else:
                # 如果無法讀取檔案，嘗試使用解析出的授權類型
                log(f"使用解析出的授權類型: {license_type}")
                license_str = license_type.upper()
        else:
            log(f"警告: 無法解析授權條款格式: {license_str}")
            # 如果無法解析，保留原始參考
    
    # 如果授權條款是 UNKNOWN 或缺失，嘗試在同一目錄中尋找 LICENSE 檔案
    if license_str == "UNKNOWN":
        log(f"在 package.json 中未找到授權條款，搜尋 LICENSE 檔案中...")
        license_content = find_license_in_directory(ext_dir)
        if license_content:
            detected_license = detect_license_from_content(license_content)
            log(f"從目錄搜尋偵測到授權內容: {detected_license}")
            license_str = detected_license
        else:
            log(f"警告: 在目錄中未找到 LICENSE 檔案")
    
    write_license_file(ext_report_dir, license_str)
    log(f"偵測到的授權條款: {license_str}")

    # 授權條款政策
    lc = license_check(str(license_str), allow_licenses, deny_licenses)
    license_result = "PASS"
    if lc == "deny":
        license_result = "LICENSE_DENY"
        write_result_file(ext_report_dir, "LICENSE_DENY", f"授權條款被拒絕: {license_str}")
        log(f"警告: {name} 的授權條款被拒絕: {license_str}")
    else:
        write_result_file(ext_report_dir, "PASS")

    # SBOM
    sbom = os.path.join(ext_report_dir, "cyclonedx.json")
    syft_sbom(ext_dir, sbom, bin_syft)

    # Grype
    grype_json = os.path.join(ext_report_dir, "grype.json")
    grype_scan_sbom(sbom, grype_json, bin_grype)

    # OSV
    osv_json = os.path.join(ext_report_dir, "osv.json")
    osv_scan_tree(ext_dir, osv_json, bin_osv)

    # 計算高嚴重性漏洞
    high = count_high_from_grype(grype_json, max_cvss)

    # 摘要檔案
    write_extension_summary(ext_report_dir, name, license_str, sbom, grype_json, osv_json, sha, high, max_cvss)

    # 根據漏洞更新結果
    if high > 0:
        vuln_result = "VULN_DENY"
        write_result_file(ext_report_dir, "VULN_DENY", f"漏洞被拒絕: {high} 個發現 >= CVSS {max_cvss}")
        log(f"警告: 發現 {name} 的漏洞: {high} 個發現 >= CVSS {max_cvss}")
    else:
        vuln_result = "PASS"
        # 如果授權條款已經被拒絕，不要覆寫
        if license_result == "PASS":
            write_result_file(ext_report_dir, "PASS")
    
    # 回傳最嚴重的結果
    if vuln_result == "VULN_DENY":
        return 43  # EXIT_VULN_DENY
    elif license_result == "LICENSE_DENY":
        return 42  # EXIT_LICENSE_DENY
    else:
        return 0  # EXIT_OK

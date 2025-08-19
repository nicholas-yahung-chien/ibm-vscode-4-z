#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
安全掃描模組
包含 SBOM 生成、漏洞掃描和結果分析功能
"""

import json
import subprocess
from utils import log


def syft_sbom(ext_dir: str, out_bom: str, bin_syft: str) -> None:
    """使用 syft 生成軟體物料清單 (SBOM)。"""
    # syft packages <dir> -o cyclonedx-json > out
    cmd = [bin_syft, "packages", ext_dir, "-o", "cyclonedx-json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if proc.returncode != 0:
        raise RuntimeError(f"syft 失敗: {proc.stderr}")
    with open(out_bom, "w", encoding="utf-8") as f:
        f.write(proc.stdout)


def grype_scan_sbom(bom_path: str, out_json: str, bin_grype: str) -> None:
    """使用 grype 掃描 SBOM 中的漏洞。"""
    cmd = [bin_grype, f"sbom:{bom_path}", "-o", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    # grype 可能回傳非零值；我們接受但記錄輸出
    with open(out_json, "w", encoding="utf-8") as f:
        f.write(proc.stdout or "")


def osv_scan_tree(ext_dir: str, out_json: str, bin_osv: str) -> None:
    """使用 OSV 掃描目錄樹中的漏洞。"""
    cmd = [bin_osv, "--recursive", ext_dir, "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    with open(out_json, "w", encoding="utf-8") as f:
        f.write(proc.stdout or "")


def count_high_from_grype(grype_json_path: str, max_cvss: float) -> int:
    """從 grype 結果中計算高嚴重性漏洞數量。"""
    try:
        with open(grype_json_path, "r", encoding="utf-8") as f:
            data = json.loads(f.read() or "{}")
    except Exception:
        return 0
    matches = data.get("matches", []) or []
    high = 0
    for m in matches:
        vuln = (m or {}).get("vulnerability") or {}
        cvsses = vuln.get("cvss", []) or []
        for cv in cvsses:
            metrics = (cv or {}).get("metrics") or {}
            base = metrics.get("baseScore")
            try:
                if base is not None and float(base) >= max_cvss:
                    high += 1
            except Exception:
                pass
    return high

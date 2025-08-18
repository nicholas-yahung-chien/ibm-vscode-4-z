#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
import zipfile
from pathlib import Path

try:
    import yaml  # PyYAML
except Exception as e:
    print("::error::PyYAML not installed. pip install pyyaml", file=sys.stderr)
    raise

try:
    import requests
except Exception as e:
    print("::warning::'requests' not installed; will fall back to 'npx ovsx' for downloads.", file=sys.stderr)
    requests = None

# ---------- Defaults & paths ----------
ROOT_DIR = Path(__file__).resolve().parent.parent
WORK_DIR = os.path.join(ROOT_DIR, "work")
DIST_DIR = os.path.join(ROOT_DIR, "dist")
REPORT_DIR = os.path.join(ROOT_DIR, "reports")
EXTENSIONS_DIR = os.path.join(ROOT_DIR.parent, "extensions")
EXTENSIONS_CONFIG = os.path.join(ROOT_DIR.parent, "scripts", "configs", "extensions.yml")
POLICY = os.path.join(ROOT_DIR, "policy.yml")

# Default OpenVSX registry; can be overridden via CLI argument
DEFAULT_OVSX_REGISTRY = "https://open-vsx.org"
ENV_OVSX_REGISTRY = DEFAULT_OVSX_REGISTRY
BIN_SYFT = os.environ.get("SYFT_BIN", os.path.join(ROOT_DIR, "tools", "syft.exe"))
BIN_GRYPE = os.environ.get("GRYPE_BIN", os.path.join(ROOT_DIR, "tools", "grype.exe"))
BIN_OSV = os.environ.get("OSV_BIN", os.path.join(ROOT_DIR, "tools", "osv-scanner.exe"))
BIN_OVSX = os.environ.get("OVSX_BIN", "npx ovsx")

EXIT_OK = 0
EXIT_LICENSE_DENY = 42
EXIT_VULN_DENY = 43

# ---------- Utilities ----------
def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def run(cmd, capture=False, check=True, text=True):
    """Run a command; return (code, stdout)."""
    if isinstance(cmd, str):
        shell = True
    else:
        shell = False
    
    # Ensure proper encoding for Windows compatibility
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    
    proc = subprocess.run(cmd, shell=shell, capture_output=capture, text=text, 
                         encoding='utf-8', errors='replace', env=env)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, proc.stdout, proc.stderr)
    return proc.returncode, (proc.stdout if capture else "")

def require_bin(name: str) -> None:
    """Ensure binary is available in PATH or as absolute path."""
    # Check if it's an absolute path
    if os.path.isabs(name):
        if not os.path.exists(name):
            raise RuntimeError(f"Missing binary: {name}")
        return
    
    # Check if it's in PATH
    if shutil.which(name.split()[0]) is None:
        raise RuntimeError(f"Missing binary: {name}")

def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def read_policy(policy_path):
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
    """Read extensions configuration from YAML file."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    
    extensions = []
    for publisher, ext_list in config.items():
        for ext_item in ext_list:
            # Handle both string and dict formats
            if isinstance(ext_item, dict):
                for ext_name, version in ext_item.items():
                    extensions.append(("openvsx", f"{publisher}.{ext_name}", version))
            elif isinstance(ext_item, str):
                # Handle simple string format if needed
                log(f"Warning: Unexpected string format in extensions config: {ext_item}")
    
    return extensions

def license_check(license_str: str, allow_list, deny_list) -> str:
    # Normalize license string
    license_str = license_str.strip()
    
    # Check exact match first
    if license_str in deny_list:
        return "deny"
    if license_str in allow_list:
        return "allow"
    
    # Handle special cases
    if license_str.startswith("SEE LICENSE IN"):
        # This usually means the license is in a separate file, often MIT or similar
        # We should have already processed this in scan_one, but just in case
        return "allow"  # Assume it's acceptable unless explicitly denied
    
    if license_str in ["UNKNOWN", "Proprietary", "Commercial"]:
        return "deny"  # Unknown licenses are denied by default
    
    # Convert to lowercase for case-insensitive comparison
    license_lower = license_str.lower()
    
    # Normalize common license variations
    # Replace spaces with hyphens for common patterns
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
    
    # Remove common suffixes like "(see LICENSE.txt)", "(see LICENSE)", etc.
    import re
    normalized_license = re.sub(r'\s*\(see\s+[^)]+\)', '', normalized_license)
    normalized_license = re.sub(r'\s*\([^)]*license[^)]*\)', '', normalized_license)
    
    # Check normalized license against allow list
    for allowed in allow_list:
        allowed_lower = allowed.lower()
        if normalized_license == allowed_lower:
            return "allow"
        # Also check if the normalized license contains the allowed license
        if allowed_lower in normalized_license:
            return "allow"
    
    # Check normalized license against deny list
    for denied in deny_list:
        denied_lower = denied.lower()
        if normalized_license == denied_lower:
            return "deny"
        # Also check if the normalized license contains the denied license
        if denied_lower in normalized_license:
            return "deny"
    
    # Split into words and create a set for efficient lookup
    license_words = set(license_lower.split())
    
    # Check if any allowed license is contained as whole words (case insensitive)
    for allowed in allow_list:
        allowed_lower = allowed.lower()
        # Check exact match first
        if license_lower == allowed_lower:
            return "allow"
        # Check if the allowed license is a single word that exists in the license string
        if allowed_lower in license_words:
            return "allow"
        # Check if the allowed license contains multiple words and all are present
        allowed_words = allowed_lower.split()
        if len(allowed_words) > 1 and all(word in license_words for word in allowed_words):
            return "allow"
        # Check if the allowed license contains hyphens (like "EPL-2.0")
        if "-" in allowed_lower and allowed_lower in license_lower:
            # For hyphenated licenses, check if they appear as a whole in the license string
            # This handles cases like "EPL-2.0" in "This is EPL-2.0 licensed"
            return "allow"
    
    # Check if any denied license is contained as whole words (case insensitive)
    for denied in deny_list:
        denied_lower = denied.lower()
        # Check exact match first
        if license_lower == denied_lower:
            return "deny"
        # Check if the denied license is a single word that exists in the license string
        if denied_lower in license_words:
            return "deny"
        # Check if the denied license contains multiple words and all are present
        denied_words = denied_lower.split()
        if len(denied_words) > 1 and all(word in license_words for word in denied_words):
            return "deny"
        # Check if the denied license contains hyphens
        if "-" in denied_lower and denied_lower in license_lower:
            return "deny"
    
    # If we have an allow list and the license is not in it, deny
    if allow_list:
        return "deny"
    
    # If no allow list, allow everything except explicitly denied
    return "allow"

def ensure_dirs():
    os.makedirs(WORK_DIR, exist_ok=True)
    os.makedirs(DIST_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)

def find_local_vsix(publisher_ext: str, version: str) -> str:
    """Find local VSIX file in extensions directory."""
    import glob
    
    # Try different naming patterns with flexible matching
    patterns = [
        # Exact matches first
        f"{publisher_ext}-{version}.vsix",
        f"{publisher_ext.replace('.', '_')}-{version}.vsix",
        f"{publisher_ext}@{version}.vsix",
        
        # Flexible patterns that allow any characters between version and .vsix
        f"{publisher_ext}-{version}*.vsix",
        f"{publisher_ext.replace('.', '_')}-{version}*.vsix",
        f"{publisher_ext}@{version}*.vsix",
        
        # Also try with underscore replacement for publisher
        f"{publisher_ext.replace('.', '_')}-{version}*.vsix",
        f"{publisher_ext.replace('.', '_')}@{version}*.vsix",
        
        # Try patterns with different separators
        f"{publisher_ext}_{version}*.vsix",
        f"{publisher_ext.replace('.', '_')}_{version}*.vsix",
    ]
    
    for pattern in patterns:
        # Use glob to find files matching the pattern
        search_pattern = os.path.join(EXTENSIONS_DIR, pattern)
        matching_files = glob.glob(search_pattern)
        
        if matching_files:
            # Return the first match
            return matching_files[0]
    
    # If no pattern matches, try a more flexible search
    # Look for files that contain both publisher_ext and version
    try:
        for filename in os.listdir(EXTENSIONS_DIR):
            if filename.endswith('.vsix'):
                # Check if filename contains both publisher and version
                publisher_clean = publisher_ext.replace('.', '_')
                if (publisher_ext in filename or publisher_clean in filename) and version in filename:
                    return os.path.join(EXTENSIONS_DIR, filename)
    except Exception as e:
        log(f"Warning: Error during flexible VSIX search: {e}")
    
    return None

def vsix_url_openvsx(publisher: str, ext: str, version: str) -> str:
    # https://open-vsx.org/api/{publisher}/{extension}/{version}/file/{publisher}.{extension}-{version}.vsix
    base = ENV_OVSX_REGISTRY.rstrip("/")
    return f"{base}/api/{publisher}/{ext}/{version}/file/{publisher}.{ext}-{version}.vsix"

def download_vsix_http(publisher_ext: str, version: str, out_path) -> bool:
    if requests is None:
        return False
    publisher, ext = publisher_ext.split(".", 1)
    url = vsix_url_openvsx(publisher, ext, version)
    log(f"Trying HTTP download: {url}")
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            if r.status_code != 200:
                log(f"HTTP download failed: HTTP {r.status_code}")
                return False
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as e:
        log(f"HTTP download error: {e}")
        return False

def download_vsix_ovsx(publisher_ext: str, version: str, out_path) -> None:
    # npx ovsx get publisher.extension --version X --registryUrl ... -o path
    cmd = f'{BIN_OVSX} get {publisher_ext} --version {version} --registryUrl {ENV_OVSX_REGISTRY} --out "{out_path}"'
    run(cmd, check=True)

def unzip_vsix(vsix_path, dest_dir) -> None:
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    
    # Check if file is a valid ZIP file
    try:
        with zipfile.ZipFile(vsix_path, "r") as zf:
            zf.extractall(dest_dir)
    except zipfile.BadZipFile:
        # Check if it's an HTML error page
        with open(vsix_path, "r", encoding="utf-8") as f:
            content = f.read(1000)  # Read first 1000 chars
            if "<!DOCTYPE html>" in content or "<html" in content:
                raise RuntimeError(f"Downloaded file is an HTML page, not a VSIX file. The extension may not exist on OpenVSX or requires authentication.")
            else:
                raise RuntimeError(f"Downloaded file is not a valid ZIP file: {vsix_path}")

def find_package_json(ext_dir) -> str:
    p1 = os.path.join(ext_dir, "extension", "package.json")
    p2 = os.path.join(ext_dir, "package.json")
    if os.path.exists(p1):
        return p1
    if os.path.exists(p2):
        return p2
    raise FileNotFoundError("No package.json found in VSIX.")

def find_license_in_directory(ext_dir: str) -> str:
    """Find and read license files in the extension directory."""
    # Common license file names to search for
    license_files = [
        "LICENSE.txt",
        "LICENSE.md", 
        "LICENSE",
        "license.txt",
        "license.md",
        "license"
    ]
    
    # Search in the extension directory and its subdirectories
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
                            log(f"Found license file: {license_path}")
                            return content
                except Exception as e:
                    log(f"Warning: Failed to read license file {license_path}: {e}")
    
    return None

def read_license_file(ext_dir: str, license_ref: str) -> str:
    """Read license content from referenced file."""
    if not license_ref.startswith("SEE LICENSE IN "):
        return None
    
    # Extract filename from "SEE LICENSE IN filename"
    filename = license_ref[15:].strip()
    
    # Try different possible locations
    possible_paths = [
        os.path.join(ext_dir, filename),
        os.path.join(ext_dir, "extension", filename),
        os.path.join(ext_dir, "..", filename),
        os.path.join(ext_dir, "extension", "..", filename),
        # Also try common variations
        os.path.join(ext_dir, filename + ".txt"),
        os.path.join(ext_dir, filename + ".md"),
        os.path.join(ext_dir, "extension", filename + ".txt"),
        os.path.join(ext_dir, "extension", filename + ".md"),
        # Try without extension if filename has one
        os.path.join(ext_dir, filename.split('.')[0]),
        os.path.join(ext_dir, "extension", filename.split('.')[0])
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    # Return the entire file content for license detection
                    if len(content) > 0:
                        return content
            except Exception as e:
                log(f"Warning: Failed to read license file {path}: {e}")
    
    return None

def detect_license_from_content(content: str) -> str:
    """Detect license type from license file content."""
    content_upper = content.upper()
    
    # Split content into words for whole word matching
    content_words = set(content_upper.split())

    # Detected license
    detected_license = "UNKNOWN"
    
    # Common license patterns - check more specific patterns first
    # Use whole word matching to avoid false positives
    
    # Check for Eclipse Public License (prioritize over GPL)
    if "ECLIPSE" in content_words and "PUBLIC" in content_words and "LICENSE" in content_words:
        # Check for version 2 in the content (not just as a separate word)
        if "VERSION" in content_words and ("2" in content_words or "V.2" in content_upper or "VERSION 2" in content_upper) or "EPL-2" in content_words:
            detected_license = "EPL-2.0"
        else:
            detected_license = "EPL-1.0"
    
    # Check for GNU General Public License
    elif "GNU" in content_words and "GENERAL" in content_words and "PUBLIC" in content_words and "LICENSE" in content_words:
        if "VERSION" in content_words and "3" in content_words or "GPL-3" in content_words:
            detected_license = "GPL-3.0"
        elif "VERSION" in content_words and "2" in content_words or "GPL-2" in content_words:
            detected_license = "GPL-2.0"
        else:
            detected_license = "GPL"
    
    # Check for BSD licenses
    elif "BSD" in content_words and "LICENSE" in content_words:
        if "3-CLAUSE" in content_words or "3" in content_words:
            detected_license = "BSD-3-Clause"
        elif "2-CLAUSE" in content_words or "2" in content_words:
            detected_license = "BSD-2-Clause"
        else:
            detected_license = "BSD-3-Clause"  # Default to 3-clause if not specified
    
    # Check for Apache License
    elif "APACHE" in content_words and "LICENSE" in content_words:
        detected_license = "Apache-2.0"
    
    # Check for MIT License
    elif "MIT" in content_words and "LICENSE" in content_words:
        detected_license = "MIT"
    
    # Check for Mozilla Public License
    elif "MOZILLA" in content_words and "PUBLIC" in content_words and "LICENSE" in content_words:
        detected_license = "MPL-2.0"
    
    # Check for ISC License
    elif "ISC" in content_words and "LICENSE" in content_words:
        detected_license = "ISC"
    
    # Fallback: check for common license abbreviations as whole words
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
    
    # Private co-operation licesne usually has broader scope
    # Check for Broadcom
    if "BROADCOM" in content_words:
        detected_license = "Broadcom"
    
    # Check for IBM
    elif "IBM" in content_words:
        detected_license = "IBM"

    # Check for Microsoft
    elif "MICROSOFT" in content_words:
        detected_license = "Microsoft"

    # Otherwise
    if detected_license == "UKNOWN":
        # For unknown licenses, try to extract a meaningful identifier
        # Look for common patterns in the first few lines
        lines = content.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if line and len(line) > 10 and len(line) < 100:
                # Return a reasonable identifier from the first meaningful line
                detected_license = line[:80] + "..." if len(line) > 80 else line
        
        # If no meaningful line found, return a truncated version
        if len(content) > 100:
            detected_license = content[:100] + "..."
        else:
            detected_license = content
    
    return detected_license

def syft_sbom(ext_dir, out_bom) -> None:
    # syft packages <dir> -o cyclonedx-json > out
    cmd = [BIN_SYFT, "packages", ext_dir, "-o", "cyclonedx-json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if proc.returncode != 0:
        raise RuntimeError(f"syft failed: {proc.stderr}")
    with open(out_bom, "w", encoding="utf-8") as f:
        f.write(proc.stdout)

def grype_scan_sbom(bom_path, out_json) -> None:
    cmd = [BIN_GRYPE, f"sbom:{bom_path}", "-o", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    # grype may return non-zero; we accept but record output
    with open(out_json, "w", encoding="utf-8") as f:
        f.write(proc.stdout or "")

def osv_scan_tree(ext_dir, out_json) -> None:
    cmd = [BIN_OSV, "--recursive", ext_dir, "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    with open(out_json, "w", encoding="utf-8") as f:
        f.write(proc.stdout or "")

def count_high_from_grype(grype_json_path, max_cvss: float) -> int:
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

def write_summary_row(summary_md, pubext: str, version: str, license_str: str, result: str, high: int, sha: str):
    row = f"| `{pubext}@{version}` | `{license_str}` | **{result}** | {high if high is not None else '-'} | `{sha or '-'}` |\n"
    with open(summary_md, "a", encoding="utf-8") as f:
        f.write(row)

# ---------- Core per-extension ----------
def scan_one(source: str, pubext: str, version: str, allow_licenses, deny_licenses, max_cvss: float) -> int:
    name = f"{pubext}@{version}"
    slug = f"{pubext.replace('.', '_')}-{version}"
    out_dir = os.path.join(WORK_DIR, slug)
    ext_dir = os.path.join(out_dir, "ext")
    vsix = os.path.join(DIST_DIR, f"{slug}.vsix")
    
    # Create extension-specific report directory
    ext_report_dir = os.path.join(REPORT_DIR, slug)
    os.makedirs(ext_report_dir, exist_ok=True)

    log(f"=== Processing: {name} ({source}) ===")
    os.makedirs(out_dir, exist_ok=True)

    # Check for local VSIX first
    local_vsix = find_local_vsix(pubext, version)
    if local_vsix:
        log(f"Found local VSIX: {local_vsix}")
        # Copy local file to dist directory
        shutil.copy2(local_vsix, vsix)
        log(f"Copied local VSIX to: {vsix}")
    else:
        # Download from OpenVSX if not found locally
        if source != "openvsx":
            raise RuntimeError(f"Unknown source: {source} (supported: openvsx)")

        log(f"No local VSIX found, downloading from OpenVSX...")
        ok = False
        if requests is not None:
            ok = download_vsix_http(pubext, version, vsix)
        if not ok:
            # fallback to npx ovsx
            require_bin(BIN_OVSX)
            download_vsix_ovsx(pubext, version, vsix)

    # SHA256
    sha = sha256_file(vsix)
    with open(os.path.join(ext_report_dir, "sha256.txt"), "w", encoding="utf-8") as f:
        f.write(sha + "\n")

    # Unzip
    unzip_vsix(vsix, ext_dir)

    # License (MVP: package.json license)
    pkg = find_package_json(ext_dir)
    try:
        with open(pkg, "r", encoding="utf-8") as f:
            pkg_json = json.loads(f.read())
    except Exception as e:
        raise RuntimeError(f"Failed to parse {pkg}: {e}")
    
    license_str = pkg_json.get("license") or "UNKNOWN"
    
    # Handle "SEE LICENSE IN" format
    if isinstance(license_str, str) and license_str.startswith("SEE LICENSE IN "):
        log(f"Found license reference: {license_str}")
        license_content = read_license_file(ext_dir, license_str)
        if license_content:
            detected_license = detect_license_from_content(license_content)
            log(f"License content detected: {detected_license}")
            license_str = detected_license
        else:
            log(f"Warning: Could not read license file referenced in: {license_str}")
            # Keep the original reference if we can't read the file
    
    # If license is UNKNOWN or missing, try to find LICENSE files in the same directory
    if license_str == "UNKNOWN":
        log(f"No license found in package.json, searching for LICENSE files...")
        license_content = find_license_in_directory(ext_dir)
        if license_content:
            detected_license = detect_license_from_content(license_content)
            log(f"License content detected from directory search: {detected_license}")
            license_str = detected_license
        else:
            log(f"Warning: No LICENSE file found in directory")
    
    with open(os.path.join(ext_report_dir, "license.txt"), "w", encoding="utf-8") as f:
        f.write(str(license_str) + "\n")
    log(f"License detected: {license_str}")

    # License policy
    lc = license_check(str(license_str), allow_licenses, deny_licenses)
    license_result = "PASS"
    if lc == "deny":
        license_result = "LICENSE_DENY"
        with open(os.path.join(ext_report_dir, "result.txt"), "w", encoding="utf-8") as f:
            f.write(f"License denied: {license_str}\n")
        log(f"Warning: License denied for {name}: {license_str}")
    else:
        with open(os.path.join(ext_report_dir, "result.txt"), "w", encoding="utf-8") as f:
            f.write("PASS\n")

    # SBOM
    sbom = os.path.join(ext_report_dir, "cyclonedx.json")
    syft_sbom(ext_dir, sbom)

    # Grype
    grype_json = os.path.join(ext_report_dir, "grype.json")
    grype_scan_sbom(sbom, grype_json)

    # OSV
    osv_json = os.path.join(ext_report_dir, "osv.json")
    osv_scan_tree(ext_dir, osv_json)

    # Count high
    high = count_high_from_grype(grype_json, max_cvss)

    # Summary files
    summary_txt = textwrap.dedent(f"""\
    extension: {name}
    license: {license_str}
    sbom: {os.path.basename(sbom)}
    grype: {os.path.basename(grype_json)}
    osv: {os.path.basename(osv_json)}
    sha256: {sha}
    high_or_equal_cvss_{str(max_cvss).replace('.', '_')}: {high}
    """)
    with open(os.path.join(ext_report_dir, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary_txt)

    # Update result based on vulnerabilities
    if high > 0:
        vuln_result = "VULN_DENY"
        with open(os.path.join(ext_report_dir, "result.txt"), "w", encoding="utf-8") as f:
            f.write(f"Vulnerability denied: {high} findings >= CVSS {max_cvss}\n")
        log(f"Warning: Vulnerabilities found for {name}: {high} findings >= CVSS {max_cvss}")
    else:
        vuln_result = "PASS"
        # Don't overwrite if license was already denied
        if license_result == "PASS":
            with open(os.path.join(ext_report_dir, "result.txt"), "w", encoding="utf-8") as f:
                f.write("PASS\n")
    
    # Return the most severe result
    if vuln_result == "VULN_DENY":
        return EXIT_VULN_DENY
    elif license_result == "LICENSE_DENY":
        return EXIT_LICENSE_DENY
    else:
        return EXIT_OK

# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(description="VS Code Extensions Audit (Python MVP)")
    parser.add_argument("--root", default=str(ROOT_DIR), help="Project root (contains policy.yml, extensions.yml)")
    parser.add_argument(
        "--ovsx-registry",
        default=DEFAULT_OVSX_REGISTRY,
        help="OpenVSX Registry base URL. If not provided, uses remote default."
    )
    args = parser.parse_args()

    # Override registry from CLI
    global ENV_OVSX_REGISTRY
    ENV_OVSX_REGISTRY = args.ovsx_registry.rstrip("/") or DEFAULT_OVSX_REGISTRY

    ensure_dirs()

    # Required tools
    require_bin("python")  # this interpreter
    # Node/npm only needed if HTTP download not used or fails
    # External scanners:
    require_bin(BIN_SYFT)
    require_bin(BIN_GRYPE)
    require_bin(BIN_OSV)

    allow_licenses, deny_licenses, max_cvss = read_policy(POLICY)
    log(f"Allowed licenses: {', '.join(allow_licenses) if allow_licenses else '(any)'}")
    log(f"Denied licenses: {', '.join(deny_licenses) if deny_licenses else '(none)'}")
    log(f"Max CVSS allowed: {max_cvss}")

    summary_md = os.path.join(REPORT_DIR, "summary.md")
    with open(summary_md, "w", encoding="utf-8") as f:
        f.write("# VS Code Extensions Audit Report\n\n")
        f.write(f"| Extension | License | Result | High(CVSS>={max_cvss}) | SHA256 |\n")
        f.write("|---|---|---:|---:|---|\n")
    
    # Track issues for summary
    license_issues = []
    vuln_issues = []
    error_issues = []

    overall_rc = 0

    # Read extensions from YAML config
    extensions = read_extensions_config(EXTENSIONS_CONFIG)
    log(f"Loaded {len(extensions)} extensions from {EXTENSIONS_CONFIG}")

    for source, pubext, version in extensions:
        try:
            rc = scan_one(source, pubext, version, allow_licenses, deny_licenses, max_cvss)
        except Exception as e:
            log(f"Error processing {pubext}@{version}: {e}")
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
            vuln_issues.append(f"{pubext}@{version}: {high} vulnerabilities >= CVSS {max_cvss}")
        else:
            result = "ERROR"

        write_summary_row(summary_md, pubext, version, license_str, result, None if high == "-" else int(high), sha)

        # Track the most severe issue for overall result
        if rc != 0 and overall_rc == 0:
            overall_rc = rc

    # Add summary of issues to the report
    with open(summary_md, "a", encoding="utf-8") as f:
        f.write("\n## Summary of Issues\n\n")
        
        if license_issues:
            f.write("### License Issues\n\n")
            f.write("The following extensions have license issues:\n\n")
            for issue in license_issues:
                f.write(f"- {issue}\n")
            f.write("\n")
        
        if vuln_issues:
            f.write("### Vulnerability Issues\n\n")
            f.write("The following extensions have vulnerability issues:\n\n")
            for issue in vuln_issues:
                f.write(f"- {issue}\n")
            f.write("\n")
        
        if error_issues:
            f.write("### Processing Errors\n\n")
            f.write("The following extensions encountered processing errors:\n\n")
            for issue in error_issues:
                f.write(f"- {issue}\n")
            f.write("\n")
        
        if not license_issues and not vuln_issues and not error_issues:
            f.write("✅ No issues found. All extensions passed the audit.\n\n")
        else:
            f.write(f"⚠️  Total issues found: {len(license_issues)} license issues, {len(vuln_issues)} vulnerability issues, {len(error_issues)} processing errors\n\n")

    # Log summary
    if license_issues:
        log(f"Found {len(license_issues)} license issues")
    if vuln_issues:
        log(f"Found {len(vuln_issues)} vulnerability issues")
    if error_issues:
        log(f"Found {len(error_issues)} processing errors")
    
    log(f"Overall result code: {overall_rc}")
    log(f"Reports generated under: {REPORT_DIR}")
    sys.exit(overall_rc)


if __name__ == "__main__":
    main()

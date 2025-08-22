# 工具安全掃描報告

| 工具名稱 | 版本 | CPE 名稱 | 最高 CVSS | 高風險漏洞數量 | 狀態 |
|---|---|---|---|---|---|
| vscode | 1.101.0 | `cpe:2.3:a:microsoft:visual_studio_code:-:*:*:*:*:*:*:*` | 0.0 | 0 | ✅ 通過檢查 (最高 CVSS: 0.0) |
| python | 3.13.3 | `cpe:2.3:a:python:python:-:*:*:*:*:*:*:*` | 8.8 | 1 | ⚠️ 發現 1 個高風險漏洞 (最高 CVSS: 8.8) |
| nodejs | 22.16.0 | `cpe:2.3:a:nodejs:node.js:-:*:*:*:*:*:*:*` | 7.5 | 0 | ✅ 通過檢查 (最高 CVSS: 7.5) |
| groovy | 4.0.27 | `cpe:2.3:a:apache:groovy:-:*:*:*:*:*:*:*` | 0.0 | 0 | ✅ 通過檢查 (最高 CVSS: 0.0) |
| git | 2.50.0 | `cpe:2.3:a:git-scm:git:-:*:*:*:*:*:*:*` | 0.0 | 0 | ✅ 通過檢查 (最高 CVSS: 0.0) |
| maven | 3.9.11 | `cpe:2.3:a:apache:maven:-:*:*:*:*:*:*:*` | 0.0 | 0 | ✅ 通過檢查 (最高 CVSS: 0.0) |
| zowe-core | 3.2.0 | `cpe:2.3:a:zowe:zowe_cli:-:*:*:*:*:*:*:*` | 5.9 | 0 | ✅ 通過檢查 (最高 CVSS: 5.9) |
| java21 | 21.0.7 | `cpe:2.3:a:ibm:semeru_runtime:-:*:*:*:*:*:*:*` | 0.0 | 0 | ✅ 通過檢查 (最高 CVSS: 0.0) |

## 詳細漏洞資訊

### python@3.13.3

**CPE:** `cpe:2.3:a:python:python:3.13.3:*:*:*:*:*:*:*`

**最高 CVSS 分數:** 8.8

**高風險漏洞數量:** 1

**漏洞列表:**

- CVE-2020-29396 (CVSS: 8.8) - A sandboxing issue in Odoo Community 11.0 through 13.0 and Odoo Enterprise 11.0 through 13.0, when running with Python 3.6 or later, allows remote authenticated users to execute arbitrary code, leading to privilege escalation.


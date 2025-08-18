# VS Code Extensions Audit (Windows MVP)

以 **PowerShell** 在 Windows 上稽核 VS Code 擴充套件：
- 來源：Open VSX（可改私有 Open VSX）
- 產出：CycloneDX SBOM（Syft）、弱點掃描（Grype + OSV-Scanner）、License（取 package.json）
- 政策：`policy.yml`
- 清單：`extensions.allowlist`

## 本機使用
1. 安裝：
   - Node.js，並執行 `npm i -g ovsx`
   - Python 3
   - 下載並放入 PATH：
     - Syft（Windows）
     - Grype（Windows）
     - OSV-Scanner（Windows）
2. 執行：
   ```powershell
   pwsh -File scripts/scan.ps1

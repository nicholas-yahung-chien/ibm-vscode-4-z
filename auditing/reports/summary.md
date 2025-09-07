
## 掃描範圍

本稽核包含以下三個方面的安全檢查：

1. **VS Code 擴充功能** - 檢查授權條款和漏洞
2. **PyPI 套件** - 檢查 Python 套件的漏洞
3. **工具軟體** - 檢查 tools.yml 中有 CPE 設定的工具漏洞

---

# VS Code 擴充功能安全稽核報告

| 擴充功能 | 授權條款 | 稽核結果 | 高風險漏洞數量 (CVSS≥8.0) | SHA256 雜湊值 |
|---|---|---|---|---|
| `ibm.zopendebug@5.5.2` | `IBM` | **通過** | 0 | `b7e2b3ff8a0c5adaf6546418e62465cc253372790a71ba5d46e0bf5765364b39` |
| `ibm.zopeneditor@5.7.1` | `IBM` | **通過** | 0 | `9675aefc5d6007321fde2af340f8abffd3b436ee99237ba3f2e3f04c1f13bf57` |
| `ibm.zcommoncomponent@16.1.125082220` | `IBM` | **通過** | 0 | `1b036d0820bcb66991423737e2a25bc258051fd0cdaab8701896a12feec7816b` |
| `ibm.zfilemanager@16.1.125082220` | `IBM` | **通過** | 0 | `69f60f4fc9692d948764e699d3536952a7b53986464743e7abd6acf78a081a3e` |
| `ibm.zfaultanalyzer@16.1.125082220` | `IBM` | **通過** | 0 | `7d5abf50b3473be13b55a8dfc12296f8673375eeef420261a3b5faa194d41244` |
| `ibm.db2forzosdeveloperextension@2.2.3` | `IBM` | **通過** | 0 | `cc9af0189c959a8a3205d680994a7fe7aa13c22af31d6bbb60148afc30c23c78` |
| `ibm.ibm-developer@1.0.1` | `Apache 2.0 (see LICENSE.txt)` | **通過** | 0 | `ddd7093ba265eec5c739dc95069121b6644a68e3d04957d18a198aacca3a8e06` |
| `ibm.wca-core@1.6.2` | `IBM` | **通過** | 0 | `df4ffbe81160330c91be98b3ed140f5d26f87e6c956f4cfc1c0778cc95e7f554` |
| `vscjava.vscode-maven@0.44.2024072906` | `MIT` | **通過** | 0 | `f52f19cde7e0f62de76623d902d5b9693d3b769667855d30f433f9bdd9c4b457` |
| `broadcommfd.explorer-for-endevor@1.11.1` | `Broadcom` | **通過** | 0 | `843313b3f3d4ca53c3566bd463259a1f777a2dff344ece8a1948910dd704312e` |
| `broadcommfd.abend-analyzer@1.3.0` | `Broadcom` | **通過** | 0 | `fb49b98a3d87684332f193df40230d2ff07d742c4cde225e62dc646ca8211953` |
| `broadcommfd.ccf@1.2.1` | `Broadcom` | **通過** | 0 | `11523100625a69b4ab3b40ca50f5e9bab89a1cb06fcb1f2a7187ea408ace0953` |
| `broadcommfd.data-editor-for-mainframe@1.0.0` | `Broadcom` | **通過** | 0 | `1b57bf384fd42a3d77b490e7b5c3cd5057a01645a826fda9efdfef0e3d01c949` |
| `broadcommfd.debugger-for-mainframe@1.13.0` | `Broadcom` | **通過** | 0 | `67414c183c747797e4eea77ec33e99165cb042b9d10e7aa741d69595af78bf9d` |
| `broadcommfd.hlasm-language-support@1.17.0` | `EPL-2.0` | **通過** | 0 | `54deddb05c2af4e5f5bc0456ced18c9aef846f5466eb3e6192cf818003fe8006` |
| `broadcommfd.cobol-language-support@2.4.0` | `EPL-2.0` | **通過** | 0 | `05af9e5aab193cf710b78c8f8c3ed62f8f2158a81209c9b63574fd17a0aaecc4` |
| `broadcommfd.jcl-language-support@3.0.0` | `Broadcom` | **通過** | 0 | `f2ae4f1a1a73edc6158f72ff963e06b6b74d6930e16725aaedda76a056acdb4a` |
| `broadcommfd.lsp-for-rexx@0.0.22` | `Broadcom` | **通過** | 0 | `10fb65628b5ff801351b7c527c02b807a2c1a76f5d27a4160bdd56dabce3e87e` |
| `zowe.cics-extension-for-zowe@3.11.0` | `EPL-2.0` | **通過** | 0 | `c6b434ae624867b5995cd425086824a9ae550b5140bc01c3c8990e00a9714677` |
| `zowe.zowe-explorer-ftp-extension@3.2.2` | `EPL-2.0` | **通過** | 0 | `e460967e6c4efff075074623f8ffebd27bb6e81248872d0e8536b36476ab49a7` |
| `zowe.vscode-extension-for-zowe@3.2.2` | `EPL-2.0` | **通過** | 0 | `9af31efb26e3e87cc6fb7ba0ab97d1ee3142286fd5ecbb40db1610b3aeec9f5e` |
| `continue.continue@1.2.2` | `Apache-2.0` | **通過** | 0 | `25cb62141901d8fb2034afba3bd398f1f47b15518b5f23db78429a9714b3ebda` |
| `redhat.vscode-yaml@1.18.0` | `MIT` | **通過** | 0 | `52dc43a65391516aa6896e88f27e1984aec70107520c6e1dc3b33f71b8e49996` |
| `redhat.ansible@25.4.0` | `MIT` | **通過** | 0 | `13f06880db5ac78764bfa86561c6918a74f1af88e757257d85509d90892e97db` |
| `ms-vscode-remote.remote-wsl@0.99.0` | `Microsoft` | **通過** | 0 | `cf0338823d75b0cd341e368e505119efb566d3b8820f0c0f984aa227dee45cbf` |
| `ms-vscode-remote.remote-ssh@0.120.0` | `Microsoft` | **通過** | 0 | `0fd6262ca183b486f6c067cb3516dccea2f87f32c049b642ff9eb77b0cea195d` |
| `ms-vscode-remote.remote-containers@0.422.0` | `Microsoft` | **通過** | 0 | `50c5c265ef27bf038092b1f134aabe2fe01832832fab6a230e7e4dacc75338d9` |
| `ms-vscode.remote-server@1.5.2` | `Microsoft` | **通過** | 0 | `1aa6f7fdf4904b7ad885ea054bc92ca2275a66b3a57717983e81529734a09952` |
| `ms-ceintl.vscode-language-pack-zh-hant@1.101.2025061109` | `Microsoft` | **通過** | 0 | `e005e98897c57783e9311f3d2105939f3794fa7dd13b098cd70688fa1d2876ba` |

## 問題摘要

✅ **稽核成功** - 所有擴充功能、PyPI 套件和工具都通過了安全檢查，未發現任何問題。


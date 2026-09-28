# Outlook Leak Line Scanner

在 GitHub 代码中扫描下面这种泄露行：

```text
邮箱----密码----client_id----refresh_token
```

命中后不验证，不做 JSON，不拆字段，直接把完整原始行逐行追加到：

```text
results.txt
```

## GitHub Actions

工作流文件：

```text
.github/workflows/scan.yml
```

运行方式：

1. 在仓库 `Settings -> Secrets and variables -> Actions` 添加 `GH_TOKEN`。
2. `GH_TOKEN` 使用有 `public_repo` 或 `repo` 权限的 GitHub Token。
3. 打开 `Actions -> Scan Outlook Leak Lines -> Run workflow`。
4. 扫描完成后在本次运行的 `Artifacts` 下载 `outlook-results-*`。

工作流默认每 6 小时运行一次。

## 本地运行

```bash
pip install -r requirements.txt

export GITHUB_TOKEN=ghp_xxx
python cli.py scan
```

Windows PowerShell：

```powershell
$env:GITHUB_TOKEN="ghp_xxx"
python cli.py scan
```

## 可调配置

通过环境变量覆盖：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SEARCH_QUERIES` | 内置 5 组查询 | 使用 `|` 分隔多个 GitHub 搜索语句 |
| `MAX_PAGES` | `3` | 每个搜索语句最多拉取页数 |
| `MAX_FILES_PER_SCAN` | `500` | 单次最多下载匹配文件数 |
| `MAX_FILE_BYTES` | `2000000` | 超过该大小的文件跳过 |
| `MIN_REFRESH_TOKEN_LENGTH` | `80` | refresh token 最短长度 |
| `RESULTS_FILE` | `results.txt` | 输出路径 |

`results.txt` 已加入 `.gitignore`，不要提交到仓库。

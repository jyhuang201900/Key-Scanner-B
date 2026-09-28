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

1. 打开 `Actions -> Scan Outlook Leak Lines`。
2. 点击 `Run workflow`。
3. 扫描完成后在本次运行的 `Artifacts` 下载 `outlook-results-*`。

工作流默认使用 GitHub Actions 内置的 `github.token`，不需要额外配置 Secret。
默认每 6 小时运行一次，修改扫描器代码后也会自动运行一次。

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
| `SEARCH_QUERIES` | 内置 12 组查询 | 使用 `|` 分隔多个 GitHub 搜索语句 |
| `MAX_PAGES` | `10` | 每个搜索语句最多拉取页数 |
| `MAX_FILES_PER_QUERY` | `250` | 每条查询最多检查文件数 |
| `MAX_FILES_PER_SCAN` | `3000` | 单次最多检查文件数 |
| `MAX_FILE_BYTES` | `2000000` | 超过该大小的文件跳过 |
| `MIN_REFRESH_TOKEN_LENGTH` | `80` | refresh token 最短长度 |
| `RESULTS_FILE` | `results.txt` | 输出路径 |

`results.txt` 已加入 `.gitignore`，不要提交到仓库。

## 覆盖范围

GitHub 代码搜索不是全量数据源，无法扫描 GitHub 上的每一段代码，原因是：

- 只索引默认分支。
- 超大文件或超长代码行可能被排除。
- 每个搜索语句存在结果数量上限。
- 私有仓库需要有权限的 Token。
- 代码必须能被搜索关键词命中，未包含关键词的泄露行不会返回。

当前默认配置会把扫描量提高到最多检查 3000 个匹配文件，但仍然是
“尽可能多扫”，不是 GitHub 全量扫描。

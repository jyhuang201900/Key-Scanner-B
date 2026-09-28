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
每轮结果会通过 Actions Cache 继承上一轮内容，`results.txt` 会持续累加。

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
| `SEARCH_QUERIES` | 内置 14 组权重查询 | 设置后覆盖默认查询计划 |
| `MAX_PAGES` | `10` | 每个搜索语句最多拉取页数 |
| `MAX_FILES_PER_QUERY` | `500` | 每条查询硬上限 |
| `MAX_FILES_PER_SCAN` | `3000` | 单轮最多检查文件数 |
| `MAX_FILE_BYTES` | `2000000` | 超过该大小的文件跳过 |
| `DOWNLOAD_WORKERS` | `16` | 并发下载线程数 |
| `DENSE_FILE_LINES` | `20` | 单文件命中行数达到该值记为高密度 dump |
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

查询计划分三层，依据是 GitHub 搜索 API 的实测行为：

- **A 稀有指纹**：`MsaArtifacts` 全网仅约 142 个文件，结果不会被 1000 条上限截断，
  能 100% 覆盖。
- **B filename 分区**：泄露文件命名可预测（results/accounts/token/email），
  是把裸域名查询切成可枚举小集合的主要手段。
- **C 共现词**：`refreshtoken`、`clientid` 等纯字母数字词，用于收窄裸域名范围。

刻意不使用的内容：`----`（搜索会剥掉符号，退化为空查询）、`@hotmail.com`（符号被剥离，
等价于裸域名）、`size:` 分档（对稀有词只会把搜索空间压到个位数）、
`M.C5` / `BAY.0.U`（剥离后变形且过短）。

扫描器会统计每个文件的命中行数，把命中行数 ≥ `DENSE_FILE_LINES` 的文件标记为
`DUMP HIT`，并把每条查询的产出写进 `scan_stats.json`。

当前配置单轮最多检查 3000 个匹配文件，但仍然是
“尽可能多扫”，不是 GitHub 全量扫描。

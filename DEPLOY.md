# GitHub Actions 部署

## 1. 上传代码

把本项目推到你的 GitHub 仓库。

## 2. Token

工作流使用 GitHub Actions 内置的 `github.token`，不需要添加 Secret。

如果以后需要扫描更多私有资源，再改用具备 `repo` 权限的 PAT。

## 3. 运行

进入：

```text
Actions -> Scan Outlook Leak Lines -> Run workflow
```

工作流会：

1. 搜索 GitHub 代码。
2. 命中 `邮箱----密码----client_id----refresh_token` 后立即写入 `results.txt`。
3. 把 `results.txt` 上传成 Artifact。

Artifact 名称：

```text
outlook-results-<run_number>
```

## 4. 定时运行

`.github/workflows/scan.yml` 默认每 6 小时执行一次：

```yaml
schedule:
  - cron: "0 */6 * * *"
```

## 注意

- 不要把 `results.txt` 提交回仓库。
- Artifact 默认保留 7 天。
- 如果要扩大扫描范围，在仓库 Actions 环境变量中设置 `SEARCH_QUERIES`。

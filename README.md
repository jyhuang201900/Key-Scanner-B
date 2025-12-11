# Gemini Key Scanner

现代化的Gemini API密钥扫描器，支持GitHub搜索和密钥验证。

## 特性

- 🔍 GitHub代码搜索，多维度查询策略
- ✅ 并发密钥验证，支持15线程
- 🎯 智能过滤，去除测试和示例密钥
- 📊 JSON格式存储，便于数据分析
- 🌐 RESTful API，支持远程调用
- 💻 命令行工具，操作简单

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置GitHub Token

```bash
export GITHUB_TOKEN=your_github_token_here
```

### 3. 运行扫描

```bash
# 仅扫描
python cli.py scan

# 仅验证
python cli.py validate

# 扫描+验证
python cli.py both --export-txt
```

### 4. 启动API服务

```bash
python api.py
```

## API端点

- `GET /` - API信息
- `POST /scan` - 执行扫描
- `POST /validate` - 验证密钥
- `GET /keys` - 获取所有密钥
- `GET /valid-keys` - 获取有效密钥
- `GET /stats` - 获取统计信息

## GitHub Actions部署

创建 `.github/workflows/scan.yml`:

```yaml
name: Scan Keys

on:
  schedule:
    - cron: '0 0 * * *'
  workflow_dispatch:

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: python cli.py both --export-txt
        env:
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
      - uses: actions/upload-artifact@v3
        with:
          name: results
          path: output/
```

## 项目结构

```
gemini-key-scanner/
├── config.py       # 配置文件
├── scanner.py      # 核心扫描器
├── validator.py    # 密钥验证器
├── storage.py      # 存储管理
├── api.py          # Flask API
├── cli.py          # 命令行工具
├── requirements.txt
└── output/         # 输出目录
    ├── found_keys.json
    └── valid_keys.json
```

## 配置说明

编辑 `config.py` 自定义:

- `SEARCH_PREFIX`: 密钥前缀 (默认: AIzaSy)
- `MIN_KEY_LENGTH`: 最小长度 (默认: 39)
- `MAX_WORKERS`: 验证线程数 (默认: 15)
- `EXCLUDE_PATTERNS`: 过滤关键词

## 注意事项

- 遵守GitHub API速率限制
- 不要滥用他人密钥
- 定期清理output目录
- 生产环境建议使用环境变量

## License

MIT
"# Key-Scanner-B" 

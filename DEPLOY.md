# GitHub 部署指南

## 方法一：GitHub Actions 自动运行

### 1. 创建GitHub仓库
```bash
cd gemini-key-scanner
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/jyhuang201900/gemini-key-scanner.git
git push -u origin main
```

### 2. 设置GitHub Token Secret
1. 获取GitHub Token
   - 访问 https://github.com/settings/tokens
   - 点击 "Generate new token (classic)"
   - 勾选 `repo` 和 `workflow` 权限
   - 生成并复制token

2. 添加Secret
   - 进入你的仓库
   - Settings → Secrets and variables → Actions
   - 点击 "New repository secret"
   - Name: `GH_TOKEN`
   - Value: 粘贴你的token
   - 点击 "Add secret"

### 3. 启用GitHub Actions
1. 进入仓库的 Actions 标签
2. 点击 "I understand my workflows, go ahead and enable them"
3. 点击 "Scan Gemini Keys" 工作流
4. 点击 "Run workflow" 手动触发

### 4. 查看结果
- Actions 页面查看运行日志
- 完成后在 Artifacts 下载结果文件
- 自动每6小时运行一次

---

## 方法二：Vercel/Railway 部署API

### Vercel部署
```bash
# 安装Vercel CLI
npm i -g vercel

# 登录
vercel login

# 部署
cd gemini-key-scanner
vercel
```

创建 `vercel.json`:
```json
{
  "version": 2,
  "builds": [
    {
      "src": "api.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "api.py"
    }
  ],
  "env": {
    "GITHUB_TOKEN": "@github_token"
  }
}
```

### Railway部署
1. 访问 https://railway.app
2. 连接GitHub仓库
3. 添加环境变量 `GITHUB_TOKEN`
4. 自动部署

---

## 方法三：Render部署

1. 访问 https://render.com
2. New → Web Service
3. 连接GitHub仓库
4. 配置：
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python api.py`
   - Environment Variables: `GITHUB_TOKEN=your_token`
5. Create Web Service

---

## 方法四：Replit部署

1. 访问 https://replit.com
2. Import from GitHub
3. 粘贴仓库URL
4. 在Secrets添加 `GITHUB_TOKEN`
5. 运行 `python api.py`

---

## 使用已部署的API

```bash
# 扫描密钥
curl -X POST https://your-app.vercel.app/scan

# 验证密钥
curl -X POST https://your-app.vercel.app/validate

# 获取有效密钥
curl https://your-app.vercel.app/valid-keys
```

---

## 常见问题

### Q: GitHub Actions 没有运行？
A: 检查 Settings → Actions → General → Workflow permissions
   选择 "Read and write permissions"

### Q: 速率限制？
A: GitHub Token 每小时最多5000次请求，合理设置运行频率

### Q: 如何查看日志？
A: Actions → 点击具体运行 → 查看各步骤日志

### Q: 结果在哪里？
A: Actions → 运行详情 → Artifacts → 下载 scan-results

---

## 推荐配置

- **小规模使用**: GitHub Actions (免费)
- **API服务**: Vercel/Railway (免费额度)
- **高频扫描**: 自建服务器 + 定时任务

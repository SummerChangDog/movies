# 部署指南

## 本地部署

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
复制 `.env.example` 文件为 `.env`：
```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的API密钥：
- `OMDB_API_KEY`: 从 http://www.omdbapi.com/apikey.aspx 获取

### 3. 添加Logo图片
在 `static/images/` 文件夹中添加以下图片：
- douban-logo.png
- imdb-logo.png
- rt-logo.png
- no-poster.jpg

### 4. 运行应用
```bash
python app.py
```

访问 http://localhost:5000 查看网站

## 云端部署

### Heroku部署

1. 创建 `Procfile` 文件：
```
web: gunicorn app:app
```

2. 添加 `gunicorn` 到 requirements.txt

3. 部署到Heroku：
```bash
heroku create your-app-name
heroku config:set OMDB_API_KEY=your-api-key
git push heroku main
```

### Vercel部署

1. 创建 `vercel.json` 文件：
```json
{
  "builds": [
    {
      "src": "app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app.py"
    }
  ]
}
```

2. 使用Vercel CLI部署：
```bash
vercel
```

### Railway部署

1. 连接GitHub仓库到Railway
2. 在Railway中设置环境变量
3. Railway会自动检测并部署Flask应用

## 生产环境注意事项

1. 设置 `DEBUG=False`
2. 使用强密钥替换 `SECRET_KEY`
3. 考虑使用Redis缓存替代文件缓存
4. 配置HTTPS
5. 设置适当的CORS策略

## 性能优化

1. 使用CDN加速静态资源
2. 启用Gzip压缩
3. 优化图片大小
4. 使用生产级WSGI服务器（如Gunicorn）
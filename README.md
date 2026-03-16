# 电影评分聚合网站

一个美观的电影评分聚合网站，支持中英文电影名称搜索，聚合显示豆瓣、IMDb和烂番茄的评分。

## 功能特点

- 🎬 支持中文和英文电影名称搜索
- 📊 聚合显示多个平台的评分：
  - 豆瓣评分
  - IMDb评分
  - 烂番茄评分（专业影评人评分 + 观众评分）
- 🎨 现代化的响应式设计
- 🚀 快速的搜索体验

## 技术栈

- 前端：HTML5 + CSS3 + JavaScript
- 后端：Python (Flask)
- API：豆瓣API、OMDb API（用于IMDb和烂番茄数据）

## 本地开发

1. 克隆仓库
```bash
git clone [仓库地址]
cd movies
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置API密钥
- 在 `config.py` 中配置你的OMDb API密钥

4. 运行应用
```bash
python app.py
```

5. 在浏览器中访问 `http://localhost:5000`

## 部署

本项目可以部署到 Vercel、Netlify 或其他支持 Python 的平台。

## 许可证

MIT License
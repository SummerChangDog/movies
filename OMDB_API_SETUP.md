# OMDb API密钥设置指南

## 问题
当前API密钥无效，导致无法获取电影数据。

## 解决方案

### 方法1：获取免费的OMDb API密钥

1. 访问 [OMDb API官网](http://www.omdbapi.com/apikey.aspx)
2. 选择免费计划（FREE - 1,000 daily limit）
3. 填写邮箱地址
4. 在邮箱中查收API密钥
5. 将密钥更新到 `config.py` 文件中

### 方法2：使用环境变量

创建 `.env` 文件：
```
OMDB_API_KEY=你的新API密钥
```

### 方法3：直接修改config.py

```python
OMDB_API_KEY = os.getenv('OMDB_API_KEY', "你的新API密钥")
```

## 测试API密钥

获取新密钥后，可以通过以下URL测试：
```
http://www.omdbapi.com/?apikey=你的密钥&s=Inception
```

应该返回电影搜索结果，而不是错误信息。

## 临时解决方案

如果暂时无法获取API密钥，可以修改代码使用模拟数据进行测试。
# Vertex AI PDF Reader

这是一个使用 Google Vertex AI 的 Gemini Pro 模型来处理和分析 PDF 文档的 Python 应用程序。

## 功能特点
- PDF 文档读取和文本提取
- 使用 Gemini Pro 模型进行文档分析
- 支持中文和英文文档处理

## 环境要求
- Python 3.8+
- Google Cloud 项目和认证
- Vertex AI API 启用

## 安装步骤
1. 克隆项目到本地
2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置 Google Cloud 认证：
- 设置环境变量 GOOGLE_APPLICATION_CREDENTIALS 指向您的服务账号密钥文件
- 或将服务账号密钥文件重命名为 `credentials.json` 放在项目根目录

## 使用方法
```python
python main.py --pdf_path your_pdf_file.pdf
```

## 注意事项
- 确保您有足够的 Vertex AI API 配额
- PDF 文件大小建议不超过 20MB
- 请妥善保管您的 Google Cloud 认证信息

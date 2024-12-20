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

# PDF Processing API

基于 Vertex AI 的 PDF 文档处理 API 服务，支持 PDF 转图片和文本提取功能。

## 功能特点

- PDF 文件上传和转换
- 异步处理和状态查询
- 基于 Vertex AI 的文本提取
- JSON 格式的结构化输出

## API 接口

### 1. 创建任务

```http
POST /tasks/
```

上传 PDF 文件并创建处理任务。

**请求参数：**
- `file`: PDF 文件（multipart/form-data）

**响应：**
```json
{
    "task_id": "uuid",
    "status": "pending",
    "created_at": "timestamp",
    "updated_at": "timestamp",
    "file_name": "example.pdf",
    "total_pages": null,
    "current_page": null,
    "error": null
}
```

### 2. 查询任务状态

```http
GET /tasks/{task_id}/status
```

查询任务的当前处理状态。

**响应：**
```json
{
    "task_id": "uuid",
    "status": "converting|converted|analyzing|completed|failed",
    "created_at": "timestamp",
    "updated_at": "timestamp",
    "file_name": "example.pdf",
    "total_pages": 10,
    "current_page": 5,
    "error": null
}
```

### 3. 获取任务结果

```http
GET /tasks/{task_id}/result
```

获取已完成任务的处理结果。

**响应：**
```json
{
    "task_id": "uuid",
    "status": "completed",
    "file_name": "example.pdf",
    "total_pages": 10,
    "results": [
        {
            "page_number": 1,
            "content": "页面文本内容",
            "confidence": 0.95
        }
    ],
    "created_at": "timestamp",
    "completed_at": "timestamp",
    "error": null
}
```

## 安装部署

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 安装系统依赖：
```bash
# Debian/Ubuntu
apt-get install -y poppler-utils

# macOS
brew install poppler
```

3. 设置环境变量：
```bash
export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/credentials.json"
```

4. 启动服务：
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## 使用示例

```python
import requests

# 1. 上传 PDF 文件
with open("example.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/tasks/",
        files={"file": f}
    )
task = response.json()
task_id = task["task_id"]

# 2. 查询状态
status = requests.get(f"http://localhost:8000/tasks/{task_id}/status").json()
print(f"处理状态: {status['status']}")

# 3. 获取结果
result = requests.get(f"http://localhost:8000/tasks/{task_id}/result").json()
print(f"处理结果: {result}")

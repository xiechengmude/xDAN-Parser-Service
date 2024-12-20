from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import File, UploadFile, HTTPException, Path
from fastapi.responses import JSONResponse, FileResponse
import asyncio
from pathlib import Path

from .models import TaskResponse, TaskResult, TaskStatus
from .services import PDFProcessingService
from .routes import pdf, pptx

app = FastAPI(title="Document Processing API")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(pdf.router)
app.include_router(pptx.router)

# 初始化服务
pdf_service = PDFProcessingService()

@app.post("/tasks/", response_model=TaskResponse)
async def create_task(file: UploadFile = File(...)):
    """
    创建新的PDF处理任务
    
    - **file**: PDF文件
    
    返回任务ID和初始状态
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # 创建任务
    task = pdf_service.create_task(file.filename)
    
    # 保存文件
    file_path = os.path.join(pdf_service.upload_dir, f"{task.task_id}.pdf")
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # 异步处理PDF
    asyncio.create_task(pdf_service.process_pdf(task.task_id, file_path))
    
    return task

@app.get("/tasks/{task_id}/status", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """
    获取任务状态
    
    - **task_id**: 任务ID
    
    返回任务的当前状态
    """
    task = pdf_service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.get("/tasks/{task_id}/result", response_model=Optional[TaskResult])
async def get_task_result(task_id: str):
    """
    获取任务结果
    
    - **task_id**: 任务ID
    
    返回任务的完整结果（如果已完成）
    """
    result = pdf_service.get_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found or task not completed")
    return result

@app.post("/convert/{task_id}", response_model=TaskResponse)
async def convert_pdf(task_id: str = Path(..., description="任务ID")):
    """
    将任务的 PDF 转换为图片
    
    - **task_id**: 任务ID
    
    返回转换后的状态
    """
    task = pdf_service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    file_path = os.path.join(pdf_service.upload_dir, f"{task_id}.pdf")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    await pdf_service.convert_pdf_to_images(task_id, file_path)
    return pdf_service.get_task_status(task_id)

@app.get("/images/{task_id}/{page}", response_class=FileResponse)
async def get_page_image(task_id: str, page: int):
    """
    获取指定页面的图片
    
    - **task_id**: 任务ID
    - **page**: 页码
    
    返回图片文件
    """
    task = pdf_service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in [TaskStatus.CONVERTED, TaskStatus.ANALYZING, TaskStatus.COMPLETED]:
        raise HTTPException(status_code=400, detail="PDF not yet converted to images")
    
    image_path = os.path.join(pdf_service.output_dir, task_id, 'images', f"page_{page}.png")
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(image_path)

@app.post("/analyze/{task_id}/{page}", response_model=Dict)
async def analyze_page(task_id: str, page: int):
    """
    分析指定页面的内容
    
    - **task_id**: 任务ID
    - **page**: 页码
    
    返回分析结果
    """
    task = pdf_service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in [TaskStatus.CONVERTED, TaskStatus.ANALYZING, TaskStatus.COMPLETED]:
        raise HTTPException(status_code=400, detail="PDF not yet converted to images")
    
    image_path = os.path.join(pdf_service.output_dir, task_id, 'images', f"page_{page}.png")
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    result = await pdf_service.analyze_image(task_id, image_path, page - 1)
    return result

@app.get("/")
async def root():
    return {
        "message": "Welcome to Document Processing API",
        "version": "1.0.0",
        "endpoints": {
            "pdf": "/pdf/...",
            "pptx": "/pptx/..."
        }
    }

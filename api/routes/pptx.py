import os
from fastapi import APIRouter, File, UploadFile, HTTPException, Path
from fastapi.responses import FileResponse
from typing import List

from ..services.pptx_service import PPTXProcessingService
from ..models import TaskResponse, TaskStatus

router = APIRouter(prefix="/pptx", tags=["pptx"])

# 初始化服务
pptx_service = PPTXProcessingService()

@router.post("/tasks/", response_model=TaskResponse)
async def create_task(file: UploadFile = File(...)):
    """
    上传PPT文件并创建转换任务
    
    - **file**: PPT文件
    
    返回任务ID和初始状态
    """
    if not file.filename.lower().endswith(('.ppt', '.pptx')):
        raise HTTPException(status_code=400, detail="Only PPT/PPTX files are allowed")
    
    # 创建任务
    task = pptx_service.create_task(file.filename)
    
    # 保存文件
    file_path = os.path.join(pptx_service.upload_dir, f"{task.task_id}.pptx")
    content = await file.read()
    async with aiofiles.open(file_path, "wb") as buffer:
        await buffer.write(content)
    
    # 异步处理PPT
    asyncio.create_task(pptx_service.convert_pptx_to_images(task.task_id, file_path))
    
    return task

@router.get("/tasks/{task_id}/status", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """
    获取任务状态
    
    - **task_id**: 任务ID
    
    返回任务的当前状态
    """
    task = pptx_service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.get("/tasks/{task_id}/slides/{slide_number}", response_class=FileResponse)
async def get_slide_image(
    task_id: str,
    slide_number: int = Path(..., gt=0, description="幻灯片页码")
):
    """
    获取指定幻灯片的图片
    
    - **task_id**: 任务ID
    - **slide_number**: 幻灯片页码
    
    返回图片文件
    """
    task = pptx_service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in [TaskStatus.COMPLETED]:
        raise HTTPException(status_code=400, detail="Slides not yet converted")
    
    if not task.total_slides or slide_number > task.total_slides:
        raise HTTPException(status_code=404, detail="Slide number out of range")
    
    image_path = os.path.join(
        pptx_service.output_dir,
        task_id,
        'slides',
        f"slide_{slide_number}.png"
    )
    
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(image_path)

@router.get("/tasks/{task_id}/slides", response_model=List[str])
async def list_slides(task_id: str):
    """
    获取任务的所有幻灯片图片路径
    
    - **task_id**: 任务ID
    
    返回所有幻灯片的图片路径
    """
    task = pptx_service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in [TaskStatus.COMPLETED]:
        raise HTTPException(status_code=400, detail="Slides not yet converted")
    
    return pptx_service.tasks[task_id]["image_paths"]

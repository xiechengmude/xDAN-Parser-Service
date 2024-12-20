import os
import asyncio
from typing import List, Optional, Dict
from datetime import datetime
import uuid
from pathlib import Path
import json

from pdf2image import convert_from_path
from vertexai.generative_models import GenerativeModel, Part
import vertexai
from PIL import Image
import io

from .models import TaskStatus, TaskResponse, TaskResult, PageResult
from .prompts import PDFExtractionPrompt, PDFTableExtractionPrompt

class PDFProcessingService:
    def __init__(self, 
                 upload_dir: str = "uploads",
                 output_dir: str = "outputs",
                 project_id: str = "elated-bison-417808",
                 location: str = "us-central1",
                 model_name: str = "gemini-1.5-pro-002"):
        self.upload_dir = upload_dir
        self.output_dir = output_dir
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        self.tasks: Dict[str, Dict] = {}
        
        # 创建必要的目录
        Path(upload_dir).mkdir(parents=True, exist_ok=True)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 初始化 Vertex AI
        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel(model_name)
        
        # 初始化提示词
        self.pdf_prompt = PDFExtractionPrompt()
        self.table_prompt = PDFTableExtractionPrompt()
        
        # self.pdf_prompt = PDFExtractionPrompt()
        # self.table_prompt = PDFTableExtractionPrompt()
        
    def create_task(self, file_name: str) -> TaskResponse:
        """创建新任务"""
        task_id = str(uuid.uuid4())
        now = datetime.now()
        
        task_info = {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "created_at": now,
            "updated_at": now,
            "file_name": file_name,
            "total_pages": None,
            "current_page": None,
            "error": None,
            "results": []
        }
        
        self.tasks[task_id] = task_info
        return TaskResponse(**task_info)

    def get_task_status(self, task_id: str) -> Optional[TaskResponse]:
        """获取任务状态"""
        if task_id not in self.tasks:
            return None
        return TaskResponse(**self.tasks[task_id])

    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """获取任务结果"""
        if task_id not in self.tasks:
            return None
            
        task = self.tasks[task_id]
        if task["status"] != TaskStatus.COMPLETED:
            return None
            
        return TaskResult(
            task_id=task["task_id"],
            status=task["status"],
            file_name=task["file_name"],
            total_pages=task["total_pages"],
            results=[PageResult(**r) for r in task["results"]],
            created_at=task["created_at"],
            completed_at=task["updated_at"],
            error=task["error"]
        )

    async def convert_pdf_to_images(self, task_id: str, file_path: str) -> List[str]:
        """
        将 PDF 转换为图片
        
        Args:
            task_id: 任务ID
            file_path: PDF文件路径
            
        Returns:
            List[str]: 图片文件路径列表
        """
        try:
            self._update_task_status(task_id, TaskStatus.CONVERTING)
            
            # 创建图片保存目录
            image_dir = os.path.join(self.output_dir, task_id, 'images')
            Path(image_dir).mkdir(parents=True, exist_ok=True)
            
            # 转换PDF为图片
            images = convert_from_path(file_path)
            image_paths = []
            
            # 保存图片
            for i, image in enumerate(images):
                image_path = os.path.join(image_dir, f"page_{i+1}.png")
                image.save(image_path, "PNG")
                image_paths.append(image_path)
            
            # 更新任务信息
            self.tasks[task_id]["total_pages"] = len(images)
            self.tasks[task_id]["image_paths"] = image_paths
            self._update_task_status(task_id, TaskStatus.CONVERTED)
            
            return image_paths
            
        except Exception as e:
            self.tasks[task_id]["error"] = str(e)
            self._update_task_status(task_id, TaskStatus.FAILED)
            raise

    async def analyze_image(self, task_id: str, image_path: str, page_num: int) -> Optional[Dict]:
        """
        分析单个图片
        
        Args:
            task_id: 任务ID
            image_path: 图片路径
            page_num: 页码
            
        Returns:
            Dict: 分析结果
        """
        try:
            with Image.open(image_path) as image:
                return await self._process_single_page(task_id, page_num, image)
        except Exception as e:
            self.tasks[task_id]["error"] = str(e)
            raise

    async def process_pdf(self, task_id: str, file_path: str):
        """处理PDF文件"""
        try:
            # 转换PDF为图片
            image_paths = await self.convert_pdf_to_images(task_id, file_path)
            
            # 更新状态为分析中
            self._update_task_status(task_id, TaskStatus.ANALYZING)
            
            # 处理每一页
            results = []
            for i, image_path in enumerate(image_paths):
                self.tasks[task_id]["current_page"] = i + 1
                result = await self.analyze_image(task_id, image_path, i)
                if result:
                    results.append(result)
            
            # 保存结果
            self.tasks[task_id]["results"] = results
            self._update_task_status(task_id, TaskStatus.COMPLETED)
            
        except Exception as e:
            self.tasks[task_id]["error"] = str(e)
            self._update_task_status(task_id, TaskStatus.FAILED)
            raise

    async def _process_single_page(self, task_id: str, page_num: int, image: Image.Image, max_retries: int = 3) -> Optional[Dict]:
        """处理单个页面"""
        for attempt in range(max_retries):
            try:
                # 转换为字节流
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()

                # 获取提示词和配置
                prompt = self.pdf_prompt.get_prompt(
                    page_number=page_num + 1,
                    total_pages=self.tasks[task_id]["total_pages"],
                    language="auto",
                    document_type="general"
                )
                config = self.pdf_prompt.get_generation_config()

                # 调用模型
                response = await self.model.generate_content_async(
                    [prompt, Part.from_data(img_byte_arr, mime_type="image/png")],
                    generation_config=config
                )
                
                return {
                    "page_number": page_num + 1,
                    "content": response.text,
                    "confidence": 0.9  # TODO: 实现实际的置信度计算
                }

            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

    def _update_task_status(self, task_id: str, status: TaskStatus):
        """更新任务状态"""
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["updated_at"] = datetime.now()

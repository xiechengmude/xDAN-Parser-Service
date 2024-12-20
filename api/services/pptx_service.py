import os
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
import uuid
from datetime import datetime
import io
import tempfile
import shutil

from pptx import Presentation
from PIL import Image
import aiofiles

from ..models import TaskStatus, TaskResponse

class PPTXProcessingService:
    """PPT处理服务"""
    
    def __init__(self, 
                 upload_dir: str = "uploads",
                 output_dir: str = "outputs",
                 image_format: str = "png",
                 dpi: int = 300):
        self.upload_dir = upload_dir
        self.output_dir = output_dir
        self.image_format = image_format.lower()
        self.dpi = dpi
        self.tasks: Dict[str, Dict] = {}
        
        # 创建必要的目录
        Path(upload_dir).mkdir(parents=True, exist_ok=True)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 检查 LibreOffice 是否安装
        self._check_libreoffice()
    
    def _check_libreoffice(self):
        """检查 LibreOffice 是否已安装"""
        try:
            import subprocess
            process = subprocess.run(
                ['soffice', '--version'],
                capture_output=True,
                text=True
            )
            if process.returncode != 0:
                raise RuntimeError("LibreOffice not found. Please install it first.")
        except FileNotFoundError:
            raise RuntimeError(
                "LibreOffice not found. Please install it first.\n"
                "On macOS: brew install libreoffice\n"
                "On Ubuntu: sudo apt-get install libreoffice\n"
                "On Windows: Download from https://www.libreoffice.org/"
            )
    
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
            "total_slides": None,
            "current_slide": None,
            "error": None,
            "image_paths": []
        }
        
        self.tasks[task_id] = task_info
        return TaskResponse(**task_info)
    
    def get_task_status(self, task_id: str) -> Optional[TaskResponse]:
        """获取任务状态"""
        if task_id not in self.tasks:
            return None
        return TaskResponse(**self.tasks[task_id])
    
    async def convert_pptx_to_images(self, task_id: str, file_path: str) -> List[str]:
        """
        将PPT转换为图片
        
        Args:
            task_id: 任务ID
            file_path: PPT文件路径
            
        Returns:
            List[str]: 图片文件路径列表
        """
        try:
            self._update_task_status(task_id, TaskStatus.CONVERTING)
            
            # 创建输出目录
            image_dir = os.path.join(self.output_dir, task_id, 'slides')
            Path(image_dir).mkdir(parents=True, exist_ok=True)
            
            # 获取总页数
            prs = Presentation(file_path)
            total_slides = len(prs.slides)
            self.tasks[task_id]["total_slides"] = total_slides
            
            # 使用临时目录进行转换
            with tempfile.TemporaryDirectory() as temp_dir:
                # 复制文件到临时目录
                temp_file = os.path.join(temp_dir, "presentation.pptx")
                shutil.copy2(file_path, temp_file)
                
                # 转换为图片
                await self._convert_to_images(temp_file, image_dir)
                
                # 重命名和整理文件
                image_paths = await self._organize_images(image_dir, total_slides)
                
                # 更新任务信息
                self.tasks[task_id]["image_paths"] = image_paths
                self._update_task_status(task_id, TaskStatus.COMPLETED)
                
                return image_paths
            
        except Exception as e:
            self.tasks[task_id]["error"] = str(e)
            self._update_task_status(task_id, TaskStatus.FAILED)
            raise
    
    async def _convert_to_images(self, input_path: str, output_dir: str):
        """使用 LibreOffice 转换PPT为图片"""
        cmd = [
            'soffice',
            '--headless',
            '--convert-to',
            self.image_format,
            '--outdir',
            output_dir,
            input_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"Conversion failed: {stderr.decode()}")
    
    async def _organize_images(self, image_dir: str, total_slides: int) -> List[str]:
        """整理和重命名转换后的图片"""
        image_paths = []
        
        # 获取所有转换后的图片
        files = sorted(os.listdir(image_dir))
        images = [f for f in files if f.lower().endswith(f'.{self.image_format}')]
        
        if len(images) != total_slides:
            raise RuntimeError(
                f"Expected {total_slides} images, but got {len(images)}"
            )
        
        # 重命名图片
        for i, image in enumerate(images, 1):
            old_path = os.path.join(image_dir, image)
            new_path = os.path.join(image_dir, f"slide_{i}.{self.image_format}")
            
            # 如果需要，调整图片大小和DPI
            await self._process_image(old_path, new_path)
            image_paths.append(new_path)
        
        return image_paths
    
    async def _process_image(self, input_path: str, output_path: str):
        """处理图片（调整大小和DPI）"""
        # 读取图片
        img = Image.open(input_path)
        
        # 设置DPI
        img.info['dpi'] = (self.dpi, self.dpi)
        
        # 保存图片
        await self._save_image(img, output_path)
        
        # 关闭图片
        img.close()
        
        # 如果输出路径与输入路径不同，删除原图片
        if input_path != output_path:
            os.remove(input_path)
    
    async def _save_image(self, image: Image.Image, path: str):
        """异步保存图片"""
        # 转换为字节流
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format=self.image_format.upper(), dpi=(self.dpi, self.dpi))
        img_byte_arr = img_byte_arr.getvalue()
        
        # 异步写入文件
        async with aiofiles.open(path, 'wb') as f:
            await f.write(img_byte_arr)
    
    def _update_task_status(self, task_id: str, status: TaskStatus):
        """更新任务状态"""
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["updated_at"] = datetime.now()

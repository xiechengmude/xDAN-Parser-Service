import os
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict
from pathlib import Path
from api_client import PDFProcessingClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BatchProcessor:
    """批量处理PDF文件"""
    
    def __init__(self, input_dir: str, output_dir: str, max_concurrent: int = 3):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.max_concurrent = max_concurrent
        self.client = PDFProcessingClient()
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        
    async def process_file(self, pdf_path: str) -> Dict:
        """
        处理单个PDF文件
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            Dict: 处理结果
        """
        try:
            # 上传文件
            task = self.client.upload_pdf(pdf_path)
            task_id = task["task_id"]
            
            # 转换为图片
            self.client.convert_pdf(task_id)
            status = self.client.wait_for_status(task_id, ["converted"])
            
            # 创建输出目录
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            task_output_dir = os.path.join(self.output_dir, pdf_name)
            Path(task_output_dir).mkdir(parents=True, exist_ok=True)
            
            # 下载所有图片
            total_pages = status["total_pages"]
            for page in range(1, total_pages + 1):
                image_path = self.client.download_page_image(task_id, page, task_output_dir)
                logging.info(f"保存图片: {image_path}")
            
            # 处理文档
            self.client.process_document(task_id)
            self.client.wait_for_status(task_id, ["completed"])
            
            # 获取结果
            result = self.client.get_result(task_id)
            
            # 保存结果
            result_path = os.path.join(task_output_dir, "result.json")
            with open(result_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logging.info(f"文件处理完成: {pdf_path}")
            return result
            
        except Exception as e:
            logging.error(f"处理文件失败 {pdf_path}: {e}")
            raise
    
    async def process_directory(self):
        """处理目录中的所有PDF文件"""
        # 获取所有PDF文件
        pdf_files = [
            os.path.join(self.input_dir, f)
            for f in os.listdir(self.input_dir)
            if f.lower().endswith('.pdf')
        ]
        
        if not pdf_files:
            logging.warning(f"目录中没有PDF文件: {self.input_dir}")
            return
        
        logging.info(f"找到 {len(pdf_files)} 个PDF文件")
        
        # 创建输出目录
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # 并发处理文件
        tasks = []
        for pdf_file in pdf_files:
            task = asyncio.create_task(self.process_file(pdf_file))
            tasks.append(task)
            
            # 控制并发数
            if len(tasks) >= self.max_concurrent:
                await asyncio.gather(*tasks)
                tasks = []
        
        # 等待剩余任务完成
        if tasks:
            await asyncio.gather(*tasks)
        
        logging.info("所有文件处理完成")

async def main():
    # 设置输入输出目录
    input_dir = "input_pdfs"  # 替换为实际的输入目录
    output_dir = "output"     # 替换为实际的输出目录
    
    # 创建处理器
    processor = BatchProcessor(input_dir, output_dir)
    
    # 开始处理
    await processor.process_directory()

if __name__ == "__main__":
    asyncio.run(main())

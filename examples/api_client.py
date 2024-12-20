import os
import requests
import time
from typing import Optional, Dict, List
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PDFProcessingClient:
    """PDF处理API客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        
    def upload_pdf(self, pdf_path: str) -> Dict:
        """
        上传PDF文件
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            Dict: 包含task_id的响应
        """
        logging.info(f"上传PDF文件: {pdf_path}")
        with open(pdf_path, 'rb') as f:
            response = requests.post(
                f"{self.base_url}/tasks/",
                files={"file": f}
            )
        response.raise_for_status()
        return response.json()
    
    def convert_pdf(self, task_id: str) -> Dict:
        """
        将PDF转换为图片
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 转换状态
        """
        logging.info(f"开始转换PDF: {task_id}")
        response = requests.post(f"{self.base_url}/convert/{task_id}")
        response.raise_for_status()
        return response.json()
    
    def get_status(self, task_id: str) -> Dict:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 任务状态
        """
        response = requests.get(f"{self.base_url}/tasks/{task_id}/status")
        response.raise_for_status()
        return response.json()
    
    def wait_for_status(self, task_id: str, target_status: List[str], check_interval: int = 1) -> Dict:
        """
        等待任务达到指定状态
        
        Args:
            task_id: 任务ID
            target_status: 目标状态列表
            check_interval: 检查间隔（秒）
            
        Returns:
            Dict: 最终状态
        """
        while True:
            status = self.get_status(task_id)
            current_status = status["status"]
            
            if current_status in target_status:
                return status
            
            if current_status == "failed":
                raise Exception(f"任务失败: {status.get('error')}")
            
            logging.info(f"当前状态: {current_status}, 等待中...")
            time.sleep(check_interval)
    
    def download_page_image(self, task_id: str, page: int, output_dir: str) -> str:
        """
        下载指定页面的图片
        
        Args:
            task_id: 任务ID
            page: 页码
            output_dir: 输出目录
            
        Returns:
            str: 保存的图片路径
        """
        logging.info(f"下载第 {page} 页图片")
        response = requests.get(f"{self.base_url}/images/{task_id}/{page}", stream=True)
        response.raise_for_status()
        
        # 创建输出目录
        output_dir = os.path.join(output_dir, task_id)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 保存图片
        image_path = os.path.join(output_dir, f"page_{page}.png")
        with open(image_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return image_path
    
    def analyze_page(self, task_id: str, page: int) -> Dict:
        """
        分析单个页面
        
        Args:
            task_id: 任务ID
            page: 页码
            
        Returns:
            Dict: 分析结果
        """
        logging.info(f"分析第 {page} 页")
        response = requests.post(f"{self.base_url}/analyze/{task_id}/{page}")
        response.raise_for_status()
        return response.json()
    
    def process_document(self, task_id: str) -> Dict:
        """
        处理整个文档
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 处理结果
        """
        logging.info(f"开始处理文档: {task_id}")
        response = requests.post(f"{self.base_url}/tasks/{task_id}/process")
        response.raise_for_status()
        return response.json()
    
    def get_result(self, task_id: str) -> Dict:
        """
        获取处理结果
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 处理结果
        """
        response = requests.get(f"{self.base_url}/tasks/{task_id}/result")
        response.raise_for_status()
        return response.json()


def main():
    # 创建客户端
    client = PDFProcessingClient()
    
    # 上传PDF
    pdf_path = "example.pdf"  # 替换为实际的PDF路径
    task = client.upload_pdf(pdf_path)
    task_id = task["task_id"]
    
    try:
        # 转换为图片
        client.convert_pdf(task_id)
        status = client.wait_for_status(task_id, ["converted"])
        
        # 下载并保存所有页面的图片
        total_pages = status["total_pages"]
        output_dir = "output"
        
        for page in range(1, total_pages + 1):
            image_path = client.download_page_image(task_id, page, output_dir)
            logging.info(f"图片已保存: {image_path}")
            
            # 分析单个页面
            result = client.analyze_page(task_id, page)
            logging.info(f"页面分析结果: {result}")
        
        # 或者处理整个文档
        client.process_document(task_id)
        client.wait_for_status(task_id, ["completed"])
        
        # 获取完整结果
        result = client.get_result(task_id)
        logging.info(f"文档处理完成，结果: {result}")
        
    except Exception as e:
        logging.error(f"处理过程中出错: {e}")
        raise

if __name__ == "__main__":
    main()

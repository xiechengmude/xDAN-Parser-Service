import unittest
import os
import asyncio
import json
from pathlib import Path
from main import async_process_pdf, process_with_pdf2image
import time
from typing import Optional, Dict, List

class TestPDFParsing(unittest.TestCase):
    def setUp(self):
        self.pdf_path = "docs/pdf/ari_vr_2024.pdf"
        self.test_output_dir = "test_output"
        Path(self.test_output_dir).mkdir(exist_ok=True)

    def tearDown(self):
        # 清理测试输出目录（可选）
        pass

    def check_content_quality(self, content: Dict) -> bool:
        """检查内容质量的辅助方法"""
        try:
            # 检查是否包含关键字段
            required_fields = ['page_number', 'content']
            for field in required_fields:
                if field not in content:
                    print(f"缺少必要字段: {field}")
                    return False
            
            # 检查内容是否为空
            if not content['content'] or not content['content'].strip():
                print("内容为空")
                return False
            
            # 检查内容长度是否合理（假设正常页面至少有50个字符）
            if len(content['content']) < 50:
                print(f"内容过短: {len(content['content'])} 字符")
                return False
                
            return True
        except Exception as e:
            print(f"检查内容质量时出错: {str(e)}")
            return False

    def process_with_retry(self, method: str, max_retries: int = 3) -> Optional[List[Dict]]:
        """使用重试机制处理PDF"""
        output_dir = os.path.join(self.test_output_dir, method)
        for attempt in range(max_retries):
            try:
                if method == 'pdf2image':
                    result = process_with_pdf2image(self.pdf_path, output_dir)
                    return result
                else:
                    result = asyncio.run(async_process_pdf(
                        self.pdf_path,
                        output_dir=output_dir,
                        method=method
                    ))
                    return result
            except Exception as e:
                print(f"处理失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                continue
        return None

    def test_pdf2image_processing(self):
        """测试使用pdf2image方法处理PDF"""
        result = self.process_with_retry('pdf2image')
        
        # 基本检查
        self.assertIsNotNone(result, "PDF处理结果不应为空")
        self.assertIsInstance(result, list, "处理结果应该是列表")
        self.assertGreater(len(result), 0, "处理结果不应为空列表")
        
        # 检查每页的内容质量
        for page_content in result:
            self.assertTrue(
                self.check_content_quality(page_content),
                f"页面 {page_content.get('page_number', '未知')} 的内容质量不符合要求"
            )

    def test_vllm_processing(self):
        """测试使用vllm方法处理PDF"""
        result = self.process_with_retry('vllm')
        
        # 基本检查
        self.assertIsNotNone(result, "PDF处理结果不应为空")
        self.assertIsInstance(result, list, "处理结果应该是列表")
        self.assertGreater(len(result), 0, "处理结果不应为空列表")
        
        # 检查每页的内容质量
        for page_content in result:
            self.assertTrue(
                self.check_content_quality(page_content),
                f"页面 {page_content.get('page_number', '未知')} 的内容质量不符合要求"
            )

    def test_compare_methods(self):
        """比较两种处理方法的结果"""
        pdf2image_result = self.process_with_retry('pdf2image')
        vllm_result = self.process_with_retry('vllm')
        
        # 确保两种方法都成功处理了PDF
        self.assertIsNotNone(pdf2image_result, "pdf2image 处理失败")
        self.assertIsNotNone(vllm_result, "vllm 处理失败")
        
        # 比较页数是否一致
        self.assertEqual(
            len(pdf2image_result),
            len(vllm_result),
            "两种方法处理的页数不一致"
        )
        
        # 比较每页的内容
        for pdf2image_page, vllm_page in zip(pdf2image_result, vllm_result):
            # 检查页码是否匹配
            self.assertEqual(
                pdf2image_page['page_number'],
                vllm_page['page_number'],
                "页码不匹配"
            )
            
            # 比较内容长度（允许20%的差异）
            pdf2image_len = len(pdf2image_page['content'])
            vllm_len = len(vllm_page['content'])
            difference_ratio = abs(pdf2image_len - vllm_len) / max(pdf2image_len, vllm_len)
            self.assertLess(
                difference_ratio,
                0.2,
                f"页面 {pdf2image_page['page_number']}: 内容长度差异过大"
            )

if __name__ == '__main__':
    unittest.main()

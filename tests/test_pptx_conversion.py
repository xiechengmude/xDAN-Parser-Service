import os
import sys
import asyncio
import pytest
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from api.services.pptx_service import PPTXProcessingService

@pytest.fixture
def test_dirs():
    """创建测试用的临时目录"""
    # 使用项目目录下的 test_outputs 目录
    upload_dir = os.path.join(project_root, "test_outputs", "uploads")
    output_dir = os.path.join(project_root, "test_outputs", "slides")
    
    # 确保目录存在
    Path(upload_dir).mkdir(parents=True, exist_ok=True)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    return upload_dir, output_dir

@pytest.fixture
def pptx_service(test_dirs):
    """创建 PPT 处理服务实例"""
    upload_dir, output_dir = test_dirs
    return PPTXProcessingService(
        upload_dir=upload_dir,
        output_dir=output_dir,
        dpi=300
    )

@pytest.fixture
def test_pptx():
    """获取测试用的 PPT 文件路径"""
    pptx_path = os.path.join(project_root, "docs", "ppt", "test.pptx")
    if not os.path.exists(pptx_path):
        raise FileNotFoundError(f"测试 PPT 文件不存在: {pptx_path}")
    return pptx_path

async def test_pptx_conversion(pptx_service, test_pptx):
    """测试 PPT 转换功能"""
    try:
        # 1. 创建任务
        task = pptx_service.create_task("test.pptx")
        assert task.status == "PENDING"
        
        # 2. 转换 PPT
        image_paths = await pptx_service.convert_pptx_to_images(
            task.task_id,
            test_pptx
        )
        
        # 3. 检查结果
        assert len(image_paths) > 0, "应该至少生成一张图片"
        
        # 检查所有生成的图片
        for path in image_paths:
            assert os.path.exists(path), f"图片文件不存在: {path}"
            assert os.path.getsize(path) > 0, f"图片文件为空: {path}"
        
        # 4. 检查任务状态
        task = pptx_service.get_task_status(task.task_id)
        assert task.status == "COMPLETED"
        assert task.total_slides == len(image_paths)
        assert not task.error
        
        print(f"\n成功转换 PPT，共生成 {len(image_paths)} 张图片:")
        for i, path in enumerate(image_paths, 1):
            print(f"  第 {i} 页: {path}")
            print(f"  文件大小: {os.path.getsize(path) / 1024:.2f} KB")
        
    except Exception as e:
        print(f"\n转换失败: {str(e)}")
        raise

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_pptx_conversion(
        PPTXProcessingService(
            upload_dir="test_outputs/uploads",
            output_dir="test_outputs/slides"
        ),
        os.path.join(project_root, "docs", "ppt", "test.pptx")
    ))

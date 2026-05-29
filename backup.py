#!/usr/bin/env python3
"""
备份项目和数据 - 打包成一个压缩文件
用法: python backup.py [输出文件名]
"""
import os
import sys
import tarfile
import datetime
import tempfile
import shutil

def main():
    # 项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    # 输出文件名
    if len(sys.argv) > 1:
        output_name = sys.argv[1]
    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"price_monitor_backup_{timestamp}.tar.gz"

    # 确保输出文件名有 .tar.gz 后缀
    if not output_name.endswith('.tar.gz'):
        output_name += '.tar.gz'

    output_path = os.path.abspath(output_name)

    print("="*60)
    print("🛡️  保价追踪系统 - 备份工具")
    print("="*60)
    print(f"项目目录: {project_root}")
    print(f"输出文件: {output_path}")
    print()

    # 要包含的文件和目录
    include_list = [
        'app.py',
        'src/',
        'templates/',
        'configs/',
        'data/',
        'migrations/',
        'requirements.txt',
        'start.sh',
        'README.md',
        'CLAUDE.md',
    ]

    # 检查文件是否存在
    print("检查文件...")
    to_include = []
    for item in include_list:
        if os.path.exists(item):
            to_include.append(item)
            print(f"  ✓ {item}")
        else:
            print(f"  ✗ {item} (不存在，跳过)")

    print()

    if not to_include:
        print("❌ 没有找到任何需要备份的文件")
        sys.exit(1)

    # 创建压缩包
    print("正在创建压缩包...")
    with tarfile.open(output_path, "w:gz", compresslevel=6) as tar:
        for item in to_include:
            arcname = item
            tar.add(item, arcname=arcname)
            print(f"  已添加: {item}")

    print()

    # 显示结果
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print("="*60)
    print(f"✅ 备份完成!")
    print(f"文件: {output_path}")
    print(f"大小: {size_mb:.2f} MB")
    print()
    print("在新机器上恢复运行:")
    print(f"  1. 复制 {output_name} 到新机器")
    print(f"  2. 解压: tar -xzf {output_name}")
    print(f"  3. 进入目录: cd price_monitor")
    print(f"  4. 创建虚拟环境: python3 -m venv venv")
    print(f"  5. 激活虚拟环境: source venv/bin/activate")
    print(f"  6. 安装依赖: pip install -r requirements.txt")
    print(f"  7. 启动服务: ./start.sh")
    print("="*60)


if __name__ == "__main__":
    main()

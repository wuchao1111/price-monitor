#!/usr/bin/env python3
"""
恢复项目和数据 - 从备份文件恢复
用法: python restore.py <备份文件名>
"""
import os
import sys
import tarfile
import tempfile
import shutil

def main():
    if len(sys.argv) < 2:
        print("="*60)
        print("🛡️  保价追踪系统 - 恢复工具")
        print("="*60)
        print("用法: python restore.py <备份文件名.tar.gz>")
        sys.exit(1)

    backup_file = sys.argv[1]

    if not os.path.exists(backup_file):
        print(f"❌ 备份文件不存在: {backup_file}")
        sys.exit(1)

    print("="*60)
    print("🛡️  保价追踪系统 - 恢复工具")
    print("="*60)
    print(f"备份文件: {backup_file}")
    print()

    # 当前目录
    current_dir = os.getcwd()

    # 解压到临时目录，检查内容
    print("检查备份内容...")
    with tempfile.TemporaryDirectory() as tmpdir:
        with tarfile.open(backup_file, "r:gz") as tar:
            tar.extractall(path=tmpdir)

        # 列出内容
        items = sorted(os.listdir(tmpdir))
        print("备份包含:")
        for item in items:
            size = ""
            item_path = os.path.join(tmpdir, item)
            if os.path.isfile(item_path):
                size = f" ({os.path.getsize(item_path)/1024:.1f} KB)"
            print(f"  - {item}{size}")

        print()

        # 询问目标目录
        print("请选择恢复方式:")
        print("  1. 恢复到当前目录 (会覆盖同名文件!)")
        print("  2. 恢复到新目录")
        print("  3. 取消")

        choice = input("\n请输入选项 (1/2/3): ").strip()

        if choice == "3":
            print("已取消")
            return

        target_dir = None
        if choice == "1":
            target_dir = current_dir
        elif choice == "2":
            default_name = "price_monitor"
            dir_name = input(f"请输入目录名 (默认: {default_name}): ").strip()
            if not dir_name:
                dir_name = default_name
            target_dir = os.path.join(current_dir, dir_name)
            os.makedirs(target_dir, exist_ok=True)
        else:
            print("无效选项")
            return

        print()
        print(f"目标目录: {target_dir}")

        confirm = input("确认恢复? (y/n): ").strip().lower()
        if confirm != "y":
            print("已取消")
            return

        # 复制文件
        print()
        print("正在恢复...")
        for item in items:
            src = os.path.join(tmpdir, item)
            dst = os.path.join(target_dir, item)
            if os.path.exists(dst):
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                else:
                    os.remove(dst)
            shutil.move(src, dst)
            print(f"  已恢复: {item}")

    print()
    print("="*60)
    print(f"✅ 恢复完成!")
    print(f"目录: {target_dir}")
    print()
    print("接下来:")
    print(f"  1. cd {target_dir}")
    print(f"  2. 创建虚拟环境: python3 -m venv venv")
    print(f"  3. 激活虚拟环境: source venv/bin/activate")
    print(f"  4. 安装依赖: pip install -r requirements.txt")
    print(f"  5. 启动服务: ./start.sh")
    print("="*60)


if __name__ == "__main__":
    main()

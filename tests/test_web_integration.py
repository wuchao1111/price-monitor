#!/usr/bin/env python3
"""
HTTP 集成测试 - 模拟用户真实操作
"""
import os
import sys
import time
import subprocess
import requests

# 测试配置
BASE_URL = "http://127.0.0.1:9000"
TIMEOUT = 10

def print_step(num, desc):
    print(f"\n{'='*60}\n{num}. {desc}\n{'='*60}")

def check_server():
    """检查服务是否启动"""
    try:
        resp = requests.get(BASE_URL, timeout=2)
        return resp.status_code == 200
    except:
        return False

def test_flow():
    session = requests.Session()

    # 1. 测试首页
    print_step(1, "访问首页")
    resp = session.get(BASE_URL)
    print(f"  状态码: {resp.status_code}")
    assert resp.status_code == 200, "首页访问失败"
    assert "保价" in resp.text or "商品" in resp.text, "内容不正确"

    # 2. 测试新增商品页面
    print_step(2, "访问新增商品页面")
    resp = session.get(f"{BASE_URL}/product/new")
    print(f"  状态码: {resp.status_code}")
    assert resp.status_code == 200

    # 3. 提交新增商品
    print_step(3, "提交新增商品")
    product_name = "测试商品-HTTP测试"
    resp = session.post(f"{BASE_URL}/product/new", data={
        "name": product_name,
        "keywords": "测试",
        "original_price": 3999.0,
        "original_order_no": "HTTP-TEST-001",
        "original_channel": "拼多多",
        "store_activity": "店铺券-50",
        "group_activity": "团长返利-20"
    }, allow_redirects=True)
    print(f"  状态码: {resp.status_code}")
    assert resp.status_code == 200, "添加商品失败"

    # 4. 查找商品ID
    print_step(4, "查找新添加的商品")
    resp = session.get(BASE_URL)
    # 这里简化处理，直接测试详情页，实际可以从首页解析
    # 我们用一个已有的商品ID或者通过搜索找到
    # 先尝试搜索
    resp = session.get(f"{BASE_URL}?q=HTTP")
    print(f"  搜索完成")

    # 5. 先访问首页拿到商品列表（简化版测试）
    print_step(5, "直接测试已有商品的完整流程")
    print("  注意: 如果没有测试商品，请先手动创建一个，或用现有ID")

    # 获取商品ID（从数据库查询）
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    import yaml
    from src.storage.database import Database
    from src.storage.crud import ProductCRUD
    config_path = os.path.join(os.path.dirname(__file__), 'configs', 'config.local.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    db_path = config['database']['path']
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), db_path)
    db = Database(db_path)
    products = ProductCRUD(db).list_all()
    db.close()

    if not products:
        print("  无商品，退出测试")
        return

    test_product = products[0]
    product_id = test_product.id
    print(f"  使用商品: ID={product_id}, name={test_product.name}")

    # 6. 访问商品详情页
    print_step(6, "访问商品详情页")
    resp = session.get(f"{BASE_URL}/product/{product_id}")
    print(f"  状态码: {resp.status_code}")
    assert resp.status_code == 200, "详情页访问失败"

    # 7. 添加保价记录
    print_step(7, "添加保价记录")
    resp = session.post(f"{BASE_URL}/product/{product_id}/guarantee", data={
        "low_price_channel": "淘宝",
        "low_price_order_no": "TB-12345",
        "low_price": 3799.0,
        "note": "HTTP测试保价记录"
    }, allow_redirects=True)
    print(f"  状态码: {resp.status_code}")
    assert resp.status_code == 200, "添加保价记录失败"

    # 8. 获取保价记录ID（从数据库查询）
    from src.storage.crud import PriceGuaranteeCRUD
    db = Database(db_path)
    records = PriceGuaranteeCRUD(db).list_by_product(product_id)
    db.close()
    if not records:
        print("  无保价记录，跳过后续测试")
        return
    record_id = records[0].id
    print(f"  保价记录ID: {record_id}")

    # 9. 测试提交客服
    print_step(8, "点击提交客服 (pending → processing)")
    resp = session.post(f"{BASE_URL}/guarantee/{record_id}/submit", allow_redirects=True)
    print(f"  状态码: {resp.status_code}")
    assert resp.status_code == 200, "提交客服失败"

    # 10. 验证状态变更
    db = Database(db_path)
    record = PriceGuaranteeCRUD(db).get_by_id(record_id)
    db.close()
    print(f"  状态: {record.status}")
    assert record.status == "processing", "状态应该是 processing"

    # 11. 测试确认到账
    print_step(9, "点击确认到账 (processing → confirmed)")
    resp = session.post(f"{BASE_URL}/guarantee/{record_id}/confirm", allow_redirects=True)
    print(f"  状态码: {resp.status_code}")
    assert resp.status_code == 200, "确认到账失败"

    # 12. 验证状态变更
    db = Database(db_path)
    record = PriceGuaranteeCRUD(db).get_by_id(record_id)
    db.close()
    print(f"  状态: {record.status}")
    assert record.status == "confirmed", "状态应该是 confirmed"

    # 13. 测试撤销
    print_step(10, "点击撤销 (confirmed → pending)")
    resp = session.post(f"{BASE_URL}/guarantee/{record_id}/undo", allow_redirects=True)
    print(f"  状态码: {resp.status_code}")
    assert resp.status_code == 200, "撤销失败"

    # 14. 验证最终状态
    db = Database(db_path)
    record = PriceGuaranteeCRUD(db).get_by_id(record_id)
    db.close()
    print(f"  最终状态: {record.status}")
    assert record.status == "pending", "状态应该是 pending"

    print("\n" + "="*60)
    print("✅ 所有集成测试通过！")
    print("="*60)

if __name__ == "__main__":
    print("="*60)
    print("HTTP 集成测试")
    print("="*60)

    if not check_server():
        print("\n❌ 服务未启动！")
        print("请先运行: source venv/bin/activate && python start_fixed.py\n")
        sys.exit(1)

    print("✅ 服务运行正常")

    try:
        test_flow()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)

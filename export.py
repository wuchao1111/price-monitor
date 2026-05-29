#!/usr/bin/env python3
"""
导出数据到 Excel/CSV
用法: python export.py [输出文件名]
默认输出: price_monitor_export.xlsx 或 .csv
"""
import os
import sys
import csv
from datetime import datetime

# 项目根目录
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, 'src'))

import yaml
from src.storage.database import Database

def export_csv(data, filename, headers):
    with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in data:
            writer.writerow(row)
    print(f"✓ 已导出: {filename}")

def main():
    print("="*60)
    print("🛡️  保价追踪系统 - 数据导出工具")
    print("="*60)

    # 加载配置
    config_path = os.path.join(project_root, 'configs', 'config.local.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    db_path = config['database']['path']
    if not os.path.isabs(db_path):
        db_path = os.path.join(project_root, db_path)

    print(f"数据库: {db_path}")
    print()

    # 连接数据库
    db = Database(db_path)

    # 1. 导出商品
    print("导出商品...")
    cursor = db.execute("""
        SELECT id, name, original_price, current_guaranteed_price,
               pending_guarantee_price, original_order_no, original_channel,
               store_activity, group_activity, store_activity_claimed,
               group_activity_claimed, created_at, updated_at
        FROM products ORDER BY created_at DESC
    """)
    products = cursor.fetchall()

    product_rows = []
    for p in products:
        product_rows.append([
            p['id'], p['name'], p['original_price'], p['current_guaranteed_price'],
            p['pending_guarantee_price'], p['original_order_no'], p['original_channel'],
            p['store_activity'], p['group_activity'],
            '是' if p['store_activity_claimed'] else '否',
            '是' if p['group_activity_claimed'] else '否',
            p['created_at'], p['updated_at']
        ])

    product_headers = [
        'ID', '商品名称', '原价', '已保低价', '待保低价',
        '订单号', '购买渠道', '店铺活动', '团购活动',
        '店铺活动已领取', '团购活动已领取', '创建时间', '更新时间'
    ]

    # 2. 导出保价记录
    print("导出保价记录...")
    cursor = db.execute("""
        SELECT r.id, p.name as product_name, r.low_price_channel,
               r.low_price_order_no, r.low_price, r.guarantee_amount,
               r.status, r.note, r.submitted_at, r.confirmed_at
        FROM price_guarantee_records r
        LEFT JOIN products p ON r.product_id = p.id
        ORDER BY r.submitted_at DESC
    """)
    records = cursor.fetchall()

    status_map = {
        'pending': '待提交',
        'processing': '处理中',
        'confirmed': '已到账',
        'rejected': '已拒绝'
    }

    record_rows = []
    for r in records:
        record_rows.append([
            r['id'], r['product_name'], r['low_price_channel'],
            r['low_price_order_no'], r['low_price'], r['guarantee_amount'],
            status_map.get(r['status'], r['status']), r['note'],
            r['submitted_at'], r['confirmed_at']
        ])

    record_headers = [
        'ID', '商品名称', '低价渠道', '低价订单号',
        '发现低价', '保价金额', '状态', '备注',
        '提交时间', '到账时间'
    ]

    # 输出文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if len(sys.argv) > 1:
        base_name = sys.argv[1]
        if base_name.endswith('.xlsx') or base_name.endswith('.csv'):
            base_name = base_name.rsplit('.', 1)[0]
    else:
        base_name = f"price_monitor_export_{timestamp}"

    # 导出 CSV
    product_file = f"{base_name}_products.csv"
    record_file = f"{base_name}_records.csv"

    export_csv(product_rows, product_file, product_headers)
    export_csv(record_rows, record_file, record_headers)

    print()
    print("="*60)
    print(f"✅ 导出完成!")
    print(f"商品数据: {product_file} ({len(product_rows)} 条)")
    print(f"保价记录: {record_file} ({len(record_rows)} 条)")
    print()
    print("直接用 Excel 打开即可!")
    print("="*60)


if __name__ == "__main__":
    main()

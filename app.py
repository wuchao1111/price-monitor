#!/usr/bin/env python3
"""
简化启动脚本 - 带错误处理
"""
import os
import sys
import yaml
import traceback

print("="*50)
print("保价追踪系统启动中...")
print("="*50)

try:
    # Add src to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

    # Import libraries
    print("[1/6] 导入库...")
    import uvicorn
    from jinja2 import Environment, FileSystemLoader
    from fastapi import FastAPI, Form, Request
    from fastapi.responses import HTMLResponse, RedirectResponse

    from src.storage.database import Database
    from src.storage import ProductCRUD, PriceGuaranteeCRUD
    from src.models.schemas import Product, PriceGuaranteeRecord
    print("  库导入成功")

    app = FastAPI(title="Price Guarantee Tracker")
    print("[2/6] FastAPI初始化成功")

    # Load config
    config_path = os.path.join(os.path.dirname(__file__), 'configs', 'config.local.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    db_path = config['database']['path']
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), db_path)
    print(f"[3/6] 数据库: {db_path}")

    # Templates
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    jinja_env = Environment(loader=FileSystemLoader(template_dir))
    print("[4/6] 模板加载成功")

    def get_db():
        return Database(db_path)

    def render_template(name: str, **context):
        template = jinja_env.get_template(name)
        return HTMLResponse(template.render(**context))

    # --- Routes ---

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        q = request.query_params.get("q", "")
        status_filter = request.query_params.get("status", "")
        page_str = request.query_params.get("page", "1")
        try:
            page = int(page_str)
            if page < 1:
                page = 1
        except ValueError:
            page = 1
        page_size = 5

        db = get_db()
        product_crud = ProductCRUD(db)

        total = 0
        if q and q.strip() and status_filter:
            products = product_crud.search_by_status_paginated(q.strip(), status_filter, page, page_size)
            total = product_crud.count_search_by_status(q.strip(), status_filter)
        elif q and q.strip():
            products = product_crud.search_paginated(q.strip(), page, page_size)
            total = product_crud.count_search(q.strip())
        elif status_filter:
            products = product_crud.list_by_status_paginated(status_filter, page, page_size)
            total = product_crud.count_by_status(status_filter)
        else:
            products = product_crud.list_all_paginated(page, page_size)
            total = product_crud.count_all()

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        product_dicts = [p.model_dump() for p in products]
        return render_template("index.html",
            products=product_dicts,
            search_query=q or "",
            status_filter=status_filter or "",
            current_page=page,
            total_pages=total_pages,
            total=total,
            title="保价商品列表"
        )

    @app.get("/product/new", response_class=HTMLResponse)
    async def new_product_form():
        return render_template("product_form.html",
            product=None,
            action="/product/new",
            title="新增保价商品"
        )

    @app.get("/product/{product_id}/edit", response_class=HTMLResponse)
    async def edit_product_form(product_id: int):
        db = get_db()
        product = ProductCRUD(db).get_by_id(product_id)
        if not product:
            return RedirectResponse(url="/", status_code=303)
        product_dict = product.model_dump()
        return render_template("product_form.html",
            product=product_dict,
            action=f"/product/{product_id}/edit",
            title=f"编辑商品 - {product.name}"
        )

    @app.get("/product/{product_id}", response_class=HTMLResponse)
    async def product_detail(product_id: int):
        db = get_db()
        product_crud = ProductCRUD(db)
        guarantee_crud = PriceGuaranteeCRUD(db)
        product = product_crud.get_by_id(product_id)
        if not product:
            return RedirectResponse(url="/", status_code=303)
        guarantee_records = guarantee_crud.list_by_product(product_id)

        total_guaranteed = 0.0
        total_pending = 0.0
        for record in guarantee_records:
            if product.original_price and record.low_price:
                diff = product.original_price - record.low_price
                if record.status == "confirmed":
                    total_guaranteed += diff
                elif record.status == "pending":
                    total_pending += diff

        product_dict = product.model_dump()
        record_dicts = [r.model_dump() for r in guarantee_records]
        return render_template("product.html",
            product=product_dict,
            guarantee_records=record_dicts,
            price_history=[],
            change_logs=[],
            total_guaranteed=total_guaranteed,
            total_pending=total_pending,
            title=f"商品详情 - {product.name}"
        )

    @app.post("/product/new")
    async def create_product(name: str = Form(...), keywords: str = Form(""), welfare_policy: str = Form(""),
                             original_price: float = Form(None), original_order_no: str = Form(""),
                             original_channel: str = Form(""), store_activity: str = Form(""),
                             group_activity: str = Form("")):
        db = get_db()
        product = Product(name=name, keywords=keywords, welfare_policy=welfare_policy,
                         original_price=original_price, original_order_no=original_order_no,
                         original_channel=original_channel, store_activity=store_activity,
                         group_activity=group_activity, current_lowest_price=original_price)
        ProductCRUD(db).create(product)
        return RedirectResponse(url="/", status_code=303)

    @app.post("/product/{product_id}/edit")
    async def update_product(product_id: int, name: str = Form(...), keywords: str = Form(""),
                            welfare_policy: str = Form(""), original_price: float = Form(None),
                            original_order_no: str = Form(""), original_channel: str = Form(""),
                            store_activity: str = Form(""), group_activity: str = Form("")):
        db = get_db()
        product_crud = ProductCRUD(db)
        product = product_crud.get_by_id(product_id)
        if product:
            product.name = name
            product.keywords = keywords
            product.welfare_policy = welfare_policy
            product.original_price = original_price
            product.original_order_no = original_order_no
            product.original_channel = original_channel
            product.store_activity = store_activity
            product.group_activity = group_activity
            product_crud.update(product)
        return RedirectResponse(url="/", status_code=303)

    @app.post("/product/{product_id}/guarantee")
    async def add_guarantee(product_id: int, low_price_channel: str = Form(...),
                            low_price_order_no: str = Form(""), low_price: float = Form(...), note: str = Form("")):
        db = get_db()
        product_crud = ProductCRUD(db)
        guarantee_crud = PriceGuaranteeCRUD(db)
        product = product_crud.get_by_id(product_id)
        if not product:
            return RedirectResponse(url="/", status_code=303)

        guarantee_amount = 0.0
        if product.original_price and product.original_price > low_price:
            guarantee_amount = product.original_price - low_price

        record = PriceGuaranteeRecord(product_id=product_id, low_price_channel=low_price_channel,
                                     low_price_order_no=low_price_order_no, low_price=low_price,
                                     guarantee_amount=guarantee_amount, note=note)
        guarantee_crud.create(record)

        new_pending = product.pending_guarantee_price
        if new_pending is None or low_price < new_pending:
            new_pending = low_price
        product_crud.update_price_guarantee(product_id, pending_guarantee_price=new_pending)
        return RedirectResponse(url=f"/product/{product_id}", status_code=303)

    @app.post("/guarantee/{record_id}/confirm")
    async def confirm_guarantee(record_id: int):
        db = get_db()
        guarantee_crud = PriceGuaranteeCRUD(db)
        product_crud = ProductCRUD(db)
        record = guarantee_crud.get_by_id(record_id)
        if record:
            guarantee_crud.update_status(record_id, "confirmed")
            product = product_crud.get_by_id(record.product_id)
            if product:
                new_guaranteed = product.current_guaranteed_price
                if new_guaranteed is None or record.low_price < new_guaranteed:
                    new_guaranteed = record.low_price
                product_crud.update_price_guarantee(record.product_id,
                    current_guaranteed_price=new_guaranteed,
                    pending_guarantee_price=product.pending_guarantee_price)
        return RedirectResponse(url=f"/product/{record.product_id}", status_code=303)

    @app.post("/guarantee/{record_id}/submit")
    async def submit_guarantee(record_id: int):
        db = get_db()
        guarantee_crud = PriceGuaranteeCRUD(db)
        record = guarantee_crud.get_by_id(record_id)
        if record:
            guarantee_crud.update_status(record_id, "processing")
        return RedirectResponse(url=f"/product/{record.product_id}", status_code=303)

    @app.post("/guarantee/{record_id}/reject")
    async def reject_guarantee(record_id: int):
        db = get_db()
        guarantee_crud = PriceGuaranteeCRUD(db)
        record = guarantee_crud.get_by_id(record_id)
        if record:
            guarantee_crud.update_status(record_id, "rejected")
        return RedirectResponse(url=f"/product/{record.product_id}", status_code=303)

    @app.post("/guarantee/{record_id}/undo")
    async def undo_guarantee(record_id: int):
        db = get_db()
        guarantee_crud = PriceGuaranteeCRUD(db)
        product_crud = ProductCRUD(db)
        record = guarantee_crud.get_by_id(record_id)
        if record:
            guarantee_crud.update_status(record_id, "pending")
            product_crud.recalculate_guaranteed_price(record.product_id)
        return RedirectResponse(url=f"/product/{record.product_id}", status_code=303)

    @app.post("/product/{product_id}/activity")
    async def toggle_activity_claimed(product_id: int, type: str = Form(...)):
        db = get_db()
        product_crud = ProductCRUD(db)
        product = product_crud.get_by_id(product_id)
        if product:
            if type == "store":
                product_crud.update_activity_claimed(product_id, store_activity_claimed=True)
            elif type == "group":
                product_crud.update_activity_claimed(product_id, group_activity_claimed=True)
        return RedirectResponse(url=f"/product/{product_id}", status_code=303)

    @app.post("/product/{product_id}/delete")
    async def delete_product(product_id: int):
        db = get_db()
        ProductCRUD(db).delete(product_id)
        return RedirectResponse(url="/", status_code=303)

    print("[5/6] 路由注册成功")
    print("\n" + "="*50)
    print("🚀 启动成功！")
    print("📱 本地访问: http://127.0.0.1:9000")
    print("🌐 内网访问: http://<你的电脑IP>:9000")
    print("="*50 + "\n")
    # 监听所有网卡，允许内网访问
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "9000"))
    uvicorn.run(app, host=host, port=port)

except Exception as e:
    print("\n❌ 启动失败！")
    print("="*50)
    print(f"错误: {type(e).__name__}: {e}")
    print("\n详细堆栈:")
    print(traceback.format_exc())
    print("="*50)
    sys.exit(1)

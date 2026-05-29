"""
CLI - Command Line Interface
Interactive command line for user interaction
"""
import asyncio
import logging
import os
import sys
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from src.agent.core import PriceMonitorAgent
from src.storage.database import Database
from src.storage import ProductCRUD, PriceHistoryCRUD, ChangeLogCRUD
from src.skills.manager import SkillManager
from src.modules.notification import NotificationManager, TerminalNotification, WeComNotification, DingTalkNotification
from src.modules.comparator import PriceComparator

console = Console()


def setup_notification_manager(config: dict) -> NotificationManager:
    """Setup notification manager from config"""
    manager = NotificationManager()

    # Terminal notification is always enabled for CLI
    manager.add_channel(TerminalNotification(enabled=True))

    # WeCom
    wecom_config = config['notification']['wecom']
    if wecom_config['enabled'] and wecom_config['webhook_url']:
        manager.add_channel(WeComNotification(
            webhook_url=wecom_config['webhook_url'],
            enabled=True
        ))

    # DingTalk
    dingtalk_config = config['notification']['dingtalk']
    if dingtalk_config['enabled'] and dingtalk_config['webhook_url']:
        manager.add_channel(DingTalkNotification(
            webhook_url=dingtalk_config['webhook_url'],
            enabled=True
        ))

    return manager


def init_agent(config_path: str) -> PriceMonitorAgent:
    """Initialize the agent with all dependencies"""
    import yaml
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    db_path = config['database']['path']
    db = Database(db_path)

    # Initialize database if not exists
    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'migrations',
        '001_initial.sql'
    )
    if not os.path.exists(db_path):
        db.init_schema(migration_path)
        console.print(f"[green]✓[/green] Database initialized at {db_path}")

    product_crud = ProductCRUD(db)
    price_history_crud = PriceHistoryCRUD(db)
    change_log_crud = ChangeLogCRUD(db)

    skill_manager = SkillManager()

    # Import and register skills
    from src.skills import register_all_skills
    register_all_skills(skill_manager, config)

    comparator = PriceComparator(product_crud, price_history_crud)

    notification_manager = setup_notification_manager(config)

    agent = PriceMonitorAgent(
        config_path,
        product_crud,
        price_history_crud,
        change_log_crud,
        skill_manager,
        comparator,
        notification_manager,
    )

    return agent


@click.group()
@click.option('--config', '-c', default='./configs/config.local.yaml', help='Path to config file')
@click.pass_context
def cli(ctx, config):
    """Price Monitor AI Agent CLI"""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config


@cli.command(name='interactive')
@click.pass_context
def interactive(ctx):
    """Start interactive CLI mode"""
    config_path = ctx.obj['config_path']
    agent = init_agent(config_path)

    console.print("\n[bold blue]🤖 Price Monitor AI Agent - Interactive Mode[/bold blue]")
    console.print("Type 'exit' or 'quit' to exit\n")

    try:
        while True:
            user_input = console.input("[bold green]you>[/bold green] ")
            user_input = user_input.strip()
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit', 'q']:
                console.print("[blue]Goodbye![/blue]")
                break

            with console.status("[bold yellow]Thinking...[/bold yellow]"):
                response = asyncio.run(agent.chat(user_input))

            console.print(f"[bold purple]agent>[/bold purple] {response}\n")

    except KeyboardInterrupt:
        console.print("\n[blue]Goodbye![/blue]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logging.exception("Interactive mode error")


@cli.command(name='add')
@click.argument('name')
@click.argument('keywords')
@click.option('--welfare', '-w', help='Welfare policy description')
@click.option('--price', '-p', type=float, help='Initial lowest price')
@click.pass_context
def add_product(ctx, name, keywords, welfare, price):
    """Add a new product to monitor"""
    config_path = ctx.obj['config_path']
    agent = init_agent(config_path)
    prompt = f"Add a new product with name '{name}', keywords '{keywords}'"
    if welfare:
        prompt += f", welfare policy '{welfare}'"
    if price:
        prompt += f", initial price {price}"

    response = asyncio.run(agent.chat(prompt))
    console.print(response)


@cli.command(name='list')
@click.pass_context
def list_products(ctx):
    """List all monitored products"""
    config_path = ctx.obj['config_path']
    agent = init_agent(config_path)
    response = asyncio.run(agent.chat("List all monitored products"))

    # Try to extract product data and display as table
    try:
        result = asyncio.run(agent._tool_list_products())
        products = result.get('products', [])
        if products:
            table = Table(title="Monitored Products")
            table.add_column("ID", justify="right", style="cyan")
            table.add_column("Name", style="white")
            table.add_column("Keywords", style="dim")
            table.add_column("Lowest Price", justify="right", style="green")
            table.add_column("Welfare Policy", style="yellow")

            for p in products:
                price_str = f"{p['current_lowest_price']:.2f}" if p.get('current_lowest_price') else "None"
                welfare = p.get('welfare_policy') or ""
                if welfare and len(welfare) > 30:
                    welfare = welfare[:27] + "..."
                table.add_row(
                    str(p['id']),
                    p['name'],
                    p['keywords'],
                    price_str,
                    welfare
                )
            console.print(table)
        else:
            console.print("[yellow]No products found[/yellow]")
    except Exception:
        # Fall back to text response
        console.print(response)


@cli.command(name='check')
@click.argument('product_id', type=int)
@click.pass_context
def check_product(ctx, product_id):
    """Manually check price for a product"""
    config_path = ctx.obj['config_path']
    agent = init_agent(config_path)
    with console.status(f"[bold yellow]Checking price for product {product_id}...[/bold yellow]"):
        response = asyncio.run(agent.chat(f"Check product {product_id}"))
    console.print(response)


@cli.command(name='confirm')
@click.argument('product_id', type=int)
@click.argument('new_price', type=float)
@click.pass_context
def confirm_update(ctx, product_id, new_price):
    """Confirm price update for a product"""
    config_path = ctx.obj['config_path']
    agent = init_agent(config_path)
    response = asyncio.run(agent.chat(f"Confirm update for product {product_id} with new price {new_price}"))
    console.print(response)


@cli.command(name='history')
@click.argument('product_id', type=int)
@click.option('--limit', '-l', type=int, default=20, help='Number of entries to show')
@click.pass_context
def price_history(ctx, product_id, limit):
    """Show price history for a product"""
    config_path = ctx.obj['config_path']
    agent = init_agent(config_path)

    try:
        result = asyncio.run(agent._tool_get_price_history(product_id, limit))
        if result['success'] and result.get('history'):
            table = Table(title=f"Price History - Product {product_id}")
            table.add_column("ID", justify="right", style="cyan")
            table.add_column("Price", justify="right", style="green")
            table.add_column("Source", style="blue")
            table.add_column("Queried At", style="dim")

            for entry in reversed(result['history']):
                ts = entry.get('queried_at', '')
                if ts:
                    ts = str(ts).split('.')[0]
                table.add_row(
                    str(entry['id']),
                    f"{entry['price']:.2f}",
                    entry['source'],
                    ts
                )
            console.print(table)
        else:
            console.print("[yellow]No price history found[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command(name='changelog')
@click.argument('product_id', type=int)
@click.option('--limit', '-l', type=int, default=20, help='Number of entries to show')
@click.pass_context
def change_log(ctx, product_id, limit):
    """Show change log for a product"""
    config_path = ctx.obj['config_path']
    agent = init_agent(config_path)

    from src.storage import ChangeLogCRUD
    config_path = ctx.obj['config_path']
    import yaml
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    db = Database(config['database']['path'])
    db.connect()
    crud = ChangeLogCRUD(db)
    logs = crud.list_by_product(product_id, limit)

    if logs:
        table = Table(title=f"Change Log - Product {product_id}")
        table.add_column("ID", justify="right", style="cyan")
        table.add_column("Old Price", justify="right", style="red")
        table.add_column("New Price", justify="right", style="green")
        table.add_column("Changed By", style="blue")
        table.add_column("Changed At", style="dim")
        table.add_column("Note", style="yellow")

        for entry in logs:
            old = f"{entry.old_price:.2f}" if entry.old_price else "None"
            note = entry.note or ""
            if note and len(note) > 20:
                note = note[:17] + "..."
            ts = str(entry.changed_at).split('.')[0] if entry.changed_at else ""
            table.add_row(
                str(entry.id),
                old,
                f"{entry.new_price:.2f}",
                entry.changed_by,
                ts,
                note
            )
        console.print(table)
    else:
        console.print("[yellow]No change log found[/yellow]")


@cli.command(name='delete')
@click.argument('product_id', type=int)
@click.pass_context
def delete_product(ctx, product_id):
    """Delete a monitored product"""
    config_path = ctx.obj['config_path']
    agent = init_agent(config_path)
    response = asyncio.run(agent.chat(f"Delete product {product_id}"))
    console.print(response)


if __name__ == '__main__':
    cli()

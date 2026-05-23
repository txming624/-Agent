"""
运维排障Agent - 主入口
支持CLI交互和直接API调用
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

from .config import load_config, AppConfig
from .orchestrator import Orchestrator, DiagnosisResult


def print_banner():
    """打印启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                   运维排障 Agent v1.0                        ║
║                                                              ║
║   日志分析 → 根因定位 → 自动修复建议                           ║
║                                                              ║
║   支持: 本地日志文件 | Elasticsearch | RAG知识库               ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def interactive_mode(orchestrator: Orchestrator):
    """交互模式"""
    print("\n📌 交互模式 - 输入 'help' 查看命令\n")

    while True:
        try:
            cmd = input("ops-agent> ").strip()

            if not cmd:
                continue

            if cmd == "quit" or cmd == "exit":
                print("👋 再见!")
                break

            elif cmd == "help":
                print_help()

            elif cmd == "status":
                show_status(orchestrator)

            elif cmd.startswith("analyze"):
                handle_analyze(orchestrator, cmd)

            elif cmd.startswith("search"):
                handle_search(orchestrator, cmd)

            elif cmd == "demo":
                run_demo(orchestrator)

            else:
                print(f"❌ 未知命令: {cmd}，输入 'help' 查看可用命令")

        except KeyboardInterrupt:
            print("\n👋 再见!")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")


def print_help():
    """打印帮助信息"""
    help_text = """
可用命令:
  analyze local [--hours N] [--keywords kw1,kw2]  - 分析本地日志
  analyze es [--hours N] [--keywords kw1,kw2]     - 分析ES日志
  search <关键词>                                   - 搜索故障库
  status                                           - 查看系统状态
  demo                                             - 运行演示
  help                                             - 显示帮助
  quit/exit                                        - 退出
    """
    print(help_text)


def show_status(orchestrator: Orchestrator):
    """显示系统状态"""
    config = orchestrator.config

    print("\n📊 系统状态:")
    print(f"  LLM模型: {config.llm.model}")
    print(f"  LLM接口: {config.llm.base_url}")
    print(f"  日志目录: {config.log_dir}")
    print(f"  向量数据库: {config.rag.vector_db_path}")

    try:
        stats = orchestrator.knowledge_base.get_stats()
        print(f"  知识库文档数: {stats.get('total_documents', 0)}")
    except Exception:
        print(f"  知识库状态: 未初始化")

    print()


def handle_analyze(orchestrator: Orchestrator, cmd: str):
    """处理分析命令"""
    parts = cmd.split()
    if len(parts) < 2:
        print("❌ 用法: analyze <local|es> [--hours N] [--keywords kw1,kw2]")
        return

    source_type = parts[1]

    # 解析参数
    hours = 24
    keywords = None

    i = 2
    while i < len(parts):
        if parts[i] == "--hours" and i + 1 < len(parts):
            hours = int(parts[i + 1])
            i += 2
        elif parts[i] == "--keywords" and i + 1 < len(parts):
            keywords = parts[i + 1].split(",")
            i += 2
        else:
            i += 1

    print(f"\n🔍 开始分析 (数据源: {source_type}, 时间范围: {hours}小时)")

    result = orchestrator.diagnose(
        source_type=source_type,
        hours=hours,
        keywords=keywords
    )

    print_report(result)


def handle_search(orchestrator: Orchestrator, cmd: str):
    """处理搜索命令"""
    parts = cmd.split(maxsplit=1)
    if len(parts) < 2:
        print("❌ 用法: search <关键词>")
        return

    query = parts[1]
    print(f"\n🔍 搜索: {query}")

    try:
        results = orchestrator.knowledge_base.search(query, top_k=3)
        if results:
            print(f"\n找到 {len(results)} 条相关案例:\n")
            for i, r in enumerate(results, 1):
                print(f"--- 案例{i} (相似度: {r.get('score', 0):.2f}) ---")
                print(r.get("content", "")[:500])
                print()
        else:
            print("未找到相关案例")
    except Exception as e:
        print(f"❌ 搜索失败: {e}")


def run_demo(orchestrator: Orchestrator):
    """运行演示"""
    print("\n🎯 运行演示模式...")

    from ..collectors.log_collector import LogEntry
    from datetime import datetime, timedelta

    # 模拟日志数据
    demo_logs = [
        LogEntry(
            timestamp=datetime.now() - timedelta(minutes=30),
            level="ERROR",
            source="app-server",
            message="Connection pool exhausted: Cannot get a connection, pool error Timeout waiting for idle object",
        ),
        LogEntry(
            timestamp=datetime.now() - timedelta(minutes=29),
            level="ERROR",
            source="app-server",
            message="Failed to execute database query: java.sql.SQLException: Cannot get a connection",
        ),
        LogEntry(
            timestamp=datetime.now() - timedelta(minutes=28),
            level="WARN",
            source="app-server",
            message="High response time detected: average 5000ms in last 1 minute",
        ),
        LogEntry(
            timestamp=datetime.now() - timedelta(minutes=27),
            level="ERROR",
            source="app-server",
            message="HTTP 500 error for /api/orders: Internal Server Error",
        ),
        LogEntry(
            timestamp=datetime.now() - timedelta(minutes=26),
            level="CRITICAL",
            source="monitoring",
            message="Service health check failed: app-server is not responding",
        ),
    ]

    result = orchestrator.diagnose_from_logs(demo_logs, context="电商订单服务出现故障")
    print_report(result)


def print_report(result: DiagnosisResult):
    """打印诊断报告"""
    print("\n" + "=" * 60)
    print(result.generate_report(format="markdown"))
    print("=" * 60)


def save_report(result: DiagnosisResult, output_path: str):
    """保存报告到文件"""
    report = result.generate_report(format="markdown")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ 报告已保存到: {output_path}")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="运维排障Agent - 自动化故障诊断",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m ops_agent                                    # 交互模式
  python -m ops_agent --source local --hours 24          # 分析本地日志
  python -m ops_agent --source es --hours 6              # 分析ES日志
  python -m ops_agent --demo                             # 演示模式
  python -m ops_agent --source local --output report.md  # 分析并保存报告
        """
    )

    parser.add_argument("--source", choices=["local", "es", "elasticsearch"], help="日志数据源")
    parser.add_argument("--hours", type=int, default=24, help="分析最近N小时的日志 (默认: 24)")
    parser.add_argument("--keywords", help="关键词过滤，逗号分隔")
    parser.add_argument("--levels", help="日志级别过滤，逗号分隔 (如: ERROR,WARN)")
    parser.add_argument("--pattern", default="*.log", help="日志文件匹配模式 (默认: *.log)")
    parser.add_argument("--output", help="报告输出文件路径")
    parser.add_argument("--demo", action="store_true", help="运行演示模式")
    parser.add_argument("--no-interactive", action="store_true", help="不进入交互模式")
    parser.add_argument("--init-kb", help="初始化知识库 (指定故障库JSON文件路径)")

    args = parser.parse_args()

    # 加载配置
    config = load_config()

    # 创建编排器
    orchestrator = Orchestrator(config)

    # 初始化知识库
    if args.init_kb:
        orchestrator.init_knowledge_base(args.init_kb)

    # 演示模式
    if args.demo:
        print_banner()
        run_demo(orchestrator)
        return

    # 命令行分析模式
    if args.source:
        print_banner()
        keywords = args.keywords.split(",") if args.keywords else None
        levels = args.levels.split(",") if args.levels else None

        result = orchestrator.diagnose(
            source_type=args.source,
            file_pattern=args.pattern,
            hours=args.hours,
            keywords=keywords,
            levels=levels,
        )

        if args.output:
            save_report(result, args.output)
        else:
            print_report(result)
        return

    # 交互模式
    if not args.no_interactive:
        print_banner()
        interactive_mode(orchestrator)


if __name__ == "__main__":
    main()

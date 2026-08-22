"""Command-line entry point for the acceptance MVP."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from auditor.pipeline import AuditPipeline
from auditor.providers import (
    DemoMockProvider,
    OpenAICompatibleProvider,
    ProviderError,
)
from auditor.render import JSONReportRenderer, MarkdownReportRenderer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auditor", description="AI 观点审计器")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit", help="审计一段观点并生成 Markdown 报告")
    audit.add_argument("text", nargs="?", help="待审计观点")
    audit.add_argument("--file", type=Path, help="从 Markdown 或文本文件读取观点")
    audit.add_argument(
        "--provider",
        choices=["mock", "openai-compatible", "openai"],
        default="mock",
        help="Provider（默认 mock；openai/openai-compatible 使用环境变量配置）",
    )
    audit.add_argument("--base-url", help="OpenAI-Compatible API 根地址")
    audit.add_argument("--model", help="模型名称，默认读取 OPENAI_MODEL")
    audit.add_argument("--timeout", type=float, default=60.0, help="请求超时秒数")
    audit.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="报告格式",
    )
    audit.add_argument(
        "--compress-only",
        action="store_true",
        help="只输出压缩后的观点",
    )
    audit.add_argument("--output", type=Path, help="将 Markdown 报告写入文件")
    return parser


def _read_text(args: argparse.Namespace) -> str:
    if args.file and args.text:
        raise ValueError("text and --file cannot be used together")
    if args.file:
        try:
            return args.file.read_text(encoding="utf-8")
        except OSError as error:
            raise ValueError(f"cannot read input file: {args.file}") from error
    if args.text:
        return args.text
    if not sys.stdin.isatty():
        stdin_text = sys.stdin.read()
        if stdin_text.strip():
            return stdin_text
    if sys.stdin.isatty():
        prompted = input("请输入要审计的观点：\n> ")
        if prompted.strip():
            return prompted
    raise ValueError("provide a viewpoint as text or with --file")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "audit":
        parser.error("unsupported command")

    try:
        text = _read_text(args)
        provider = (
            DemoMockProvider()
            if args.provider == "mock"
            else OpenAICompatibleProvider(
                base_url=args.base_url,
                model=args.model,
                timeout=args.timeout,
            )
        )
        try:
            report = AuditPipeline(provider).run(
                text, include_alternatives=not args.compress_only
            )
        finally:
            close = getattr(provider, "close", None)
            if close is not None:
                close()
        if args.compress_only:
            output = report.graph.compressed_view + "\n"
        elif args.format == "json":
            output = JSONReportRenderer().render(report)
        else:
            output = MarkdownReportRenderer().render(report)
        if args.output:
            try:
                args.output.write_text(output, encoding="utf-8")
            except OSError as error:
                raise ValueError(f"cannot write output file: {args.output}") from error
            print(f"报告已写入：{args.output}", file=sys.stderr)
        else:
            sys.stdout.write(output)
    except (ValueError, ProviderError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

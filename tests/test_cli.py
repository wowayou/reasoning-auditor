from pathlib import Path
import json

from auditor.cli import main


def test_cli_prints_compressed_view(capsys) -> None:
    exit_code = main(["audit", "观点", "--compress-only"])

    assert exit_code == 0
    assert capsys.readouterr().out == "观点\n"


def test_cli_reads_file_and_writes_markdown(tmp_path: Path) -> None:
    source = tmp_path / "input.md"
    output = tmp_path / "report.md"
    source.write_text("文件中的观点", encoding="utf-8")

    assert main(["audit", "--file", str(source), "--output", str(output)]) == 0
    markdown = output.read_text(encoding="utf-8")
    assert markdown.startswith("# AI观点审计报告")
    assert "文件中的观点" in markdown


def test_cli_prints_json_report(capsys) -> None:
    assert main(["audit", "观点", "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["graph"]["original_text"] == "观点"
    assert payload["rhetoric"]["risk"] == "LOW"


def test_cli_can_read_piped_stdin(monkeypatch, capsys) -> None:
    class NonInteractiveStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return "管道输入观点"

    monkeypatch.setattr("sys.stdin", NonInteractiveStdin())

    assert main(["audit", "--compress-only"]) == 0
    assert capsys.readouterr().out == "管道输入观点\n"


def test_cli_prompts_when_run_without_input(monkeypatch, capsys) -> None:
    class InteractiveStdin:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr("sys.stdin", InteractiveStdin())
    monkeypatch.setattr("builtins.input", lambda _: "交互输入观点")

    assert main(["audit", "--compress-only"]) == 0
    assert capsys.readouterr().out == "交互输入观点\n"

import json
import runpy
import types

import pytest

import evalforge.__main__ as cli
from evalforge.__main__ import main
from evalforge.registry import registry


def _clear_registry():
    registry._suites.clear()
    registry._agents.clear()


def test_cli_list_and_run(tmp_path, capsys):
    _clear_registry()
    suite_file = tmp_path / "suite.py"
    suite_file.write_text(
        "from evalforge import TestCase\n"
        "from evalforge.registry import registry\n"
        "from evalforge.scorer import exact_match\n"
        "@registry.suite('demo-suite')\n"
        "def suite():\n"
        "    return [TestCase(id='t1', input='x', expected_output='ok', scoring=exact_match())]\n"
        "@registry.agent('demo-agent')\n"
        "def agent(_input):\n"
        "    return 'ok'\n"
    )

    assert main(["list", str(suite_file), "--output", "json"]) == 0
    listing = json.loads(capsys.readouterr().out)
    assert "demo-suite" in listing["suites"]
    assert "demo-agent" in listing["agents"]

    _clear_registry()
    exit_code = main([
        "run",
        str(suite_file),
        "--suite",
        "demo-suite",
        "--agent",
        "demo-agent",
        "--output",
        "json",
    ])
    run_out = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert run_out["passed"] == 1


def test_cli_compare(tmp_path, capsys):
    history = tmp_path / "history.jsonl"
    history.write_text(
        json.dumps(
            {
                "suite_name": "demo",
                "run_id": "a",
                "pass_rate": 1.0,
                "results": [{"test_case_id": "x", "passed": True}],
            }
        )
        + "\n"
        + json.dumps(
            {
                "suite_name": "demo",
                "run_id": "b",
                "pass_rate": 0.0,
                "results": [{"test_case_id": "x", "passed": False}],
            }
        )
        + "\n"
    )

    exit_code = main(["compare", str(history), "--output", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["regressions"] == ["x"]

    exit_code = main(["compare", str(history)])
    plain = capsys.readouterr().out
    assert exit_code == 1
    assert "Regressions:" in plain
    assert "- x" in plain


def test_cli_error_and_plain_paths(tmp_path, capsys):
    _clear_registry()

    assert main(["list"]) == 0
    plain = capsys.readouterr().out
    assert "Suites:" in plain

    missing = main(["run", str(tmp_path / "missing.py")])
    err = capsys.readouterr().err
    assert missing == 2
    assert "Error:" in err

    empty_history = tmp_path / "empty.jsonl"
    empty_history.write_text("")
    compare_code = main(["compare", str(empty_history)])
    output = capsys.readouterr().out
    assert compare_code == 1
    assert "No runs found" in output


def test_cli_parse_choose_and_module_load_edges(tmp_path, monkeypatch):
    existing = tmp_path / "ok.py"
    existing.write_text("x = 1\n")

    assert cli._parse_tags(None) is None
    assert cli._parse_tags(" ,, ") is None
    assert cli._parse_tags("a, b") == ["a", "b"]

    with pytest.raises(ValueError, match="Unknown suite"):
        cli._choose_one("suite", ["s1"], "missing")
    with pytest.raises(ValueError, match="No suites registered"):
        cli._choose_one("suite", [], None)
    with pytest.raises(ValueError, match="Multiple suites"):
        cli._choose_one("suite", ["a", "b"], None)
    assert cli._choose_one("suite", ["a"], None) == "a"

    monkeypatch.setattr(
        cli.importlib.util,
        "spec_from_file_location",
        lambda *_args, **_kwargs: types.SimpleNamespace(loader=None),
    )
    with pytest.raises(RuntimeError, match="Unable to load module"):
        cli._load_python_file(str(existing))


def test_cli_run_with_tags_html_output_and_compare_plain(tmp_path, capsys):
    _clear_registry()
    suite_file = tmp_path / "suite_tags.py"
    suite_file.write_text(
        "from evalforge import TestCase\n"
        "from evalforge.registry import registry\n"
        "from evalforge.scorer import exact_match\n"
        "@registry.suite('tag-suite')\n"
        "def suite():\n"
        "    return [\n"
        "        TestCase(id='keep', input='x', expected_output='ok', scoring=exact_match(), tags=['keep']),\n"
        "        TestCase(id='drop', input='y', expected_output='ok', scoring=exact_match(), tags=['drop']),\n"
        "    ]\n"
        "@registry.agent('tag-agent')\n"
        "def agent(_input):\n"
        "    return 'ok'\n"
    )

    code = main([
        "run",
        str(suite_file),
        "--suite",
        "tag-suite",
        "--agent",
        "tag-agent",
        "--tags",
        "keep",
        "--output",
        "html",
    ])
    html = capsys.readouterr().out
    assert code == 0
    assert "<!DOCTYPE html>" in html
    assert "keep" in html
    assert "drop" not in html

    assert main(["list", str(suite_file)]) == 0
    listing_plain = capsys.readouterr().out
    assert "- tag-suite" in listing_plain
    assert "- tag-agent" in listing_plain

    history = tmp_path / "history_plain.jsonl"
    history.write_text(
        json.dumps(
            {
                "suite_name": "demo",
                "run_id": "a",
                "pass_rate": 1.0,
                "results": [{"test_case_id": "x", "passed": True}],
            }
        )
        + "\n"
        + json.dumps(
            {
                "suite_name": "demo",
                "run_id": "b",
                "pass_rate": 1.0,
                "results": [{"test_case_id": "x", "passed": True}],
            }
        )
        + "\n"
    )
    code = main(["compare", str(history)])
    plain = capsys.readouterr().out
    assert code == 0
    assert "Regressions: none" in plain


def test_cli_compare_suite_and_not_enough_runs(tmp_path, capsys):
    history = tmp_path / "history_suite.jsonl"
    history.write_text(
        json.dumps(
            {
                "suite_name": "only",
                "run_id": "one",
                "pass_rate": 1.0,
                "results": [{"test_case_id": "x", "passed": True}],
            }
        )
        + "\n"
    )

    code = main(["compare", str(history), "--suite", "only"])
    output = capsys.readouterr().out
    assert code == 1
    assert "Need at least two runs to compare" in output


def test_cli_print_run_cli_and_module_entrypoint(tmp_path, monkeypatch):
    _clear_registry()

    called = {"report": 0}
    monkeypatch.setattr(cli, "print_report", lambda *_args, **_kwargs: called.__setitem__("report", 1))

    suite_file = tmp_path / "suite_cli.py"
    suite_file.write_text(
        "from evalforge import TestCase\n"
        "from evalforge.registry import registry\n"
        "from evalforge.scorer import exact_match\n"
        "@registry.suite('s')\n"
        "def suite():\n"
        "    return [TestCase(id='a', input='x', expected_output='ok', scoring=exact_match())]\n"
        "@registry.agent('a')\n"
        "def agent(_input):\n"
        "    return 'ok'\n"
    )
    assert main(["run", str(suite_file), "--suite", "s", "--agent", "a", "--output", "cli"]) == 0
    assert called["report"] == 1

    monkeypatch.setattr("sys.argv", ["evalforge", "list"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("evalforge.__main__", run_name="__main__")
    assert exc.value.code == 0

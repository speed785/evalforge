import json

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

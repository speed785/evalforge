from evalforge.test_case import TestResult


def test_test_result_status_error_branch():
    result = TestResult(test_case_id="x", passed=False, score=0.0, error="boom")
    assert result.status == "error"

"""Unit tests for evaluation_service helper functions."""

from app.services.evaluation_service import _is_successful_result


class TestIsSuccessfulResult:
    def test_list_with_valid_items(self):
        assert _is_successful_result({"raw_response": [{"model": "gpt-5.2"}]}) is True

    def test_list_with_failed_item(self):
        assert _is_successful_result({"raw_response": [{"failed": True}]}) is False

    def test_list_with_skipped_item(self):
        assert _is_successful_result({"raw_response": [{"skipped": True}]}) is False

    def test_empty_list(self):
        assert _is_successful_result({"raw_response": []}) is False

    def test_dict_ok(self):
        assert _is_successful_result({"raw_response": {"model": "gpt-5.2"}}) is True

    def test_dict_failed(self):
        assert _is_successful_result({"raw_response": {"failed": True}}) is False

    def test_none_raw(self):
        assert _is_successful_result({"raw_response": None}) is False

    def test_missing_raw(self):
        assert _is_successful_result({}) is False

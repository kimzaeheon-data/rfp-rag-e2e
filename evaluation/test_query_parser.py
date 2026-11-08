"""Offline regressions for catalog condition extraction and the legacy search path."""

import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.retrieval.query_parser import extract_metadata


def catalog_fields(**overrides):
    fields = {
        "agency": None,
        "budget_conditions": [],
        "date_field": None,
        "date_min": None,
        "date_max": None,
        "sort_by": None,
        "sort_order": None,
        "unsupported_conditions": [],
    }
    if "budget_min" in overrides:
        fields["budget_conditions"].append({"amount": overrides.pop("budget_min"), "operator": "이상"})
    if "budget_max" in overrides:
        fields["budget_conditions"].append({"amount": overrides.pop("budget_max"), "operator": "이하"})
    fields.update(overrides)
    return fields


class QueryParserTests(unittest.TestCase):
    def parse(self, payload, question="등록된 사업을 모두 알려줘", *, for_catalog=True):
        response = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
        )])
        with patch("backend.retrieval.query_parser.OpenAI") as factory:
            factory.return_value.chat.completions.create.return_value = response
            result = extract_metadata(question, timeout=10.0, for_catalog=for_catalog)
        return result, factory

    def test_scope_comes_from_filters_including_zero_and_empty_result_conditions(self):
        cases = (
            {"budget_min": 0},
            {"budget_min": 500_000_000},
            {"budget_min": 100_000_000, "budget_max": 500_000_000},
            {"budget_min": 1_000_000_000_000},
            {"agency": "테스트정보원"},
            {"date_field": "announcement_date", "date_min": "2024-05-01", "date_max": "2024-06-30"},
            {"budget_min": 500_000_000, "sort_by": "budget_amount", "sort_order": "asc"},
        )
        for values in cases:
            with self.subTest(values=values):
                result, _ = self.parse(catalog_fields(**values))
                self.assertEqual(result["catalog_scope"], "filtered")
                for key, value in values.items():
                    self.assertEqual(result[key], value)

    def test_budget_comparisons_are_converted_to_inclusive_integer_bounds(self):
        cases = (
            ("이상", 500_000_000, None),
            ("초과", 500_000_001, None),
            ("이하", None, 500_000_000),
            ("미만", None, 499_999_999),
            ("같음", 500_000_000, 500_000_000),
        )
        for operator, lower, upper in cases:
            with self.subTest(operator=operator):
                result, _ = self.parse(catalog_fields(budget_conditions=[
                    {"amount": 500_000_000, "operator": operator}
                ]))
                self.assertEqual(result["budget_min"], lower)
                self.assertEqual(result["budget_max"], upper)
                self.assertEqual(result["catalog_scope"], "filtered")

    def test_multiple_budget_comparisons_use_the_intersection(self):
        conditions = [
            {"amount": 500_000_000, "operator": "초과"},
            {"amount": 100_000_000, "operator": "이상"},
            {"amount": 900_000_000, "operator": "이하"},
            {"amount": 700_000_000, "operator": "미만"},
        ]
        for values in (conditions, list(reversed(conditions))):
            with self.subTest(conditions=values):
                result, _ = self.parse(catalog_fields(budget_conditions=values))
                self.assertEqual(result["budget_min"], 500_000_001)
                self.assertEqual(result["budget_max"], 699_999_999)

    def test_zero_budget_strict_upper_bound_is_a_valid_empty_result_condition(self):
        result, _ = self.parse(catalog_fields(budget_conditions=[
            {"amount": 0, "operator": "미만"}
        ]))
        self.assertEqual(result["budget_max"], -1)
        self.assertEqual(result["catalog_scope"], "filtered")

    def test_catalog_excludes_the_exact_threshold_for_strict_comparisons(self):
        from langchain_core.documents import Document
        from backend.retrieval.catalog import catalog_response

        docs = {
            label: Document(page_content="", metadata={
                "doc_id": label, "project_name": label, "budget_amount": budget
            })
            for label, budget in (("below", 499_999_999), ("equal", 500_000_000), ("above", 500_000_001))
        }
        store = SimpleNamespace(
            index_to_docstore_id=dict(enumerate(docs)),
            docstore=SimpleNamespace(search=docs.__getitem__),
        )
        for operator, expected in (("초과", {"above"}), ("미만", {"below"})):
            with self.subTest(operator=operator):
                parsed, _ = self.parse(catalog_fields(budget_conditions=[
                    {"amount": 500_000_000, "operator": operator}
                ]))
                result = catalog_response("list", parsed, lambda: store)
                self.assertEqual(result["route_status"], "catalog_ok")
                self.assertEqual({d.metadata["doc_id"] for d in result["docs"]}, expected)

    def test_unfiltered_and_sort_only_queries_have_all_scope(self):
        for values in ({}, {"sort_by": "announcement_date", "sort_order": "asc"}):
            with self.subTest(values=values):
                result, _ = self.parse(catalog_fields(**values))
                self.assertEqual(result["catalog_scope"], "all")

    def test_unsupported_partial_conditions_are_not_promoted_to_supported(self):
        for condition in ("공기업", "5억 이상이거나 1억 이하", "기관 A 또는 기관 B", "제외"):
            with self.subTest(condition=condition):
                result, _ = self.parse(catalog_fields(
                    budget_min=500_000_000, unsupported_conditions=[condition]
                ))
                self.assertEqual(result["catalog_scope"], "unsupported")

    def test_unanchored_relative_dates_do_not_call_the_api(self):
        questions = (
            "최근 한 달에 공개된 사업을 모두 알려줘",
            "지난 2주에 공개된 사업을 모두 알려줘",
            "이번 달에 발주한 사업을 모두 알려줘",
            "올해 공개된 사업을 모두 알려줘",
            "오늘 공개된 사업을 모두 알려줘",
            "최근에 공개된 사업을 모두 알려줘",
        )
        with patch("backend.retrieval.query_parser.OpenAI") as factory:
            for question in questions:
                with self.subTest(question=question):
                    result = extract_metadata(question, timeout=10.0, for_catalog=True)
                    self.assertEqual(result["catalog_scope"], "unsupported")
                    self.assertIsNone(result["date_min"])
            factory.assert_not_called()

    def test_explicit_reference_dates_can_be_resolved_by_the_model(self):
        for question in (
            "2024-06-30 기준 최근 한 달에 공개된 사업을 모두 알려줘",
            "기준일은 2024년 6월 30일. 최근 한 달에 공개된 사업을 모두 알려줘",
        ):
            with self.subTest(question=question):
                result, factory = self.parse(catalog_fields(
                    date_field="announcement_date", date_min="2024-05-30", date_max="2024-06-30"
                ), question)
                factory.assert_called_once_with(timeout=10.0, max_retries=0)
                self.assertEqual(result["catalog_scope"], "filtered")

    def test_agency_name_containing_a_date_word_is_not_rejected(self):
        result, factory = self.parse(
            catalog_fields(agency="내일연구원"), "내일연구원 발주 사업을 모두 알려줘"
        )
        factory.assert_called_once()
        self.assertEqual(result["agency"], "내일연구원")
        self.assertEqual(result["catalog_scope"], "filtered")

    def test_invalid_conditions_are_rejected(self):
        cases = (
            {"budget_min": True},
            {"budget_min": -1},
            {"budget_min": "500000000"},
            {"budget_conditions": [{"amount": 500_000_000, "operator": "invalid"}]},
            {"budget_conditions": [{"amount": 500_000_000}]},
            {"budget_conditions": None},
            {"budget_min": 500_000_000, "budget_max": 100_000_000},
            {"date_min": "2024-01-01"},
            {"date_field": "announcement_date", "date_min": "2024-02-30"},
            {"date_field": "bid_end", "date_min": "2024-07-01", "date_max": "2024-06-01"},
            {"sort_by": "budget_amount"},
            {"sort_order": "asc"},
            {"unsupported_conditions": None},
            {"catalog_scope": "filtered"},
        )
        for values in cases:
            with self.subTest(values=values):
                result, _ = self.parse(catalog_fields(**values))
                self.assertEqual(result["catalog_scope"], "unsupported")

    def test_structured_output_and_reasoning_preserve_the_service_timeout(self):
        _, factory = self.parse(catalog_fields(budget_min=500_000_000))
        factory.assert_called_once_with(timeout=10.0, max_retries=0)
        options = factory.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(options["model"], "gpt-5-nano")
        self.assertEqual(options["reasoning_effort"], "minimal")
        schema = options["response_format"]["json_schema"]
        self.assertTrue(schema["strict"])
        self.assertFalse(schema["schema"]["additionalProperties"])
        self.assertEqual(set(schema["schema"]["required"]), set(catalog_fields()))
        self.assertNotIn("catalog_scope", schema["schema"]["properties"])

    def test_regular_search_keeps_its_existing_metadata_contract(self):
        result, factory = self.parse(
            {"agency": "테스트정보원", "project_name": "테스트 사업", "budget_min": 0},
            "테스트정보원의 테스트 사업 예산을 알려줘", for_catalog=False,
        )
        self.assertEqual(result["agency"], "테스트정보원")
        self.assertEqual(result["project_name"], "테스트 사업")
        self.assertEqual(result["budget_min"], 0)
        self.assertNotIn("catalog_scope", result)
        options = factory.return_value.chat.completions.create.call_args.kwargs
        self.assertNotIn("response_format", options)
        self.assertNotIn("reasoning_effort", options)


if __name__ == "__main__":
    unittest.main()

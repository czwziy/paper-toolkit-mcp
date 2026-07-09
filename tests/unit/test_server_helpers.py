"""Hermetic unit tests for server.py aggregation helpers.

Covers the post-cleanup aggregation logic that AI-facing search relies on:
  - _filter_by_year: post-hoc year filtering with boundary + malformed-date cases
  - _simplify_for_ai: field projection (DOI/pdf_url never leaked to AI)
  - _dedupe_papers: multi-source field merging + abstract-required invariant
  - _merge_papers: JSON list/dict merge logic (real data-flow format)
  - _parse_sources: preset group resolution + unknown filtering

All list/dict fields (authors/categories/keywords/references/extra) use
JSON strings as they would in real Paper.to_dict() output — not Python
lists/dicts — so these tests catch the real merge bugs that the previous
list-based tests masked.

storage.upsert_papers is mocked so these tests never touch the real DB.
"""
import json
import unittest
from unittest.mock import patch

from paper_toolkit_mcp import server


def _patch_upsert():
    """Mock storage.upsert_papers so _dedupe_papers is hermetic."""
    return patch.object(server.storage, "upsert_papers", return_value=0)


def _jlist(items):
    """Helper: build a JSON list string as Paper.to_dict() would emit."""
    return json.dumps(items, ensure_ascii=False)


def _jdict(d):
    """Helper: build a JSON dict string as Paper.to_dict() would emit."""
    return json.dumps(d, ensure_ascii=False)


class TestFilterByYear(unittest.TestCase):
    def test_no_bounds_returns_all(self):
        papers = [{"published_date": "2020-01-01"}, {"published_date": "2024-01-01"}]
        self.assertEqual(len(server._filter_by_year(papers)), 2)

    def test_year_from_filters_out_older(self):
        papers = [{"published_date": "2020-01-01"}, {"published_date": "2024-01-01"}]
        result = server._filter_by_year(papers, year_from=2023)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["published_date"], "2024-01-01")

    def test_year_to_filters_out_newer(self):
        papers = [{"published_date": "2020-01-01"}, {"published_date": "2024-01-01"}]
        result = server._filter_by_year(papers, year_to=2021)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["published_date"], "2020-01-01")

    def test_both_bounds_inclusive(self):
        papers = [
            {"published_date": "2019"},
            {"published_date": "2022"},
            {"published_date": "2025"},
        ]
        result = server._filter_by_year(papers, year_from=2020, year_to=2024)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["published_date"], "2022")

    def test_missing_date_excluded_when_filtering(self):
        papers = [
            {"published_date": ""},
            {"published_date": None},
            {"published_date": "2023-01-01"},
        ]
        result = server._filter_by_year(papers, year_from=2020)
        self.assertEqual(len(result), 1)

    def test_malformed_date_excluded(self):
        papers = [
            {"published_date": "not-a-date"},
            {"published_date": "2023-01-01"},
        ]
        result = server._filter_by_year(papers, year_from=2020)
        self.assertEqual(len(result), 1)

    def test_year_from_zero_treated_as_disabled(self):
        papers = [{"published_date": "1990-01-01"}, {"published_date": "2024-01-01"}]
        result = server._filter_by_year(papers, year_from=0)
        self.assertEqual(len(result), 2)


class TestSimplifyForAi(unittest.TestCase):
    def test_projects_only_required_fields(self):
        paper = {
            "cite_key": "Kxq",
            "title": "Title",
            "abstract": "  Abstract  ",
            "published_date": "2023-05-01",
            "source": "arxiv",
            "doi": "10.1000/x",
            "pdf_url": "http://example.org/paper.pdf",
            "paper_id": "secret-id",
        }
        result = server._simplify_for_ai(paper)
        self.assertEqual(result["cite_key"], "Kxq")
        self.assertEqual(result["title"], "Title")
        self.assertEqual(result["abstract"], "Abstract")  # stripped
        self.assertEqual(result["year"], 2023)
        self.assertEqual(result["source"], "arxiv")
        # Sensitive/internal fields must NOT leak to AI
        self.assertNotIn("doi", result)
        self.assertNotIn("pdf_url", result)
        self.assertNotIn("paper_id", result)

    def test_year_empty_when_no_date(self):
        result = server._simplify_for_ai({"cite_key": "X", "abstract": "A"})
        self.assertEqual(result["year"], "")

    def test_year_empty_for_malformed_date(self):
        result = server._simplify_for_ai({"published_date": "abc", "abstract": "A"})
        self.assertEqual(result["year"], "")

    def test_handles_missing_fields_gracefully(self):
        result = server._simplify_for_ai({})
        self.assertEqual(result["cite_key"], "")
        self.assertEqual(result["abstract"], "")
        self.assertEqual(result["year"], "")


class TestDedupePapers(unittest.TestCase):
    def test_discards_papers_without_abstract(self):
        """Design invariant: no abstract → not stored, not returned."""
        papers = [
            {"doi": "10.1/a", "title": "Has", "abstract": "real abstract", "source": "arxiv"},
            {"doi": "10.2/b", "title": "NoAbs", "abstract": "", "source": "pubmed"},
            {"doi": "10.3/c", "title": "BlankAbs", "abstract": "   ", "source": "pmc"},
            {"doi": "10.4/d", "title": "NoneAbs", "abstract": None, "source": "dblp"},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["doi"], "10.1/a")

    def test_merges_complementary_fields_from_multiple_sources(self):
        """Same DOI from arxiv (has PDF) + crossref (has journal date) → merged."""
        papers = [
            {
                "doi": "10.1/x", "title": "T", "abstract": "A",
                "source": "arxiv", "pdf_url": "http://pdf",
            },
            {
                "doi": "10.1/x", "title": "T", "abstract": "A",
                "source": "crossref", "published_date": "2023-01-01",
            },
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        merged = result[0]
        self.assertEqual(merged["pdf_url"], "http://pdf")
        self.assertEqual(merged["published_date"], "2023-01-01")
        self.assertIn("arxiv", merged["source"])
        self.assertIn("crossref", merged["source"])

    def test_distinct_dois_kept_separate(self):
        papers = [
            {"doi": "10.1/a", "title": "A", "abstract": "x"},
            {"doi": "10.2/b", "title": "B", "abstract": "y"},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 2)

    def test_dedup_by_title_when_no_doi(self):
        """Papers without DOI dedup by title+authors."""
        papers = [
            {"title": "Same Title", "authors": _jlist(["Same Author"]), "abstract": "A", "source": "arxiv"},
            {"title": "Same Title", "authors": _jlist(["Same Author"]), "abstract": "A", "source": "pubmed"},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)

    def test_upsert_called_with_deduped(self):
        """_dedupe_papers must persist deduped results to storage."""
        papers = [
            {"doi": "10.1/a", "title": "A", "abstract": "x"},
            {"doi": "10.2/b", "title": "B", "abstract": "y"},
        ]
        with patch.object(server.storage, "upsert_papers", return_value=2) as mock:
            server._dedupe_papers(papers)
        mock.assert_called_once()
        upserted = mock.call_args[0][0]
        self.assertEqual(len(upserted), 2)

    # --- 跨源合并深化测试（多源字段互补是核心设计） ---
    # 所有 list/dict 字段使用真实的 JSON 字符串格式（Paper.to_dict() 的输出）

    def test_three_sources_merge_into_one(self):
        """arxiv(PDF) + crossref(date) + semantic(keywords) → 单条全字段记录."""
        papers = [
            {
                "doi": "10.5/multi", "title": "Multi-Source Paper", "abstract": "Core abstract",
                "source": "arxiv", "pdf_url": "https://arxiv.org/pdf/10.5",
                "categories": _jlist(["cs.AI"]),
            },
            {
                "doi": "10.5/multi", "title": "Multi-Source Paper", "abstract": "Core abstract",
                "source": "crossref", "published_date": "2024-03-15",
                "url": "https://doi.org/10.5/multi",
            },
            {
                "doi": "10.5/multi", "title": "Multi-Source Paper", "abstract": "Core abstract",
                "source": "semantic",
                "keywords": _jlist(["deep learning"]),
            },
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        m = result[0]
        # 三源各自贡献的字段都应存在
        self.assertEqual(m["pdf_url"], "https://arxiv.org/pdf/10.5")
        self.assertEqual(m["published_date"], "2024-03-15")
        self.assertEqual(m["url"], "https://doi.org/10.5/multi")
        # JSON 字段应为合并后的 JSON 字符串
        self.assertEqual(json.loads(m["categories"]), ["cs.AI"])
        self.assertEqual(json.loads(m["keywords"]), ["deep learning"])
        # source 字段累积所有来源
        for src in ("arxiv", "crossref", "semantic"):
            self.assertIn(src, m["source"])

    def test_cross_source_abstract_backfill(self):
        """源 A 无摘要 + 源 B 有摘要（同 DOI）→ 合并后保留摘要，不丢弃.

        这是关键场景：单个无摘要的 paper 会被丢弃，但如果同 dedup_key
        的另一源有摘要，合并结果应当保留。否则会丢失有摘要的记录。
        """
        papers = [
            {"doi": "10.6/backfill", "title": "T", "abstract": "", "source": "crossref"},
            {"doi": "10.6/backfill", "title": "T", "abstract": "Real abstract from arxiv",
             "source": "arxiv", "pdf_url": "https://arxiv.org/pdf/x"},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["abstract"], "Real abstract from arxiv")
        self.assertEqual(result[0]["pdf_url"], "https://arxiv.org/pdf/x")

    def test_cross_source_abstract_backfill_reverse_order(self):
        """顺序无关：先有摘要后无摘要 → 同样保留摘要."""
        papers = [
            {"doi": "10.7/rev", "title": "T", "abstract": "From arxiv", "source": "arxiv"},
            {"doi": "10.7/rev", "title": "T", "abstract": "", "source": "crossref"},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["abstract"], "From arxiv")

    def test_all_sources_no_abstract_discards_group(self):
        """同 DOI 的所有源都无摘要 → 整组丢弃."""
        papers = [
            {"doi": "10.8/none", "title": "T", "abstract": "", "source": "arxiv"},
            {"doi": "10.8/none", "title": "T", "abstract": None, "source": "crossref"},
            {"doi": "10.8/none", "title": "T", "abstract": "  ", "source": "semantic"},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 0)

    def test_existing_nonempty_field_not_overwritten_by_empty(self):
        """已有非空字段不被后续空值覆盖."""
        papers = [
            {"doi": "10.9/prio", "title": "Original Title", "abstract": "Original abstract",
             "source": "arxiv", "pdf_url": "https://original.pdf"},
            {"doi": "10.9/prio", "title": "", "abstract": "",
             "source": "crossref", "pdf_url": ""},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        m = result[0]
        self.assertEqual(m["title"], "Original Title")
        self.assertEqual(m["abstract"], "Original abstract")
        self.assertEqual(m["pdf_url"], "https://original.pdf")

    def test_pdf_url_cross_source_completion(self):
        """源 A 有 PDF URL，源 B 没有 → 合并后保留 A 的."""
        papers = [
            {"doi": "10.10/pdf", "title": "T", "abstract": "A", "source": "crossref"},
            {"doi": "10.10/pdf", "title": "T", "abstract": "A", "source": "arxiv",
             "pdf_url": "https://arxiv.org/pdf/10.10"},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pdf_url"], "https://arxiv.org/pdf/10.10")

    def test_source_field_accumulates_all_sources(self):
        """多次合并后 source 字段应包含所有来源标识."""
        papers = [
            {"doi": "10.11/src", "title": "T", "abstract": "A", "source": "arxiv"},
            {"doi": "10.11/src", "title": "T", "abstract": "A", "source": "pubmed"},
            {"doi": "10.11/src", "title": "T", "abstract": "A", "source": "semantic"},
            {"doi": "10.11/src", "title": "T", "abstract": "A", "source": "dblp"},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        for src in ("arxiv", "pubmed", "semantic", "dblp"):
            self.assertIn(src, result[0]["source"])

    def test_source_field_no_substring_false_positive(self):
        """源名子串匹配 bug 回归：'med' 不应匹配到已有 'medrxiv'."""
        # 旧实现用 `in` 子串判断，会导致 "med" 被认为已存在而不追加
        papers = [
            {"doi": "10.15/sub", "title": "T", "abstract": "A", "source": "medrxiv"},
            {"doi": "10.15/sub", "title": "T", "abstract": "A", "source": "med"},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        src = result[0]["source"]
        sources = {s.strip() for s in src.split(",")}
        self.assertIn("medrxiv", sources)
        self.assertIn("med", sources)

    def test_json_list_field_merge_deduplicates(self):
        """JSON list 字段（authors/categories/keywords/references）合并去重.

        使用真实 JSON 字符串格式（Paper.to_dict() 的输出），而非 Python list。
        这能抓住旧实现的死代码 bug（旧 list 合并分支永不触发）。
        """
        papers = [
            {"doi": "10.12/list", "title": "T", "abstract": "A", "source": "arxiv",
             "authors": _jlist(["Alice", "Bob"]), "categories": _jlist(["cs.AI", "cs.LG"])},
            {"doi": "10.12/list", "title": "T", "abstract": "A", "source": "semantic",
             "authors": _jlist(["Bob", "Charlie"]), "categories": _jlist(["cs.AI", "cs.CL"])},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        m = result[0]
        # 合并去重，保持首次出现顺序
        self.assertEqual(json.loads(m["authors"]), ["Alice", "Bob", "Charlie"])
        self.assertEqual(json.loads(m["categories"]), ["cs.AI", "cs.LG", "cs.CL"])

    def test_json_dict_field_merge(self):
        """JSON dict 字段（extra）合并：new 覆盖 old 的同名键，互补键保留.

        这能抓住旧实现的 bug：旧代码 `str(dict)` 存的是 Python repr，
        不可解析；且 dict 合并分支用 isinstance(list) 判断永不触发。
        """
        papers = [
            {"doi": "10.16/dict", "title": "T", "abstract": "A", "source": "arxiv",
             "extra": _jdict({"publisher": "Elsevier", "oa": "green"})},
            {"doi": "10.16/dict", "title": "T", "abstract": "A", "source": "crossref",
             "extra": _jdict({"publisher": "Springer", "issn": "1234-5678"})},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        m = result[0]
        extra = json.loads(m["extra"])
        # new 覆盖 old 同名键
        self.assertEqual(extra["publisher"], "Springer")
        # 互补键保留
        self.assertEqual(extra["oa"], "green")
        self.assertEqual(extra["issn"], "1234-5678")

    def test_extra_not_python_repr(self):
        """extra 必须是 JSON 而非 Python repr（str(dict)）.

        旧 bug：extra 被 str() 后存为 "{'k': 'v'}"（单引号），
        json.loads 会失败。新实现必须保证可解析。
        """
        paper = {
            "doi": "10.17/repr", "title": "T", "abstract": "A", "source": "arxiv",
            "extra": _jdict({"k": "v"}),
        }
        with _patch_upsert():
            result = server._dedupe_papers([paper])
        self.assertEqual(len(result), 1)
        # 必须是合法 JSON（双引号），不是 Python repr（单引号）
        parsed = json.loads(result[0]["extra"])
        self.assertEqual(parsed, {"k": "v"})

    def test_references_field_merges_as_json_list(self):
        """references 字段（DB 列名 refs）作为 JSON list 合并."""
        papers = [
            {"doi": "10.18/refs", "title": "T", "abstract": "A", "source": "arxiv",
             "references": _jlist(["10.1/x", "10.2/y"])},
            {"doi": "10.18/refs", "title": "T", "abstract": "A", "source": "crossref",
             "references": _jlist(["10.2/y", "10.3/z"])},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        refs = json.loads(result[0]["references"])
        self.assertEqual(refs, ["10.1/x", "10.2/y", "10.3/z"])

    def test_published_date_cross_source_backfill(self):
        """源 A 无日期 + 源 B 有日期 → 合并后补全."""
        papers = [
            {"doi": "10.13/date", "title": "T", "abstract": "A", "source": "arxiv"},
            {"doi": "10.13/date", "title": "T", "abstract": "A", "source": "crossref",
             "published_date": "2022-06-01"},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["published_date"], "2022-06-01")

    def test_doi_normalization_for_dedup(self):
        """DOI 大小写/空格差异应识别为同一论文."""
        papers = [
            {"doi": "  10.14/CASE  ", "title": "T", "abstract": "A", "source": "arxiv"},
            {"doi": "10.14/case", "title": "T", "abstract": "A", "source": "crossref"},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)

    def test_merge_does_not_lose_distinct_papers(self):
        """混合场景：有重复也有独立论文 → 正确区分."""
        papers = [
            # 两条同 DOI（应合并）
            {"doi": "10.20/a", "title": "Dup A", "abstract": "A1", "source": "arxiv"},
            {"doi": "10.20/a", "title": "Dup A", "abstract": "A1", "source": "crossref"},
            # 一条独立
            {"doi": "10.21/b", "title": "Unique B", "abstract": "B1", "source": "pubmed"},
            # 两条同 title 无 DOI（应合并）
            {"title": "No DOI Title", "authors": _jlist(["Same Author"]), "abstract": "C1", "source": "semantic"},
            {"title": "No DOI Title", "authors": _jlist(["Same Author"]), "abstract": "C1", "source": "dblp"},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 3)

    def test_malformed_json_does_not_crash_merge(self):
        """损坏的 JSON 字符串不应导致合并崩溃（降级为空列表）."""
        papers = [
            {"doi": "10.19/bad", "title": "T", "abstract": "A", "source": "arxiv",
             "authors": "not-valid-json", "extra": "also-not-json"},
            {"doi": "10.19/bad", "title": "T", "abstract": "A", "source": "crossref",
             "authors": _jlist(["Alice"])},
        ]
        with _patch_upsert():
            result = server._dedupe_papers(papers)
        self.assertEqual(len(result), 1)
        # 损坏的 JSON 降级为空，新数据正常合并
        self.assertEqual(json.loads(result[0]["authors"]), ["Alice"])


class TestMergePapersDirect(unittest.TestCase):
    """直接测试 _merge_papers，覆盖边界情况."""

    def test_empty_json_list_treated_as_empty(self):
        existing = {"authors": "[]"}
        new = {"authors": _jlist(["Alice"])}
        server._merge_papers(existing, new)
        self.assertEqual(json.loads(existing["authors"]), ["Alice"])

    def test_empty_json_dict_treated_as_empty(self):
        existing = {"extra": "{}"}
        new = {"extra": _jdict({"k": "v"})}
        server._merge_papers(existing, new)
        self.assertEqual(json.loads(existing["extra"]), {"k": "v"})

    def test_new_empty_does_not_overwrite_existing_list(self):
        existing = {"authors": _jlist(["Alice"])}
        new = {"authors": "[]"}
        server._merge_papers(existing, new)
        self.assertEqual(json.loads(existing["authors"]), ["Alice"])

    def test_new_empty_does_not_overwrite_existing_dict(self):
        existing = {"extra": _jdict({"k": "v"})}
        new = {"extra": "{}"}
        server._merge_papers(existing, new)
        self.assertEqual(json.loads(existing["extra"]), {"k": "v"})

    def test_source_set_membership_not_substring(self):
        """'pmc' 已存在时，'pmc' 不应重复添加；'pmc2' 应添加."""
        existing = {"source": "arxiv,pmc"}
        new = {"source": "pmc"}
        server._merge_papers(existing, new)
        self.assertEqual(existing["source"], "arxiv,pmc")  # no dup

        new2 = {"source": "pmc2"}
        server._merge_papers(existing, new2)
        sources = {s.strip() for s in existing["source"].split(",")}
        self.assertEqual(sources, {"arxiv", "pmc", "pmc2"})


class TestParseSources(unittest.TestCase):
    def test_all_returns_all_sources(self):
        self.assertEqual(set(server._parse_sources("all")), set(server.ALL_SOURCES))

    def test_empty_returns_all(self):
        self.assertEqual(set(server._parse_sources("")), set(server.ALL_SOURCES))

    def test_preset_group_medical(self):
        result = server._parse_sources("medical")
        self.assertEqual(set(result), {"pubmed", "pmc", "medrxiv"})

    def test_preset_group_cs(self):
        result = server._parse_sources("cs")
        self.assertEqual(set(result), {"arxiv", "dblp", "semantic"})

    def test_preset_group_metadata(self):
        result = server._parse_sources("metadata")
        self.assertEqual(set(result), {"crossref", "openalex"})

    def test_comma_separated_individual(self):
        result = server._parse_sources("arxiv,pubmed")
        self.assertEqual(set(result), {"arxiv", "pubmed"})

    def test_unknown_sources_filtered(self):
        result = server._parse_sources("arxiv,unknown,foo")
        self.assertEqual(result, ["arxiv"])

    def test_group_mixed_with_individual(self):
        result = server._parse_sources("arxiv,medical")
        self.assertEqual(set(result), {"arxiv", "pubmed", "pmc", "medrxiv"})

    def test_dedupes_repeated(self):
        result = server._parse_sources("arxiv,arxiv,pubmed")
        self.assertEqual(result, ["arxiv", "pubmed"])


if __name__ == "__main__":
    unittest.main()

"""真实抓取集成测试：验证每个学术源能否真正获取摘要与全文。

默认不参与 CI（CI 仅跑 tests/unit 离线单测，见 pyproject.toml 的 testpaths）。
本地运行方式：

    pytest tests/integration/test_live_fetch.py -m integration --no-cov

设计原则（harness 9.4 验证强制 —— 没有机械化的验证就不是约定）：
- 稳定平台（arxiv/pubmed/crossref/openalex/semantic/biorxiv/medrxiv/iacr/
  europepmc/dblp/zenodo/hal/doaj/pmc）：硬断言。搜索必须返回结果；有摘要的源
  摘要须非空（dblp 无摘要，改为断言 title+authors）；支持 read 的源须提取到
  >200 字符的实质文本。任一失败即代表连接器真正坏了，需修复。
- 不稳定平台（google_scholar/ssrn/citeseerx/base/openaire/unpaywall）：已知
  反爬/限流（见 README "Known Upstream Limitations"），网络异常时 pytest.skip
  而非失败，避免因上游不稳定误伤测试套件。

read 模式说明：
- "always"：直接 read 第一条结果的 paper_id（arxiv/biorxiv/medrxiv/iacr）
- "oa"：在结果中找第一条带 pdf_url 的开放获取论文再 read（semantic/pmc/europepmc）
- "record"：仅当结果带 pdf_url 才 read（zenodo/hal/doaj），否则跳过 read
- None：read 仅返回 info-only 提示信息（pubmed/crossref/openalex/dblp），不断言全文
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

# 用于 read 测试的临时保存目录
SAVE_PATH = "/tmp/paper_live_fetch_test"

# ---------------------------------------------------------------------------
# 平台能力表
# ---------------------------------------------------------------------------
# has_abstract=False 的源（dblp）改为断言 title + authors 非空
# read_mode 决定是否断言全文，详见模块 docstring
STABLE_PLATFORMS = [
    {"id": "arxiv", "module": "arxiv", "cls": "ArxivSearcher",
     "query": "attention mechanism", "kwargs": {"max_results": 3},
     "has_abstract": True, "read_mode": "always"},
    {"id": "pubmed", "module": "pubmed", "cls": "PubMedSearcher",
     "query": "transformer neural network", "kwargs": {"max_results": 3},
     "has_abstract": True, "read_mode": None},
    {"id": "biorxiv", "module": "biorxiv", "cls": "BioRxivSearcher",
     "query": "bioinformatics", "kwargs": {"max_results": 3, "days": 60},
     "has_abstract": True, "read_mode": "always"},
    {"id": "medrxiv", "module": "medrxiv", "cls": "MedRxivSearcher",
     "query": "infectious_diseases", "kwargs": {"max_results": 3, "days": 60},
     "has_abstract": True, "read_mode": "always"},
    {"id": "crossref", "module": "crossref", "cls": "CrossRefSearcher",
     "query": "graph neural network", "kwargs": {"max_results": 3},
     "has_abstract": True, "read_mode": None},
    {"id": "openalex", "module": "openalex", "cls": "OpenAlexSearcher",
     "query": "vision transformers", "kwargs": {"max_results": 3},
     "has_abstract": True, "read_mode": None},
    {"id": "semantic", "module": "semantic", "cls": "SemanticSearcher",
     "query": "BERT language model", "kwargs": {"max_results": 5},
     "has_abstract": True, "read_mode": "oa"},
    {"id": "europepmc", "module": "europepmc", "cls": "EuropePMCSearcher",
     "query": "genomics", "kwargs": {"max_results": 5},
     "has_abstract": True, "read_mode": "oa"},
    {"id": "pmc", "module": "pmc", "cls": "PMCSearcher",
     "query": "cancer immunotherapy", "kwargs": {"max_results": 5},
     "has_abstract": True, "read_mode": "oa"},
    {"id": "iacr", "module": "iacr", "cls": "IACRSearcher",
     "query": "zero knowledge proof",
     "kwargs": {"max_results": 3, "fetch_details": False},
     "has_abstract": True, "read_mode": "always"},
    {"id": "dblp", "module": "dblp", "cls": "DBLPSearcher",
     "query": "machine learning", "kwargs": {"max_results": 3},
     "has_abstract": False, "read_mode": None},
    {"id": "zenodo", "module": "zenodo", "cls": "ZenodoSearcher",
     "query": "machine learning", "kwargs": {"max_results": 5},
     "has_abstract": True, "read_mode": "record"},
    {"id": "hal", "module": "hal", "cls": "HALSearcher",
     "query": "machine learning", "kwargs": {"max_results": 5},
     "has_abstract": True, "read_mode": "record"},
    {"id": "doaj", "module": "doaj", "cls": "DOAJSearcher",
     "query": "machine learning", "kwargs": {"max_results": 5},
     "has_abstract": True, "read_mode": "record"},
]

# 不稳定平台：网络异常 skip，不挂套件
UNSTABLE_PLATFORMS = [
    {"id": "google_scholar", "module": "google_scholar", "cls": "GoogleScholarSearcher",
     "query": "deep learning survey", "kwargs": {"max_results": 3}},
    {"id": "ssrn", "module": "ssrn", "cls": "SSRNSearcher",
     "query": "machine learning", "kwargs": {"max_results": 3}},
    {"id": "citeseerx", "module": "citeseerx", "cls": "CiteSeerXSearcher",
     "query": "machine learning", "kwargs": {"max_results": 3}},
    {"id": "base", "module": "base_search", "cls": "BASESearcher",
     "query": "machine learning", "kwargs": {"max_results": 3}},
    {"id": "openaire", "module": "openaire", "cls": "OpenAiresearcher",
     "query": "climate change", "kwargs": {"max_results": 3}},
]


def _make_searcher(spec):
    """按能力表惰性构造 searcher，避免模块加载即触发不必要导入。"""
    mod = __import__(
        f"paper_toolkit_mcp.academic_platforms.{spec['module']}",
        fromlist=[spec["cls"]],
    )
    return getattr(mod, spec["cls"])()


@pytest.fixture(scope="module", autouse=True)
def _ensure_save_path():
    import os
    os.makedirs(SAVE_PATH, exist_ok=True)
    yield


# ---------------------------------------------------------------------------
# 稳定平台：search + 摘要 + 全文 硬断言
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("spec", STABLE_PLATFORMS, ids=[p["id"] for p in STABLE_PLATFORMS])
def test_stable_platform_live_fetch(spec):
    """稳定平台：搜索返回结果 → 断言摘要/元数据 → 断言全文（如支持 read）。"""
    searcher = _make_searcher(spec)
    papers = searcher.search(spec["query"], **spec["kwargs"])

    # 1. 搜索必须返回结果
    assert papers, f"{spec['id']}: search returned 0 results"
    paper = papers[0]
    assert paper.title, f"{spec['id']}: first paper has empty title"

    # 2. 摘要断言（dblp 无摘要，改为断言 authors）
    if spec["has_abstract"]:
        assert paper.abstract and paper.abstract.strip(), (
            f"{spec['id']}: first paper has empty abstract"
        )
        assert len(paper.abstract.strip()) > 50, (
            f"{spec['id']}: abstract too short ({len(paper.abstract.strip())} chars), "
            f"not a real abstract: {paper.abstract.strip()[:60]!r}"
        )
    else:
        # 元数据源：至少要有作者或 DOI
        assert paper.authors or paper.doi, (
            f"{spec['id']}: metadata source returned neither authors nor doi"
        )

    # 3. 全文断言（按 read_mode）
    mode = spec["read_mode"]
    if mode is None:
        return  # info-only / 不支持 read，跳过全文断言

    if mode == "oa":
        target = next((p for p in papers if p.pdf_url), None)
        if target is None:
            pytest.skip(f"{spec['id']}: no open-access paper with pdf_url in results")
    elif mode == "record":
        if not paper.pdf_url:
            pytest.skip(f"{spec['id']}: first result has no pdf_url, skip record-dependent read")
        target = paper
    else:  # always
        target = paper

    text = searcher.read_paper(target.paper_id, SAVE_PATH)
    assert text and isinstance(text, str), (
        f"{spec['id']}: read_paper returned non-string/empty: {text!r}"
    )
    assert len(text) > 200, (
        f"{spec['id']}: extracted fulltext too short ({len(text)} chars): {text[:80]!r}"
    )
    assert any(c.isalpha() for c in text), (
        f"{spec['id']}: extracted fulltext has no alphabetic content"
    )


# ---------------------------------------------------------------------------
# 不稳定平台：网络异常时 skip
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("spec", UNSTABLE_PLATFORMS, ids=[p["id"] for p in UNSTABLE_PLATFORMS])
def test_unstable_platform_search_optional(spec):
    """不稳定平台：能搜到结果则断言 title 非空；网络异常/0 结果则 skip。"""
    try:
        searcher = _make_searcher(spec)
        papers = searcher.search(spec["query"], **spec["kwargs"])
    except Exception as e:  # 网络/限流/反爬
        pytest.skip(f"{spec['id']}: upstream unavailable ({type(e).__name__}: {e})")

    if not papers:
        pytest.skip(f"{spec['id']}: returned 0 results (upstream rate-limited/blocked)")
    assert papers[0].title, f"{spec['id']}: first paper has empty title"

"""Hermetic unit tests for citation verification (verifier module).

All external HTTP calls are mocked — no network access required.
Tests cover: config loading, score parsing, citation sentence extraction,
single citation verification, manuscript verification, and config validation.
"""
import asyncio
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from paper_toolkit_mcp.storage import PaperStorage
from paper_toolkit_mcp.verifier import (
    ModelConfig,
    VerifierConfig,
    _parse_score_response,
    _verdict,
    extract_citation_sentences,
    load_verifier_config,
    verify_single,
    write_default_config,
)
from paper_toolkit_mcp.verifier import (
    verify_manuscript as _verify_manuscript,
)


class TestParseScoreResponse(unittest.TestCase):
    def test_valid_json(self):
        text = '{"score": 4, "reason": "Good match"}'
        result = _parse_score_response(text, (1, 5))
        self.assertEqual(result["score"], 4)
        self.assertEqual(result["reason"], "Good match")

    def test_json_in_code_fence(self):
        text = '```json\n{"score": 3, "reason": "Partial"}\n```'
        result = _parse_score_response(text, (1, 5))
        self.assertEqual(result["score"], 3)

    def test_json_embedded_in_text(self):
        text = 'The score is {"score": 5, "reason": "Perfect"} for this one.'
        result = _parse_score_response(text, (1, 5))
        self.assertEqual(result["score"], 5)

    def test_score_out_of_range_clamps_to_zero(self):
        text = '{"score": 9, "reason": "Too high"}'
        result = _parse_score_response(text, (1, 5))
        self.assertEqual(result["score"], 0)

    def test_fallback_to_first_integer(self):
        text = "I would give this a 2 out of 5."
        result = _parse_score_response(text, (1, 5))
        self.assertEqual(result["score"], 2)

    def test_completely_unparseable(self):
        text = "No score here at all"
        result = _parse_score_response(text, (1, 5))
        self.assertEqual(result["score"], 0)


class TestVerdict(unittest.TestCase):
    def test_match(self):
        self.assertEqual(_verdict(4.0, (1, 5)), "match")

    def test_partial(self):
        self.assertEqual(_verdict(2.5, (1, 5)), "partial")

    def test_mismatch(self):
        self.assertEqual(_verdict(1.0, (1, 5)), "mismatch")


class TestExtractCitationSentences(unittest.TestCase):
    def test_simple_sentence(self):
        text = "Deep learning has achieved great success [@Kxq]."
        results = extract_citation_sentences(text)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["cite_key"], "Kxq")
        self.assertIn("Deep learning", results[0]["sentence"])

    def test_multiple_citations(self):
        text = (
            "CNNs are widely used [@Abc]. "
            "Transformers have replaced RNNs [@Def]."
        )
        results = extract_citation_sentences(text)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["cite_key"], "Abc")
        self.assertEqual(results[1]["cite_key"], "Def")

    def test_deduplication(self):
        text = "This is stated in [@Kxq] and also in [@Kxq]."
        results = extract_citation_sentences(text)
        self.assertEqual(len(results), 1)

    def test_no_citations(self):
        text = "No citations here."
        results = extract_citation_sentences(text)
        self.assertEqual(len(results), 0)

    def test_sentence_boundary_at_newline(self):
        text = "Previous work [@Xyz]\nNew paragraph here."
        results = extract_citation_sentences(text)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["cite_key"], "Xyz")


class TestLoadVerifierConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_file_returns_empty_config(self):
        config = load_verifier_config(os.path.join(self.tmpdir, "nonexistent.json"))
        self.assertEqual(len(config.models), 0)

    def test_default_config_path_is_under_harness(self):
        """Default config path should be .harness/verifier_models.json."""
        from paper_toolkit_mcp.verifier import _default_config_path

        path = _default_config_path(work_dir=self.tmpdir)
        self.assertIn(".harness", path)
        self.assertTrue(path.endswith("verifier_models.json"))

    def test_valid_config_file(self):
        config_data = {
            "models": [
                {
                    "name": "test-model",
                    "provider": "openai_compatible",
                    "api_key_env": "TEST_KEY",
                    "base_url": "https://api.test.com/v1",
                    "model": "test-v1",
                },
            ],
            "score_range": [1, 5],
        }
        path = os.path.join(self.tmpdir, "verifier_models.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        config = load_verifier_config(path)
        self.assertEqual(len(config.models), 1)
        self.assertEqual(config.models[0].name, "test-model")
        self.assertEqual(config.score_range, (1, 5))

    def test_invalid_json_returns_empty(self):
        path = os.path.join(self.tmpdir, "bad.json")
        with open(path, "w") as f:
            f.write("not json")
        config = load_verifier_config(path)
        self.assertEqual(len(config.models), 0)

    def test_missing_required_field_skips_model(self):
        config_data = {
            "models": [{"name": "incomplete"}],  # missing api_key_env, model
        }
        path = os.path.join(self.tmpdir, "partial.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        config = load_verifier_config(path)
        self.assertEqual(len(config.models), 0)


class TestWriteDefaultConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_template_file(self):
        path = os.path.join(self.tmpdir, "verifier_models.json")
        result = write_default_config(path)
        self.assertTrue(os.path.isfile(result))
        with open(result, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("models", data)

    def test_does_not_overwrite_existing(self):
        path = os.path.join(self.tmpdir, "verifier_models.json")
        with open(path, "w") as f:
            f.write('{"existing": true}')
        write_default_config(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("existing", data)


class TestVerifySingle(unittest.TestCase):
    """Test verify_single with mocked HTTP calls and real storage."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.storage = PaperStorage(db_path=self.db_path)
        # Insert a test paper
        self.storage.upsert_paper({
            "doi": "10.1/test",
            "paper_id": "p1",
            "title": "Deep Learning for Medical Imaging",
            "authors": '["Author A"]',
            "abstract": "This paper surveys deep learning methods for medical image analysis.",
            "source": "arxiv",
        })
        self.paper_row = self.storage.get_by_doi("10.1/test")
        self.cite_key = self.paper_row["cite_key"]

    def tearDown(self):
        self.storage.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_models_returns_error(self):
        config = VerifierConfig(models=[])
        result = asyncio.run(verify_single(
            sentence="Deep learning is used in medicine.",
            cite_key=self.cite_key,
            paper_title="Test",
            paper_abstract="Test abstract",
            config=config,
            storage=self.storage,
        ))
        self.assertIn("error", result)

    def test_cached_scores_returned_without_api_call(self):
        # Pre-populate cache with scores for both models
        config = VerifierConfig(models=[
            ModelConfig(name="model-a", provider="openai_compatible",
                        api_key_env="KEY_A", base_url="https://api.a.com/v1", model="a"),
            ModelConfig(name="model-b", provider="openai_compatible",
                        api_key_env="KEY_B", base_url="https://api.b.com/v1", model="b"),
        ])
        sentence = "Deep learning is used in medicine."
        self.storage.upsert_score(self.cite_key, sentence, "model-a", 4, "Good")
        self.storage.upsert_score(self.cite_key, sentence, "model-b", 3, "OK")

        result = asyncio.run(verify_single(
            sentence=sentence,
            cite_key=self.cite_key,
            paper_title="Test",
            paper_abstract="Test abstract",
            config=config,
            storage=self.storage,
        ))
        self.assertTrue(result["from_cache"])
        self.assertEqual(result["scores"]["model-a"], 4)
        self.assertEqual(result["scores"]["model-b"], 3)

    @patch("paper_toolkit_mcp.verifier._call_model", new_callable=AsyncMock)
    def test_api_call_and_cache(self, mock_call):
        mock_call.return_value = {
            "model_name": "test-model",
            "score": 5,
            "reason": "Perfect match",
            "raw_response": "mocked",
        }
        config = VerifierConfig(models=[
            ModelConfig(name="test-model", provider="openai_compatible",
                        api_key_env="TEST_KEY", base_url="https://api.test.com/v1", model="test"),
        ])
        with patch.dict(os.environ, {"TEST_KEY": "sk-test"}):
            result = asyncio.run(verify_single(
                sentence="Deep learning is used in medicine.",
                cite_key=self.cite_key,
                paper_title="Deep Learning for Medical Imaging",
                paper_abstract="This paper surveys deep learning methods.",
                config=config,
                storage=self.storage,
            ))
        self.assertFalse(result["from_cache"])
        self.assertEqual(result["scores"]["test-model"], 5)
        self.assertEqual(result["verdict"], "match")

        # Verify cached in DB
        cached = self.storage.get_cached_scores(self.cite_key, "Deep learning is used in medicine.")
        self.assertEqual(len(cached), 1)
        self.assertEqual(cached[0]["score"], 5)


class TestVerifyManuscript(unittest.TestCase):
    """Test verify_manuscript with mocked verify_single."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.storage = PaperStorage(db_path=self.db_path)

    def tearDown(self):
        self.storage.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_file_not_found(self):
        config = VerifierConfig(models=[
            ModelConfig(name="m1", provider="openai_compatible",
                        api_key_env="K", base_url="https://api.test.com/v1", model="m"),
        ])
        result = asyncio.run(_verify_manuscript(
            "/nonexistent/file.md", config, self.storage
        ))
        self.assertIn("error", result)

    def test_no_citations(self):
        md_path = os.path.join(self.tmpdir, "test.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("No citations here.\n")
        config = VerifierConfig(models=[
            ModelConfig(name="m1", provider="openai_compatible",
                        api_key_env="K", base_url="https://api.test.com/v1", model="m"),
        ])
        result = asyncio.run(_verify_manuscript(md_path, config, self.storage))
        self.assertEqual(result["status"], "no_citations_found")

    def test_no_models_configured(self):
        md_path = os.path.join(self.tmpdir, "test.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("Some claim [@Xyz].\n")
        config = VerifierConfig(models=[])
        result = asyncio.run(_verify_manuscript(md_path, config, self.storage))
        self.assertIn("error", result)

    @patch("paper_toolkit_mcp.verifier.verify_single", new_callable=AsyncMock)
    def test_successful_verification(self, mock_verify):
        # Insert a paper
        self.storage.upsert_paper({
            "doi": "10.1/test",
            "paper_id": "p1",
            "title": "Test Paper",
            "authors": '["Author"]',
            "abstract": "Abstract here.",
            "source": "arxiv",
        })
        row = self.storage.get_by_doi("10.1/test")
        cite_key = row["cite_key"]

        mock_verify.return_value = {
            "cite_key": cite_key,
            "sentence": f"Some claim [@{cite_key}].",
            "scores": {"test-model": 4},
            "avg_score": 4.0,
            "verdict": "match",
            "details": {},
            "from_cache": False,
        }

        md_path = os.path.join(self.tmpdir, "test.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"Some claim [@{cite_key}].\n")

        config = VerifierConfig(models=[
            ModelConfig(name="test-model", provider="openai_compatible",
                        api_key_env="K", base_url="https://api.test.com/v1", model="m"),
        ])
        result = asyncio.run(_verify_manuscript(md_path, config, self.storage))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["match"], 1)

    def test_unresolved_cite_key(self):
        """Cite key not in papers.db should be reported as unresolved."""
        md_path = os.path.join(self.tmpdir, "test.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("Some claim [@ZZZ].\n")

        config = VerifierConfig(models=[
            ModelConfig(name="m1", provider="openai_compatible",
                        api_key_env="K", base_url="https://api.test.com/v1", model="m"),
        ])
        with patch.dict(os.environ, {"K": "sk-test"}):
            result = asyncio.run(_verify_manuscript(md_path, config, self.storage))
        self.assertIn("ZZZ", result.get("unresolved_keys", []))


class TestStorageScoreMethods(unittest.TestCase):
    """Test citation_scores CRUD in PaperStorage."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.storage = PaperStorage(db_path=self.db_path)

    def tearDown(self):
        self.storage.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_upsert_and_get_score(self):
        self.storage.upsert_score("Kxq", "A sentence.", "gpt-4o", 4, "Good match")
        scores = self.storage.get_cached_scores("Kxq", "A sentence.")
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0]["score"], 4)
        self.assertEqual(scores[0]["model_name"], "gpt-4o")

    def test_upsert_updates_existing(self):
        self.storage.upsert_score("Kxq", "A sentence.", "gpt-4o", 3, "OK")
        self.storage.upsert_score("Kxq", "A sentence.", "gpt-4o", 5, "Actually great")
        scores = self.storage.get_cached_scores("Kxq", "A sentence.")
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0]["score"], 5)

    def test_multiple_models_same_sentence(self):
        self.storage.upsert_score("Kxq", "A sentence.", "model-a", 4, "")
        self.storage.upsert_score("Kxq", "A sentence.", "model-b", 2, "")
        scores = self.storage.get_cached_scores("Kxq", "A sentence.")
        self.assertEqual(len(scores), 2)

    def test_delete_scores_by_cite_key(self):
        self.storage.upsert_score("Kxq", "S1", "m1", 4, "")
        self.storage.upsert_score("Kxq", "S2", "m1", 3, "")
        deleted = self.storage.delete_scores("Kxq")
        self.assertEqual(deleted, 2)
        self.assertEqual(len(self.storage.get_cached_scores("Kxq", "S1")), 0)

    def test_delete_scores_by_sentence(self):
        self.storage.upsert_score("Kxq", "S1", "m1", 4, "")
        self.storage.upsert_score("Kxq", "S2", "m1", 3, "")
        deleted = self.storage.delete_scores("Kxq", "S1")
        self.assertEqual(deleted, 1)
        self.assertEqual(len(self.storage.get_cached_scores("Kxq", "S1")), 0)
        self.assertEqual(len(self.storage.get_cached_scores("Kxq", "S2")), 1)

    def test_sentence_hash_stable(self):
        h1 = PaperStorage.sentence_hash("Hello world")
        h2 = PaperStorage.sentence_hash("Hello world")
        self.assertEqual(h1, h2)

    def test_sentence_hash_different_for_different_text(self):
        h1 = PaperStorage.sentence_hash("Hello world")
        h2 = PaperStorage.sentence_hash("Hello earth")
        self.assertNotEqual(h1, h2)

    def test_get_all_scores(self):
        self.storage.upsert_score("Kxq", "S1", "m1", 4, "")
        self.storage.upsert_score("Abc", "S2", "m1", 3, "")
        all_scores = self.storage.get_all_scores()
        self.assertEqual(len(all_scores), 2)

    def test_get_all_scores_filtered_by_cite_key(self):
        self.storage.upsert_score("Kxq", "S1", "m1", 4, "")
        self.storage.upsert_score("Abc", "S2", "m1", 3, "")
        filtered = self.storage.get_all_scores(cite_key="Kxq")
        self.assertEqual(len(filtered), 1)


if __name__ == "__main__":
    unittest.main()

"""集成测试目录的 pytest 配置。

- collect_ignore：test_e2e.py / test_functional.py 是顶层脚本（import 时即执行
  真实网络请求），并非 pytest 用例。在此忽略它们的收集，避免 `pytest
  tests/integration/` 在收集阶段就触发整轮网络抓取；这两个脚本仍可用
  `python tests/integration/test_e2e.py` 手动运行。
- 注册 integration marker，消除 unknown-marker 警告。
"""
collect_ignore = ["test_e2e.py", "test_functional.py"]


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: 需要网络访问的真实抓取测试，默认不参与 CI"
    )

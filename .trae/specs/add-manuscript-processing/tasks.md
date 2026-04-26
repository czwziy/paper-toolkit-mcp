# Tasks

- [x] Task 1: 创建 search_cache 模块
  - [x] 实现缓存读写逻辑（JSON 格式）
  - [x] 实现 TTL 过期检查
  - [x] 实现缓存清理功能
  - [x] 添加单元测试

- [x] Task 2: 创建 reference 模块
  - [x] 实现占位符解析（正则匹配）
  - [x] 实现 BibTeX 格式生成
  - [x] 实现 RIS 格式生成
  - [x] 实现 GB/T 7714-2015 格式化
  - [x] 添加单元测试

- [x] Task 3: 创建 pandoc_helper 模块
  - [x] 实现 pandoc 可用性检查
  - [x] 实现 Markdown → Word 转换
  - [x] 支持 CSL 样式指定
  - [x] 处理 pandoc 错误

- [x] Task 4: 下载常用 CSL 文件
  - [x] 从 Zotero CSL 仓库下载 chinese-gb7714-2015-numeric.csl
  - [x] 从 Zotero CSL 仓库下载 apa-7th-edition.csl
  - [x] 从 Zotero CSL 仓库下载 ieee.csl
  - [x] 从 Zotero CSL 仓库下载 vancouver.csl
  - [x] 从 Zotero CSL 仓库下载 harvard.csl
  - [x] 保存到项目 `csl/` 目录

- [x] Task 5: 修改 base.py 集成缓存
  - [x] 在 PaperSource 基类添加缓存装饰器/方法
  - [x] 所有 Searcher 自动继承缓存行为

- [x] Task 6: 修改 server.py 添加新工具
  - [x] 添加 `process_manuscript` 工具
  - [x] 添加 `get_paper_metadata` 工具
  - [x] 添加 `export_references` 工具

- [x] Task 7: 修改 cli.py 添加命令
  - [x] 添加 `manuscript` 命令
  - [x] 添加 `cache list/clear` 命令

# Task Dependencies

- Task 2 依赖 Task 1（reference 模块需要缓存支持）
- Task 6 依赖 Task 1, 2, 3（新工具依赖所有新模块）
- Task 5 依赖 Task 1（基类需要缓存模块）
- Task 7 依赖 Task 1, 2（CLI 需要缓存和引用模块）
- Task 4 可并行执行（独立任务）
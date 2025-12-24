"""
L4 Operational Knowledge 检索测试

验证：
1. .ai/operations/ 目录结构正确
2. index.yaml 可解析
3. SOP 文件可被检索
4. AI 能根据关键词匹配正确的 SOP
"""

import os
from pathlib import Path

import pytest
import yaml


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


class TestL4Structure:
    """测试 L4 目录结构"""

    def test_operations_dir_exists(self):
        """验证 .ai/operations/ 目录存在"""
        ops_dir = PROJECT_ROOT / ".ai" / "operations"
        assert ops_dir.exists(), f"L4 目录不存在: {ops_dir}"
        assert ops_dir.is_dir(), f"L4 路径不是目录: {ops_dir}"

    def test_index_yaml_exists(self):
        """验证 index.yaml 存在"""
        index_file = PROJECT_ROOT / ".ai" / "operations" / "index.yaml"
        assert index_file.exists(), f"L4 索引不存在: {index_file}"

    def test_readme_exists(self):
        """验证 README.md 存在"""
        readme = PROJECT_ROOT / ".ai" / "operations" / "README.md"
        assert readme.exists(), f"L4 README 不存在: {readme}"


class TestL4Index:
    """测试 L4 索引"""

    @pytest.fixture
    def index(self) -> dict:
        """加载 index.yaml"""
        index_file = PROJECT_ROOT / ".ai" / "operations" / "index.yaml"
        with open(index_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_index_has_version(self, index):
        """验证索引有版本号"""
        assert "version" in index
        assert index["version"] == "1.0"

    def test_index_has_sops(self, index):
        """验证索引有 SOPs 部分"""
        assert "sops" in index
        assert isinstance(index["sops"], dict)

    def test_index_has_quick_match(self, index):
        """验证索引有快速匹配规则"""
        assert "quick_match" in index
        assert isinstance(index["quick_match"], dict)

    def test_referenced_files_exist(self, index):
        """验证索引引用的文件都存在"""
        ops_dir = PROJECT_ROOT / ".ai" / "operations"

        # 检查 SOPs 部分
        for category, sops in index.get("sops", {}).items():
            for sop in sops:
                if "file" in sop:
                    sop_file = ops_dir / sop["file"]
                    assert sop_file.exists(), f"SOP 文件不存在: {sop_file}"

    def test_quick_match_files_exist(self, index):
        """验证快速匹配引用的文件都存在"""
        ops_dir = PROJECT_ROOT / ".ai" / "operations"

        for keyword, files in index.get("quick_match", {}).items():
            for file in files:
                file_path = ops_dir / file
                assert file_path.exists(), f"快速匹配文件不存在: {file_path} (关键词: {keyword})"


class TestL4Retrieval:
    """测试 L4 检索能力"""

    @pytest.fixture
    def index(self) -> dict:
        """加载 index.yaml"""
        index_file = PROJECT_ROOT / ".ai" / "operations" / "index.yaml"
        with open(index_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def find_sop_by_keyword(self, index: dict, keyword: str) -> list[str]:
        """根据关键词查找 SOP 文件"""
        # 直接匹配 quick_match
        quick_match = index.get("quick_match", {})
        for key, files in quick_match.items():
            if keyword.lower() in key.lower():
                return files

        # 搜索 SOPs 的 triggers
        results = []
        for category, sops in index.get("sops", {}).items():
            for sop in sops:
                triggers = sop.get("triggers", [])
                for trigger in triggers:
                    if keyword.lower() in trigger.lower():
                        results.append(sop["file"])
                        break

        return results

    def test_find_qdrant_sop(self, index):
        """测试：关键词 'qdrant' 能找到 Qdrant SOP"""
        files = self.find_sop_by_keyword(index, "qdrant")
        assert len(files) > 0, "关键词 'qdrant' 应该匹配到 SOP"
        assert any("qdrant" in f.lower() for f in files)

    def test_find_memory_sync_sop(self, index):
        """测试：关键词 'pending' 能找到 Memory Sync SOP"""
        files = self.find_sop_by_keyword(index, "pending")
        assert len(files) > 0, "关键词 'pending' 应该匹配到 SOP"
        assert any("memory" in f.lower() or "sync" in f.lower() for f in files)

    def test_find_session_workflow(self, index):
        """测试：关键词 '会话开始' 能找到 Session Workflow"""
        files = self.find_sop_by_keyword(index, "会话开始")
        assert len(files) > 0, "关键词 '会话开始' 应该匹配到 workflow"


class TestL4Content:
    """测试 L4 内容质量"""

    def get_sop_files(self) -> list[Path]:
        """获取所有 SOP 文件"""
        ops_dir = PROJECT_ROOT / ".ai" / "operations"
        return list(ops_dir.glob("sop-*.md")) + list(ops_dir.glob("workflow-*.md"))

    def test_sop_has_trigger_section(self):
        """验证 SOP 文件有触发条件"""
        for sop_file in self.get_sop_files():
            content = sop_file.read_text(encoding="utf-8")
            assert "触发条件" in content or "Trigger" in content.lower(), \
                f"SOP 缺少触发条件: {sop_file.name}"

    def test_sop_has_steps(self):
        """验证 SOP 文件有步骤"""
        for sop_file in self.get_sop_files():
            content = sop_file.read_text(encoding="utf-8")
            assert "##" in content, f"SOP 缺少步骤章节: {sop_file.name}"
            # 检查是否有代码块（步骤通常包含命令）
            assert "```" in content, f"SOP 缺少代码示例: {sop_file.name}"

    def test_sop_has_related_files(self):
        """验证 SOP 文件有相关文件引用"""
        for sop_file in self.get_sop_files():
            content = sop_file.read_text(encoding="utf-8")
            # 检查是否有"相关文件"部分或文件引用
            has_related = "相关文件" in content or "Related" in content
            has_file_ref = ".md" in content or ".yaml" in content
            assert has_related or has_file_ref, \
                f"SOP 缺少相关文件引用: {sop_file.name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

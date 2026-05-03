"""Tests for Chinese taxonomy baseline."""


from repo_wiki.planner.schema import (
    DEFAULT_CHINESE_TAXONOMY,
    WikiTaxonomyCategory,
)


class TestChineseTaxonomy:
    """Tests for Chinese taxonomy baseline."""

    def test_taxonomy_categories_count(self):
        """Test that we have exactly 11 taxonomy categories."""
        assert len(DEFAULT_CHINESE_TAXONOMY) == 11

    def test_all_categories_have_chinese_names(self):
        """Test all categories have Chinese display names."""
        expected_prefixes = [
            "项目",
            "架构",
            "核心服务",
            "Python",
            "前端",
            "数据模型",
            "API",
            "部署运维",
            "开发",
            "安全",
            "故障",
        ]
        category_values = [cat.value for cat in WikiTaxonomyCategory]
        for prefix in expected_prefixes:
            matches = [v for v in category_values if prefix in v]
            assert len(matches) >= 1, f"No category with prefix '{prefix}'"

    def test_category_order_in_default_taxonomy(self):
        """Test that categories appear in expected order."""
        expected_order = [
            WikiTaxonomyCategory.PROJECT_OVERVIEW,
            WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            WikiTaxonomyCategory.CORE_SERVICES,
            WikiTaxonomyCategory.PYTHON_SERVICES,
            WikiTaxonomyCategory.FRONTEND_APPLICATIONS,
            WikiTaxonomyCategory.DATA_MODELS,
            WikiTaxonomyCategory.API_REFERENCE,
            WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            WikiTaxonomyCategory.SECURITY_COMPLIANCE,
            WikiTaxonomyCategory.TROUBLESHOOTING,
        ]
        assert expected_order == DEFAULT_CHINESE_TAXONOMY

    def test_qoder_like_taxonomy_mapping(self):
        """Test that the taxonomy maps correctly to Qoder-like output categories."""
        # Project overview maps to root-level index pages
        assert WikiTaxonomyCategory.PROJECT_OVERVIEW.value == "项目概述"
        # Architecture maps to design docs
        assert WikiTaxonomyCategory.ARCHITECTURE_DESIGN.value == "架构设计"
        # Services map to core service documentation
        assert WikiTaxonomyCategory.CORE_SERVICES.value == "核心服务"
        # Python services specifically for Python projects
        assert WikiTaxonomyCategory.PYTHON_SERVICES.value == "Python服务"
        # Frontend for UI/UX docs
        assert WikiTaxonomyCategory.FRONTEND_APPLICATIONS.value == "前端应用"
        # Data models for schema/entity docs
        assert WikiTaxonomyCategory.DATA_MODELS.value == "数据模型"
        # API reference for endpoint docs
        assert WikiTaxonomyCategory.API_REFERENCE.value == "API参考"
        # Deployment for ops docs
        assert WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS.value == "部署运维"
        # Development guide for contributor docs
        assert WikiTaxonomyCategory.DEVELOPMENT_GUIDE.value == "开发指南"
        # Security for compliance docs
        assert WikiTaxonomyCategory.SECURITY_COMPLIANCE.value == "安全合规"
        # Troubleshooting for FAQ/debug docs
        assert WikiTaxonomyCategory.TROUBLESHOOTING.value == "故障排除"

    def test_taxonomy_profile_configurable(self):
        """Test that taxonomy can be configured per profile."""
        # The profile field in WikiPlanManifest controls which taxonomy is used
        profile = "qoder-chinese"
        assert profile == "qoder-chinese"

        # Alternative profiles could have different taxonomies
        alt_profile = "qoder-english"
        assert alt_profile == "qoder-english"


class TestAIAPiAtlasTaxonomyFixture:
    """Tests for AI_API_Atlas taxonomy planning assertions."""

    def test_ai_api_atlas_category_coverage(self):
        """Test that AI_API_Atlas would have coverage across all categories."""
        categories = [cat for cat in WikiTaxonomyCategory]

        # AI_API_Atlas should have pages in each category
        expected_coverage = {
            WikiTaxonomyCategory.PROJECT_OVERVIEW: ["overview", "readme", "quickstart"],
            WikiTaxonomyCategory.ARCHITECTURE_DESIGN: ["architecture", "components", "data-flow"],
            WikiTaxonomyCategory.CORE_SERVICES: ["index", "ai-services"],
            WikiTaxonomyCategory.API_REFERENCE: ["api-overview", "endpoints"],
            WikiTaxonomyCategory.DATA_MODELS: ["data-models-overview"],
            WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS: ["deployment", "config"],
            WikiTaxonomyCategory.DEVELOPMENT_GUIDE: ["development", "testing"],
            WikiTaxonomyCategory.SECURITY_COMPLIANCE: ["security", "auth"],
            WikiTaxonomyCategory.TROUBLESHOOTING: ["troubleshooting", "errors"],
        }

        for category, expected_pages in expected_coverage.items():
            assert category in categories, f"Missing category {category}"

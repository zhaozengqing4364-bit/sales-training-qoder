from common.knowledge_engine.config_repo import KnowledgeEntityAliasConfig
from common.knowledge_engine.entity_resolver import KnowledgeEntityResolver


class TestKnowledgeEntityResolver:
    def test_resolver_maps_alias_to_canonical_entity(self):
        resolver = KnowledgeEntityResolver(
            entity_aliases=[
                KnowledgeEntityAliasConfig(
                    canonical_entity="石犀科技",
                    alias="世袭科技",
                    entity_type="company",
                    confidence=0.96,
                )
            ]
        )

        result = resolver.resolve_query("请介绍一下世袭科技")

        assert result.resolved is True
        assert result.normalized_query == "请介绍一下石犀科技"
        assert result.canonical_entities == ["石犀科技"]
        assert len(result.matches) == 1
        assert result.matches[0].canonical_entity == "石犀科技"
        assert result.matches[0].matched_text == "世袭科技"
        assert result.matches[0].match_source == "alias"

    def test_resolver_preserves_exact_canonical_entity_mentions(self):
        resolver = KnowledgeEntityResolver(
            entity_aliases=[
                KnowledgeEntityAliasConfig(
                    canonical_entity="石犀科技",
                    alias="世袭科技",
                    entity_type="company",
                    confidence=0.96,
                )
            ]
        )

        result = resolver.resolve_query("请介绍一下石犀科技")

        assert result.resolved is True
        assert result.normalized_query == "请介绍一下石犀科技"
        assert result.canonical_entities == ["石犀科技"]
        assert len(result.matches) == 1
        assert result.matches[0].matched_text == "石犀科技"
        assert result.matches[0].match_source == "canonical"

    def test_resolver_returns_original_query_when_no_entity_matches(self):
        resolver = KnowledgeEntityResolver(
            entity_aliases=[
                KnowledgeEntityAliasConfig(
                    canonical_entity="石犀科技",
                    alias="世袭科技",
                    entity_type="company",
                    confidence=0.96,
                )
            ]
        )

        result = resolver.resolve_query("请介绍一下这家公司")

        assert result.resolved is False
        assert result.normalized_query == "请介绍一下这家公司"
        assert result.canonical_entities == []
        assert result.matches == []

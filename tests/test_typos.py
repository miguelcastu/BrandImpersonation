from brandwatch.config import BrandConfig
from brandwatch.discovery import build_ct_query_plan, filter_candidates, parse_ct_findings
from brandwatch.typos import generate_variants


def make_config():
    return BrandConfig(
        name="Microsoft",
        keywords=("microsoft",),
        legitimate_domains=("microsoft.com",),
        ct_queries=("microsoft-login", "microsoft365", "microsoft-support"),
    )


def test_variants_are_deterministic_bounded_and_include_required_edits():
    config = make_config()
    first = generate_variants(config)
    second = generate_variants(config)
    values = {variant.value for variant in first}

    assert first == second
    assert len(first) == 20
    assert len(values) == 20
    assert {"m1crosoft", "micr0soft", "micro5oft", "micros0ft"} <= values
    assert any(variant.rule.startswith("delete:") for variant in first)
    assert any(variant.rule.startswith("swap:") for variant in first)
    assert "microsoft" not in values


def test_variant_candidate_survives_filter_but_official_domain_is_excluded():
    config = make_config()
    assert filter_candidates(
        ["micr0soft-login.example", "login.microsoft.com", "unrelated.example"], config
    ) == {"micr0soft-login.example"}


def test_ct_fixture_tracks_the_variant_that_matched():
    config = make_config()
    findings = parse_ct_findings(
        [{"name_value": "micr0soft-login.example\nlogin.microsoft.com"}],
        config,
        search_term="micr0soft",
    )
    assert len(findings) == 1
    assert findings[0].hostname == "micr0soft-login.example"
    assert findings[0].matched_term == "micr0soft"
    assert findings[0].match_kind == "variant"
    assert findings[0].search_term == "micr0soft"


def test_ct_query_plan_keeps_configured_terms_first_and_caps_external_searches():
    plan = build_ct_query_plan(make_config())
    assert len(plan) == 10
    assert [item.term for item in plan[:3]] == [
        "microsoft-login",
        "microsoft365",
        "microsoft-support",
    ]
    assert all(item.kind == "configured" for item in plan[:3])
    assert all(item.kind == "variant" for item in plan[3:])


def test_literal_keyword_match_does_not_record_substring_variants():
    config = make_config()
    findings = parse_ct_findings(
        [{"name_value": "microsoft-support.example"}],
        config,
        search_term="microsoft-support",
    )
    assert [(item.matched_term, item.match_kind) for item in findings] == [
        ("microsoft", "keyword")
    ]


def test_variant_ct_query_does_not_admit_literal_keyword_noise(monkeypatch):
    from brandwatch.discovery import search_crtsh_findings

    config = make_config()

    def fake_fetch(term, timeout):
        assert timeout == 20
        if term == "micr0soft":
            return [
                {"name_value": "micr0soft-login.example"},
                {"name_value": "microsoft-support.example"},
            ]
        return []

    monkeypatch.setattr("brandwatch.discovery._fetch_crtsh", fake_fetch)
    findings = search_crtsh_findings(config, max_queries=5)
    assert [(item.hostname, item.matched_term) for item in findings] == [
        ("micr0soft-login.example", "micr0soft")
    ]

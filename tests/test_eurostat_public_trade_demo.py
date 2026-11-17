import pytest

from examples.mega_market.eurostat_public_trade_demo import (
    build_request_url,
    parse_sdmx_csv,
)

HEADER = (
    "STRUCTURE,STRUCTURE_ID,STRUCTURE_NAME,ACTION,FREQ,REPORTER,PARTNER,"
    "PRODUCT,FLOW,TIME_PERIOD,INDICATORS,OBS_VALUE,OBS_STATUS,UNIT_MULT\n"
)
ROWS = (
    "data,DS-045409,Trade data,I,A,DE,FR,8703,1,2020,VALUE_IN_EUROS,1200,,0\n"
    "data,DS-045409,Trade data,I,A,DE,FR,1001,1,2021,VALUE_IN_EUROS,1500,,0\n"
)


def test_builds_a_narrow_comext_query():
    url = build_request_url(2020, 2025)
    assert "/DS-045409/A.DE.FR.1001.1.VALUE_IN_EUROS?" in url
    assert "startPeriod=2020" in url
    assert "endPeriod=2025" in url


def test_rejects_reversed_year_range():
    with pytest.raises(ValueError):
        build_request_url(2025, 2020)


def test_normalizes_trade_observation_shape_without_float():
    result = parse_sdmx_csv((HEADER + ROWS).encode(), 2020, 2025)
    assert result["numeric_observation_count"] == 2
    assert result["dimensions"]["reporter"] == "DE"
    assert result["dimensions"]["partner"] == "FR"
    assert result["dimensions"]["flow"] == "imports"
    assert result["observations"][0]["obs_value"] == "1200"
    assert result["observations"][0]["unit_multiplier"] == 0


def test_rejects_a_different_partner_in_response():
    wrong = ROWS.replace(",FR,1001,", ",US,1001,")
    with pytest.raises(ValueError, match="PARTNER"):
        parse_sdmx_csv((HEADER + wrong).encode(), 2020, 2025)


def test_rejects_duplicate_years():
    duplicate = ROWS + ROWS.splitlines(keepends=True)[0]
    with pytest.raises(ValueError, match="duplicate annual observation"):
        parse_sdmx_csv((HEADER + duplicate).encode(), 2020, 2025)


def test_rejects_non_csv_or_error_document():
    with pytest.raises(ValueError, match="Unexpected Eurostat response"):
        parse_sdmx_csv(b"<error>NO_RESULTS</error>", 2020, 2025)


def test_rejects_empty_numeric_result():
    empty_rows = (
        "data,DS-045409,Trade data,I,A,DE,FR,1001,1,2020,VALUE_IN_EUROS,..,,0\n"
    )
    with pytest.raises(ValueError, match="no numeric observations"):
        parse_sdmx_csv((HEADER + empty_rows).encode(), 2020, 2025)


def test_rejects_non_decimal_observation():
    invalid = ROWS.replace(",1200,,0", ",twelve,,0")
    with pytest.raises(ValueError, match="non-decimal"):
        parse_sdmx_csv((HEADER + invalid).encode(), 2020, 2025)

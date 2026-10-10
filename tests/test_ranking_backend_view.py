"""SAPI-61 — COMPONENT: `app.components.ranking_backend_view` (CA3, CA4, CA5).

Renderizado con `st` mockeado (mismo patrón que `tests/test_prototype_freshness.py`)
y mapa Folium real. La integración completa con AppTest vive en
`tests/test_sapi61_http_stub.py`.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import folium
import pytest

from app.components import ranking_backend_view as view_mod
from app.components.ranking_backend_view import (
    FIXED_DISCLAIMER,
    FRESHNESS_HISTORICAL_LABEL,
    NOT_IN_CONTRACT,
    NOT_PROVIDED,
    build_map,
    cell_from_click,
)
from app.utils.backend_client import (
    ERROR_KIND_CONNECTION,
    ERROR_KIND_HTTP_BACKEND,
    BackendError,
    RankingView,
    parse_ranking,
)
from app.utils.reference_topography import (
    REFERENCE_TOPOGRAPHY_CSV,
    CellTopography,
    load_reference_topography,
    reference_topography,
)
from src.geo.grid import all_cells
from tests.test_backend_client import EXTENDED_FIELDS, real_payload

FETCHED_AT = datetime(2026, 10, 10, 15, 30, tzinfo=timezone.utc)


def v0_view() -> RankingView:
    return parse_ranking(real_payload(), fetched_at=FETCHED_AT)


def extended_view(**overrides: object) -> RankingView:
    payload = {**real_payload(), **copy.deepcopy(EXTENDED_FIELDS)}
    payload.update(overrides)
    return parse_ranking(payload, fetched_at=FETCHED_AT)


def _markdown_blob(mock_st: MagicMock) -> str:
    return "\n".join(str(c.args[0]) for c in mock_st.markdown.call_args_list if c.args)


def _mock_expander(mock_st: MagicMock) -> None:
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    mock_st.expander.return_value = ctx


def _rectangles(fmap: folium.Map) -> list[folium.Rectangle]:
    return [c for c in fmap._children.values() if isinstance(c, folium.Rectangle)]


# ── mapa (CA3 mapa, CA5) ─────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ["Prioridades", "Todas las celdas"])
def test_map_has_exactly_50_rectangles_with_authoritative_geometry(mode: str) -> None:
    fmap = build_map(v0_view(), mode, selected_id=None)
    rects = _rectangles(fmap)
    assert len(rects) == 50
    expected = {
        c["cell_id"]: [[c["min_lat"], c["min_lon"]], [c["max_lat"], c["max_lon"]]]
        for c in all_cells()
    }
    seen = set()
    for rect in rects:
        tip_html = next(iter(rect._children.values())).text  # tooltip, hijo del rectángulo
        cell_id = tip_html.split("<b>")[1].split("</b>")[0]
        seen.add(cell_id)
        assert rect.locations == expected[cell_id]
    assert seen == set(expected)


def test_map_tooltip_preserves_score_priority_and_declares_firms_unavailable() -> None:
    fmap = build_map(v0_view(), "Todas las celdas", selected_id=None)
    tips = [next(iter(r._children.values())).text for r in _rectangles(fmap)]
    vp028 = next(t for t in tips if "<b>VP-028</b>" in t)
    assert "Prioridad #49" in vp028
    assert "Score 0.102103" in vp028
    assert f"Historial FIRMS: {NOT_IN_CONTRACT}" in vp028
    assert "Elevación" in vp028 and "(ref.)" in vp028
    assert all("Historial FIRMS: 0" not in t for t in tips)


def test_map_marks_the_selected_cell() -> None:
    fmap = build_map(v0_view(), "Prioridades", selected_id="VP-038")
    selected = [r for r in _rectangles(fmap) if r.options["color"] == view_mod._SELECTED_EDGE]
    assert len(selected) == 1
    assert selected[0].options["weight"] == 3.0


def test_map_priority_mode_highlights_only_the_top_tie_group() -> None:
    fmap = build_map(v0_view(), "Prioridades", selected_id=None)
    strong = [r for r in _rectangles(fmap) if r.options["fillOpacity"] > 0.1]
    assert len(strong) == 7  # empate real de 7 celdas con display_rank 1


def test_map_without_topography_shows_nd_never_zero() -> None:
    fmap = build_map(v0_view(), "Todas las celdas", None, topography={})
    tips = [next(iter(r._children.values())).text for r in _rectangles(fmap)]
    assert all("Elevación N/D" in t and "Pendiente N/D" in t for t in tips)
    assert all("Elevación 0 m" not in t for t in tips)


def test_map_uses_folium_openstreetmap_tiles_without_api_key() -> None:
    fmap = build_map(v0_view(), "Todas las celdas", None)
    tiles = [c for c in fmap._children.values() if isinstance(c, folium.TileLayer)]
    assert tiles and "openstreetmap" in tiles[0].tiles.lower()


# ── selección por click ──────────────────────────────────────────────────────


def test_click_inside_a_cell_resolves_with_the_authoritative_grid() -> None:
    cell = all_cells()[37]  # VP-038
    lat = (cell["min_lat"] + cell["max_lat"]) / 2
    lon = (cell["min_lon"] + cell["max_lon"]) / 2
    assert cell_from_click({"last_clicked": {"lat": lat, "lng": lon}}) == "VP-038"


@pytest.mark.parametrize(
    "event",
    [
        None,
        {},
        {"last_clicked": None},
        {"last_clicked": {"lat": 0.0, "lng": 0.0}},
        {"last_clicked": {"lat": "x", "lng": "y"}},
        {"last_clicked": {"lat": 1}},
        "texto",
    ],
)
def test_click_outside_or_malformed_returns_none(event: object) -> None:
    assert cell_from_click(event) is None


# ── header / frescura (CA3 frescura, anti-invención) ─────────────────────────


@patch("app.components.ranking_backend_view.st")
def test_v0_header_declares_station_and_horizon_without_inventing(mock_st: MagicMock) -> None:
    payload = real_payload()
    del payload["horizon_hours"]
    view_mod._render_header(parse_ranking(payload, fetched_at=FETCHED_AT))
    text = _markdown_blob(mock_st)
    assert "PROTOTIPO EXPLORATORIO" in text and "BACKEND REST" in text
    assert "01 sep 2026" in text
    assert "DATOS HISTÓRICOS" not in text
    assert f"Estación meteorológica: {NOT_PROVIDED}" in text
    assert f"horizonte {NOT_PROVIDED}" in text
    assert "Obtenido del backend: 15:30 UTC" in text
    assert "DMC Rodelillo" not in text


@patch("app.components.ranking_backend_view.st")
def test_v0_header_shows_human_window_when_horizon_present(mock_st: MagicMock) -> None:
    view_mod._render_header(v0_view())
    text = _markdown_blob(mock_st)
    assert "00:00 → 06:00 UTC" in text
    assert "próximas" not in text.lower()


@patch("app.components.ranking_backend_view.st")
def test_v0_freshness_state_is_explicit_pending_not_a_banner(mock_st: MagicMock) -> None:
    view_mod._render_freshness_state(v0_view())
    mock_st.warning.assert_not_called()
    mock_st.info.assert_called_once()
    msg = mock_st.info.call_args[0][0]
    assert "no informada por el backend" in msg
    assert "No se asume que el ranking represente el riesgo actual" in msg
    assert "hace" not in msg  # ninguna antigüedad calculada localmente


@patch("app.components.ranking_backend_view.st")
def test_extended_historical_freshness_renders_banner_and_badge(mock_st: MagicMock) -> None:
    view = extended_view()
    view_mod._render_freshness_state(view)
    mock_st.info.assert_not_called()
    mock_st.warning.assert_called_once()
    banner = mock_st.warning.call_args[0][0]
    assert "DATOS HISTÓRICOS" in banner and "hace 157 h" in banner
    assert "NO representa el riesgo actual" in banner
    view_mod._render_header(view)
    header = _markdown_blob(mock_st)
    assert header.count("DATOS HISTÓRICOS") == 1
    assert "DMC Rodelillo · 330007" in header


@pytest.mark.parametrize("label", ["DATOS RECIENTES", "DATOS CON RETRASO"])
@patch("app.components.ranking_backend_view.st")
def test_extended_non_historical_freshness_has_no_banner(mock_st: MagicMock, label: str) -> None:
    view = extended_view(freshness=label, age_hours=3.0)
    view_mod._render_freshness_state(view)
    mock_st.warning.assert_not_called()
    mock_st.info.assert_not_called()
    view_mod._render_header(view)
    assert "DATOS HISTÓRICOS" not in _markdown_blob(mock_st)


@patch("app.components.ranking_backend_view.st")
def test_partial_freshness_fields_are_not_rendered_as_a_banner(mock_st: MagicMock) -> None:
    payload = real_payload()
    payload["freshness"] = FRESHNESS_HISTORICAL_LABEL  # sin age_hours/weather_timestamp
    view_mod._render_freshness_state(parse_ranking(payload))
    mock_st.warning.assert_not_called()
    mock_st.info.assert_called_once()


# ── KPIs / disclaimer ────────────────────────────────────────────────────────


@patch("app.components.ranking_backend_view.st")
def test_kpi_strip_v0_declares_meteo_unavailable_and_counts_cells(mock_st: MagicMock) -> None:
    view_mod._render_kpi_strip(v0_view())
    text = _markdown_blob(mock_st)
    assert text.count(NOT_PROVIDED) == 4
    assert ">50<" in text and "Celdas evaluadas" in text
    assert "°C" not in text and "km/h" not in text


@patch("app.components.ranking_backend_view.st")
def test_kpi_strip_extended_shows_backend_meteo_verbatim(mock_st: MagicMock) -> None:
    view_mod._render_kpi_strip(extended_view())
    text = _markdown_blob(mock_st)
    assert "18.8 °C" in text and "72 %" in text and "15.7 km/h" in text and "Inactiva" in text
    assert NOT_PROVIDED not in text


@patch("app.components.ranking_backend_view.st")
def test_disclaimer_from_backend_is_escaped_and_rn01_text_kept(mock_st: MagicMock) -> None:
    view = extended_view(disclaimer="<script>alert(1)</script> aviso")
    view_mod._render_disclaimer(view)
    text = _markdown_blob(mock_st)
    assert "<script>" not in text and "&lt;script&gt;" in text
    assert FIXED_DISCLAIMER in text


@patch("app.components.ranking_backend_view.st")
def test_disclaimer_absent_uses_fixed_text_once(mock_st: MagicMock) -> None:
    payload = real_payload()
    del payload["disclaimer"]
    view_mod._render_disclaimer(parse_ranking(payload))
    assert _markdown_blob(mock_st).count(FIXED_DISCLAIMER) == 1


# ── paneles (CA3 ranking/empates, CA5) ───────────────────────────────────────


@patch("app.components.ranking_backend_view.st")
def test_priority_panel_shows_real_tie_group(mock_st: MagicMock) -> None:
    view_mod._render_priority_panel(v0_view())
    text = _markdown_blob(mock_st)
    assert "#1" in text and "<b>7 celdas</b> empatadas" in text
    assert "0.131293" in text
    assert "Empate real del modelo · 7 celdas" in text
    for cid in ("VP-001", "VP-002", "VP-016", "VP-013", "VP-012", "VP-011", "VP-033"):
        assert cid in text


@patch("app.components.ranking_backend_view.st")
def test_selected_panel_v0_territory_from_reference_and_unavailable_states(
    mock_st: MagicMock,
) -> None:
    view_mod._render_selected_panel(v0_view(), "VP-038")
    text = _markdown_blob(mock_st)
    assert "VP-038" in text and "Prioridad #49" in text and "0.102103" in text and "×2" in text
    assert "Territorio (referencia)" in text
    assert "Topografía de referencia" in text
    assert f"Historial FIRMS</span><b>{NOT_IN_CONTRACT}" in text
    assert f"Meteorología usada</span><b>{NOT_PROVIDED}" in text
    assert "T+6h" in text and "01 sep 2026 06:00 UTC" in text
    # VP-038 no tiene cobertura DEM en la tabla congelada: N/D, nunca "0 m".
    assert "Elevación</span><b>N/D" in text and "Sin cobertura DEM" in text
    assert "0 m" not in text


@patch("app.components.ranking_backend_view.st")
def test_selected_panel_covered_cell_shows_reference_topography(mock_st: MagicMock) -> None:
    view_mod._render_selected_panel(v0_view(), "VP-001")
    text = _markdown_blob(mock_st)
    topo = reference_topography()["VP-001"]
    assert topo.dem_available
    assert f"Elevación</span><b>{topo.elevation:.0f} m" in text
    assert f"Pendiente</span><b>{topo.slope:.1f}°" in text
    assert "Sin cobertura DEM" not in text


@patch("app.components.ranking_backend_view.st")
def test_selected_panel_without_dem_coverage_shows_nd(mock_st: MagicMock) -> None:
    topo = {"VP-001": CellTopography("VP-001", None, None, False)}
    view_mod._render_selected_panel(v0_view(), "VP-001", topography=topo)
    text = _markdown_blob(mock_st)
    assert "Elevación</span><b>N/D" in text and "Pendiente</span><b>N/D" in text
    assert "Sin cobertura DEM" in text


@patch("app.components.ranking_backend_view.st")
def test_selected_panel_extended_meteo_and_missing_horizon(mock_st: MagicMock) -> None:
    payload = {**real_payload(), **copy.deepcopy(EXTENDED_FIELDS)}
    del payload["horizon_hours"]
    view_mod._render_selected_panel(parse_ranking(payload), "VP-001")
    text = _markdown_blob(mock_st)
    assert "18.8 °C" in text and "72 %" in text and "15.7 km/h" in text
    assert f"Horizonte</span><b>{NOT_PROVIDED}" in text


@patch("app.components.ranking_backend_view.st")
def test_selected_panel_unknown_cell_warns(mock_st: MagicMock) -> None:
    view_mod._render_selected_panel(v0_view(), "VP-999")
    mock_st.warning.assert_called_once()


@patch("app.components.ranking_backend_view.st")
def test_ranking_expander_table_preserves_order_and_ties(mock_st: MagicMock) -> None:
    _mock_expander(mock_st)
    view_mod._render_ranking_expander(v0_view())
    df = mock_st.dataframe.call_args[0][0]
    assert list(df["Celda"]) == [c["cell_id"] for c in real_payload()["cells"]]
    assert list(df["Prioridad"][:8]) == [1] * 7 + [8]
    assert list(df["Empate"][:1]) == ["×7"] and list(df["Empate"][-2:]) == ["×2", "×2"]


# ── trazabilidad (CA3) ───────────────────────────────────────────────────────


@patch("app.components.ranking_backend_view.st")
def test_tech_expander_v0_traceability_and_pending_fields(mock_st: MagicMock) -> None:
    _mock_expander(mock_st)
    view_mod._render_tech_expander(v0_view())
    text = _markdown_blob(mock_st)
    payload = real_payload()
    assert "GET /api/v1/ranking" in text
    assert payload["inputs_fingerprint"] in text
    assert "prototype_model_d_v1" in text
    assert "2026-09-01 00:00:00 UTC" in text and "2026-09-01 06:00:00 UTC" in text
    assert "sapi-ranking-v0" in text and "relative_rank" in text and "`false`" in text
    assert f"Estación DMC:** {NOT_PROVIDED}" in text
    assert f"Weather timestamp usado:** {NOT_PROVIDED}" in text
    assert f"frescura de la observación:** {NOT_PROVIDED}" in text
    assert f"Procedencia FIRMS:** {NOT_PROVIDED}" in text
    assert "Metadata pendiente de la extensión aditiva" in text
    for name in ("weather_timestamp", "freshness", "age_hours", "station_id", "meteo_actual"):
        assert f"`{name}`" in text
    assert "Dataset hash" not in text  # reemplazado por inputs_fingerprint
    assert "localhost" not in text and "8080" not in text
    assert FIXED_DISCLAIMER in mock_st.caption.call_args[0][0]


@patch("app.components.ranking_backend_view.st")
def test_tech_expander_extended_metadata_rendered_verbatim(mock_st: MagicMock) -> None:
    _mock_expander(mock_st)
    view_mod._render_tech_expander(extended_view())
    text = _markdown_blob(mock_st)
    assert "PROTOTYPE / EXPLORATORY" in text
    assert "Rodelillo 330007" in text
    assert "2026-08-31 23:45:00 UTC" in text
    assert "156.9 h" in text and FRESHNESS_HISTORICAL_LABEL in text
    assert "origen current" in text and "2026-08-30" in text and "lag 2" in text
    assert "FIRMS AL DÍA" in text
    assert "Metadata pendiente" not in text


# ── estado de error (CA4) ────────────────────────────────────────────────────


@patch("app.components.ranking_backend_view.st")
def test_error_state_is_visible_generic_and_without_internals(mock_st: MagicMock) -> None:
    view_mod._render_backend_error(BackendError(ERROR_KIND_CONNECTION, detail="ConnectionError"))
    mock_st.error.assert_called_once()
    text = mock_st.error.call_args[0][0]
    assert "No se pudo obtener el ranking del backend" in text
    assert "No se pudo conectar" in text
    assert "Traceback" not in text and "ConnectionError" not in text
    captions = " ".join(c.args[0] for c in mock_st.caption.call_args_list)
    assert "SAPI_BACKEND_BASE_URL" in captions and "inferencia local" in captions


@patch("app.components.ranking_backend_view.st")
def test_error_state_shows_backend_error_type_and_message(mock_st: MagicMock) -> None:
    exc = BackendError(
        ERROR_KIND_HTTP_BACKEND,
        http_status=503,
        error_type="upstream_unavailable",
        backend_message="El servicio ML no está disponible.",
    )
    view_mod._render_backend_error(exc)
    assert "503" in mock_st.error.call_args[0][0]
    captions = " ".join(c.args[0] for c in mock_st.caption.call_args_list)
    assert "upstream_unavailable" in captions
    assert "El servicio ML no está disponible." in captions


@patch("app.components.ranking_backend_view.st")
def test_dashboard_entry_point_renders_error_state_on_backend_error(mock_st: MagicMock) -> None:
    mock_st.sidebar.button.return_value = False
    with patch.object(view_mod, "_load_ranking", side_effect=BackendError(ERROR_KIND_CONNECTION)):
        view_mod.render_ranking_backend_dashboard()
    mock_st.error.assert_called_once()
    mock_st.columns.assert_not_called()


@patch("app.components.ranking_backend_view.st")
def test_refresh_button_clears_cache_before_loading(mock_st: MagicMock) -> None:
    mock_st.sidebar.button.return_value = True
    with patch.object(view_mod, "refresh_ranking_cache") as clear, patch.object(
        view_mod, "_load_ranking", side_effect=BackendError(ERROR_KIND_CONNECTION)
    ):
        view_mod.render_ranking_backend_dashboard()
    clear.assert_called_once()


# ── topografía de referencia ─────────────────────────────────────────────────


def test_reference_topography_table_covers_the_grid() -> None:
    table = load_reference_topography()
    assert REFERENCE_TOPOGRAPHY_CSV.exists()
    assert set(table) == {c["cell_id"] for c in all_cells()}
    covered = {cid for cid, row in table.items() if row.dem_available}
    uncovered = set(table) - covered
    assert len(covered) == 30 and len(uncovered) == 20  # cobertura real de la tabla Hito 1
    # Celdas sin valor DEM en la tabla congelada: se exponen como N/D (nunca 0).
    assert {"VP-007", "VP-017", "VP-038"} <= uncovered
    assert all(table[cid].elevation is None and table[cid].slope is None for cid in uncovered)
    assert all(table[cid].elevation is not None and table[cid].slope is not None for cid in covered)


def test_reference_topography_missing_or_corrupt_file_degrades_to_empty(tmp_path: Path) -> None:
    assert load_reference_topography(tmp_path / "no_existe.csv") == {}
    broken = tmp_path / "broken.csv"
    broken.write_text("cell_id,elevacion,pendiente,dem_disponible\nVP-001,abc,,False\n,1,2,True\n")
    table = load_reference_topography(broken)
    assert set(table) == {"VP-001"}
    assert table["VP-001"].elevation is None and table["VP-001"].dem_available is False

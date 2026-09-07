"""Renderizado cartográfico Folium del mapa de riesgo.

La capa principal es el **riesgo por celda**: relleno graduado por
probabilidad, para que el riesgo alto se lea de un vistazo. Los focos FIRMS
como mini-marcadores quedaron fuera del render por defecto — mezclaban una
fecha histórica (2024-02-03) con el escenario del dashboard y distraían del
semáforo. La función `add_detection_layer` sigue disponible si hace falta
una vista de referencia aparte.

El basemap es un lienzo gris neutro y no OpenStreetMap: los caminos y usos
de suelo coloreados de OSM competían con el semáforo de riesgo.
"""

from __future__ import annotations

import json
import math
from typing import Optional

import folium
import geopandas as gpd
import pandas as pd
from branca.element import MacroElement, Template

from app.data.firms_detections import EVENT_DATE, load_event_detections
from app.theme import tokens as theme
from app.utils.cell_zones import zone_label_for_cell
from app.utils.grid import CELL_RADIUS_METERS, grid_bounds, grid_center
from app.utils.risk_colors import map_selection_style, risk_color, risk_palette

# Lienzo gris de Esri. Se probó primero "CartoDB positron", que es el neutro
# habitual, pero CARTO pasó a exigir API key y estampa "API KEY REQUIRED"
# sobre cada tile: inservible para una demo. Este servicio no pide clave.
_ESRI_CANVAS = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas"
BASEMAP_TILES = f"{_ESRI_CANVAS}/World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}"
BASEMAP_LABELS = f"{_ESRI_CANVAS}/World_Light_Gray_Reference/MapServer/tile/{{z}}/{{y}}/{{x}}"
BASEMAP_ATTR = "Esri, HERE, Garmin, © OpenStreetMap contributors"
BASEMAP_NAME = "Mapa base"

# Los nombres de lugares van en su propio pane por encima de las celdas. En
# Leaflet los tiles viven siempre debajo de los vectores, así que sin esto la
# capa de riesgo tapa "Quilpué" — la comuna que, junto con Viña del Mar, el
# dashboard afirma cubrir, y el evaluador tiene que poder leer.
LABELS_PANE = "etiquetas"
LABELS_Z_INDEX = 650

RISK_LAYER_NAME = "Riesgo por celda (escenario)"
DETECTION_LAYER_NAME = f"Focos reales {EVENT_DATE} (referencia)"

DETECTION_FILL = theme.DETECTION_FILL
DETECTION_STROKE = theme.DETECTION_STROKE

_RISK_LEGEND_ROWS = (
    ("alto", "Alto", "≥66 % o regla 30-30-30"),
    ("medio", "Medio", "33 % a 66 %"),
    ("bajo", "Bajo", "<33 %"),
)


def _base_map(location: tuple[float, float], zoom: int) -> folium.Map:
    """Mapa con el lienzo neutro y los nombres de lugares por encima."""
    m = folium.Map(location=location, zoom_start=zoom, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles=BASEMAP_TILES,
        attr=BASEMAP_ATTR,
        name=BASEMAP_NAME,
        control=False,
    ).add_to(m)
    folium.map.CustomPane(LABELS_PANE, z_index=LABELS_Z_INDEX).add_to(m)
    folium.TileLayer(
        tiles=BASEMAP_LABELS,
        attr=BASEMAP_ATTR,
        name="Nombres de lugares",
        control=False,
        pane=LABELS_PANE,
    ).add_to(m)
    return m


def _cell_center(geometry) -> tuple[float, float]:
    """Obtiene centro de celda (lat, lon) para marcador circular."""
    if geometry is None or geometry.is_empty:
        return grid_center()
    if geometry.geom_type == "Point":
        return geometry.y, geometry.x
    centroid = geometry.centroid
    return centroid.y, centroid.x


def risk_fill_opacity(probabilidad: float) -> float:
    """Opacidad del relleno según probabilidad.

    Reemplaza el `fill_opacity=0.45` plano anterior, que dejaba una celda al
    10 % y una al 64 % con exactamente el mismo peso visual.
    """
    prob = min(1.0, max(0.0, float(probabilidad)))
    return round(0.18 + 0.50 * prob, 3)


def risk_stroke_weight(probabilidad: float) -> float:
    """Grosor de borde según probabilidad: refuerza la jerarquía del relleno."""
    prob = min(1.0, max(0.0, float(probabilidad)))
    return round(0.8 + 1.7 * prob, 2)


def detection_radius(frp: float, frp_max: float) -> float:
    """Radio en píxeles de un foco según su FRP, en escala logarítmica.

    El FRP del evento va de 0,6 a 324 MW. En escala lineal los focos chicos
    desaparecerían y los grandes taparían el mapa; en logarítmica los tres
    órdenes de magnitud entran en un rango de 2,5 a 8 px.
    """
    if frp_max <= 0 or frp <= 0:
        return 2.5
    escala = math.log10(1 + max(0.0, float(frp))) / math.log10(1 + float(frp_max))
    return round(2.5 + 5.5 * min(1.0, escala), 2)


def build_risk_legend_html() -> str:
    """Contenido de la leyenda con forma + color + umbral por nivel."""
    from app.components.risk_level import risk_shape_svg

    filas = "".join(
        f'<div style="display:flex;align-items:center;gap:6px;margin:2px 0;">'
        f'<span style="width:18px;height:18px;border-radius:3px;'
        f"background:{risk_palette(nivel).surface};display:inline-grid;"
        f'place-items:center;flex:none;">'
        f"{risk_shape_svg(nivel, fill=risk_palette(nivel).on_solid, size=12)}"
        f"</span>"
        f'<span style="font-weight:600;">{etiqueta}</span>'
        f'<span style="opacity:0.7;">{detalle}</span>'
        f"</div>"
        for nivel, etiqueta, detalle in _RISK_LEGEND_ROWS
    )
    micro = theme.TYPE_SCALE["micro"]
    return (
        f'<div style="background:rgba(255,255,255,0.94);'
        f"border:1px solid {theme.BORDER_SUBTLE};"
        f'border-radius:{theme.RADIUS_PX["card"]}px;padding:8px 10px;'
        f"font-size:{micro.size_px}px;line-height:1.35;"
        f'color:{theme.TEXT_PRIMARY};box-shadow:0 1px 4px rgba(0,0,0,0.16);">'
        '<div style="font-weight:700;margin-bottom:4px;">Probabilidad de ignición</div>'
        f"{filas}"
        "</div>"
    )


class RiskLegend(MacroElement):
    """Leyenda como control nativo de Leaflet, anclada abajo a la derecha.

    Se probó primero un div suelto con `position: fixed`. Funciona en el HTML
    del mapa abierto solo, pero dentro del iframe que monta `st_folium` no se
    ancla y la leyenda desaparece. Un `L.control` se posiciona contra el
    contenedor del mapa, así que da igual dónde esté embebido.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        var {{ this.get_name() }} = L.control({position: 'bottomright'});
        {{ this.get_name() }}.onAdd = function (map) {
            var div = L.DomUtil.create('div', 'sapi-risk-legend');
            div.innerHTML = {{ this.contenido }};
            L.DomEvent.disableClickPropagation(div);
            return div;
        };
        {{ this.get_name() }}.addTo({{ this._parent.get_name() }});
        {% endmacro %}
        """
    )

    def __init__(self) -> None:
        super().__init__()
        self._name = "RiskLegend"
        self.contenido = json.dumps(build_risk_legend_html())


def add_detection_layer(m: folium.Map, detections: Optional[pd.DataFrame] = None) -> bool:
    """Agrega la capa de focos reales. Devuelve False si no hay datos.

    Si el asset no está, la capa simplemente no se dibuja: el mapa de riesgo
    no depende de ella.
    """
    focos = load_event_detections() if detections is None else detections
    if focos is None or focos.empty:
        return False

    frp_max = float(focos["frp"].max())
    capa = folium.FeatureGroup(name=DETECTION_LAYER_NAME, show=True)
    for foco in focos.itertuples():
        frp = float(foco.frp)
        folium.CircleMarker(
            location=[float(foco.latitude), float(foco.longitude)],
            radius=detection_radius(frp, frp_max),
            color=DETECTION_STROKE,
            weight=0.8,
            fill=True,
            fill_color=DETECTION_FILL,
            fill_opacity=0.85,
            tooltip=f"Foco {EVENT_DATE} · FRP {frp:.1f} MW",
        ).add_to(capa)
    capa.add_to(m)
    return True


def render_folium_map(
    gdf: gpd.GeoDataFrame,
    center: Optional[tuple[float, float]] = None,
    zoom: int = 11,
    selected_cell_id: Optional[str] = None,
    show_detections: bool = False,
) -> folium.Map:
    """Renderiza el mapa de riesgo del corredor.

    Args:
        gdf: GeoDataFrame con geometrías, probabilidad y nivel_riesgo.
        center: Centro explícito (lat, lon). Si es None, encuadra la grilla.
        zoom: Zoom inicial, usado solo cuando se pasa un centro explícito.
        selected_cell_id: Celda a resaltar.
        show_detections: Si True, agrega focos FIRMS históricos (apagado por
            defecto: no pertenecen al escenario del día consultado).

    Returns:
        Mapa Folium configurado.
    """
    if gdf.empty:
        fallback = grid_center()
        m = _base_map(fallback, zoom)
        folium.Marker(
            list(fallback),
            popup="Sin datos de riesgo disponibles",
            icon=folium.Icon(color="gray"),
        ).add_to(m)
        return m

    m = _base_map(center if center is not None else grid_center(), zoom)
    if center is None:
        # Encuadrar la grilla en vez de fijar un zoom: con 34,5 km de ancho un
        # zoom fijo recorta el corredor en pantallas angostas.
        lon_min, lon_max, lat_min, lat_max = grid_bounds()
        m.fit_bounds([[lat_min, lon_min], [lat_max, lon_max]], padding=(12, 12))

    capa_riesgo = folium.FeatureGroup(name=RISK_LAYER_NAME, show=True)
    for _, row in gdf.iterrows():
        cell_id = str(row.get("cell_id", ""))
        nivel = str(row.get("nivel_riesgo", "bajo"))
        color = risk_color(nivel)
        prob = float(row.get("probabilidad", 0))
        lat, lon = _cell_center(row.geometry)
        zona = zone_label_for_cell(cell_id)
        is_selected = selected_cell_id is not None and cell_id == selected_cell_id
        sel = map_selection_style(nivel, color) if is_selected else None
        popup_html = (
            f"<b>Celda:</b> {cell_id or 'N/A'}<br>"
            f"<b>Zona climática:</b> {zona}<br>"
            f"<b>Probabilidad:</b> {prob:.2%}<br>"
            f"<b>Nivel:</b> {nivel}<br>"
            f"<b>Temperatura:</b> {row.get('temperatura', 'N/A')} °C<br>"
            f"<b>Humedad:</b> {row.get('humedad_relativa', 'N/A')} %<br>"
            f"<b>Viento:</b> {row.get('velocidad_viento', 'N/A')} km/h<br>"
            f"<b>Regla 30-30-30:</b> {'Activa' if row.get('regla_30_30_30') else 'Inactiva'}"
        )
        folium.Circle(
            location=[lat, lon],
            radius=CELL_RADIUS_METERS,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=cell_id,
            color=sel["stroke"] if sel else color,
            fill=True,
            fill_color=color,
            fill_opacity=sel["fill_opacity"] if sel else risk_fill_opacity(prob),
            weight=sel["weight"] if sel else risk_stroke_weight(prob),
        ).add_to(capa_riesgo)
        if sel:
            # Solo la celda seleccionada lleva marcador central. Antes lo
            # llevaban las 50, y ese punteado uniforme era buena parte de lo
            # que hacía ver el mapa como una retícula sintética.
            folium.CircleMarker(
                location=[lat, lon],
                radius=sel["marker_radius"],
                color=sel["marker_color"],
                fill=True,
                fill_color=sel["marker_color"],
                fill_opacity=0.95,
                tooltip=cell_id,
                popup=folium.Popup(f"<b>{cell_id}</b>", max_width=120),
            ).add_to(capa_riesgo)
    capa_riesgo.add_to(m)

    if show_detections:
        add_detection_layer(m)

    RiskLegend().add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)

    return m

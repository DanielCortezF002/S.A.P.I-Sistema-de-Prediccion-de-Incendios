package cl.sapi.backend.ranking.persistence;

import java.util.List;

/**
 * Ranking completo de una ejecución persistida: metadatos + exactamente 50 celdas.
 *
 * @param execution metadatos de {@code ejecuciones}
 * @param cells predicciones ordenadas por {@code rank} ascendente
 */
public record PersistedRanking(ExecutionRecord execution, List<CellPredictionRow> cells) {
}

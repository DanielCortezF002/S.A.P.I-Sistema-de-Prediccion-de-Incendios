package cl.sapi.backend.ranking.persistence;

/**
 * Una fila de {@code predicciones_celda} (ranking relativo de una celda).
 *
 * @param cellId identificador {@code VP-NNN}
 * @param score score relativo en {@code [0, 1]} (no probabilidad calibrada)
 * @param rank posición única 1..50
 * @param displayRank método min
 * @param tieGroupSize tamaño del grupo de empate
 */
public record CellPredictionRow(
        String cellId,
        double score,
        int rank,
        int displayRank,
        int tieGroupSize) {
}

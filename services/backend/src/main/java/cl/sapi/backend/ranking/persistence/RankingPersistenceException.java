package cl.sapi.backend.ranking.persistence;

/**
 * Fallo al persistir o leer un ranking en PostgreSQL/PostGIS (SAPI-59).
 *
 * <p>Es unchecked para que el write-through de {@code RankingService} responda 500
 * (fail-closed, ADR-007) sin filtrar detalles de la base al cliente.
 */
public class RankingPersistenceException extends RuntimeException {

    public RankingPersistenceException(String message) {
        super(message);
    }

    public RankingPersistenceException(String message, Throwable cause) {
        super(message, cause);
    }
}

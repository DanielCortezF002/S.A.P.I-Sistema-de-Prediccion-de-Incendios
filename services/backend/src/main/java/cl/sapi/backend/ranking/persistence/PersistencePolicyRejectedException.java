package cl.sapi.backend.ranking.persistence;

/**
 * Rechazo de persistencia por política de procedencia (SAPI F1, D2-B): un replay contra una
 * fila existente con {@code firms_origin} legacy ({@code NULL}, anterior a V004) nunca se
 * actualiza, infiere ni borra. Subtipo de {@link RankingPersistenceException} para que
 * {@code RankingService} lo mapee igual (500 {@code internal_error}, fail-closed).
 */
public class PersistencePolicyRejectedException extends RankingPersistenceException {

    public PersistencePolicyRejectedException(String message) {
        super(message);
    }
}

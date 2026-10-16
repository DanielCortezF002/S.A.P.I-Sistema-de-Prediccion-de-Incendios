package cl.sapi.backend.ranking.persistence;

import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

import org.jspecify.annotations.Nullable;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import tools.jackson.databind.JsonNode;

/**
 * Persistencia write-through del ranking validado (SAPI-59) sobre el esquema v2.
 *
 * <p>Idempotencia por clave natural {@code (forecast_time, model_version, inputs_fingerprint)}:
 * {@code INSERT … ON CONFLICT DO NOTHING}, luego inserción de exactamente 50 filas o reutilización
 * de las ya existentes. No recalcula scores ni reordena celdas. No toca {@code celdas_geom}.
 * En replay, la metadata de {@code ejecuciones} (salvo {@code id}/{@code created_at}) debe coincidir;
 * nunca se sobrescribe.
 *
 * <p>Activación por {@code sapi.persistence.enabled} (true por defecto); no usa
 * {@code @ConditionalOnBean(JdbcTemplate)} porque se evalúa antes del auto-config JDBC.
 */
@Service
@ConditionalOnProperty(prefix = "sapi.persistence", name = "enabled", havingValue = "true", matchIfMissing = true)
public class RankingPersistenceService {

    private final RankingRepository repository;
    private final FirmsOriginPolicy firmsOriginPolicy;

    public RankingPersistenceService(RankingRepository repository, FirmsOriginPolicy firmsOriginPolicy) {
        this.repository = repository;
        this.firmsOriginPolicy = firmsOriginPolicy;
    }

    /**
     * Variante sin JDBC para tests surefire que excluyen DataSource (no persiste nada).
     *
     * @return servicio que ignora {@link #persist(JsonNode)} y no encuentra rankings
     */
    public static RankingPersistenceService noOp() {
        return new NoOpRankingPersistenceService();
    }

    /**
     * Persiste un {@code RankingResult} ya validado por {@code RankingResultValidator}.
     *
     * @param ranking árbol JSON validado (no se modifica)
     * @return el {@code id} de la ejecución (nueva o ya existente)
     */
    @Transactional
    public long persist(JsonNode ranking) {
        Objects.requireNonNull(ranking, "ranking");
        OffsetDateTime forecastTime = parseForecastTime(ranking.get("forecast_time").stringValue());
        String modelVersion = ranking.get("model_version").stringValue();
        String fingerprint = ranking.get("inputs_fingerprint").stringValue();
        String schemaVersion = ranking.get("schema_version").stringValue();
        String scoreSemantics = ranking.get("score_semantics").stringValue();
        boolean scientificValidation = ranking.get("scientific_model_validation").booleanValue();
        Integer horizonHours = horizonHours(ranking);
        String firmsOrigin = firmsOrigin(ranking);
        // A3 completo (Astra P1-01): el mismo bean de política se consulta aquí también, antes
        // de tocar el repositorio -- no solo en RankingService. Una llamada directa a persist()
        // (bypaseando el gate HTTP) con un origen ausente o fuera de la política efectiva
        // (p. ej. "baseline"/"reproducibility" cuando la política vigente es solo "current")
        // se rechaza igual, sin inserciones parciales.
        if (!firmsOriginPolicy.isAllowed(firmsOrigin)) {
            throw new PersistencePolicyRejectedException(
                    "firms_origin " + (firmsOrigin == null ? "ausente" : "\"" + firmsOrigin + "\"")
                            + " no autorizado por la política efectiva de persistencia; rechazado antes de "
                            + "acceder al repositorio (A3)");
        }
        List<CellPredictionRow> cells = extractCells(ranking.get("cells"));

        try {
            Optional<Long> inserted = repository.insertExecution(
                    forecastTime, modelVersion, fingerprint, schemaVersion,
                    scoreSemantics, scientificValidation, horizonHours, firmsOrigin);
            long executionId;
            if (inserted.isPresent()) {
                executionId = inserted.get();
            }
            else {
                executionId = repository
                        .findExecutionId(forecastTime, modelVersion, fingerprint)
                        .orElseThrow(() -> new RankingPersistenceException(
                                "conflicto de clave natural sin fila de ejecuciones visible"));
                ExecutionRecord stored = repository.findExecutionById(executionId)
                        .orElseThrow(() -> new RankingPersistenceException(
                                "ejecución existente no legible tras conflicto de clave natural"));
                if (stored.firmsOrigin() == null) {
                    // D2-B (Jira #10134): fila legacy (anterior a V004). El replay se rechaza
                    // tal cual; nunca se actualiza, infiere ni borra.
                    throw new PersistencePolicyRejectedException(
                            "replay contra ejecución " + executionId
                                    + " con firms_origin legacy (NULL); rechazado por política D2-B");
                }
                assertSameExecutionMetadata(
                        stored, forecastTime, modelVersion, fingerprint, schemaVersion,
                        scoreSemantics, scientificValidation, horizonHours, firmsOrigin);
            }

            int existing = repository.countPredictions(executionId);
            if (existing == 0) {
                repository.insertPredictions(executionId, forecastTime, cells);
            }
            else if (existing == RankingRepository.CELL_COUNT) {
                assertSamePredictions(executionId, cells);
            }
            else {
                throw new RankingPersistenceException(
                        "ejecución " + executionId + " tiene " + existing
                                + " predicciones; se esperaban 0 o " + RankingRepository.CELL_COUNT);
            }
            return executionId;
        }
        catch (RankingPersistenceException ex) {
            throw ex;
        }
        catch (RuntimeException ex) {
            throw new RankingPersistenceException("no se pudo persistir el ranking", ex);
        }
    }

    /**
     * Recupera el ranking completo de la última ejecución persistida.
     *
     * <p>Definición aprobada: {@code ORDER BY created_at DESC, id DESC}. No usa
     * {@code forecast_time} como criterio de "última".
     */
    @Transactional(readOnly = true)
    public Optional<PersistedRanking> findLatestRanking() {
        try {
            Optional<ExecutionRecord> execution = repository.findLatestExecution();
            if (execution.isEmpty()) {
                return Optional.empty();
            }
            List<CellPredictionRow> cells = repository.findPredictionsByExecutionId(execution.get().id());
            if (cells.size() != RankingRepository.CELL_COUNT) {
                throw new RankingPersistenceException(
                        "la última ejecución " + execution.get().id() + " no tiene "
                                + RankingRepository.CELL_COUNT + " predicciones");
            }
            return Optional.of(new PersistedRanking(execution.get(), List.copyOf(cells)));
        }
        catch (RankingPersistenceException ex) {
            throw ex;
        }
        catch (RuntimeException ex) {
            throw new RankingPersistenceException("no se pudo leer el último ranking", ex);
        }
    }

    /** Cuenta filas en {@code celdas_geom} (CA2; no modifica geometrías). */
    @Transactional(readOnly = true)
    public int countCeldasGeom() {
        return repository.countCeldasGeom();
    }

    /** Cuenta geometrías válidas en SRID 4326 (CA2). */
    @Transactional(readOnly = true)
    public int countValidCeldasGeomSrid4326() {
        return repository.countValidCeldasGeomSrid4326();
    }

    /**
     * Compara metadata de {@code ejecuciones} con el ranking entrante (sin id/created_at).
     * {@code forecast_time} se compara por instante UTC, no por texto de offset.
     */
    private static void assertSameExecutionMetadata(
            ExecutionRecord stored,
            OffsetDateTime forecastTime,
            String modelVersion,
            String fingerprint,
            String schemaVersion,
            String scoreSemantics,
            boolean scientificValidation,
            @Nullable Integer horizonHours,
            @Nullable String firmsOrigin) {
        boolean same = stored.forecastTime().toInstant().equals(forecastTime.toInstant())
                && stored.modelVersion().equals(modelVersion)
                && stored.inputsFingerprint().equals(fingerprint)
                && stored.schemaVersion().equals(schemaVersion)
                && stored.scoreSemantics().equals(scoreSemantics)
                && stored.scientificModelValidation() == scientificValidation
                && Objects.equals(stored.horizonHours(), horizonHours)
                && Objects.equals(stored.firmsOrigin(), firmsOrigin);
        if (!same) {
            throw new RankingPersistenceException(
                    "idempotencia: metadata de ejecución divergente; no se sobrescribe");
        }
    }

    private void assertSamePredictions(long executionId, List<CellPredictionRow> expected) {
        List<CellPredictionRow> stored = repository.findPredictionsByExecutionId(executionId);
        if (stored.size() != expected.size()) {
            throw new RankingPersistenceException(
                    "idempotencia: ejecución " + executionId + " tiene predicciones incompletas");
        }
        for (int i = 0; i < expected.size(); i++) {
            CellPredictionRow want = expected.get(i);
            CellPredictionRow have = stored.get(i);
            if (!want.cellId().equals(have.cellId())
                    || Double.compare(want.score(), have.score()) != 0
                    || want.rank() != have.rank()
                    || want.displayRank() != have.displayRank()
                    || want.tieGroupSize() != have.tieGroupSize()) {
                throw new RankingPersistenceException(
                        "idempotencia: ejecución " + executionId
                                + " ya existe con predicciones distintas; no se sobrescribe");
            }
        }
    }

    private static List<CellPredictionRow> extractCells(JsonNode cells) {
        if (cells == null || !cells.isArray() || cells.size() != RankingRepository.CELL_COUNT) {
            throw new RankingPersistenceException(
                    "cells debe ser un arreglo de " + RankingRepository.CELL_COUNT + " elementos");
        }
        List<CellPredictionRow> rows = new ArrayList<>(RankingRepository.CELL_COUNT);
        for (int i = 0; i < cells.size(); i++) {
            JsonNode cell = cells.get(i);
            rows.add(new CellPredictionRow(
                    cell.get("cell_id").stringValue(),
                    cell.get("score").doubleValue(),
                    cell.get("rank").intValue(),
                    cell.get("display_rank").intValue(),
                    cell.get("tie_group_size").intValue()));
        }
        return List.copyOf(rows);
    }

    private static OffsetDateTime parseForecastTime(String value) {
        try {
            return OffsetDateTime.parse(value);
        }
        catch (DateTimeParseException ex) {
            throw new RankingPersistenceException("forecast_time no es OffsetDateTime: " + value, ex);
        }
    }

    /**
     * Lee {@code firms_origin} tal cual llega, sin inferirlo (IA-P1-01); null si está ausente
     * o es JSON null. La validación de que esté en el contrato/política corre antes, en
     * {@code RankingResultValidator} y el gate de {@code RankingService}.
     */
    static @Nullable String firmsOrigin(JsonNode ranking) {
        JsonNode node = ranking.get("firms_origin");
        return node == null || node.isNull() ? null : node.stringValue();
    }

    /**
     * Lee {@code horizon_hours} como {@code Integer} positivo exacto, o null si ausente.
     * Rechaza valores que no caben en {@code int} (sin truncar con {@code intValue()}).
     */
    static @Nullable Integer horizonHours(JsonNode ranking) {
        if (!ranking.has("horizon_hours") || ranking.get("horizon_hours").isNull()) {
            return null;
        }
        JsonNode node = ranking.get("horizon_hours");
        if (!node.isIntegralNumber() || !node.canConvertToInt()) {
            throw new RankingPersistenceException("horizon_hours fuera del rango int positivo");
        }
        int value = node.intValue();
        if (value < 1) {
            throw new RankingPersistenceException("horizon_hours fuera del rango int positivo");
        }
        return value;
    }

    /** Implementación que no escribe ni lee; solo para surefire sin DataSource. */
    private static final class NoOpRankingPersistenceService extends RankingPersistenceService {

        private NoOpRankingPersistenceService() {
            super(null, null);
        }

        @Override
        public long persist(JsonNode ranking) {
            Objects.requireNonNull(ranking, "ranking");
            return -1L;
        }

        @Override
        public Optional<PersistedRanking> findLatestRanking() {
            return Optional.empty();
        }

        @Override
        public int countCeldasGeom() {
            return 0;
        }

        @Override
        public int countValidCeldasGeomSrid4326() {
            return 0;
        }
    }
}

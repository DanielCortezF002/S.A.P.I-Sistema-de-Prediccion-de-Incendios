package cl.sapi.backend.ranking.persistence;

import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

import org.jspecify.annotations.Nullable;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

/**
 * Acceso JDBC al esquema v2 ({@code ejecuciones}, {@code predicciones_celda}, {@code celdas_geom}).
 *
 * <p>No inserta ni actualiza geometrías: {@code celdas_geom} queda a cargo de V003.
 */
@Repository
@ConditionalOnBean(JdbcTemplate.class)
public class RankingRepository {

    static final int CELL_COUNT = 50;

    private static final String INSERT_EJECUCION = """
            INSERT INTO ejecuciones (
                forecast_time, model_version, inputs_fingerprint, schema_version,
                score_semantics, scientific_model_validation, horizon_hours)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (forecast_time, model_version, inputs_fingerprint) DO NOTHING
            RETURNING id
            """;

    private static final String SELECT_EJECUCION_ID = """
            SELECT id FROM ejecuciones
            WHERE forecast_time = ? AND model_version = ? AND inputs_fingerprint = ?
            """;

    private static final String SELECT_EJECUCION_BY_ID = """
            SELECT id, forecast_time, model_version, inputs_fingerprint, schema_version,
                   score_semantics, scientific_model_validation, horizon_hours, created_at
            FROM ejecuciones
            WHERE id = ?
            """;

    private static final String SELECT_LATEST_EJECUCION = """
            SELECT id, forecast_time, model_version, inputs_fingerprint, schema_version,
                   score_semantics, scientific_model_validation, horizon_hours, created_at
            FROM ejecuciones
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """;

    private static final String COUNT_PREDICCIONES =
            "SELECT COUNT(*) FROM predicciones_celda WHERE ejecucion_id = ?";

    private static final String INSERT_PREDICCION = """
            INSERT INTO predicciones_celda (
                ejecucion_id, forecast_time, cell_id, score, rank, display_rank, tie_group_size)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """;

    private static final String SELECT_PREDICCIONES = """
            SELECT cell_id, score, rank, display_rank, tie_group_size
            FROM predicciones_celda
            WHERE ejecucion_id = ?
            ORDER BY rank ASC
            """;

    private static final String COUNT_CELDAS = "SELECT COUNT(*) FROM celdas_geom";

    private static final String COUNT_CELDAS_VALIDAS = """
            SELECT COUNT(*) FROM celdas_geom
            WHERE ST_SRID(geom) = 4326 AND ST_IsValid(geom)
            """;

    private static final RowMapper<ExecutionRecord> EXECUTION_MAPPER = (rs, rowNum) -> mapExecution(rs);

    private static final RowMapper<CellPredictionRow> CELL_MAPPER = (rs, rowNum) -> new CellPredictionRow(
            rs.getString("cell_id"),
            rs.getDouble("score"),
            rs.getInt("rank"),
            rs.getInt("display_rank"),
            rs.getInt("tie_group_size"));

    private final JdbcTemplate jdbc;

    public RankingRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /**
     * Inserta una ejecución; si la clave natural ya existe, no hace nada.
     *
     * @return el {@code id} si se insertó una fila nueva; vacío si hubo conflicto
     */
    public Optional<Long> insertExecution(
            OffsetDateTime forecastTime,
            String modelVersion,
            String inputsFingerprint,
            String schemaVersion,
            String scoreSemantics,
            boolean scientificModelValidation,
            @Nullable Integer horizonHours) {
        List<Long> ids = jdbc.query(INSERT_EJECUCION, (rs, rowNum) -> rs.getLong(1),
                Timestamp.from(forecastTime.toInstant()),
                modelVersion,
                inputsFingerprint,
                schemaVersion,
                scoreSemantics,
                scientificModelValidation,
                horizonHours);
        return ids.stream().findFirst();
    }

    /** Resuelve el {@code id} de una ejecución por su clave natural. */
    public Optional<Long> findExecutionId(
            OffsetDateTime forecastTime, String modelVersion, String inputsFingerprint) {
        List<Long> ids = jdbc.query(SELECT_EJECUCION_ID, (rs, rowNum) -> rs.getLong(1),
                Timestamp.from(forecastTime.toInstant()), modelVersion, inputsFingerprint);
        return ids.stream().findFirst();
    }

    public Optional<ExecutionRecord> findExecutionById(long id) {
        List<ExecutionRecord> rows = jdbc.query(SELECT_EJECUCION_BY_ID, EXECUTION_MAPPER, id);
        return rows.stream().findFirst();
    }

    /**
     * Última ejecución persistida: {@code ORDER BY created_at DESC, id DESC}.
     *
     * <p>{@code created_at} es el instante de persistencia; {@code forecast_time} es el instante
     * evaluado por el modelo (no define "última ejecución").
     */
    public Optional<ExecutionRecord> findLatestExecution() {
        List<ExecutionRecord> rows = jdbc.query(SELECT_LATEST_EJECUCION, EXECUTION_MAPPER);
        return rows.stream().findFirst();
    }

    public int countPredictions(long executionId) {
        Integer count = jdbc.queryForObject(COUNT_PREDICCIONES, Integer.class, executionId);
        return count == null ? 0 : count;
    }

    /** Inserta las 50 predicciones de una ejecución en lote. */
    public void insertPredictions(long executionId, OffsetDateTime forecastTime, List<CellPredictionRow> cells) {
        if (cells.size() != CELL_COUNT) {
            throw new RankingPersistenceException(
                    "se esperaban " + CELL_COUNT + " celdas y se recibieron " + cells.size());
        }
        Timestamp forecastTs = Timestamp.from(forecastTime.toInstant());
        jdbc.batchUpdate(INSERT_PREDICCION, cells, cells.size(), (PreparedStatement ps, CellPredictionRow cell) -> {
            ps.setLong(1, executionId);
            ps.setTimestamp(2, forecastTs);
            ps.setString(3, cell.cellId());
            ps.setDouble(4, cell.score());
            ps.setInt(5, cell.rank());
            ps.setInt(6, cell.displayRank());
            ps.setInt(7, cell.tieGroupSize());
        });
    }

    public List<CellPredictionRow> findPredictionsByExecutionId(long executionId) {
        return jdbc.query(SELECT_PREDICCIONES, CELL_MAPPER, executionId);
    }

    public int countCeldasGeom() {
        Integer count = jdbc.queryForObject(COUNT_CELDAS, Integer.class);
        return count == null ? 0 : count;
    }

    public int countValidCeldasGeomSrid4326() {
        Integer count = jdbc.queryForObject(COUNT_CELDAS_VALIDAS, Integer.class);
        return count == null ? 0 : count;
    }

    private static ExecutionRecord mapExecution(ResultSet rs) throws SQLException {
        Integer horizon = (Integer) rs.getObject("horizon_hours");
        return new ExecutionRecord(
                rs.getLong("id"),
                toOffsetDateTime(rs.getTimestamp("forecast_time")),
                rs.getString("model_version"),
                rs.getString("inputs_fingerprint"),
                rs.getString("schema_version"),
                rs.getString("score_semantics"),
                rs.getBoolean("scientific_model_validation"),
                horizon,
                toOffsetDateTime(rs.getTimestamp("created_at")));
    }

    private static OffsetDateTime toOffsetDateTime(Timestamp timestamp) {
        return timestamp.toInstant().atOffset(ZoneOffset.UTC);
    }
}

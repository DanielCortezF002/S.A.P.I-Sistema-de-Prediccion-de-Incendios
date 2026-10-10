package cl.sapi.backend.ranking.persistence;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

import cl.sapi.backend.ranking.RankingResultValidator;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/**
 * ITs reales SAPI-59 (CA1–CA5) con Testcontainers PostgreSQL/PostGIS y Flyway V001–V003.
 *
 * <p>Ejecutar en Omen: {@code ./mvnw -B -pl services/backend verify} (failsafe / backend-it).
 * En Cursor sin Docker: no declarar PASS; surefire los excluye ({@code *IT.java}).
 */
@SpringBootTest
@ActiveProfiles("it")
@Testcontainers(disabledWithoutDocker = true)
class RankingPersistenceIT {

    private static final DockerImageName POSTGIS =
            DockerImageName.parse("postgis/postgis:15-3.4").asCompatibleSubstituteFor("postgres");

    @Container
    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer(POSTGIS)
            .withDatabaseName("sapi")
            .withUsername("sapi")
            .withPassword("sapi");

    @DynamicPropertySource
    static void datasource(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        Path migrations = Path.of("..", "..", "db", "migration").toAbsolutePath().normalize();
        registry.add("spring.flyway.locations", () -> "filesystem:" + migrations);
        registry.add("sapi.ml.base-url", () -> "http://127.0.0.1:9");
    }

    @Autowired
    private RankingPersistenceService persistence;

    @Autowired
    private JdbcTemplate jdbc;

    private JsonNode ranking;

    @BeforeEach
    void loadRanking() {
        RankingResultValidator.Validation validation = RankingResultValidator.validate(realRankingBytes());
        assertThat(validation.violation()).isEmpty();
        ranking = validation.ranking();
        jdbc.update("DELETE FROM predicciones_celda");
        jdbc.update("DELETE FROM ejecuciones");
    }

    @Test
    @DisplayName("SAPI-59.CA1 — metadata + exactamente 50 predicciones_celda y created_at de BD")
    void ca1PersistsMetadataAndFiftyScores() {
        long id = persistence.persist(ranking);

        Integer executions = jdbc.queryForObject("SELECT COUNT(*) FROM ejecuciones", Integer.class);
        Integer predictions = jdbc.queryForObject(
                "SELECT COUNT(*) FROM predicciones_celda WHERE ejecucion_id = ?", Integer.class, id);
        assertThat(executions).isEqualTo(1);
        assertThat(predictions).isEqualTo(50);

        ExecutionRecord stored = jdbc.queryForObject("""
                SELECT id, forecast_time, model_version, inputs_fingerprint, schema_version,
                       score_semantics, scientific_model_validation, horizon_hours, created_at
                FROM ejecuciones WHERE id = ?
                """, (rs, rowNum) -> new ExecutionRecord(
                rs.getLong("id"),
                rs.getTimestamp("forecast_time").toInstant().atOffset(java.time.ZoneOffset.UTC),
                rs.getString("model_version"),
                rs.getString("inputs_fingerprint"),
                rs.getString("schema_version"),
                rs.getString("score_semantics"),
                rs.getBoolean("scientific_model_validation"),
                (Integer) rs.getObject("horizon_hours"),
                rs.getTimestamp("created_at").toInstant().atOffset(java.time.ZoneOffset.UTC)), id);

        assertThat(stored).isNotNull();
        assertThat(stored.modelVersion()).isEqualTo(ranking.get("model_version").stringValue());
        assertThat(stored.createdAt()).isNotNull();
        assertThat(stored.scientificModelValidation()).isFalse();
        assertThat(stored.scoreSemantics()).isEqualTo("relative_rank");
    }

    @Test
    @DisplayName("SAPI-59.CA2 — 50 geometrías SRID 4326 válidas; persistir no las modifica")
    void ca2GeometriesPreserved() {
        assertThat(persistence.countCeldasGeom()).isEqualTo(50);
        assertThat(persistence.countValidCeldasGeomSrid4326()).isEqualTo(50);

        String fingerprintBefore = jdbc.queryForObject(
                "SELECT md5(string_agg(ST_AsEWKT(geom), ',' ORDER BY cell_id)) FROM celdas_geom",
                String.class);

        persistence.persist(ranking);

        String fingerprintAfter = jdbc.queryForObject(
                "SELECT md5(string_agg(ST_AsEWKT(geom), ',' ORDER BY cell_id)) FROM celdas_geom",
                String.class);
        assertThat(fingerprintAfter).isEqualTo(fingerprintBefore);
        assertThat(persistence.countCeldasGeom()).isEqualTo(50);
        Integer prediccionesGeomWrites = jdbc.queryForObject(
                "SELECT COUNT(*) FROM predicciones_celda", Integer.class);
        assertThat(prediccionesGeomWrites).isEqualTo(50);
    }

    @Test
    @DisplayName("SAPI-59.CA3 — latest = created_at DESC, id DESC; max de 10 lecturas medidas < 1000 ms")
    void ca3LatestByCreatedAt() {
        long older = persistence.persist(ranking);

        ObjectNode newerNode = (ObjectNode) ranking.deepCopy();
        newerNode.put("forecast_time", "2026-08-01T00:00:00Z");
        newerNode.put("inputs_fingerprint", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb");
        long newer = persistence.persist(newerNode);
        assertThat(newer).isNotEqualTo(older);

        // Fuerza created_at del "más reciente por forecast_time" a ser más antiguo.
        jdbc.update("UPDATE ejecuciones SET created_at = now() - interval '1 hour' WHERE id = ?", newer);
        jdbc.update("UPDATE ejecuciones SET created_at = now() WHERE id = ?", older);

        // Warm-up: fuera de la ventana oficial (no incluye Docker/Flyway/fixtures/INSERTs).
        for (int i = 0; i < 2; i++) {
            assertLatestRanking(persistence.findLatestRanking(), older);
        }

        long[] samplesMs = new long[10];
        for (int i = 0; i < samplesMs.length; i++) {
            long startNs = System.nanoTime();
            Optional<PersistedRanking> latest = persistence.findLatestRanking();
            long elapsedNs = System.nanoTime() - startNs;
            samplesMs[i] = elapsedNs / 1_000_000L;
            assertLatestRanking(latest, older);
        }

        long[] sorted = Arrays.copyOf(samplesMs, samplesMs.length);
        Arrays.sort(sorted);
        long minMs = sorted[0];
        long medianMs = (sorted[4] + sorted[5]) / 2L;
        long maxMs = sorted[sorted.length - 1];
        String samples = Arrays.toString(samplesMs).replace(" ", "");
        String result = maxMs < 1000L ? "PASS" : "FAIL";
        System.out.printf(Locale.ROOT,
                "SAPI59_CA3_LATENCY_MS samples=%s min=%d median=%d max=%d threshold=1000 result=%s%n",
                samples, minMs, medianMs, maxMs, result);

        assertThat(maxMs)
                .as("CA3 max latency across 10 measured reads of findLatestRanking()")
                .isLessThan(1000L);
    }

    private static void assertLatestRanking(Optional<PersistedRanking> latest, long expectedExecutionId) {
        assertThat(latest).isPresent();
        assertThat(latest.get().execution().id()).isEqualTo(expectedExecutionId);
        assertThat(latest.get().cells()).hasSize(50);
        assertThat(latest.get().cells().get(0).rank()).isEqualTo(1);
        assertThat(latest.get().cells().get(49).rank()).isEqualTo(50);
    }

    @Test
    @DisplayName("SAPI-59.CA4.A — misma corrida dos veces → 1 ejecución + 50 predicciones")
    void ca4SameTwice() {
        long first = persistence.persist(ranking);
        long second = persistence.persist(ranking);
        assertThat(second).isEqualTo(first);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM ejecuciones", Integer.class)).isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM predicciones_celda", Integer.class)).isEqualTo(50);
    }

    @Test
    @DisplayName("SAPI-59.CA4.B — dos hilos concurrentes misma clave → 1 ejecución + 50 predicciones")
    void ca4Concurrent() throws Exception {
        int threads = 8;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch ready = new CountDownLatch(threads);
        CountDownLatch go = new CountDownLatch(1);
        AtomicReference<Throwable> error = new AtomicReference<>();
        List<Future<Long>> futures = new ArrayList<>();
        try {
            for (int i = 0; i < threads; i++) {
                futures.add(pool.submit(() -> {
                    ready.countDown();
                    go.await(30, TimeUnit.SECONDS);
                    return persistence.persist(ranking);
                }));
            }
            assertThat(ready.await(30, TimeUnit.SECONDS)).isTrue();
            go.countDown();
            List<Long> ids = new ArrayList<>();
            for (Future<Long> future : futures) {
                try {
                    ids.add(future.get(60, TimeUnit.SECONDS));
                }
                catch (Exception ex) {
                    error.compareAndSet(null, ex);
                }
            }
            assertThat(error.get()).isNull();
            assertThat(ids.stream().distinct()).hasSize(1);
            assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM ejecuciones", Integer.class)).isEqualTo(1);
            assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM predicciones_celda", Integer.class)).isEqualTo(50);
        }
        finally {
            pool.shutdownNow();
        }
    }

    @Test
    @DisplayName("SAPI-59.CA4.C — mismo forecast/model, fingerprint distinto → nueva ejecución")
    void ca4DifferentFingerprint() {
        long first = persistence.persist(ranking);
        ObjectNode other = (ObjectNode) ranking.deepCopy();
        other.put("inputs_fingerprint", "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc");
        long second = persistence.persist(other);
        assertThat(second).isNotEqualTo(first);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM ejecuciones", Integer.class)).isEqualTo(2);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM predicciones_celda", Integer.class)).isEqualTo(100);
    }

    @Test
    @DisplayName("SAPI-59.CA5 — Flyway V001–V003 aplicadas; persistencia redonda OK")
    void ca5FlywayAndPersistenceRoundTrip() {
        Integer flywayCount = jdbc.queryForObject("SELECT COUNT(*) FROM flyway_schema_history", Integer.class);
        assertThat(flywayCount).isGreaterThanOrEqualTo(3);
        List<String> versions = jdbc.queryForList("SELECT version FROM flyway_schema_history ORDER BY installed_rank",
                String.class);
        assertThat(versions).contains("001", "002", "003");

        long id = persistence.persist(ranking);
        Optional<PersistedRanking> latest = persistence.findLatestRanking();
        assertThat(latest).isPresent();
        assertThat(latest.get().execution().id()).isEqualTo(id);
        assertThat(latest.get().cells()).hasSize(50);
    }

    @Test
    @DisplayName("SAPI-59 — no sobrescribe silenciosamente predicciones distintas de la misma clave")
    void rejectsDivergentReplay() {
        long id = persistence.persist(ranking);
        jdbc.update("UPDATE predicciones_celda SET score = 0.999 WHERE ejecucion_id = ? AND rank = 1", id);

        assertThatThrownBy(() -> persistence.persist(ranking))
                .isInstanceOf(RankingPersistenceException.class)
                .hasMessageContaining("distintas");
    }

    private static byte[] realRankingBytes() {
        try (InputStream in = RankingPersistenceIT.class.getResourceAsStream(
                "/ml/predict-reproducible-2026-09-01.json")) {
            return in.readAllBytes();
        }
        catch (IOException ex) {
            throw new UncheckedIOException(ex);
        }
    }
}

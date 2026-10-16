package cl.sapi.backend.ranking.persistence;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.sql.Timestamp;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Comparator;

import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationVersion;
import org.flywaydb.core.api.output.MigrateResult;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataIntegrityViolationException;
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
 * SAPI F1 (D10/R2, IA-P1-03, Jira #10134/#10135): el CHECK {@code NOT VALID} de V004 es
 * {@code NOT NULL} hacia adelante, no retroactivo. Prueba obligatoria del Build (plan v2
 * canónico §D.6): una fila nacida antes de V004 (legacy) sobrevive con {@code firms_origin}
 * NULL, pero todo INSERT o UPDATE nuevo -- incluido sobre esa misma fila -- falla cerrado.
 *
 * <p>Flyway de Spring Boot migra V001-V004 solo al arrancar el contexto; este test controla
 * Flyway por su propia API, a un target intermedio (V003), para insertar una fila "legacy"
 * real antes de que exista la columna, y recién después migrar a V004.
 */
@SpringBootTest(properties = "spring.flyway.enabled=false")
@ActiveProfiles("it")
@Testcontainers(disabledWithoutDocker = true)
class FirmsOriginLegacyRowIT {

    private static final DockerImageName POSTGIS =
            DockerImageName.parse("postgis/postgis:15-3.4").asCompatibleSubstituteFor("postgres");

    @Container
    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer(POSTGIS)
            .withDatabaseName("sapi")
            .withUsername("sapi")
            .withPassword("sapi");

    private static final Path MIGRATIONS = Path.of("..", "..", "db", "migration").toAbsolutePath().normalize();

    @DynamicPropertySource
    static void datasource(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add("sapi.ml.base-url", () -> "http://127.0.0.1:9");
    }

    @Autowired
    private RankingPersistenceService persistence;

    @Autowired
    private JdbcTemplate jdbc;

    private long legacyExecutionId;
    private JsonNode rankingSameKeyAsLegacy;

    @BeforeEach
    void migrateToV003ThenInsertLegacyRowThenMigrateToV004() {
        jdbc.execute("DROP SCHEMA public CASCADE");
        jdbc.execute("CREATE SCHEMA public");

        Flyway toV003 = Flyway.configure()
                .dataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword())
                .locations("filesystem:" + MIGRATIONS)
                .target(MigrationVersion.fromVersion("3"))
                .load();
        toV003.migrate();

        RankingResultValidator.Validation validation =
                RankingResultValidator.validate(FixturesForThisTest.realRankingBytes());
        assertThat(validation.violation()).isEmpty();
        JsonNode baseRanking = validation.ranking();
        rankingSameKeyAsLegacy = ((ObjectNode) baseRanking.deepCopy()).put("firms_origin", "reproducibility");

        // Fila "legacy": insertada cuando la columna firms_origin todavía no existía.
        legacyExecutionId = jdbc.queryForObject("""
                INSERT INTO ejecuciones (
                    forecast_time, model_version, inputs_fingerprint, schema_version,
                    score_semantics, scientific_model_validation, horizon_hours)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """, Long.class,
                Timestamp.from(OffsetDateTime.parse(baseRanking.get("forecast_time").stringValue()).toInstant()),
                baseRanking.get("model_version").stringValue(),
                baseRanking.get("inputs_fingerprint").stringValue(),
                baseRanking.get("schema_version").stringValue(),
                baseRanking.get("score_semantics").stringValue(),
                baseRanking.get("scientific_model_validation").booleanValue(),
                baseRanking.get("horizon_hours").intValue());

        Flyway toV004 = Flyway.configure()
                .dataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword())
                .locations("filesystem:" + MIGRATIONS)
                .target(MigrationVersion.LATEST)
                .load();
        toV004.migrate();
    }

    @Test
    @DisplayName("D10/R2 — la fila legacy sobrevive con firms_origin NULL tras V004 (NOT VALID no es retroactivo)")
    void legacyRowSurvivesWithNullOrigin() {
        String origin = jdbc.queryForObject(
                "SELECT firms_origin FROM ejecuciones WHERE id = ?", String.class, legacyExecutionId);
        assertThat(origin).isNull();
    }

    @Test
    @DisplayName("F1 D2-B — replay con la misma clave natural que la fila legacy se rechaza, sin UPDATE")
    void replayAgainstLegacyRowIsRejectedWithoutUpdating() {
        assertThatThrownBy(() -> persistence.persist(rankingSameKeyAsLegacy))
                .isInstanceOf(PersistencePolicyRejectedException.class);

        String stillNull = jdbc.queryForObject(
                "SELECT firms_origin FROM ejecuciones WHERE id = ?", String.class, legacyExecutionId);
        assertThat(stillNull).isNull();
        Integer executions = jdbc.queryForObject("SELECT COUNT(*) FROM ejecuciones", Integer.class);
        assertThat(executions).isEqualTo(1);
        Integer predictions = jdbc.queryForObject("SELECT COUNT(*) FROM predicciones_celda", Integer.class);
        assertThat(predictions).isEqualTo(0);
    }

    @Test
    @DisplayName("D10/R2, IA-P1-03 — tras V004, un INSERT nuevo con firms_origin NULL falla cerrado")
    void newInsertWithNullOriginFailsClosed() {
        assertThatThrownBy(() -> jdbc.update("""
                INSERT INTO ejecuciones (
                    forecast_time, model_version, inputs_fingerprint, schema_version,
                    score_semantics, scientific_model_validation, horizon_hours, firms_origin)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                Timestamp.from(OffsetDateTime.parse("2026-09-02T00:00:00Z").toInstant()),
                "prototype_model_d_v1",
                "f".repeat(64),
                "sapi-ranking-v0", "relative_rank", false, 6))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("D10/R2, IA-P1-03 — tras V004, un UPDATE nuevo que deja firms_origin NULL también falla cerrado")
    void newUpdateSettingNullOriginFailsClosed() {
        long id = persistence.persist(rankingNotCollidingWithLegacy());

        assertThatThrownBy(() -> jdbc.update("UPDATE ejecuciones SET firms_origin = NULL WHERE id = ?", id))
                .isInstanceOf(DataIntegrityViolationException.class);

        String stillSet = jdbc.queryForObject(
                "SELECT firms_origin FROM ejecuciones WHERE id = ?", String.class, id);
        assertThat(stillSet).isEqualTo("reproducibility");
    }

    @Test
    @DisplayName("D10/R2, IA-P1-03 — UPDATE de OTRA columna en la fila legacy también falla cerrado")
    void updateOfAnotherColumnOnLegacyRowAlsoFailsClosed() {
        // El CHECK evalúa la fila completa resultante, no solo la columna tocada: firms_origin
        // sigue NULL en la imagen nueva de la fila, así que CUALQUIER UPDATE sobre una fila
        // legacy falla, no solo los que tocan firms_origin directamente. No se repara el dato.
        assertThatThrownBy(() -> jdbc.update(
                "UPDATE ejecuciones SET horizon_hours = 99 WHERE id = ?", legacyExecutionId))
                .isInstanceOf(DataIntegrityViolationException.class);

        Integer stillOriginalHorizon = jdbc.queryForObject(
                "SELECT horizon_hours FROM ejecuciones WHERE id = ?", Integer.class, legacyExecutionId);
        assertThat(stillOriginalHorizon).isNotEqualTo(99);
    }

    @Test
    @DisplayName("D10/R2 — INSERT del backend ANTERIOR a F1 (sin firms_origin, ON CONFLICT DO NOTHING) falla cerrado"
            + " con clave nueva (sin colisión real)")
    void oldBackendInsertOnConflictDoNothingFailsClosedAgainstV004Schema() {
        // SQL literal de RankingRepository ANTES de F1 (7 columnas, sin firms_origin): si el
        // backend viejo se revirtiera sobre una base que ya tiene V004, cada persist() nuevo
        // falla cerrado -- nunca persiste F1 en silencio (ADR-007 §5). Clave nueva: no hay fila
        // previa con esta clave natural, así que ON CONFLICT nunca llega a decidir nada; ver el
        // siguiente test para el caso con colisión real.
        assertThatThrownBy(() -> jdbc.update("""
                INSERT INTO ejecuciones (
                    forecast_time, model_version, inputs_fingerprint, schema_version,
                    score_semantics, scientific_model_validation, horizon_hours)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (forecast_time, model_version, inputs_fingerprint) DO NOTHING
                """,
                Timestamp.from(OffsetDateTime.parse("2026-09-03T00:00:00Z").toInstant()),
                "prototype_model_d_v1",
                "a".repeat(64),
                "sapi-ranking-v0", "relative_rank", false, 6))
                .isInstanceOf(DataIntegrityViolationException.class);

        Integer found = jdbc.queryForObject(
                "SELECT COUNT(*) FROM ejecuciones WHERE inputs_fingerprint = ?", Integer.class, "a".repeat(64));
        assertThat(found).isZero();
    }

    @Test
    @DisplayName("Astra IA-P1-03/D10/R2 — INSERT del backend ANTERIOR con la MISMA clave natural que una fila "
            + "V004 existente (colisión real) también falla cerrado, sin fila duplicada ni silenciada por ON CONFLICT")
    void oldBackendInsertOnConflictDoNothingFailsClosedWithRealKeyCollision() {
        // Hallazgo Astra sección 5: el test anterior usaba una clave nueva y "no demuestra
        // todavía el comportamiento cuando existe realmente el conflicto de clave". Aquí sí hay
        // colisión real: se persiste primero una ejecución V004 válida (vía el backend nuevo),
        // y luego se repite el INSERT literal del backend ANTERIOR (sin firms_origin) contra
        // EXACTAMENTE la misma clave natural (forecast_time, model_version, inputs_fingerprint).
        //
        // Comportamiento real de PostgreSQL (no inventado, verificado con Testcontainers):
        // el CHECK (firms_origin IS NOT NULL) se evalúa como parte de la fila propuesta por el
        // INSERT ANTES de que el motor decida si hay conflicto de unicidad. ON CONFLICT DO
        // NOTHING solo intercepta errores de unique_violation/exclusion_violation (doc oficial
        // de PostgreSQL) -- nunca check_violation. Por lo tanto la colisión real NO degrada a un
        // "silencioso no-op" vía DO NOTHING: sigue fallando cerrado con el mismo
        // DataIntegrityViolationException, y la fila existente permanece intacta.
        long existingId = persistence.persist(rankingNotCollidingWithLegacy());
        JsonNode existing = rankingNotCollidingWithLegacy();

        assertThatThrownBy(() -> jdbc.update("""
                INSERT INTO ejecuciones (
                    forecast_time, model_version, inputs_fingerprint, schema_version,
                    score_semantics, scientific_model_validation, horizon_hours)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (forecast_time, model_version, inputs_fingerprint) DO NOTHING
                """,
                Timestamp.from(OffsetDateTime.parse(existing.get("forecast_time").stringValue()).toInstant()),
                existing.get("model_version").stringValue(),
                existing.get("inputs_fingerprint").stringValue(),
                existing.get("schema_version").stringValue(),
                existing.get("score_semantics").stringValue(),
                existing.get("scientific_model_validation").booleanValue(),
                existing.get("horizon_hours").intValue()))
                .isInstanceOf(DataIntegrityViolationException.class);

        Integer totalWithThatFingerprint = jdbc.queryForObject(
                "SELECT COUNT(*) FROM ejecuciones WHERE inputs_fingerprint = ?",
                Integer.class, existing.get("inputs_fingerprint").stringValue());
        assertThat(totalWithThatFingerprint).as("ni fila duplicada ni silenciada por ON CONFLICT").isEqualTo(1);
        String stillStoredOrigin = jdbc.queryForObject(
                "SELECT firms_origin FROM ejecuciones WHERE id = ?", String.class, existingId);
        assertThat(stillStoredOrigin).as("la fila existente no se altera").isEqualTo("reproducibility");
    }

    @Test
    @DisplayName("E.2 #15 — backend viejo (locations V001-V003) arranca sobre base con V004 (*:future) y roll-forward OK")
    void oldBackendFlywayLocationsStartSuccessfullyThenRollForward() throws java.io.IOException {
        Path oldBackendLocations = Files.createTempDirectory("sapi-f1-old-backend-migrations");
        try {
            for (String name : new String[] {
                    "V001__enable_postgis.sql", "V002__create_sapi_v2_schema.sql", "V003__seed_celdas_geom.sql"}) {
                Files.copy(MIGRATIONS.resolve(name), oldBackendLocations.resolve(name),
                        StandardCopyOption.REPLACE_EXISTING);
            }

            Flyway oldBackendFlyway = Flyway.configure()
                    .dataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword())
                    .locations("filesystem:" + oldBackendLocations)
                    .load();
            // La base ya está en V004 (más adelante que lo que el backend viejo conoce).
            // Comportamiento default de Flyway (*:future): no falla al arrancar, no intenta
            // revertir ni reaplicar nada -- ignora la migración futura.
            MigrateResult result = oldBackendFlyway.migrate();
            assertThat(result.migrationsExecuted).isZero();

            Integer versionAfterOldBackend = jdbc.queryForObject(
                    "SELECT COUNT(*) FROM flyway_schema_history WHERE version = '004'", Integer.class);
            assertThat(versionAfterOldBackend).isEqualTo(1);

            // Roll-forward: el backend compatible (locations completas) vuelve a migrar sin error.
            Flyway rollForward = Flyway.configure()
                    .dataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword())
                    .locations("filesystem:" + MIGRATIONS)
                    .target(MigrationVersion.LATEST)
                    .load();
            MigrateResult rollForwardResult = rollForward.migrate();
            assertThat(rollForwardResult.migrationsExecuted).isZero();
            assertThat(rollForwardResult.success).isTrue();
        }
        finally {
            Files.walk(oldBackendLocations)
                    .sorted(Comparator.reverseOrder())
                    .forEach(path -> {
                        try {
                            Files.delete(path);
                        }
                        catch (java.io.IOException ex) {
                            path.toFile().deleteOnExit();
                        }
                    });
        }
    }

    private JsonNode rankingNotCollidingWithLegacy() {
        ObjectNode other = (ObjectNode) rankingSameKeyAsLegacy.deepCopy();
        other.put("inputs_fingerprint", "e".repeat(64));
        return other;
    }

    /** Evita depender del paquete de test de {@code cl.sapi.backend.ranking} solo por el fixture. */
    private static final class FixturesForThisTest {
        static byte[] realRankingBytes() {
            try (var in = FirmsOriginLegacyRowIT.class.getResourceAsStream(
                    "/ml/predict-reproducible-2026-09-01.json")) {
                return in.readAllBytes();
            }
            catch (java.io.IOException ex) {
                throw new java.io.UncheckedIOException(ex);
            }
        }
    }
}

package cl.sapi.backend.ranking;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import tools.jackson.databind.JsonNode;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

import cl.sapi.backend.ranking.StubMlServer.Reply;

/**
 * SAPI F1 (Astra B1): HTTP real (Spring Boot) → PostgreSQL/PostGIS real (Testcontainers), con
 * la política efectiva fijada a {@code current} únicamente (A2). Verifica rechazo de orígenes
 * no autorizados con {@code internal_error} y cero escrituras en ambas tablas, el camino feliz
 * con {@code current} sobre una identidad sintética distinta del fixture histórico, idempotencia
 * y concurrencia real de ocho hilos con el MISMO origen autorizado. La concurrencia con dos
 * orígenes autorizados DIVERGENTES sobre la misma identidad de negocio está en
 * {@link RankingHttpToPostgresDivergentOriginsIT} (política efectiva distinta: ambos orígenes
 * habilitados a la vez, como en el overlay de Compose base / E2E aislado).
 */
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT,
        properties = {"sapi.ml.connect-timeout=2s", "sapi.ml.read-timeout=5s",
                "sapi.persistence.allowed-firms-origins=current"})
@ActiveProfiles("it")
@Testcontainers(disabledWithoutDocker = true)
class RankingHttpToPostgresIT {

    private static final DockerImageName POSTGIS =
            DockerImageName.parse("postgis/postgis:15-3.4").asCompatibleSubstituteFor("postgres");

    @Container
    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer(POSTGIS)
            .withDatabaseName("sapi")
            .withUsername("sapi")
            .withPassword("sapi");

    private static final StubMlServer ML = new StubMlServer();

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        Path migrations = Path.of("..", "..", "db", "migration").toAbsolutePath().normalize();
        registry.add("spring.flyway.locations", () -> "filesystem:" + migrations);
        registry.add("sapi.ml.base-url", ML::baseUrl);
    }

    @AfterAll
    static void stopStub() {
        ML.close();
    }

    @Value("${local.server.port}")
    private int port;

    private JdbcTemplate jdbc;

    @Autowired
    void setJdbc(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @BeforeEach
    void reset() {
        ML.reset();
        jdbc.update("DELETE FROM predicciones_celda");
        jdbc.update("DELETE FROM ejecuciones");
        System.out.printf(Locale.ROOT,
                "SAPI_F1_B1_CONFIG allowed_firms_origins=current db=%s %s%n",
                POSTGRES.getJdbcUrl(), GitIdentity.CURRENT.describe());
    }

    /**
     * Identidad del candidato realmente ejecutado (Astra, hallazgo "evidencia del SHA final"):
     * nunca un literal fijo en el código -- se calcula una sola vez por JVM invocando
     * {@code git} sobre el repositorio real, con un resultado explícito para cuando {@code git}
     * no está disponible (nunca inventa ni reutiliza un SHA de otra corrida).
     */
    private enum GitIdentity {
        CURRENT;

        private final String head;
        private final String tree;
        private final boolean dirty;
        private final boolean available;

        GitIdentity() {
            String resolvedHead = runGit("rev-parse", "HEAD");
            String resolvedTree = runGit("rev-parse", "HEAD^{tree}");
            String status = runGit("status", "--porcelain");
            this.available = resolvedHead != null && resolvedTree != null;
            this.head = resolvedHead == null ? "unavailable" : resolvedHead;
            this.tree = resolvedTree == null ? "unavailable" : resolvedTree;
            this.dirty = status != null && !status.isBlank();
        }

        String describe() {
            return available
                    ? String.format(Locale.ROOT, "commit_under_test=%s tree_under_test=%s worktree=%s",
                            head, tree, dirty ? "dirty" : "clean")
                    : "commit_under_test=unavailable (git no accesible en este entorno de test)";
        }

        private static String runGit(String... args) {
            try {
                List<String> command = new java.util.ArrayList<>(List.of("git"));
                command.addAll(List.of(args));
                Process process = new ProcessBuilder(command)
                        .directory(Path.of(".").toAbsolutePath().toFile())
                        .redirectErrorStream(false)
                        .start();
                String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();
                boolean finished = process.waitFor(10, TimeUnit.SECONDS);
                return finished && process.exitValue() == 0 && !output.isEmpty() ? output : null;
            }
            catch (IOException | InterruptedException ex) {
                return null;
            }
        }
    }

    @Test
    @DisplayName("B1 — firms_origin ausente → 500 internal_error, 0 ejecuciones, 0 predicciones, sin fila por clave natural")
    void missingOriginRejectedWithZeroWrites() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()));
        int before = countExecutions();

        HttpResponse<byte[]> response = get("/api/v1/ranking");

        assertThat(response.statusCode()).isEqualTo(500);
        assertThat(errorType(response)).isEqualTo("internal_error");
        assertThat(countExecutions()).isEqualTo(before).isZero();
        assertThat(countPredictions()).isZero();
        logResult("missingOrigin", response.statusCode(), before, countExecutions());
    }

    @Test
    @DisplayName("B1 — firms_origin=baseline con política current → 500 internal_error, 0 ejecuciones, 0 predicciones, sin fila por clave natural")
    void baselineOriginRejectedWithZeroWrites() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRankingWith(root -> root.put("firms_origin", "baseline"))));
        int before = countExecutions();

        HttpResponse<byte[]> response = get("/api/v1/ranking");

        assertThat(response.statusCode()).isEqualTo(500);
        assertThat(errorType(response)).isEqualTo("internal_error");
        assertThat(countExecutions()).isEqualTo(before).isZero();
        assertThat(countPredictions()).isZero();
        assertThat(countByFingerprint(Fixtures.MAPPER.readTree(Fixtures.realRanking())
                .get("inputs_fingerprint").stringValue())).isZero();
        logResult("baselineOrigin", response.statusCode(), before, countExecutions());
    }

    @Test
    @DisplayName("B1 — firms_origin=reproducibility con política current → 500 internal_error, 0 ejecuciones, 0 predicciones")
    void reproducibilityOriginRejectedWhenPolicyIsCurrentOnly() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRankingWith(root -> root.put("firms_origin", "reproducibility"))));
        int before = countExecutions();

        HttpResponse<byte[]> response = get("/api/v1/ranking");

        assertThat(response.statusCode()).isEqualTo(500);
        assertThat(errorType(response)).isEqualTo("internal_error");
        assertThat(countExecutions()).isEqualTo(before).isZero();
        assertThat(countPredictions()).isZero();
        logResult("reproducibilityOrigin", response.statusCode(), before, countExecutions());
    }

    @Test
    @DisplayName("B1 — control sintético (identidad distinta del fixture histórico): firms_origin=current → 200, 1 ejecución, exactamente 50 predicciones")
    void allowedCurrentOriginPersistsOneExecutionAndFiftyPredictions() throws Exception {
        ML.reply(Reply.json(200, Fixtures.syntheticIdentityWithOrigin("current")));
        int before = countExecutions();

        HttpResponse<byte[]> response = get("/api/v1/ranking");

        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(countExecutions()).isEqualTo(before + 1).isEqualTo(1);
        assertThat(countPredictions()).isEqualTo(50);
        String storedOrigin = jdbc.queryForObject("SELECT firms_origin FROM ejecuciones LIMIT 1", String.class);
        assertThat(storedOrigin).isEqualTo("current");
        String storedFingerprint = jdbc.queryForObject(
                "SELECT inputs_fingerprint FROM ejecuciones LIMIT 1", String.class);
        assertThat(storedFingerprint)
                .as("la identidad del control CURRENT debe ser sintética, nunca la clave del fixture histórico")
                .isEqualTo(Fixtures.SYNTHETIC_FINGERPRINT)
                .isNotEqualTo(Fixtures.MAPPER.readTree(Fixtures.realRanking())
                        .get("inputs_fingerprint").stringValue());
        logResult("allowedCurrent", response.statusCode(), before, countExecutions());
    }

    @Test
    @DisplayName("B1 — replay idempotente con firms_origin=current (identidad sintética): 2 llamadas → 1 ejecución, 50 predicciones")
    void idempotentReplayWithCurrentOrigin() throws Exception {
        ML.reply(Reply.json(200, Fixtures.syntheticIdentityWithOrigin("current")));

        HttpResponse<byte[]> first = get("/api/v1/ranking");
        HttpResponse<byte[]> second = get("/api/v1/ranking");

        assertThat(first.statusCode()).isEqualTo(200);
        assertThat(second.statusCode()).isEqualTo(200);
        assertThat(first.body()).isEqualTo(second.body());
        assertThat(countExecutions()).isEqualTo(1);
        assertThat(countPredictions()).isEqualTo(50);
        logResult("idempotentReplay", second.statusCode(), 1, countExecutions());
    }

    @Test
    @DisplayName("B1 — idempotencia concurrente: 8 hilos, mismo origen autorizado (current) sobre la misma identidad → 1 ejecución, 50 predicciones")
    void concurrentRequestsWithSameAllowedOriginArePersistedIdempotently() throws Exception {
        ML.reply(Reply.json(200, Fixtures.syntheticIdentityWithOrigin("current")));
        // Los ocho hilos envían la MISMA réplica (mismo origen, misma identidad de negocio):
        // esto prueba idempotencia bajo concurrencia real, no mezcla de procedencias distintas.
        // La concurrencia con dos orígenes autorizados divergentes sobre la misma identidad está
        // en RankingHttpToPostgresDivergentOriginsIT (Astra, sección 4).
        int threads = 8;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch ready = new CountDownLatch(threads);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Integer>> futures = new java.util.ArrayList<>();
        try {
            for (int i = 0; i < threads; i++) {
                futures.add(pool.submit(() -> {
                    ready.countDown();
                    go.await(30, TimeUnit.SECONDS);
                    return get("/api/v1/ranking").statusCode();
                }));
            }
            assertThat(ready.await(30, TimeUnit.SECONDS)).isTrue();
            go.countDown();
            List<Integer> statuses = new java.util.ArrayList<>();
            for (Future<Integer> f : futures) {
                statuses.add(f.get(60, TimeUnit.SECONDS));
            }
            assertThat(statuses).allMatch(status -> status == 200);
            assertThat(countExecutions()).isEqualTo(1);
            assertThat(countPredictions()).isEqualTo(50);
            logResult("concurrentCurrentOnly", 200, 1, countExecutions());
        }
        finally {
            pool.shutdownNow();
        }
    }

    private int countExecutions() {
        Integer n = jdbc.queryForObject("SELECT COUNT(*) FROM ejecuciones", Integer.class);
        return n == null ? 0 : n;
    }

    private int countPredictions() {
        Integer n = jdbc.queryForObject("SELECT COUNT(*) FROM predicciones_celda", Integer.class);
        return n == null ? 0 : n;
    }

    private int countByFingerprint(String fingerprint) {
        Integer n = jdbc.queryForObject(
                "SELECT COUNT(*) FROM ejecuciones WHERE inputs_fingerprint = ?", Integer.class, fingerprint);
        return n == null ? 0 : n;
    }

    /** {@code error_type} del cuerpo {@code Error} (backend.v0.yaml), para no limitarse al status HTTP. */
    static String errorType(HttpResponse<byte[]> response) {
        JsonNode body = Fixtures.MAPPER.readTree(response.body());
        JsonNode node = body.get("error_type");
        return node == null || node.isNull() ? null : node.stringValue();
    }

    private static void logResult(String scenario, int status, int before, int after) {
        System.out.printf(Locale.ROOT, "SAPI_F1_B1_RESULT scenario=%s status=%d executions_before=%d executions_after=%d%n",
                scenario, status, before, after);
    }

    private HttpResponse<byte[]> get(String path) throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path)).GET().build();
        try (HttpClient client = HttpClient.newHttpClient()) {
            return client.send(request, HttpResponse.BodyHandlers.ofByteArray());
        }
    }
}

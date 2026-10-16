package cl.sapi.backend.ranking;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

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
 * SAPI F1 (Astra, sección 4: "La prueba de ocho hilos no prueba orígenes divergentes").
 *
 * <p>Política efectiva {@code current,reproducibility} (igual que el Compose base / E2E
 * aislado, distinta del overlay operacional que solo permite {@code current}): ambos orígenes
 * están autorizados a la vez. Ejercita concurrencia REAL de dos procedencias distintas sobre la
 * MISMA identidad de negocio (clave natural {@code forecast_time}/{@code model_version}/
 * {@code inputs_fingerprint}) y establece el comportamiento esperado desde el contrato real de
 * {@link cl.sapi.backend.ranking.persistence.RankingPersistenceService#persist}, no uno
 * inventado:
 *
 * <ul>
 *   <li>El primer INSERT que gana la carrera fija el {@code firms_origin} persistido para esa
 *       identidad (clave natural única en {@code ejecuciones}).
 *   <li>Toda petición posterior con el MISMO origen que el ganador es un replay idempotente:
 *       {@code assertSameExecutionMetadata} coincide → 200.
 *   <li>Toda petición con el OTRO origen autorizado encuentra metadata divergente
 *       ({@code firms_origin} no coincide) → {@code RankingPersistenceException} →
 *       {@code RankingError.INTERNAL_ERROR} → 500 {@code internal_error}, sin fila nueva.
 * </ul>
 *
 * <p>Con 8 peticiones concurrentes y alternancia estricta 1:1 del stub, hay exactamente 4 con
 * cada origen: por lo tanto, sin importar cuál de los dos gane la carrera, el resultado final es
 * siempre exactamente 4 éxitos (200) y 4 rechazos (500), 1 ejecución, 50 predicciones, y el
 * {@code firms_origin} almacenado es uno solo de los dos valores -- nunca ambos, nunca nulo,
 * nunca corrompido.
 */
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT,
        properties = {"sapi.ml.connect-timeout=2s", "sapi.ml.read-timeout=5s",
                "sapi.persistence.allowed-firms-origins=current,reproducibility"})
@ActiveProfiles("it")
@Testcontainers(disabledWithoutDocker = true)
class RankingHttpToPostgresDivergentOriginsIT {

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
    }

    @Test
    @DisplayName("F1 B4 (Astra) — 8 hilos, 4 con current + 4 con reproducibility sobre la MISMA identidad: "
            + "exactamente 4x200/4x500, 1 ejecución, 50 predicciones, sin mezclar procedencias")
    void concurrentRequestsWithDivergentAuthorizedOriginsNeverMixProvenance() throws Exception {
        byte[] current = Fixtures.syntheticIdentityWithOrigin("current");
        byte[] reproducibility = Fixtures.syntheticIdentityWithOrigin("reproducibility");
        ML.replyAlternating(Reply.json(200, current), Reply.json(200, reproducibility));

        int threads = 8;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch ready = new CountDownLatch(threads);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<HttpResponse<byte[]>>> futures = new java.util.ArrayList<>();
        try {
            for (int i = 0; i < threads; i++) {
                futures.add(pool.submit(() -> {
                    ready.countDown();
                    go.await(30, TimeUnit.SECONDS);
                    return get("/api/v1/ranking");
                }));
            }
            assertThat(ready.await(30, TimeUnit.SECONDS)).isTrue();
            go.countDown();
            List<HttpResponse<byte[]>> responses = new java.util.ArrayList<>();
            for (Future<HttpResponse<byte[]>> f : futures) {
                responses.add(f.get(60, TimeUnit.SECONDS));
            }

            long ok = responses.stream().filter(r -> r.statusCode() == 200).count();
            long rejected = responses.stream().filter(r -> r.statusCode() == 500).count();
            assertThat(ok).as("exactamente 4 peticiones comparten el origen que ganó la carrera").isEqualTo(4);
            assertThat(rejected).as("exactamente 4 peticiones con el origen perdedor, rechazadas").isEqualTo(4);
            assertThat(responses).filteredOn(r -> r.statusCode() == 500)
                    .allSatisfy(r -> assertThat(RankingHttpToPostgresIT.errorType(r)).isEqualTo("internal_error"));

            assertThat(countExecutions()).as("ninguna petición rechazada crea una fila nueva").isEqualTo(1);
            assertThat(countPredictions()).isEqualTo(50);
            String storedOrigin = jdbc.queryForObject("SELECT firms_origin FROM ejecuciones LIMIT 1", String.class);
            assertThat(storedOrigin)
                    .as("procedencia persistida: exactamente una de las dos, nunca mezclada ni nula")
                    .isIn("current", "reproducibility");
            long distinctOrigins = jdbc.queryForObject(
                    "SELECT COUNT(DISTINCT firms_origin) FROM ejecuciones", Long.class);
            assertThat(distinctOrigins).isEqualTo(1);
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

    private HttpResponse<byte[]> get(String path) throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path)).GET().build();
        try (HttpClient client = HttpClient.newHttpClient()) {
            return client.send(request, HttpResponse.BodyHandlers.ofByteArray());
        }
    }
}

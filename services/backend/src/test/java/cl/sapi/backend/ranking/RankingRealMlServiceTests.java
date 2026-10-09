package cl.sapi.backend.ranking;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import tools.jackson.databind.JsonNode;

/**
 * Integración contra el servicio ML real (FastAPI + Modelo D), no un stub (SAPI-57.CA4, variante "real").
 *
 * <p>Se activa con {@code SAPI_IT_ML_BASE_URL} apuntando a un servicio ML en modo reproducible
 * ({@code SAPI_REPRODUCIBILITY_MODE=1}); sin esa variable se omite. El E2E completo es SAPI-66.
 */
@EnabledIfEnvironmentVariable(named = "SAPI_IT_ML_BASE_URL", matches = "https?://.+")
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT, properties = "sapi.ml.read-timeout=120s")
class RankingRealMlServiceTests {

    private static final String ML_BASE_URL = System.getenv("SAPI_IT_ML_BASE_URL");

    @DynamicPropertySource
    static void mlBaseUrl(DynamicPropertyRegistry registry) {
        registry.add("sapi.ml.base-url", () -> ML_BASE_URL);
    }

    @Value("${local.server.port}")
    private int port;

    @Test
    @DisplayName("SAPI-57.CA4 — Spring ↔ FastAPI real: el backend devuelve los mismos bytes que POST /predict")
    void backendReturnsSameBytesAsMlService() throws Exception {
        byte[] direct = postPredict("{}");

        HttpResponse<byte[]> response = get("/api/v1/ranking");

        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).isEqualTo(direct);
        assertThat(BackendContract.validate(200, response.body())).isEmpty();
        JsonNode ranking = Fixtures.MAPPER.readTree(response.body());
        assertThat(ranking.get("cells")).hasSize(50);
        assertThat(ranking.get("score_semantics").stringValue()).isEqualTo("relative_rank");
        assertThat(ranking.get("scientific_model_validation").booleanValue()).isFalse();
    }

    @Test
    @DisplayName("SAPI-57.CA4 — Spring ↔ FastAPI real: forecast_time explícito llega al ML y vuelve igual")
    void explicitForecastTimeRoundTrips() throws Exception {
        String forecastTime = Fixtures.MAPPER.readTree(postPredict("{}")).get("forecast_time").stringValue();
        byte[] direct = postPredict("{\"forecast_time\":\"" + forecastTime + "\"}");

        HttpResponse<byte[]> response = get("/api/v1/ranking?forecast_time="
                + URLEncoder.encode(forecastTime, StandardCharsets.UTF_8));

        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).isEqualTo(direct);
    }

    @Test
    @DisplayName("SAPI-57.CA2 — Spring ↔ FastAPI real: un forecast_time futuro propaga 503 prototype_unavailable")
    void futureForecastTimePropagates503() throws Exception {
        HttpResponse<byte[]> response = get("/api/v1/ranking?forecast_time="
                + URLEncoder.encode("2099-01-01T00:00:00Z", StandardCharsets.UTF_8));

        assertThat(response.statusCode()).isEqualTo(503);
        assertThat(BackendContract.validate(503, response.body())).isEmpty();
        assertThat(Fixtures.MAPPER.readTree(response.body()).get("error_type").stringValue())
                .isEqualTo("prototype_unavailable");
    }

    private HttpResponse<byte[]> get(String path) throws Exception {
        try (HttpClient client = HttpClient.newHttpClient()) {
            return client.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path)).GET().build(),
                    HttpResponse.BodyHandlers.ofByteArray());
        }
    }

    private static byte[] postPredict(String json) throws Exception {
        try (HttpClient client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).build()) {
            HttpResponse<byte[]> response = client.send(HttpRequest.newBuilder(URI.create(ML_BASE_URL + "/predict"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json)).build(),
                    HttpResponse.BodyHandlers.ofByteArray());
            assertThat(response.statusCode()).isEqualTo(200);
            return response.body();
        }
    }
}

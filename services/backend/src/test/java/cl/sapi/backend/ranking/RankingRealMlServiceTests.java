package cl.sapi.backend.ranking;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/**
 * Integración contra el servicio ML real (FastAPI + Modelo D), no un stub (SAPI-57.CA4, variante "real").
 *
 * <p>Se activa con {@code SAPI_IT_ML_BASE_URL} apuntando a un servicio ML en modo reproducible
 * ({@code SAPI_REPRODUCIBILITY_MODE=1}); sin esa variable se omite. El E2E completo es SAPI-66.
 *
 * <p>El backend habla con el ML a través de {@link RecordingMlProxy}, que graba los bytes exactos de
 * cada evaluación: la igualdad literal se exige contra la MISMA evaluación que relayó el backend.
 * Dos evaluaciones distintas del ML nunca coinciden byte a byte ({@code age_hours} se mide contra el
 * reloj), así que esa comparación solo se hace, aparte, sin los campos derivados del reloj.
 */
@EnabledIfEnvironmentVariable(named = "SAPI_IT_ML_BASE_URL", matches = "https?://.+")
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT, properties = "sapi.ml.read-timeout=120s")
class RankingRealMlServiceTests {

    private static final String ML_BASE_URL = System.getenv("SAPI_IT_ML_BASE_URL");
    private static final RecordingMlProxy PROXY = startProxy();

    @DynamicPropertySource
    static void mlBaseUrl(DynamicPropertyRegistry registry) {
        registry.add("sapi.ml.base-url", PROXY::baseUrl);
    }

    @AfterAll
    static void stopProxy() {
        PROXY.close();
    }

    @Value("${local.server.port}")
    private int port;

    @Test
    @DisplayName("SAPI-57.CA4 — Spring ↔ FastAPI real: el backend devuelve los mismos bytes que el ML en esa evaluación")
    void backendReturnsSameBytesAsMlService() throws Exception {
        int before = PROXY.calls();

        HttpResponse<byte[]> response = get("/api/v1/ranking");

        assertThat(PROXY.calls() - before).isEqualTo(1);
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).isEqualTo(PROXY.lastMlBody());
        assertThat(BackendContract.validate(200, response.body())).isEmpty();
        JsonNode ranking = Fixtures.MAPPER.readTree(response.body());
        assertThat(ranking.get("cells")).hasSize(50);
        assertThat(ranking.get("score_semantics").stringValue()).isEqualTo("relative_rank");
        assertThat(ranking.get("scientific_model_validation").booleanValue()).isFalse();
        assertThat(ranking.has("age_hours")).isTrue();
        assertThat(ranking.has("freshness")).isTrue();
        assertThat(withoutClockFields(postPredict("{}"))).isEqualTo(withoutClockFields(response.body()));
    }

    @Test
    @DisplayName("SAPI-57.CA1, CA4 — Spring ↔ FastAPI real: un forecast_time anterior llega al ML y vuelve evaluado")
    void explicitEarlierForecastTimeRoundTrips() throws Exception {
        byte[] latest = postPredict("{}");
        OffsetDateTime earlier = OffsetDateTime.parse(
                Fixtures.MAPPER.readTree(latest).get("forecast_time").stringValue()).minusHours(6);
        String forecastTime = earlier.withOffsetSameInstant(ZoneOffset.UTC)
                .format(DateTimeFormatter.ISO_OFFSET_DATE_TIME);
        int before = PROXY.calls();

        HttpResponse<byte[]> response = get("/api/v1/ranking?forecast_time="
                + URLEncoder.encode(forecastTime, StandardCharsets.UTF_8));

        assertThat(PROXY.calls() - before).isEqualTo(1);
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).isEqualTo(PROXY.lastMlBody());
        assertThat(withoutClockFields(response.body()))
                .isEqualTo(withoutClockFields(postPredict("{\"forecast_time\":\"" + forecastTime + "\"}")))
                .isNotEqualTo(withoutClockFields(latest));
        assertThat(OffsetDateTime.parse(Fixtures.MAPPER.readTree(response.body()).get("forecast_time").stringValue())
                .toInstant()).isEqualTo(earlier.toInstant());
    }

    @Test
    @DisplayName("SAPI-57.CA1, CA4 — Spring ↔ FastAPI real: un offset +HH:MM (enviado como %2B) se respeta")
    void positiveOffsetRoundTrips() throws Exception {
        byte[] latest = postPredict("{}");
        OffsetDateTime earlier = OffsetDateTime.parse(
                Fixtures.MAPPER.readTree(latest).get("forecast_time").stringValue()).minusHours(6);
        String withOffset = earlier.withOffsetSameInstant(ZoneOffset.ofHours(3))
                .format(DateTimeFormatter.ISO_OFFSET_DATE_TIME);
        int before = PROXY.calls();

        HttpResponse<byte[]> response = get("/api/v1/ranking?forecast_time="
                + URLEncoder.encode(withOffset, StandardCharsets.UTF_8));

        assertThat(withOffset).contains("+03:00");
        assertThat(PROXY.calls() - before).isEqualTo(1);
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).isEqualTo(PROXY.lastMlBody());
        assertThat(withoutClockFields(response.body()))
                .isEqualTo(withoutClockFields(postPredict("{\"forecast_time\":\"" + withOffset + "\"}")));
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

    @Test
    @DisplayName("SAPI-57.CA3 (mutación) — una reserialización del cuerpo rompe la igualdad literal de bytes")
    void reserializedBodyBreaksLiteralByteEquality() throws Exception {
        PROXY.mutateWith(body -> Fixtures.MAPPER.writerWithDefaultPrettyPrinter()
                .writeValueAsBytes(Fixtures.MAPPER.readTree(body)));
        try {
            HttpResponse<byte[]> response = get("/api/v1/ranking");

            assertThat(response.statusCode()).isEqualTo(200);
            assertThat(Fixtures.MAPPER.readTree(response.body())).isEqualTo(Fixtures.MAPPER.readTree(PROXY.lastMlBody()));
            assertThat(response.body()).isNotEqualTo(PROXY.lastMlBody());
        }
        finally {
            PROXY.mutateWith(null);
        }
    }

    /** Comparación entre DOS evaluaciones: sin los campos que dependen del reloj de captura. */
    private static JsonNode withoutClockFields(byte[] body) {
        ObjectNode node = (ObjectNode) Fixtures.MAPPER.readTree(body);
        node.remove("age_hours");
        node.remove("freshness");
        return node;
    }

    private static RecordingMlProxy startProxy() {
        try {
            return new RecordingMlProxy(ML_BASE_URL);
        }
        catch (IOException ex) {
            throw new UncheckedIOException(ex);
        }
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

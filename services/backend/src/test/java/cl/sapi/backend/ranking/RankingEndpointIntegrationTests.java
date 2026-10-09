package cl.sapi.backend.ranking;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.logging.logback.StructuredLogEncoder;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.LoggerContext;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import cl.sapi.backend.ranking.StubMlServer.Reply;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ArrayNode;

/**
 * Integración Spring ↔ servicio ML por HTTP real (SAPI-57.CA4, con un stub del ML): el backend corre en
 * un puerto aleatorio y llama a un servidor HTTP en 127.0.0.1 que responde lo que cada test programa.
 */
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT,
        properties = {"sapi.ml.connect-timeout=1s", "sapi.ml.read-timeout=1s"})
class RankingEndpointIntegrationTests {

    private static final StubMlServer ML = new StubMlServer();

    @DynamicPropertySource
    static void mlBaseUrl(DynamicPropertyRegistry registry) {
        registry.add("sapi.ml.base-url", ML::baseUrl);
    }

    @AfterAll
    static void stopStub() {
        ML.close();
    }

    @Value("${local.server.port}")
    private int port;

    private final ListAppender<ILoggingEvent> logs = new ListAppender<>();

    @BeforeEach
    void setUp() {
        ML.reset();
        logs.start();
        ((Logger) LoggerFactory.getLogger(RankingService.LOGGER_NAME)).addAppender(logs);
    }

    @AfterEach
    void tearDown() {
        ((Logger) LoggerFactory.getLogger(RankingService.LOGGER_NAME)).detachAppender(logs);
    }

    // --- CA1 / CA3 / CA4: camino feliz ---------------------------------------------------------

    @Test
    @DisplayName("SAPI-57.CA1 — el backend llama POST /predict del ML por HTTP con cuerpo {} y JSON")
    void callsPredictWithEmptyBody() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()));

        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of());

        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(ML.received()).hasSize(1);
        StubMlServer.Received request = ML.received().get(0);
        assertThat(request.method()).isEqualTo("POST");
        assertThat(request.path()).isEqualTo("/predict");
        assertThat(request.header("Content-Type")).startsWith("application/json");
        assertThat(Fixtures.MAPPER.readTree(request.body())).isEqualTo(Fixtures.MAPPER.readTree("{}"));
        assertThat(request.header("X-Request-Id")).isEqualTo(requestId(response));
    }

    @ParameterizedTest(name = "{0}")
    @ValueSource(strings = {"2026-09-01T00:00:00Z", "2026-10-01T18:00:00-03:00", "2026-10-01T21:00:00+00:00",
            "2026-10-01T21:00:00.5+00:00"})
    @DisplayName("SAPI-57.CA1 — forecast_time se reenvía al ML sin modificar")
    void forwardsForecastTime(String forecastTime) throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()));

        HttpResponse<byte[]> response = get("/api/v1/ranking?forecast_time="
                + URLEncoder.encode(forecastTime, StandardCharsets.UTF_8), Map.of());

        assertThat(response.statusCode()).isEqualTo(200);
        JsonNode sent = Fixtures.MAPPER.readTree(ML.received().get(0).body());
        assertThat(sent.propertyNames()).containsExactly("forecast_time");
        assertThat(sent.get("forecast_time").stringValue()).isEqualTo(forecastTime);
    }

    @Test
    @DisplayName("SAPI-57.CA3 — GET /api/v1/ranking devuelve las 50 celdas del ML sin reordenar ni reformatear")
    void returnsMlBodyUnchanged() throws Exception {
        byte[] mlBody = Fixtures.realRanking();
        ML.reply(Reply.json(200, mlBody));

        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of());

        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.headers().firstValue("Content-Type")).hasValueSatisfying(
                type -> assertThat(type).startsWith("application/json"));
        assertThat(response.body()).isEqualTo(mlBody);
        ArrayNode cells = (ArrayNode) Fixtures.MAPPER.readTree(response.body()).get("cells");
        assertThat(cells).hasSize(50);
        for (int i = 0; i < cells.size(); i++) {
            assertThat(cells.get(i).get("rank").intValue()).isEqualTo(i + 1);
            if (i > 0) {
                assertThat(cells.get(i).get("score").doubleValue())
                        .isLessThanOrEqualTo(cells.get(i - 1).get("score").doubleValue());
            }
        }
    }

    @Test
    @DisplayName("SAPI-57.CA3 — la respuesta 200 cumple backend.v0.yaml (RankingResult vía $ref)")
    void successResponseConformsToContract() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()));

        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of());

        assertThat(BackendContract.declaredStatuses()).contains("200");
        assertThat(BackendContract.validate(response.statusCode(), response.body())).isEmpty();
    }

    @Test
    @DisplayName("SAPI-57.CA3 — el validador de contrato del test detecta un RankingResult inválido")
    void contractValidatorIsNotVacuous() {
        byte[] invalid = Fixtures.realRankingWith(root -> {
            ((ArrayNode) root.get("cells")).remove(0);
            root.put("forecast_time", "ayer");
        });
        assertThat(BackendContract.validate(200, invalid)).isNotEmpty();
        assertThat(BackendContract.validate(503, "{\"status\":\"error\"}".getBytes(StandardCharsets.UTF_8)))
                .isNotEmpty();
    }

    // --- CA2: errores controlados --------------------------------------------------------------

    static Stream<Arguments> mlFailures() {
        byte[] real = Fixtures.realRanking();
        return Stream.of(
                Arguments.of("200 no JSON", Reply.json(200, "<html>proxy</html>".getBytes(StandardCharsets.UTF_8)),
                        502, "upstream_invalid_response"),
                Arguments.of("200 con 49 celdas", Reply.json(200,
                        Fixtures.realRankingWith(root -> ((ArrayNode) root.get("cells")).remove(49))),
                        502, "upstream_invalid_response"),
                Arguments.of("200 con validación científica true", Reply.json(200,
                        Fixtures.realRankingWith(root -> root.put("scientific_model_validation", true))),
                        502, "upstream_invalid_response"),
                Arguments.of("200 sin cuerpo", Reply.json(200, new byte[0]), 502, "upstream_invalid_response"),
                Arguments.of("201 con ranking válido", Reply.json(201, real), 502, "upstream_invalid_response"),
                Arguments.of("302 redirección", new Reply(302, new byte[0],
                        Map.of("Location", "http://127.0.0.1:9/predict"), 0), 502, "upstream_invalid_response"),
                Arguments.of("404", Reply.json(404, "{\"detail\":\"Not Found\"}".getBytes(StandardCharsets.UTF_8)),
                        502, "upstream_invalid_response"),
                Arguments.of("422 invalid_request", Reply.json(422, Fixtures.mlError("invalid_request")),
                        422, "invalid_request"),
                Arguments.of("422 sin cuerpo Error", Reply.json(422, "{}".getBytes(StandardCharsets.UTF_8)),
                        502, "upstream_invalid_response"),
                Arguments.of("500 internal_error", Reply.json(500, Fixtures.mlError("internal_error")),
                        500, "internal_error"),
                Arguments.of("503 prototype_unavailable", Reply.json(503, Fixtures.mlError("prototype_unavailable")),
                        503, "prototype_unavailable"),
                Arguments.of("503 data_unavailable", Reply.json(503, Fixtures.mlError("data_unavailable")),
                        503, "data_unavailable"),
                Arguments.of("503 sin cuerpo Error", Reply.json(503, "<html>503</html>".getBytes(StandardCharsets.UTF_8)),
                        503, "upstream_unavailable"),
                Arguments.of("503 error_type desconocido", Reply.json(503, Fixtures.mlError("otro_error")),
                        503, "upstream_unavailable"),
                Arguments.of("502 de un proxy", Reply.json(502, new byte[0]), 502, "upstream_invalid_response"));
    }

    @ParameterizedTest(name = "{0} → {2} {3}")
    @MethodSource("mlFailures")
    @DisplayName("SAPI-57.CA2 — cada respuesta del ML se mapea a un error controlado del contrato")
    void mapsMlFailures(String name, Reply reply, int status, String errorType) throws Exception {
        ML.reply(reply);

        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of());

        assertError(response, status, errorType);
    }

    @Test
    @DisplayName("SAPI-57.CA2 — el ML no responde dentro del timeout → 504 upstream_timeout")
    void timeoutIs504() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()).delayed(3_000));

        long start = System.nanoTime();
        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of());
        Duration elapsed = Duration.ofNanos(System.nanoTime() - start);

        assertError(response, 504, "upstream_timeout");
        assertThat(elapsed).isLessThan(Duration.ofMillis(2_800));
    }

    @Test
    @DisplayName("SAPI-57.CA2 — un cuerpo del ML mayor al máximo → 502 upstream_invalid_response")
    void oversizedBodyIs502() throws Exception {
        ML.reply(Reply.json(200, new byte[2 * 1024 * 1024]));

        assertError(get("/api/v1/ranking", Map.of()), 502, "upstream_invalid_response");
    }

    @ParameterizedTest(name = "\"{0}\"")
    @ValueSource(strings = {"2026-10-01T18:00:00", "2026-10-01", "mañana", "", "2026-13-01T00:00:00Z"})
    @DisplayName("SAPI-57.CA2 — forecast_time inválido → 422 invalid_request sin llamar al ML")
    void invalidForecastTimeIs422WithoutCallingMl(String forecastTime) throws Exception {
        HttpResponse<byte[]> response = get("/api/v1/ranking?forecast_time="
                + URLEncoder.encode(forecastTime, StandardCharsets.UTF_8), Map.of());

        assertError(response, 422, "invalid_request");
        assertThat(ML.received()).isEmpty();
    }

    // --- CA5: logs estructurados ---------------------------------------------------------------

    @Test
    @DisplayName("SAPI-57.CA5 — cada llamada al ML deja un log ml_predict con request_id y latencia")
    void logsEachMlCall() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()));

        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of());

        ILoggingEvent event = singleEvent("ml_predict");
        Map<String, Object> fields = fields(event);
        assertThat(event.getLevel()).isEqualTo(Level.INFO);
        assertThat(fields).containsEntry("request_id", requestId(response))
                .containsEntry("forecast_time_requested", "latest")
                .containsEntry("ml_http_status", 200)
                .containsEntry("outcome", "ok")
                .containsEntry("backend_http_status", 200)
                .containsEntry("model_version", "prototype_model_d_v1")
                .containsEntry("forecast_time", "2026-09-01T00:00:00Z")
                .containsKey("inputs_fingerprint");
        assertThat((Long) fields.get("ml_latency_ms")).isGreaterThanOrEqualTo(0L);
        assertThat(event.getFormattedMessage()).startsWith("ml_predict request_id=" + requestId(response))
                .contains("ml_latency_ms=").doesNotContain("score").doesNotContain("VP-0");
    }

    @Test
    @DisplayName("SAPI-57.CA5 — un timeout queda en el log con outcome upstream_timeout y nivel WARN")
    void logsTimeouts() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()).delayed(3_000));

        get("/api/v1/ranking", Map.of());

        ILoggingEvent event = singleEvent("ml_predict");
        assertThat(event.getLevel()).isEqualTo(Level.WARN);
        assertThat(fields(event)).containsEntry("outcome", "upstream_timeout")
                .containsEntry("ml_http_status", "none")
                .containsEntry("backend_http_status", 504);
    }

    @Test
    @DisplayName("SAPI-57.CA5 — un X-Request-Id válido se conserva y se propaga al ML")
    void keepsValidRequestId() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()));

        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of("X-Request-Id", "streamlit-42.a:b"));

        assertThat(requestId(response)).isEqualTo("streamlit-42.a:b");
        assertThat(ML.received().get(0).header("X-Request-Id")).isEqualTo("streamlit-42.a:b");
        assertThat(fields(singleEvent("ml_predict"))).containsEntry("request_id", "streamlit-42.a:b");
    }

    @Test
    @DisplayName("SAPI-57.CA5 — un X-Request-Id inseguro se reemplaza por uno generado")
    void replacesUnsafeRequestId() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()));

        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of("X-Request-Id", "a b<script>"));

        assertThat(requestId(response)).matches("[0-9a-f-]{36}");
        assertThat(ML.received().get(0).header("X-Request-Id")).isEqualTo(requestId(response));
    }

    @Test
    @DisplayName("SAPI-57.CA5 — una solicitud rechazada deja un log sin el valor recibido")
    void logsRejectedRequestWithoutValue() throws Exception {
        HttpResponse<byte[]> response = get("/api/v1/ranking?forecast_time=" + URLEncoder.encode(
                "x\ny=1", StandardCharsets.UTF_8), Map.of());

        ILoggingEvent event = singleEvent("ranking_request_rejected");
        assertThat(fields(event)).containsEntry("request_id", requestId(response))
                .containsEntry("backend_http_status", 422);
        assertThat(event.getFormattedMessage()).doesNotContain("y=1").doesNotContain("\n");
    }

    @Test
    @DisplayName("SAPI-57.CA5 — con el formato estructurado logstash de Spring Boot, los campos salen como JSON")
    void fieldsRenderAsJsonWithStructuredLogging() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()));
        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of());
        ILoggingEvent event = singleEvent("ml_predict");

        StructuredLogEncoder encoder = new StructuredLogEncoder();
        encoder.setContext((LoggerContext) LoggerFactory.getILoggerFactory());
        encoder.setFormat("logstash");
        encoder.start();
        JsonNode json = Fixtures.MAPPER.readTree(encoder.encode(event));
        encoder.stop();

        assertThat(json.get("event").stringValue()).isEqualTo("ml_predict");
        assertThat(json.get("request_id").stringValue()).isEqualTo(requestId(response));
        assertThat(json.get("ml_latency_ms").isIntegralNumber()).isTrue();
        assertThat(json.get("outcome").stringValue()).isEqualTo("ok");
    }

    // --- helpers ---------------------------------------------------------------------------------

    private HttpResponse<byte[]> get(String path, Map<String, String> headers)
            throws IOException, InterruptedException {
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path)).GET();
        headers.forEach(request::header);
        try (HttpClient client = HttpClient.newHttpClient()) {
            return client.send(request.build(), HttpResponse.BodyHandlers.ofByteArray());
        }
    }

    private static String requestId(HttpResponse<?> response) {
        return response.headers().firstValue("X-Request-Id").orElseThrow();
    }

    private static void assertError(HttpResponse<byte[]> response, int status, String errorType) {
        assertThat(response.statusCode()).isEqualTo(status);
        assertThat(BackendContract.declaredStatuses()).contains(String.valueOf(status));
        assertThat(BackendContract.validate(status, response.body())).isEmpty();
        JsonNode body = Fixtures.MAPPER.readTree(response.body());
        assertThat(body.get("status").stringValue()).isEqualTo("error");
        assertThat(body.get("error_type").stringValue()).isEqualTo(errorType);
        assertThat(body.get("message").stringValue()).doesNotContain("mensaje del ML").doesNotContain("127.0.0.1")
                .doesNotContain("Exception");
        assertThat(response.headers().firstValue("X-Request-Id")).isPresent();
    }

    private ILoggingEvent singleEvent(String eventName) {
        List<ILoggingEvent> matching = logs.list.stream()
                .filter(event -> eventName.equals(fields(event).get("event")))
                .toList();
        assertThat(matching).hasSize(1);
        return matching.get(0);
    }

    private static Map<String, Object> fields(ILoggingEvent event) {
        Map<String, Object> fields = new LinkedHashMap<>();
        if (event.getKeyValuePairs() != null) {
            event.getKeyValuePairs().forEach(pair -> fields.put(pair.key, pair.value));
        }
        return fields;
    }
}

package cl.sapi.backend.ranking;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.Socket;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Arrays;
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
import cl.sapi.backend.ranking.ml.MlServiceClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

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
    private final ListAppender<ILoggingEvent> rootLogs = new ListAppender<>();

    @BeforeEach
    void setUp() {
        ML.reset();
        logs.start();
        rootLogs.start();
        ((Logger) LoggerFactory.getLogger(RankingService.LOGGER_NAME)).addAppender(logs);
        ((Logger) LoggerFactory.getLogger(org.slf4j.Logger.ROOT_LOGGER_NAME)).addAppender(rootLogs);
    }

    @AfterEach
    void tearDown() {
        ((Logger) LoggerFactory.getLogger(RankingService.LOGGER_NAME)).detachAppender(logs);
        ((Logger) LoggerFactory.getLogger(org.slf4j.Logger.ROOT_LOGGER_NAME)).detachAppender(rootLogs);
    }

    // --- CA1 / CA3 / CA4: camino feliz por HTTP real contra el stub ------------------------------

    @Test
    @DisplayName("SAPI-57.CA1, CA4 — el backend llama POST /predict del ML por HTTP con cuerpo {} y JSON")
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
    @DisplayName("SAPI-57.CA1, CA4 — forecast_time se reenvía al ML sin modificar")
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
    @DisplayName("SAPI-57.CA3, CA4 — GET /api/v1/ranking devuelve las 50 celdas del ML ordenadas, sin reordenar")
    void returnsFiftyCellsOrderedByScore() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()));

        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of());

        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.headers().firstValue("Content-Type")).hasValueSatisfying(
                type -> assertThat(type).startsWith("application/json"));
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
    @DisplayName("SAPI-57.CA3, CA4 — el cuerpo del ML se reenvía byte a byte, sin reformatear")
    void forwardsExactBytes() throws Exception {
        // Válido para el contrato, pero cualquier re-serialización lo cambiaría: espacios, un escape
        // ó, el número 0.50 y un salto de línea final.
        String real = new String(Fixtures.realRanking(), StandardCharsets.UTF_8);
        byte[] mlBody = ("{ \"nota\" : \"evaluaci\\u00f3n\" ,\n  \"factor\": 0.50,\n" + real.substring(1) + "\n")
                .getBytes(StandardCharsets.UTF_8);
        assertThat(RankingResultValidator.violation(mlBody)).isEmpty();
        ML.reply(Reply.json(200, mlBody));

        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of());

        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).isEqualTo(mlBody);
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
    @DisplayName("SAPI-57.CA3 — el validador de contrato del test detecta cada violación por separado")
    void contractValidatorIsNotVacuous() {
        assertThat(BackendContract.validate(200,
                Fixtures.realRankingWith(root -> root.put("forecast_time", "ayer")))).isNotEmpty();
        assertThat(BackendContract.validate(200,
                Fixtures.realRankingWith(root -> ((ArrayNode) root.get("cells")).remove(0)))).isNotEmpty();
        assertThat(BackendContract.validate(422, "{\"status\":\"error\"}".getBytes(StandardCharsets.UTF_8)))
                .isNotEmpty();
        assertThat(BackendContract.validate(503, "{\"status\":\"error\"}".getBytes(StandardCharsets.UTF_8)))
                .isNotEmpty();
    }

    // --- CA2: errores controlados --------------------------------------------------------------

    static Stream<Arguments> mlFailures() {
        byte[] real = Fixtures.realRanking();
        String ft = "2026-09-01T00:00:00Z";
        return Stream.of(
                Arguments.of("200 no JSON", null, Reply.json(200, "<html>proxy</html>".getBytes(StandardCharsets.UTF_8)),
                        502, "upstream_invalid_response"),
                Arguments.of("200 con 49 celdas", null, Reply.json(200,
                        Fixtures.realRankingWith(root -> ((ArrayNode) root.get("cells")).remove(49))),
                        502, "upstream_invalid_response"),
                Arguments.of("200 con score > 1", null, Reply.json(200, Fixtures.realRankingWith(root -> {
                    for (int i = 0; i < 7; i++) {
                        ((ObjectNode) root.get("cells").get(i)).put("score", 1.5);
                    }
                })), 502, "upstream_invalid_response"),
                Arguments.of("200 con validación científica true", null, Reply.json(200,
                        Fixtures.realRankingWith(root -> root.put("scientific_model_validation", true))),
                        502, "upstream_invalid_response"),
                Arguments.of("200 sin cuerpo", null, Reply.json(200, new byte[0]), 502, "upstream_invalid_response"),
                Arguments.of("201 con ranking válido", null, Reply.json(201, real), 502, "upstream_invalid_response"),
                Arguments.of("302 redirección", null, new Reply(302, new byte[0],
                        Map.of("Location", "http://127.0.0.1:9/predict"), 0, -1), 502, "upstream_invalid_response"),
                Arguments.of("404", null, Reply.json(404, "{\"detail\":\"Not Found\"}".getBytes(StandardCharsets.UTF_8)),
                        502, "upstream_invalid_response"),
                Arguments.of("422 invalid_request con forecast_time", ft,
                        Reply.json(422, Fixtures.mlError("invalid_request")), 422, "invalid_request"),
                Arguments.of("422 invalid_request sin forecast_time", null,
                        Reply.json(422, Fixtures.mlError("invalid_request")), 502, "upstream_invalid_response"),
                Arguments.of("422 sin cuerpo Error", ft, Reply.json(422, "{}".getBytes(StandardCharsets.UTF_8)),
                        502, "upstream_invalid_response"),
                Arguments.of("500 internal_error", null, Reply.json(500, Fixtures.mlError("internal_error")),
                        500, "internal_error"),
                Arguments.of("503 prototype_unavailable", ft, Reply.json(503, Fixtures.mlError("prototype_unavailable")),
                        503, "prototype_unavailable"),
                Arguments.of("503 data_unavailable", null, Reply.json(503, Fixtures.mlError("data_unavailable")),
                        503, "data_unavailable"),
                Arguments.of("503 sin cuerpo Error", null,
                        Reply.json(503, "<html>503</html>".getBytes(StandardCharsets.UTF_8)), 503, "upstream_unavailable"),
                Arguments.of("503 error_type desconocido", null, Reply.json(503, Fixtures.mlError("otro_error")),
                        503, "upstream_unavailable"),
                Arguments.of("502 de un proxy", null, Reply.json(502, new byte[0]), 502, "upstream_invalid_response"));
    }

    @ParameterizedTest(name = "{0} → {3} {4}")
    @MethodSource("mlFailures")
    @DisplayName("SAPI-57.CA2, CA5 — cada respuesta del ML se mapea a un error del contrato y deja su ml_predict")
    void mapsMlFailures(String name, String forecastTime, Reply reply, int status, String errorType)
            throws Exception {
        ML.reply(reply);

        HttpResponse<byte[]> response = get("/api/v1/ranking" + (forecastTime == null ? ""
                : "?forecast_time=" + URLEncoder.encode(forecastTime, StandardCharsets.UTF_8)), Map.of());

        assertError(response, status, errorType);
        ILoggingEvent event = singleEvent("ml_predict");
        assertThat(event.getLevel()).isEqualTo(Level.WARN);
        assertThat(fields(event)).containsEntry("request_id", requestId(response))
                .containsEntry("ml_responded", true)
                .containsEntry("ml_http_status", reply.status())
                .containsEntry("outcome", errorType)
                .containsEntry("backend_http_status", status);
    }

    @Test
    @DisplayName("SAPI-57.CA2 — el ML no envía headers dentro del timeout → 504 upstream_timeout")
    void timeoutBeforeHeadersIs504() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()).delayed(3_000));

        long start = System.nanoTime();
        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of());
        Duration elapsed = Duration.ofNanos(System.nanoTime() - start);

        assertError(response, 504, "upstream_timeout");
        assertThat(elapsed).isLessThan(Duration.ofMillis(2_800));
    }

    @Test
    @DisplayName("SAPI-57.CA2, CA5 — el cuerpo del ML se detiene después de los headers → 504 upstream_timeout")
    void timeoutAfterHeadersIs504() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()).stalledAfter(100, 3_000));

        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of());

        assertError(response, 504, "upstream_timeout");
        assertThat(fields(singleEvent("ml_predict"))).containsEntry("ml_responded", true)
                .containsEntry("ml_http_status", 200)
                .containsEntry("outcome", "upstream_timeout");
    }

    @Test
    @DisplayName("SAPI-57.CA2 — un cuerpo de exactamente 1 MiB se acepta y se reenvía igual")
    void bodyOfExactlyTheMaximumIsAccepted() throws Exception {
        byte[] mlBody = paddedRanking(MlServiceClient.MAX_BODY_BYTES);
        ML.reply(Reply.json(200, mlBody));

        HttpResponse<byte[]> response = get("/api/v1/ranking", Map.of());

        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).isEqualTo(mlBody);
    }

    @Test
    @DisplayName("SAPI-57.CA2, CA5 — un cuerpo válido de 1 MiB + 1 byte → 502 upstream_invalid_response")
    void bodyOverTheMaximumIs502() throws Exception {
        ML.reply(Reply.json(200, paddedRanking(MlServiceClient.MAX_BODY_BYTES + 1)));

        assertError(get("/api/v1/ranking", Map.of()), 502, "upstream_invalid_response");
        assertThat((String) fields(singleEvent("ml_predict")).get("violation")).contains("supera 1048576");
    }

    @Test
    @DisplayName("SAPI-57.CA2 — un 503 del ML con cuerpo mayor al máximo → 502 upstream_invalid_response")
    void oversizedErrorBodyIs502() throws Exception {
        ML.reply(Reply.json(503, paddedRanking(MlServiceClient.MAX_BODY_BYTES + 1)));

        assertError(get("/api/v1/ranking", Map.of()), 502, "upstream_invalid_response");
    }

    @ParameterizedTest(name = "\"{0}\"")
    @ValueSource(strings = {"2026-10-01T18:00:00", "2026-10-01", "mañana", "", "2026-13-01T00:00:00Z",
            "2026-10-01T18:00-03:00", "2026-10-01T18:00:00+0300", "2026-10-01T18:00:00-00:00",
            "2026-10-01T18:00:00Z\n"})
    @DisplayName("SAPI-57.CA2 — forecast_time que no es RFC 3339 → 422 invalid_request sin llamar al ML")
    void invalidForecastTimeIs422WithoutCallingMl(String forecastTime) throws Exception {
        HttpResponse<byte[]> response = get("/api/v1/ranking?forecast_time="
                + URLEncoder.encode(forecastTime, StandardCharsets.UTF_8), Map.of());

        assertError(response, 422, "invalid_request");
        assertThat(ML.received()).isEmpty();
        assertThat(eventsNamed("ml_predict")).isEmpty();
    }

    @Test
    @DisplayName("SAPI-57.CA2 — un parámetro que no se puede decodificar (%ZZ) → 422 con X-Request-Id, sin errores")
    void undecodableParameterIs422() throws Exception {
        RawResponse response = rawGet("/api/v1/ranking?forecast_time=%ZZ", "zz-request-1");

        assertThat(response.status()).isEqualTo(422);
        assertThat(response.header("X-Request-Id")).isEqualTo("zz-request-1");
        assertThat(BackendContract.validate(422, response.body())).isEmpty();
        assertThat(Fixtures.MAPPER.readTree(response.body()).get("error_type").stringValue())
                .isEqualTo("invalid_request");
        assertThat(fields(singleEvent("ranking_request_rejected")))
                .containsEntry("request_id", "zz-request-1")
                .containsEntry("reason", "parametros_no_decodificables");
        assertThat(ML.received()).isEmpty();
        assertThat(rootLogs.list).noneMatch(event -> event.getLevel() == Level.ERROR);
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
                .containsEntry("ml_responded", true)
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
    @DisplayName("SAPI-57.CA5 — un timeout sin respuesta queda en el log con outcome upstream_timeout y nivel WARN")
    void logsTimeouts() throws Exception {
        ML.reply(Reply.json(200, Fixtures.realRanking()).delayed(3_000));

        get("/api/v1/ranking", Map.of());

        ILoggingEvent event = singleEvent("ml_predict");
        assertThat(event.getLevel()).isEqualTo(Level.WARN);
        assertThat(fields(event)).containsEntry("outcome", "upstream_timeout")
                .containsEntry("ml_responded", false)
                .doesNotContainKey("ml_http_status")
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
    @DisplayName("SAPI-57.CA5 — una solicitud rechazada deja un log sin el valor recibido y sin ml_predict")
    void logsRejectedRequestWithoutValue() throws Exception {
        HttpResponse<byte[]> response = get("/api/v1/ranking?forecast_time=" + URLEncoder.encode(
                "x\ny=1", StandardCharsets.UTF_8), Map.of());

        ILoggingEvent event = singleEvent("ranking_request_rejected");
        assertThat(fields(event)).containsEntry("request_id", requestId(response))
                .containsEntry("backend_http_status", 422);
        assertThat(event.getFormattedMessage()).doesNotContain("y=1").doesNotContain("\n");
        assertThat(eventsNamed("ml_predict")).isEmpty();
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
        assertThat(json.get("ml_http_status").isIntegralNumber()).isTrue();
        assertThat(json.get("ml_responded").booleanValue()).isTrue();
        assertThat(json.get("outcome").stringValue()).isEqualTo("ok");
    }

    // --- helpers ---------------------------------------------------------------------------------

    /** El ranking real con espacios al final hasta medir exactamente {@code size} bytes (JSON válido). */
    private static byte[] paddedRanking(int size) {
        byte[] real = Fixtures.realRanking();
        byte[] padded = Arrays.copyOf(real, size);
        Arrays.fill(padded, real.length, size, (byte) ' ');
        return padded;
    }

    private HttpResponse<byte[]> get(String path, Map<String, String> headers)
            throws IOException, InterruptedException {
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path)).GET();
        headers.forEach(request::header);
        try (HttpClient client = HttpClient.newHttpClient()) {
            return client.send(request.build(), HttpResponse.BodyHandlers.ofByteArray());
        }
    }

    /** Respuesta HTTP leída de un socket crudo. */
    private record RawResponse(int status, Map<String, String> headers, byte[] body) {

        String header(String name) {
            return headers.get(name.toLowerCase());
        }
    }

    /** GET por socket crudo: permite enviar una URL que {@link URI} rechazaría (por ejemplo {@code %ZZ}). */
    private RawResponse rawGet(String pathAndQuery, String requestId) throws IOException {
        try (Socket socket = new Socket(InetAddress.getLoopbackAddress(), port)) {
            socket.setSoTimeout(10_000);
            OutputStream out = socket.getOutputStream();
            out.write(("GET " + pathAndQuery + " HTTP/1.1\r\nHost: 127.0.0.1\r\nX-Request-Id: " + requestId
                    + "\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
            out.flush();
            InputStream in = socket.getInputStream();
            ByteArrayOutputStream all = new ByteArrayOutputStream();
            in.transferTo(all);
            byte[] raw = all.toByteArray();
            String text = new String(raw, StandardCharsets.ISO_8859_1);
            int split = text.indexOf("\r\n\r\n");
            String[] lines = text.substring(0, split).split("\r\n");
            Map<String, String> headers = new LinkedHashMap<>();
            for (int i = 1; i < lines.length; i++) {
                int colon = lines[i].indexOf(':');
                headers.put(lines[i].substring(0, colon).trim().toLowerCase(), lines[i].substring(colon + 1).trim());
            }
            byte[] body = Arrays.copyOfRange(raw, split + 4, raw.length);
            if ("chunked".equalsIgnoreCase(headers.get("transfer-encoding"))) {
                body = dechunk(body);
            }
            return new RawResponse(Integer.parseInt(lines[0].split(" ")[1]), headers, body);
        }
    }

    private static byte[] dechunk(byte[] chunked) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int pos = 0;
        while (true) {
            int lineEnd = indexOf(chunked, pos);
            int size = Integer.parseInt(new String(chunked, pos, lineEnd - pos, StandardCharsets.US_ASCII).trim(), 16);
            if (size == 0) {
                return out.toByteArray();
            }
            out.write(chunked, lineEnd + 2, size);
            pos = lineEnd + 2 + size + 2;
        }
    }

    private static int indexOf(byte[] data, int from) {
        for (int i = from; i < data.length - 1; i++) {
            if (data[i] == '\r' && data[i + 1] == '\n') {
                return i;
            }
        }
        throw new IllegalStateException("respuesta chunked incompleta");
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

    private List<ILoggingEvent> eventsNamed(String eventName) {
        return logs.list.stream().filter(event -> eventName.equals(fields(event).get("event"))).toList();
    }

    private ILoggingEvent singleEvent(String eventName) {
        List<ILoggingEvent> matching = eventsNamed(eventName);
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

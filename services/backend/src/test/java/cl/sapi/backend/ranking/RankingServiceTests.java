package cl.sapi.backend.ranking;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.net.URI;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.springframework.web.client.RestClient;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import cl.sapi.backend.ranking.ml.MlCallException;
import cl.sapi.backend.ranking.ml.MlResponse;
import cl.sapi.backend.ranking.ml.MlServiceClient;
import cl.sapi.backend.ranking.ml.MlServiceProperties;
import cl.sapi.backend.ranking.persistence.RankingPersistenceService;

/** {@link RankingService} con un cliente ML falso: rutas que no se provocan por HTTP (SAPI-57.CA2, CA5). */
class RankingServiceTests {

    private final ListAppender<ILoggingEvent> logs = new ListAppender<>();

    @BeforeEach
    void attach() {
        logs.start();
        ((Logger) LoggerFactory.getLogger(RankingService.LOGGER_NAME)).addAppender(logs);
    }

    @AfterEach
    void detach() {
        ((Logger) LoggerFactory.getLogger(RankingService.LOGGER_NAME)).detachAppender(logs);
    }

    @Test
    @DisplayName("SAPI-57.CA2, CA5 — un error inesperado → 500 internal_error y un único ml_predict en ERROR con la causa")
    void unexpectedErrorIsInternalError() {
        RankingOutcome outcome = service(() -> {
            throw new IllegalStateException("fallo interno");
        }).rank(null, "req-1");

        assertThat(outcome.status()).isEqualTo(500);
        assertThat(outcome.error()).isEqualTo(RankingError.INTERNAL_ERROR);
        ILoggingEvent event = singleMlPredict();
        assertThat(event.getLevel()).isEqualTo(Level.ERROR);
        assertThat(event.getThrowableProxy()).isNotNull();
        assertThat(fields(event)).containsEntry("outcome", "internal_error")
                .containsEntry("error_class", "IllegalStateException")
                .containsEntry("ml_responded", false)
                .containsEntry("backend_http_status", 500);
        assertThat(event.getFormattedMessage()).doesNotContain("fallo interno");
    }

    @Test
    @DisplayName("SAPI-57.CA2, CA5 — corte a mitad del cuerpo → 503 upstream_unavailable con ml_http_status")
    void midBodyCutKeepsTheStatus() {
        RankingOutcome outcome = service(() -> {
            throw new MlCallException(MlCallException.Kind.UNAVAILABLE, 200, new IOException("closed"));
        }).rank(null, "req-2");

        assertThat(outcome.error()).isEqualTo(RankingError.UPSTREAM_UNAVAILABLE);
        assertThat(fields(singleMlPredict())).containsEntry("ml_responded", true)
                .containsEntry("ml_http_status", 200)
                .containsEntry("outcome", "upstream_unavailable");
    }

    @Test
    @DisplayName("SAPI-57.CA2, CA5 — plazo vencido durante el cuerpo → 504 upstream_timeout con ml_http_status")
    void bodyTimeoutIs504() {
        RankingOutcome outcome = service(() -> {
            throw new MlCallException(MlCallException.Kind.TIMEOUT, 200, new IOException("closed"));
        }).rank(null, "req-3");

        assertThat(outcome.status()).isEqualTo(504);
        assertThat(fields(singleMlPredict())).containsEntry("ml_http_status", 200)
                .containsEntry("outcome", "upstream_timeout");
    }

    @Test
    @DisplayName("SAPI-57.CA5 — un model_version con caracteres inseguros no se escribe en el log")
    void unsafeModelVersionIsNotLogged() {
        byte[] body = Fixtures.realRankingWith(root -> root.put("model_version", "v1 ‮\nmalo"));

        RankingOutcome outcome = service(() -> new MlResponse(200, body, false)).rank(null, "req-4");

        assertThat(outcome.status()).isEqualTo(200);
        assertThat(outcome.body()).isEqualTo(body);
        ILoggingEvent event = singleMlPredict();
        assertThat(fields(event)).containsEntry("model_version", "[omitido]");
        assertThat(event.getFormattedMessage()).doesNotContain("malo").doesNotContain("\n");
    }

    @Test
    @DisplayName("SAPI-57.CA5 — logfmt escapa comillas, controles, formato, separadores y surrogates sueltos")
    void logfmtEscapesUnsafeCharacters() {
        assertThat(RankingService.logfmt("prototype_model_d_v1")).isEqualTo("prototype_model_d_v1");
        assertThat(RankingService.logfmt("a b\"c\\d\ne f‮g\uD800"))
                .isEqualTo("\"a b\\\"c\\\\d\\u000ae\\u2028f\\u202eg\\ud800\"");
    }

    @Test
    @DisplayName("SAPI-59 — tras validación 200, write-through llama a persistencia antes del ranking")
    void successfulRankingPersistsWriteThrough() {
        java.util.concurrent.atomic.AtomicInteger persists = new java.util.concurrent.atomic.AtomicInteger();
        RankingPersistenceService tracking = new RankingPersistenceService(null) {
            @Override
            public long persist(tools.jackson.databind.JsonNode ranking) {
                persists.incrementAndGet();
                return 42L;
            }
        };
        RankingOutcome outcome = service(() -> new MlResponse(200, Fixtures.realRanking(), false), tracking)
                .rank(null, "req-persist");

        assertThat(outcome.status()).isEqualTo(200);
        assertThat(outcome.body()).isEqualTo(Fixtures.realRanking());
        assertThat(persists.get()).isEqualTo(1);
        assertThat(fields(singleMlPredict())).containsEntry("ejecucion_id", 42L);
    }

    private static RankingService service(Supplier<MlResponse> behavior) {
        return service(behavior, RankingPersistenceService.noOp());
    }

    private static RankingService service(Supplier<MlResponse> behavior, RankingPersistenceService persistence) {
        MlServiceClient client = new MlServiceClient(RestClient.builder(), new MlServiceProperties(
                URI.create("http://127.0.0.1:9"), Duration.ofSeconds(1), Duration.ofSeconds(1))) {
            @Override
            public MlResponse predict(String forecastTime, String requestId) {
                return behavior.get();
            }
        };
        return new RankingService(client, persistence);
    }

    private ILoggingEvent singleMlPredict() {
        List<ILoggingEvent> events = logs.list.stream()
                .filter(event -> "ml_predict".equals(fields(event).get("event")))
                .toList();
        assertThat(events).hasSize(1);
        return events.get(0);
    }

    private static Map<String, Object> fields(ILoggingEvent event) {
        Map<String, Object> fields = new LinkedHashMap<>();
        if (event.getKeyValuePairs() != null) {
            event.getKeyValuePairs().forEach(pair -> fields.put(pair.key, pair.value));
        }
        return fields;
    }
}

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
import cl.sapi.backend.ranking.persistence.FirmsOriginPolicy;
import cl.sapi.backend.ranking.persistence.RankingPersistenceException;
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
        byte[] body = Fixtures.realRankingWith(root -> {
            root.put("model_version", "v1 ‮\nmalo");
            root.put("firms_origin", "reproducibility");
        });

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
    @DisplayName("SAPI-59 — tras validación 200 con origen autorizado, write-through llama a persistencia")
    void successfulRankingPersistsWriteThrough() {
        java.util.concurrent.atomic.AtomicInteger persists = new java.util.concurrent.atomic.AtomicInteger();
        RankingPersistenceService tracking = new RankingPersistenceService(null, null) {
            @Override
            public long persist(tools.jackson.databind.JsonNode ranking) {
                persists.incrementAndGet();
                return 42L;
            }
        };
        byte[] body = Fixtures.realRankingWith(root -> root.put("firms_origin", "reproducibility"));
        RankingOutcome outcome = service(() -> new MlResponse(200, body, false), tracking)
                .rank(null, "req-persist");

        assertThat(outcome.status()).isEqualTo(200);
        assertThat(outcome.body()).isEqualTo(body);
        assertThat(persists.get()).isEqualTo(1);
        assertThat(fields(singleMlPredict())).containsEntry("ejecucion_id", 42L);
    }

    @Test
    @DisplayName("SAPI-59 — fallo de persistencia tras ranking ML válido → 500 INTERNAL_ERROR (fail-closed)")
    void persistenceFailureIsInternalErrorNotRanking200() {
        RankingPersistenceService failing = new RankingPersistenceService(null, null) {
            @Override
            public long persist(tools.jackson.databind.JsonNode ranking) {
                throw new RankingPersistenceException("fallo de persistencia controlado");
            }
        };
        byte[] mlBody = Fixtures.realRankingWith(root -> root.put("firms_origin", "reproducibility"));
        RankingOutcome outcome = service(() -> new MlResponse(200, mlBody, false), failing)
                .rank(null, "req-persist-fail");

        assertThat(outcome.status()).isEqualTo(500);
        assertThat(outcome.error()).isEqualTo(RankingError.INTERNAL_ERROR);
        assertThat(outcome.body()).isNotEqualTo(mlBody);
        ILoggingEvent event = singleMlPredict();
        assertThat(event.getLevel()).isEqualTo(Level.ERROR);
        assertThat(fields(event)).containsEntry("outcome", "internal_error")
                .containsEntry("error_class", "RankingPersistenceException")
                .containsEntry("backend_http_status", 500)
                .containsEntry("ml_http_status", 200);
        assertThat(event.getFormattedMessage()).doesNotContain("fallo de persistencia controlado");
    }

    // --- SAPI F1 (gate A3, Jira #10134/#10135): procedencia ------------------------------------

    @Test
    @DisplayName("F1 — firms_origin ausente → 500 internal_error, cero llamadas a persistencia")
    void missingFirmsOriginIsRejectedWithoutPersisting() {
        java.util.concurrent.atomic.AtomicInteger persists = new java.util.concurrent.atomic.AtomicInteger();
        RankingPersistenceService tracking = new RankingPersistenceService(null, null) {
            @Override
            public long persist(tools.jackson.databind.JsonNode ranking) {
                persists.incrementAndGet();
                return 1L;
            }
        };

        RankingOutcome outcome = service(() -> new MlResponse(200, Fixtures.realRanking(), false), tracking)
                .rank(null, "req-no-origin");

        assertThat(outcome.status()).isEqualTo(500);
        assertThat(outcome.error()).isEqualTo(RankingError.INTERNAL_ERROR);
        assertThat(persists.get()).isZero();
        ILoggingEvent event = singleMlPredict();
        assertThat(fields(event)).containsEntry("outcome", "internal_error")
                .containsEntry("persistence_policy", "rejected")
                .containsEntry("firms_origin_observed", "[ausente]")
                .containsEntry("firms_origin_policy_effective", List.of("current", "reproducibility"))
                .containsEntry("backend_http_status", 500);
        assertThat(event.getThrowableProxy()).isNull();
    }

    @Test
    @DisplayName("F1 — firms_origin fuera de la política configurada → 500, cero escrituras")
    void disallowedFirmsOriginIsRejectedWithoutPersisting() {
        java.util.concurrent.atomic.AtomicInteger persists = new java.util.concurrent.atomic.AtomicInteger();
        RankingPersistenceService tracking = new RankingPersistenceService(null, null) {
            @Override
            public long persist(tools.jackson.databind.JsonNode ranking) {
                persists.incrementAndGet();
                return 1L;
            }
        };
        byte[] body = Fixtures.realRankingWith(root -> root.put("firms_origin", "baseline"));

        RankingOutcome outcome = service(() -> new MlResponse(200, body, false), tracking, policyAllowing("current"))
                .rank(null, "req-disallowed-origin");

        assertThat(outcome.status()).isEqualTo(500);
        assertThat(persists.get()).isZero();
        assertThat(fields(singleMlPredict())).containsEntry("persistence_policy", "rejected")
                .containsEntry("firms_origin_observed", "baseline")
                .containsEntry("firms_origin_policy_effective", List.of("current"));
    }

    private static RankingService service(Supplier<MlResponse> behavior) {
        return service(behavior, RankingPersistenceService.noOp());
    }

    private static RankingService service(Supplier<MlResponse> behavior, RankingPersistenceService persistence) {
        return service(behavior, persistence, policyAllowing("current", "reproducibility"));
    }

    private static RankingService service(
            Supplier<MlResponse> behavior, RankingPersistenceService persistence, FirmsOriginPolicy policy) {
        MlServiceClient client = new MlServiceClient(RestClient.builder(), new MlServiceProperties(
                URI.create("http://127.0.0.1:9"), Duration.ofSeconds(1), Duration.ofSeconds(1))) {
            @Override
            public MlResponse predict(String forecastTime, String requestId) {
                return behavior.get();
            }
        };
        return new RankingService(client, persistence, policy);
    }

    private static FirmsOriginPolicy policyAllowing(String... values) {
        FirmsOriginPolicy policy = new FirmsOriginPolicy();
        policy.setAllowedFirmsOrigins(List.of(values));
        policy.validate();
        return policy;
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

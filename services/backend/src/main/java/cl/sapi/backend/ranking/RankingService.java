package cl.sapi.backend.ranking;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.regex.Pattern;

import org.jspecify.annotations.Nullable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.event.Level;
import org.slf4j.spi.LoggingEventBuilder;
import org.springframework.stereotype.Service;

import cl.sapi.backend.ranking.ml.MlCallException;
import cl.sapi.backend.ranking.ml.MlResponse;
import cl.sapi.backend.ranking.ml.MlServiceClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * Obtiene el ranking del servicio ML y decide la respuesta del backend (SAPI-57, ADR-010).
 *
 * <p>Un 200 del ML se reenvía solo si cumple el contrato; nunca se responde 200 con un resultado
 * inválido (RN-09). Cada llamada deja una línea de log estructurada {@code ml_predict} (SAPI-57.CA5) con
 * el {@code request_id}, la latencia y el resultado, sin scores ni celdas.
 */
@Service
public class RankingService {

    /** Logger de las llamadas al servicio ML. */
    public static final String LOGGER_NAME = "sapi.backend.ml";

    private static final Logger LOG = LoggerFactory.getLogger(LOGGER_NAME);
    private static final JsonMapper MAPPER = JsonMapper.builder().build();
    private static final Pattern PLAIN_LOG_VALUE = Pattern.compile("[A-Za-z0-9._:+/-]+");

    /** Errores del ML que se propagan con su mismo {@code error_type} (backend.v0.yaml, 503). */
    private static final Map<String, RankingError> PROPAGATED_503 = Map.of(
            RankingError.PROTOTYPE_UNAVAILABLE.type(), RankingError.PROTOTYPE_UNAVAILABLE,
            RankingError.DATA_UNAVAILABLE.type(), RankingError.DATA_UNAVAILABLE);

    private final MlServiceClient client;

    public RankingService(MlServiceClient client) {
        this.client = client;
    }

    /**
     * Pide el ranking al ML.
     *
     * @param forecastTime {@code forecast_time} ya validado, o null para el último bucket real
     * @param requestId identificador de correlación
     */
    public RankingOutcome rank(@Nullable String forecastTime, String requestId) {
        Map<String, Object> fields = new LinkedHashMap<>();
        fields.put("request_id", requestId);
        fields.put("forecast_time_requested", forecastTime == null ? "latest" : forecastTime);
        long start = System.nanoTime();
        RankingOutcome outcome;
        try {
            MlResponse response = client.predict(forecastTime, requestId);
            fields.put("ml_http_status", response.status());
            outcome = interpret(response, fields);
        }
        catch (MlCallException ex) {
            fields.put("ml_http_status", "none");
            outcome = RankingOutcome.error(ex.kind() == MlCallException.Kind.TIMEOUT
                    ? RankingError.UPSTREAM_TIMEOUT : RankingError.UPSTREAM_UNAVAILABLE);
        }
        fields.put("ml_latency_ms", (System.nanoTime() - start) / 1_000_000);
        fields.put("outcome", outcome.outcomeName());
        fields.put("backend_http_status", outcome.status());
        log(outcome.error() == null ? Level.INFO : Level.WARN, "ml_predict", fields);
        return outcome;
    }

    /**
     * Rechaza una solicitud inválida sin llamar al ML (422). El log no incluye el valor recibido.
     *
     * @param reason motivo fijo para el log, nunca el valor enviado por el cliente
     */
    public RankingOutcome reject(String requestId, String reason) {
        RankingOutcome outcome = RankingOutcome.error(RankingError.INVALID_REQUEST);
        Map<String, Object> fields = new LinkedHashMap<>();
        fields.put("request_id", requestId);
        fields.put("outcome", outcome.outcomeName());
        fields.put("backend_http_status", outcome.status());
        fields.put("reason", reason);
        log(Level.WARN, "ranking_request_rejected", fields);
        return outcome;
    }

    private static RankingOutcome interpret(MlResponse response, Map<String, Object> fields) {
        switch (response.status()) {
            case 200 -> {
                Optional<String> violation = response.bodyTooLarge()
                        ? Optional.of("el cuerpo supera " + MlServiceClient.MAX_BODY_BYTES + " bytes")
                        : RankingResultValidator.violation(response.body());
                if (violation.isPresent()) {
                    fields.put("violation", violation.get());
                    return RankingOutcome.error(RankingError.UPSTREAM_INVALID_RESPONSE);
                }
                JsonNode root = MAPPER.readTree(response.body());
                fields.put("model_version", root.get("model_version").stringValue());
                fields.put("forecast_time", root.get("forecast_time").stringValue());
                fields.put("inputs_fingerprint", root.get("inputs_fingerprint").stringValue());
                return RankingOutcome.ranking(response.body());
            }
            case 422 -> {
                return RankingResultValidator.errorType(response.body())
                        .filter(RankingError.INVALID_REQUEST.type()::equals)
                        .map(type -> RankingOutcome.error(RankingError.INVALID_REQUEST))
                        .orElseGet(() -> RankingOutcome.error(RankingError.UPSTREAM_INVALID_RESPONSE));
            }
            case 500 -> {
                return RankingOutcome.error(RankingError.INTERNAL_ERROR);
            }
            case 503 -> {
                return RankingResultValidator.errorType(response.body())
                        .map(PROPAGATED_503::get)
                        .map(RankingOutcome::error)
                        .orElseGet(() -> RankingOutcome.error(RankingError.UPSTREAM_UNAVAILABLE));
            }
            default -> {
                return RankingOutcome.error(RankingError.UPSTREAM_INVALID_RESPONSE);
            }
        }
    }

    private static void log(Level level, String event, Map<String, Object> fields) {
        LoggingEventBuilder builder = LOG.atLevel(level).addKeyValue("event", event);
        StringBuilder message = new StringBuilder(event);
        fields.forEach((key, value) -> {
            builder.addKeyValue(key, value);
            message.append(' ').append(key).append('=').append(logfmt(String.valueOf(value)));
        });
        builder.log(message.toString());
    }

    /** Valor logfmt: tal cual si es seguro; si no, entre comillas y con caracteres de control escapados. */
    private static String logfmt(String value) {
        if (PLAIN_LOG_VALUE.matcher(value).matches()) {
            return value;
        }
        StringBuilder quoted = new StringBuilder("\"");
        for (char c : value.toCharArray()) {
            if (c == '"' || c == '\\') {
                quoted.append('\\').append(c);
            }
            else if (Character.isISOControl(c)) {
                quoted.append(String.format(Locale.ROOT, "\\u%04x", (int) c));
            }
            else {
                quoted.append(c);
            }
        }
        return quoted.append('"').toString();
    }
}

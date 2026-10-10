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
import cl.sapi.backend.ranking.persistence.RankingPersistenceService;
import tools.jackson.databind.JsonNode;

/**
 * Obtiene el ranking del servicio ML, lo valida (SAPI-57) y lo persiste (SAPI-59, ADR-007).
 *
 * <p>Un 200 del ML se reenvía solo si cumple el contrato y la persistencia write-through
 * termina bien; nunca se responde 200 con un resultado inválido (RN-09) ni sin traza en
 * {@code ejecuciones}/{@code predicciones_celda} cuando la base está configurada.
 * Cada llamada deja exactamente un evento de log estructurado {@code ml_predict}
 * (SAPI-57.CA5) con el {@code request_id}, la latencia del ML y el resultado, sin scores ni celdas.
 */
@Service
public class RankingService {

    /** Logger de las llamadas al servicio ML. */
    public static final String LOGGER_NAME = "sapi.backend.ml";

    private static final Logger LOG = LoggerFactory.getLogger(LOGGER_NAME);
    private static final Pattern PLAIN_LOG_VALUE = Pattern.compile("[A-Za-z0-9._:+/-]+");
    private static final Pattern SAFE_MODEL_VERSION = Pattern.compile("[A-Za-z0-9._:+-]{1,128}");

    /** Errores del ML que se propagan con su mismo {@code error_type} (backend.v0.yaml, 503). */
    private static final Map<String, RankingError> PROPAGATED_503 = Map.of(
            RankingError.PROTOTYPE_UNAVAILABLE.type(), RankingError.PROTOTYPE_UNAVAILABLE,
            RankingError.DATA_UNAVAILABLE.type(), RankingError.DATA_UNAVAILABLE);

    private final MlServiceClient client;
    private final RankingPersistenceService persistence;

    public RankingService(MlServiceClient client, RankingPersistenceService persistence) {
        this.client = client;
        this.persistence = persistence;
    }

    /**
     * Pide el ranking al ML y entrega la respuesta del backend: el cuerpo del ML validado o un error.
     *
     * @param forecastTime {@code forecast_time} ya validado, o null para el último bucket real
     * @param requestId identificador de correlación
     */
    public RankingOutcome rank(@Nullable String forecastTime, String requestId) {
        Map<String, Object> details = new LinkedHashMap<>();
        long start = System.nanoTime();
        long latencyMs = -1;
        @Nullable Integer httpStatus = null;
        RankingOutcome outcome;
        Level level = Level.WARN;
        @Nullable Throwable cause = null;
        try {
            MlResponse response = client.predict(forecastTime, requestId);
            latencyMs = elapsedMs(start);
            httpStatus = response.status();
            outcome = interpret(response, forecastTime != null, details);
            if (outcome.error() == null) {
                level = Level.INFO;
            }
        }
        catch (MlCallException ex) {
            latencyMs = elapsedMs(start);
            httpStatus = ex.httpStatus();
            outcome = RankingOutcome.error(ex.kind() == MlCallException.Kind.TIMEOUT
                    ? RankingError.UPSTREAM_TIMEOUT : RankingError.UPSTREAM_UNAVAILABLE);
        }
        catch (RuntimeException ex) {
            if (latencyMs < 0) {
                latencyMs = elapsedMs(start);
            }
            outcome = RankingOutcome.error(RankingError.INTERNAL_ERROR);
            details.put("error_class", ex.getClass().getSimpleName());
            level = Level.ERROR;
            cause = ex;
        }
        Map<String, Object> fields = new LinkedHashMap<>();
        fields.put("request_id", requestId);
        fields.put("forecast_time_requested", forecastTime == null ? "latest" : forecastTime);
        fields.put("ml_responded", httpStatus != null);
        if (httpStatus != null) {
            fields.put("ml_http_status", httpStatus);
        }
        fields.put("ml_latency_ms", latencyMs);
        fields.put("outcome", outcome.outcomeName());
        fields.put("backend_http_status", outcome.status());
        fields.putAll(details);
        log(level, "ml_predict", fields, cause);
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
        log(Level.WARN, "ranking_request_rejected", fields, null);
        return outcome;
    }

    private RankingOutcome interpret(MlResponse response, boolean forecastTimeSent, Map<String, Object> details) {
        if (response.bodyTooLarge()) {
            details.put("violation", "el cuerpo supera " + MlServiceClient.MAX_BODY_BYTES + " bytes");
            return RankingOutcome.error(RankingError.UPSTREAM_INVALID_RESPONSE);
        }
        switch (response.status()) {
            case 200 -> {
                RankingResultValidator.Validation validation = RankingResultValidator.validate(response.body());
                if (validation.violation().isPresent()) {
                    details.put("violation", validation.violation().get());
                    return RankingOutcome.error(RankingError.UPSTREAM_INVALID_RESPONSE);
                }
                JsonNode ranking = validation.ranking();
                String modelVersion = ranking.get("model_version").stringValue();
                details.put("model_version",
                        SAFE_MODEL_VERSION.matcher(modelVersion).matches() ? modelVersion : "[omitido]");
                details.put("forecast_time", ranking.get("forecast_time").stringValue());
                details.put("inputs_fingerprint", ranking.get("inputs_fingerprint").stringValue());
                // SAPI-59: write-through tras validación SAPI-57 y antes de RankingOutcome.ranking.
                long executionId = persistence.persist(ranking);
                if (executionId >= 0) {
                    details.put("ejecucion_id", executionId);
                }
                return RankingOutcome.ranking(response.body());
            }
            case 422 -> {
                if (!forecastTimeSent) {
                    details.put("violation", "el ML respondió 422 a una petición sin forecast_time");
                    return RankingOutcome.error(RankingError.UPSTREAM_INVALID_RESPONSE);
                }
                Optional<String> type = RankingResultValidator.errorType(response.body());
                if (type.filter(RankingError.INVALID_REQUEST.type()::equals).isPresent()) {
                    return RankingOutcome.error(RankingError.INVALID_REQUEST);
                }
                details.put("violation", "422 sin cuerpo Error invalid_request");
                return RankingOutcome.error(RankingError.UPSTREAM_INVALID_RESPONSE);
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
                details.put("violation", "código HTTP no previsto: " + response.status());
                return RankingOutcome.error(RankingError.UPSTREAM_INVALID_RESPONSE);
            }
        }
    }

    private static long elapsedMs(long start) {
        return (System.nanoTime() - start) / 1_000_000;
    }

    private static void log(Level level, String event, Map<String, Object> fields, @Nullable Throwable cause) {
        LoggingEventBuilder builder = LOG.atLevel(level).addKeyValue("event", event);
        if (cause != null) {
            builder.setCause(cause);
        }
        StringBuilder message = new StringBuilder(event);
        fields.forEach((key, value) -> {
            builder.addKeyValue(key, value);
            message.append(' ').append(key).append('=').append(logfmt(String.valueOf(value)));
        });
        builder.log(message.toString());
    }

    /**
     * Valor logfmt: tal cual si es seguro; si no, entre comillas y con escapes para comillas, barras,
     * caracteres de control o de formato, separadores de línea y párrafo, y surrogates sueltos.
     */
    static String logfmt(String value) {
        if (PLAIN_LOG_VALUE.matcher(value).matches()) {
            return value;
        }
        StringBuilder quoted = new StringBuilder("\"");
        value.codePoints().forEach(codePoint -> {
            if (codePoint == '"' || codePoint == '\\') {
                quoted.append('\\').appendCodePoint(codePoint);
            }
            else if (mustEscape(codePoint)) {
                quoted.append(codePoint <= 0xFFFF
                        ? String.format(Locale.ROOT, "\\u%04x", codePoint)
                        : String.format(Locale.ROOT, "\\U%08x", codePoint));
            }
            else {
                quoted.appendCodePoint(codePoint);
            }
        });
        return quoted.append('"').toString();
    }

    private static boolean mustEscape(int codePoint) {
        int type = Character.getType(codePoint);
        return Character.isISOControl(codePoint)
                || type == Character.FORMAT
                || type == Character.LINE_SEPARATOR
                || type == Character.PARAGRAPH_SEPARATOR
                || type == Character.SURROGATE;
    }
}

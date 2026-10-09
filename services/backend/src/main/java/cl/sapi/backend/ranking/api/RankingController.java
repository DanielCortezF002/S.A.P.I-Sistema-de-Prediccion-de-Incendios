package cl.sapi.backend.ranking.api;

import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.UUID;
import java.util.regex.Pattern;

import org.jspecify.annotations.Nullable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import cl.sapi.backend.ranking.RankingError;
import cl.sapi.backend.ranking.RankingOutcome;
import cl.sapi.backend.ranking.RankingService;
import cl.sapi.backend.ranking.ml.MlServiceClient;

/**
 * {@code GET /api/v1/ranking} (contracts/openapi/backend.v0.yaml, SAPI-57.CA3).
 *
 * <p>Valida {@code forecast_time}, pide el ranking al servicio ML y devuelve su cuerpo sin reordenar ni
 * reformatear. Toda respuesta lleva {@code X-Request-Id}: el recibido si es seguro, o uno nuevo.
 */
@RestController
public class RankingController {

    private static final Logger LOG = LoggerFactory.getLogger(RankingController.class);
    private static final Pattern SAFE_REQUEST_ID = Pattern.compile("[A-Za-z0-9._:-]{1,64}");

    private final RankingService service;

    public RankingController(RankingService service) {
        this.service = service;
    }

    @GetMapping(path = "/api/v1/ranking", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<byte[]> ranking(
            @RequestParam(name = "forecast_time", required = false) @Nullable String forecastTime,
            @RequestHeader(name = MlServiceClient.REQUEST_ID_HEADER, required = false) @Nullable String requestId) {
        String id = requestId != null && SAFE_REQUEST_ID.matcher(requestId).matches()
                ? requestId : UUID.randomUUID().toString();
        RankingOutcome outcome;
        try {
            outcome = forecastTime != null && !isOffsetDateTime(forecastTime)
                    ? service.reject(id, "forecast_time_invalido")
                    : service.rank(forecastTime, id);
        }
        catch (RuntimeException ex) {
            LOG.error("ranking_unexpected_error request_id={}", id, ex);
            outcome = RankingOutcome.error(RankingError.INTERNAL_ERROR);
        }
        return ResponseEntity.status(outcome.status())
                .header(MlServiceClient.REQUEST_ID_HEADER, id)
                .contentType(MediaType.APPLICATION_JSON)
                .body(outcome.body());
    }

    /** ISO 8601 con zona horaria explícita, la misma regla que aplica el servicio ML. */
    private static boolean isOffsetDateTime(String value) {
        try {
            OffsetDateTime.parse(value, DateTimeFormatter.ISO_OFFSET_DATE_TIME);
            return true;
        }
        catch (DateTimeParseException ex) {
            return false;
        }
    }
}

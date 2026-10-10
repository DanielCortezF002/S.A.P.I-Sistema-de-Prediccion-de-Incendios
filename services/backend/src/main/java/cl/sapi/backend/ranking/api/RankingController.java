package cl.sapi.backend.ranking.api;

import java.util.UUID;
import java.util.regex.Pattern;

import org.apache.tomcat.util.http.InvalidParameterException;
import org.jspecify.annotations.Nullable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import cl.sapi.backend.ranking.ForecastTime;
import cl.sapi.backend.ranking.RankingError;
import cl.sapi.backend.ranking.RankingOutcome;
import cl.sapi.backend.ranking.RankingService;
import cl.sapi.backend.ranking.ml.MlServiceClient;
import jakarta.servlet.http.HttpServletRequest;

/**
 * {@code GET /api/v1/ranking} (contracts/openapi/backend.v0.yaml, SAPI-57.CA3).
 *
 * <p>Valida {@code forecast_time} (RFC 3339, un pre-filtro: la validación final la hace el servicio ML),
 * pide el ranking al ML y devuelve su cuerpo sin reordenar ni reformatear. Cada respuesta de este handler
 * lleva {@code X-Request-Id}: el recibido si es seguro, o uno nuevo. Las respuestas que Spring genera
 * antes de llegar aquí (405, 406, 404) quedan fuera del contrato.
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
        String id = requestId(requestId);
        RankingOutcome outcome;
        try {
            outcome = forecastTime != null && !ForecastTime.isValid(forecastTime)
                    ? service.reject(id, "forecast_time_invalido")
                    : service.rank(forecastTime, id);
        }
        catch (RuntimeException ex) {
            LOG.atError().addKeyValue("event", "ranking_unexpected_error").addKeyValue("request_id", id)
                    .setCause(ex).log("ranking_unexpected_error request_id=" + id);
            outcome = RankingOutcome.error(RankingError.INTERNAL_ERROR);
        }
        return respond(outcome, id);
    }

    /**
     * Parámetros de query que Tomcat no puede decodificar (por ejemplo {@code %ZZ}) o que exceden su
     * límite: es un {@code forecast_time} inválido para el contrato (422), no un 400 genérico. No se leen
     * los parámetros, porque Tomcat relanzaría el mismo error.
     */
    @ExceptionHandler(InvalidParameterException.class)
    public ResponseEntity<byte[]> undecodableParameters(HttpServletRequest request) {
        String id = requestId(request.getHeader(MlServiceClient.REQUEST_ID_HEADER));
        return respond(service.reject(id, "parametros_no_decodificables"), id);
    }

    private static String requestId(@Nullable String received) {
        return received != null && SAFE_REQUEST_ID.matcher(received).matches()
                ? received : UUID.randomUUID().toString();
    }

    private static ResponseEntity<byte[]> respond(RankingOutcome outcome, String requestId) {
        return ResponseEntity.status(outcome.status())
                .header(MlServiceClient.REQUEST_ID_HEADER, requestId)
                .contentType(MediaType.APPLICATION_JSON)
                .body(outcome.body());
    }
}

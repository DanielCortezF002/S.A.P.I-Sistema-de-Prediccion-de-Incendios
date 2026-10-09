package cl.sapi.backend.ranking;

import java.util.LinkedHashMap;
import java.util.Map;

import org.jspecify.annotations.Nullable;

import tools.jackson.databind.json.JsonMapper;

/**
 * Respuesta final de {@code GET /api/v1/ranking}: el código HTTP y los bytes del cuerpo.
 *
 * @param status código HTTP del backend
 * @param body cuerpo JSON: el {@code RankingResult} del ML sin cambios, o un cuerpo {@code Error}
 * @param error el error, o null si el ranking es válido
 */
public record RankingOutcome(int status, byte[] body, @Nullable RankingError error) {

    private static final JsonMapper MAPPER = JsonMapper.builder().build();

    /** Ranking válido: se reenvían los bytes del ML sin reordenar ni reformatear. */
    public static RankingOutcome ranking(byte[] mlBody) {
        return new RankingOutcome(200, mlBody, null);
    }

    /** Error del contrato con mensaje genérico ({@code status}, {@code error_type}, {@code message}). */
    public static RankingOutcome error(RankingError error) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("status", "error");
        body.put("error_type", error.type());
        body.put("message", error.message());
        return new RankingOutcome(error.status(), MAPPER.writeValueAsBytes(body), error);
    }

    /** Valor de {@code outcome} en el log: {@code ok} o el {@code error_type}. */
    public String outcomeName() {
        return error == null ? "ok" : error.type();
    }
}

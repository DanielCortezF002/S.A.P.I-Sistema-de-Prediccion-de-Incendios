package cl.sapi.backend.ranking.ml;

/**
 * Respuesta HTTP del servicio ML tal como llegó: código y bytes del cuerpo, sin interpretar.
 *
 * @param status código HTTP
 * @param body cuerpo crudo; vacío si el ML no envió cuerpo o si superó el tamaño máximo
 * @param bodyTooLarge true si el cuerpo superó {@link MlServiceClient#MAX_BODY_BYTES}
 */
public record MlResponse(int status, byte[] body, boolean bodyTooLarge) {
}

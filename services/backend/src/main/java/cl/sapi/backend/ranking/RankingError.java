package cl.sapi.backend.ranking;

/**
 * Errores de {@code GET /api/v1/ranking} (contracts/openapi/backend.v0.yaml, ADR-010).
 *
 * <p>Los mensajes son fijos y genéricos: nunca exponen rutas, trazas ni el cuerpo del servicio ML (RN-09).
 */
public enum RankingError {

    INVALID_REQUEST(422, "invalid_request",
            "La petición no cumple el contrato: forecast_time debe ser una fecha-hora RFC 3339 con zona horaria."),
    INTERNAL_ERROR(500, "internal_error", "Error interno al generar el ranking."),
    UPSTREAM_INVALID_RESPONSE(502, "upstream_invalid_response", "El servicio ML devolvió una respuesta inválida."),
    UPSTREAM_UNAVAILABLE(503, "upstream_unavailable", "El servicio ML no está disponible."),
    PROTOTYPE_UNAVAILABLE(503, "prototype_unavailable",
            "No se puede puntuar con los insumos disponibles para el forecast_time solicitado."),
    DATA_UNAVAILABLE(503, "data_unavailable", "Insumo de datos no disponible o ilegible."),
    UPSTREAM_TIMEOUT(504, "upstream_timeout", "El servicio ML no respondió a tiempo.");

    private final int status;
    private final String type;
    private final String message;

    RankingError(int status, String type, String message) {
        this.status = status;
        this.type = type;
        this.message = message;
    }

    public int status() {
        return status;
    }

    /** Valor de {@code error_type} en el cuerpo de error. */
    public String type() {
        return type;
    }

    public String message() {
        return message;
    }
}

package cl.sapi.backend.ranking.ml;

/**
 * La llamada al servicio ML no obtuvo respuesta HTTP: no se pudo conectar o se agotó el timeout.
 */
public class MlCallException extends RuntimeException {

    /** Causa de la falla, que decide el código del backend (ADR-010). */
    public enum Kind {
        /** No hubo conexión o se cortó antes de completar la respuesta (503). */
        UNAVAILABLE,
        /** Se agotó el timeout de conexión o de lectura (504). */
        TIMEOUT
    }

    private final Kind kind;

    public MlCallException(Kind kind, Throwable cause) {
        super(kind.name(), cause);
        this.kind = kind;
    }

    public Kind kind() {
        return kind;
    }
}

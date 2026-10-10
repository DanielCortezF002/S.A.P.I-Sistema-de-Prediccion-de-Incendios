package cl.sapi.backend.ranking.ml;

import org.jspecify.annotations.Nullable;

/**
 * La llamada al servicio ML no terminó con una respuesta completa: no se pudo conectar, se agotó el
 * timeout o la conexión se cortó mientras llegaba el cuerpo.
 */
public class MlCallException extends RuntimeException {

    /** Causa de la falla, que decide el código del backend (ADR-010). */
    public enum Kind {
        /** No hubo conexión, o se cortó antes de completar la respuesta (503). */
        UNAVAILABLE,
        /** Se agotó el timeout de conexión o el plazo de lectura, incluido el del cuerpo (504). */
        TIMEOUT
    }

    private final Kind kind;
    private final @Nullable Integer httpStatus;

    public MlCallException(Kind kind, @Nullable Integer httpStatus, Throwable cause) {
        super(kind.name(), cause);
        this.kind = kind;
        this.httpStatus = httpStatus;
    }

    public Kind kind() {
        return kind;
    }

    /** Código HTTP del ML si alcanzó a llegar la línea de estado; null si no hubo respuesta. */
    public @Nullable Integer httpStatus() {
        return httpStatus;
    }
}

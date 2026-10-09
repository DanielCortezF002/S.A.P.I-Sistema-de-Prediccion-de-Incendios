package cl.sapi.backend.ranking.ml;

import java.net.URI;
import java.time.Duration;
import java.util.Objects;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Conexión con el servicio ML (SAPI-57, ADR-010). Se configura por variables de entorno en
 * {@code application.properties}: {@code SAPI_ML_BASE_URL}, {@code SAPI_ML_CONNECT_TIMEOUT} y
 * {@code SAPI_ML_READ_TIMEOUT}.
 *
 * @param baseUrl URL base del servicio ML, sin {@code /predict}
 * @param connectTimeout tiempo máximo para abrir la conexión
 * @param readTimeout tiempo máximo de espera de la respuesta; debe superar la duración del scoring
 */
@ConfigurationProperties("sapi.ml")
public record MlServiceProperties(URI baseUrl, Duration connectTimeout, Duration readTimeout) {

    public MlServiceProperties {
        Objects.requireNonNull(baseUrl, "sapi.ml.base-url es obligatorio");
        Objects.requireNonNull(connectTimeout, "sapi.ml.connect-timeout es obligatorio");
        Objects.requireNonNull(readTimeout, "sapi.ml.read-timeout es obligatorio");
        String scheme = baseUrl.getScheme();
        if (!"http".equals(scheme) && !"https".equals(scheme)) {
            throw new IllegalArgumentException("sapi.ml.base-url debe ser http o https");
        }
        if (connectTimeout.isNegative() || connectTimeout.isZero()
                || readTimeout.isNegative() || readTimeout.isZero()) {
            throw new IllegalArgumentException("los timeouts de sapi.ml deben ser positivos");
        }
    }
}

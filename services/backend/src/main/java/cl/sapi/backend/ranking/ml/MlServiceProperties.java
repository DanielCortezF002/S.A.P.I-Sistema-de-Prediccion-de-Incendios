package cl.sapi.backend.ranking.ml;

import java.net.URI;
import java.time.Duration;
import java.time.temporal.ChronoUnit;
import java.util.Objects;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.convert.DurationUnit;

/**
 * Conexión con el servicio ML (SAPI-57, ADR-010). Se configura por variables de entorno en
 * {@code application.properties}: {@code SAPI_ML_BASE_URL}, {@code SAPI_ML_CONNECT_TIMEOUT} y
 * {@code SAPI_ML_READ_TIMEOUT}. Un timeout sin unidad se lee en segundos ({@code 60} = 60 s).
 *
 * @param baseUrl URL base del servicio ML, sin {@code /predict}
 * @param connectTimeout tiempo máximo para abrir la conexión
 * @param readTimeout plazo total para recibir la respuesta completa; debe superar la duración del scoring
 */
@ConfigurationProperties("sapi.ml")
public record MlServiceProperties(
        URI baseUrl,
        @DurationUnit(ChronoUnit.SECONDS) Duration connectTimeout,
        @DurationUnit(ChronoUnit.SECONDS) Duration readTimeout) {

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

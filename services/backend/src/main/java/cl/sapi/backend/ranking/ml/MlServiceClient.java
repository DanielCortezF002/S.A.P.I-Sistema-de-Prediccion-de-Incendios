package cl.sapi.backend.ranking.ml;

import java.io.IOException;
import java.io.InputStream;
import java.net.SocketTimeoutException;
import java.net.http.HttpClient;
import java.net.http.HttpTimeoutException;
import java.util.Map;

import org.jspecify.annotations.Nullable;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.http.client.ClientHttpRequestFactoryBuilder;
import org.springframework.boot.http.client.HttpClientSettings;
import org.springframework.boot.http.client.HttpRedirects;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

/**
 * Cliente HTTP del servicio ML: {@code POST /predict} con {@link RestClient} (SAPI-57.CA1, ADR-010).
 *
 * <p>Devuelve el código y los bytes de la respuesta sin interpretarlos; la validación del contrato y el
 * mapeo de errores viven en {@code RankingService}. Usa el cliente HTTP del JDK en HTTP/1.1, sin seguir
 * redirecciones, con los timeouts de {@link MlServiceProperties}.
 */
@Component
@EnableConfigurationProperties(MlServiceProperties.class)
public class MlServiceClient {

    /** Header de correlación que el backend propaga al servicio ML. */
    public static final String REQUEST_ID_HEADER = "X-Request-Id";

    /** Tamaño máximo aceptado para el cuerpo del ML (una respuesta real ocupa unos 5 KB). */
    public static final int MAX_BODY_BYTES = 1024 * 1024;

    private final RestClient restClient;

    public MlServiceClient(RestClient.Builder builder, MlServiceProperties properties) {
        HttpClientSettings settings = HttpClientSettings.defaults()
                .withTimeouts(properties.connectTimeout(), properties.readTimeout())
                .withRedirects(HttpRedirects.DONT_FOLLOW);
        this.restClient = builder.clone()
                .baseUrl(properties.baseUrl().toString())
                .requestFactory(ClientHttpRequestFactoryBuilder.jdk()
                        .withHttpClientCustomizer(client -> client.version(HttpClient.Version.HTTP_1_1))
                        .build(settings))
                .build();
    }

    /**
     * Pide el ranking al servicio ML.
     *
     * @param forecastTime {@code forecast_time} ya validado, o null para el último bucket real
     * @param requestId identificador de correlación de la solicitud
     * @return la respuesta HTTP del ML, cualquiera sea su código
     * @throws MlCallException si no hubo respuesta HTTP (ML inaccesible o timeout)
     */
    public MlResponse predict(@Nullable String forecastTime, String requestId) {
        Map<String, String> body = forecastTime == null ? Map.of() : Map.of("forecast_time", forecastTime);
        try {
            return restClient.post()
                    .uri("/predict")
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .header(REQUEST_ID_HEADER, requestId)
                    .body(body)
                    .exchange((request, response) -> read(response.getStatusCode().value(), response.getBody()));
        }
        catch (ResourceAccessException ex) {
            throw new MlCallException(isTimeout(ex) ? MlCallException.Kind.TIMEOUT : MlCallException.Kind.UNAVAILABLE, ex);
        }
    }

    private static MlResponse read(int status, @Nullable InputStream stream) throws IOException {
        if (stream == null) {
            return new MlResponse(status, new byte[0], false);
        }
        byte[] bytes = stream.readNBytes(MAX_BODY_BYTES + 1);
        if (bytes.length > MAX_BODY_BYTES) {
            return new MlResponse(status, new byte[0], true);
        }
        return new MlResponse(status, bytes, false);
    }

    private static boolean isTimeout(Throwable error) {
        for (Throwable cause = error; cause != null; cause = cause.getCause()) {
            if (cause instanceof HttpTimeoutException || cause instanceof SocketTimeoutException) {
                return true;
            }
        }
        return false;
    }
}

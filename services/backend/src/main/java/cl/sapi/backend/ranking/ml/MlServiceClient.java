package cl.sapi.backend.ranking.ml;

import java.io.IOException;
import java.io.InputStream;
import java.net.SocketTimeoutException;
import java.net.http.HttpClient;
import java.net.http.HttpTimeoutException;
import java.time.Duration;
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
 * redirecciones, con los timeouts de {@link MlServiceProperties}. Con este cliente el timeout de lectura
 * es un plazo total, desde el envío hasta el último byte del cuerpo.
 */
@Component
@EnableConfigurationProperties(MlServiceProperties.class)
public class MlServiceClient {

    /** Header de correlación que el backend propaga al servicio ML. */
    public static final String REQUEST_ID_HEADER = "X-Request-Id";

    /** Tamaño máximo aceptado para el cuerpo del ML (una respuesta real ocupa unos 5 KB). */
    public static final int MAX_BODY_BYTES = 1024 * 1024;

    private final RestClient restClient;
    /** El plazo que arma Spring para la lectura (milisegundos enteros). */
    private final Duration readDeadline;

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
        this.readDeadline = Duration.ofMillis(properties.readTimeout().toMillis());
    }

    /**
     * Pide el ranking al servicio ML.
     *
     * @param forecastTime {@code forecast_time} ya validado, o null para el último bucket real
     * @param requestId identificador de correlación de la solicitud
     * @return la respuesta HTTP completa del ML, cualquiera sea su código
     * @throws MlCallException si no hubo respuesta completa (ML inaccesible, timeout o corte del cuerpo)
     */
    public MlResponse predict(@Nullable String forecastTime, String requestId) {
        Map<String, String> body = forecastTime == null ? Map.of() : Map.of("forecast_time", forecastTime);
        long start = System.nanoTime();
        try {
            return restClient.post()
                    .uri("/predict")
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .header(REQUEST_ID_HEADER, requestId)
                    .body(body)
                    .exchange((request, response) ->
                            read(response.getStatusCode().value(), response.getBody(), start));
        }
        catch (ResourceAccessException ex) {
            MlCallException.Kind kind = isTimeout(ex) ? MlCallException.Kind.TIMEOUT : MlCallException.Kind.UNAVAILABLE;
            throw new MlCallException(kind, null, ex);
        }
    }

    /**
     * Lee el cuerpo con tope de tamaño. Si la lectura falla, la línea de estado ya llegó: es un timeout si
     * se agotó el plazo de lectura (Spring cierra el stream al vencer) y un corte de conexión si no.
     */
    private MlResponse read(int status, @Nullable InputStream stream, long start) {
        if (stream == null) {
            return new MlResponse(status, new byte[0], false);
        }
        byte[] bytes;
        try {
            bytes = stream.readNBytes(MAX_BODY_BYTES + 1);
        }
        catch (IOException ex) {
            closeQuietly(stream);
            boolean expired = Duration.ofNanos(System.nanoTime() - start).compareTo(readDeadline) >= 0;
            throw new MlCallException(expired ? MlCallException.Kind.TIMEOUT : MlCallException.Kind.UNAVAILABLE,
                    status, ex);
        }
        if (bytes.length > MAX_BODY_BYTES) {
            // Cerrar antes de que RestClient drene el resto: un cuerpo enorme o infinito no retiene el hilo.
            closeQuietly(stream);
            return new MlResponse(status, new byte[0], true);
        }
        return new MlResponse(status, bytes, false);
    }

    /** true si la causa es un timeout antes de recibir la respuesta (conexión o espera de headers). */
    static boolean isTimeout(Throwable error) {
        for (Throwable cause = error; cause != null; cause = cause.getCause()) {
            if (cause instanceof HttpTimeoutException || cause instanceof SocketTimeoutException) {
                return true;
            }
        }
        return false;
    }

    private static void closeQuietly(InputStream stream) {
        try {
            stream.close();
        }
        catch (IOException ex) {
            // Ya se decidió el resultado; el cierre es solo para liberar la conexión.
        }
    }
}

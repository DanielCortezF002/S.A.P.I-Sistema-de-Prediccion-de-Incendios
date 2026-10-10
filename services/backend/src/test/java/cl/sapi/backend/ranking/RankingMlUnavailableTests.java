package cl.sapi.backend.ranking;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.List;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import tools.jackson.databind.JsonNode;

/** Servicio ML caído: nadie escucha en su puerto (SAPI-57.CA2). */
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
class RankingMlUnavailableTests {

    @DynamicPropertySource
    static void closedMlPort(DynamicPropertyRegistry registry) {
        int port;
        try (ServerSocket socket = new ServerSocket(0, 1, InetAddress.getLoopbackAddress())) {
            port = socket.getLocalPort();
        }
        catch (IOException ex) {
            throw new UncheckedIOException(ex);
        }
        registry.add("sapi.ml.base-url", () -> "http://127.0.0.1:" + port);
    }

    @Value("${local.server.port}")
    private int port;

    @Test
    @DisplayName("SAPI-57.CA2, CA5 — ML caído → 503 upstream_unavailable con cuerpo del contrato y su ml_predict")
    void mlDownIs503() throws Exception {
        Logger logger = (Logger) LoggerFactory.getLogger(RankingService.LOGGER_NAME);
        ListAppender<ILoggingEvent> logs = new ListAppender<>();
        logs.start();
        logger.addAppender(logs);
        HttpResponse<byte[]> response;
        try (HttpClient client = HttpClient.newHttpClient()) {
            response = client.send(HttpRequest.newBuilder(
                    URI.create("http://127.0.0.1:" + port + "/api/v1/ranking")).GET().build(),
                    HttpResponse.BodyHandlers.ofByteArray());
        }
        finally {
            logger.detachAppender(logs);
        }

        assertThat(response.statusCode()).isEqualTo(503);
        assertThat(response.headers().firstValue("X-Request-Id")).isPresent();
        assertThat(BackendContract.validate(503, response.body())).isEmpty();
        JsonNode body = Fixtures.MAPPER.readTree(response.body());
        assertThat(body.get("error_type").stringValue()).isEqualTo("upstream_unavailable");
        assertThat(body.get("message").stringValue()).doesNotContain("127.0.0.1").doesNotContain("Connect");
        List<ILoggingEvent> events = logs.list.stream()
                .filter(event -> event.getKeyValuePairs() != null && event.getKeyValuePairs().stream()
                        .anyMatch(pair -> "event".equals(pair.key) && "ml_predict".equals(pair.value)))
                .toList();
        assertThat(events).hasSize(1);
        assertThat(events.get(0).getKeyValuePairs())
                .anyMatch(pair -> "ml_responded".equals(pair.key) && Boolean.FALSE.equals(pair.value))
                .anyMatch(pair -> "outcome".equals(pair.key) && "upstream_unavailable".equals(pair.value))
                .noneMatch(pair -> "ml_http_status".equals(pair.key));
    }
}

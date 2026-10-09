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

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

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
    @DisplayName("SAPI-57.CA2 — ML caído → 503 upstream_unavailable con cuerpo del contrato")
    void mlDownIs503() throws Exception {
        HttpResponse<byte[]> response;
        try (HttpClient client = HttpClient.newHttpClient()) {
            response = client.send(HttpRequest.newBuilder(
                    URI.create("http://127.0.0.1:" + port + "/api/v1/ranking")).GET().build(),
                    HttpResponse.BodyHandlers.ofByteArray());
        }

        assertThat(response.statusCode()).isEqualTo(503);
        assertThat(BackendContract.validate(503, response.body())).isEmpty();
        JsonNode body = Fixtures.MAPPER.readTree(response.body());
        assertThat(body.get("error_type").stringValue()).isEqualTo("upstream_unavailable");
        assertThat(body.get("message").stringValue()).doesNotContain("127.0.0.1").doesNotContain("Connect");
    }
}

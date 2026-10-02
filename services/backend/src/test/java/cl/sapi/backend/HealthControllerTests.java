package cl.sapi.backend;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.Reader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.yaml.snakeyaml.Yaml;

import tools.jackson.databind.ObjectMapper;

/**
 * GET /health contra el servidor real (puerto aleatorio) y contra el contrato congelado
 * contracts/openapi/backend.v0.yaml (schema BackendHealth).
 */
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
class HealthControllerTests {

    private static final Path CONTRACT =
            Path.of("..", "..", "contracts", "openapi", "backend.v0.yaml");

    @Value("${local.server.port}")
    private int port;

    private HttpResponse<String> getHealth() throws IOException, InterruptedException {
        HttpRequest request =
                HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/health")).GET().build();
        return HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
    }

    @Test
    void healthReturnsUp() throws Exception {
        HttpResponse<String> response = getHealth();

        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.headers().firstValue("Content-Type")).hasValueSatisfying(
                contentType -> assertThat(contentType).startsWith("application/json"));
        assertThat(new ObjectMapper().readValue(response.body(), Map.class))
                .isEqualTo(Map.of("status", "UP"));
    }

    @Test
    @SuppressWarnings("unchecked")
    void healthResponseConformsToFrozenContract() throws Exception {
        Map<String, Object> contract;
        try (Reader reader = Files.newBufferedReader(CONTRACT, StandardCharsets.UTF_8)) {
            contract = new Yaml().load(reader);
        }
        Map<String, Object> paths = (Map<String, Object>) contract.get("paths");
        Map<String, Object> responses = (Map<String, Object>)
                ((Map<String, Object>) ((Map<String, Object>) paths.get("/health")).get("get"))
                        .get("responses");
        Map<String, Object> schema = (Map<String, Object>)
                ((Map<String, Object>) ((Map<String, Object>) contract.get("components"))
                        .get("schemas")).get("BackendHealth");
        List<String> required = (List<String>) schema.get("required");
        Map<String, Object> properties = (Map<String, Object>) schema.get("properties");
        List<String> statusEnum =
                (List<String>) ((Map<String, Object>) properties.get("status")).get("enum");

        HttpResponse<String> response = getHealth();
        Map<String, Object> body = new ObjectMapper().readValue(response.body(), Map.class);

        assertThat(responses).containsKey(String.valueOf(response.statusCode()));
        assertThat(body.keySet()).containsAll(required);
        assertThat(properties.keySet()).containsAll(body.keySet());
        assertThat(statusEnum).contains((String) body.get("status"));
    }
}

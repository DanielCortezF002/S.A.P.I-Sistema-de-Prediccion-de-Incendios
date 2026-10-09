package cl.sapi.backend.ranking;

import java.io.IOException;
import java.io.Reader;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.Set;

import org.yaml.snakeyaml.Yaml;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.networknt.schema.JsonSchema;
import com.networknt.schema.JsonSchemaFactory;
import com.networknt.schema.SchemaLocation;
import com.networknt.schema.SchemaValidatorsConfig;
import com.networknt.schema.SpecVersion;
import com.networknt.schema.ValidationMessage;
import com.networknt.schema.oas.OpenApi30;

/**
 * Valida respuestas de {@code GET /api/v1/ranking} contra el contrato congelado
 * {@code contracts/openapi/backend.v0.yaml}, siguiendo sus {@code $ref} hacia {@code ml-service.v0.yaml}
 * con un validador JSON Schema en dialecto OpenAPI 3.0.
 */
final class BackendContract {

    static final Path CONTRACTS = Path.of("..", "..", "contracts", "openapi").toAbsolutePath().normalize();
    static final Path BACKEND = CONTRACTS.resolve("backend.v0.yaml");

    private static final String RANKING_RESPONSES = "/paths/~1api~1v1~1ranking/get/responses";
    private static final String JSON_SCHEMA = "/content/application~1json/schema";

    private static final JsonSchemaFactory FACTORY = JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V4,
            builder -> builder.metaSchema(OpenApi30.getInstance())
                    .defaultMetaSchemaIri(OpenApi30.getInstance().getIri()));
    private static final SchemaValidatorsConfig CONFIG =
            SchemaValidatorsConfig.builder().formatAssertionsEnabled(true).build();
    private static final ObjectMapper JSON = new ObjectMapper();

    private BackendContract() {
    }

    /** Códigos HTTP que el contrato declara para {@code GET /api/v1/ranking}. */
    static Set<String> declaredStatuses() {
        return rankingResponses().keySet();
    }

    /** Errores de validación del cuerpo contra el schema declarado para ese código (vacío = cumple). */
    static Set<ValidationMessage> validate(int status, byte[] body) {
        try {
            return schemaFor(status).validate(JSON.readTree(body));
        }
        catch (IOException ex) {
            throw new UncheckedIOException(ex);
        }
    }

    /** Schema de la respuesta {@code status}, resolviendo un {@code $ref} de respuesta entre archivos. */
    @SuppressWarnings("unchecked")
    static JsonSchema schemaFor(int status) {
        Object response = rankingResponses().get(String.valueOf(status));
        if (response == null) {
            throw new AssertionError("backend.v0.yaml no declara el código " + status);
        }
        String location;
        String ref = (String) ((Map<String, Object>) response).get("$ref");
        if (ref == null) {
            location = BACKEND.toUri() + "#" + RANKING_RESPONSES + "/" + status + JSON_SCHEMA;
        }
        else {
            String[] parts = ref.split("#", 2);
            location = CONTRACTS.resolve(parts[0]).normalize().toUri() + "#" + parts[1] + JSON_SCHEMA;
        }
        return FACTORY.getSchema(SchemaLocation.of(location), CONFIG);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> rankingResponses() {
        Map<String, Object> contract;
        try (Reader reader = Files.newBufferedReader(BACKEND, StandardCharsets.UTF_8)) {
            contract = new Yaml().load(reader);
        }
        catch (IOException ex) {
            throw new UncheckedIOException(ex);
        }
        Map<String, Object> paths = (Map<String, Object>) contract.get("paths");
        Map<String, Object> ranking = (Map<String, Object>) paths.get("/api/v1/ranking");
        return (Map<String, Object>) ((Map<String, Object>) ranking.get("get")).get("responses");
    }
}

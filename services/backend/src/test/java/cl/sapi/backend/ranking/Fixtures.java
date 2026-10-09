package cl.sapi.backend.ranking;

import java.io.IOException;
import java.io.InputStream;
import java.io.Reader;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Map;
import java.util.function.Consumer;

import org.yaml.snakeyaml.Yaml;

import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ObjectNode;

/** Cuerpos de prueba: la respuesta real del ML y variantes derivadas en memoria. */
final class Fixtures {

    static final JsonMapper MAPPER = JsonMapper.builder().build();

    private Fixtures() {
    }

    /** Respuesta real de {@code POST /predict} (ver src/test/resources/ml/README.md). */
    static byte[] realRanking() {
        try (InputStream in = Fixtures.class.getResourceAsStream("/ml/predict-reproducible-2026-09-01.json")) {
            return in.readAllBytes();
        }
        catch (IOException ex) {
            throw new UncheckedIOException(ex);
        }
    }

    /** La respuesta real con una modificación aplicada sobre una copia. */
    static byte[] realRankingWith(Consumer<ObjectNode> change) {
        ObjectNode root = (ObjectNode) MAPPER.readTree(realRanking());
        change.accept(root);
        return MAPPER.writeValueAsBytes(root);
    }

    /** El ejemplo sintético {@code RankingResultSynthetic} de ml-service.v0.yaml, como JSON. */
    @SuppressWarnings("unchecked")
    static byte[] contractSyntheticExample() {
        Map<String, Object> contract;
        try (Reader reader = Files.newBufferedReader(BackendContract.CONTRACTS.resolve("ml-service.v0.yaml"),
                StandardCharsets.UTF_8)) {
            contract = new Yaml().load(reader);
        }
        catch (IOException ex) {
            throw new UncheckedIOException(ex);
        }
        Map<String, Object> examples = (Map<String, Object>) ((Map<String, Object>) contract.get("components"))
                .get("examples");
        Object value = ((Map<String, Object>) examples.get("RankingResultSynthetic")).get("value");
        return MAPPER.writeValueAsBytes(value);
    }

    /** Cuerpo {@code Error} como el que emite el servicio ML. */
    static byte[] mlError(String errorType) {
        return MAPPER.writeValueAsBytes(Map.of("status", "error", "error_type", errorType, "message", "mensaje del ML"));
    }
}

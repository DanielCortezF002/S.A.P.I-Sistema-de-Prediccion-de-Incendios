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

    /**
     * La respuesta real con {@code firms_origin=reproducibility} (SAPI F1, Jira #10134): el
     * fixture protegido no lo trae (ver ml/README.md), pero es justo lo que
     * {@code SAPI_REPRODUCIBILITY_MODE=1} habría producido para este {@code forecast_time}.
     * Usar donde el test espera que el gate de procedencia autorice la persistencia.
     */
    static byte[] realRankingWithAllowedOrigin() {
        return realRankingWith(root -> root.put("firms_origin", "reproducibility"));
    }

    /**
     * Fingerprint sha256 con patrón repetido, deliberadamente distinguible de un hash real (los
     * del fixture protegido tienen entropía de hash genuina). 64 caracteres hexadecimales
     * válidos para {@code RankingResultValidator}, nunca un valor que pueda confundirse con
     * procedencia histórica auténtica.
     */
    static final String SYNTHETIC_FINGERPRINT = "ab".repeat(32);

    /** {@code forecast_time} claramente distinto del fixture histórico (2026-09-01). */
    static final String SYNTHETIC_FORECAST_TIME = "2026-10-14T00:00:00Z";

    /**
     * La respuesta real con una identidad de negocio (clave natural
     * {@code forecast_time}/{@code inputs_fingerprint}) inequívocamente sintética y
     * {@code firms_origin} dado, para no presentar la clave del fixture histórico protegido
     * como si fuera una ejecución CURRENT auténtica (hallazgo Astra, sección 4). Las 50 celdas
     * y el resto de los campos contractuales se conservan sin cambios.
     *
     * @param firmsOrigin valor de {@code firms_origin} a fijar sobre la identidad sintética
     */
    static byte[] syntheticIdentityWithOrigin(String firmsOrigin) {
        return realRankingWith(root -> root
                .put("forecast_time", SYNTHETIC_FORECAST_TIME)
                .put("inputs_fingerprint", SYNTHETIC_FINGERPRINT)
                .put("firms_origin", firmsOrigin));
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

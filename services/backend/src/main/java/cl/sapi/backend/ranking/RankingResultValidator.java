package cl.sapi.backend.ranking;

import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.HashSet;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;

import tools.jackson.core.JacksonException;
import tools.jackson.core.StreamReadFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * Verifica que un cuerpo del servicio ML cumpla {@code RankingResult} (ml-service.v0.yaml) antes de
 * reenviarlo: campos obligatorios y sus formatos, y las invariantes de la grilla que JSON Schema no
 * expresa (RN-02, RN-03, RN-04). Nunca modifica el cuerpo: el backend reenvía los mismos bytes.
 *
 * <p>Los campos desconocidos se ignoran, porque el contrato solo admite cambios aditivos.
 */
public final class RankingResultValidator {

    static final int CELL_COUNT = 50;

    private static final Pattern FINGERPRINT = Pattern.compile("^[0-9a-f]{64}$");
    private static final Pattern CELL_ID = Pattern.compile("^VP-\\d{3}$");
    private static final Set<String> EXPECTED_CELL_IDS = expectedCellIds();

    private static final JsonMapper MAPPER = JsonMapper.builder()
            .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)
            .build();

    private RankingResultValidator() {
    }

    /**
     * Valida un cuerpo {@code RankingResult}.
     *
     * @return la primera violación encontrada (solo para el log), o vacío si el cuerpo es válido
     */
    public static Optional<String> violation(byte[] body) {
        JsonNode root = parse(body);
        if (root == null || !root.isObject()) {
            return Optional.of("el cuerpo no es un objeto JSON");
        }
        if (!isString(root, "schema_version", "sapi-ranking-v0")) {
            return Optional.of("schema_version distinto de sapi-ranking-v0");
        }
        JsonNode modelVersion = root.get("model_version");
        if (modelVersion == null || !modelVersion.isString() || modelVersion.stringValue().isEmpty()) {
            return Optional.of("model_version ausente o vacío");
        }
        if (!isOffsetDateTime(root.get("forecast_time"))) {
            return Optional.of("forecast_time no es una fecha-hora ISO 8601 con zona horaria");
        }
        JsonNode fingerprint = root.get("inputs_fingerprint");
        if (fingerprint == null || !fingerprint.isString() || !FINGERPRINT.matcher(fingerprint.stringValue()).matches()) {
            return Optional.of("inputs_fingerprint no es un sha256 hexadecimal");
        }
        if (!isString(root, "score_semantics", "relative_rank")) {
            return Optional.of("score_semantics distinto de relative_rank");
        }
        JsonNode validation = root.get("scientific_model_validation");
        if (validation == null || !validation.isBoolean() || validation.booleanValue()) {
            return Optional.of("scientific_model_validation distinto de false");
        }
        if (root.has("horizon_hours") && !isIntegerInRange(root.get("horizon_hours"), 1, Integer.MAX_VALUE)) {
            return Optional.of("horizon_hours no es un entero >= 1");
        }
        if (root.has("disclaimer") && !root.get("disclaimer").isString()) {
            return Optional.of("disclaimer no es un string");
        }
        return cellsViolation(root.get("cells"));
    }

    /**
     * Lee el {@code error_type} de un cuerpo {@code Error} (status, error_type y message obligatorios).
     *
     * @return el {@code error_type}, o vacío si el cuerpo no cumple el schema {@code Error}
     */
    public static Optional<String> errorType(byte[] body) {
        JsonNode root = parse(body);
        if (root == null || !root.isObject() || !isString(root, "status", "error")) {
            return Optional.empty();
        }
        JsonNode type = root.get("error_type");
        JsonNode message = root.get("message");
        if (type == null || !type.isString() || message == null || !message.isString()) {
            return Optional.empty();
        }
        return Optional.of(type.stringValue());
    }

    private static Optional<String> cellsViolation(JsonNode cells) {
        if (cells == null || !cells.isArray() || cells.size() != CELL_COUNT) {
            return Optional.of("cells no es un arreglo de exactamente 50 celdas");
        }
        double[] scores = new double[CELL_COUNT];
        Set<String> ids = new HashSet<>();
        for (int i = 0; i < CELL_COUNT; i++) {
            JsonNode cell = cells.get(i);
            if (cell == null || !cell.isObject()) {
                return Optional.of("cells[" + i + "] no es un objeto");
            }
            JsonNode id = cell.get("cell_id");
            if (id == null || !id.isString() || !CELL_ID.matcher(id.stringValue()).matches()) {
                return Optional.of("cells[" + i + "].cell_id inválido");
            }
            ids.add(id.stringValue());
            JsonNode score = cell.get("score");
            if (score == null || !score.isNumber() || !Double.isFinite(score.doubleValue())
                    || score.doubleValue() < 0 || score.doubleValue() > 1) {
                return Optional.of("cells[" + i + "].score no es un número en [0, 1]");
            }
            scores[i] = score.doubleValue();
            for (String field : new String[] {"rank", "display_rank", "tie_group_size"}) {
                if (!isIntegerInRange(cell.get(field), 1, CELL_COUNT)) {
                    return Optional.of("cells[" + i + "]." + field + " no es un entero en [1, 50]");
                }
            }
            if (cell.get("rank").intValue() != i + 1) {
                return Optional.of("cells[" + i + "].rank no sigue el orden 1..50");
            }
            if (i > 0 && scores[i] > scores[i - 1]) {
                return Optional.of("cells[" + i + "].score crece al avanzar el rank");
            }
        }
        if (!ids.equals(EXPECTED_CELL_IDS)) {
            return Optional.of("los cell_id no son exactamente VP-001..VP-050");
        }
        for (int i = 0; i < CELL_COUNT; i++) {
            int higher = 0;
            int tied = 0;
            for (double other : scores) {
                if (other > scores[i]) {
                    higher++;
                }
                else if (other == scores[i]) {
                    tied++;
                }
            }
            JsonNode cell = cells.get(i);
            if (cell.get("display_rank").intValue() != higher + 1) {
                return Optional.of("cells[" + i + "].display_rank no sigue el método min");
            }
            if (cell.get("tie_group_size").intValue() != tied) {
                return Optional.of("cells[" + i + "].tie_group_size no cuenta el grupo de empate");
            }
        }
        return Optional.empty();
    }

    private static JsonNode parse(byte[] body) {
        if (body == null || body.length == 0) {
            return null;
        }
        try {
            return MAPPER.readTree(body);
        }
        catch (JacksonException ex) {
            return null;
        }
    }

    private static boolean isString(JsonNode root, String field, String expected) {
        JsonNode node = root.get(field);
        return node != null && node.isString() && expected.equals(node.stringValue());
    }

    private static boolean isIntegerInRange(JsonNode node, int min, int max) {
        return node != null && node.isIntegralNumber() && node.canConvertToInt()
                && node.intValue() >= min && node.intValue() <= max;
    }

    private static boolean isOffsetDateTime(JsonNode node) {
        if (node == null || !node.isString()) {
            return false;
        }
        try {
            OffsetDateTime.parse(node.stringValue(), DateTimeFormatter.ISO_OFFSET_DATE_TIME);
            return true;
        }
        catch (DateTimeParseException ex) {
            return false;
        }
    }

    private static Set<String> expectedCellIds() {
        Set<String> ids = new HashSet<>();
        for (int i = 1; i <= CELL_COUNT; i++) {
            ids.add(String.format(Locale.ROOT, "VP-%03d", i));
        }
        return Set.copyOf(ids);
    }
}

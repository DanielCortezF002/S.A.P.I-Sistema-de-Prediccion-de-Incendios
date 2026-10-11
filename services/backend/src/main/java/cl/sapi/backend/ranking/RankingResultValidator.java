package cl.sapi.backend.ranking;

import java.time.DateTimeException;
import java.time.LocalDate;
import java.util.HashSet;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;

import org.jspecify.annotations.Nullable;

import tools.jackson.core.JacksonException;
import tools.jackson.core.StreamReadFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * Verifica que un cuerpo del servicio ML cumpla {@code RankingResult} (ml-service.v0.yaml) antes de
 * reenviarlo: campos obligatorios y sus formatos, y las invariantes de la grilla que JSON Schema no
 * expresa (RN-02, RN-03, RN-04). Nunca modifica el cuerpo: el backend reenvía los mismos bytes.
 *
 * <p>Solo acepta JSON en UTF-8 que empieza con {@code {}: sin BOM y sin bytes nulos (UTF-16/32). Los
 * campos desconocidos se ignoran, porque el contrato solo admite cambios aditivos.
 */
public final class RankingResultValidator {

    static final int CELL_COUNT = 50;

    private static final Pattern FINGERPRINT = Pattern.compile("[0-9a-f]{64}");
    private static final Pattern CELL_ID = Pattern.compile("VP-\\d{3}");
    private static final Pattern ISO_DATE = Pattern.compile("\\d{4}-\\d{2}-\\d{2}");
    private static final Set<String> FRESHNESS = Set.of(
            "DATOS RECIENTES", "DATOS CON RETRASO", "DATOS HISTÓRICOS / DESACTUALIZADOS");
    private static final Set<String> FIRMS_ORIGIN = Set.of("baseline", "current", "reproducibility");
    private static final Set<String> FIRMS_STATUS = Set.of("FIRMS AL DÍA", "FIRMS DESACTUALIZADO");
    private static final Set<String> EXPECTED_CELL_IDS = expectedCellIds();

    private static final JsonMapper MAPPER = JsonMapper.builder()
            .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)
            .build();

    /**
     * Resultado de la validación.
     *
     * @param violation la primera violación encontrada (solo para el log), o vacío si el cuerpo es válido
     * @param ranking el árbol ya validado, o null si el cuerpo no es válido
     */
    public record Validation(Optional<String> violation, @Nullable JsonNode ranking) {

        static Validation invalid(String violation) {
            return new Validation(Optional.of(violation), null);
        }
    }

    private RankingResultValidator() {
    }

    /** Valida un cuerpo {@code RankingResult} y, si es válido, devuelve su árbol JSON. */
    public static Validation validate(byte[] body) {
        JsonNode root = parse(body);
        if (root == null || !root.isObject()) {
            return Validation.invalid("el cuerpo no es un objeto JSON en UTF-8");
        }
        if (!isString(root, "schema_version", "sapi-ranking-v0")) {
            return Validation.invalid("schema_version distinto de sapi-ranking-v0");
        }
        JsonNode modelVersion = root.get("model_version");
        if (modelVersion == null || !modelVersion.isString() || modelVersion.stringValue().isEmpty()) {
            return Validation.invalid("model_version ausente o vacío");
        }
        JsonNode forecastTime = root.get("forecast_time");
        if (forecastTime == null || !forecastTime.isString() || !ForecastTime.isValid(forecastTime.stringValue())) {
            return Validation.invalid("forecast_time no es una fecha-hora RFC 3339");
        }
        JsonNode fingerprint = root.get("inputs_fingerprint");
        if (fingerprint == null || !fingerprint.isString() || !FINGERPRINT.matcher(fingerprint.stringValue()).matches()) {
            return Validation.invalid("inputs_fingerprint no es un sha256 hexadecimal");
        }
        if (!isString(root, "score_semantics", "relative_rank")) {
            return Validation.invalid("score_semantics distinto de relative_rank");
        }
        JsonNode validation = root.get("scientific_model_validation");
        if (validation == null || !validation.isBoolean() || validation.booleanValue()) {
            return Validation.invalid("scientific_model_validation distinto de false");
        }
        if (root.has("horizon_hours") && !isPositiveInteger(root.get("horizon_hours"))) {
            return Validation.invalid("horizon_hours no es un entero >= 1");
        }
        if (root.has("disclaimer") && !root.get("disclaimer").isString()) {
            return Validation.invalid("disclaimer no es un string");
        }
        Optional<String> metadata = metadataViolation(root);
        if (metadata.isPresent()) {
            return Validation.invalid(metadata.get());
        }
        Optional<String> cells = cellsViolation(root.get("cells"));
        return cells.isPresent() ? new Validation(cells, null) : new Validation(Optional.empty(), root);
    }

    /** Atajo de {@link #validate(byte[])}: solo la violación. */
    public static Optional<String> violation(byte[] body) {
        return validate(body).violation();
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

    /**
     * Los nueve campos de metadata son opcionales. Si faltan, el cuerpo sigue siendo válido
     * (respuestas anteriores a la extensión). Si están, el tipo debe coincidir con el contrato;
     * un valor mal formado no se reenvía.
     */
    private static Optional<String> metadataViolation(JsonNode root) {
        if (root.has("weather_timestamp") && !isRfc3339(root.get("weather_timestamp"))) {
            return Optional.of("weather_timestamp no es una fecha-hora RFC 3339");
        }
        if (root.has("age_hours") && !isNonNegativeFinite(root.get("age_hours"))) {
            return Optional.of("age_hours no es un número finito >= 0");
        }
        if (root.has("freshness") && !isOneOf(root.get("freshness"), FRESHNESS)) {
            return Optional.of("freshness no es un valor del contrato");
        }
        if (root.has("station_id") && !isNonEmptyString(root.get("station_id"))) {
            return Optional.of("station_id ausente o vacío");
        }
        if (root.has("station_name") && !isNonEmptyString(root.get("station_name"))) {
            return Optional.of("station_name ausente o vacío");
        }
        if (root.has("firms_origin") && !isOneOf(root.get("firms_origin"), FIRMS_ORIGIN)) {
            return Optional.of("firms_origin no es un valor del contrato");
        }
        if (root.has("firms_coverage_end") && !isIsoDate(root.get("firms_coverage_end"))) {
            return Optional.of("firms_coverage_end no es una fecha ISO");
        }
        if (root.has("firms_lag_days") && !isNonNegativeInteger(root.get("firms_lag_days"))) {
            return Optional.of("firms_lag_days no es un entero >= 0");
        }
        if (root.has("firms_status") && !isOneOf(root.get("firms_status"), FIRMS_STATUS)) {
            return Optional.of("firms_status no es un valor del contrato");
        }
        return Optional.empty();
    }

    private static Optional<String> cellsViolation(@Nullable JsonNode cells) {
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

    /** Parsea un objeto JSON en UTF-8; null si el cuerpo está vacío, no empieza con '{' o no es JSON. */
    private static @Nullable JsonNode parse(byte @Nullable [] body) {
        if (body == null || !startsAsUtf8Object(body)) {
            return null;
        }
        try {
            return MAPPER.readTree(body);
        }
        catch (JacksonException ex) {
            return null;
        }
    }

    /**
     * El primer byte no blanco es '{' y no hay bytes nulos: descarta BOM y UTF-16/32, que Jackson
     * detectaría por su cuenta, para que solo pase JSON en UTF-8 (RFC 8259 §8.1).
     */
    private static boolean startsAsUtf8Object(byte[] body) {
        int first = -1;
        for (int i = 0; i < body.length; i++) {
            byte b = body[i];
            if (b == 0) {
                return false;
            }
            if (first < 0 && b != ' ' && b != '\t' && b != '\n' && b != '\r') {
                first = i;
            }
        }
        return first >= 0 && body[first] == '{';
    }

    private static boolean isString(JsonNode root, String field, String expected) {
        JsonNode node = root.get(field);
        return node != null && node.isString() && expected.equals(node.stringValue());
    }

    private static boolean isIntegerInRange(@Nullable JsonNode node, int min, int max) {
        return node != null && node.isIntegralNumber() && node.canConvertToInt()
                && node.intValue() >= min && node.intValue() <= max;
    }

    private static boolean isPositiveInteger(@Nullable JsonNode node) {
        return node != null && node.isIntegralNumber() && node.bigIntegerValue().signum() > 0;
    }

    private static boolean isRfc3339(@Nullable JsonNode node) {
        return node != null && node.isString() && ForecastTime.isValid(node.stringValue());
    }

    private static boolean isNonNegativeFinite(@Nullable JsonNode node) {
        if (node == null || !node.isNumber()) {
            return false;
        }
        double value = node.doubleValue();
        return Double.isFinite(value) && value >= 0;
    }

    private static boolean isNonNegativeInteger(@Nullable JsonNode node) {
        return node != null && node.isIntegralNumber() && node.bigIntegerValue().signum() >= 0;
    }

    private static boolean isNonEmptyString(@Nullable JsonNode node) {
        return node != null && node.isString() && !node.stringValue().isEmpty();
    }

    private static boolean isOneOf(@Nullable JsonNode node, Set<String> allowed) {
        return node != null && node.isString() && allowed.contains(node.stringValue());
    }

    private static boolean isIsoDate(@Nullable JsonNode node) {
        if (node == null || !node.isString() || !ISO_DATE.matcher(node.stringValue()).matches()) {
            return false;
        }
        try {
            LocalDate.parse(node.stringValue());
            return true;
        }
        catch (DateTimeException ex) {
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

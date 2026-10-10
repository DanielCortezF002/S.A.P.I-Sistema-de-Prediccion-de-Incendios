package cl.sapi.backend.ranking;

import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Locale;
import java.util.regex.Pattern;

import org.jspecify.annotations.Nullable;

/**
 * Regla única de {@code forecast_time} ({@code format: date-time} en los contratos, RFC 3339): la aplica
 * el controller a la entrada y el validador a la respuesta del ML.
 *
 * <p>Exige fecha, hora con segundos, fracción opcional de hasta 9 dígitos y zona {@code Z} u offset
 * {@code ±HH:MM}; rechaza {@code -00:00} ("offset desconocido" en RFC 3339). Luego verifica el calendario
 * con {@link OffsetDateTime}, que además limita el offset a ±18:00. Es más estricta que el parser del
 * servicio ML: la validación final de la entrada la hace el ML.
 */
public final class ForecastTime {

    private static final Pattern RFC_3339 = Pattern.compile(
            "\\d{4}-\\d{2}-\\d{2}[Tt]\\d{2}:\\d{2}:\\d{2}(\\.\\d{1,9})?([Zz]|[+-]\\d{2}:\\d{2})");

    private ForecastTime() {
    }

    /** true si {@code value} es una fecha-hora RFC 3339 válida con zona horaria. */
    public static boolean isValid(@Nullable String value) {
        if (value == null || !RFC_3339.matcher(value).matches() || value.endsWith("-00:00")) {
            return false;
        }
        try {
            OffsetDateTime.parse(value.toUpperCase(Locale.ROOT), DateTimeFormatter.ISO_OFFSET_DATE_TIME);
            return true;
        }
        catch (DateTimeParseException ex) {
            return false;
        }
    }
}

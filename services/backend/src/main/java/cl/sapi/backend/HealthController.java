package cl.sapi.backend;

import java.util.Map;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Liveness del backend (contracts/openapi/backend.v0.yaml, GET /health).
 *
 * <p>Solo indica que el proceso está arriba: no consulta al servicio ML ni a la base de datos.
 */
@RestController
public class HealthController {

    @GetMapping(path = "/health", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, String> health() {
        return Map.of("status", "UP");
    }
}

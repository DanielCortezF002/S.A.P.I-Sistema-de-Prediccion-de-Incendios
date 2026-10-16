package cl.sapi.backend.ranking.persistence;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import jakarta.annotation.PostConstruct;
import org.jspecify.annotations.Nullable;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * Gate de procedencia (SAPI F1, Jira SAPI-43 #10134/#10135, dictamen Astra). Único bean de
 * política (A3): decide, antes de persistir, si un {@code firms_origin} puede escribirse.
 *
 * <p>No infiere procedencia desde {@code inputs_fingerprint} (IA-P1-01): un origen ausente o
 * fuera de {@code sapi.persistence.allowed-firms-origins} se rechaza tal cual llega.
 * Falla rápido al arrancar si la lista está vacía o contiene valores fuera del contrato
 * {@code ml-service.v0.yaml} (baseline/current/reproducibility).
 */
@Component
@ConfigurationProperties(prefix = "sapi.persistence")
public class FirmsOriginPolicy {

    /** Valores de {@code firms_origin} del contrato (ml-service.v0.yaml). */
    private static final Set<String> CONTRACT_VALUES = Set.of("baseline", "current", "reproducibility");

    private List<String> allowedFirmsOrigins = List.of();

    /** Setter de binding de Spring; usar {@link #isAllowed(String)}, no mutar la lista desde fuera. */
    public void setAllowedFirmsOrigins(List<String> allowedFirmsOrigins) {
        this.allowedFirmsOrigins = List.copyOf(allowedFirmsOrigins);
    }

    public List<String> getAllowedFirmsOrigins() {
        return allowedFirmsOrigins;
    }

    @PostConstruct
    public void validate() {
        if (allowedFirmsOrigins.isEmpty()) {
            throw new IllegalStateException(
                    "sapi.persistence.allowed-firms-origins no puede estar vacío (F1, D1/D2/D10)");
        }
        Set<String> unknown = allowedFirmsOrigins.stream()
                .filter(value -> !CONTRACT_VALUES.contains(value))
                .collect(Collectors.toSet());
        if (!unknown.isEmpty()) {
            throw new IllegalStateException(
                    "sapi.persistence.allowed-firms-origins contiene valores fuera de contrato: " + unknown);
        }
    }

    /**
     * @param firmsOrigin valor recibido del ML, o null si el campo está ausente
     * @return true solo si no es null y está en la lista configurada; nunca infiere un valor
     */
    public boolean isAllowed(@Nullable String firmsOrigin) {
        return firmsOrigin != null && allowedFirmsOrigins.contains(firmsOrigin);
    }
}

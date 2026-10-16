package cl.sapi.backend.ranking.persistence;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;

import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.ConfigDataApplicationContextInitializer;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Configuration;

/**
 * A2 (Astra): binding real de Spring para {@code sapi.persistence.allowed-firms-origins},
 * aislado del resto del contexto de la aplicación (sin DataSource, sin Flyway).
 */
class FirmsOriginPolicyBindingTests {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withUserConfiguration(PolicyConfig.class);

    @Configuration(proxyBeanMethods = false)
    @EnableConfigurationProperties(FirmsOriginPolicy.class)
    static class PolicyConfig {
    }

    @Test
    void variableAusenteFallaAlArrancar() {
        contextRunner.run(context -> {
            assertThat(context).hasFailed();
            assertThat(context.getStartupFailure())
                    .hasStackTraceContaining("allowed-firms-origins");
        });
    }

    /**
     * Astra, sección 3: los seis tests anteriores construyen el bean de política fuera de todo
     * archivo real de propiedades. Este prueba el arranque REAL: carga
     * {@code services/backend/src/main/resources/application.properties} -- el archivo de
     * producción, no el de {@code src/test/resources} que este módulo usa para sus demás tests
     * -- vía {@code spring.config.location=file:...} apuntando al archivo en disco, de modo que
     * el valor de {@code sapi.persistence.allowed-firms-origins} resuelto es el default real
     * ({@code ${SAPI_PERSISTENCE_ALLOWED_FIRMS_ORIGINS:current}}), no un literal reescrito en el
     * test ni el valor de conveniencia de {@code src/test/resources/application.properties}
     * ({@code current,reproducibility}).
     */
    @Test
    void variableAusenteUsaElDefaultRealDeApplicationPropertiesDeProduccion() {
        assertThat(System.getenv("SAPI_PERSISTENCE_ALLOWED_FIRMS_ORIGINS"))
                .as("precondición del test: si esta variable existe en el entorno, el resultado "
                        + "no probaría el default y el test debe fallar en vez de aparentar pasar")
                .isNull();

        Path productionProperties = Path.of(
                        "src", "main", "resources", "application.properties")
                .toAbsolutePath().normalize();
        assertThat(productionProperties).exists();

        new ApplicationContextRunner()
                .withInitializer(new ConfigDataApplicationContextInitializer())
                .withPropertyValues("spring.config.location=file:" + productionProperties)
                .withUserConfiguration(PolicyConfig.class)
                .run(context -> {
                    assertThat(context).hasNotFailed();
                    FirmsOriginPolicy policy = context.getBean(FirmsOriginPolicy.class);
                    assertThat(policy.getAllowedFirmsOrigins()).containsExactly("current");
                    assertThat(policy.isAllowed("current")).isTrue();
                    assertThat(policy.isAllowed("baseline")).isFalse();
                    assertThat(policy.isAllowed("reproducibility")).isFalse();
                });
    }

    @Test
    void variableVaciaFallaAlArrancar() {
        contextRunner.withPropertyValues("sapi.persistence.allowed-firms-origins=").run(context -> {
            assertThat(context).hasFailed();
        });
    }

    @Test
    void valorInvalidoFueraDelContratoFallaAlArrancar() {
        contextRunner.withPropertyValues("sapi.persistence.allowed-firms-origins=current,produccion")
                .run(context -> {
                    assertThat(context).hasFailed();
                    assertThat(context.getStartupFailure()).hasStackTraceContaining("produccion");
                });
    }

    @Test
    void unSoloValorSeLigaYAutorizaSoloEse() {
        contextRunner.withPropertyValues("sapi.persistence.allowed-firms-origins=current").run(context -> {
            assertThat(context).hasNotFailed();
            FirmsOriginPolicy policy = context.getBean(FirmsOriginPolicy.class);
            assertThat(policy.getAllowedFirmsOrigins()).containsExactly("current");
            assertThat(policy.isAllowed("current")).isTrue();
            assertThat(policy.isAllowed("reproducibility")).isFalse();
            assertThat(policy.isAllowed("baseline")).isFalse();
            assertThat(policy.isAllowed(null)).isFalse();
        });
    }

    @Test
    void delimitadorComaSinEspaciosSeLigaCorrectamente() {
        contextRunner.withPropertyValues("sapi.persistence.allowed-firms-origins=current,reproducibility")
                .run(context -> {
                    assertThat(context).hasNotFailed();
                    FirmsOriginPolicy policy = context.getBean(FirmsOriginPolicy.class);
                    assertThat(policy.getAllowedFirmsOrigins()).containsExactly("current", "reproducibility");
                });
    }

    @Test
    void delimitadorComaConEspacioDespuesSeRecortaIgual() {
        // Comportamiento real verificado del Binder de Spring Boot para List<String>: recorta
        // los espacios alrededor de cada elemento separado por coma. "current, reproducibility"
        // liga igual que "current,reproducibility" -- no queda un valor " reproducibility" con
        // espacio que luego fallara silenciosamente contra el contrato.
        contextRunner.withPropertyValues("sapi.persistence.allowed-firms-origins=current, reproducibility")
                .run(context -> {
                    assertThat(context).hasNotFailed();
                    FirmsOriginPolicy policy = context.getBean(FirmsOriginPolicy.class);
                    assertThat(policy.getAllowedFirmsOrigins()).containsExactly("current", "reproducibility");
                });
    }
}

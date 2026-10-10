package cl.sapi.backend.ranking.ml;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

/** Configuración del cliente ML por variables de entorno (SAPI-57, ADR-010). */
class MlServicePropertiesTests {

    @EnableConfigurationProperties(MlServiceProperties.class)
    static class Config {
    }

    private final ApplicationContextRunner runner = new ApplicationContextRunner()
            .withUserConfiguration(Config.class)
            .withPropertyValues("sapi.ml.base-url=http://localhost:8000");

    @ParameterizedTest(name = "\"{0}\" → {1} ms")
    @CsvSource({"60, 60000", "2, 2000", "500ms, 500", "PT1S, 1000", "2s, 2000"})
    @DisplayName("SAPI-57.CA2 — un timeout sin unidad se lee en segundos; con unidad, como se indica")
    void timeoutsBind(String value, long millis) {
        runner.withPropertyValues("sapi.ml.connect-timeout=" + value, "sapi.ml.read-timeout=" + value)
                .run(context -> {
                    MlServiceProperties properties = context.getBean(MlServiceProperties.class);
                    assertThat(properties.connectTimeout()).isEqualTo(Duration.ofMillis(millis));
                    assertThat(properties.readTimeout()).isEqualTo(Duration.ofMillis(millis));
                });
    }

    @Test
    @DisplayName("SAPI-57.CA2 — un timeout 0 o una URL que no es http(s) impiden arrancar")
    void invalidValuesFailAtStartup() {
        runner.withPropertyValues("sapi.ml.connect-timeout=2", "sapi.ml.read-timeout=0")
                .run(context -> assertThat(context).hasFailed());
        runner.withPropertyValues("sapi.ml.base-url=ftp://localhost", "sapi.ml.connect-timeout=2",
                "sapi.ml.read-timeout=60").run(context -> assertThat(context).hasFailed());
    }
}

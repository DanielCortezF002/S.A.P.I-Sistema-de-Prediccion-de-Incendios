# S.A.P.I. v2 - Backend Spring Boot (SAPI-54). Puerto 8080.
# Contrato: contracts/openapi/backend.v0.yaml. Build reproducible con el Maven
# Wrapper versionado sobre Temurin 21; runtime solo con JRE y usuario sin
# privilegios. Sin secretos: la configuración llega por variables de entorno.
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY .mvn .mvn
COPY mvnw pom.xml ./
RUN sh ./mvnw -B -q dependency:go-offline
COPY src src
# Los tests se ejecutan con `mvnw verify` desde el repositorio (necesitan el
# contrato en contracts/openapi/); la imagen solo empaqueta.
RUN sh ./mvnw -B -q -DskipTests package

FROM eclipse-temurin:21-jre
RUN useradd --system --uid 10001 --no-create-home sapi
WORKDIR /app
COPY --from=build /build/target/backend-0.0.1-SNAPSHOT.jar app.jar
USER sapi
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

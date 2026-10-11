# SOLO SANDBOX (no versionado): la etapa de build del backend necesita llegar a
# Maven Central a través del proxy de egress de la sesión, que re-termina TLS.
# Se agrega su CA al truststore del JDK y al almacén del sistema, y el proxy.
# La imagen final del backend usa eclipse-temurin:21-jre, que no se toca.
FROM maven:3.9-eclipse-temurin-21
COPY agent-proxy-ca.crt /usr/local/share/ca-certificates/agent-proxy-ca.crt
# El archivo trae dos certificados; keytool importa solo el primero de cada archivo.
RUN cd /tmp && awk '/BEGIN CERTIFICATE/{n++} {print > ("ccr-" n ".pem")}' \
      /usr/local/share/ca-certificates/agent-proxy-ca.crt \
    && for f in ccr-*.pem; do keytool -importcert -noprompt -cacerts -storepass changeit \
         -alias "$f" -file "$f"; done \
    && update-ca-certificates
# ENV: proxy del sandbox para wget/curl y para la JVM (valores redactados)
# Maven Central (repo.maven.apache.org) responde 429 a la IP compartida del
# sandbox: el wrapper y las dependencias usan el mirror público de Central.
COPY settings.xml [m2-del-contenedor]/settings.xml
ENV MVNW_REPOURL=https://maven-central.storage-download.googleapis.com/maven2

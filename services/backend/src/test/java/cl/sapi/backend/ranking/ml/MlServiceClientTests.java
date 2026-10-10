package cl.sapi.backend.ranking.ml;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowableOfType;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.net.ConnectException;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.net.URI;
import java.net.http.HttpConnectTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Arrays;
import java.util.Locale;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

/**
 * {@link MlServiceClient} contra un servidor HTTP mínimo sobre {@link ServerSocket}, sin contexto Spring:
 * permite cortar o detener la respuesta en un punto exacto (SAPI-57.CA2).
 */
class MlServiceClientTests {

    private static final int MIB = 1024 * 1024;

    @Test
    @DisplayName("SAPI-57.CA2 — un cuerpo mayor al máximo no espera el resto: corta en cuanto supera 1 MiB")
    void oversizedBodyDoesNotWaitForTheRest() throws Exception {
        try (RawServer server = new RawServer(socket -> {
            OutputStream out = socket.getOutputStream();
            out.write(headers(200, 3 * MIB));
            byte[] chunk = new byte[64 * 1024];
            Arrays.fill(chunk, (byte) ' ');
            for (int written = 0; written < 3 * MIB / 2; written += chunk.length) {
                out.write(chunk);
            }
            out.flush();
            Thread.sleep(30_000);
        })) {
            MlServiceClient client = client(server.uri(), Duration.ofSeconds(10));

            long start = System.nanoTime();
            MlResponse response = client.predict(null, "t-oversize");
            Duration elapsed = Duration.ofNanos(System.nanoTime() - start);

            assertThat(response.bodyTooLarge()).isTrue();
            assertThat(response.body()).isEmpty();
            assertThat(elapsed).isLessThan(Duration.ofSeconds(5));
        }
    }

    @Test
    @DisplayName("SAPI-57.CA2 — el cuerpo se detiene después de los headers: TIMEOUT con el status recibido")
    void stalledBodyIsTimeoutWithStatus() throws Exception {
        byte[] body = realRanking();
        try (RawServer server = new RawServer(socket -> {
            OutputStream out = socket.getOutputStream();
            out.write(headers(200, body.length));
            out.write(body, 0, 100);
            out.flush();
            Thread.sleep(5_000);
        })) {
            MlServiceClient client = client(server.uri(), Duration.ofSeconds(1));

            MlCallException error = catchThrowableOfType(MlCallException.class, () -> client.predict(null, "t-stall"));

            assertThat(error.kind()).isEqualTo(MlCallException.Kind.TIMEOUT);
            assertThat(error.httpStatus()).isEqualTo(200);
        }
    }

    @Test
    @DisplayName("SAPI-57.CA2 — la conexión se corta a mitad del cuerpo antes del plazo: UNAVAILABLE con el status")
    void midBodyDisconnectIsUnavailableWithStatus() throws Exception {
        byte[] body = realRanking();
        try (RawServer server = new RawServer(socket -> {
            OutputStream out = socket.getOutputStream();
            out.write(headers(200, body.length));
            out.write(body, 0, 100);
            out.flush();
        })) {
            MlServiceClient client = client(server.uri(), Duration.ofSeconds(10));

            long start = System.nanoTime();
            MlCallException error = catchThrowableOfType(MlCallException.class, () -> client.predict(null, "t-cut"));
            Duration elapsed = Duration.ofNanos(System.nanoTime() - start);

            assertThat(error.kind()).isEqualTo(MlCallException.Kind.UNAVAILABLE);
            assertThat(error.httpStatus()).isEqualTo(200);
            assertThat(elapsed).isLessThan(Duration.ofSeconds(5));
        }
    }

    @Test
    @DisplayName("SAPI-57.CA2 — nadie escucha en el puerto: UNAVAILABLE sin status")
    void connectionRefusedIsUnavailable() throws Exception {
        int port;
        try (ServerSocket socket = new ServerSocket(0, 1, InetAddress.getLoopbackAddress())) {
            port = socket.getLocalPort();
        }
        MlServiceClient client = client(URI.create("http://127.0.0.1:" + port), Duration.ofSeconds(2));

        MlCallException error = catchThrowableOfType(MlCallException.class, () -> client.predict(null, "t-refused"));

        assertThat(error.kind()).isEqualTo(MlCallException.Kind.UNAVAILABLE);
        assertThat(error.httpStatus()).isNull();
    }

    @Test
    @DisplayName("SAPI-57.CA2 — un timeout de conexión o de espera de headers se clasifica como timeout (504)")
    void timeoutClassification() {
        assertThat(MlServiceClient.isTimeout(new ResourceAccessException("x", new HttpConnectTimeoutException("c"))))
                .isTrue();
        assertThat(MlServiceClient.isTimeout(new ResourceAccessException("x", new SocketTimeoutException("r"))))
                .isTrue();
        assertThat(MlServiceClient.isTimeout(new ResourceAccessException("x", new ConnectException("refused"))))
                .isFalse();
    }

    // --- helpers ---------------------------------------------------------------------------------

    private static MlServiceClient client(URI baseUrl, Duration readTimeout) {
        return new MlServiceClient(RestClient.builder(),
                new MlServiceProperties(baseUrl, Duration.ofSeconds(1), readTimeout));
    }

    private static byte[] headers(int status, int contentLength) {
        return String.format(Locale.ROOT, "HTTP/1.1 %d OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n",
                status, contentLength).getBytes(StandardCharsets.US_ASCII);
    }

    private static byte[] realRanking() {
        try (InputStream in = MlServiceClientTests.class.getResourceAsStream("/ml/predict-reproducible-2026-09-01.json")) {
            return in.readAllBytes();
        }
        catch (IOException ex) {
            throw new UncheckedIOException(ex);
        }
    }

    /** Respuesta programada sobre el socket ya conectado. */
    @FunctionalInterface
    private interface SocketAction {
        void respond(Socket socket) throws IOException, InterruptedException;
    }

    /** Servidor HTTP mínimo de una sola conexión: lee la petición completa y ejecuta la respuesta. */
    private static final class RawServer implements AutoCloseable {

        private final ServerSocket server;
        private final Thread thread;

        RawServer(SocketAction action) throws IOException {
            server = new ServerSocket(0, 1, InetAddress.getLoopbackAddress());
            thread = new Thread(() -> {
                try (Socket socket = server.accept()) {
                    readRequest(socket.getInputStream());
                    action.respond(socket);
                }
                catch (IOException ex) {
                    // El cliente cerró la conexión: es parte de varios escenarios.
                }
                catch (InterruptedException ex) {
                    Thread.currentThread().interrupt();
                }
            });
            thread.setDaemon(true);
            thread.start();
        }

        URI uri() {
            return URI.create("http://127.0.0.1:" + server.getLocalPort());
        }

        @Override
        public void close() throws IOException {
            thread.interrupt();
            server.close();
        }

        /** Lee headers y cuerpo (Content-Length o chunked) para no cerrar con datos sin leer. */
        private static void readRequest(InputStream in) throws IOException {
            ByteArrayOutputStream head = new ByteArrayOutputStream();
            int matched = 0;
            byte[] end = {'\r', '\n', '\r', '\n'};
            while (matched < end.length) {
                int b = in.read();
                if (b < 0) {
                    return;
                }
                head.write(b);
                matched = b == end[matched] ? matched + 1 : (b == '\r' ? 1 : 0);
            }
            String headers = head.toString(StandardCharsets.ISO_8859_1).toLowerCase(Locale.ROOT);
            int lengthAt = headers.indexOf("content-length:");
            if (lengthAt >= 0) {
                int lineEnd = headers.indexOf("\r\n", lengthAt);
                in.readNBytes(Integer.parseInt(headers.substring(lengthAt + 15, lineEnd).trim()));
            }
            else if (headers.contains("transfer-encoding: chunked")) {
                while (true) {
                    String sizeLine = readLine(in);
                    int size = Integer.parseInt(sizeLine.trim(), 16);
                    if (size == 0) {
                        readLine(in);
                        return;
                    }
                    in.readNBytes(size);
                    readLine(in);
                }
            }
        }

        private static String readLine(InputStream in) throws IOException {
            StringBuilder line = new StringBuilder();
            int previous = -1;
            while (true) {
                int b = in.read();
                if (b < 0 || (previous == '\r' && b == '\n')) {
                    return line.toString().replace("\r", "");
                }
                line.append((char) b);
                previous = b;
            }
        }
    }
}

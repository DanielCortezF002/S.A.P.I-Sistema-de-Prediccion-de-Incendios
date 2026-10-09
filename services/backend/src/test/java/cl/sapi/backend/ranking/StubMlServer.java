package cl.sapi.backend.ranking;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicReference;

import com.sun.net.httpserver.HttpServer;

/**
 * Servicio ML de prueba: un servidor HTTP real en 127.0.0.1 con respuesta programable. Registra cada
 * petición recibida para verificar qué envía el backend (SAPI-57.CA1, CA4).
 */
final class StubMlServer implements AutoCloseable {

    /** Respuesta programada: código, cuerpo, headers extra y demora antes de responder. */
    record Reply(int status, byte[] body, Map<String, String> headers, long delayMillis) {

        static Reply json(int status, byte[] body) {
            return new Reply(status, body, Map.of("Content-Type", "application/json"), 0);
        }

        Reply delayed(long millis) {
            return new Reply(status, body, headers, millis);
        }
    }

    /** Petición recibida por el stub. */
    record Received(String method, String path, Map<String, List<String>> headers, byte[] body) {

        String header(String name) {
            return headers.entrySet().stream()
                    .filter(entry -> entry.getKey().equalsIgnoreCase(name))
                    .map(entry -> entry.getValue().get(0))
                    .findFirst()
                    .orElse(null);
        }
    }

    private final HttpServer server;
    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final AtomicReference<Reply> reply = new AtomicReference<>(Reply.json(200, new byte[0]));
    private final List<Received> received = new CopyOnWriteArrayList<>();

    StubMlServer() {
        try {
            server = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
        }
        catch (IOException ex) {
            throw new UncheckedIOException(ex);
        }
        server.setExecutor(executor);
        server.createContext("/", exchange -> {
            try (exchange; InputStream in = exchange.getRequestBody()) {
                received.add(new Received(exchange.getRequestMethod(), exchange.getRequestURI().getPath(),
                        Map.copyOf(exchange.getRequestHeaders()), in.readAllBytes()));
                Reply current = reply.get();
                if (current.delayMillis() > 0) {
                    Thread.sleep(current.delayMillis());
                }
                current.headers().forEach((name, value) -> exchange.getResponseHeaders().add(name, value));
                int length = current.body().length;
                exchange.sendResponseHeaders(current.status(), length == 0 ? -1 : length);
                if (length > 0) {
                    try (OutputStream out = exchange.getResponseBody()) {
                        out.write(current.body());
                    }
                }
            }
            catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
            }
            catch (IOException ex) {
                // El cliente cerró la conexión (por ejemplo, por timeout): no hay nada que responder.
            }
        });
        server.start();
    }

    String baseUrl() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    void reply(Reply next) {
        reply.set(next);
    }

    List<Received> received() {
        return received;
    }

    void reset() {
        received.clear();
        reply.set(Reply.json(200, new byte[0]));
    }

    @Override
    public void close() {
        server.stop(0);
        executor.shutdownNow();
    }
}

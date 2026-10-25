package cl.sapi.backend.ranking;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.UnaryOperator;

import com.sun.net.httpserver.HttpServer;

/**
 * R6.3-B (diseño R6.2-C + punto de mutación para la prueba de reserialización). Proxy HTTP transparente entre el backend y el ML real:
 * reenvía cada {@code POST /predict} sin tocar el cuerpo y guarda los bytes exactos que el ML devolvió.
 * Permite exigir igualdad LITERAL de bytes sobre la MISMA evaluación (el backend relaya lo que recibió),
 * sin depender de que dos evaluaciones del ML coincidan (age_hours depende del reloj).
 */
final class RecordingMlProxy implements AutoCloseable {

    private final HttpServer server;
    private final HttpClient client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).build();
    private final AtomicReference<byte[]> lastMlBody = new AtomicReference<>();
    private final AtomicReference<Integer> calls = new AtomicReference<>(0);
    private final AtomicReference<UnaryOperator<byte[]>> mutation = new AtomicReference<>(UnaryOperator.identity());

    RecordingMlProxy(String mlBaseUrl) throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/predict", exchange -> {
            byte[] request;
            try (InputStream in = exchange.getRequestBody()) {
                request = in.readAllBytes();
            }
            try {
                HttpResponse<byte[]> upstream = client.send(
                        HttpRequest.newBuilder(URI.create(mlBaseUrl + "/predict"))
                                .header("Content-Type", "application/json")
                                .POST(HttpRequest.BodyPublishers.ofByteArray(request))
                                .build(),
                        HttpResponse.BodyHandlers.ofByteArray());
                lastMlBody.set(upstream.body());
                calls.updateAndGet(n -> n + 1);
                byte[] relayed = mutation.get().apply(upstream.body());
                exchange.getResponseHeaders().add("Content-Type", "application/json");
                exchange.sendResponseHeaders(upstream.statusCode(), relayed.length);
                try (OutputStream out = exchange.getResponseBody()) {
                    out.write(relayed);
                }
            }
            catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                exchange.sendResponseHeaders(502, -1);
            }
        });
        server.start();
    }

    String baseUrl() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    /** Bytes exactos que el ML devolvió en la última llamada relayada por el backend. */
    byte[] lastMlBody() {
        return lastMlBody.get();
    }

    int calls() {
        return calls.get();
    }

    /** Solo para la prueba de mutación: transforma el cuerpo que se entrega al backend (lo grabado no cambia). */
    void mutateWith(UnaryOperator<byte[]> transform) {
        mutation.set(transform == null ? UnaryOperator.identity() : transform);
    }

    @Override
    public void close() {
        server.stop(0);
    }
}

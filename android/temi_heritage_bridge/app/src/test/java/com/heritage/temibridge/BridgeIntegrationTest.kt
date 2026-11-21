package com.heritage.temibridge

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import java.net.InetAddress
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit

/** 真实 WebSocket 对接 Kotlin 协调器；SDK 事件由明确标记的测试驱动提供。 */
class BridgeIntegrationTest {
    @Test fun actualSocketCarriesHandshakeNavigationStopAndSpeech() {
        MockWebServer().use { server ->
            server.start(InetAddress.getByName("127.0.0.1"), 0)
            val peer = LinkedBlockingQueue<WebSocket>()
            val inbound = LinkedBlockingQueue<JsonObject>()
            server.enqueue(MockResponse().withWebSocketUpgrade(object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) { peer.add(webSocket) }
                override fun onMessage(webSocket: WebSocket, text: String) {
                    inbound.add(JsonParser.parseString(text).asJsonObject)
                }
                override fun onClosing(webSocket: WebSocket, code: Int, reason: String) { webSocket.close(1000, null) }
            }))
            val dispatch = LinkedBlockingQueue<() -> Unit>()
            val driverCalls = mutableListOf<String>()
            val driver = object : BridgeDriver {
                override fun savedLocations() = setOf("exhibit_01")
                override fun goTo(location: String) { driverCalls.add("navigate:$location") }
                override fun stopMovement() { driverCalls.add("stop") }
                override fun speak(text: String): String { driverCalls.add("speak:$text"); return "fake-sdk-uuid" }
                override fun cancelSpeech() { driverCalls.add("cancel") }
            }
            lateinit var transport: WebSocketBridgeClient
            val bridge = BridgeCoordinator(driver, { transport.send(it) })
            transport = WebSocketBridgeClient(object : BridgeDispatcher {
                override fun post(block: () -> Unit) { dispatch.add(block) }
                override fun postDelayed(delayMs: Long, block: () -> Unit) { /* 测试不会自动重试。 */ }
            }, object : BridgeTransportListener {
                override fun onOpen() { assertTrue(bridge.onSocketOpen()) }
                override fun onText(text: String) { assertTrue(bridge.onSocketMessage(text)) }
                override fun onClosed(reason: String) { bridge.onSocketClosed() }
                override fun onStatus(status: String) { }
            })

            fun nextMessage(predicate: (JsonObject) -> Boolean): JsonObject {
                val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
                while (System.nanoTime() < deadline) {
                    dispatch.poll(30, TimeUnit.MILLISECONDS)?.invoke()
                    val message = inbound.poll()
                    if (message != null && predicate(message)) return message
                }
                error("等待实际 WebSocket 消息超时")
            }
            fun event(id: String, status: String) = nextMessage {
                it["type"].asString == "event" && it["id"].asString == id && it["status"].asString == status
            }
            fun ack(id: String) = nextMessage { it["type"].asString == "ack" && it["id"].asString == id }

            bridge.onRobotReady(true)
            try {
                val token = "jvm-integration-token"
                transport.start("ws://127.0.0.1:${server.port}/temi", token)
                val socket = peer.poll(5, TimeUnit.SECONDS)!!
                assertEquals("Bearer $token", server.takeRequest(5, TimeUnit.SECONDS)!!.getHeader("Authorization"))
                nextMessage { it["type"].asString == "hello" }
                socket.send("""{"type":"hello_ack","protocol_version":1}""")
                socket.send("""{"type":"state_request"}""")
                assertTrue(nextMessage { it["type"].asString == "state" }["connected"].asBoolean)
                fun command(id: String, kind: String, key: String, value: String) = socket.send(
                    BridgeProtocol.encode("type" to "command", "id" to id, "command" to kind,
                        key to value, "expires_at_ms" to System.currentTimeMillis() + 20_000),
                )

                command("nav", "navigate", "location", "exhibit_01")
                assertTrue(ack("nav")["accepted"].asBoolean)
                assertTrue("navigate:exhibit_01" in driverCalls)
                bridge.onNavigationStatus("exhibit_01", "going", "test SDK feedback")
                event("nav", "going")
                bridge.onRobotPosition(0.5, 0.1, 0.0, true)
                bridge.tick()
                assertEquals(0.5, nextMessage { it["type"].asString == "state" }["x"].asDouble, 0.0)

                command("stop", "stop", "target_id", "nav")
                assertTrue(ack("stop")["accepted"].asBoolean)
                assertTrue("stop" in driverCalls)
                bridge.onNavigationStatus("exhibit_01", "abort", "test SDK terminal")
                bridge.onVelocity(0.0)
                event("nav", "stopped")
                event("stop", "complete")

                command("tts", "speak", "text", "欢迎")
                assertTrue(ack("tts")["accepted"].asBoolean)
                assertTrue("speak:欢迎" in driverCalls)
                bridge.onTtsStatus("fake-sdk-uuid", "STARTED")
                bridge.onTtsStatus("fake-sdk-uuid", "COMPLETED")
                event("tts", "started")
                event("tts", "complete")
            } finally { transport.stop() }
        }
    }
}

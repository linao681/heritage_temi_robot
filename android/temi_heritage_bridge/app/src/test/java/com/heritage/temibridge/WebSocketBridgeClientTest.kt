package com.heritage.temibridge

import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okio.ByteString
import org.junit.Assert.*
import org.junit.Test
import java.net.InetAddress
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit

class WebSocketBridgeClientTest {
    // Tests use a synthetic credential; no real token is required.
    private val testToken = "mock-token-123456"

    @Test fun endpointPolicyAllowsOnlyLiteralPrivateIpv4AndExactPath() {
        for (host in listOf("127.0.0.1", "127.1.2.3", "10.0.0.1", "172.16.0.1", "172.31.255.254", "192.168.1.2")) {
            val request = bridgeRequest("ws://$host:8765/temi", testToken)
            assertEquals(host, request.url.host)
            assertEquals("/temi", request.url.encodedPath)
            assertEquals("Bearer $testToken", request.header("Authorization"))
        }
        assertTrue(bridgeRequest("wss://192.168.1.2/temi", testToken).url.isHttps)

        for (url in listOf(
            "http://127.0.0.1/temi", "ws://localhost/temi", "ws://[::1]/temi",
            "ws://0.0.0.0/temi", "ws://8.8.8.8/temi", "ws://169.254.1.1/temi",
            "ws://172.15.0.1/temi", "ws://172.32.0.1/temi", "ws://192.169.1.1/temi",
            "ws://127.1/temi", "ws://127.000.0.1/temi", "ws://127.0.0.256/temi",
            "ws://127.0.0.1:0/temi", "ws://127.0.0.1:65536/temi",
            "ws://secret@127.0.0.1/temi", "ws://127.0.0.1/temi?token=secret",
            "ws://127.0.0.1/temi#fragment", "ws://127.0.0.1/temi/",
            "ws://127.0.0.1/TEMI", "ws://127.0.0.1/%74emi", " ws://127.0.0.1/temi"
        )) {
            assertThrows(url, IllegalArgumentException::class.java) { bridgeRequest(url, testToken) }
        }
    }

    @Test fun tokenPolicyRequiresPrintableAsciiWithoutWhitespace() {
        val url = "ws://127.0.0.1/temi"
        for (token in listOf("short", "123456789012345 ", "123456789012345\t", "123456789012345\n",
            "123456789012345\u0000", "123456789012345中")) {
            assertThrows(IllegalArgumentException::class.java) { bridgeRequest(url, token) }
        }
    }

    @Test fun loopbackAuthenticationMessageDeliveryAndManualStop() = withServer { server, client, dispatcher, listener ->
        val peer = Peer()
        server.enqueue(peer.response())
        client.start(serverUrl(server), testToken)
        dispatcher.await { listener.opens == 1 }
        val request = server.takeRequest(5, TimeUnit.SECONDS)!!
        assertEquals("/temi", request.path)
        assertEquals("Bearer $testToken", request.getHeader("Authorization"))

        val socket = peer.sockets.poll(5, TimeUnit.SECONDS)!!
        val message = """{"type":"example","text":"欢迎"}"""
        assertTrue(socket.send(message))
        dispatcher.await { listener.texts.size == 1 }
        assertEquals(listOf(message), listener.texts)
        assertTrue(client.send(message))
        assertEquals(message, peer.received.poll(5, TimeUnit.SECONDS))

        // A malformed restart does not disconnect or overwrite the current session.
        assertThrows(IllegalArgumentException::class.java) { client.start("ws://8.8.8.8/temi", testToken) }
        assertTrue(client.send(message))
        assertEquals(message, peer.received.poll(5, TimeUnit.SECONDS))
        assertTrue(listener.closes.isEmpty())

        client.stop()
        assertEquals(1, listener.closes.size)
        assertFalse(client.send(message))
        assertTrue(dispatcher.delayed.isEmpty())
    }

    @Test fun remoteCloseReconnectsAndStopInvalidatesPendingRetry() = withServer { server, client, dispatcher, listener ->
        val first = Peer()
        val second = Peer()
        server.enqueue(first.response())
        server.enqueue(second.response())
        client.start(serverUrl(server), testToken)
        dispatcher.await { listener.opens == 1 }
        val firstSocket = first.sockets.poll(5, TimeUnit.SECONDS)!!
        assertTrue(firstSocket.close(1000, "remote close"))
        dispatcher.await { listener.closes.size == 1 && dispatcher.delayed.size == 1 }
        assertFalse(client.send("{}"))
        dispatcher.runRetry()

        dispatcher.await { listener.opens == 2 }
        val secondSocket = second.sockets.poll(5, TimeUnit.SECONDS)!!
        // Nothing from the first session is replayed on the new connection.
        assertNull(second.received.poll(100, TimeUnit.MILLISECONDS))
        assertTrue(secondSocket.close(1000, "remote close"))
        dispatcher.await { listener.closes.size == 2 && dispatcher.delayed.size == 1 }
        client.stop()
        dispatcher.runRetry()
        assertEquals(2, server.requestCount)
        assertFalse(client.send("{}"))
    }

    @Test fun binaryOversizedAndExplicitProtocolErrorsInvalidateConnection() = withServer { server, client, dispatcher, listener ->
        val peers = List(3) { Peer() }
        peers.forEach { server.enqueue(it.response()) }
        client.start(serverUrl(server), testToken)

        dispatcher.await { listener.opens == 1 }
        assertTrue(peers[0].sockets.poll(5, TimeUnit.SECONDS)!!.send(ByteString.of(1, 2, 3)))
        dispatcher.await { listener.closes.size == 1 && dispatcher.delayed.size == 1 }
        assertTrue(listener.texts.isEmpty())
        dispatcher.runRetry()

        dispatcher.await { listener.opens == 2 }
        val overLimit = "中".repeat(22_000) // 66,000 bytes, not 22,000 bytes.
        assertFalse(client.send(overLimit))
        assertTrue(peers[1].sockets.poll(5, TimeUnit.SECONDS)!!.send(overLimit))
        dispatcher.await { listener.closes.size == 2 && dispatcher.delayed.size == 1 }
        assertTrue(listener.texts.isEmpty())
        dispatcher.runRetry()

        dispatcher.await { listener.opens == 3 }
        client.reconnectAfterProtocolError()
        assertEquals(3, listener.closes.size)
        assertFalse(client.send("{}"))
        assertEquals(1, dispatcher.delayed.size)
    }

    private fun withServer(test: (MockWebServer, WebSocketBridgeClient, QueuedDispatcher, RecordingListener) -> Unit) {
        MockWebServer().use { server ->
            server.start(InetAddress.getByName("127.0.0.1"), 0)
            val dispatcher = QueuedDispatcher()
            val listener = RecordingListener()
            val client = WebSocketBridgeClient(dispatcher, listener)
            try {
                test(server, client, dispatcher, listener)
                assertTrue(listener.statuses.none { it.contains(testToken) })
                assertTrue(listener.closes.none { it.contains(testToken) })
            } finally {
                client.stop()
            }
        }
    }

    private fun serverUrl(server: MockWebServer) = "ws://127.0.0.1:${server.port}/temi"

    private class Peer : WebSocketListener() {
        val sockets = LinkedBlockingQueue<WebSocket>()
        val received = LinkedBlockingQueue<String>()
        fun response() = MockResponse().withWebSocketUpgrade(this)
        override fun onOpen(webSocket: WebSocket, response: okhttp3.Response) { sockets.add(webSocket) }
        override fun onMessage(webSocket: WebSocket, text: String) { received.add(text) }
        override fun onClosing(webSocket: WebSocket, code: Int, reason: String) { webSocket.close(1000, null) }
    }

    private class RecordingListener : BridgeTransportListener {
        var opens = 0
        val texts = mutableListOf<String>()
        val closes = mutableListOf<String>()
        val statuses = mutableListOf<String>()
        override fun onOpen() { opens++ }
        override fun onText(text: String) { texts.add(text) }
        override fun onClosed(reason: String) { closes.add(reason) }
        override fun onStatus(status: String) { statuses.add(status) }
    }

    private class QueuedDispatcher : BridgeDispatcher {
        private val posted = LinkedBlockingQueue<() -> Unit>()
        val delayed = ArrayDeque<Pair<Long, () -> Unit>>()
        override fun post(block: () -> Unit) { posted.add(block) }
        override fun postDelayed(delayMs: Long, block: () -> Unit) { delayed.addLast(delayMs to block) }

        fun runRetry() { delayed.removeFirst().second.invoke() }

        fun await(condition: () -> Boolean) {
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
            while (!condition()) {
                val remaining = deadline - System.nanoTime()
                check(remaining > 0) { "Timed out waiting for transport event" }
                val next = posted.poll(remaining, TimeUnit.NANOSECONDS)
                checkNotNull(next) { "Timed out waiting for transport event" }.invoke()
            }
        }
    }
}

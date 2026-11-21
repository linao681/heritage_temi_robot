package com.heritage.temibridge

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import java.net.Proxy
import java.net.URI
import java.util.concurrent.TimeUnit

interface BridgeDispatcher {
    fun post(block: () -> Unit)
    fun postDelayed(delayMs: Long, block: () -> Unit)
}

interface BridgeTransportListener {
    fun onOpen()
    fun onText(text: String)
    fun onClosed(reason: String)
    fun onStatus(status: String)
}

/** 验证地址及认证 token 之后才创建请求；不允许 DNS、重定向或公网地址。 */
internal fun bridgeRequest(url: String, token: String): Request {
    val uri = runCatching { URI(url) }.getOrNull()
        ?: throw IllegalArgumentException("无效 Bridge 地址")
    val host = uri.host ?: throw IllegalArgumentException("必须使用私有 IPv4 地址")
    val parts = host.split('.')
    val bytes = parts.map { it.toIntOrNull() }
    val validIpv4 = parts.size == 4 && parts.all { it.matches(Regex("0|[1-9][0-9]{0,2}")) } &&
        bytes.all { it != null && it in 0..255 }
    require(validIpv4) { "必须使用私有 IPv4 地址" }
    val a = bytes[0]!!
    val b = bytes[1]!!
    require(a == 127 || a == 10 || (a == 172 && b in 16..31) || (a == 192 && b == 168)) { "禁止公网地址" }
    require(uri.scheme in listOf("ws", "wss") && uri.rawPath == "/temi" &&
        uri.rawUserInfo == null && uri.rawQuery == null && uri.rawFragment == null &&
        (uri.port == -1 || uri.port in 1..65535)) { "地址必须使用 ws/wss 和 /temi 路径" }
    require(token.length >= 16 && token.all { it.code in 33..126 }) { "认证 token 格式无效" }
    return Request.Builder().url(url).header("Authorization", "Bearer $token").build()
}

/** OkHttp 负责 Ping/Pong；所有状态变化通过 dispatcher 串行传回 Android 主线程。 */
class WebSocketBridgeClient(
    private val dispatcher: BridgeDispatcher,
    private val listener: BridgeTransportListener,
    client: OkHttpClient = OkHttpClient(),
) {
    private val client = client.newBuilder().proxy(Proxy.NO_PROXY)
        .followRedirects(false).followSslRedirects(false)
        .pingInterval(5, TimeUnit.SECONDS).connectTimeout(5, TimeUnit.SECONDS).build()
    private var request: Request? = null
    private var socket: WebSocket? = null
    private var generation = 0L
    private var opened = false
    private var retries = 0

    fun start(url: String, token: String) {
        val validated = bridgeRequest(url, token) // 失败不得破坏已有连接。
        stop()
        request = validated
        retries = 0
        connect()
    }

    private fun connect() {
        val current = request ?: return
        val session = ++generation
        listener.onStatus("连接中")
        socket = client.newWebSocket(current, object : WebSocketListener() {
            private fun dispatch(ws: WebSocket, block: () -> Unit) = dispatcher.post {
                if (session == generation && ws === socket) block() else ws.cancel()
            }

            override fun onOpen(webSocket: WebSocket, response: Response) = dispatch(webSocket) {
                opened = true
                retries = 0
                listener.onStatus("网络已连接，等待协议同步")
                listener.onOpen()
            }

            override fun onMessage(webSocket: WebSocket, text: String) = dispatch(webSocket) {
                if (text.isEmpty() || text.toByteArray(Charsets.UTF_8).size > BridgeProtocol.MAX_BYTES || '\uFFFD' in text) {
                    reconnectAfterProtocolError()
                } else listener.onText(text)
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) = dispatch(webSocket) {
                reconnectAfterProtocolError()
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) = dispatch(webSocket) {
                retire("服务器关闭连接", retry = true, graceful = true)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = dispatch(webSocket) {
                retire("连接关闭", retry = true)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) = dispatch(webSocket) {
                // 不记录 exception/request 可能包含的认证数据。
                retire("连接失败或心跳超时", retry = true)
            }
        })
    }

    fun send(text: String): Boolean {
        if (!opened || text.isEmpty() || text.toByteArray(Charsets.UTF_8).size > BridgeProtocol.MAX_BYTES) return false
        val sent = socket?.send(text) == true
        if (!sent) retire("发送失败", retry = true)
        return sent
    }

    fun reconnectAfterProtocolError() { retire("协议错误", retry = true) }

    fun stop() {
        request = null
        retire("主动断开", retry = false, graceful = true)
    }

    private fun retire(reason: String, retry: Boolean, graceful: Boolean = false) {
        val previous = socket
        val wasOpen = opened
        opened = false
        socket = null
        val retired = ++generation
        // 先禁用发送再通知协调器，确保本地停止旧任务且不向新会话重放。
        if (wasOpen) listener.onClosed(reason)
        if (graceful) previous?.close(1000, null) else previous?.cancel()
        listener.onStatus(reason)
        if (retry && request != null) {
            val delay = (1000L shl retries.coerceAtMost(4)).coerceAtMost(15_000L)
            retries++
            dispatcher.postDelayed(delay) {
                if (retired == generation && request != null && socket == null) connect()
            }
        }
    }
}

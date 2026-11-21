package com.heritage.temibridge

import android.app.Activity
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

/** 前台调试 Bridge；认证 token 不保存，退出前尽力停止本 App 的控制任务。 */
class MainActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var transport: WebSocketBridgeClient
    private lateinit var coordinator: BridgeCoordinator
    private lateinit var driver: SdkTemiDriver
    private lateinit var status: TextView
    private lateinit var stopButton: Button
    private var sdkReady = false
    private var networkStatus = "未连接"
    private val tick = object : Runnable {
        override fun run() {
            coordinator.tick()
            handler.postDelayed(this, 100L)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            val padding = (20 * resources.displayMetrics.density).toInt()
            setPadding(padding, padding, padding, padding)
        }
        val title = TextView(this).apply { text = "非遗展厅导览 · temi Bridge"; textSize = 24f }
        status = TextView(this).apply { textSize = 16f }
        val address = EditText(this).apply {
            hint = "ws://192.168.x.x:8765/temi"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            isSingleLine = true
        }
        val token = EditText(this).apply {
            hint = "Gateway 认证 token"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            isSingleLine = true
            isSaveEnabled = false
            if (android.os.Build.VERSION.SDK_INT >= 26) importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO
        }
        val connectButton = Button(this).apply { text = "连接 Gateway" }
        val disconnectButton = Button(this).apply { text = "断开（停止本应用任务）" }
        stopButton = Button(this).apply { text = "本地停止运动"; isEnabled = false }
        val note = TextView(this).apply {
            text = "仅在可信局域网与前台使用。真实导航须先设置已保存地点；协议确认不等于物理安全证明。"
        }
        listOf(title, status, address, token, connectButton, disconnectButton, stopButton, note).forEach { content.addView(it) }
        setContentView(content)

        @Suppress("DEPRECATION")
        val activityInfo = packageManager.getActivityInfo(componentName, PackageManager.GET_META_DATA)
        driver = SdkTemiDriver(activityInfo) { ready ->
            sdkReady = ready
            stopButton.isEnabled = ready
            showStatus()
        }
        coordinator = BridgeCoordinator(driver, { message -> transport.send(message) })
        transport = WebSocketBridgeClient(object : BridgeDispatcher {
            override fun post(block: () -> Unit) { handler.post { block() } }
            override fun postDelayed(delayMs: Long, block: () -> Unit) { handler.postDelayed({ block() }, delayMs) }
        }, object : BridgeTransportListener {
            override fun onOpen() { if (!coordinator.onSocketOpen()) transport.reconnectAfterProtocolError() }
            override fun onText(text: String) {
                if (!coordinator.onSocketMessage(text)) transport.reconnectAfterProtocolError()
                else { networkStatus = "已连接 / 协议处理中"; showStatus() }
            }
            override fun onClosed(reason: String) { coordinator.onSocketClosed() }
            override fun onStatus(status: String) { networkStatus = status; showStatus() }
        })
        connectButton.setOnClickListener {
            try {
                transport.start(address.text.toString(), token.text.toString())
                token.text.clear()
            } catch (_: IllegalArgumentException) {
                networkStatus = "地址或 token 无效，请使用私有 IPv4 /temi"
                showStatus()
            }
        }
        disconnectButton.setOnClickListener { transport.stop() }
        stopButton.setOnClickListener { coordinator.localStop() }
        showStatus()
    }

    private fun showStatus() {
        status.text = "网络：$networkStatus\ntemi SDK：${if (sdkReady) "Ready" else "未 Ready"}"
    }

    override fun onStart() {
        super.onStart()
        driver.startListening(coordinator)
        handler.post(tick)
    }

    override fun onStop() {
        handler.removeCallbacks(tick)
        transport.stop()
        driver.stopListening()
        coordinator.onRobotReady(false)
        sdkReady = false
        stopButton.isEnabled = false
        showStatus()
        super.onStop()
    }
}

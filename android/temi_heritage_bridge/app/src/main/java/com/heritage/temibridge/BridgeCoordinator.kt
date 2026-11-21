package com.heritage.temibridge

import kotlin.math.abs
import com.heritage.temibridge.BridgeProtocol.Command

/** 实机调用仅由 Android SDK 适配器实现；测试使用独立假驱动。 */
interface BridgeDriver {
    fun savedLocations(): Set<String>
    fun goTo(location: String)
    fun stopMovement()
    fun speak(text: String): String
    fun cancelSpeech()
    fun setNavigationSpeed(speedMps: Float): Int = -1
}

/** 所有方法均在同一个 UI 线程调用。断线后保留待确认动作的隔离槽位。 */
class BridgeCoordinator(
    private val driver: BridgeDriver,
    private val send: (String) -> Boolean,
    private val nowMs: () -> Long = System::currentTimeMillis,
) {
    private data class Task(val command: Command, val epoch: Long, var started: Boolean = false,
                            var sdkId: String = "", var reported: Boolean = false)
    private data class StopWait(var request: Task?, var terminal: Boolean, var zero: Boolean = false)

    private var opened = false
    private var helloAck = false
    private var synced = false
    private var epoch = 0L
    private var ready = false
    private var battery = -1
    private var x = 0.0
    private var y = 0.0
    private var yaw = 0.0
    private var validPose = false
    private var velocityMoving = false
    private var navStatus = "disconnected"
    private var location = ""
    private var error = ""
    private var nav: Task? = null
    private var speech: Task? = null
    private var stopping: StopWait? = null
    private var canceling: Task? = null
    private var cancelRequested = false
    private var lastNavId = ""
    private val seen = LinkedHashMap<String, Long>()

    fun onSocketOpen(): Boolean {
        if (opened) onSocketClosed()
        opened = true
        helloAck = false
        synced = false
        epoch++
        return send(BridgeProtocol.encode("type" to "hello", "protocol_version" to 1))
    }

    fun onSocketClosed() {
        if (!opened) return
        opened = false
        helloAck = false
        synced = false
        // 旧会话的控制确认必须失效；物理停止证据仍待收集。
        stopping?.request = null
        canceling = null
        if (nav != null || stopping != null) requestStop(null)
        if (speech != null) requestCancel(null)
    }

    fun onSocketMessage(text: String): Boolean {
        if (!opened) return false
        val message = BridgeProtocol.parse(text) ?: return false
        return when (message.type) {
            "hello_ack" -> if (helloAck) false else { helloAck = true; true }
            "state_request" -> {
                if (!helloAck) false else {
                    synced = true
                    if (sendState()) true else { synced = false; false }
                }
            }
            "command" -> synced && handleCommand(message.command!!)
            else -> false
        }
    }

    private fun sendState(): Boolean = !synced || send(BridgeProtocol.encode(
        "type" to "state", "connected" to ready, "battery_percentage" to battery,
        "x" to x, "y" to y, "yaw" to yaw, "navigation_status" to navStatus,
        "current_location" to location, "is_moving" to (velocityMoving || nav != null || stopping != null),
        "error_message" to error, "frame_id" to if (ready && validPose) "temi_sdk_unverified" else "",
    ))

    private fun ack(command: Command, accepted: Boolean, message: String): Boolean = send(BridgeProtocol.encode(
        "type" to "ack", "id" to command.id, "accepted" to accepted, "message" to message,
    ))

    private fun event(task: Task, kind: String, status: String, description: String = "") {
        if (opened && synced && task.epoch == epoch) send(BridgeProtocol.encode(
            "type" to "event", "id" to task.command.id, "event" to kind,
            "status" to status, "description" to description,
        ))
    }

    private fun handleCommand(command: Command): Boolean {
        val now = nowMs()
        seen.entries.removeAll { it.value <= now }
        if (seen.containsKey(command.id)) return ack(command, false, "duplicate id")
        if (seen.size >= if (command.kind == "stop" || command.kind == "cancel_speech") 8192 else 8064)
            return ack(command, false, "command history full")
        seen[command.id] = maxOf(command.expires, now + 300_000L)
        if (command.expires <= now || command.expires - now > 86_400_000L)
            return ack(command, false, "expired or invalid deadline")
        if (!ready) return ack(command, false, "SDK not ready")
        val task = Task(command, epoch)
        when (command.kind) {
            "navigate" -> {
                if (nav != null || stopping != null || velocityMoving) return ack(command, false, "motion not idle")
                val validLocation = runCatching { command.argument in driver.savedLocations() }.getOrDefault(false)
                if (!validLocation) return ack(command, false, "unknown saved location")
                if (!ack(command, true, "accepted")) return false
                nav = task
                navStatus = "start"
                error = ""
                try { driver.goTo(command.argument) }
                catch (_: Exception) {
                    task.reported = true
                    event(task, "navigation_status", "timeout", "SDK call failed; stop unconfirmed")
                    requestStop(null)
                }
            }
            "set_speed" -> {
                if (nav == null || nav?.command?.id != command.navigationSessionId || !nav!!.started ||
                    stopping != null || speech != null || cancelRequested)
                    return ack(command, false, "stale navigation session or motion is blocked")
                if (!ack(command, true, "accepted")) return false
                val result = runCatching { driver.setNavigationSpeed(command.targetSpeedMps) }.getOrDefault(-1)
                val status = if (result == 200) "complete" else "error"
                event(task, "speed_status", status,
                    "target_speed_mps=${command.targetSpeedMps};sdk_code=$result;reason=${command.controlReason}")
            }
            "speak" -> {
                if (speech != null || cancelRequested) return ack(command, false, "speech busy")
                if (!ack(command, true, "accepted")) return false
                speech = task
                try { task.sdkId = driver.speak(command.argument) }
                catch (_: Exception) {
                    task.reported = true
                    event(task, "speech_status", "error", "SDK call failed")
                    requestCancel(null)
                }
            }
            "stop" -> {
                val target = command.argument
                if (target.isNotEmpty() && target != (nav?.command?.id ?: lastNavId))
                    return ack(command, false, "stale stop target")
                if (stopping?.request != null) return ack(command, false, "stop pending")
                if (!ack(command, true, "accepted")) return false
                requestStop(task)
            }
            "cancel_speech" -> {
                if (speech?.command?.id != command.argument || canceling != null)
                    return ack(command, false, "stale or busy speech cancellation")
                if (!ack(command, true, "accepted")) return false
                requestCancel(task)
            }
        }
        return true
    }

    /** STOP 的 Unit 返回只表示已调用；必须等待匹配终态和新的零速度证据。 */
    private fun requestStop(request: Task?, force: Boolean = false) {
        val previous = stopping
        if (previous != null && request == null && !force) return
        val wait = previous ?: StopWait(null, nav == null)
        wait.request = request
        wait.zero = false
        stopping = wait
        error = "停车待确认"
        try { driver.stopMovement() }
        catch (_: Exception) {
            if (request != null) event(request, "stop_status", "error", "SDK stop call failed")
            wait.request = null
        }
    }

    private fun confirmStop() {
        val wait = stopping ?: return
        if (!wait.zero || !wait.terminal) return
        val current = nav
        if (current != null && !current.reported) event(current, "navigation_status", "stopped", "motion stopped")
        if (current != null) lastNavId = current.command.id
        nav = null
        wait.request?.let {
            if (nowMs() >= it.command.expires)
                event(it, "stop_status", "error", "stop evidence arrived after deadline")
            else event(it, "stop_status", "complete", "stop callback and zero velocity observed")
        }
        stopping = null
        navStatus = if (ready) "stopped" else "disconnected"
        error = ""
        sendState()
    }

    private fun requestCancel(request: Task?, force: Boolean = false) {
        if (cancelRequested && request == null && !force) return
        cancelRequested = true
        canceling = request
        try { driver.cancelSpeech() }
        catch (_: Exception) {
            if (request != null) event(request, "speech_cancel_status", "error", "SDK cancel call failed")
            canceling = null
        }
    }

    fun localStop() { requestStop(stopping?.request, force = true) }

    fun onRobotReady(ready: Boolean) {
        val wasReady = this.ready
        this.ready = ready
        if (!ready) {
            navStatus = "disconnected"
            validPose = false
            battery = -1
            stopping?.request = null
            canceling = null
            if (nav != null || stopping != null) requestStop(null)
            if (speech != null) requestCancel(null)
        } else if (!wasReady) {
            // SDK 重新就绪后重试尚未确认的本地安全动作，不重放导航/播报。
            if (nav != null || stopping != null) requestStop(null, force = true)
            else navStatus = "idle"
            if (speech != null) requestCancel(null, force = true)
        }
        sendState()
    }

    fun onRobotPosition(x: Double, y: Double, yaw: Double, valid: Boolean) {
        validPose = valid && x.isFinite() && y.isFinite() && yaw.isFinite()
        this.x = if (validPose) x else 0.0
        this.y = if (validPose) y else 0.0
        this.yaw = if (validPose) yaw else 0.0
    }

    fun onBattery(level: Int?) { battery = level?.takeIf { it in 0..100 } ?: -1 }

    fun onVelocity(velocity: Double) {
        if (!velocity.isFinite() || !ready) return
        velocityMoving = abs(velocity) > 0.001
        stopping?.let { it.zero = !velocityMoving; confirmStop() }
    }

    fun onNavigationStatus(location: String, status: String, description: String) {
        val task = nav ?: return
        if (task.command.argument != location || !ready) return
        val terminal = status == "complete" || status == "abort"
        if (stopping != null) {
            if (terminal) { stopping?.terminal = true; confirmStop() }
            return
        }
        if (nowMs() >= task.command.expires) { tick(); return }
        if (status in setOf("start", "calculating", "going", "reposing")) {
            task.started = true
            navStatus = status
            event(task, "navigation_status", status, description)
        } else if (terminal && task.started && !task.reported) {
            navStatus = status
            if (status == "complete") this.location = location
            event(task, "navigation_status", status, description)
            lastNavId = task.command.id
            nav = null
        }
    }

    fun onTtsStatus(sdkId: String, status: String) {
        val task = speech ?: return
        if (task.sdkId != sdkId || sdkId.isBlank() || !ready) return
        val mapped = when (status.uppercase()) {
            "STARTED" -> "started"
            "COMPLETED", "COMPLETE" -> "complete"
            "ERROR" -> "error"
            "NOT_ALLOWED" -> "not_allowed"
            "CANCELED", "CANCELLED" -> "canceled"
            else -> return
        }
        if (mapped == "started") {
            if (nowMs() >= task.command.expires) { tick(); return }
            if (!task.reported && !cancelRequested) event(task, "speech_status", mapped)
            return
        }
        if (!task.reported) {
            val terminal = when {
                nowMs() >= task.command.expires -> "error"
                cancelRequested -> "canceled"
                else -> mapped
            }
            event(task, "speech_status", terminal)
        }
        canceling?.let {
            if (nowMs() >= it.command.expires)
                event(it, "speech_cancel_status", "error", "terminal arrived after deadline")
            else event(it, "speech_cancel_status", "complete", "matching TTS terminal observed")
        }
        speech = null
        canceling = null
        cancelRequested = false
    }

    /** 每个 tick 都检查本地任务期限，即使 Linux 已离线也不会自动续跑。 */
    fun tick() {
        val now = nowMs()
        nav?.let { task ->
            if (now >= task.command.expires && !task.reported) {
                task.reported = true
                event(task, "navigation_status", "timeout", "local navigation deadline")
                navStatus = "timeout"
                requestStop(null)
            }
        }
        stopping?.let { wait ->
            wait.request?.let { task -> if (now >= task.command.expires) {
                event(task, "stop_status", "error", "stop not confirmed before deadline")
                wait.request = null
            } }
        }
        speech?.let { task -> if (now >= task.command.expires && !task.reported) {
            task.reported = true
            event(task, "speech_status", "error", "local speech deadline")
            requestCancel(null)
        } }
        canceling?.let { task -> if (now >= task.command.expires) {
            event(task, "speech_cancel_status", "error", "speech cancel not confirmed")
            canceling = null
        } }
        sendState()
    }
}

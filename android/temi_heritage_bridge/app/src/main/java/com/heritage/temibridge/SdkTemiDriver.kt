package com.heritage.temibridge

import android.content.pm.ActivityInfo
import android.util.Log
import com.robotemi.sdk.BatteryData
import com.robotemi.sdk.Robot
import com.robotemi.sdk.TtsRequest
import com.robotemi.sdk.listeners.OnBatteryStatusChangedListener
import com.robotemi.sdk.listeners.OnGoToLocationStatusChangedListener
import com.robotemi.sdk.listeners.OnMovementVelocityChangedListener
import com.robotemi.sdk.listeners.OnRobotReadyListener
import com.robotemi.sdk.navigation.listener.OnCurrentPositionChangedListener
import com.robotemi.sdk.navigation.model.Position

/** 唯一的实体 SDK 适配层；监听器生命周期及控制方法均在 Android 主线程。 */
class SdkTemiDriver(
    private val activityInfo: ActivityInfo,
    private val onReadyChanged: (Boolean) -> Unit,
) : BridgeDriver, OnRobotReadyListener, OnCurrentPositionChangedListener,
    OnBatteryStatusChangedListener, OnGoToLocationStatusChangedListener,
    OnMovementVelocityChangedListener, Robot.TtsListener {

    private var robot: Robot? = null
    private var coordinator: BridgeCoordinator? = null

    /** 绑定官方服务；没有 Launcher 服务的普通 Android 设备不会报告 Ready。 */
    fun startListening(sink: BridgeCoordinator) {
        if (robot != null) return
        coordinator = sink
        try {
            val instance = Robot.getInstance()
            robot = instance
            instance.addOnCurrentPositionChangedListener(this)
            instance.addOnBatteryStatusChangedListener(this)
            instance.addOnGoToLocationStatusChangedListener(this)
            instance.addOnMovementVelocityChangedListener(this)
            instance.addTtsListener(this)
            instance.addOnRobotReadyListener(this)
        } catch (_: Exception) {
            Log.w("TemiBridge", "SDK 监听器初始化失败")
            stopListening()
            sink.onRobotReady(false)
            onReadyChanged(false)
        }
    }

    fun stopListening() {
        robot?.let { instance ->
            // 分别注销，避免单个异常阻止其余监听器清理。
            listOf<() -> Unit>(
                { instance.removeOnRobotReadyListener(this) },
                { instance.removeOnCurrentPositionChangedListener(this) },
                { instance.removeOnBatteryStatusChangedListener(this) },
                { instance.removeOnGoToLocationStatusChangedListener(this) },
                { instance.removeOnMovementVelocityChangedListener(this) },
                { instance.removeTtsListener(this) },
            ).forEach { runCatching { it() } }
        }
        robot = null
        coordinator = null
    }

    private fun readyRobot(): Robot = robot?.takeIf { it.isReady }
        ?: throw IllegalStateException("temi SDK 未就绪")

    override fun savedLocations(): Set<String> = readyRobot().locations.toSet()

    override fun goTo(location: String) {
        val instance = readyRobot()
        require(location in instance.locations) { "目标不是已保存地点" }
        // 保留机器人原有避障、安全和速度设置，不强制关闭避障。
        instance.goTo(location)
    }

    override fun stopMovement() { readyRobot().stopMovement() }

    override fun setNavigationSpeed(speedMps: Float): Int =
        TemiSpeedManager { speed -> readyRobot().setCurrentGoToSpeed(speed) }.setCurrentNavigationSpeed(speedMps)

    override fun speak(text: String): String {
        val instance = readyRobot()
        val request = TtsRequest.create(text, language = TtsRequest.Language.ZH_CN)
        instance.speak(request)
        return request.id.toString()
    }

    override fun cancelSpeech() { readyRobot().cancelAllTtsRequests() }

    override fun onRobotReady(isReady: Boolean) {
        if (isReady) {
            robot?.let { instance ->
                runCatching { instance.onStart(activityInfo) }
                runCatching { instance.batteryData }.getOrNull()?.let { coordinator?.onBattery(it.level) }
            }
        }
        coordinator?.onRobotReady(isReady)
        onReadyChanged(isReady)
    }

    override fun onCurrentPositionChanged(position: Position) {
        // 坐标原值仅用于遥测；SDK 量纲/真实地图仍需实体标定。
        val valid = robot?.isReady == true && position.isInMapArea == true
        coordinator?.onRobotPosition(position.x.toDouble(), position.y.toDouble(), position.yaw.toDouble(), valid)
    }

    override fun onBatteryStatusChanged(batteryData: BatteryData?) {
        coordinator?.onBattery(batteryData?.level)
    }

    override fun onGoToLocationStatusChanged(location: String, status: String, descriptionId: Int, description: String) {
        coordinator?.onNavigationStatus(location, status, description.ifBlank { "SDK description $descriptionId" })
    }

    override fun onMovementVelocityChanged(velocity: Float) { coordinator?.onVelocity(velocity.toDouble()) }

    override fun onTtsStatusChanged(ttsRequest: TtsRequest) {
        coordinator?.onTtsStatus(ttsRequest.id.toString(), ttsRequest.status.name)
    }
}

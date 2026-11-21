package com.heritage.temibridge

/** temi SDK 的目标速度封装；只设置当前应用的有效 GoTo，不等同于实测速度。 */
class TemiSpeedManager(private val setSpeed: (Float) -> Int) {
    fun setCurrentNavigationSpeed(speedMps: Float): Int {
        require(speedMps.isFinite() && speedMps in 0.3f..0.8f) { "软件导航限速为 0.3~0.8 m/s" }
        return setSpeed(speedMps)
    }
}

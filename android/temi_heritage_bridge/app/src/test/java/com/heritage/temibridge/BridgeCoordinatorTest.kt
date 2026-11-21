package com.heritage.temibridge

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import org.junit.Assert.*
import org.junit.Test

class BridgeCoordinatorTest {
    private class Fixture {
        var time = 100_000L
        val out = mutableListOf<JsonObject>()
        val calls = mutableListOf<String>()
        var failSend = false
        var speedResult = 200
        val driver = object : BridgeDriver {
            override fun savedLocations() = setOf("hall", "door")
            override fun goTo(location: String) { calls.add("go:$location") }
            override fun stopMovement() { calls.add("stop") }
            override fun speak(text: String): String {
                calls.add("speak:$text")
                return "sdk-uuid-${calls.size}"
            }
            override fun cancelSpeech() { calls.add("cancel") }
            override fun setNavigationSpeed(speedMps: Float): Int { calls.add("speed:$speedMps"); return speedResult }
        }
        val bridge = BridgeCoordinator(driver, {
            if (failSend) false
            else {
                val message = JsonParser.parseString(it).asJsonObject
                out.add(message)
                calls.add("send:${message["type"].asString}:${message["id"]?.asString.orEmpty()}")
                true
            }
        }, { time })

        fun handshake(ready: Boolean = true) {
            bridge.onRobotReady(ready)
            assertTrue(bridge.onSocketOpen())
            assertTrue(bridge.onSocketMessage("""{"type":"hello_ack","protocol_version":1}"""))
            assertTrue(bridge.onSocketMessage("""{"type":"state_request"}"""))
        }

        fun command(id: String, name: String, parameter: String, value: String,
                    expires: Long = time + 10_000): Boolean =
            bridge.onSocketMessage("""{"type":"command","id":"$id","command":"$name","$parameter":"$value","expires_at_ms":$expires}""")

        fun nav(id: String = "n", expires: Long = time + 10_000) =
            command(id, "navigate", "location", "hall", expires)

        fun ack(id: String) = out.last { it["type"].asString == "ack" && it["id"].asString == id }["accepted"].asBoolean
        fun statuses(id: String): List<String> = out.filter {
            it["type"].asString == "event" && it["id"].asString == id
        }.map { it["status"].asString }
        fun state() = out.last { it["type"].asString == "state" }
        fun sdkId() = "sdk-uuid-${calls.indexOfLast { it.startsWith("speak:") } + 1}"
    }


    @Test fun dynamicSpeedRequiresMatchingActiveNavigationAndReportsSdkCode() {
        val f = Fixture()
        f.handshake()
        assertTrue(f.nav())
        f.bridge.onNavigationStatus("hall", "going", "started")
        val request = """{"type":"command","id":"speed1","command":"set_speed","navigation_session_id":"n","target_speed_mps":0.6,"control_reason":"crowd","expires_at_ms":110000}"""
        assertTrue(f.bridge.onSocketMessage(request))
        assertTrue(f.ack("speed1"))
        assertTrue(f.calls.contains("speed:0.6"))
        assertEquals("complete", f.out.last { it["type"].asString == "event" && it["id"].asString == "speed1" }["status"].asString)
        val stale = request.replace("speed1", "speed2").replace("""navigation_session_id":"n""", """navigation_session_id":"old""")
        assertTrue(f.bridge.onSocketMessage(stale))
        assertFalse(f.ack("speed2"))
    }

    @Test fun speedManagerValidatesSoftwareRangeAndPreservesSdkReturnCode() {
        var applied = 0f
        val manager = TemiSpeedManager { speed -> applied = speed; 0 }
        assertEquals(0, manager.setCurrentNavigationSpeed(0.3f))
        assertEquals(0.3f, applied, 0f)
        assertThrows(IllegalArgumentException::class.java) { manager.setCurrentNavigationSpeed(0.0f) }
        assertThrows(IllegalArgumentException::class.java) { manager.setCurrentNavigationSpeed(0.9f) }
    }

    @Test fun handshakeReportsUnknownDataAndLaterReady() {
        val f = Fixture()
        f.handshake(false)
        assertEquals(listOf("hello", "state"), f.out.map { it["type"].asString })
        assertEquals(1, f.out.first()["protocol_version"].asInt)
        assertFalse(f.state()["connected"].asBoolean)
        assertEquals(-1, f.state()["battery_percentage"].asInt)
        assertEquals("", f.state()["frame_id"].asString)
        f.bridge.onRobotReady(true)
        assertTrue(f.state()["connected"].asBoolean)
        f.bridge.onBattery(85)
        f.bridge.onRobotPosition(2.0, 3.0, 0.2, true)
        f.bridge.tick()
        assertEquals(85, f.state()["battery_percentage"].asInt)
        assertEquals("temi_sdk_unverified", f.state()["frame_id"].asString)
        assertEquals(2.0, f.state()["x"].asDouble, 0.0)
        f.bridge.onRobotPosition(Double.NaN, 3.0, 0.2, true)
        f.bridge.tick()
        assertEquals("", f.state()["frame_id"].asString)
    }

    @Test fun rejectsInvalidExpiredUnreadyUnknownAndDuplicateCommandsWithoutInvokingSdk() {
        val f = Fixture()
        f.handshake(false)
        assertTrue(f.nav("unready"))
        assertFalse(f.ack("unready"))
        f.bridge.onRobotReady(true)
        assertTrue(f.nav("unready"))
        assertFalse(f.ack("unready"))
        assertTrue(f.nav("expired", f.time))
        assertFalse(f.ack("expired"))
        assertTrue(f.command("unknown", "navigate", "location", "not_saved"))
        assertFalse(f.ack("unknown"))
        assertTrue(f.calls.none { it.startsWith("go:") })
        assertTrue(f.nav())
        assertTrue(f.ack("n"))
        assertTrue(f.calls.indexOf("send:ack:n") < f.calls.indexOf("go:hall"))
        assertTrue(f.nav())
        assertFalse(f.ack("n"))
        assertEquals(1, f.calls.count { it == "go:hall" })
    }

    @Test fun malformedProtocolIsRejectedWithoutDispatch() {
        val f = Fixture()
        f.handshake()
        val invalid = listOf(
            """{"type":"command","id":"x","command":"navigate","location":"hall","expires_at_ms":"800000"}""",
            """{"type":"command","id":"x","command":"navigate","location":"hall","expires_at_ms":NaN}""",
            """{"type":"command","id":"x","command":"navigate","location":"hall","expires_at_ms":800000.0}""",
            """{"type":"command","id":"x","command":"navigate","location":"hall","expires_at_ms":800000,"id":"y"}""",
            """{"type":"state_request"} {}""",
            """{"type":"state_request","x":"${"汉".repeat(22_000)}"}""",
            """{"type":"command","id":"${"x".repeat(129)}","command":"navigate","location":"hall","expires_at_ms":800000}"""
        )
        invalid.forEach { assertFalse(it.take(100), f.bridge.onSocketMessage(it)) }
        assertTrue(f.calls.none { it.startsWith("go:") })
    }

    @Test fun navigationOnlyAcceptsMatchingTargetAfterProgress() {
        val f = Fixture()
        f.handshake()
        f.nav()
        f.bridge.onNavigationStatus("hall", "complete", "stale")
        f.bridge.onNavigationStatus("door", "start", "other")
        f.bridge.onNavigationStatus("door", "complete", "other")
        assertTrue(f.statuses("n").isEmpty())
        f.bridge.onNavigationStatus("hall", "start", "")
        f.bridge.onNavigationStatus("hall", "going", "")
        f.bridge.onNavigationStatus("hall", "complete", "arrived")
        assertEquals(listOf("start", "going", "complete"), f.statuses("n"))
        f.bridge.onNavigationStatus("hall", "complete", "duplicate")
        f.bridge.tick()
        assertEquals("hall", f.state()["current_location"].asString)
        assertEquals(listOf("start", "going", "complete"), f.statuses("n"))
    }

    @Test fun stopRequiresPostCommandZeroVelocityAndMatchingTerminal() {
        val f = Fixture()
        f.handshake()
        f.nav()
        f.bridge.onNavigationStatus("hall", "going", "")
        f.bridge.onVelocity(0.0) // old zero does not count
        f.command("wrong", "stop", "target_id", "old")
        assertFalse(f.ack("wrong"))
        assertFalse(f.calls.contains("stop"))
        f.command("s", "stop", "target_id", "n")
        assertTrue(f.ack("s"))
        assertTrue(f.calls.contains("stop"))
        f.bridge.onNavigationStatus("door", "abort", "")
        f.bridge.onVelocity(0.0)
        assertTrue(f.statuses("s").isEmpty())
        f.bridge.onNavigationStatus("hall", "complete", "racing with stop")
        assertEquals(listOf("complete"), f.statuses("s"))
        assertFalse(f.statuses("n").contains("complete"))
        assertTrue(f.statuses("n").contains("stopped"))
    }

    @Test fun timedOutStopDoesNotReleaseNavigationUntilBothEvidenceArrive() {
        val f = Fixture()
        f.handshake()
        f.nav()
        f.bridge.onNavigationStatus("hall", "start", "")
        f.command("s", "stop", "target_id", "n", f.time + 100)
        f.bridge.onNavigationStatus("hall", "abort", "")
        f.time += 101
        f.bridge.tick()
        assertEquals(listOf("error"), f.statuses("s"))
        f.nav("blocked")
        assertFalse(f.ack("blocked"))
        f.bridge.onVelocity(0.0)
        f.nav("new")
        assertTrue(f.ack("new"))
        assertEquals(listOf("error"), f.statuses("s"))
    }

    @Test fun speechAndCancelCorrelateByExactSdkUuidAndIgnoreLateResults() {
        val f = Fixture()
        f.handshake()
        f.command("t", "speak", "text", "Hello")
        val uuid = f.sdkId()
        f.bridge.onTtsStatus("other", "COMPLETED")
        assertTrue(f.statuses("t").isEmpty())
        f.bridge.onTtsStatus(uuid, "STARTED")
        assertEquals(listOf("started"), f.statuses("t"))
        f.command("wrong", "cancel_speech", "target_id", "old")
        assertFalse(f.ack("wrong"))
        f.command("c", "cancel_speech", "target_id", "t")
        assertTrue(f.ack("c"))
        assertTrue(f.calls.contains("cancel"))
        f.bridge.onTtsStatus("other", "CANCELED")
        assertTrue(f.statuses("c").isEmpty())
        f.bridge.onTtsStatus(uuid, "CANCELED")
        assertEquals(listOf("complete"), f.statuses("c"))
        assertEquals(listOf("started", "canceled"), f.statuses("t"))
        f.command("new", "speak", "text", "Bye")
        f.bridge.onTtsStatus(uuid, "COMPLETED")
        assertTrue(f.statuses("new").isEmpty())
        f.bridge.onTtsStatus(f.sdkId(), "COMPLETED")
        assertEquals(listOf("complete"), f.statuses("new"))
    }

    @Test fun expiryAndDisconnectStopRemoteOperationsWithoutReplay() {
        val f = Fixture()
        f.handshake()
        f.nav("n", f.time + 100)
        f.bridge.onNavigationStatus("hall", "going", "")
        f.command("t", "speak", "text", "Hello")
        val uuid = f.sdkId()
        f.time += 101
        f.bridge.tick()
        assertEquals(listOf("going", "timeout"), f.statuses("n"))
        assertTrue(f.calls.contains("stop"))
        f.bridge.onSocketClosed()
        val closeCount = f.calls.count { it == "stop" }
        assertTrue(f.calls.contains("cancel"))
        f.bridge.onSocketClosed()
        assertEquals(closeCount, f.calls.count { it == "stop" })
        f.handshake()
        f.nav("blocked")
        assertFalse(f.ack("blocked"))
        f.bridge.onNavigationStatus("hall", "abort", "")
        f.bridge.onVelocity(0.0)
        f.bridge.onTtsStatus(uuid, "CANCELED")
        f.nav("n")
        assertFalse(f.ack("n"))
        f.nav("new")
        assertTrue(f.ack("new"))
        assertEquals(listOf("going", "timeout"), f.statuses("n"))
        assertTrue(f.statuses("t").isEmpty())
    }

    @Test fun failedAckDoesNotDispatchNavigation() {
        val f = Fixture()
        f.handshake()
        f.failSend = true
        assertFalse(f.nav())
        assertTrue(f.calls.none { it.startsWith("go:") })
    }

    @Test fun lateStopAndSpeechTerminalCannotClaimSuccessBeforeNextTick() {
        val f = Fixture()
        f.handshake()
        f.nav()
        f.bridge.onNavigationStatus("hall", "going", "")
        f.command("s", "stop", "target_id", "n", f.time + 100)
        f.bridge.onNavigationStatus("hall", "abort", "")
        f.time += 101
        f.bridge.onVelocity(0.0)
        assertEquals(listOf("error"), f.statuses("s"))
        f.command("t", "speak", "text", "Hello", f.time + 100)
        val uuid = f.sdkId()
        f.time += 101
        f.bridge.onTtsStatus(uuid, "COMPLETED")
        assertEquals(listOf("error"), f.statuses("t"))
    }

    @Test fun reconnectAllowsNewStopWhileRetainingOldMotionQuarantine() {
        val f = Fixture()
        f.handshake()
        f.nav()
        f.bridge.onNavigationStatus("hall", "going", "")
        f.command("old-stop", "stop", "target_id", "n")
        f.bridge.onSocketClosed()
        f.handshake()
        f.nav("blocked")
        assertFalse(f.ack("blocked"))
        f.command("new-stop", "stop", "target_id", "n")
        assertTrue(f.ack("new-stop"))
        f.bridge.onNavigationStatus("hall", "abort", "")
        f.bridge.onVelocity(0.0)
        assertEquals(listOf("complete"), f.statuses("new-stop"))
        assertTrue(f.statuses("old-stop").isEmpty())
    }

    @Test fun sdkReadinessLossRetriesSafetyCallsWhenServiceReturns() {
        val f = Fixture()
        f.handshake()
        f.nav()
        f.command("t", "speak", "text", "Hello")
        f.bridge.onRobotReady(false)
        val stops = f.calls.count { it == "stop" }
        val cancels = f.calls.count { it == "cancel" }
        f.bridge.onRobotReady(true)
        assertTrue(f.calls.count { it == "stop" } > stops)
        assertTrue(f.calls.count { it == "cancel" } > cancels)
        f.nav("blocked")
        assertFalse(f.ack("blocked"))
    }
}

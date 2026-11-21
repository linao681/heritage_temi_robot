package com.heritage.temibridge

import com.google.gson.Gson
import com.google.gson.stream.JsonReader
import com.google.gson.stream.JsonToken
import java.io.StringReader

/** v1 协议仅接受扁平 JSON 对象，严格检查字段、类型和重复键。 */
internal object BridgeProtocol {
    const val MAX_BYTES = 65_536
    private val gson = Gson()

    data class Command(val id: String, val kind: String, val argument: String, val expires: Long,
                       val navigationSessionId: String = "", val targetSpeedMps: Float = Float.NaN,
                       val controlReason: String = "")
    data class Message(val type: String, val command: Command? = null)
    private data class Field(val kind: JsonToken, val value: String)

    fun encode(vararg fields: Pair<String, Any>): String = gson.toJson(linkedMapOf(*fields))

    fun parse(text: String): Message? {
        if (text.toByteArray(Charsets.UTF_8).size > MAX_BYTES) return null
        return try {
            val reader = JsonReader(StringReader(text))
            reader.isLenient = false
            val fields = linkedMapOf<String, Field>()
            reader.beginObject()
            while (reader.hasNext()) {
                val name = reader.nextName()
                if (fields.containsKey(name)) return null
                val kind = reader.peek()
                val value = when (kind) {
                    JsonToken.STRING, JsonToken.NUMBER -> reader.nextString()
                    JsonToken.BOOLEAN -> reader.nextBoolean().toString()
                    else -> return null
                }
                fields[name] = Field(kind, value)
            }
            reader.endObject()
            if (reader.peek() != JsonToken.END_DOCUMENT) return null
            fun string(name: String) = fields[name]?.takeIf { it.kind == JsonToken.STRING }?.value
            fun integer(name: String) = fields[name]?.takeIf {
                it.kind == JsonToken.NUMBER && it.value.matches(Regex("[0-9]+"))
            }?.value?.toLongOrNull()
            when (val type = string("type")) {
                "hello_ack" -> if (fields.keys == setOf("type", "protocol_version") && integer("protocol_version") == 1L) Message(type) else null
                "state_request" -> if (fields.keys == setOf("type")) Message(type) else null
                "command" -> {
                    val id = string("id") ?: return null
                    if (id.isBlank() || id.length > 128) return null
                    val kind = string("command") ?: return null
                    val argumentName = when (kind) {
                        "navigate" -> "location"
                        "speak" -> "text"
                        "stop", "cancel_speech" -> "target_id"
                        "set_speed" -> "navigation_session_id"
                        else -> return null
                    }
                    val required = if (kind == "set_speed") setOf("type", "id", "command", "navigation_session_id", "target_speed_mps", "control_reason", "expires_at_ms")
                        else setOf("type", "id", "command", argumentName, "expires_at_ms")
                    if (fields.keys != required) return null
                    val argument = string(argumentName) ?: return null
                    val targetSpeed = fields["target_speed_mps"]?.takeIf { it.kind == JsonToken.NUMBER }?.value?.toFloatOrNull() ?: Float.NaN
                    val reason = string("control_reason") ?: ""
                    if (kind == "set_speed" && (!targetSpeed.isFinite() || targetSpeed !in 0.3f..0.8f || reason.isBlank())) return null
                    if (kind != "stop" && argument.isBlank()) return null
                    if (argumentName == "target_id" && argument.length > 128) return null
                    val expires = integer("expires_at_ms")?.takeIf { it > 0 } ?: return null
                    Message(type, Command(id, kind, argument, expires,
                        if (kind == "set_speed") argument else "", targetSpeed, reason))
                }
                else -> null
            }
        } catch (_: Exception) { null }
    }
}

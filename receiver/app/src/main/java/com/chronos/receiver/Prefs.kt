package com.chronos.receiver

import android.content.Context

class Prefs(context: Context) {
    private val prefs = context.getSharedPreferences("chronos_receiver", Context.MODE_PRIVATE)

    var botToken: String
        get() = prefs.getString(KEY_TOKEN, "") ?: ""
        set(value) = prefs.edit().putString(KEY_TOKEN, value.trim()).apply()

    var channelId: String
        get() = prefs.getString(KEY_CHANNEL, "") ?: ""
        set(value) = prefs.edit().putString(KEY_CHANNEL, value.trim()).apply()

    var backendChannelId: String
        get() = prefs.getString(KEY_BACKEND, "") ?: ""
        set(value) = prefs.edit().putString(KEY_BACKEND, value.trim()).apply()

    var laptopIp: String
        get() = prefs.getString(KEY_LAPTOP_IP, "") ?: ""
        set(value) = prefs.edit().putString(KEY_LAPTOP_IP, value.trim()).apply()

    var timeoutSec: Int
        get() = prefs.getInt(KEY_TIMEOUT, 30)
        set(value) = prefs.edit().putInt(KEY_TIMEOUT, value.coerceIn(5, 120)).apply()

    /** Must match discord.command_prefix on the host (default "!"). */
    var commandPrefix: String
        get() {
            val raw = prefs.getString(KEY_PREFIX, "!") ?: "!"
            return raw.ifBlank { "!" }
        }
        set(value) {
            val p = value.trim().ifBlank { "!" }
            prefs.edit().putString(KEY_PREFIX, p).apply()
        }

    fun isConfigured(): Boolean =
        botToken.isNotBlank() && channelId.isNotBlank() && laptopIp.isNotBlank()

    fun channelFor(command: String): String {
        val c = command.trim().lowercase()
        val p = commandPrefix.lowercase()
        val backend = backendChannelId
        if (backend.isNotBlank() && (
                c.startsWith("${p}lock") ||
                c.startsWith("?status") ||
                c.startsWith("?ping")
            )
        ) {
            return backend
        }
        return channelId
    }

    companion object {
        private const val KEY_TOKEN = "bot_token"
        private const val KEY_CHANNEL = "channel_id"
        private const val KEY_BACKEND = "backend_channel_id"
        private const val KEY_LAPTOP_IP = "laptop_ip"
        private const val KEY_TIMEOUT = "timeout_sec"
        private const val KEY_PREFIX = "command_prefix"
    }
}

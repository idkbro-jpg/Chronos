package com.chronos.remote

import android.content.Context

class Prefs(context: Context) {
    private val prefs = context.getSharedPreferences("chronos_remote", Context.MODE_PRIVATE)

    var botToken: String
        get() = prefs.getString(KEY_TOKEN, "") ?: ""
        set(value) = prefs.edit().putString(KEY_TOKEN, value.trim()).apply()

    var channelId: String
        get() = prefs.getString(KEY_CHANNEL, "") ?: ""
        set(value) = prefs.edit().putString(KEY_CHANNEL, value.trim()).apply()

    /** Optional: kritische Commands (!lock, ?status, ?ping) */
    var backendChannelId: String
        get() = prefs.getString(KEY_BACKEND, "") ?: ""
        set(value) = prefs.edit().putString(KEY_BACKEND, value.trim()).apply()

    fun isConfigured(): Boolean =
        botToken.isNotBlank() && channelId.isNotBlank()

    fun channelFor(command: String): String {
        val c = command.trim().lowercase()
        val backend = backendChannelId
        if (backend.isNotBlank() && (c.startsWith("!lock") || c.startsWith("?status") || c.startsWith("?ping") || c == "!lock" || c == "?status" || c == "?ping")) {
            return backend
        }
        return channelId
    }

    companion object {
        private const val KEY_TOKEN = "bot_token"
        private const val KEY_CHANNEL = "channel_id"
        private const val KEY_BACKEND = "backend_channel_id"
    }
}

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

    fun isConfigured(): Boolean =
        botToken.isNotBlank() && channelId.isNotBlank()

    companion object {
        private const val KEY_TOKEN = "bot_token"
        private const val KEY_CHANNEL = "channel_id"
    }
}

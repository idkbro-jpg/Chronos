package com.chronos.remote

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class DiscordClient(
    private val botToken: String,
    private val channelId: String
) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    fun sendCommand(content: String): Result<Unit> {
        if (botToken.isBlank() || channelId.isBlank()) {
            return Result.failure(IllegalStateException("Token or Channel-ID missing"))
        }

        val bodyJson = JSONObject().put("content", content).toString()

        val request = Request.Builder()
            .url("https://discord.com/api/v10/channels/$channelId/messages")
            .addHeader("Authorization", "Bot $botToken")
            .addHeader("User-Agent", "ChronosRemote/0.1.0-beta")
            .post(bodyJson.toRequestBody(jsonMedia))
            .build()

        return try {
            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) Result.success(Unit)
                else Result.failure(Exception("Discord ${response.code}: ${response.body?.string()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

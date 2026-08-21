package com.chronos.receiver

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class DiscordClient(private val botToken: String) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    fun sendMessage(channelId: String, content: String): Result<Unit> {
        if (botToken.isBlank() || channelId.isBlank()) {
            return Result.failure(IllegalStateException("Token or Channel missing"))
        }
        val body = JSONObject().put("content", content).toString()
        val request = Request.Builder()
            .url("https://discord.com/api/v10/channels/$channelId/messages")
            .addHeader("Authorization", "Bot $botToken")
            .addHeader("User-Agent", "ChronosReceiver/0.2.0-beta")
            .post(body.toRequestBody(jsonMedia))
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

    fun fetchRecent(channelId: String, limit: Int = 15): Result<List<DiscordMessage>> {
        if (botToken.isBlank() || channelId.isBlank()) {
            return Result.failure(IllegalStateException("Token or Channel missing"))
        }
        val request = Request.Builder()
            .url("https://discord.com/api/v10/channels/$channelId/messages?limit=$limit")
            .addHeader("Authorization", "Bot $botToken")
            .addHeader("User-Agent", "ChronosReceiver/0.2.0-beta")
            .get()
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    return Result.failure(Exception("Discord ${response.code}"))
                }
                val arr = JSONArray(response.body?.string() ?: "[]")
                val list = mutableListOf<DiscordMessage>()
                for (i in 0 until arr.length()) {
                    val o = arr.getJSONObject(i)
                    val author = o.optJSONObject("author")
                    list.add(
                        DiscordMessage(
                            id = o.getString("id"),
                            content = o.optString("content", ""),
                            authorId = author?.optString("id") ?: "",
                            authorBot = author?.optBoolean("bot") == true
                        )
                    )
                }
                Result.success(list)
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

data class DiscordMessage(
    val id: String,
    val content: String,
    val authorId: String,
    val authorBot: Boolean
)

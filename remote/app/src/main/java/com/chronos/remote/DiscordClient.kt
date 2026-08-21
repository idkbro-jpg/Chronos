package com.chronos.remote

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class DiscordClient(
    private val botToken: String
) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    fun sendCommand(channelId: String, content: String): Result<String> {
        if (botToken.isBlank() || channelId.isBlank()) {
            return Result.failure(IllegalStateException("Token or Channel-ID missing"))
        }
        val bodyJson = JSONObject().put("content", content).toString()
        val request = Request.Builder()
            .url("https://discord.com/api/v10/channels/$channelId/messages")
            .addHeader("Authorization", "Bot $botToken")
            .addHeader("User-Agent", "ChronosRemote/0.2.0-beta")
            .post(bodyJson.toRequestBody(jsonMedia))
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                val body = response.body?.string() ?: ""
                if (response.isSuccessful) {
                    val id = JSONObject(body).optString("id", "")
                    Result.success(id)
                } else {
                    Result.failure(Exception("Discord ${response.code}: $body"))
                }
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    fun fetchRecent(channelId: String, limit: Int = 15): Result<List<Pair<String, String>>> {
        if (botToken.isBlank() || channelId.isBlank()) {
            return Result.failure(IllegalStateException("Token or Channel missing"))
        }
        val request = Request.Builder()
            .url("https://discord.com/api/v10/channels/$channelId/messages?limit=$limit")
            .addHeader("Authorization", "Bot $botToken")
            .addHeader("User-Agent", "ChronosRemote/0.2.0-beta")
            .get()
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    return Result.failure(Exception("Discord ${response.code}"))
                }
                val arr = JSONArray(response.body?.string() ?: "[]")
                val list = mutableListOf<Pair<String, String>>()
                for (i in 0 until arr.length()) {
                    val o = arr.getJSONObject(i)
                    list.add(o.getString("id") to o.optString("content", ""))
                }
                Result.success(list)
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

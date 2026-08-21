package com.chronos.receiver

import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.InetSocketAddress
import java.net.Socket
import kotlin.system.measureTimeMillis

data class ReachResult(
    val online: Boolean,
    val latencyMs: Long? = null,
    val detail: String = ""
)

/**
 * Checks whether [host] answers within [timeoutSec] seconds.
 * Tries TCP connect (port 22, then 80) and falls back to system ping.
 */
fun checkHost(host: String, timeoutSec: Int): ReachResult {
    if (host.isBlank()) {
        return ReachResult(false, detail = "keine Laptop-IP konfiguriert")
    }

    val timeoutMs = (timeoutSec * 1000).coerceIn(3000, 120_000)

    // 1) TCP to common ports
    for (port in listOf(22, 80, 443, 445)) {
        try {
            val ms = measureTimeMillis {
                Socket().use { socket ->
                    socket.connect(InetSocketAddress(host, port), timeoutMs.coerceAtMost(5000))
                }
            }
            return ReachResult(true, ms, "TCP :$port")
        } catch (_: Exception) {
            // try next
        }
    }

    // 2) system ping (works on many Android builds without root)
    return try {
        val pb = ProcessBuilder("ping", "-c", "1", "-W", timeoutSec.toString(), host)
        pb.redirectErrorStream(true)
        val proc = pb.start()
        val output = BufferedReader(InputStreamReader(proc.inputStream)).readText()
        val ok = proc.waitFor() == 0
        val timeMatch = Regex("""time[=<]([0-9.]+)\s*ms""").find(output)
        val ms = timeMatch?.groupValues?.get(1)?.toDoubleOrNull()?.toLong()
        if (ok) {
            ReachResult(true, ms, "ping")
        } else {
            ReachResult(false, detail = "keine Antwort innerhalb von ${timeoutSec}s")
        }
    } catch (e: Exception) {
        ReachResult(false, detail = e.message ?: "ping fehlgeschlagen")
    }
}

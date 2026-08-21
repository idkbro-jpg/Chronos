package com.chronos.receiver

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.NetworkCheck
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                ReceiverApp()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReceiverApp() {
    val context = LocalContext.current
    val prefs = remember { Prefs(context) }
    var showSettings by remember { mutableStateOf(!prefs.isConfigured()) }
    val scope = rememberCoroutineScope()

    var listening by remember { mutableStateOf(false) }
    var lastLog by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }

    // Poll Discord for ?status / ?ping while listening
    LaunchedEffect(listening, prefs.botToken, prefs.channelId) {
        if (!listening || !prefs.isConfigured()) return@LaunchedEffect
        val seen = mutableSetOf<String>()
        val discord = DiscordClient(prefs.botToken, prefs.channelId)
        while (isActive && listening) {
            val result = withContext(Dispatchers.IO) { discord.fetchRecentMessages(15) }
            result.onSuccess { messages ->
                for (msg in messages.reversed()) {
                    if (msg.id in seen) continue
                    seen.add(msg.id)
                    val body = msg.content.trim()
                    if (!body.startsWith("?")) continue
                    // ignore pure bot noise later if needed
                    val cmd = body.lowercase().substringBefore(" ").trim()
                    when (cmd) {
                        "?status", "?ping" -> {
                            lastLog = "Empfangen: $body"
                            val reply = withContext(Dispatchers.IO) {
                                handleQuery(cmd, prefs)
                            }
                            withContext(Dispatchers.IO) { discord.sendMessage(reply) }
                            lastLog = reply
                        }
                    }
                }
                if (seen.size > 200) {
                    val keep = seen.toList().takeLast(100)
                    seen.clear()
                    seen.addAll(keep)
                }
            }.onFailure {
                lastLog = "Poll-Fehler: ${it.message}"
            }
            delay(4000)
        }
    }

    if (showSettings) {
        SettingsScreen(prefs) { showSettings = false }
    } else {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("Chronos Receiver", fontWeight = FontWeight.Bold) },
                    actions = {
                        IconButton(onClick = { showSettings = true }) {
                            Icon(Icons.Default.Settings, contentDescription = "Settings")
                        }
                    }
                )
            }
        ) { padding ->
            Column(
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(24.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    "Prefix ?  \u00b7  status / ping",
                    style = MaterialTheme.typography.titleMedium
                )

                Text(
                    "Laptop: ${prefs.laptopIp.ifBlank { "(nicht gesetzt)" }}",
                    style = MaterialTheme.typography.bodyMedium
                )

                Row(
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    FilterChip(
                        selected = listening,
                        onClick = { listening = !listening },
                        label = { Text(if (listening) "Listening AN" else "Listening AUS") }
                    )
                }

                Button(
                    onClick = {
                        scope.launch {
                            busy = true
                            lastLog = withContext(Dispatchers.IO) { handleQuery("?status", prefs) }
                            busy = false
                        }
                    },
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth().height(72.dp)
                ) {
                    Icon(Icons.Default.Info, null)
                    Spacer(Modifier.width(12.dp))
                    Text("?status", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                }

                Button(
                    onClick = {
                        scope.launch {
                            busy = true
                            lastLog = withContext(Dispatchers.IO) { handleQuery("?ping", prefs) }
                            busy = false
                        }
                    },
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth().height(72.dp)
                ) {
                    Icon(Icons.Default.NetworkCheck, null)
                    Spacer(Modifier.width(12.dp))
                    Text("?ping", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                }

                if (busy) {
                    CircularProgressIndicator()
                }

                if (lastLog.isNotBlank()) {
                    Card(Modifier.fillMaxWidth()) {
                        Text(lastLog, Modifier.padding(16.dp))
                    }
                }

                Text(
                    "Beta \u2013 nur status/ping. WoL kommt sp\u00e4ter.",
                    style = MaterialTheme.typography.labelSmall
                )
            }
        }
    }
}

private fun handleQuery(cmd: String, prefs: Prefs): String {
    val host = prefs.laptopIp
    val timeout = prefs.timeoutSec
    val result = checkHost(host, timeout)

    return when {
        cmd == "?status" && result.online -> {
            val ms = result.latencyMs?.let { "${it}ms" } ?: "ein paar ms"
            "**Receiver online** \u00b7 PC **erreichbar** ($ms, ${result.detail})"
        }
        cmd == "?status" && !result.online -> {
            "**Receiver online** \u00b7 PC **nicht erreichbar** " +
                "(Timeout ${timeout}s). ${result.detail}. " +
                "Stelle sicher, dass dein Ger\u00e4t am Internet/Netz h\u00e4ngt und die IP stimmt."
        }
        cmd == "?ping" && result.online -> {
            val ms = result.latencyMs?.let { "${it}ms" } ?: "?ms"
            "PC ist **online**, erreicht in **$ms** (${result.detail})"
        }
        else -> {
            "PC hat nach **${timeout}s** nicht geantwortet (Timeout). " +
                "Stelle sicher, dass dein Ger\u00e4t an das Internet verbunden ist. " +
                "Detail: ${result.detail}"
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(prefs: Prefs, onSave: () -> Unit) {
    var token by remember { mutableStateOf(prefs.botToken) }
    var channel by remember { mutableStateOf(prefs.channelId) }
    var ip by remember { mutableStateOf(prefs.laptopIp) }
    var timeout by remember { mutableStateOf(prefs.timeoutSec.toString()) }
    val context = LocalContext.current

    Scaffold(topBar = { TopAppBar(title = { Text("Settings") }) }) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            OutlinedTextField(token, { token = it }, label = { Text("Bot Token") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(channel, { channel = it }, label = { Text("Channel ID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(ip, { ip = it }, label = { Text("Laptop IP (LAN oder Tailscale)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(timeout, { timeout = it }, label = { Text("Timeout Sekunden") }, modifier = Modifier.fillMaxWidth(), singleLine = true)

            Button(
                onClick = {
                    if (token.isBlank() || channel.isBlank() || ip.isBlank()) {
                        Toast.makeText(context, "Token, Channel, IP ausf\u00fcllen", Toast.LENGTH_SHORT).show()
                        return@Button
                    }
                    prefs.botToken = token
                    prefs.channelId = channel
                    prefs.laptopIp = ip
                    prefs.timeoutSec = timeout.toIntOrNull() ?: 30
                    Toast.makeText(context, "Gespeichert", Toast.LENGTH_SHORT).show()
                    onSave()
                },
                modifier = Modifier.fillMaxWidth().height(56.dp)
            ) { Text("Speichern") }
        }
    }
}

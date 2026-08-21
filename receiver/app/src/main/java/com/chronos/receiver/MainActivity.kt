package com.chronos.receiver

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.NetworkCheck
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
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
    var busy by remember { mutableStateOf(false) }
    val log = remember { mutableStateListOf<String>() }
    var cmdInput by remember { mutableStateOf("") }
    val listState = rememberLazyListState()

    fun append(msg: String) {
        log.add(msg)
        if (log.size > 200) log.removeAt(0)
    }

    // Poll both channels for ?status / ?ping
    LaunchedEffect(listening) {
        if (!listening || !prefs.isConfigured()) return@LaunchedEffect
        val seen = mutableSetOf<String>()
        val discord = DiscordClient(prefs.botToken)
        val channels = listOfNotNull(
            prefs.channelId.takeIf { it.isNotBlank() },
            prefs.backendChannelId.takeIf { it.isNotBlank() }
        ).distinct()

        while (isActive && listening) {
            for (ch in channels) {
                val result = withContext(Dispatchers.IO) { discord.fetchRecent(ch, 15) }
                result.onSuccess { messages ->
                    for (msg in messages.reversed()) {
                        if (msg.id in seen) continue
                        seen.add(msg.id)
                        val body = msg.content.trim()
                        if (!body.startsWith("?")) continue
                        val head = body.lowercase().substringBefore(" ").trim()
                        if (head == "?status" || head == "?ping") {
                            append("empangen: $body")
                            val reply = withContext(Dispatchers.IO) { handleLocal(head, prefs) }
                            append(reply)
                            withContext(Dispatchers.IO) {
                                discord.sendMessage(ch, reply)
                            }
                        }
                    }
                }.onFailure {
                    append("Poll-Fehler: ${it.message}")
                }
            }
            if (seen.size > 300) {
                val keep = seen.toList().takeLast(150)
                seen.clear()
                seen.addAll(keep)
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
                    .padding(16.dp)
            ) {
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    FilterChip(
                        selected = listening,
                        onClick = { listening = !listening },
                        label = { Text(if (listening) "Listening AN" else "Listening AUS") }
                    )
                    Text(
                        "PC: ${prefs.laptopIp.ifBlank { "?" }}",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.weight(1f)
                    )
                }

                Spacer(Modifier.height(8.dp))

                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = {
                            scope.launch {
                                busy = true
                                append(handleLocal("?status", prefs))
                                busy = false
                            }
                        },
                        enabled = !busy,
                        modifier = Modifier.weight(1f)
                    ) {
                        Icon(Icons.Default.Info, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("?status")
                    }
                    Button(
                        onClick = {
                            scope.launch {
                                busy = true
                                append(handleLocal("?ping", prefs))
                                busy = false
                            }
                        },
                        enabled = !busy,
                        modifier = Modifier.weight(1f)
                    ) {
                        Icon(Icons.Default.NetworkCheck, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("?ping")
                    }
                }

                Spacer(Modifier.height(8.dp))

                Text("Output", style = MaterialTheme.typography.labelMedium)
                Card(Modifier.fillMaxWidth().weight(1f)) {
                    LazyColumn(
                        state = listState,
                        modifier = Modifier.fillMaxSize().padding(8.dp)
                    ) {
                        items(log) { line ->
                            Text(
                                line,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 12.sp,
                                modifier = Modifier.padding(vertical = 2.dp)
                            )
                        }
                    }
                }

                LaunchedEffect(log.size) {
                    if (log.isNotEmpty()) listState.animateScrollToItem(log.lastIndex)
                }

                Spacer(Modifier.height(8.dp))

                Row(
                    Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedTextField(
                        value = cmdInput,
                        onValueChange = { cmdInput = it },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        placeholder = { Text("?ping  |  !lock  |  …") },
                        enabled = !busy
                    )
                    IconButton(
                        onClick = {
                            val t = cmdInput.trim()
                            if (t.isEmpty()) return@IconButton
                            scope.launch {
                                busy = true
                                processCmd(t, prefs, log)
                                cmdInput = ""
                                busy = false
                            }
                        },
                        enabled = !busy && cmdInput.isNotBlank()
                    ) {
                        Icon(Icons.Default.Send, contentDescription = "Senden")
                    }
                }

                if (busy) {
                    LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 4.dp))
                }
            }
        }
    }
}

private fun handleLocal(cmd: String, prefs: Prefs): String {
    val host = prefs.laptopIp
    val timeout = prefs.timeoutSec
    val result = checkHost(host, timeout)
    return when {
        cmd == "?status" && result.online -> {
            val ms = result.latencyMs?.let { "${it}ms" } ?: "ein paar ms"
            "Receiver online · PC erreichbar ($ms, ${result.detail})"
        }
        cmd == "?status" && !result.online -> {
            "Receiver online · PC nicht erreichbar (Timeout ${timeout}s). ${result.detail}. " +
                "Stelle sicher, dass dein Gerät am Netz hängt und die IP stimmt."
        }
        cmd == "?ping" && result.online -> {
            val ms = result.latencyMs?.let { "${it}ms" } ?: "?ms"
            "PC ist online, erreicht in $ms (${result.detail})"
        }
        else -> {
            "PC hat nach ${timeout}s nicht geantwortet (Timeout). " +
                "Stelle sicher, dass dein Gerät an das Internet verbunden ist. Detail: ${result.detail}"
        }
    }
}

private suspend fun processCmd(raw: String, prefs: Prefs, log: MutableList<String>) {
    val t = raw.trim()
    val head = t.lowercase().substringBefore(" ").trim()
    log.add("> $t")

    if (head == "?status" || head == "?ping") {
        log.add(handleLocal(head, prefs))
        return
    }

    // alles andere → Discord (Backend-Channel wenn passend)
    if (prefs.botToken.isBlank()) {
        log.add("Kein Token – kann nicht senden")
        return
    }
    val ch = prefs.channelFor(t)
    if (ch.isBlank()) {
        log.add("Keine Channel-ID")
        return
    }
    val discord = DiscordClient(prefs.botToken)
    val result = withContext(Dispatchers.IO) { discord.sendMessage(ch, t) }
    result.fold(
        onSuccess = { log.add("gesendet → ${if (ch == prefs.backendChannelId) "backend" else "main"}") },
        onFailure = { log.add("Fehler: ${it.message}") }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(prefs: Prefs, onSave: () -> Unit) {
    var token by remember { mutableStateOf(prefs.botToken) }
    var channel by remember { mutableStateOf(prefs.channelId) }
    var backend by remember { mutableStateOf(prefs.backendChannelId) }
    var ip by remember { mutableStateOf(prefs.laptopIp) }
    var timeout by remember { mutableStateOf(prefs.timeoutSec.toString()) }
    val context = LocalContext.current

    Scaffold(topBar = { TopAppBar(title = { Text("Settings") }) }) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            OutlinedTextField(token, { token = it }, label = { Text("Bot Token") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(channel, { channel = it }, label = { Text("Channel ID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(
                backend, { backend = it },
                label = { Text("Backend Channel ID (optional)") },
                supportingText = { Text("!lock, ?status, ?ping") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            OutlinedTextField(ip, { ip = it }, label = { Text("Laptop IP") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(timeout, { timeout = it }, label = { Text("Timeout Sekunden") }, modifier = Modifier.fillMaxWidth(), singleLine = true)

            Button(
                onClick = {
                    if (token.isBlank() || channel.isBlank() || ip.isBlank()) {
                        Toast.makeText(context, "Token, Channel, IP nötig", Toast.LENGTH_SHORT).show()
                        return@Button
                    }
                    prefs.botToken = token
                    prefs.channelId = channel
                    prefs.backendChannelId = backend
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

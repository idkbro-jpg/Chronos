package com.chronos.remote

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
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Screenshot
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                ChronosRemoteApp()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChronosRemoteApp() {
    val context = LocalContext.current
    val prefs = remember { Prefs(context) }
    var showSettings by remember { mutableStateOf(!prefs.isConfigured()) }
    val scope = rememberCoroutineScope()

    var isSending by remember { mutableStateOf(false) }
    val log = remember { mutableStateListOf<String>() }
    var cmdInput by remember { mutableStateOf("") }
    val listState = rememberLazyListState()

    fun append(msg: String) {
        log.add(msg)
        if (log.size > 200) log.removeAt(0)
    }

    if (showSettings) {
        SettingsScreen(prefs) { showSettings = false }
    } else {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("Chronos Remote", fontWeight = FontWeight.Bold) },
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
                // Buttons
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    SmallBtn("Status", Icons.Default.Info, !isSending, Modifier.weight(1f)) {
                        scope.launch { runCmd(prefs, "!status", log) { isSending = it } }
                    }
                    SmallBtn("Lock", Icons.Default.Lock, !isSending, Modifier.weight(1f)) {
                        scope.launch { runCmd(prefs, "!lock", log) { isSending = it } }
                    }
                    SmallBtn("SS", Icons.Default.Screenshot, !isSending, Modifier.weight(1f)) {
                        scope.launch { runCmd(prefs, "!screenshot", log) { isSending = it } }
                    }
                }

                Spacer(Modifier.height(12.dp))

                // Output log
                Text("Output", style = MaterialTheme.typography.labelMedium)
                Card(
                    Modifier
                        .fillMaxWidth()
                        .weight(1f)
                ) {
                    LazyColumn(
                        state = listState,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(8.dp)
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

                // CMD input
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
                        placeholder = { Text("!status / !lock / …") },
                        enabled = !isSending
                    )
                    IconButton(
                        onClick = {
                            val t = cmdInput.trim()
                            if (t.isEmpty()) return@IconButton
                            scope.launch {
                                runCmd(prefs, t, log) { isSending = it }
                                cmdInput = ""
                            }
                        },
                        enabled = !isSending && cmdInput.isNotBlank()
                    ) {
                        Icon(Icons.Default.Send, contentDescription = "Senden")
                    }
                }

                if (isSending) {
                    LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 4.dp))
                }
            }
        }
    }
}

@Composable
fun SmallBtn(
    title: String,
    icon: ImageVector,
    enabled: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Button(onClick = onClick, enabled = enabled, modifier = modifier.height(48.dp)) {
        Icon(icon, null, Modifier.size(18.dp))
        Spacer(Modifier.width(4.dp))
        Text(title, fontSize = 13.sp)
    }
}

private suspend fun runCmd(
    prefs: Prefs,
    command: String,
    log: MutableList<String>,
    setBusy: (Boolean) -> Unit
) {
    setBusy(true)
    val channel = prefs.channelFor(command)
    log.add("> $command  [${if (channel == prefs.backendChannelId) "backend" else "main"}]")

    val discord = DiscordClient(prefs.botToken)
    val sendResult = withContext(Dispatchers.IO) { discord.sendCommand(channel, command) }

    sendResult.fold(
        onSuccess = { msgId ->
            log.add("gesendet.")
            // kurze Zeit Antworten aus dem Channel nachladen
            delay(1500)
            val seen = mutableSetOf(msgId)
            repeat(4) {
                delay(2000)
                val replies = withContext(Dispatchers.IO) { discord.fetchRecent(channel, 10) }
                replies.onSuccess { list ->
                    for ((id, content) in list.reversed()) {
                        if (id in seen) continue
                        if (content.isBlank()) continue
                        seen.add(id)
                        val short = if (content.length > 300) content.take(297) + "…" else content
                        log.add("< $short")
                    }
                }
            }
        },
        onFailure = { log.add("Fehler: ${it.message}") }
    )
    setBusy(false)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(prefs: Prefs, onSave: () -> Unit) {
    var token by remember { mutableStateOf(prefs.botToken) }
    var channel by remember { mutableStateOf(prefs.channelId) }
    var backend by remember { mutableStateOf(prefs.backendChannelId) }
    val context = LocalContext.current

    Scaffold(topBar = { TopAppBar(title = { Text("Settings") }) }) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            OutlinedTextField(token, { token = it }, label = { Text("Bot Token") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(channel, { channel = it }, label = { Text("Command Channel ID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(
                backend,
                { backend = it },
                label = { Text("Backend Channel ID (optional)") },
                supportingText = { Text("!lock, ?status, ?ping landen hier") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            Button(
                onClick = {
                    if (token.isBlank() || channel.isBlank()) {
                        Toast.makeText(context, "Token + Channel nötig", Toast.LENGTH_SHORT).show()
                        return@Button
                    }
                    prefs.botToken = token
                    prefs.channelId = channel
                    prefs.backendChannelId = backend
                    Toast.makeText(context, "Gespeichert", Toast.LENGTH_SHORT).show()
                    onSave()
                },
                modifier = Modifier.fillMaxWidth().height(56.dp)
            ) { Text("Speichern") }
        }
    }
}

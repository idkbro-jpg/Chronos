package com.chronos.send

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Screenshot
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme()
            ) {
                ChronosSendApp()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChronosSendApp() {
    val context = LocalContext.current
    val prefs = remember { Prefs(context) }
    var showSettings by remember { mutableStateOf(!prefs.isConfigured()) }
    val scope = rememberCoroutineScope()

    var isSending by remember { mutableStateOf(false) }
    var lastResult by remember { mutableStateOf<String?>(null) }

    if (showSettings) {
        SettingsScreen(
            prefs = prefs,
            onSave = {
                showSettings = false
                lastResult = null
            }
        )
    } else {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("Chronos Send", fontWeight = FontWeight.Bold) },
                    actions = {
                        IconButton(onClick = { showSettings = true }) {
                            Icon(Icons.Default.Settings, contentDescription = "Settings")
                        }
                    }
                )
            }
        ) { padding ->
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(24.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "Notfall-Buttons",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                EmergencyButton(
                    title = "Status",
                    subtitle = "!status",
                    icon = Icons.Default.Info,
                    enabled = !isSending,
                    onClick = {
                        scope.launch {
                            sendCommand(prefs, "!status") { sending, result ->
                                isSending = sending
                                lastResult = result
                            }
                        }
                    }
                )

                EmergencyButton(
                    title = "Lock",
                    subtitle = "!lock  (braucht ✅)",
                    icon = Icons.Default.Lock,
                    enabled = !isSending,
                    containerColor = MaterialTheme.colorScheme.errorContainer,
                    contentColor = MaterialTheme.colorScheme.onErrorContainer,
                    onClick = {
                        scope.launch {
                            sendCommand(prefs, "!lock") { sending, result ->
                                isSending = sending
                                lastResult = result
                            }
                        }
                    }
                )

                EmergencyButton(
                    title = "Screenshot",
                    subtitle = "!screenshot  (braucht ✅)",
                    icon = Icons.Default.Screenshot,
                    enabled = !isSending,
                    onClick = {
                        scope.launch {
                            sendCommand(prefs, "!screenshot") { sending, result ->
                                isSending = sending
                                lastResult = result
                            }
                        }
                    }
                )

                if (isSending) {
                    CircularProgressIndicator(modifier = Modifier.padding(top = 16.dp))
                    Text("Sende Command…")
                }

                lastResult?.let { msg ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 12.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = if (msg.startsWith("OK"))
                                MaterialTheme.colorScheme.primaryContainer
                            else
                                MaterialTheme.colorScheme.errorContainer
                        )
                    ) {
                        Text(
                            text = msg,
                            modifier = Modifier.padding(16.dp),
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }

                Spacer(modifier = Modifier.height(24.dp))

                Text(
                    text = "Beta 0.1.0 – Send Mode only",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline
                )
            }
        }
    }
}

@Composable
fun EmergencyButton(
    title: String,
    subtitle: String,
    icon: ImageVector,
    enabled: Boolean,
    onClick: () -> Unit,
    containerColor: androidx.compose.ui.graphics.Color = MaterialTheme.colorScheme.primaryContainer,
    contentColor: androidx.compose.ui.graphics.Color = MaterialTheme.colorScheme.onPrimaryContainer
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier
            .fillMaxWidth()
            .height(88.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = containerColor,
            contentColor = contentColor
        ),
        shape = MaterialTheme.shapes.large
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(32.dp))
            Column {
                Text(title, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                Text(subtitle, fontSize = 13.sp)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    prefs: Prefs,
    onSave: () -> Unit
) {
    var token by remember { mutableStateOf(prefs.botToken) }
    var channel by remember { mutableStateOf(prefs.channelId) }
    val context = LocalContext.current

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Settings") })
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp)
        ) {
            Text(
                "Discord Bot Token + Channel-ID eintragen.\n" +
                        "Das ist derselbe Token, den der Daemon auch benutzt (oder ein separater Bot).",
                style = MaterialTheme.typography.bodyMedium
            )

            OutlinedTextField(
                value = token,
                onValueChange = { token = it },
                label = { Text("Bot Token") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            OutlinedTextField(
                value = channel,
                onValueChange = { channel = it },
                label = { Text("Command Channel ID") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            Button(
                onClick = {
                    if (token.isBlank() || channel.isBlank()) {
                        Toast.makeText(context, "Beide Felder ausfüllen", Toast.LENGTH_SHORT).show()
                        return@Button
                    }
                    prefs.botToken = token
                    prefs.channelId = channel
                    Toast.makeText(context, "Gespeichert", Toast.LENGTH_SHORT).show()
                    onSave()
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
            ) {
                Text("Speichern")
            }
        }
    }
}

private suspend fun sendCommand(
    prefs: Prefs,
    command: String,
    onUpdate: (sending: Boolean, result: String?) -> Unit
) {
    onUpdate(true, null)
    val result = withContext(Dispatchers.IO) {
        DiscordClient(prefs.botToken, prefs.channelId).sendCommand(command)
    }
    onUpdate(
        false,
        result.fold(
            onSuccess = { "OK – `$command` gesendet" },
            onFailure = { "Fehler: ${it.message}" }
        )
    )
}

package com.chronos.remote

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Screenshot
import androidx.compose.material.icons.filled.Settings
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
    var lastResult by remember { mutableStateOf<String?>(null) }

    if (showSettings) {
        SettingsScreen(prefs = prefs, onSave = { showSettings = false; lastResult = null })
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
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(24.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text("Notfall-Buttons (Send)", style = MaterialTheme.typography.titleMedium)

                EmergencyButton("Status", "!status", Icons.Default.Info, !isSending) {
                    scope.launch { send(prefs, "!status") { s, r -> isSending = s; lastResult = r } }
                }
                EmergencyButton(
                    "Lock", "!lock  (braucht \u2705)", Icons.Default.Lock, !isSending,
                    MaterialTheme.colorScheme.errorContainer,
                    MaterialTheme.colorScheme.onErrorContainer
                ) {
                    scope.launch { send(prefs, "!lock") { s, r -> isSending = s; lastResult = r } }
                }
                EmergencyButton("Screenshot", "!screenshot  (braucht \u2705)", Icons.Default.Screenshot, !isSending) {
                    scope.launch { send(prefs, "!screenshot") { s, r -> isSending = s; lastResult = r } }
                }

                if (isSending) {
                    CircularProgressIndicator(Modifier.padding(top = 16.dp))
                    Text("Sende Command\u2026")
                }

                lastResult?.let { msg ->
                    Card(
                        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = if (msg.startsWith("OK"))
                                MaterialTheme.colorScheme.primaryContainer
                            else MaterialTheme.colorScheme.errorContainer
                        )
                    ) {
                        Text(msg, Modifier.padding(16.dp))
                    }
                }

                Text("Beta 0.1.0 \u2013 Send / Remote", style = MaterialTheme.typography.labelSmall)
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
        modifier = Modifier.fillMaxWidth().height(88.dp),
        colors = ButtonDefaults.buttonColors(containerColor = containerColor, contentColor = contentColor),
        shape = MaterialTheme.shapes.large
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Icon(icon, null, Modifier.size(32.dp))
            Column {
                Text(title, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                Text(subtitle, fontSize = 13.sp)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(prefs: Prefs, onSave: () -> Unit) {
    var token by remember { mutableStateOf(prefs.botToken) }
    var channel by remember { mutableStateOf(prefs.channelId) }
    val context = LocalContext.current

    Scaffold(topBar = { TopAppBar(title = { Text("Settings") }) }) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp)
        ) {
            OutlinedTextField(token, { token = it }, label = { Text("Bot Token") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(channel, { channel = it }, label = { Text("Command Channel ID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Button(
                onClick = {
                    if (token.isBlank() || channel.isBlank()) {
                        Toast.makeText(context, "Beide Felder ausf\u00fcllen", Toast.LENGTH_SHORT).show()
                        return@Button
                    }
                    prefs.botToken = token
                    prefs.channelId = channel
                    Toast.makeText(context, "Gespeichert", Toast.LENGTH_SHORT).show()
                    onSave()
                },
                modifier = Modifier.fillMaxWidth().height(56.dp)
            ) { Text("Speichern") }
        }
    }
}

private suspend fun send(prefs: Prefs, command: String, onUpdate: (Boolean, String?) -> Unit) {
    onUpdate(true, null)
    val result = withContext(Dispatchers.IO) {
        DiscordClient(prefs.botToken, prefs.channelId).sendCommand(command)
    }
    onUpdate(false, result.fold(
        onSuccess = { "OK \u2013 `$command` gesendet" },
        onFailure = { "Fehler: ${it.message}" }
    ))
}

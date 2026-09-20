package com.ebook.ocrreader.ui

import android.content.Context
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ebook.ocrreader.ReaderApp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppSettingsScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val prefs = remember { (context.applicationContext as ReaderApp).repo.prefs }

    var ocrLanguage by remember { mutableStateOf(prefs.getString("language", "한국어") ?: "한국어") }
    var ocrQuality by remember { mutableIntStateOf(prefs.getInt("quality", 2200)) }
    var chargingOnly by remember { mutableStateOf(prefs.getBoolean("charging", false)) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("설정", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로가기")
                    }
                }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            // Privacy & Offline Badge Card
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.Top
                ) {
                    Icon(
                        imageVector = Icons.Default.Security,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(28.dp)
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            "100% 완전 오프라인 & 프라이버시 보장",
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.titleSmall,
                            color = MaterialTheme.colorScheme.onPrimaryContainer
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "본 앱은 외부 LLM(인공지능) 서버나 클라우드 OCR을 전혀 사용하지 않습니다.\n" +
                                    "모든 PDF 렌더링, 텍스트 인식, 데이터 저장은 기기 내부에서 완전히 오프라인으로 안전하게 실행됩니다.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.85f),
                            lineHeight = 18.sp
                        )
                    }
                }
            }

            // 1. OCR Settings Section
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    "OCR 엔진 설정",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )

                // OCR Language
                Text("인식 언어", fontWeight = FontWeight.Medium)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    listOf("한국어" to "한국어 + 영어", "영어" to "영어 전용").forEach { (code, name) ->
                        val selected = ocrLanguage == code
                        FilterChip(
                            selected = selected,
                            onClick = {
                                ocrLanguage = code
                                prefs.edit().putString("language", code).apply()
                            },
                            label = { Text(name) }
                        )
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))

                // OCR Quality
                Text("인식 품질 (렌더링 해상도)", fontWeight = FontWeight.Medium)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    listOf(
                        1600 to "빠르게 (1600px)",
                        2200 to "일반 (2200px)",
                        3000 to "고품질 (3000px)"
                    ).forEach { (px, label) ->
                        val selected = ocrQuality == px
                        FilterChip(
                            selected = selected,
                            onClick = {
                                ocrQuality = px
                                prefs.edit().putInt("quality", px).apply()
                            },
                            label = { Text(label, fontSize = 12.sp) }
                        )
                    }
                }
                Text(
                    "해상도가 높을수록 작은 글씨 인식률이 향상되지만 배터리와 처리 시간이 더 소요됩니다. (일반 2200px 권장)",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray
                )

                Spacer(modifier = Modifier.height(6.dp))

                // Charging constraint
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("충전 중에만 대량 OCR 실행", fontWeight = FontWeight.Medium)
                        Text("배터리 소모를 방지하기 위해 기기가 충전 중일 때만 백그라운드 OCR을 수행합니다", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                    }
                    Switch(
                        checked = chargingOnly,
                        onCheckedChange = {
                            chargingOnly = it
                            prefs.edit().putBoolean("charging", it).apply()
                        }
                    )
                }
            }

            HorizontalDivider()

            // 2. App Info Section
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "앱 정보",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )

                ListItem(
                    headlineContent = { Text("OCR Reflow Reader (오프라인 OCR 리더)") },
                    supportingContent = { Text("버전 1.0.0 (On-Device OCR & Reflow Engine)") }
                )

                ListItem(
                    headlineContent = { Text("사용 오픈소스 & SDK") },
                    supportingContent = { Text("Google ML Kit Text Recognition, AndroidX Room, Jetpack Compose, Android PdfRenderer") }
                )
            }

            Spacer(modifier = Modifier.height(32.dp))
        }
    }
}

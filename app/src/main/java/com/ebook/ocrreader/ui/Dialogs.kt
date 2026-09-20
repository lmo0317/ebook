package com.ebook.ocrreader.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ebook.ocrreader.*
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReaderSettingsSheet(
    settings: ReaderSettings,
    onSettingsChanged: ((ReaderSettings) -> ReaderSettings) -> Unit,
    onRebuildParagraphs: (() -> Unit)? = null,
    onDismiss: () -> Unit
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .padding(bottom = 32.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(20.dp)
        ) {
            Text(
                text = "독서 설정",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold
            )

            // 1. Font Size
            Column {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("글자 크기", fontWeight = FontWeight.Medium)
                    Text("${settings.fontSizeSp.toInt()} sp", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary)
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(onClick = {
                        if (settings.fontSizeSp > 12f) onSettingsChanged { it.copy(fontSizeSp = it.fontSizeSp - 1f) }
                    }) {
                        Text("A-", fontWeight = FontWeight.Bold, fontSize = 14.sp)
                    }
                    Slider(
                        value = settings.fontSizeSp,
                        onValueChange = { value -> onSettingsChanged { it.copy(fontSizeSp = value) } },
                        valueRange = 12f..40f,
                        steps = 27,
                        modifier = Modifier.weight(1f)
                    )
                    IconButton(onClick = {
                        if (settings.fontSizeSp < 40f) onSettingsChanged { it.copy(fontSizeSp = it.fontSizeSp + 1f) }
                    }) {
                        Text("A+", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    }
                }
            }

            // 2. Font Family
            Column {
                Text("글꼴", fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    listOf("Sans" to "기본 고딕 (Sans)", "Serif" to "바탕 / 명조 (Serif)").forEach { (key, label) ->
                        val selected = settings.fontFamily == key
                        Button(
                            onClick = { onSettingsChanged { it.copy(fontFamily = key) } },
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant,
                                contentColor = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant
                            ),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text(label, fontSize = 13.sp)
                        }
                    }
                }
            }

            // 3. Theme
            Column {
                Text("배경 테마", fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(10.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    listOf("Light" to "밝게", "Sepia" to "세피아", "Dark" to "어둡게").forEach { (themeKey, name) ->
                        val themeColors = ReaderThemes.getColors(themeKey)
                        val isSelected = settings.theme == themeKey
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(12.dp))
                                .background(themeColors.background)
                                .border(
                                    width = if (isSelected) 2.5.dp else 1.dp,
                                    color = if (isSelected) MaterialTheme.colorScheme.primary else themeColors.divider,
                                    shape = RoundedCornerShape(12.dp)
                                )
                                .clickable { onSettingsChanged { it.copy(theme = themeKey) } }
                                .padding(vertical = 12.dp)
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(24.dp)
                                    .clip(CircleShape)
                                    .background(themeColors.surface)
                                    .border(1.dp, themeColors.divider, CircleShape),
                                contentAlignment = Alignment.Center
                            ) {
                                if (isSelected) {
                                    Icon(
                                        imageVector = Icons.Default.Check,
                                        contentDescription = null,
                                        tint = themeColors.text,
                                        modifier = Modifier.size(16.dp)
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(name, color = themeColors.text, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                        }
                    }
                }
            }

            // 4. Line Spacing & Margins
            Column {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("줄 간격", fontWeight = FontWeight.Medium)
                    Text(String.format(Locale.getDefault(), "%.1fx", settings.lineHeightMultiplier), color = MaterialTheme.colorScheme.primary)
                }
                Slider(
                    value = settings.lineHeightMultiplier,
                    onValueChange = { onSettingsChanged { s -> s.copy(lineHeightMultiplier = it) } },
                    valueRange = 1.0f..2.4f,
                    steps = 13
                )
            }

            Column {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("좌우 여백", fontWeight = FontWeight.Medium)
                    Text("${settings.horizontalMarginDp} dp", color = MaterialTheme.colorScheme.primary)
                }
                Slider(
                    value = settings.horizontalMarginDp.toFloat(),
                    onValueChange = { onSettingsChanged { s -> s.copy(horizontalMarginDp = it.toInt()) } },
                    valueRange = 8f..48f,
                    steps = 19
                )
            }

            Column {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("문단 간격", fontWeight = FontWeight.Medium)
                    Text("${settings.paragraphSpacingDp} dp", color = MaterialTheme.colorScheme.primary)
                }
                Slider(
                    value = settings.paragraphSpacingDp.toFloat(),
                    onValueChange = { onSettingsChanged { s -> s.copy(paragraphSpacingDp = it.toInt()) } },
                    valueRange = 0f..32f,
                    steps = 16
                )
            }

            HorizontalDivider()

            // 5. Layout Filters
            Text("문서 필터 및 디스플레이", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("페이지 번호 숨기기", fontWeight = FontWeight.Medium)
                    Text("상/하단에 단독으로 위치한 페이지 번호 제거", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                }
                Switch(
                    checked = settings.hidePageNumbers,
                    onCheckedChange = { onSettingsChanged { s -> s.copy(hidePageNumbers = it) } }
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("머리말 숨기기", fontWeight = FontWeight.Medium)
                    Text("페이지 상단 여백의 헤더 텍스트 숨김", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                }
                Switch(
                    checked = settings.hideHeaders,
                    onCheckedChange = { onSettingsChanged { s -> s.copy(hideHeaders = it) } }
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("꼬리말 숨기기", fontWeight = FontWeight.Medium)
                    Text("페이지 하단 여백의 푸터 텍스트 숨김", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                }
                Switch(
                    checked = settings.hideFooters,
                    onCheckedChange = { onSettingsChanged { s -> s.copy(hideFooters = it) } }
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("화면 켜짐 유지", fontWeight = FontWeight.Medium)
                    Text("독서 중 화면이 자동으로 꺼지지 않음", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                }
                Switch(
                    checked = settings.keepScreenOn,
                    onCheckedChange = { onSettingsChanged { s -> s.copy(keepScreenOn = it) } }
                )
            }

            if (onRebuildParagraphs != null) {
                HorizontalDivider()
                OutlinedButton(
                    onClick = { onRebuildParagraphs(); onDismiss() },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.Refresh, null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("문단 구조 재구성 (개행/제목 재분석)")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ParagraphActionSheet(
    paragraph: Paragraph,
    onViewOriginal: (() -> Unit)? = null,
    onCopy: () -> Unit,
    onAddBookmark: () -> Unit,
    onEdit: () -> Unit,
    onSearch: () -> Unit,
    onDismiss: () -> Unit
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .padding(bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "P. ${paragraph.page} 문단 메뉴",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )

            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = paragraph.text,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(12.dp)
                )
            }

            Spacer(modifier = Modifier.height(4.dp))

            if (onViewOriginal != null) {
                ListItem(
                    headlineContent = { Text("원본 페이지에서 확인") },
                    supportingContent = { Text("스캔 이미지에서 이 문단의 원본 위치를 강조 표시합니다") },
                    leadingContent = { Icon(Icons.Default.FindInPage, null, tint = MaterialTheme.colorScheme.primary) },
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .clickable { onViewOriginal(); onDismiss() }
                )
            }

            ListItem(
                headlineContent = { Text("텍스트 복사") },
                leadingContent = { Icon(Icons.Default.ContentCopy, null) },
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .clickable { onCopy(); onDismiss() }
            )

            ListItem(
                headlineContent = { Text("책갈피 등록") },
                leadingContent = { Icon(Icons.Default.BookmarkBorder, null) },
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .clickable { onAddBookmark(); onDismiss() }
            )

            ListItem(
                headlineContent = { Text("문단 텍스트 수정") },
                supportingContent = { Text("OCR 인식 오류를 직접 교정합니다") },
                leadingContent = { Icon(Icons.Default.Edit, null) },
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .clickable { onEdit(); onDismiss() }
            )

            ListItem(
                headlineContent = { Text("본문에서 검색") },
                leadingContent = { Icon(Icons.Default.Search, null) },
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .clickable { onSearch(); onDismiss() }
            )
        }
    }
}

@Composable
fun ParagraphEditDialog(
    paragraph: Paragraph,
    onSave: (String) -> Unit,
    onDismiss: () -> Unit
) {
    var text by remember { mutableStateOf(paragraph.text) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("문단 텍스트 수정 (P. ${paragraph.page})") },
        text = {
            Column(modifier = Modifier.fillMaxWidth()) {
                Text(
                    "OCR 인식 오류가 있는 문장을 올바르게 수정하세요.",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray
                )
                Spacer(modifier = Modifier.height(12.dp))
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it },
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 120.dp, max = 260.dp),
                    label = { Text("문단 텍스트") }
                )
            }
        },
        confirmButton = {
            Button(
                onClick = { onSave(text); onDismiss() },
                enabled = text.isNotBlank()
            ) {
                Text("저장")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("취소") }
        }
    )
}

@Composable
fun AddBookmarkDialog(
    page: Int,
    onSave: (String) -> Unit,
    onDismiss: () -> Unit
) {
    var memo by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("책갈피 추가 (P. $page)") },
        text = {
            Column {
                Text("현재 위치에 메모와 함께 책갈피를 추가합니다.", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                Spacer(modifier = Modifier.height(12.dp))
                OutlinedTextField(
                    value = memo,
                    onValueChange = { memo = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("메모 (선택사항)") },
                    placeholder = { Text("예: 인상 깊은 구절, 3장 시작") }
                )
            }
        },
        confirmButton = {
            Button(onClick = { onSave(memo); onDismiss() }) { Text("추가") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("취소") }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchInBookDialog(
    onSearch: suspend (String) -> List<Paragraph>,
    onSelectParagraph: (Paragraph) -> Unit,
    onDismiss: () -> Unit
) {
    var query by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<Paragraph>>(emptyList()) }
    var searched by remember { mutableStateOf(false) }
    var isSearching by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = false)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .padding(bottom = 24.dp)
        ) {
            Text(
                text = "본문 검색",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("검색할 단어 입력...") },
                    singleLine = true,
                    trailingIcon = {
                        if (query.isNotEmpty()) {
                            IconButton(onClick = { query = ""; results = emptyList(); searched = false }) {
                                Icon(Icons.Default.Close, null)
                            }
                        }
                    }
                )
                Spacer(modifier = Modifier.width(8.dp))
                Button(
                    onClick = {
                        if (query.isNotBlank()) {
                            isSearching = true
                            scope.launch {
                                results = onSearch(query.trim())
                                searched = true
                                isSearching = false
                            }
                        }
                    },
                    enabled = query.isNotBlank() && !isSearching
                ) {
                    Icon(Icons.Default.Search, null)
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            if (isSearching) {
                Box(modifier = Modifier.fillMaxWidth().height(160.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else if (searched) {
                Text(
                    text = "검색 결과 ${results.size}건",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(8.dp))
                if (results.isEmpty()) {
                    Box(modifier = Modifier.fillMaxWidth().height(120.dp), contentAlignment = Alignment.Center) {
                        Text("검색 결과가 없습니다.", color = Color.Gray)
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 380.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(results, key = { it.id }) { item ->
                            Surface(
                                shape = RoundedCornerShape(8.dp),
                                color = MaterialTheme.colorScheme.surfaceVariant,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        onSelectParagraph(item)
                                        onDismiss()
                                    }
                            ) {
                                Column(modifier = Modifier.padding(12.dp)) {
                                    Text(
                                        text = "P. ${item.page}",
                                        style = MaterialTheme.typography.labelMedium,
                                        color = MaterialTheme.colorScheme.primary,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(
                                        text = item.text,
                                        style = MaterialTheme.typography.bodyMedium,
                                        maxLines = 3,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TocAndBookmarksDialog(
    contents: List<Paragraph>,
    bookmarks: List<Bookmark>,
    onSelectPage: (Int) -> Unit,
    onDeleteBookmark: (Long) -> Unit,
    onDismiss: () -> Unit,
    onSelectParagraph: ((Paragraph) -> Unit)? = null
) {
    var selectedTab by remember { mutableIntStateOf(0) }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .padding(bottom = 32.dp)
        ) {
            TabRow(selectedTabIndex = selectedTab) {
                Tab(
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 },
                    text = { Text("목차 (${contents.size})") },
                    icon = { Icon(Icons.Default.MenuBook, null) }
                )
                Tab(
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 },
                    text = { Text("책갈피 (${bookmarks.size})") },
                    icon = { Icon(Icons.Default.Bookmark, null) }
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            if (selectedTab == 0) {
                if (contents.isEmpty()) {
                    Box(modifier = Modifier.fillMaxWidth().height(160.dp), contentAlignment = Alignment.Center) {
                        Text("감지된 제목/목차가 없습니다.", color = Color.Gray)
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 400.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(contents) { title ->
                            ListItem(
                                headlineContent = { Text(title.text, fontWeight = FontWeight.Medium) },
                                trailingContent = {
                                    Badge { Text("P. ${title.page}") }
                                },
                                modifier = Modifier
                                    .clip(RoundedCornerShape(8.dp))
                                    .clickable {
                                        if (onSelectParagraph != null) {
                                            onSelectParagraph(title)
                                        } else {
                                            onSelectPage(title.page)
                                        }
                                        onDismiss()
                                    }
                            )
                        }
                    }
                }
            } else {
                if (bookmarks.isEmpty()) {
                    Box(modifier = Modifier.fillMaxWidth().height(160.dp), contentAlignment = Alignment.Center) {
                        Text("등록된 책갈피가 없습니다.", color = Color.Gray)
                    }
                } else {
                    val dateFormat = remember { SimpleDateFormat("yyyy.MM.dd HH:mm", Locale.getDefault()) }
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 400.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(bookmarks, key = { it.id }) { bm ->
                            Surface(
                                shape = RoundedCornerShape(8.dp),
                                color = MaterialTheme.colorScheme.surfaceVariant,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        onSelectPage(bm.page)
                                        onDismiss()
                                    }
                            ) {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(12.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(modifier = Modifier.weight(1f)) {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Text(
                                                "P. ${bm.page}",
                                                style = MaterialTheme.typography.labelLarge,
                                                fontWeight = FontWeight.Bold,
                                                color = MaterialTheme.colorScheme.primary
                                            )
                                            Spacer(modifier = Modifier.width(8.dp))
                                            Text(
                                                dateFormat.format(Date(bm.created)),
                                                style = MaterialTheme.typography.bodySmall,
                                                color = Color.Gray
                                            )
                                        }
                                        if (bm.memo.isNotBlank()) {
                                            Spacer(modifier = Modifier.height(4.dp))
                                            Text(bm.memo, style = MaterialTheme.typography.bodyMedium)
                                        }
                                    }
                                    IconButton(onClick = { onDeleteBookmark(bm.id) }) {
                                        Icon(Icons.Default.Delete, "삭제", tint = Color.Gray)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun BookDetailDialog(
    book: Book,
    onUpdate: (title: String, author: String, memo: String) -> Unit,
    onDelete: () -> Unit,
    onExport: (html: Boolean) -> Unit,
    onDismiss: () -> Unit
) {
    var title by remember { mutableStateOf(book.title) }
    var author by remember { mutableStateOf(book.author) }
    var memo by remember { mutableStateOf(book.memo) }
    var showDeleteConfirm by remember { mutableStateOf(false) }

    val dateFormat = remember { SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()) }

    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("도서 삭제") },
            text = { Text("'${book.title}' 도서와 추출된 모든 OCR 데이터를 기기에서 완전히 삭제하시겠습니까?") },
            confirmButton = {
                Button(
                    onClick = { showDeleteConfirm = false; onDelete(); onDismiss() },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                ) {
                    Text("삭제")
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteConfirm = false }) { Text("취소") }
            }
        )
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("도서 정보 및 편집") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("도서 제목") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = author,
                    onValueChange = { author = it },
                    label = { Text("저자") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = memo,
                    onValueChange = { memo = it },
                    label = { Text("도서 메모") },
                    modifier = Modifier.fillMaxWidth()
                )

                HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))

                Text("파일 이름: ${book.fileName}", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                Text("페이지 수: ${book.pages} 쪽", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                Text("파일 크기: ${book.size / 1024 / 1024} MB", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                Text("등록 일시: ${dateFormat.format(Date(book.created))}", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                if (book.opened > 0) {
                    Text("최근 읽음: ${dateFormat.format(Date(book.opened))}", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                }

                HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))

                Text("OCR 텍스트 내보내기", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedButton(
                        onClick = { onExport(false); onDismiss() },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("TXT 파일", fontSize = 12.sp)
                    }
                    OutlinedButton(
                        onClick = { onExport(true); onDismiss() },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("HTML 파일", fontSize = 12.sp)
                    }
                }

                Spacer(modifier = Modifier.height(4.dp))

                Button(
                    onClick = { showDeleteConfirm = true },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.errorContainer, contentColor = MaterialTheme.colorScheme.onErrorContainer),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.Delete, null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("이 도서 삭제")
                }
            }
        },
        confirmButton = {
            Button(onClick = {
                onUpdate(title, author, memo)
                onDismiss()
            }) {
                Text("저장")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("닫기") }
        }
    )
}

@Composable
fun OcrStatusDialog(
    book: Book,
    pages: List<Page>,
    onPause: () -> Unit,
    onResume: (retryErrors: Boolean) -> Unit,
    onResetAll: () -> Unit,
    onRetryPage: (Int) -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("OCR 진행 상태") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = book.title,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )

                val progress = if (book.pages > 0) book.done.toFloat() / book.pages else 0f
                LinearProgressIndicator(
                    progress = { progress },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(8.dp)
                        .clip(RoundedCornerShape(4.dp))
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        "${book.done} / ${book.pages} 페이지 (${(progress * 100).toInt()}%)",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium
                    )
                    Text(
                        text = when (book.status) {
                            "COMPLETED" -> "완료"
                            "PROCESSING" -> "처리 중"
                            "PAUSED" -> "일시정지"
                            else -> "오류 발생"
                        },
                        color = when (book.status) {
                            "COMPLETED" -> Color(0xFF10B981)
                            "PROCESSING" -> MaterialTheme.colorScheme.primary
                            "PAUSED" -> Color(0xFFF59E0B)
                            else -> Color(0xFFEF4444)
                        },
                        fontWeight = FontWeight.Bold
                    )
                }

                if (book.error.isNotBlank()) {
                    Text(
                        text = book.error,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall
                    )
                }

                // Control buttons
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    if (book.status == "PROCESSING") {
                        OutlinedButton(
                            onClick = onPause,
                            modifier = Modifier.weight(1f)
                        ) {
                            Icon(Icons.Default.Pause, null, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("일시정지", fontSize = 12.sp)
                        }
                    } else {
                        Button(
                            onClick = { onResume(false) },
                            modifier = Modifier.weight(1f)
                        ) {
                            Icon(Icons.Default.PlayArrow, null, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("OCR 계속", fontSize = 12.sp)
                        }
                    }

                    OutlinedButton(
                        onClick = { onResume(true) },
                        modifier = Modifier.weight(1f)
                    ) {
                        Icon(Icons.Default.Refresh, null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("실패 재시도", fontSize = 12.sp)
                    }
                }

                OutlinedButton(
                    onClick = onResetAll,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)
                ) {
                    Text("전체 처음부터 다시 OCR", fontSize = 12.sp)
                }

                HorizontalDivider()

                // Page summary grid / list
                Text("페이지별 상태", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
                val errorPages = pages.filter { it.status == "ERROR" }
                if (errorPages.isNotEmpty()) {
                    Text(
                        "오류 발생 페이지 (${errorPages.size}개): ${errorPages.joinToString { "${it.number}쪽" }}",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.Red
                    )
                }

                Text(
                    "• 완료: ${pages.count { it.status == "COMPLETED" }} 쪽\n" +
                            "• 진행 중: ${pages.count { it.status == "PROCESSING" }} 쪽\n" +
                            "• 대기 중: ${pages.count { it.status == "NOT_STARTED" }} 쪽\n" +
                            "• 오류: ${errorPages.size} 쪽",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray
                )
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("닫기") }
        }
    )
}

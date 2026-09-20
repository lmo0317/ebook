package com.ebook.ocrreader.ui

import android.content.Intent
import android.graphics.BitmapFactory
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ebook.ocrreader.Book
import com.ebook.ocrreader.BookSortOrder
import com.ebook.ocrreader.LibraryViewModel
import com.ebook.ocrreader.Page
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LibraryScreen(
    viewModel: LibraryViewModel,
    onOpenBook: (String) -> Unit,
    onOpenSettings: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    val books by viewModel.books.collectAsState()
    val sortOrder by viewModel.sortOrder.collectAsState()
    val searchQuery by viewModel.searchQuery.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    var showSearchBar by remember { mutableStateOf(false) }
    var selectedBookForDetail by remember { mutableStateOf<Book?>(null) }
    var selectedBookForOcrStatus by remember { mutableStateOf<Book?>(null) }
    var ocrStatusPages by remember { mutableStateOf<List<Page>>(emptyList()) }

    // SAF File picker launcher (supports PDF and TXT)
    val filePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri != null) {
            viewModel.importBook(uri)
        }
    }

    LaunchedEffect(Unit) {
        launch {
            viewModel.errorMessage.collectLatest { msg ->
                Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
            }
        }
        launch {
            viewModel.successMessage.collectLatest { msg ->
                Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "내 서재",
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.titleLarge
                        )
                        if (books.isNotEmpty()) {
                            Spacer(modifier = Modifier.width(8.dp))
                            Badge(containerColor = MaterialTheme.colorScheme.primaryContainer) {
                                Text("${books.size}권", color = MaterialTheme.colorScheme.onPrimaryContainer)
                            }
                        }
                    }
                },
                actions = {
                    IconButton(onClick = { showSearchBar = !showSearchBar }) {
                        Icon(Icons.Default.Search, "검색")
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, "앱 설정")
                    }
                }
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { filePickerLauncher.launch(arrayOf("application/pdf", "text/plain", "application/zip", "application/x-zip-compressed", "application/octet-stream", "*/*")) },
                icon = { Icon(Icons.Default.Add, "도서 추가") },
                text = { Text("도서 추가") },
                containerColor = MaterialTheme.colorScheme.primary,
                contentColor = MaterialTheme.colorScheme.onPrimary
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            // Search Bar
            if (showSearchBar) {
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = { viewModel.setSearchQuery(it) },
                    placeholder = { Text("도서 제목 또는 저자 검색...") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 6.dp),
                    singleLine = true,
                    leadingIcon = { Icon(Icons.Default.Search, null) },
                    trailingIcon = {
                        if (searchQuery.isNotEmpty()) {
                            IconButton(onClick = { viewModel.setSearchQuery("") }) {
                                Icon(Icons.Default.Close, "지우기")
                            }
                        }
                    }
                )
            }

            // Sort Filter Chips
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FilterChip(
                    selected = sortOrder == BookSortOrder.RECENT,
                    onClick = { viewModel.setSortOrder(BookSortOrder.RECENT) },
                    label = { Text("최근 읽은 순") }
                )
                FilterChip(
                    selected = sortOrder == BookSortOrder.ADDED,
                    onClick = { viewModel.setSortOrder(BookSortOrder.ADDED) },
                    label = { Text("추가한 순") }
                )
                FilterChip(
                    selected = sortOrder == BookSortOrder.TITLE,
                    onClick = { viewModel.setSortOrder(BookSortOrder.TITLE) },
                    label = { Text("제목 순") }
                )
            }

            if (isLoading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }

            if (books.isEmpty() && !isLoading) {
                // Empty Library State
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(32.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        Surface(
                            shape = RoundedCornerShape(28.dp),
                            color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f),
                            modifier = Modifier.size(96.dp)
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(
                                    imageVector = Icons.Default.MenuBook,
                                    contentDescription = null,
                                    modifier = Modifier.size(48.dp),
                                    tint = MaterialTheme.colorScheme.primary
                                )
                            }
                        }

                        Text(
                            text = if (searchQuery.isNotBlank()) "검색된 도서가 없습니다." else "서재에 등록된 도서가 없습니다.",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )

                        Text(
                            text = "스캔본 PDF나 텍스트(TXT) 파일을 추가하면 문단을 분석하여\n휴대폰 화면에 맞는 최적의 크기로 편안하게 읽을 수 있습니다.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color.Gray,
                            textAlign = TextAlign.Center
                        )

                        Button(
                            onClick = { filePickerLauncher.launch(arrayOf("application/pdf", "text/plain", "application/zip", "application/x-zip-compressed", "application/octet-stream", "*/*")) },
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Icon(Icons.Default.UploadFile, null)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("도서 가져오기 (ZIP / PDF / TXT)")
                        }
                    }
                }
            } else {
                // Book Grid
                LazyVerticalGrid(
                    columns = GridCells.Adaptive(minSize = 155.dp),
                    contentPadding = PaddingValues(16.dp),
                    horizontalArrangement = Arrangement.spacedBy(14.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                    modifier = Modifier.fillMaxSize()
                ) {
                    items(books, key = { it.id }) { book ->
                        BookCard(
                            book = book,
                            coverFile = viewModel.getCoverFile(book.id),
                            onClick = { onOpenBook(book.id) },
                            onDetailClick = { selectedBookForDetail = book },
                            onOcrStatusClick = {
                                scope.launch {
                                    ocrStatusPages = viewModel.getPages(book.id)
                                    selectedBookForOcrStatus = book
                                }
                            },
                            onExportClick = { html ->
                                viewModel.exportBook(book.id, html) { file ->
                                    val sendIntent = Intent(Intent.ACTION_SEND).apply {
                                        type = if (html) "text/html" else "text/plain"
                                        putExtra(Intent.EXTRA_SUBJECT, book.title)
                                        putExtra(Intent.EXTRA_TEXT, file.readText())
                                    }
                                    context.startActivity(Intent.createChooser(sendIntent, "내보내기 공유"))
                                }
                            },
                            onRebuildParagraphsClick = { viewModel.rebuildParagraphs(book.id) },
                            onDeleteClick = { viewModel.deleteBook(book.id) }
                        )
                    }
                }
            }
        }
    }

    // Detail Dialog
    selectedBookForDetail?.let { book ->
        BookDetailDialog(
            book = book,
            onUpdate = { title, author, memo ->
                viewModel.updateBookMetadata(book.id, title, author, memo)
            },
            onDelete = {
                viewModel.deleteBook(book.id)
            },
            onExport = { html ->
                viewModel.exportBook(book.id, html) { file ->
                    val sendIntent = Intent(Intent.ACTION_SEND).apply {
                        type = if (html) "text/html" else "text/plain"
                        putExtra(Intent.EXTRA_SUBJECT, book.title)
                        putExtra(Intent.EXTRA_TEXT, file.readText())
                    }
                    context.startActivity(Intent.createChooser(sendIntent, "내보내기 공유"))
                }
            },
            onDismiss = { selectedBookForDetail = null }
        )
    }

    // OCR Status Dialog
    selectedBookForOcrStatus?.let { book ->
        OcrStatusDialog(
            book = book,
            pages = ocrStatusPages,
            onPause = { viewModel.pauseOcr(book.id) },
            onResume = { retryErrors -> viewModel.resumeOcr(book.id, retryErrors) },
            onResetAll = { viewModel.resetAndReOcr(book.id) },
            onRetryPage = { pageNum -> },
            onDismiss = { selectedBookForOcrStatus = null }
        )
    }
}

@Composable
fun BookCard(
    book: Book,
    coverFile: File,
    onClick: () -> Unit,
    onDetailClick: () -> Unit,
    onOcrStatusClick: () -> Unit,
    onExportClick: (html: Boolean) -> Unit,
    onRebuildParagraphsClick: () -> Unit,
    onDeleteClick: () -> Unit
) {
    var menuExpanded by remember { mutableStateOf(false) }

    Card(
        shape = RoundedCornerShape(14.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .clickable(onClick = onClick)
    ) {
        Column {
            // Cover Image with Status Overlay
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(210.dp)
                    .background(Color(0xFFE2E8F0))
            ) {
                var coverBitmap by remember(coverFile.lastModified()) {
                    mutableStateOf(
                        if (coverFile.exists()) BitmapFactory.decodeFile(coverFile.absolutePath) else null
                    )
                }

                if (coverBitmap != null) {
                    Image(
                        bitmap = coverBitmap!!.asImageBitmap(),
                        contentDescription = book.title,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.fillMaxSize()
                    )
                } else {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = Icons.Default.MenuBook,
                            contentDescription = null,
                            modifier = Modifier.size(54.dp),
                            tint = Color.LightGray
                        )
                    }
                }

                // Status Badge
                val isTxtBook = book.fileName.endsWith(".txt", ignoreCase = true) || book.status == "READY"
                Surface(
                    color = when {
                        isTxtBook -> Color(0xDD0284C7)
                        book.status == "COMPLETED" -> Color(0xDD10B981)
                        book.status == "PROCESSING" -> Color(0xDD2563EB)
                        book.status == "PAUSED" -> Color(0xDDF59E0B)
                        else -> Color(0xDDEF4444)
                    },
                    shape = RoundedCornerShape(bottomEnd = 8.dp),
                    modifier = Modifier.align(Alignment.TopStart)
                ) {
                    Text(
                        text = when {
                            isTxtBook -> "e-Book"
                            book.status == "COMPLETED" -> "OCR 완료"
                            book.status == "PROCESSING" -> "OCR ${book.done}/${book.pages}"
                            book.status == "PAUSED" -> "일시정지"
                            else -> "OCR 오류"
                        },
                        color = Color.White,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                    )
                }

                // Top right 3-dots menu button
                Box(modifier = Modifier.align(Alignment.TopEnd)) {
                    Surface(
                        shape = RoundedCornerShape(bottomStart = 8.dp),
                        color = Color(0x99000000)
                    ) {
                        IconButton(
                            onClick = { menuExpanded = true },
                            modifier = Modifier.size(32.dp)
                        ) {
                            Icon(
                                Icons.Default.MoreVert,
                                "메뉴",
                                tint = Color.White,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }

                    DropdownMenu(
                        expanded = menuExpanded,
                        onDismissRequest = { menuExpanded = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text("도서 정보 및 편집") },
                            leadingIcon = { Icon(Icons.Default.Info, null) },
                            onClick = { menuExpanded = false; onDetailClick() }
                        )
                        if (!isTxtBook) {
                            DropdownMenuItem(
                                text = { Text("OCR 상태 및 제어") },
                                leadingIcon = { Icon(Icons.Default.Sync, null) },
                                onClick = { menuExpanded = false; onOcrStatusClick() }
                            )
                        }
                        DropdownMenuItem(
                            text = { Text("텍스트 내보내기 (TXT)") },
                            leadingIcon = { Icon(Icons.Default.Description, null) },
                            onClick = { menuExpanded = false; onExportClick(false) }
                        )
                        DropdownMenuItem(
                            text = { Text("HTML 내보내기") },
                            leadingIcon = { Icon(Icons.Default.Code, null) },
                            onClick = { menuExpanded = false; onExportClick(true) }
                        )
                        if (!isTxtBook) {
                            DropdownMenuItem(
                                text = { Text("문단 구조 재구성 (개행/제목 정리)") },
                                leadingIcon = { Icon(Icons.Default.Refresh, null) },
                                onClick = { menuExpanded = false; onRebuildParagraphsClick() }
                            )
                        }
                        HorizontalDivider()
                        DropdownMenuItem(
                            text = { Text("도서 삭제", color = MaterialTheme.colorScheme.error) },
                            leadingIcon = { Icon(Icons.Default.Delete, null, tint = MaterialTheme.colorScheme.error) },
                            onClick = { menuExpanded = false; onDeleteClick() }
                        )
                    }
                }
            }

            // Book Info
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(12.dp)
            ) {
                Text(
                    text = book.title,
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )

                if (book.author.isNotBlank()) {
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = book.author,
                        fontSize = 12.sp,
                        color = Color.Gray,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                // Progress Bar
                val progress = if (book.pages > 0) book.done.toFloat() / book.pages else 0f
                LinearProgressIndicator(
                    progress = { progress },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(4.dp)
                        .clip(RoundedCornerShape(2.dp)),
                    color = when (book.status) {
                        "COMPLETED" -> Color(0xFF10B981)
                        "PAUSED" -> Color(0xFFF59E0B)
                        "ERROR" -> Color(0xFFEF4444)
                        else -> MaterialTheme.colorScheme.primary
                    }
                )

                Spacer(modifier = Modifier.height(4.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "${book.pages} 쪽",
                        fontSize = 11.sp,
                        color = Color.Gray
                    )
                    Text(
                        text = "${(progress * 100).toInt()}%",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }
        }
    }
}

package com.ebook.ocrreader.ui

import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.view.WindowManager
import android.widget.Toast
import androidx.compose.animation.*
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.ebook.ocrreader.Paragraph
import com.ebook.ocrreader.ReaderColors
import com.ebook.ocrreader.ReaderThemes
import com.ebook.ocrreader.ReaderViewModel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReaderScreen(
    viewModel: ReaderViewModel,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    val book by viewModel.book.collectAsState()
    val pages by viewModel.pages.collectAsState()
    val paragraphs by viewModel.paragraphs.collectAsState()
    val bookmarks by viewModel.bookmarks.collectAsState()
    val settings by viewModel.settings.collectAsState()
    val isOriginalMode by viewModel.isOriginalMode.collectAsState()
    val currentPage by viewModel.currentPage.collectAsState()
    val highlightBox by viewModel.highlightBox.collectAsState()
    val originalBitmap by viewModel.originalBitmap.collectAsState()
    val isRenderingPage by viewModel.isRenderingPage.collectAsState()

    // Screen-on flag
    val activity = context as? Activity
    DisposableEffect(settings.keepScreenOn) {
        if (settings.keepScreenOn) {
            activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
        onDispose {
            activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    // Toast messages
    LaunchedEffect(Unit) {
        viewModel.message.collectLatest { msg ->
            Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
        }
    }

    var showBars by remember { mutableStateOf(true) }
    var showSettingsSheet by remember { mutableStateOf(false) }
    var showSearchDialog by remember { mutableStateOf(false) }
    var showTocDialog by remember { mutableStateOf(false) }
    var selectedParagraphForMenu by remember { mutableStateOf<Paragraph?>(null) }
    var editingParagraph by remember { mutableStateOf<Paragraph?>(null) }
    var bookmarkingPage by remember { mutableStateOf<Int?>(null) }
    var viewingImageBitmap by remember { mutableStateOf<Bitmap?>(null) }
    var viewingImageCaption by remember { mutableStateOf("") }

    val themeColors = ReaderThemes.getColors(settings.theme)
    val fontFamily = ReaderThemes.getFontFamily(settings.fontFamily)

    val listState = rememberLazyListState()

    // Scroll to position on start
    var hasRestoredScroll by remember { mutableStateOf(false) }
    LaunchedEffect(paragraphs) {
        if (!hasRestoredScroll && paragraphs.isNotEmpty()) {
            val targetIndex = paragraphs.indexOfFirst { it.page >= currentPage }.coerceAtLeast(0)
            if (targetIndex >= 0) {
                listState.scrollToItem(targetIndex)
            }
            hasRestoredScroll = true
        }
    }

    // Track visible page
    LaunchedEffect(listState) {
        snapshotFlow { listState.firstVisibleItemIndex }.collect { index ->
            if (paragraphs.isNotEmpty() && index in paragraphs.indices) {
                val p = paragraphs[index]
                if (p.page != currentPage) {
                    viewModel.setCurrentPage(p.page)
                }
            }
        }
    }

    Scaffold(
        containerColor = themeColors.background,
        contentColor = themeColors.text
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            if (isOriginalMode && book != null) {
                // 1. Original PDF Mode
                val pageInfo = pages.find { it.number == currentPage }
                OriginalPageView(
                    book = book!!,
                    currentPage = currentPage,
                    pageInfo = pageInfo,
                    bitmap = originalBitmap,
                    isRendering = isRenderingPage,
                    highlightBox = highlightBox,
                    onPageChange = { viewModel.setCurrentPage(it) },
                    onRotatePage = { viewModel.rotateCurrentPage() },
                    onRetryOcr = { viewModel.retryCurrentPageOcr() },
                    onClearHighlight = { viewModel.clearHighlight() },
                    onSwitchToReflow = { viewModel.setMode(false) }
                )
            } else {
                // 2. OCR Reflow Mode
                if (book != null && paragraphs.isEmpty()) {
                    // Empty / OCR still in progress
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(24.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Card(
                            colors = CardDefaults.cardColors(containerColor = themeColors.surface),
                            shape = RoundedCornerShape(16.dp),
                            modifier = Modifier.fillMaxWidth(0.9f)
                        ) {
                            Column(
                                modifier = Modifier.padding(24.dp),
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.spacedBy(16.dp)
                            ) {
                                CircularProgressIndicator(color = themeColors.accent)
                                Text(
                                    "페이지 OCR 텍스트를 분석하고 있습니다...",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = themeColors.text,
                                    textAlign = TextAlign.Center
                                )
                                Text(
                                    "진행률: ${book!!.done} / ${book!!.pages} 쪽 완료\n" +
                                            "첫 페이지 분석이 완료되는 즉시 읽을 수 있습니다.",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = themeColors.text.copy(alpha = 0.8f),
                                    textAlign = TextAlign.Center
                                )
                                Button(
                                    onClick = { viewModel.setMode(true) },
                                    colors = ButtonDefaults.buttonColors(containerColor = themeColors.accent)
                                ) {
                                    Icon(Icons.Default.FindInPage, null, modifier = Modifier.size(18.dp))
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text("원본 PDF로 먼저 읽기")
                                }
                            }
                        }
                    }
                } else {
                    // Reflow Paragraphs LazyColumn
                    LazyColumn(
                        state = listState,
                        modifier = Modifier
                            .fillMaxSize()
                            .pointerInput(Unit) {
                                detectTapGestures(onTap = { showBars = !showBars })
                            }
                            .pointerInput(Unit) {
                                detectTransformGestures { _, _, zoom, _ ->
                                    if (zoom != 1f) {
                                        viewModel.updateSettings { s ->
                                            s.copy(fontSizeSp = (s.fontSizeSp * zoom).coerceIn(12f, 40f))
                                        }
                                    }
                                }
                            }
                            .padding(horizontal = settings.horizontalMarginDp.dp),
                        contentPadding = PaddingValues(top = 72.dp, bottom = 96.dp),
                        verticalArrangement = Arrangement.spacedBy(settings.paragraphSpacingDp.dp)
                    ) {
                        itemsIndexed(paragraphs, key = { _, p -> p.id }) { index, p ->
                            // Show page number divider when entering a new page
                            val isFirstOfPage = index == 0 || paragraphs[index - 1].page != p.page
                            if (isFirstOfPage) {
                                Spacer(modifier = Modifier.height(16.dp))
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    HorizontalDivider(
                                        modifier = Modifier.weight(1f),
                                        color = themeColors.divider
                                    )
                                    Text(
                                        text = " — P. ${p.page} — ",
                                        fontSize = 11.sp,
                                        color = themeColors.text.copy(alpha = 0.5f),
                                        fontWeight = FontWeight.Medium,
                                        modifier = Modifier.padding(horizontal = 8.dp)
                                    )
                                    HorizontalDivider(
                                        modifier = Modifier.weight(1f),
                                        color = themeColors.divider
                                    )
                                }
                                Spacer(modifier = Modifier.height(12.dp))
                            }

                            val isTitle = p.type == "TITLE"
                            val isCode = p.type == "CODE" || p.text.startsWith("```")
                            val isImage = p.type == "IMAGE" || p.text.startsWith("[IMAGE:") || (p.text.startsWith("![") && p.text.contains("](") && p.text.endsWith(")"))

                            if (isImage) {
                                InlineImageView(
                                    text = p.text,
                                    bookId = book?.id ?: "",
                                    themeColors = themeColors,
                                    fontSizeSp = settings.fontSizeSp,
                                    onImageClick = { bmp, cap ->
                                        viewingImageBitmap = bmp
                                        viewingImageCaption = cap
                                    },
                                    onLongClick = { selectedParagraphForMenu = p }
                                )
                            } else if (isCode) {
                                val cleanCode = p.text
                                    .removePrefix("```python\n")
                                    .removePrefix("```\n")
                                    .removePrefix("```")
                                    .removeSuffix("\n```")
                                    .removeSuffix("```")
                                    .trim()

                                Surface(
                                    color = themeColors.text.copy(alpha = 0.06f),
                                    shape = RoundedCornerShape(8.dp),
                                    border = androidx.compose.foundation.BorderStroke(1.dp, themeColors.divider),
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 4.dp)
                                        .combinedClickable(
                                            onLongClick = { selectedParagraphForMenu = p },
                                            onClick = { showBars = !showBars }
                                        )
                                ) {
                                    Text(
                                        text = cleanCode,
                                        fontSize = (settings.fontSizeSp * 0.85f).sp,
                                        lineHeight = (settings.fontSizeSp * 1.25f).sp,
                                        fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                                        color = themeColors.text,
                                        modifier = Modifier.padding(10.dp)
                                    )
                                }
                            } else {
                                val fontSize = (if (isTitle) settings.fontSizeSp * 1.25f else settings.fontSizeSp).sp
                                val lineHeight = (if (isTitle) settings.fontSizeSp * 1.5f else settings.fontSizeSp * settings.lineHeightMultiplier).sp
                                val fontWeight = if (isTitle) FontWeight.Bold else FontWeight.Normal

                                Text(
                                    text = p.text,
                                    fontSize = fontSize,
                                    lineHeight = lineHeight,
                                    fontWeight = fontWeight,
                                    fontFamily = fontFamily,
                                    color = if (isTitle) themeColors.accent else themeColors.text,
                                    textAlign = TextAlign.Start,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(6.dp))
                                        .combinedClickable(
                                            onLongClick = { selectedParagraphForMenu = p },
                                            onClick = { showBars = !showBars }
                                        )
                                        .padding(
                                            top = if (isTitle) 14.dp else 2.dp,
                                            bottom = if (isTitle) 6.dp else 2.dp
                                        )
                                )
                            }
                        }
                    }
                }
            }

            // Top Bar
            AnimatedVisibility(
                visible = showBars,
                enter = fadeIn() + slideInVertically { -it },
                exit = fadeOut() + slideOutVertically { -it },
                modifier = Modifier.align(Alignment.TopCenter)
            ) {
                Surface(
                    color = themeColors.surface.copy(alpha = 0.95f),
                    shadowElevation = 4.dp,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .statusBarsPadding()
                            .padding(horizontal = 8.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        IconButton(onClick = onBack) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로가기", tint = themeColors.text)
                        }

                        Text(
                            text = book?.title ?: "리더",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = themeColors.text,
                            maxLines = 1,
                            modifier = Modifier
                                .weight(1f)
                                .padding(horizontal = 8.dp)
                        )

                        // Mode Toggle Pill
                        if (viewModel.hasPdf()) {
                            Surface(
                                shape = RoundedCornerShape(16.dp),
                                color = themeColors.divider,
                                modifier = Modifier.padding(end = 4.dp)
                            ) {
                                Row {
                                    Text(
                                        text = "텍스트",
                                        fontSize = 12.sp,
                                        fontWeight = if (!isOriginalMode) FontWeight.Bold else FontWeight.Normal,
                                        color = if (!isOriginalMode) themeColors.accent else themeColors.text.copy(alpha = 0.6f),
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(16.dp))
                                            .background(if (!isOriginalMode) themeColors.surface else Color.Transparent)
                                            .clickable { viewModel.setMode(false) }
                                            .padding(horizontal = 10.dp, vertical = 6.dp)
                                    )
                                    Text(
                                        text = "원본",
                                        fontSize = 12.sp,
                                        fontWeight = if (isOriginalMode) FontWeight.Bold else FontWeight.Normal,
                                        color = if (isOriginalMode) themeColors.accent else themeColors.text.copy(alpha = 0.6f),
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(16.dp))
                                            .background(if (isOriginalMode) themeColors.surface else Color.Transparent)
                                            .clickable { viewModel.setMode(true) }
                                            .padding(horizontal = 10.dp, vertical = 6.dp)
                                    )
                                }
                            }
                        } else {
                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = themeColors.accent.copy(alpha = 0.12f),
                                modifier = Modifier.padding(end = 4.dp)
                            ) {
                                Text(
                                    text = "e-Book",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = themeColors.accent,
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                )
                            }
                        }

                        IconButton(onClick = { showTocDialog = true }) {
                            Icon(Icons.Default.MenuBook, "목차 / 책갈피", tint = themeColors.text)
                        }

                        IconButton(onClick = { showSearchDialog = true }) {
                            Icon(Icons.Default.Search, "검색", tint = themeColors.text)
                        }

                        IconButton(onClick = { showSettingsSheet = true }) {
                            Icon(Icons.Default.FormatSize, "설정", tint = themeColors.text)
                        }
                    }
                }
            }

            // Bottom Bar
            AnimatedVisibility(
                visible = showBars && book != null,
                enter = fadeIn() + slideInVertically { it },
                exit = fadeOut() + slideOutVertically { it },
                modifier = Modifier.align(Alignment.BottomCenter)
            ) {
                Surface(
                    color = themeColors.surface.copy(alpha = 0.95f),
                    shadowElevation = 6.dp,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .navigationBarsPadding()
                            .padding(horizontal = 16.dp, vertical = 8.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            IconButton(
                                onClick = {
                                    if (currentPage > 1) {
                                        val prev = currentPage - 1
                                        viewModel.setCurrentPage(prev)
                                        val idx = paragraphs.indexOfFirst { it.page >= prev }
                                        if (idx >= 0) scope.launch { listState.animateScrollToItem(idx) }
                                    }
                                },
                                enabled = currentPage > 1
                            ) {
                                Icon(Icons.AutoMirrored.Filled.ArrowBack, "이전 쪽", tint = themeColors.text)
                            }

                            Slider(
                                value = currentPage.toFloat(),
                                onValueChange = { targetPage ->
                                    val p = targetPage.toInt().coerceIn(1, book!!.pages)
                                    viewModel.setCurrentPage(p)
                                    val idx = paragraphs.indexOfFirst { it.page >= p }
                                    if (idx >= 0) scope.launch { listState.scrollToItem(idx) }
                                },
                                valueRange = 1f..book!!.pages.toFloat(),
                                modifier = Modifier.weight(1f)
                            )

                            IconButton(
                                onClick = {
                                    if (currentPage < book!!.pages) {
                                        val next = currentPage + 1
                                        viewModel.setCurrentPage(next)
                                        val idx = paragraphs.indexOfFirst { it.page >= next }
                                        if (idx >= 0) scope.launch { listState.animateScrollToItem(idx) }
                                    }
                                },
                                enabled = currentPage < book!!.pages
                            ) {
                                Icon(Icons.AutoMirrored.Filled.ArrowForward, "다음 쪽", tint = themeColors.text)
                            }
                        }

                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 8.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            val percent = if (book!!.pages > 0) (currentPage * 100) / book!!.pages else 0
                            Text(
                                text = "P. $currentPage / ${book!!.pages} ($percent%)",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Medium,
                                color = themeColors.text.copy(alpha = 0.8f)
                            )

                            if (book!!.status == "PROCESSING") {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(12.dp),
                                        strokeWidth = 2.dp,
                                        color = themeColors.accent
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        "OCR ${book!!.done}/${book!!.pages}",
                                        fontSize = 11.sp,
                                        color = themeColors.accent,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Modal Sheets & Dialogs
    if (showSettingsSheet) {
        ReaderSettingsSheet(
            settings = settings,
            onSettingsChanged = { viewModel.updateSettings(it) },
            onRebuildParagraphs = { viewModel.rebuildParagraphs() },
            onDismiss = { showSettingsSheet = false }
        )
    }

    if (showSearchDialog) {
        SearchInBookDialog(
            onSearch = { query -> viewModel.searchInBook(query) },
            onSelectParagraph = { p ->
                viewModel.setCurrentPage(p.page)
                val idx = paragraphs.indexOfFirst { it.id == p.id }
                if (idx >= 0) scope.launch { listState.scrollToItem(idx) }
            },
            onDismiss = { showSearchDialog = false }
        )
    }

    if (showTocDialog) {
        var contents by remember { mutableStateOf<List<Paragraph>>(emptyList()) }
        LaunchedEffect(Unit) {
            contents = viewModel.getContents()
        }
        TocAndBookmarksDialog(
            contents = contents,
            bookmarks = bookmarks,
            onSelectPage = { pageNum ->
                viewModel.setCurrentPage(pageNum)
                val idx = paragraphs.indexOfFirst { it.page >= pageNum }
                if (idx >= 0) scope.launch { listState.scrollToItem(idx) }
            },
            onSelectParagraph = { target ->
                viewModel.setCurrentPage(target.page)
                val idx = paragraphs.indexOfFirst { it.id == target.id }
                if (idx >= 0) {
                    scope.launch { listState.scrollToItem(idx) }
                } else {
                    val pageIdx = paragraphs.indexOfFirst { it.page >= target.page }
                    if (pageIdx >= 0) scope.launch { listState.scrollToItem(pageIdx) }
                }
            },
            onDeleteBookmark = { viewModel.deleteBookmark(it) },
            onDismiss = { showTocDialog = false }
        )
    }

    selectedParagraphForMenu?.let { p ->
        ParagraphActionSheet(
            paragraph = p,
            onViewOriginal = if (viewModel.hasPdf()) {
                { viewModel.viewOriginalParagraph(p.page, p.left, p.top, p.right, p.bottom) }
            } else null,
            onCopy = {
                val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                clipboard.setPrimaryClip(ClipData.newPlainText("OCR 텍스트", p.text))
                Toast.makeText(context, "텍스트가 클립보드에 복사되었습니다.", Toast.LENGTH_SHORT).show()
            },
            onAddBookmark = { bookmarkingPage = p.page },
            onEdit = { editingParagraph = p },
            onSearch = { showSearchDialog = true },
            onDismiss = { selectedParagraphForMenu = null }
        )
    }

    editingParagraph?.let { p ->
        ParagraphEditDialog(
            paragraph = p,
            onSave = { newText -> viewModel.editParagraph(p.id, newText) },
            onDismiss = { editingParagraph = null }
        )
    }

    bookmarkingPage?.let { page ->
        AddBookmarkDialog(
            page = page,
            onSave = { memo -> viewModel.addBookmark(page, 0, memo) },
            onDismiss = { bookmarkingPage = null }
        )
    }

    // Fullscreen Image Zoom Dialog
    if (viewingImageBitmap != null) {
        Dialog(onDismissRequest = { viewingImageBitmap = null }) {
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surface,
                shadowElevation = 8.dp,
                modifier = Modifier
                    .fillMaxWidth(0.98f)
                    .wrapContentHeight()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = viewingImageCaption.ifBlank { "이미지 원본 보기" },
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurface,
                            maxLines = 1,
                            modifier = Modifier.weight(1f)
                        )
                        IconButton(onClick = { viewingImageBitmap = null }) {
                            Icon(Icons.Default.Close, contentDescription = "닫기")
                        }
                    }
                    Spacer(modifier = Modifier.height(8.dp))

                    var scale by remember { mutableStateOf(1f) }
                    var offsetX by remember { mutableStateOf(0f) }
                    var offsetY by remember { mutableStateOf(0f) }

                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 500.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(Color.White)
                            .pointerInput(Unit) {
                                detectTransformGestures { _, pan, zoom, _ ->
                                    scale = (scale * zoom).coerceIn(1f, 4f)
                                    if (scale > 1f) {
                                        offsetX += pan.x
                                        offsetY += pan.y
                                    } else {
                                        offsetX = 0f
                                        offsetY = 0f
                                    }
                                }
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Image(
                            bitmap = viewingImageBitmap!!.asImageBitmap(),
                            contentDescription = viewingImageCaption,
                            modifier = Modifier
                                .fillMaxSize()
                                .graphicsLayer(
                                    scaleX = scale,
                                    scaleY = scale,
                                    translationX = offsetX,
                                    translationY = offsetY
                                ),
                            contentScale = ContentScale.Fit
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun InlineImageView(
    text: String,
    bookId: String,
    themeColors: ReaderColors,
    fontSizeSp: Float,
    onImageClick: (Bitmap, String) -> Unit,
    onLongClick: () -> Unit
) {
    val context = LocalContext.current
    var imgPath = ""
    var caption = ""

    if (text.startsWith("[IMAGE:") && text.endsWith("]")) {
        val inner = text.removePrefix("[IMAGE:").removeSuffix("]")
        val parts = inner.split("|", limit = 2)
        imgPath = parts[0].trim()
        caption = if (parts.size > 1) parts[1].trim() else ""
    } else if (text.startsWith("![") && text.contains("](") && text.endsWith(")")) {
        val m = Regex("!\\[(.*?)\\]\\((.*?)\\)").find(text)
        if (m != null) {
            caption = m.groupValues[1].trim()
            imgPath = m.groupValues[2].trim()
        }
    } else {
        val parts = text.split("|", limit = 2)
        imgPath = parts[0].trim()
        caption = if (parts.size > 1) parts[1].trim() else ""
    }

    val bitmap = remember(imgPath, bookId) {
        val candidates = listOf(
            File(context.filesDir, imgPath),
            File(context.filesDir, "images/$imgPath"),
            File(context.filesDir, "$bookId/$imgPath"),
            File(context.filesDir, "book_images/$imgPath"),
            File(imgPath)
        )
        val f = candidates.firstOrNull { it.exists() && it.isFile }
        if (f != null) {
            try {
                BitmapFactory.decodeFile(f.absolutePath)
            } catch (_: Exception) {
                null
            }
        } else {
            null
        }
    }

    if (bitmap != null) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 10.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Surface(
                shape = RoundedCornerShape(10.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, themeColors.divider),
                shadowElevation = 2.dp,
                color = Color.White,
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .combinedClickable(
                        onLongClick = onLongClick,
                        onClick = { onImageClick(bitmap, caption) }
                    )
            ) {
                Image(
                    bitmap = bitmap.asImageBitmap(),
                    contentDescription = caption,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(6.dp),
                    contentScale = ContentScale.FillWidth
                )
            }
            if (caption.isNotBlank()) {
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = caption,
                    fontSize = (fontSizeSp * 0.82f).sp,
                    color = themeColors.text.copy(alpha = 0.75f),
                    fontWeight = FontWeight.Medium,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 12.dp)
                )
            }
        }
    } else {
        // Fallback placeholder
        Surface(
            color = themeColors.text.copy(alpha = 0.04f),
            shape = RoundedCornerShape(8.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, themeColors.divider),
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp)
                .combinedClickable(
                    onLongClick = onLongClick,
                    onClick = {}
                )
        ) {
            Row(
                modifier = Modifier.padding(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Default.Image,
                    contentDescription = null,
                    tint = themeColors.text.copy(alpha = 0.5f),
                    modifier = Modifier.size(24.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = if (caption.isNotBlank()) caption else "🖼️ $imgPath",
                    fontSize = (fontSizeSp * 0.85f).sp,
                    color = themeColors.text.copy(alpha = 0.7f),
                    maxLines = 2
                )
            }
        }
    }
}

// Extension helper for combined clickable
@Composable
private fun Modifier.combinedClickable(
    onLongClick: () -> Unit,
    onClick: () -> Unit
): Modifier = this.pointerInput(Unit) {
    detectTapGestures(
        onLongPress = { onLongClick() },
        onTap = { onClick() }
    )
}


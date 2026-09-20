package com.ebook.ocrreader.ui

import android.graphics.Bitmap
import android.graphics.Rect
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ebook.ocrreader.Book
import com.ebook.ocrreader.Page

@Composable
fun OriginalPageView(
    book: Book,
    currentPage: Int,
    pageInfo: Page?,
    bitmap: Bitmap?,
    isRendering: Boolean,
    highlightBox: Rect?,
    onPageChange: (Int) -> Unit,
    onRotatePage: () -> Unit,
    onRetryOcr: () -> Unit,
    onClearHighlight: () -> Unit,
    onSwitchToReflow: () -> Unit,
    modifier: Modifier = Modifier
) {
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    var containerSize by remember { mutableStateOf(IntSize.Zero) }

    // Reset zoom when page changes
    LaunchedEffect(currentPage) {
        scale = 1f
        offset = Offset.Zero
    }

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Color(0xFF1E1E1E))
            .onSizeChanged { containerSize = it }
    ) {
        if (bitmap != null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clipToBounds()
                    .pointerInput(Unit) {
                        detectTapGestures(
                            onDoubleTap = {
                                if (scale > 1.2f) {
                                    scale = 1f
                                    offset = Offset.Zero
                                } else {
                                    scale = 2.5f
                                }
                            }
                        )
                    }
                    .pointerInput(Unit) {
                        detectTransformGestures { _, pan, zoom, _ ->
                            scale = (scale * zoom).coerceIn(1f, 5f)
                            if (scale == 1f) {
                                offset = Offset.Zero
                            } else {
                                val maxOffsetX = (containerSize.width * (scale - 1)) / 2f
                                val maxOffsetY = (containerSize.height * (scale - 1)) / 2f
                                offset = Offset(
                                    x = (offset.x + pan.x).coerceIn(-maxOffsetX, maxOffsetX),
                                    y = (offset.y + pan.y).coerceIn(-maxOffsetY, maxOffsetY)
                                )
                            }
                        }
                    },
                contentAlignment = Alignment.Center
            ) {
                Box(
                    modifier = Modifier
                        .graphicsLayer(
                            scaleX = scale,
                            scaleY = scale,
                            translationX = offset.x,
                            translationY = offset.y
                        )
                ) {
                    Image(
                        bitmap = bitmap.asImageBitmap(),
                        contentDescription = "PDF $currentPage 페이지 원본",
                        contentScale = ContentScale.Fit,
                        modifier = Modifier.fillMaxSize()
                    )

                    // Draw highlight bounding box if provided
                    if (highlightBox != null && bitmap.width > 0 && bitmap.height > 0) {
                        Canvas(modifier = Modifier.fillMaxSize()) {
                            val imgWidth = bitmap.width.toFloat()
                            val imgHeight = bitmap.height.toFloat()

                            // Calculate aspect fit drawn rect in Canvas
                            val scaleFit = minOf(size.width / imgWidth, size.height / imgHeight)
                            val drawnWidth = imgWidth * scaleFit
                            val drawnHeight = imgHeight * scaleFit
                            val startX = (size.width - drawnWidth) / 2f
                            val startY = (size.height - drawnHeight) / 2f

                            val boxLeft = startX + (highlightBox.left / imgWidth) * drawnWidth
                            val boxTop = startY + (highlightBox.top / imgHeight) * drawnHeight
                            val boxRight = startX + (highlightBox.right / imgWidth) * drawnWidth
                            val boxBottom = startY + (highlightBox.bottom / imgHeight) * drawnHeight

                            val rectSize = Size(boxRight - boxLeft, boxBottom - boxTop)
                            val topLeft = Offset(boxLeft, boxTop)

                            // Semi-transparent fill
                            drawRect(
                                color = Color(0x55FFEB3B),
                                topLeft = topLeft,
                                size = rectSize
                            )
                            // Bright border
                            drawRect(
                                color = Color(0xFFFF9800),
                                topLeft = topLeft,
                                size = rectSize,
                                style = Stroke(width = 3.dp.toPx())
                            )
                        }
                    }
                }
            }
        }

        if (isRendering) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color(0x88000000)),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = Color.White)
            }
        }

        // Top Overlay: Highlight Banner & Rotate button
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .align(Alignment.TopCenter)
                .padding(top = 8.dp, start = 16.dp, end = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            if (highlightBox != null) {
                Surface(
                    color = Color(0xEEFF9800),
                    shape = RoundedCornerShape(20.dp),
                    modifier = Modifier.align(Alignment.CenterHorizontally)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.FindInPage, null, tint = Color.Black, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            "선택한 문단 영역 강조 중",
                            color = Color.Black,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        IconButton(
                            onClick = onClearHighlight,
                            modifier = Modifier.size(20.dp)
                        ) {
                            Icon(Icons.Default.Close, "강조 해제", tint = Color.Black, modifier = Modifier.size(16.dp))
                        }
                    }
                }
            }

            // Page status & rotate action bar
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Surface(
                    color = Color(0xCC000000),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "P. $currentPage / ${book.pages}",
                            color = Color.White,
                            fontWeight = FontWeight.Bold,
                            fontSize = 13.sp
                        )
                        if (pageInfo?.rotation != 0) {
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                "(${pageInfo?.rotation}° 회전됨)",
                                color = Color(0xFF60A5FA),
                                fontSize = 11.sp
                            )
                        }
                    }
                }

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilledTonalIconButton(
                        onClick = onRotatePage,
                        colors = IconButtonDefaults.filledTonalIconButtonColors(
                            containerColor = Color(0xCC333333),
                            contentColor = Color.White
                        )
                    ) {
                        Icon(Icons.Default.RotateRight, "90도 회전")
                    }

                    if (pageInfo?.status == "ERROR") {
                        FilledTonalIconButton(
                            onClick = onRetryOcr,
                            colors = IconButtonDefaults.filledTonalIconButtonColors(
                                containerColor = Color(0xCCEF4444),
                                contentColor = Color.White
                            )
                        ) {
                            Icon(Icons.Default.Refresh, "OCR 다시 시도")
                        }
                    }

                    Button(
                        onClick = onSwitchToReflow,
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary),
                        shape = RoundedCornerShape(18.dp),
                        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 6.dp)
                    ) {
                        Icon(Icons.Default.MenuBook, null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("텍스트 읽기", fontSize = 12.sp)
                    }
                }
            }
        }

        // Bottom Controls: Page Navigation
        Surface(
            color = Color(0xDD121212),
            shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp),
            modifier = Modifier
                .fillMaxWidth()
                .align(Alignment.BottomCenter)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(
                        onClick = { if (currentPage > 1) onPageChange(currentPage - 1) },
                        enabled = currentPage > 1
                    ) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "이전 페이지", tint = Color.White)
                    }

                    Slider(
                        value = currentPage.toFloat(),
                        onValueChange = { onPageChange(it.toInt().coerceIn(1, book.pages)) },
                        valueRange = 1f..book.pages.toFloat(),
                        modifier = Modifier.weight(1f)
                    )

                    IconButton(
                        onClick = { if (currentPage < book.pages) onPageChange(currentPage + 1) },
                        enabled = currentPage < book.pages
                    ) {
                        Icon(Icons.AutoMirrored.Filled.ArrowForward, "다음 페이지", tint = Color.White)
                    }
                }
            }
        }
    }
}

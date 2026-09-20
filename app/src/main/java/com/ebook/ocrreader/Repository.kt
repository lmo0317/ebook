package com.ebook.ocrreader

import android.app.Application
import android.content.Context
import android.content.Intent
import android.graphics.*
import android.graphics.pdf.PdfRenderer
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import androidx.core.content.FileProvider
import androidx.room.Room
import androidx.room.withTransaction
import androidx.work.*
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import java.io.File
import java.security.MessageDigest
import java.util.UUID
import java.util.zip.ZipFile
import android.database.sqlite.SQLiteDatabase
import org.json.JSONObject

class ReaderApp : Application() {
    val db by lazy {
        Room.databaseBuilder(this, ReaderDatabase::class.java, "reader.db")
            .fallbackToDestructiveMigration()
            .build()
    }
    val repo by lazy { ReaderRepository(this, db) }
}

interface OcrEngine {
    suspend fun recognize(bitmap: Bitmap, language: String): OcrPageResult
}

class MlKitEngine : OcrEngine {
    override suspend fun recognize(bitmap: Bitmap, language: String): OcrPageResult {
        val client = if (language == "영어") {
            TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        } else {
            TextRecognition.getClient(KoreanTextRecognizerOptions.Builder().build())
        }
        try {
            val text = client.process(InputImage.fromBitmap(bitmap, 0)).await()
            return OcrPageResult(
                width = bitmap.width,
                height = bitmap.height,
                blocks = text.textBlocks.mapNotNull { block ->
                    block.boundingBox?.let { box ->
                        OcrBlock(
                            text = block.text,
                            left = box.left,
                            top = box.top,
                            right = box.right,
                            bottom = box.bottom,
                            lines = block.lines.mapNotNull { line ->
                                line.boundingBox?.let {
                                    OcrLine(line.text, it.left, it.top, it.right, it.bottom)
                                }
                            }
                        )
                    }
                }
            )
        } finally {
            client.close()
        }
    }
}

class ReaderRepository(val context: Context, val db: ReaderDatabase) {
    val dao = db.dao()
    val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    fun pdf(id: String) = File(context.filesDir, "$id.pdf")
    fun txt(id: String) = File(context.filesDir, "$id.txt")
    fun cover(id: String) = File(context.filesDir, "$id.jpg")

    suspend fun import(uri: Uri): Book = withContext(Dispatchers.IO) {
        runCatching {
            context.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION
            )
        }
        var name = "문서.pdf"
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use {
            if (it.moveToFirst()) name = it.getString(0) ?: name
        }
        val id = UUID.randomUUID().toString()

        val mimeType = context.contentResolver.getType(uri)
        val isTxt = name.endsWith(".txt", ignoreCase = true) || mimeType == "text/plain"
        if (isTxt) {
            return@withContext importTxt(uri, name, id)
        }

        val isZip = name.endsWith(".zip", ignoreCase = true) ||
                mimeType == "application/zip" ||
                mimeType == "application/x-zip-compressed" ||
                mimeType == "application/octet-stream"
        if (isZip) {
            return@withContext importZip(uri, name, id)
        }

        val file = pdf(id)
        try {
            val digest = MessageDigest.getInstance("SHA-256")
            context.contentResolver.openInputStream(uri)?.use { input ->
                file.outputStream().use { output ->
                    val buffer = ByteArray(65536)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        digest.update(buffer, 0, count)
                        output.write(buffer, 0, count)
                    }
                }
            } ?: error("파일을 읽을 수 없습니다.")

            val hash = digest.digest().joinToString("") { "%02x".format(it) }
            val duplicate = dao.duplicate(hash)
            if (duplicate != null) {
                file.delete()
                return@withContext duplicate
            }

            val count = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY).use { descriptor ->
                PdfRenderer(descriptor).use { it.pageCount }
            }
            require(count > 0) { "빈 PDF 문서입니다." }

            val book = Book(
                id = id,
                title = name.removeSuffix(".pdf"),
                uri = uri.toString(),
                fileName = name,
                size = file.length(),
                hash = hash,
                pages = count
            )

            // Render cover thumbnail
            val image = render(id, 1, 400, 0)
            try {
                cover(id).outputStream().use {
                    image.compress(Bitmap.CompressFormat.JPEG, 85, it)
                }
            } finally {
                image.recycle()
            }

            db.withTransaction {
                dao.insert(book)
                for (number in 1..count) {
                    dao.page(Page(id, number))
                }
            }

            enqueue(id)
            book
        } catch (e: Exception) {
            file.delete()
            cover(id).delete()
            throw e
        }
    }

    private suspend fun importTxt(uri: Uri, name: String, id: String): Book = withContext(Dispatchers.IO) {
        val file = txt(id)
        try {
            val digest = MessageDigest.getInstance("SHA-256")
            val byteStream = java.io.ByteArrayOutputStream()
            context.contentResolver.openInputStream(uri)?.use { input ->
                file.outputStream().use { output ->
                    val buffer = ByteArray(65536)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        digest.update(buffer, 0, count)
                        output.write(buffer, 0, count)
                        byteStream.write(buffer, 0, count)
                    }
                }
            } ?: error("파일을 읽을 수 없습니다.")

            val bytes = byteStream.toByteArray()
            val hash = digest.digest().joinToString("") { "%02x".format(it) }
            val duplicate = dao.duplicate(hash)
            if (duplicate != null) {
                file.delete()
                return@withContext duplicate
            }

            // Decode UTF-8 or fallback to MS949
            var text = try {
                String(bytes, Charsets.UTF_8)
            } catch (_: Exception) {
                String(bytes, java.nio.charset.Charset.forName("MS949"))
            }
            if (text.count { it == '\uFFFD' } > 5) {
                try {
                    val alt = String(bytes, java.nio.charset.Charset.forName("MS949"))
                    if (alt.count { it == '\uFFFD' } < text.count { it == '\uFFFD' }) {
                        text = alt
                    }
                } catch (_: Exception) {}
            }

            // Extract title
            var title = name.removeSuffix(".txt").removeSuffix(".TXT")
            val titleMatch = Regex("(?m)^도서명\\s*:\\s*(.+)$").find(text)
            if (titleMatch != null) {
                val extracted = titleMatch.groupValues[1].trim()
                if (extracted.isNotBlank()) title = extracted
            }

            data class ParsedPara(val page: Int, val text: String, val type: String)
            val parsedList = mutableListOf<ParsedPara>()

            fun determineType(raw: String): String {
                val t = raw.trim()
                return when {
                    t.startsWith("[IMAGE:") || (t.startsWith("![") && t.contains("](")) -> "IMAGE"
                    t.startsWith("```") -> "CODE"
                    t.startsWith("### ") || isHeadingPattern(t) -> "TITLE"
                    else -> "BODY"
                }
            }

            fun cleanText(raw: String, type: String): String {
                val t = raw.trim()
                return when (type) {
                    "TITLE" -> t.replace(Regex("^#+\\s*"), "").trim()
                    else -> t
                }
            }

            val pageMarkerRegex = Regex("(?m)^\\[Page\\s+(\\d+)\\]\\s*$")
            val hasPageMarkers = pageMarkerRegex.containsMatchIn(text)

            if (hasPageMarkers) {
                val parts = text.split(Regex("(?m)^\\[Page\\s+\\d+\\]\\s*$"))
                val matches = pageMarkerRegex.findAll(text).toList()

                if (parts.isNotEmpty()) {
                    val headerParas = parts[0].split(Regex("\n\\s*\n"))
                        .map { it.trim() }
                        .filter { it.isNotBlank() && !it.startsWith("도서명:") && !it.startsWith("====") }
                    for (p in headerParas) {
                        val pType = determineType(p)
                        val clean = cleanText(p, pType)
                        if (clean.isNotBlank()) parsedList.add(ParsedPara(1, clean, pType))
                    }
                }

                for (i in matches.indices) {
                    val pageNum = matches[i].groupValues[1].toIntOrNull() ?: (i + 1)
                    val partIdx = i + 1
                    if (partIdx < parts.size) {
                        val pageContent = parts[partIdx]
                        val paras = pageContent.split(Regex("\n\\s*\n"))
                            .map { it.trim() }
                            .filter { it.isNotBlank() }
                        for (p in paras) {
                            val pType = determineType(p)
                            val clean = cleanText(p, pType)
                            if (clean.isNotBlank()) parsedList.add(ParsedPara(pageNum, clean, pType))
                        }
                    }
                }
            } else {
                val paras = text.split(Regex("\n\\s*\n"))
                    .map { it.trim() }
                    .filter { it.isNotBlank() && !it.startsWith("도서명:") && !it.startsWith("====") }

                var currPage = 1
                var countOnPage = 0
                for (p in paras) {
                    val pType = determineType(p)
                    val clean = cleanText(p, pType)
                    if (clean.isNotBlank()) {
                        if ((countOnPage >= 10 && pType == "TITLE") || countOnPage >= 15) {
                            currPage++
                            countOnPage = 0
                        }
                        parsedList.add(ParsedPara(currPage, clean, pType))
                        countOnPage++
                    }
                }
            }

            require(parsedList.isNotEmpty()) { "내용이 비어있는 텍스트 문서입니다." }

            val totalPages = (parsedList.maxOfOrNull { it.page } ?: 1).coerceAtLeast(1)

            // Generate styled cover
            val coverImage = generateTxtCover(title)
            try {
                cover(id).outputStream().use {
                    coverImage.compress(Bitmap.CompressFormat.JPEG, 90, it)
                }
            } finally {
                coverImage.recycle()
            }

            val book = Book(
                id = id,
                title = title,
                uri = uri.toString(),
                fileName = name,
                size = file.length(),
                hash = hash,
                pages = totalPages,
                status = "READY",
                done = totalPages
            )

            db.withTransaction {
                dao.insert(book)
                for (pNum in 1..totalPages) {
                    dao.page(Page(bookId = id, number = pNum, width = 1000, height = 1500, status = "COMPLETED"))
                }
                val paragraphsToInsert = parsedList.mapIndexed { index, p ->
                    Paragraph(
                        bookId = id,
                        page = p.page,
                        order = index + 1,
                        original = p.text,
                        type = p.type,
                        region = "BODY",
                        left = 50,
                        top = 50,
                        right = 950,
                        bottom = 1450
                    )
                }
                paragraphsToInsert.chunked(200).forEach { batch ->
                    dao.paragraphs(batch)
                }
            }

            book
        } catch (e: Exception) {
            file.delete()
            cover(id).delete()
            throw e
        }
    }

    private suspend fun importZip(uri: Uri, name: String, id: String): Book = withContext(Dispatchers.IO) {
        val tempDir = File(context.cacheDir, "import_zip_$id")
        tempDir.deleteRecursively()
        tempDir.mkdirs()

        val digest = MessageDigest.getInstance("SHA-256")
        var zipSize = 0L

        try {
            // 1. Save zip to temporary file and compute hash
            val zipFile = File(tempDir, "archive.zip")
            context.contentResolver.openInputStream(uri)?.use { rawInput ->
                val buffer = ByteArray(65536)
                zipFile.outputStream().use { zipOut ->
                    while (true) {
                        val count = rawInput.read(buffer)
                        if (count < 0) break
                        digest.update(buffer, 0, count)
                        zipOut.write(buffer, 0, count)
                        zipSize += count
                    }
                }
            } ?: error("ZIP 파일을 열 수 없습니다.")

            val hash = digest.digest().joinToString("") { "%02x".format(it) }
            val duplicate = dao.duplicate(hash)
            if (duplicate != null) {
                tempDir.deleteRecursively()
                return@withContext duplicate
            }

            // 2. Extract all entries
            ZipFile(zipFile).use { zf ->
                val entries = zf.entries()
                while (entries.hasMoreElements()) {
                    val entry = entries.nextElement()
                    val destFile = File(tempDir, entry.name)
                    if (entry.isDirectory) {
                        destFile.mkdirs()
                    } else {
                        destFile.parentFile?.mkdirs()
                        zf.getInputStream(entry).use { entryIn ->
                            destFile.outputStream().use { entryOut ->
                                entryIn.copyTo(entryOut)
                            }
                        }
                    }
                }
            }

            // 3. Parse manifest.json if present
            var bookTitle = name.removeSuffix(".zip").removeSuffix(".ZIP")
            var bookAuthor = ""
            var bookPages = 1
            var bookMemo = "패키지 전자책"

            val manifestFile = File(tempDir, "manifest.json")
            if (manifestFile.exists()) {
                try {
                    val json = JSONObject(manifestFile.readText(Charsets.UTF_8))
                    if (json.has("title")) bookTitle = json.getString("title")
                    if (json.has("author")) bookAuthor = json.getString("author")
                    if (json.has("pages")) bookPages = json.getInt("pages")
                    if (json.has("figuresCount")) {
                        bookMemo = "고화질 도표 ${json.getInt("figuresCount")}개 수록 하이브리드 전자책"
                    }
                } catch (_: Exception) {}
            }

            // 4. Copy images to context.filesDir/images
            val imagesDir = File(tempDir, "images")
            val targetImagesDir = File(context.filesDir, "images")
            targetImagesDir.mkdirs()
            if (imagesDir.exists() && imagesDir.isDirectory) {
                imagesDir.listFiles()?.forEach { imgFile ->
                    if (imgFile.isFile) {
                        val dest = File(targetImagesDir, imgFile.name)
                        imgFile.copyTo(dest, overwrite = true)
                    }
                }
            }

            // 5. Copy cover and book.txt
            val coverFile = File(tempDir, "cover.jpg").takeIf { it.exists() }
                ?: tempDir.listFiles()?.firstOrNull { it.name.endsWith(".jpg") || it.name.endsWith(".png") }
            if (coverFile != null) {
                coverFile.copyTo(cover(id), overwrite = true)
            }

            val txtFile = File(tempDir, "book.txt").takeIf { it.exists() }
                ?: tempDir.listFiles()?.firstOrNull { it.name.endsWith(".txt") }
            if (txtFile != null) {
                txtFile.copyTo(txt(id), overwrite = true)
            }

            // 6. Import database records from embedded reader.db
            val embeddedDbFile = File(tempDir, "reader.db")
            val hasEmbeddedDb = embeddedDbFile.exists() && embeddedDbFile.length() > 0

            val book = Book(
                id = id,
                title = bookTitle,
                uri = uri.toString(),
                fileName = name,
                size = zipSize,
                hash = hash,
                pages = bookPages,
                status = "COMPLETED",
                done = bookPages,
                author = bookAuthor,
                memo = bookMemo
            )

            if (hasEmbeddedDb) {
                val sqlite = SQLiteDatabase.openDatabase(
                    embeddedDbFile.absolutePath,
                    null,
                    SQLiteDatabase.OPEN_READONLY
                )
                try {
                    val pageList = mutableListOf<Page>()
                    val paraList = mutableListOf<Paragraph>()

                    // Read Pages
                    try {
                        val pageCursor = sqlite.rawQuery("SELECT number, width, height FROM Page", null)
                        pageCursor.use { cursor ->
                            val numIdx = cursor.getColumnIndex("number")
                            val wIdx = cursor.getColumnIndex("width")
                            val hIdx = cursor.getColumnIndex("height")
                            while (cursor.moveToNext()) {
                                val num = cursor.getInt(numIdx)
                                val w = if (wIdx >= 0) cursor.getInt(wIdx) else 1000
                                val h = if (hIdx >= 0) cursor.getInt(hIdx) else 1500
                                pageList.add(Page(id, num, w, h, 0, "COMPLETED", ""))
                            }
                        }
                    } catch (_: Exception) {}

                    // Read Paragraphs
                    try {
                        val paraCursor = sqlite.rawQuery(
                            "SELECT page, `order`, original, edited, left, top, right, bottom, type, region FROM Paragraph ORDER BY page, `order`",
                            null
                        )
                        paraCursor.use { cursor ->
                            val pageIdx = cursor.getColumnIndex("page")
                            val orderIdx = cursor.getColumnIndex("order")
                            val origIdx = cursor.getColumnIndex("original")
                            val editIdx = cursor.getColumnIndex("edited")
                            val leftIdx = cursor.getColumnIndex("left")
                            val topIdx = cursor.getColumnIndex("top")
                            val rightIdx = cursor.getColumnIndex("right")
                            val bottomIdx = cursor.getColumnIndex("bottom")
                            val typeIdx = cursor.getColumnIndex("type")
                            val regIdx = cursor.getColumnIndex("region")

                            while (cursor.moveToNext()) {
                                paraList.add(Paragraph(
                                    id = 0,
                                    bookId = id,
                                    page = cursor.getInt(pageIdx),
                                    order = cursor.getInt(orderIdx),
                                    original = cursor.getString(origIdx) ?: "",
                                    edited = if (editIdx >= 0) cursor.getString(editIdx) else null,
                                    left = cursor.getInt(leftIdx),
                                    top = cursor.getInt(topIdx),
                                    right = cursor.getInt(rightIdx),
                                    bottom = cursor.getInt(bottomIdx),
                                    type = cursor.getString(typeIdx) ?: "BODY",
                                    region = if (regIdx >= 0) cursor.getString(regIdx) ?: "CONTENT" else "CONTENT"
                                ))
                            }
                        }
                    } catch (_: Exception) {}

                    val actualPages = if (pageList.isNotEmpty()) pageList.maxOf { it.number } else bookPages
                    val finalBook = book.copy(pages = actualPages, done = actualPages)

                    db.withTransaction {
                        dao.insert(finalBook)
                        if (pageList.isEmpty()) {
                            for (p in 1..actualPages) dao.page(Page(id, p, 1000, 1500, 0, "COMPLETED", ""))
                        } else {
                            pageList.forEach { dao.page(it) }
                        }
                        if (paraList.isNotEmpty()) {
                            paraList.chunked(200).forEach { batch ->
                                dao.paragraphs(batch)
                            }
                        }
                    }
                    finalBook
                } finally {
                    sqlite.close()
                }
            } else {
                db.withTransaction {
                    dao.insert(book)
                    for (p in 1..bookPages) {
                        dao.page(Page(id, p, 1000, 1500, 0, "COMPLETED", ""))
                    }
                }
                book
            }
        } finally {
            tempDir.deleteRecursively()
        }
    }

    private fun isHeadingPattern(text: String): Boolean {
        if (text.length > 65) return false
        if (Regex("(습니다|입니다|했다|였다|있다|다|냐|까|요|죠|됨)\\s*[.?!]*$").containsMatchIn(text)) {
            if (!Regex("^(제\\s*\\d+\\s*[장절편부]|Chapter|CHAPTER|PART|Part|TIP|Tip)").containsMatchIn(text)) {
                return false
            }
        }
        if (Regex("^\\d+[\\.\\)]\\s+").containsMatchIn(text)) {
            if (':' in text || text.length > 35) return false
        }
        return Regex("^(제\\s*\\d+\\s*[장절편부]|\\d+\\.\\d+(\\.\\d+)?|\\d{1,2}_|Chapter|CHAPTER|PART|Part|TIP|Tip)").containsMatchIn(text)
    }

    private fun generateTxtCover(title: String): Bitmap {
        val width = 400
        val height = 600
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)

        val bgPaint = Paint().apply {
            shader = LinearGradient(
                0f, 0f, 0f, height.toFloat(),
                Color.parseColor("#1E293B"), Color.parseColor("#0F172A"),
                Shader.TileMode.CLAMP
            )
        }
        canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), bgPaint)

        val borderPaint = Paint().apply {
            color = Color.parseColor("#334155")
            style = Paint.Style.STROKE
            strokeWidth = 3f
        }
        canvas.drawRect(20f, 20f, width - 20f, height - 20f, borderPaint)

        val badgePaint = Paint().apply {
            color = Color.parseColor("#38BDF8")
            textSize = 20f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
        }
        canvas.drawText("TXT e-Book", width / 2f, 90f, badgePaint)

        val titlePaint = Paint().apply {
            color = Color.WHITE
            textSize = 26f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
        }

        val lines = mutableListOf<String>()
        val words = title.split(" ")
        var currentLine = StringBuilder()
        for (w in words) {
            if (currentLine.isNotEmpty() && titlePaint.measureText("$currentLine $w") > width - 70) {
                lines.add(currentLine.toString())
                currentLine = StringBuilder(w)
            } else {
                if (currentLine.isNotEmpty()) currentLine.append(" ")
                currentLine.append(w)
            }
        }
        if (currentLine.isNotEmpty()) lines.add(currentLine.toString())

        val startY = (height / 2f) - ((lines.size - 1) * 36f) / 2f
        lines.forEachIndexed { i, line ->
            canvas.drawText(line, width / 2f, startY + (i * 38f), titlePaint)
        }

        return bitmap
    }

    suspend fun render(id: String, number: Int, longSide: Int, rotation: Int): Bitmap = withContext(Dispatchers.IO) {
        val file = pdf(id)
        if (!file.exists() && txt(id).exists()) {
            return@withContext Bitmap.createBitmap(longSide, (longSide * 1.4f).toInt(), Bitmap.Config.ARGB_8888).apply {
                eraseColor(Color.WHITE)
            }
        }
        require(file.exists()) { "PDF 파일을 찾을 수 없습니다." }
        ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY).use { descriptor ->
            PdfRenderer(descriptor).use { renderer ->
                renderer.openPage(number - 1).use { page ->
                    val scale = longSide.toFloat() / maxOf(page.width, page.height)
                    val targetWidth = (page.width * scale).toInt().coerceAtLeast(1)
                    val targetHeight = (page.height * scale).toInt().coerceAtLeast(1)
                    val bitmap = Bitmap.createBitmap(targetWidth, targetHeight, Bitmap.Config.ARGB_8888)
                    try {
                        bitmap.eraseColor(Color.WHITE)
                        page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_PRINT)
                        if (rotation == 0) {
                            bitmap
                        } else {
                            val matrix = Matrix().apply { postRotate(rotation.toFloat()) }
                            val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
                            if (rotated !== bitmap) bitmap.recycle()
                            rotated
                        }
                    } catch (e: Throwable) {
                        bitmap.recycle()
                        throw e
                    }
                }
            }
        }
    }

    fun enqueue(id: String) {
        val requiresCharging = prefs.getBoolean("charging", false)
        val constraints = Constraints.Builder()
            .setRequiresCharging(requiresCharging)
            .build()
        val request = OneTimeWorkRequestBuilder<OcrWorker>()
            .setInputData(workDataOf("book" to id))
            .setConstraints(constraints)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("ocr-$id", ExistingWorkPolicy.KEEP, request)
    }

    suspend fun pause(id: String) {
        val book = dao.book(id) ?: return
        dao.update(book.copy(status = "PAUSED"))
        WorkManager.getInstance(context).cancelUniqueWork("ocr-$id")
    }

    suspend fun resume(id: String, retry: Boolean = false) {
        val book = dao.book(id) ?: return
        if (retry) {
            for (number in 1..book.pages) {
                val page = dao.page(id, number) ?: continue
                if (page.status == "ERROR") {
                    dao.page(page.copy(status = "NOT_STARTED", error = ""))
                }
            }
        }
        dao.update(book.copy(status = "PROCESSING", error = ""))
        enqueue(id)
    }

    suspend fun retryPage(id: String, number: Int) {
        val page = dao.page(id, number) ?: return
        dao.page(page.copy(status = "NOT_STARTED", error = ""))
        val book = dao.book(id) ?: return
        dao.update(book.copy(status = "PROCESSING", error = ""))
        enqueue(id)
    }

    suspend fun resetAllAndOcr(id: String) = withContext(Dispatchers.IO) {
        val book = dao.book(id) ?: return@withContext
        WorkManager.getInstance(context).cancelUniqueWork("ocr-$id")
        db.withTransaction {
            for (number in 1..book.pages) {
                dao.clearBlocks(id, number)
                dao.clearParagraphs(id, number)
                val existing = dao.page(id, number)
                if (existing != null) {
                    dao.page(existing.copy(status = "NOT_STARTED", error = ""))
                } else {
                    dao.page(Page(id, number))
                }
            }
            dao.update(book.copy(status = "PROCESSING", done = 0, error = ""))
        }
        enqueue(id)
    }

    suspend fun rotate(id: String, number: Int) {
        val page = dao.page(id, number) ?: return
        dao.page(page.copy(rotation = (page.rotation + 90) % 360, status = "NOT_STARTED"))
        resume(id)
    }

    suspend fun deleteBook(id: String) = withContext(Dispatchers.IO) {
        WorkManager.getInstance(context).cancelUniqueWork("ocr-$id")
        pdf(id).delete()
        txt(id).delete()
        cover(id).delete()
        db.withTransaction {
            dao.deleteBookmarks(id)
            dao.deletePosition(id)
            dao.deleteParagraphs(id)
            dao.deleteBlocks(id)
            dao.deletePages(id)
            dao.deleteBook(id)
        }
    }

    suspend fun updateBook(id: String, title: String, author: String, memo: String) = withContext(Dispatchers.IO) {
        val book = dao.book(id) ?: return@withContext
        dao.update(book.copy(title = title.trim(), author = author.trim(), memo = memo.trim()))
    }

    suspend fun markOpened(id: String) = withContext(Dispatchers.IO) {
        val book = dao.book(id) ?: return@withContext
        dao.update(book.copy(opened = System.currentTimeMillis()))
    }

    suspend fun savePosition(id: String, page: Int, paragraphId: Long, index: Int, offset: Int) = withContext(Dispatchers.IO) {
        dao.position(Position(bookId = id, page = page, paragraphId = paragraphId, index = index, offset = offset))
    }

    suspend fun addBookmark(id: String, page: Int, paragraphId: Long, memo: String) = withContext(Dispatchers.IO) {
        dao.bookmark(Bookmark(bookId = id, page = page, paragraphId = paragraphId, memo = memo.trim()))
    }

    suspend fun deleteBookmark(id: Long) = withContext(Dispatchers.IO) {
        dao.deleteBookmark(id)
    }

    suspend fun editParagraph(id: Long, text: String) = withContext(Dispatchers.IO) {
        dao.edit(id, text)
    }

    fun visible(p: Paragraph): Boolean {
        val hideNumbers = prefs.getBoolean("numbers", true)
        val hideHeaders = prefs.getBoolean("headers", true)
        val hideFooters = prefs.getBoolean("footers", true)
        return !((p.region == "NUMBER" && hideNumbers) ||
                (p.region == "HEADER" && hideHeaders) ||
                (p.region == "FOOTER" && hideFooters))
    }

    suspend fun rebuildParagraphs(bookId: String) = withContext(Dispatchers.IO) {
        val book = dao.book(bookId) ?: return@withContext
        val hasBlocks = dao.blocksForPage(bookId, 1).isNotEmpty()
        if (!hasBlocks && (!pdf(bookId).exists() || txt(bookId).exists())) {
            return@withContext
        }
        db.withTransaction {
            dao.deleteParagraphs(bookId)
            for (pageNum in 1..book.pages) {
                val page = dao.page(bookId, pageNum) ?: continue
                val blocks = dao.blocksForPage(bookId, pageNum)
                if (blocks.isEmpty()) continue

                val ocrBlocks = blocks.map { b ->
                    val linesList = mutableListOf<OcrLine>()
                    try {
                        val arr = org.json.JSONArray(b.linesJson)
                        for (i in 0 until arr.length()) {
                            val obj = arr.getJSONObject(i)
                            linesList.add(
                                OcrLine(
                                    text = obj.getString("text"),
                                    left = obj.getInt("left"),
                                    top = obj.getInt("top"),
                                    right = obj.getInt("right"),
                                    bottom = obj.getInt("bottom")
                                )
                            )
                        }
                    } catch (_: Exception) {}

                    OcrBlock(
                        text = b.text,
                        left = b.left,
                        top = b.top,
                        right = b.right,
                        bottom = b.bottom,
                        lines = linesList
                    )
                }

                val pageResult = OcrPageResult(
                    width = if (page.width > 0) page.width else 2000,
                    height = if (page.height > 0) page.height else 2800,
                    blocks = ocrBlocks
                )
                val newParagraphs = Layout.build(bookId, pageNum, pageResult)
                dao.paragraphs(newParagraphs)
            }
        }
    }

    suspend fun export(id: String, html: Boolean): String {
        val book = dao.book(id) ?: error("도서를 찾을 수 없습니다.")
        val paragraphs = dao.allParagraphs(id).filter(::visible)

        fun escape(s: String) = s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")

        return if (html) {
            """
            <!doctype html>
            <html lang="ko">
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>${escape(book.title)}</title>
                <style>
                    body { max-width: 680px; margin: 40px auto; padding: 0 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.8; color: #222; }
                    h1 { border-bottom: 2px solid #333; padding-bottom: 8px; margin-bottom: 24px; font-size: 1.8rem; }
                    h2 { margin-top: 32px; font-size: 1.3rem; color: #111; }
                    p { margin: 16px 0; text-align: justify; word-break: break-all; }
                </style>
            </head>
            <body>
                <h1>${escape(book.title)}</h1>
                ${if (book.author.isNotBlank()) "<p><strong>저자:</strong> ${escape(book.author)}</p>" else ""}
                ${paragraphs.joinToString("\n") { if (it.type == "TITLE") "<h2>${escape(it.text)}</h2>" else "<p>${escape(it.text)}</p>" }}
            </body>
            </html>
            """.trimIndent()
        } else {
            val header = buildString {
                appendLine(book.title)
                if (book.author.isNotBlank()) appendLine("저자: ${book.author}")
                appendLine("=".repeat(30))
                appendLine()
            }
            header + paragraphs.joinToString("\n\n") { it.text }
        }
    }

    suspend fun createExportFile(id: String, html: Boolean): File = withContext(Dispatchers.IO) {
        val book = dao.book(id) ?: error("도서 없음")
        val content = export(id, html)
        val ext = if (html) "html" else "txt"
        val safeTitle = book.title.replace(Regex("[^a-zA-Z0-9가-힣_-]"), "_")
        val exportFile = File(context.cacheDir, "$safeTitle.$ext")
        exportFile.writeText(content, Charsets.UTF_8)
        exportFile
    }
}

class OcrWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val repo = (applicationContext as ReaderApp).repo
        val id = inputData.getString("book") ?: return@withContext Result.failure()
        val initial = repo.dao.book(id) ?: return@withContext Result.failure()
        if (initial.status == "PAUSED") return@withContext Result.success()

        try {
            while (!isStopped) {
                val book = repo.dao.book(id) ?: break
                if (book.status == "PAUSED") break

                // Prioritize current reading page, then forward, then backward
                val preferred = repo.dao.position(id)?.page ?: 1
                val sequence = (preferred..book.pages).toList() + (1 until preferred).toList()
                val number = sequence.firstOrNull { repo.dao.page(id, it)?.status == "NOT_STARTED" } ?: break

                val page = repo.dao.page(id, number) ?: continue
                repo.dao.page(page.copy(status = "PROCESSING"))

                try {
                    var result: OcrPageResult? = null
                    val quality = repo.prefs.getInt("quality", 2200)
                    for (resolution in listOf(quality, 1600, 1100).distinct()) {
                        try {
                            val bitmap = repo.render(id, number, resolution, page.rotation)
                            try {
                                val lang = repo.prefs.getString("language", "한국어") ?: "한국어"
                                result = MlKitEngine().recognize(bitmap, lang)
                            } finally {
                                bitmap.recycle()
                            }
                            break
                        } catch (oom: OutOfMemoryError) {
                            if (resolution == 1100) {
                                throw IllegalStateException("메모리가 부족하여 페이지 처리에 실패했습니다.")
                            }
                        }
                    }

                    val recognized = result ?: error("OCR 결과 없음")
                    repo.db.withTransaction {
                        repo.dao.clearBlocks(id, number)
                        repo.dao.clearParagraphs(id, number)
                        repo.dao.blocks(
                            recognized.blocks.map { block ->
                                Block(
                                    bookId = id,
                                    page = number,
                                    text = block.text,
                                    left = block.left,
                                    top = block.top,
                                    right = block.right,
                                    bottom = block.bottom,
                                    linesJson = org.json.JSONArray().apply {
                                        block.lines.forEach { line ->
                                            put(
                                                org.json.JSONObject()
                                                    .put("text", line.text)
                                                    .put("left", line.left)
                                                    .put("top", line.top)
                                                    .put("right", line.right)
                                                    .put("bottom", line.bottom)
                                            )
                                        }
                                    }.toString()
                                )
                            }
                        )
                        repo.dao.paragraphs(Layout.build(id, number, recognized))
                        repo.dao.page(
                            page.copy(
                                width = recognized.width,
                                height = recognized.height,
                                status = "COMPLETED",
                                error = ""
                            )
                        )
                    }
                } catch (cancel: CancellationException) {
                    repo.dao.page(page.copy(status = "NOT_STARTED"))
                    throw cancel
                } catch (e: Exception) {
                    repo.dao.page(
                        page.copy(
                            status = "ERROR",
                            error = e.message ?: "OCR 실패"
                        )
                    )
                }

                val latest = repo.dao.book(id) ?: break
                repo.dao.update(latest.copy(done = repo.dao.completed(id)))
            }

            val latest = repo.dao.book(id) ?: return@withContext Result.success()
            if (latest.status == "PAUSED") return@withContext Result.success()

            val done = repo.dao.completed(id)
            val errors = repo.dao.errors(id)
            if (done + errors < latest.pages) {
                return@withContext Result.retry()
            }

            repo.dao.update(
                latest.copy(
                    done = done,
                    status = if (errors > 0) "ERROR" else "COMPLETED",
                    error = if (errors > 0) "$errors 개 페이지 인식 실패 (다시 시도 가능)" else ""
                )
            )
            Result.success()
        } catch (cancel: CancellationException) {
            throw cancel
        } catch (e: Exception) {
            repo.dao.book(id)?.let {
                repo.dao.update(it.copy(status = "ERROR", error = e.message ?: "처리 오류"))
            }
            Result.failure()
        }
    }
}

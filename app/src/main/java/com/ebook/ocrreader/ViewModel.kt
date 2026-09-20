package com.ebook.ocrreader

import android.app.Application
import android.graphics.Bitmap
import android.graphics.Rect
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

enum class BookSortOrder {
    RECENT,
    ADDED,
    TITLE
}

class LibraryViewModel(application: Application) : AndroidViewModel(application) {
    private val repo = (application as ReaderApp).repo

    private val _sortOrder = MutableStateFlow(BookSortOrder.RECENT)
    val sortOrder = _sortOrder.asStateFlow()

    private val _searchQuery = MutableStateFlow("")
    val searchQuery = _searchQuery.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading = _isLoading.asStateFlow()

    private val _errorMessage = MutableSharedFlow<String>()
    val errorMessage = _errorMessage.asSharedFlow()

    private val _successMessage = MutableSharedFlow<String>()
    val successMessage = _successMessage.asSharedFlow()

    val books: StateFlow<List<Book>> = combine(
        repo.dao.books(),
        _sortOrder,
        _searchQuery
    ) { bookList, sort, query ->
        var filtered = if (query.isBlank()) {
            bookList
        } else {
            bookList.filter {
                it.title.contains(query, ignoreCase = true) ||
                        it.author.contains(query, ignoreCase = true)
            }
        }

        when (sort) {
            BookSortOrder.RECENT -> filtered.sortedByDescending { maxOf(it.opened, it.created) }
            BookSortOrder.ADDED -> filtered.sortedByDescending { it.created }
            BookSortOrder.TITLE -> filtered.sortedBy { it.title.lowercase() }
        }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    fun setSortOrder(order: BookSortOrder) {
        _sortOrder.value = order
    }

    fun setSearchQuery(query: String) {
        _searchQuery.value = query
    }

    fun importBook(uri: Uri) {
        viewModelScope.launch {
            _isLoading.value = true
            try {
                val book = repo.import(uri)
                _successMessage.emit("도서 '${book.title}'이(가) 등록되었습니다.")
            } catch (e: Exception) {
                _errorMessage.emit(e.message ?: "도서 가져오기 실패")
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun importPdf(uri: Uri) = importBook(uri)

    fun deleteBook(id: String) {
        viewModelScope.launch {
            try {
                repo.deleteBook(id)
                _successMessage.emit("도서가 삭제되었습니다.")
            } catch (e: Exception) {
                _errorMessage.emit(e.message ?: "삭제 실패")
            }
        }
    }

    fun updateBookMetadata(id: String, title: String, author: String, memo: String) {
        viewModelScope.launch {
            try {
                repo.updateBook(id, title, author, memo)
                _successMessage.emit("도서 정보가 수정되었습니다.")
            } catch (e: Exception) {
                _errorMessage.emit(e.message ?: "수정 실패")
            }
        }
    }

    fun pauseOcr(id: String) {
        viewModelScope.launch { repo.pause(id) }
    }

    fun resumeOcr(id: String, retryErrors: Boolean = false) {
        viewModelScope.launch { repo.resume(id, retryErrors) }
    }

    fun resetAndReOcr(id: String) {
        viewModelScope.launch { repo.resetAllAndOcr(id) }
    }

    fun exportBook(id: String, html: Boolean, onReady: (File) -> Unit) {
        viewModelScope.launch {
            try {
                val file = repo.createExportFile(id, html)
                onReady(file)
            } catch (e: Exception) {
                _errorMessage.emit(e.message ?: "내보내기 실패")
            }
        }
    }

    fun getCoverFile(id: String): File = repo.cover(id)

    suspend fun getPages(bookId: String): List<Page> = withContext(Dispatchers.IO) {
        repo.dao.allPages(bookId)
    }

    fun rebuildParagraphs(bookId: String) {
        viewModelScope.launch {
            repo.rebuildParagraphs(bookId)
            _successMessage.emit("문단 구조가 재구성되었습니다.")
        }
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
class ReaderViewModel(
    application: Application,
    val bookId: String
) : AndroidViewModel(application) {
    val repo = (application as ReaderApp).repo

    val book: StateFlow<Book?> = repo.dao.watchBook(bookId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    val pages: StateFlow<List<Page>> = repo.dao.pages(bookId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    val bookmarks: StateFlow<List<Bookmark>> = repo.dao.bookmarks(bookId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    private val _settings = MutableStateFlow(loadSettings())
    val settings = _settings.asStateFlow()

    val paragraphs: StateFlow<List<Paragraph>> = repo.dao.watchAllParagraphs(bookId)
        .combine(_settings) { list, s ->
            list.filter { p ->
                !((p.region == "NUMBER" && s.hidePageNumbers) ||
                        (p.region == "HEADER" && s.hideHeaders) ||
                        (p.region == "FOOTER" && s.hideFooters))
            }
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    private val _isOriginalMode = MutableStateFlow(false)
    val isOriginalMode = _isOriginalMode.asStateFlow()

    private val _currentPage = MutableStateFlow(1)
    val currentPage = _currentPage.asStateFlow()

    private val _highlightBox = MutableStateFlow<Rect?>(null)
    val highlightBox = _highlightBox.asStateFlow()

    private val _originalBitmap = MutableStateFlow<Bitmap?>(null)
    val originalBitmap = _originalBitmap.asStateFlow()

    private val _isRenderingPage = MutableStateFlow(false)
    val isRenderingPage = _isRenderingPage.asStateFlow()

    private val _message = MutableSharedFlow<String>()
    val message = _message.asSharedFlow()

    init {
        viewModelScope.launch {
            repo.markOpened(bookId)
            repo.rebuildParagraphs(bookId)
            val pos = repo.dao.position(bookId)
            if (pos != null && pos.page > 0) {
                _currentPage.value = pos.page
            }
        }
    }

    private fun loadSettings(): ReaderSettings {
        val p = repo.prefs
        return ReaderSettings(
            fontSizeSp = p.getFloat("font_size", 18f),
            fontFamily = p.getString("font_family", "Sans") ?: "Sans",
            lineHeightMultiplier = p.getFloat("line_height", 1.6f),
            horizontalMarginDp = p.getInt("margin", 18),
            paragraphSpacingDp = p.getInt("paragraph_spacing", 12),
            theme = p.getString("theme", "Light") ?: "Light",
            hidePageNumbers = p.getBoolean("numbers", true),
            hideHeaders = p.getBoolean("headers", true),
            hideFooters = p.getBoolean("footers", true),
            keepScreenOn = p.getBoolean("keep_screen_on", true)
        )
    }

    fun updateSettings(transform: (ReaderSettings) -> ReaderSettings) {
        val newSettings = transform(_settings.value)
        _settings.value = newSettings
        repo.prefs.edit()
            .putFloat("font_size", newSettings.fontSizeSp)
            .putString("font_family", newSettings.fontFamily)
            .putFloat("line_height", newSettings.lineHeightMultiplier)
            .putInt("margin", newSettings.horizontalMarginDp)
            .putInt("paragraph_spacing", newSettings.paragraphSpacingDp)
            .putString("theme", newSettings.theme)
            .putBoolean("numbers", newSettings.hidePageNumbers)
            .putBoolean("headers", newSettings.hideHeaders)
            .putBoolean("footers", newSettings.hideFooters)
            .putBoolean("keep_screen_on", newSettings.keepScreenOn)
            .apply()
    }

    fun hasPdf(): Boolean = repo.pdf(bookId).exists()

    fun setMode(original: Boolean) {
        if (original && !hasPdf()) {
            viewModelScope.launch {
                _message.emit("텍스트 도서는 원본 스캔 이미지가 없습니다.")
            }
            return
        }
        _isOriginalMode.value = original
        if (original) {
            loadOriginalPageBitmap(_currentPage.value)
        }
    }

    fun setCurrentPage(page: Int) {
        _currentPage.value = page
        savePosition(page, 0, 0, 0)
        if (_isOriginalMode.value) {
            loadOriginalPageBitmap(page)
        }
    }

    fun viewOriginalParagraph(pageNumber: Int, left: Int, top: Int, right: Int, bottom: Int) {
        if (!hasPdf()) return
        _currentPage.value = pageNumber
        _highlightBox.value = Rect(left, top, right, bottom)
        setMode(true)
    }

    fun clearHighlight() {
        _highlightBox.value = null
    }

    fun loadOriginalPageBitmap(pageNumber: Int) {
        if (!hasPdf()) return
        viewModelScope.launch {
            _isRenderingPage.value = true
            try {
                val page = repo.dao.page(bookId, pageNumber)
                val rotation = page?.rotation ?: 0
                val bmp = repo.render(bookId, pageNumber, 1800, rotation)
                val old = _originalBitmap.value
                _originalBitmap.value = bmp
                old?.recycle()
            } catch (e: Exception) {
                _message.emit("페이지 렌더링 실패: ${e.message}")
            } finally {
                _isRenderingPage.value = false
            }
        }
    }

    fun rotateCurrentPage() {
        viewModelScope.launch {
            val pageNum = _currentPage.value
            repo.rotate(bookId, pageNum)
            loadOriginalPageBitmap(pageNum)
            _message.emit("$pageNum 페이지 회전 완료 (OCR이 다시 진행됩니다)")
        }
    }

    fun retryCurrentPageOcr() {
        viewModelScope.launch {
            val pageNum = _currentPage.value
            repo.retryPage(bookId, pageNum)
            _message.emit("$pageNum 페이지 OCR 다시 시도 시작")
        }
    }

    fun savePosition(page: Int, paragraphId: Long, index: Int, offset: Int) {
        viewModelScope.launch {
            repo.savePosition(bookId, page, paragraphId, index, offset)
        }
    }

    fun addBookmark(page: Int, paragraphId: Long, memo: String) {
        viewModelScope.launch {
            repo.addBookmark(bookId, page, paragraphId, memo)
            _message.emit("책갈피가 등록되었습니다.")
        }
    }

    fun deleteBookmark(id: Long) {
        viewModelScope.launch {
            repo.deleteBookmark(id)
            _message.emit("책갈피가 삭제되었습니다.")
        }
    }

    fun editParagraph(id: Long, text: String) {
        viewModelScope.launch {
            repo.editParagraph(id, text)
            _message.emit("문단 텍스트가 수정되었습니다.")
        }
    }

    suspend fun getContents(): List<Paragraph> = withContext(Dispatchers.IO) {
        repo.dao.contents(bookId)
    }

    suspend fun searchInBook(query: String): List<Paragraph> = withContext(Dispatchers.IO) {
        if (query.isBlank()) emptyList() else repo.dao.search(bookId, query)
    }

    fun rebuildParagraphs() {
        viewModelScope.launch {
            repo.rebuildParagraphs(bookId)
            _message.emit("문단 구조가 최신 알고리즘으로 재구성되었습니다.")
        }
    }

    override fun onCleared() {
        super.onCleared()
        _originalBitmap.value?.recycle()
    }
}

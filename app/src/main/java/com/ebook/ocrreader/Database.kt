package com.ebook.ocrreader

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Entity
data class Book(
    @PrimaryKey val id: String,
    val title: String,
    val uri: String,
    val fileName: String,
    val size: Long,
    val hash: String,
    val pages: Int,
    val created: Long = System.currentTimeMillis(),
    val opened: Long = 0,
    val status: String = "PROCESSING",
    val done: Int = 0,
    val author: String = "",
    val memo: String = "",
    val error: String = ""
)

@Entity(primaryKeys = ["bookId", "number"])
data class Page(
    val bookId: String,
    val number: Int,
    val width: Int = 0,
    val height: Int = 0,
    val rotation: Int = 0,
    val status: String = "NOT_STARTED",
    val error: String = ""
)

@Entity(indices = [Index("bookId")])
data class Block(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val bookId: String,
    val page: Int,
    val text: String,
    val left: Int,
    val top: Int,
    val right: Int,
    val bottom: Int,
    val linesJson: String
)

@Entity(indices = [Index("bookId")])
data class Paragraph(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val bookId: String,
    val page: Int,
    val order: Int,
    val original: String,
    val edited: String? = null,
    val left: Int,
    val top: Int,
    val right: Int,
    val bottom: Int,
    val type: String = "BODY",
    val region: String = "BODY"
) {
    val text: String get() = edited ?: original
}

@Entity
data class Position(
    @PrimaryKey val bookId: String,
    val page: Int,
    val paragraphId: Long = 0,
    val index: Int = 0,
    val offset: Int = 0
)

@Entity(indices = [Index("bookId")])
data class Bookmark(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val bookId: String,
    val page: Int,
    val paragraphId: Long = 0,
    val offset: Int = 0,
    val memo: String = "",
    val created: Long = System.currentTimeMillis()
)

@Dao
interface ReaderDao {
    @Query("SELECT * FROM Book ORDER BY opened DESC, created DESC")
    fun books(): Flow<List<Book>>

    @Query("SELECT * FROM Book WHERE id=:id")
    fun watchBook(id: String): Flow<Book?>

    @Query("SELECT * FROM Book WHERE id=:id")
    suspend fun book(id: String): Book?

    @Query("SELECT * FROM Book WHERE hash=:hash LIMIT 1")
    suspend fun duplicate(hash: String): Book?

    @Insert
    suspend fun insert(book: Book)

    @Update
    suspend fun update(book: Book)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun page(page: Page)

    @Query("SELECT * FROM Page WHERE bookId=:id ORDER BY number")
    fun pages(id: String): Flow<List<Page>>

    @Query("SELECT * FROM Page WHERE bookId=:id ORDER BY number")
    suspend fun allPages(id: String): List<Page>

    @Query("SELECT * FROM Page WHERE bookId=:id AND number=:number")
    suspend fun page(id: String, number: Int): Page?

    @Query("SELECT COUNT(*) FROM Page WHERE bookId=:id AND status='COMPLETED'")
    suspend fun completed(id: String): Int

    @Query("SELECT COUNT(*) FROM Page WHERE bookId=:id AND status='ERROR'")
    suspend fun errors(id: String): Int

    @Query("SELECT * FROM Paragraph WHERE bookId=:id AND page=:page ORDER BY `order`")
    fun paragraphs(id: String, page: Int): Flow<List<Paragraph>>

    @Query("SELECT * FROM Paragraph WHERE bookId=:id ORDER BY page, `order`")
    suspend fun allParagraphs(id: String): List<Paragraph>

    @Query("SELECT * FROM Paragraph WHERE bookId=:id ORDER BY page, `order`")
    fun watchAllParagraphs(id: String): Flow<List<Paragraph>>

    @Query("SELECT * FROM Paragraph WHERE bookId=:id AND instr(lower(COALESCE(edited,original)),lower(:query)) > 0 ORDER BY page, `order` LIMIT 200")
    suspend fun search(id: String, query: String): List<Paragraph>

    @Query("SELECT * FROM Paragraph WHERE bookId=:id AND type='TITLE' ORDER BY page, `order`")
    suspend fun contents(id: String): List<Paragraph>

    @Insert
    suspend fun blocks(blocks: List<Block>)

    @Query("SELECT * FROM Block WHERE bookId=:id AND page=:page")
    suspend fun blocksForPage(id: String, page: Int): List<Block>

    @Insert
    suspend fun paragraphs(paragraphs: List<Paragraph>)

    @Query("DELETE FROM Block WHERE bookId=:id AND page=:page")
    suspend fun clearBlocks(id: String, page: Int)

    @Query("DELETE FROM Paragraph WHERE bookId=:id AND page=:page")
    suspend fun clearParagraphs(id: String, page: Int)

    @Query("UPDATE Paragraph SET edited=:text WHERE id=:id")
    suspend fun edit(id: Long, text: String)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun position(position: Position)

    @Query("SELECT * FROM Position WHERE bookId=:id")
    suspend fun position(id: String): Position?

    @Query("SELECT * FROM Position WHERE bookId=:id")
    fun watchPosition(id: String): Flow<Position?>

    @Insert
    suspend fun bookmark(mark: Bookmark)

    @Query("SELECT * FROM Bookmark WHERE bookId=:id ORDER BY created DESC")
    fun bookmarks(id: String): Flow<List<Bookmark>>

    @Query("DELETE FROM Bookmark WHERE id=:id")
    suspend fun deleteBookmark(id: Long)

    @Query("DELETE FROM Book WHERE id=:id")
    suspend fun deleteBook(id: String)

    @Query("DELETE FROM Page WHERE bookId=:id")
    suspend fun deletePages(id: String)

    @Query("DELETE FROM Block WHERE bookId=:id")
    suspend fun deleteBlocks(id: String)

    @Query("DELETE FROM Paragraph WHERE bookId=:id")
    suspend fun deleteParagraphs(id: String)

    @Query("DELETE FROM Position WHERE bookId=:id")
    suspend fun deletePosition(id: String)

    @Query("DELETE FROM Bookmark WHERE bookId=:id")
    suspend fun deleteBookmarks(id: String)
}

@Database(
    entities = [Book::class, Page::class, Block::class, Paragraph::class, Position::class, Bookmark::class],
    version = 1,
    exportSchema = false
)
abstract class ReaderDatabase : RoomDatabase() {
    abstract fun dao(): ReaderDao
}

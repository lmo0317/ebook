package com.ebook.ocrreader

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ebook.ocrreader.ui.AppSettingsScreen
import com.ebook.ocrreader.ui.LibraryScreen
import com.ebook.ocrreader.ui.ReaderScreen

sealed interface Screen {
    data object Library : Screen
    data class Reader(val bookId: String) : Screen
    data object Settings : Screen
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            OcrReaderAppTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    var currentScreen by remember { mutableStateOf<Screen>(Screen.Library) }

                    when (val screen = currentScreen) {
                        is Screen.Library -> {
                            val libraryViewModel: LibraryViewModel = viewModel()
                            LibraryScreen(
                                viewModel = libraryViewModel,
                                onOpenBook = { bookId ->
                                    currentScreen = Screen.Reader(bookId)
                                },
                                onOpenSettings = {
                                    currentScreen = Screen.Settings
                                }
                            )
                        }
                        is Screen.Reader -> {
                            BackHandler {
                                currentScreen = Screen.Library
                            }
                            val readerViewModel: ReaderViewModel = viewModel(
                                key = "reader-${screen.bookId}",
                                factory = object : ViewModelProvider.Factory {
                                    override fun <T : ViewModel> create(modelClass: Class<T>): T {
                                        @Suppress("UNCHECKED_CAST")
                                        return ReaderViewModel(application, screen.bookId) as T
                                    }
                                }
                            )
                            ReaderScreen(
                                viewModel = readerViewModel,
                                onBack = {
                                    currentScreen = Screen.Library
                                }
                            )
                        }
                        is Screen.Settings -> {
                            BackHandler {
                                currentScreen = Screen.Library
                            }
                            AppSettingsScreen(
                                onBack = {
                                    currentScreen = Screen.Library
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

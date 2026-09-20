package com.ebook.ocrreader

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily

data class ReaderSettings(
    val fontSizeSp: Float = 20f,
    val fontFamily: String = "Sans", // "Sans", "Serif"
    val lineHeightMultiplier: Float = 1.6f,
    val horizontalMarginDp: Int = 18,
    val paragraphSpacingDp: Int = 10,
    val theme: String = "Light", // "Light", "Sepia", "Dark"
    val hidePageNumbers: Boolean = true,
    val hideHeaders: Boolean = true,
    val hideFooters: Boolean = true,
    val keepScreenOn: Boolean = true
)

data class ReaderColors(
    val background: Color,
    val text: Color,
    val surface: Color,
    val divider: Color,
    val accent: Color
)

object ReaderThemes {
    val Light = ReaderColors(
        background = Color(0xFFFFFFFF),
        text = Color(0xFF1E1E1E),
        surface = Color(0xFFF6F6F6),
        divider = Color(0xFFE0E0E0),
        accent = Color(0xFF2563EB)
    )

    val Sepia = ReaderColors(
        background = Color(0xFFFAF3E0),
        text = Color(0xFF3F2B1D),
        surface = Color(0xFFF1E4C3),
        divider = Color(0xFFDCC8A2),
        accent = Color(0xFF92400E)
    )

    val Dark = ReaderColors(
        background = Color(0xFF141414),
        text = Color(0xFFE0E0E0),
        surface = Color(0xFF222222),
        divider = Color(0xFF333333),
        accent = Color(0xFF60A5FA)
    )

    fun getColors(theme: String): ReaderColors = when (theme) {
        "Sepia" -> Sepia
        "Dark" -> Dark
        else -> Light
    }

    fun getFontFamily(name: String): FontFamily = when (name) {
        "Serif" -> FontFamily.Serif
        else -> FontFamily.SansSerif
    }
}

@Composable
fun OcrReaderAppTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) {
        darkColorScheme(
            primary = Color(0xFF60A5FA),
            secondary = Color(0xFF93C5FD),
            background = Color(0xFF121212),
            surface = Color(0xFF1E1E1E),
            onPrimary = Color.Black,
            onBackground = Color.White,
            onSurface = Color.White
        )
    } else {
        lightColorScheme(
            primary = Color(0xFF2563EB),
            secondary = Color(0xFF1D4ED8),
            background = Color(0xFFF8FAFC),
            surface = Color(0xFFFFFFFF),
            onPrimary = Color.White,
            onBackground = Color(0xFF0F172A),
            onSurface = Color(0xFF0F172A)
        )
    }

    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}

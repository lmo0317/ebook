package com.ebook.ocrreader

import java.text.Normalizer

data class OcrLine(val text: String, val left: Int, val top: Int, val right: Int, val bottom: Int) {
    val height get() = bottom - top
    val width get() = right - left
}

data class OcrBlock(val text: String, val left: Int, val top: Int, val right: Int, val bottom: Int, val lines: List<OcrLine>) {
    val height get() = bottom - top
    val width get() = right - left
}

data class OcrPageResult(val width: Int, val height: Int, val blocks: List<OcrBlock>)

object Layout {

    private val BARCODE_REGEX = Regex("^(9[Ttr0-9]{8,}|[0-9a-zA-Z_\\-]{14,})")
    private val NUMBER_REGEX = Regex("^[0-9ivxIVX]{1,4}$")
    private val TITLE_PREFIX_REGEX = Regex("^(?:제\\s*\\d+\\s*[장절편부]|\\d+\\.\\d+(\\.\\d+)?|[0-9]+\\s+[가-힣]|0?\\d장|Chapter|CHAPTER|PART|Part|TIP|Tip|Q&A)\\b")
    private val SENTENCE_END_REGEX = Regex("(?:습니다|입니다|했다|였다|있다|다|냐|까|요|죠|됨|음)\\s*[.?!\"'”’)]*$")
    private val CONTINUATION_PREFIX_REGEX = Regex("^(?:니다|습니다|입니다|였다|했다|있었다|으로|에서|로서|에게|과|와|및|또는|그리고|하지만|그러나)(?:\\s|[.,!?]|$)")
    private val SPLIT_VERB_PREFIX = Regex("[가-힣]+[습합]$")

    private val NOISE_PUNCTUATIONS = setOf(".", "-", "_", "~", ",", "`", "'", "\"", "|", "/", "\\", "·", ":")
    private val HEADER_NOISE_KEYWORDS = listOf("한 권으로", "한권으로", "파인튜닝", "PART", "NLP의 과거", "전체 파인튜닝", "vLLM")
    private val FOOTER_NOISE_KEYWORDS = listOf("위키북스", "WIKIBOOKS")

    // Comprehensive dictionary of Korean OCR error patterns
    private val TYPO_REPLACEMENTS: List<Pair<Regex, String>> = listOf(
        // ㅈ / ㅊ confusions
        Regex("""(?<![가-힣a-zA-Z0-9])마지(?=\s|[.,!?]|$)""") to "마치",
        Regex("""스위지""") to "스위치",
        Regex("""거지면서""") to "거치면서",
        Regex("""순자적""") to "순차적",
        Regex("""순자\s*(?:저리|처리)""") to "순차 처리",
        Regex("""가중지""") to "가중치",
        Regex("""필수\s*절자""") to "필수 절차",
        Regex("""절자(?=\s*(?:입니다|를|가|로|에))""") to "절차",
        Regex("""자이점""") to "차이점",
        Regex("""자이점도""") to "차이점도",
        Regex("""(사소한|큰)\s+자이""") to "$1 차이",
        Regex("""(?<![가-힣])자이(가|를|로|에|의|는|도)(?![가-힣])""") to "차이$1",
        Regex("""자원의\s*저주""") to "차원의 저주",
        Regex("""자원\s*축소""") to "차원 축소",
        Regex("""(\d+)\s*자원""") to "$1차원",
        Regex("""자원\s*크기""") to "차원 크기",
        Regex("""원래\s*자원으로""") to "원래 차원으로",
        Regex("""결과의\s*자원을""") to "결과의 차원을",
        Regex("""마지막\s*자원을""") to "마지막 차원을",
        Regex("""자근차근""") to "차근차근",

        // 처리 / 저리 confusions
        Regex("""전저리""") to "전처리",
        Regex("""전저리된""") to "전처리된",
        Regex("""전저리와""") to "전처리와",
        Regex("""자연어\s*저리""") to "자연어 처리",
        Regex("""병렬\s*저리""") to "병렬 처리",
        Regex("""순차적\s*저리""") to "순차적 처리",
        Regex("""데이터\s*저리""") to "데이터 처리",
        Regex("""텐서\s*병렬\s*저리""") to "텐서 병렬 처리",
        Regex("""언어\s*저리""") to "언어 처리",
        Regex("""저리\s*속도""") to "처리 속도",
        Regex("""저리\s*시간""") to "처리 시간",
        Regex("""저리\s*능력""") to "처리 능력",
        Regex("""저리\s*과정""") to "처리 과정",
        Regex("""(?<![가-힣])저리(할|하는|하고|해|된|될|되어|되지|하지|하면|하게|됨을|되기|됩니다|했습)""") to "처리$1",
        Regex("""(?<![가-힣])저리를(?![가-힣])""") to "처리를",
        Regex("""저리합니다""") to "처리합니다",
        Regex("""저리하지""") to "처리하지",

        // ML / Tech term OCR confusions
        Regex("""모\s*텔""") to "모델",
        Regex("""모델텔""") to "모델",
        Regex("""(?<![가-힣])모텔(?=\s*(?:을|를|이|가|의|에|은|는|로|과|와|에서|훈련|학습|평가|서빙|구현|준비|생성|파라미터|크기|구조|이름))""") to "모델",
        Regex("""시권스""") to "시퀀스",
        Regex("""임겟값""") to "임계값",
        Regex("""파인[류뉴][님닝]""") to "파인튜닝",
        Regex("""(?<![가-힣])서방(?=\s*(?:최적화|기술|까지|방법|원리|구현))""") to "서빙",
        Regex("""독사들""") to "독자들",
        Regex("""맛춤화""") to "맞춤화",
        Regex("""(?<![가-힣])맛춤(?![가-힣])""") to "맞춤",
        Regex("""어텐선""") to "어텐션",
        Regex("""소포트맥스""") to "소프트맥스",
        Regex("""조조지타운""") to "조지타운",
        Regex("""조지타운-BM""") to "조지타운-IBM",
        Regex("""MIrT""") to "MIT",
        Regex("""아는\s+튜링""") to "이는 튜링",
        Regex("""(?<![가-힣])잠조(?=\s*(?:자료|문헌|하기|하여|해|테이블))""") to "참조",
        Regex("""응납""") to "응답",
        Regex("""응납자""") to "응답자",
        Regex("""응납에서""") to "응답에서",
        Regex("""응담""") to "응답",
        Regex("""담변""") to "답변",
        Regex("""평기가""") to "평가",
        Regex("""의건""") to "의견",
        Regex("""점자\s*발전""") to "점차 발전",
        Regex("""명화히""") to "명확히",
        Regex("""능려을""") to "능력을",
        Regex("""점근하기""") to "접근하기",
        Regex("""학습시길""") to "학습시킬",
        Regex("""다랑면에서""") to "다방면에서",
        Regex("""위키숙스""") to "위키북스",
        Regex("""저직권""") to "저작권",
        Regex("""감들올""") to "값들을",
        Regex("""(?<![가-힣])동해(?=\s+[A-Za-z가-힣]+(?:을|를|에))""") to "통해",
        Regex("""([을를]|이|그|이러한\s+[가-힣]+|저러한\s+[가-힣]+)\s+동해(?![가-힣])""") to "$1 통해",
        Regex("""통동해""") to "통해",
        Regex("""것입나니다""") to "것입니다",
        Regex("""추전드럽니다""") to "추천드립니다",
        Regex("""감사드럽니다""") to "감사드립니다",
        Regex("""튜랑의""") to "튜링의",
        Regex("""여전하\s+남기고""") to "여전히 남기고",
        Regex("""서자유롭지""") to "에서 자유롭지",
        Regex("""서크게""") to "에서 크게",
        Regex("""Intelligcnce""") to "Intelligence",
        Regex("""복\s*하고\s*다층적인""") to "복잡하고 다층적인",
        Regex("""때문임니다""") to "때문입니다",
        Regex("""([가-힣]+)임니다(?![가-힣])""") to "$1입니다",

        // Brand & code acronyms
        Regex("""OpenAl""") to "OpenAI",
        Regex("""OpenA(?=\s+API)""") to "OpenAI",
        Regex("""GP-4""") to "GPT-4",
        Regex("""(?<![a-zA-Z0-9])Al(?![a-zA-Z0-9])""") to "AI",
        Regex("""(?<![a-zA-Z0-9])VLLM(?![a-zA-Z0-9])""") to "vLLM",
        Regex("""Runpod""") to "RunPod",
        Regex("""(?<![a-zA-Z0-9])pqdm(?![a-zA-Z0-9])""") to "tqdm",
        Regex("""iser(?=\s*라는)""") to "user",
        Regex("""(?<![a-zA-Z0-9])Wegh(?![a-zA-Z0-9])""") to "Weights",
        Regex("""_parse\s+eva""") to "_parse_eval",
        Regex("""oN_Sum""") to "on_sum",
        Regex("""Aexa""") to "Alexa",
        Regex("""파라미터\s*뷰닝""") to "파라미터 튜닝",
        Regex("""지집서""") to "지침서",
        Regex("""터테디노트""") to "테디노트",
        Regex("""깃혀브""") to "깃허브",
        Regex("""실습0로""") to "실습으로",
        Regex("""브브릭메이트""") to "브릭메이트",
        Regex("""wWeb""") to "Web",
        Regex("""인공지식에""") to "인공지능에",
        Regex("""AT\s*모[텔델]""") to "AI 모델",
        Regex("""LlaMA""") to "Llama",

        // Broken verb endings
        Regex("""([가-힣]+)함\s*니다(?![가-힣])""") to "$1합니다",
        Regex("""([가-힣]+)습\s+니다(?![가-힣])""") to "$1습니다",
        Regex("""([가-힣]+)합\s+니다(?![가-힣])""") to "$1합니다",
        Regex("""([가-힣]+)합니\s+다(?![가-힣])""") to "$1합니다",
        Regex("""(?<![가-힣])합\s+니다(?![가-힣])""") to "합니다",
        Regex("""([가-힣]+)였습\s+니다(?![가-힣])""") to "$1였습니다",
        Regex("""([가-힣]+)되었습\s+니다(?![가-힣])""") to "$1되었습니다",
        Regex("""([가-힣]+)겠습\s+니다(?![가-힣])""") to "$1겠습니다",
        Regex("""([가-힣]+)있습\s+니다(?![가-힣])""") to "$1있습니다",
        Regex("""([가-힣]+)했습\s+니다(?![가-힣])""") to "$1했습니다",
        Regex("""고민해이야합\s*니다""") to "고민해야 합니다"
    )

    fun applyTypoFixes(text: String): String {
        var result = text
        for ((regex, replacement) in TYPO_REPLACEMENTS) {
            result = regex.replace(result, replacement)
        }
        return result
    }

    fun cleanSpacing(rawText: String): String {
        var text = normalize(rawText)
        // Fix broken particles inside phrases
        text = text.replace(Regex("\\b(기술|정보|데이터|이론|실습|학습|모델|신경망|컴퓨터|인간|기계)\\s+(의|에|을|를|이|가|은|는|와|과|로|으로)(?![가-힣])"), "$1$2")
        // Fix broken syllables across line breaks
        text = text.replace(Regex("([가-힣])\\s*\\n\\s*([가-힣])"), "$1 $2")
        text = text.replace(Regex("[ \\t]+"), " ")
        return text.trim()
    }

    fun normalize(rawText: String): String {
        var text = Normalizer.normalize(rawText, Normalizer.Form.NFC)
        // Clean invisible control chars, FFFD, etc.
        text = text.replace("\uFFFD", "").replace("\uFEFF", "").replace("\u200B", "")
        // Fix space before punctuation: e.g. "있습니다 ." -> "있습니다."
        text = text.replace(Regex("\\s+([.,!?;:])"), "$1")
        // Fix space inside brackets/quotes: e.g. "( 12 )" -> "(12)"
        text = text.replace(Regex("([(\\[{<])\\s+"), "$1")
        text = text.replace(Regex("\\s+([)\\]}>])"), "$1")
        // Fix numbered section headers: "1 . 2 . 3" -> "1.2.3"
        text = text.replace(Regex("(\\d+)\\s*\\.\\s*(\\d+)"), "$1.$2")
        // Collapse multiple spaces
        text = text.replace(Regex("\\s+"), " ")
        return text.trim()
    }

    fun isNoise(text: String, top: Int, bottom: Int, pageHeight: Int): Boolean {
        val t = text.trim()
        if (t.isEmpty()) return true

        // Standalone punctuation noise
        if (t in NOISE_PUNCTUATIONS) return true

        // Barcodes & tracking strings
        if (BARCODE_REGEX.containsMatchIn(t)) return true
        if (top > pageHeight * 0.88 && t.matches(Regex("^[0-9a-zA-Z\\s\\-_]{10,}$"))) return true

        // Standalone margin page numbers
        if (t.matches(Regex("^[0-9ivxIVX]{1,4}$")) && (top < pageHeight * 0.08 || bottom > pageHeight * 0.92)) {
            return true
        }

        // Running header noise: extreme top margin
        if (bottom < pageHeight * 0.075) {
            if (HEADER_NOISE_KEYWORDS.any { t.contains(it) }) return true
            if (t.length < 40) return true
        }

        // Running footer noise: extreme bottom margin
        if (top > pageHeight * 0.925) {
            if (FOOTER_NOISE_KEYWORDS.any { t.contains(it) }) return true
            if (t.length < 35) return true
        }

        return false
    }

    fun isCodeBlockText(text: String): Boolean {
        val lines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }
        if (lines.isEmpty()) return false

        val codeIndicators = listOf(
            "import ", "from ", "def ", "class ", "return ", "if __name__",
            "self.", "torch.", "nn.", "F.", "np.", "plt.", "model =", "loss =",
            "optimizer =", "tokenizer =", "print(", "super().", "pip install",
            "git clone", "cd ", "python ", "export ", "curl ", "wget ",
            "docker run", "runpod ", "wandb.", "def __init__", "def forward"
        )
        val codeScore = lines.count { line -> codeIndicators.any { line.startsWith(it) } }
        val syntaxScore = lines.count { line -> line.contains("=") || line.endsWith(":") || line.endsWith(")") || line.endsWith("}") }

        return (codeScore >= 2) || (lines.size >= 3 && (codeScore + syntaxScore) >= lines.size * 0.75)
    }

    fun formatCleanCode(text: String): String {
        val lines = text.lines()
        val cleanedLines = mutableListOf<String>()
        var indent = 0

        for (l in lines) {
            var s = l.trim()
            if (s.isEmpty()) continue

            s = s.replace("def_init_", "def __init__")
                .replace("super()._init_", "super().__init__")
                .replace("self. token_embedding _table", "self.token_embedding_table")
                .replace("self. position_embedding _table", "self.position_embedding_table")
                .replace("nn. Linear", "nn.Linear")
                .replace("nn. Embedding", "nn.Embedding")
                .replace("F.cross_ent ropy", "F.cross_entropy")
                .replace("max _new_tokens", "max_new_tokens")

            if (s.startsWith("elif ") || s.startsWith("else:") || s.startsWith("except") || s.startsWith("finally:")) {
                indent = maxOf(0, indent - 4)
            }

            cleanedLines.add(" ".repeat(indent) + s)

            if (s.endsWith(":")) {
                indent += 4
            } else if (s.startsWith("return ")) {
                indent = maxOf(0, indent - 4)
            }
        }

        return "```python\n" + cleanedLines.joinToString("\n") + "\n```"
    }

    /**
     * Clean and join lines within an OCR block.
     * Preserves Korean word flow and handles hyphenation.
     */
    fun joinLines(lines: List<OcrLine>): String {
        if (lines.isEmpty()) return ""
        val sb = StringBuilder()
        for (line in lines) {
            val trimmed = line.text.trim()
            if (trimmed.isEmpty()) continue
            if (sb.isEmpty()) {
                sb.append(trimmed)
            } else {
                if (sb.endsWith("-")) {
                    // English hyphenation: remove hyphen and join directly
                    sb.deleteCharAt(sb.length - 1)
                    sb.append(trimmed)
                } else if (trimmed.startsWith(".") || trimmed.startsWith(",") || trimmed.startsWith("?") || trimmed.startsWith("!")) {
                    sb.append(trimmed)
                } else {
                    sb.append(" ").append(trimmed)
                }
            }
        }
        return sb.toString()
    }

    /**
     * Sort blocks into correct reading order (1-column vs 2-column detection).
     */
    fun orderBlocks(blocks: List<OcrBlock>, pageWidth: Int): List<OcrBlock> {
        if (blocks.size <= 2) return blocks.sortedWith(compareBy({ it.top }, { it.left }))

        // Detect 2-column layout
        val splitCandidate = (38..62 step 2).map { pageWidth * it / 100 }.firstOrNull { x ->
            val leftCount = blocks.count { it.right < x - pageWidth * 0.02 }
            val rightCount = blocks.count { it.left > x + pageWidth * 0.02 }
            val crossingCount = blocks.count { it.left <= x && it.right >= x }
            leftCount >= 4 && rightCount >= 4 && crossingCount <= maxOf(1, blocks.size / 7)
        }

        val comparator = compareBy<OcrBlock> { it.top }.thenBy { it.left }

        if (splitCandidate == null) {
            // 1-column: natural top-to-bottom order
            return blocks.sortedWith(comparator)
        }

        // 2-column layout:
        val split = splitCandidate
        val spanning = blocks.filter { it.left < split && it.right > split }.sortedWith(comparator)
        val ordered = mutableListOf<OcrBlock>()
        var prevBottom = Int.MIN_VALUE

        for (barrier in spanning) {
            val band = blocks.filter { it !in spanning && it.top >= prevBottom && it.top < barrier.top }
            ordered.addAll(band.filter { it.right <= split }.sortedWith(comparator))
            ordered.addAll(band.filter { it.left >= split }.sortedWith(comparator))
            ordered.add(barrier)
            prevBottom = barrier.bottom
        }

        val tail = blocks.filter { it !in spanning && it.top >= prevBottom }
        ordered.addAll(tail.filter { it.right <= split }.sortedWith(comparator))
        ordered.addAll(tail.filter { it.left >= split }.sortedWith(comparator))

        return ordered
    }

    fun build(book: String, page: Int, result: OcrPageResult): List<Paragraph> {
        val validBlocks = result.blocks.filter { block ->
            block.text.isNotBlank() && block.height >= result.height * 0.004
        }
        if (validBlocks.isEmpty()) return emptyList()

        // Calculate median line height for font size comparisons
        val allLineHeights = validBlocks.flatMap { it.lines }.map { it.height }.sorted()
        val medianLineHeight = if (allLineHeights.isNotEmpty()) allLineHeights[allLineHeights.size / 2] else 24

        val orderedBlocks = orderBlocks(validBlocks, result.width)
        val output = mutableListOf<Paragraph>()

        // Paragraph accumulation state for body text
        var curText = StringBuilder()
        var curLeft = 0
        var curTop = 0
        var curRight = 0
        var curBottom = 0

        fun flushCurrentParagraph() {
            if (curText.isNotEmpty()) {
                val fullText = applyTypoFixes(cleanSpacing(curText.toString()))
                if (fullText.isNotBlank()) {
                    output += Paragraph(
                        bookId = book,
                        page = page,
                        order = output.size,
                        original = fullText,
                        left = curLeft,
                        top = curTop,
                        right = curRight,
                        bottom = curBottom,
                        type = "BODY",
                        region = "BODY"
                    )
                }
                curText.clear()
            }
        }

        for (block in orderedBlocks) {
            val rawText = joinLines(block.lines)
            if (rawText.isBlank()) continue

            val top = block.top
            val bottom = block.bottom
            val height = block.height

            // Barcode or standalone punctuation noise: drop completely
            val isBarcode = (BARCODE_REGEX.containsMatchIn(rawText) && rawText.length >= 10) ||
                    (top > result.height * 0.88 && rawText.matches(Regex("^[0-9a-zA-Z\\s\\-_]{12,}$")))
            val isNoisePunctuation = rawText.trim() in NOISE_PUNCTUATIONS
            if (isBarcode || isNoisePunctuation) {
                continue
            }

            // Page number filter (isolated number at top/bottom margins)
            val isNumber = NUMBER_REGEX.matches(rawText.trim()) &&
                    (top < result.height * 0.08 || bottom > result.height * 0.92)

            // Running header filter (top margin)
            val isHeader = bottom < result.height * 0.08 && (rawText.length < 60 || HEADER_NOISE_KEYWORDS.any { rawText.contains(it) })

            // Running footer filter (bottom margin)
            val isFooter = top > result.height * 0.92 && (rawText.length < 60 || FOOTER_NOISE_KEYWORDS.any { rawText.contains(it) })

            if (isNumber || isHeader || isFooter) {
                // Flush any pending body text first
                flushCurrentParagraph()

                val region = when {
                    isNumber -> "NUMBER"
                    isFooter -> "FOOTER"
                    else -> "HEADER"
                }

                output += Paragraph(
                    bookId = book,
                    page = page,
                    order = output.size,
                    original = applyTypoFixes(cleanSpacing(rawText)),
                    left = block.left,
                    top = top,
                    right = block.right,
                    bottom = bottom,
                    type = "BODY",
                    region = region
                )
                continue
            }

            // Body content processing
            val cleanedBlockText = applyTypoFixes(cleanSpacing(rawText))
            if (cleanedBlockText.isBlank()) continue

            // Code block detection
            if (isCodeBlockText(block.text)) {
                flushCurrentParagraph()
                output += Paragraph(
                    bookId = book,
                    page = page,
                    order = output.size,
                    original = formatCleanCode(block.text),
                    left = block.left,
                    top = top,
                    right = block.right,
                    bottom = bottom,
                    type = "CODE",
                    region = "BODY"
                )
                continue
            }

            // Title / Heading detection
            val isSentenceEnding = SENTENCE_END_REGEX.containsMatchIn(cleanedBlockText)
            val isContinuation = CONTINUATION_PREFIX_REGEX.containsMatchIn(cleanedBlockText)
            val avgBlockLineHeight = if (block.lines.isNotEmpty()) height / block.lines.size else height
            val hasLargeFont = avgBlockLineHeight > medianLineHeight * 1.35
            val hasTitlePattern = TITLE_PREFIX_REGEX.containsMatchIn(cleanedBlockText)

            val isTitle = cleanedBlockText.length < 75 &&
                    block.lines.size <= 2 &&
                    !isContinuation &&
                    (hasTitlePattern || (hasLargeFont && !isSentenceEnding))

            if (isTitle) {
                flushCurrentParagraph()
                output += Paragraph(
                    bookId = book,
                    page = page,
                    order = output.size,
                    original = cleanedBlockText,
                    left = block.left,
                    top = top,
                    right = block.right,
                    bottom = bottom,
                    type = "TITLE",
                    region = "BODY"
                )
                continue
            }

            // Normal body paragraph flow & cross-block sentence merging
            if (curText.isEmpty()) {
                curText.append(cleanedBlockText)
                curLeft = block.left
                curTop = top
                curRight = block.right
                curBottom = bottom
            } else {
                val prevEnds = SENTENCE_END_REGEX.containsMatchIn(curText)
                val nextCont = CONTINUATION_PREFIX_REGEX.containsMatchIn(cleanedBlockText)

                if (!prevEnds || nextCont) {
                    // Check broken verb ending stitch: e.g. "사례였습" + "니다" -> "사례였습니다"
                    if (SPLIT_VERB_PREFIX.containsMatchIn(curText) && cleanedBlockText.startsWith("니다")) {
                        curText.append(cleanedBlockText)
                    } else {
                        curText.append(" ").append(cleanedBlockText)
                    }
                    curLeft = minOf(curLeft, block.left)
                    curTop = minOf(curTop, top)
                    curRight = maxOf(curRight, block.right)
                    curBottom = maxOf(curBottom, bottom)
                } else {
                    // Previous sentence is complete, begin new paragraph
                    flushCurrentParagraph()
                    curText.append(cleanedBlockText)
                    curLeft = block.left
                    curTop = top
                    curRight = block.right
                    curBottom = bottom
                }
            }
        }

        // Flush remaining text on page
        flushCurrentParagraph()

        return output
    }
}

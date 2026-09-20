package com.ebook.ocrreader

import org.junit.Assert.*
import org.junit.Test

class LayoutTest {

    @Test
    fun testTextNormalizer() {
        val raw = "  이것은   불필요한   공백이 많은\t\t문장입니다 .   "
        val normalized = Layout.normalize(raw)
        assertEquals("이것은 불필요한 공백이 많은 문장입니다.", normalized)
    }

    @Test
    fun testSingleColumnReadingOrder() {
        // Page width 1000
        val b1 = OcrBlock("첫 번째 문단", 100, 100, 900, 200, listOf(OcrLine("첫 번째 문단", 100, 100, 900, 200)))
        val b2 = OcrBlock("두 번째 문단", 100, 250, 900, 350, listOf(OcrLine("두 번째 문단", 100, 250, 900, 350)))
        val b3 = OcrBlock("세 번째 문단", 100, 400, 900, 500, listOf(OcrLine("세 번째 문단", 100, 400, 900, 500)))

        val ordered = Layout.orderBlocks(listOf(b3, b1, b2), 1000)
        assertEquals(3, ordered.size)
        assertEquals("첫 번째 문단", ordered[0].text)
        assertEquals("두 번째 문단", ordered[1].text)
        assertEquals("세 번째 문단", ordered[2].text)
    }

    @Test
    fun testTwoColumnReadingOrder() {
        // Page width 2000, split around 1000
        // Left column (x: 100~900)
        val left1 = OcrBlock("좌측 1번", 100, 100, 900, 140, listOf(OcrLine("좌측 1번", 100, 100, 900, 140)))
        val left2 = OcrBlock("좌측 2번", 100, 160, 900, 200, listOf(OcrLine("좌측 2번", 100, 160, 900, 200)))
        val left3 = OcrBlock("좌측 3번", 100, 220, 900, 260, listOf(OcrLine("좌측 3번", 100, 220, 900, 260)))
        val left4 = OcrBlock("좌측 4번", 100, 280, 900, 320, listOf(OcrLine("좌측 4번", 100, 280, 900, 320)))

        // Right column (x: 1100~1900)
        val right1 = OcrBlock("우측 1번", 1100, 100, 1900, 140, listOf(OcrLine("우측 1번", 1100, 100, 1900, 140)))
        val right2 = OcrBlock("우측 2번", 1100, 160, 1900, 200, listOf(OcrLine("우측 2번", 1100, 160, 1900, 200)))
        val right3 = OcrBlock("우측 3번", 1100, 220, 1900, 260, listOf(OcrLine("우측 3번", 1100, 220, 1900, 260)))
        val right4 = OcrBlock("우측 4번", 1100, 280, 1900, 320, listOf(OcrLine("우측 4번", 1100, 280, 1900, 320)))

        val blocks = listOf(right1, left2, right3, left1, right2, left3, right4, left4)
        val ordered = Layout.orderBlocks(blocks, 2000)

        // Left column lines should come before right column lines
        val leftIndices = listOf("좌측 1번", "좌측 2번", "좌측 3번", "좌측 4번").map { t -> ordered.indexOfFirst { it.text == t } }
        val rightIndices = listOf("우측 1번", "우측 2번", "우측 3번", "우측 4번").map { t -> ordered.indexOfFirst { it.text == t } }

        assertTrue(leftIndices[0] < leftIndices[1])
        assertTrue(leftIndices[1] < leftIndices[2])
        assertTrue(leftIndices.maxOrNull()!! < rightIndices.minOrNull()!!)
    }

    @Test
    fun testParagraphMergeAndTitleDetection() {
        // Height 2000
        val titleLine = OcrLine("제 1 장 새로운 시작", 300, 300, 700, 360)
        val titleBlock = OcrBlock("제 1 장 새로운 시작", 300, 300, 700, 360, listOf(titleLine))

        val bodyLine1 = OcrLine("우리는 책을 읽으면서 많은 것을", 100, 450, 900, 480)
        val bodyLine2 = OcrLine("배우고 생각할 수 있습니다.", 100, 490, 700, 520)
        val bodyBlock = OcrBlock(
            "우리는 책을 읽으면서 많은 것을\n배우고 생각할 수 있습니다.",
            100, 450, 900, 520,
            listOf(bodyLine1, bodyLine2)
        )

        val headerLine = OcrLine("소설 문학 전집", 100, 40, 400, 65) // top < 2000 * 0.08 = 160
        val headerBlock = OcrBlock("소설 문학 전집", 100, 40, 400, 65, listOf(headerLine))

        val pageNumberLine = OcrLine("125", 900, 1920, 950, 1950) // bottom > 2000 * 0.92 = 1840
        val pageNumberBlock = OcrBlock("125", 900, 1920, 950, 1950, listOf(pageNumberLine))

        val result = OcrPageResult(
            width = 1000,
            height = 2000,
            blocks = listOf(headerBlock, titleBlock, bodyBlock, pageNumberBlock)
        )

        val paragraphs = Layout.build("book1", 1, result)

        val headerP = paragraphs.find { it.text == "소설 문학 전집" }
        assertNotNull(headerP)
        assertEquals("HEADER", headerP!!.region)

        val numP = paragraphs.find { it.text == "125" }
        assertNotNull(numP)
        assertEquals("NUMBER", numP!!.region)

        val titleP = paragraphs.find { it.text.contains("새로운 시작") }
        assertNotNull(titleP)
        assertEquals("TITLE", titleP!!.type)

        val bodyP = paragraphs.find { it.text.contains("배우고 생각할 수") }
        assertNotNull(bodyP)
        assertEquals("BODY", bodyP!!.type)
        assertEquals("우리는 책을 읽으면서 많은 것을 배우고 생각할 수 있습니다.", bodyP!!.text)
    }

    @Test
    fun testKoreanOcrTypoFixes() {
        val sample = "이것은 마지 사과와 같고 스위지를 켜서 순자 저리를 시작합니다. 언어 모텔의 파인류님과 시권스 처리, 자원의 저주를 거지면서 극복했습 니다."
        val fixed = Layout.applyTypoFixes(sample)
        println("FIXED_DEBUG: $fixed")
        assertTrue("마치 expected: $fixed", fixed.contains("마치"))
        assertTrue("스위치 expected", fixed.contains("스위치"))
        assertTrue("순차 처리 expected", fixed.contains("순차 처리"))
        assertTrue("언어 모델 expected", fixed.contains("언어 모델"))
        assertTrue("파인튜닝 expected", fixed.contains("파인튜닝"))
        assertTrue("시퀀스 expected", fixed.contains("시퀀스"))
        assertTrue("차원의 저주 expected", fixed.contains("차원의 저주"))
        assertTrue("거치면서 expected", fixed.contains("거치면서"))
        assertTrue("극복했습니다 expected", fixed.contains("극복했습니다"))
    }

    @Test
    fun testSentenceStitchingAcrossBlocks() {
        // Block 1 ends mid-sentence without terminal punctuation
        val line1 = OcrLine("대규모 언어 모델의 파인튜닝은 사전 학습된 가중치를 특정 작업에", 100, 200, 900, 240)
        val b1 = OcrBlock(line1.text, 100, 200, 900, 240, listOf(line1))

        // Block 2 continues the sentence
        val line2 = OcrLine("맞추어 최적화하는 대표적인 사례였습", 100, 250, 800, 290)
        val b2 = OcrBlock(line2.text, 100, 250, 800, 290, listOf(line2))

        // Block 3 starts with '니다.'
        val line3 = OcrLine("니다. 이를 통해 높은 성능을 달성합니다.", 100, 300, 750, 340)
        val b3 = OcrBlock(line3.text, 100, 300, 750, 340, listOf(line3))

        val result = OcrPageResult(width = 1000, height = 2000, blocks = listOf(b1, b2, b3))
        val paragraphs = Layout.build("book1", 1, result)

        assertEquals(1, paragraphs.size)
        val text = paragraphs[0].text
        assertEquals(
            "대규모 언어 모델의 파인튜닝은 사전 학습된 가중치를 특정 작업에 맞추어 최적화하는 대표적인 사례였습니다. 이를 통해 높은 성능을 달성합니다.",
            text
        )
    }

    @Test
    fun testCodeBlockDetectionAndFormatting() {
        val codeText = "import torch\nimport torch.nn as nn\nclass MyModel(nn.Module):\ndef_init_(self):\nsuper()._init_()\nself. Linear = nn. Linear(10, 2)\nreturn x"
        assertTrue(Layout.isCodeBlockText(codeText))
        val formatted = Layout.formatCleanCode(codeText)
        assertTrue(formatted.startsWith("```python"))
        assertTrue(formatted.contains("def __init__(self):"))
        assertTrue(formatted.contains("super().__init__()"))
        assertTrue(formatted.contains("nn.Linear(10, 2)"))
        assertTrue(formatted.endsWith("```"))
    }
}


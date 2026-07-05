from tools.file_parser import parse_file, parse_pdf, parse_docx

async def test_parse_pdf():
    result = await parse_file("assert/test.pdf")
    assert "1111" in result

async def test_parse_docx():
    result = await parse_file("assert/test.docx")
    assert "1111" in result

async def test_pdf_direct():
    result = parse_pdf("assert/test.pdf")
    assert result == "1111"

async def test_docx_direct():
    result = parse_docx("assert/test.docx")
    assert result == "1111"

async def test_invalid_extension():
    result = await parse_file("f.txt")
    assert result == ""

async def test_nonexistent_file():
    result = await parse_file("assert/nonexistent.pdf")
    assert result == ""

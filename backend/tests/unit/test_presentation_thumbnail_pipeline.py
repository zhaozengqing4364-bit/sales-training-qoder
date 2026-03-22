from pathlib import Path

import pytest

from presentation_coach.services.ppt_parser import PPTParserService


@pytest.mark.asyncio
async def test_generate_thumbnail_creates_png_file(tmp_path: Path):
    parser = PPTParserService()

    result = await parser.generate_thumbnail(
        file_content=b"fake-ppt-content",
        page_number=1,
        output_dir=str(tmp_path),
    )

    assert result.is_success
    assert result.value

    thumbnail_path = Path(result.value)
    assert thumbnail_path.exists()
    assert thumbnail_path.suffix.lower() == ".png"
    assert thumbnail_path.stat().st_size > 0

"""Generator script to produce a 5-chapter synthetic EPUB fixture for CairnBooks testing.

Chapter Narrative Arc:
- Chapter 1: Introduction of High Marshal Vasquez and Commander Thorne during the Siege of Oakhaven.
- Chapter 2: The wilderness trek across the Ashen Wastes (Vasquez absent, new characters and lore).
- Chapter 3: The Archive of Whispers (Vasquez absent, archival research and worldbuilding).
- Chapter 4: The Battle of Red Ridge (High Marshal Vasquez returns after a long absence).
- Chapter 5: The Council of Spire (Vasquez and allies consolidate victory).
"""

from pathlib import Path

from ebooklib import epub


def generate_sample_novel_epub(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    book = epub.EpubBook()
    book.set_identifier("cairnbooks-synthetic-fixture-001")
    book.set_title("The Siege of Oakhaven")
    book.set_language("en")
    book.add_author("A. R. Sterling")

    chapters_data = [
        (
            "Chapter One: The Siege Begins",
            "chapter_1.xhtml",
            """<h1>Chapter One: The Siege Begins</h1>
<p>The dawn broke crimson over the ramparts of Oakhaven. High Marshal Vasquez stood atop the north bastion, his scarred iron gauntlets resting upon the battlements. Beside him, Commander Thorne surveyed the advancing legion of the Obsidian Banner.</p>
<p>"Hold the line at all costs," Vasquez ordered, his voice cutting through the rising thunder of artillery. "The citadel must not fall before nightfall."</p>
<p>Thorne signaled the archers as siege engines groaned in the distance.</p>""",
        ),
        (
            "Chapter Two: The Ashen Wastes",
            "chapter_2.xhtml",
            """<h1>Chapter Two: The Ashen Wastes</h1>
<p>Three leagues beyond the river valley lay the silent expanse of the Ashen Wastes. Scout Jennifer trudged through grey dunes under a leaden sky, searching for any remnant of the lost supply column.</p>
<p>Nothing moved among the petrified crags. The war in the east felt distant, yet the cold wind carried the scent of sulfur and old defeat.</p>
<p>Jennifer checked her compass and pressed on toward the abandoned outpost.</p>""",
        ),
        (
            "Chapter Three: Archive of Whispers",
            "chapter_3.xhtml",
            """<h1>Chapter Three: Archive of Whispers</h1>
<p>Deep within the subterranean chambers of Morndun, Scholar Cheryl studied the ancient codices of the First Faction. Thousands of scrolls lined the granite shelves, illuminated only by tallow candles.</p>
<p>"The ancient pacts cannot be revoked," Cheryl murmured, tracing the faded runes with a trembling quill. The secret histories hinted at a betrayal centuries older than the current throne.</p>
<p>She sealed her notes as church bells tolled midnight above ground.</p>""",
        ),
        (
            "Chapter Four: The Battle of Red Ridge",
            "chapter_4.xhtml",
            """<h1>Chapter Four: The Battle of Red Ridge</h1>
<p>The southern defensive line crumbled beneath the weight of enemy cavalry. Just as despair gripped the forward vanguard, trumpets sounded from the western crest.</p>
<p>High Marshal Vasquez charged into the breach at the head of five hundred armored cataphracts. His silver cloak billowed in the tempest as his broadsword shattered the vanguard's formation.</p>
<p>"Forward for the Dawn Crown!" Vasquez roared, turning the tide of the entire engagement in a single stroke.</p>""",
        ),
        (
            "Chapter Five: Council of the Spire",
            "chapter_5.xhtml",
            """<h1>Chapter Five: Council of the Spire</h1>
<p>Victory at Red Ridge had secured the capital, but the palace halls were filled with grave whispers. In the high chamber of the Spire, High Marshal Vasquez met with Chancellor Dennis and Scout Jennifer to draft terms of surrender.</p>
<p>"The Obsidian Banner has retreated, but our frontiers remain broken," Vasquez stated, placing his battle-worn blade upon the grand map table.</p>
<p>The council deliberated late into the night, knowing the true war had only just begun.</p>""",
        ),
    ]

    epub_chapters = []
    for title, file_name, content in chapters_data:
        chap = epub.EpubHtml(title=title, file_name=file_name, lang="en")
        chap.content = f"<html><head><title>{title}</title></head><body>\n{content}\n</body></html>"
        book.add_item(chap)
        epub_chapters.append(chap)

    # Table of contents & navigation
    book.toc = tuple(epub_chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Spine (linear order)
    book.spine = ["nav"] + epub_chapters

    epub.write_epub(str(output_path), book)
    return output_path


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "sample_novel.epub"
    generate_sample_novel_epub(target)
    print(f"Generated fixture at: {target}")

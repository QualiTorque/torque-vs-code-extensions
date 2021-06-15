from typing import Optional, Tuple
from pygls.lsp.types.basic_structures import Position
from pygls.workspace import Document, position_from_utf16


def get_parent_word(document: Document, position: Position):
    lines = document.lines
    if position.line >= len(lines) or position.line == 0:
        return None

    row, col = position_from_utf16(lines, position)    
    
    cur_word = document.word_at_position(position=Position(line=row, character=col))
    line = lines[row]
    index = line.find(cur_word)
    if index >= 2:
        col = index - 2
    
    row -= 1
    word = None
    while row >= 0:
        word = document.word_at_position(position=Position(line=row, character=col))
        row -= 1
        if word:
            break
    
    return word
    

def preceding_words(document: Document, position: Position) -> Optional[Tuple[str, str]]:
    """
    Get the word under the cursor returning the start and end positions.
    """
    lines = document.lines
    if position.line >= len(lines):
        return None

    row, col = position_from_utf16(lines, position)
    line = lines[row]
    try:
        word = line[:col].strip().split()[-2:]
        return word
    except (ValueError):
        return None
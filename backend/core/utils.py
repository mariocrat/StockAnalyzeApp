CHOSUNG_LIST = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']

def get_chosung(text: str) -> str:
    """
    Convert a Korean string to its initial consonants (Chosung).
    Non-Korean characters are returned as-is.
    """
    result = ""
    for char in text:
        if '가' <= char <= '힣':
            result += CHOSUNG_LIST[(ord(char) - ord('가')) // 588]
        else:
            result += char
    return result

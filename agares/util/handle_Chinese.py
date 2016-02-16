def is_Chinese(uchar):
    """
    check whether the unicode is a Chinese character
    """
    if uchar >= u'\u4e00' and uchar<=u'\u9fa5':
        return True
    else:
        return False
        
def contain_Chinese(word):
    """
    check whether the word contains Chinese character
    """
    for uchar in word:
        if is_Chinese(uchar):
            return True
    return False

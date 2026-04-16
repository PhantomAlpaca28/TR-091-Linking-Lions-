import os

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript"
}


def detect_language(filename):

    _, ext = os.path.splitext(filename)

    return LANGUAGE_EXTENSIONS.get(ext)


def read_file_safe(path):

    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    except:

        try:
            with open(path, "r", encoding="latin-1") as f:
                return f.read()

        except:
            return ""
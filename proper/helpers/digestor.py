import shutil
from hashlib import md5


__all__ = ("Digestor", )


class Digestor:
    def __init__(self, root, *, length=12):
        self.root = root
        self.length = length
        self.manifest = {}

    def digest(self, path):
        hash = self.get_hash(path)
        new_path = path.with_suffix(f".{hash}{path.suffix}")
        shutil.copyfile(path, new_path)
        rel_path = str(path.relative_to(self.root))
        rel_new_path = str(new_path.relative_to(self.root))
        self.manifest[rel_path] = rel_new_path
        return rel_new_path

    def get_hash(self, path):
        md5_hash = md5()
        with open(path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                md5_hash.update(byte_block)
        return md5_hash.hexdigest()[:self.length]

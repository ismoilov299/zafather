"""UZ: Yuklanadigan fayllar (`InputFile`).
RU: Загружаемые файлы (`InputFile`).
EN: Files for upload (`InputFile`).
"""

from __future__ import annotations

import io
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import BinaryIO, Union

FileSource = Union[str, "os.PathLike[str]", bytes, bytearray, BinaryIO]


class InputFile:
    """UZ: Lokal fayl, baytlar yoki ochiq oqimni Telegram'ga yuklash uchun.
    RU: Для загрузки в Telegram локального файла, байтов или открытого потока.
    EN: Uploads a local file, raw bytes or an open binary stream to Telegram.

    UZ: Misol / RU: Пример / EN: Example::

        await message.answer_photo(InputFile("rasm.jpg"))
        await bot.send_document(chat_id=1, document=InputFile(b"data", filename="a.txt"))
    """

    __slots__ = ("_filename", "_source")

    def __init__(self, source: FileSource, filename: str | None = None) -> None:
        if isinstance(source, bytearray):
            source = bytes(source)
        self._source = source
        self._filename = filename or self._guess_filename(source)

    @staticmethod
    def _guess_filename(source: FileSource) -> str:
        if isinstance(source, (str, os.PathLike)):
            return os.path.basename(os.fspath(source))
        name = getattr(source, "name", None)
        if isinstance(name, str) and name:
            return os.path.basename(name)
        return "file.dat"

    @property
    def filename(self) -> str:
        return self._filename

    @contextmanager
    def open(self) -> Iterator[BinaryIO]:
        """UZ: Fayl mazmunini o'qish uchun binar oqim beradi (har safar boshidan).
        RU: Возвращает бинарный поток для чтения содержимого (каждый раз с начала).
        EN: Yields a binary stream positioned at the start of the content.
        """
        source = self._source
        if isinstance(source, bytes):
            yield io.BytesIO(source)
        elif isinstance(source, (str, os.PathLike)):
            with open(source, "rb") as stream:
                yield stream
        else:
            if source.seekable():
                source.seek(0)
            yield source

    def read(self) -> bytes:
        """UZ: Butun mazmunni xotiraga o'qiydi.
        RU: Читает всё содержимое в память.
        EN: Reads the whole content into memory.
        """
        with self.open() as stream:
            return stream.read()

    def __repr__(self) -> str:
        return f"<InputFile {self._filename!r}>"


__all__ = ["FileSource", "InputFile"]

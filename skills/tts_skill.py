"""
tts_skill.py
────────────
Offline Text-to-Speech using pyttsx3 (system TTS, zero internet needed).

Dependencies
------------
    pip install pyttsx3
    # Linux also needs: sudo apt install espeak espeak-ng libespeak-dev

Usage
-----
    from skills.tts_skill import TtsSkill

    tts = TtsSkill()
    tts.speak("Hello from Claw Code offline mode!")
    tts.speak("Task complete.", lang="ar")  # Arabic if system voice available
    tts.save("Your code has been updated.", path="output.mp3")
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any


class TtsSkill:
    """
    Simple wrapper around pyttsx3 for offline speech synthesis.

    Parameters
    ----------
    rate  : speech rate in words per minute (default 165)
    volume: 0.0 – 1.0 (default 0.9)
    voice : pyttsx3 voice id string, or None for system default
    """

    def __init__(
        self,
        rate: int = 165,
        volume: float = 0.9,
        voice: str | None = None,
    ) -> None:
        self.rate = rate
        self.volume = volume
        self.voice_id = voice
        self._engine: Any = None
        self._lock = threading.Lock()

    # ── lazy engine init ────────────────────────────────────────────────────

    def _get_engine(self) -> Any:
        if self._engine is None:
            try:
                import pyttsx3  # type: ignore
            except ImportError as exc:
                raise ImportError(
                    "TTS requires pyttsx3.\n"
                    "Run: pip install pyttsx3\n"
                    "Linux: sudo apt install espeak espeak-ng"
                ) from exc

            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)

            if self.voice_id:
                engine.setProperty("voice", self.voice_id)

            self._engine = engine
        return self._engine

    # ── public API ───────────────────────────────────────────────────────────

    def list_voices(self) -> list[dict[str, str]]:
        """Return all available voices as dicts with id, name, lang."""
        engine = self._get_engine()
        voices = engine.getProperty("voices")
        return [
            {"id": v.id, "name": v.name, "lang": ",".join(v.languages)}
            for v in voices
        ]

    def set_voice_by_lang(self, lang_prefix: str = "ar") -> bool:
        """
        Try to set a voice that matches *lang_prefix* (e.g. "ar", "en", "fr").
        Returns True if a matching voice was found.
        """
        for v in self.list_voices():
            if lang_prefix.lower() in v["lang"].lower():
                self._get_engine().setProperty("voice", v["id"])
                return True
        return False

    def speak(self, text: str, block: bool = True) -> None:
        """
        Synthesize and play *text* through the system speaker.

        Parameters
        ----------
        text  : text to speak
        block : if True (default) wait until audio finishes;
                if False, speak in a background thread
        """
        if not text.strip():
            return

        def _run() -> None:
            with self._lock:
                engine = self._get_engine()
                engine.say(text)
                engine.runAndWait()

        if block:
            _run()
        else:
            threading.Thread(target=_run, daemon=True).start()

    def save(self, text: str, path: str | Path = "output.mp3") -> Path:
        """
        Save synthesized speech to *path* (pyttsx3 saves as WAV on most
        drivers despite the extension; rename accordingly).

        Returns the resolved output path.
        """
        out = Path(path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            engine = self._get_engine()
            engine.save_to_file(text, str(out))
            engine.runAndWait()
        print(f"[tts_skill] Saved speech to {out}")
        return out

    def announce(self, level: str, message: str) -> None:
        """
        Convenience wrapper used by Claw Code hooks.

        level : "info" | "warn" | "error"
        """
        prefixes = {"warn": "Warning: ", "error": "Error: "}
        full = prefixes.get(level, "") + message
        self.speak(full, block=False)

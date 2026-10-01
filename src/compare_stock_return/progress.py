"""One stage bar, compatible with Colab; no per-day output."""

from tqdm.auto import tqdm


class Progress:
    def __init__(self, enabled: bool = True):
        self.bar = tqdm(total=10, desc="Comparison pipeline", disable=not enabled)
        self.stage = "Environment"

    def enter(self, number: int, name: str) -> None:
        self.stage = name
        self.bar.set_description(f"[{number}/10] {name}")
        self.bar.update(max(0, number - 1 - self.bar.n))

    def close(self, success: bool) -> None:
        if success:
            self.bar.update(10 - self.bar.n)
        self.bar.close()

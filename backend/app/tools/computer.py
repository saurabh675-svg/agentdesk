import asyncio
import base64
import io


class ComputerManager:
    """Desktop screenshot + mouse/keyboard automation (requires an unlocked desktop)."""

    def __init__(self) -> None:
        self.subscribers: set = set()
        self.last_frame: str | None = None

    def subscribe(self, callback) -> None:
        self.subscribers.add(callback)

    def unsubscribe(self, callback) -> None:
        self.subscribers.discard(callback)

    async def screenshot(self) -> dict:
        frame = await asyncio.to_thread(self._grab)
        self.last_frame = frame
        for callback in list(self.subscribers):
            try:
                await callback({"frame": frame})
            except Exception:
                pass
        return {"frame": frame}

    def _grab(self) -> str:
        from PIL import ImageGrab

        image = ImageGrab.grab()
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, "JPEG", quality=70)
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

    async def size(self) -> dict:
        def get_size():
            import pyautogui

            return pyautogui.size()

        size = await asyncio.to_thread(get_size)
        return {"width": size.width, "height": size.height}

    async def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> str:
        def do_click():
            import pyautogui

            pyautogui.click(x=x, y=y, button=button, clicks=clicks, interval=0.12)

        await asyncio.to_thread(do_click)
        await self.screenshot()
        return f"Clicked {button} at ({x}, {y}) x{clicks}."

    async def move(self, x: int, y: int) -> str:
        await asyncio.to_thread(lambda: __import__("pyautogui").moveTo(x, y, duration=0.2))
        await self.screenshot()
        return f"Moved the pointer to ({x}, {y})."

    async def type_text(self, text: str) -> str:
        def do_type():
            import pyautogui

            pyautogui.write(text, interval=0.01)

        await asyncio.to_thread(do_type)
        await self.screenshot()
        return f"Typed {len(text)} characters."

    async def hotkey(self, keys: list[str]) -> str:
        def do_hotkey():
            import pyautogui

            pyautogui.hotkey(*keys)

        await asyncio.to_thread(do_hotkey)
        await self.screenshot()
        return f"Pressed {'+'.join(keys)}."

    async def scroll(self, amount: int) -> str:
        await asyncio.to_thread(lambda: __import__("pyautogui").scroll(amount))
        await self.screenshot()
        return f"Scrolled by {amount}."


computer = ComputerManager()

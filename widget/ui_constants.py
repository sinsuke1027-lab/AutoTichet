from __future__ import annotations

# カラーパレット
PRIMARY: str = "#2563EB"
SUCCESS: str = "#16A34A"
WARNING: str = "#D97706"
DANGER: str = "#DC2626"

# フォント（Meiryo UI が日本語レイアウトに最適）
FONT_H1: tuple[str, int, str] = ("Meiryo UI", 16, "bold")
FONT_H2: tuple[str, int, str] = ("Meiryo UI", 13, "bold")
FONT_BODY: tuple[str, int] = ("Meiryo UI", 12)
FONT_SMALL: tuple[str, int] = ("Meiryo UI", 10)

# 余白グリッド（8px基準）
PAD_S: int = 8
PAD_M: int = 16
PAD_L: int = 24

# ウィンドウサイズ (width, height)
WIN_INPUT: tuple[int, int] = (480, 520)
WIN_WIZARD: tuple[int, int] = (480, 360)
WIN_SETTINGS: tuple[int, int] = (480, 520)
WIN_HISTORY: tuple[int, int] = (420, 380)
WIN_TODO: tuple[int, int] = (400, 480)

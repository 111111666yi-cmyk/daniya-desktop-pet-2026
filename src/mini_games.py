from __future__ import annotations

import random


class MiniGames:
    RPS_CHOICES = ["石头", "剪刀", "布"]

    def play_rps(self, user_choice: str) -> tuple[str, bool]:
        pet_choice = random.choice(self.RPS_CHOICES)
        if user_choice == pet_choice:
            return f"……都是{pet_choice}。平局，再来？", False

        user_wins = (
            (user_choice == "石头" and pet_choice == "剪刀")
            or (user_choice == "剪刀" and pet_choice == "布")
            or (user_choice == "布" and pet_choice == "石头")
        )
        if user_wins:
            return f"……出了{pet_choice}。啧，你赢了。好感度上升了哦。", True
        return f"……出了{pet_choice}。是我赢了。哼，承让啦。", False

    def roll_dice(self) -> str:
        return f"……掷出了 {random.randint(1, 6)} 点。该你了。"

    def random_100(self) -> str:
        return f"……随机数是 {random.randint(1, 100)}。你抽到多少？"

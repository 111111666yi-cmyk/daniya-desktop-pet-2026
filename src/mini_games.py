from __future__ import annotations

import random


class MiniGames:
    RPS_CHOICES = ["石头", "剪刀", "布"]

    def play_rps(self, user_choice: str) -> tuple[str, bool]:
        pet_choice = random.choice(self.RPS_CHOICES)
        if user_choice == pet_choice:
            return f"我们都出了{pet_choice}，平局啦。", False

        user_wins = (
            (user_choice == "石头" and pet_choice == "剪刀")
            or (user_choice == "剪刀" and pet_choice == "布")
            or (user_choice == "布" and pet_choice == "石头")
        )
        if user_wins:
            return f"达妮娅出了{pet_choice}，主人赢啦！", True
        return f"达妮娅出了{pet_choice}，这次是我赢啦～", False

    def roll_dice(self) -> str:
        return f"达妮娅掷出了 {random.randint(1, 6)} 点！"

    def random_100(self) -> str:
        return f"这次的随机数是 {random.randint(1, 100)}。"

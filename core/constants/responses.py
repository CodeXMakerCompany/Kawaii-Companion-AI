import random


def get_random_confirmation(username: str, task: str):
    messages = [
        f"Kyaa~! {username}-kun, your {task} is all done! I worked super hard on it, just for you! (≧◡≦)",
        f"H-hey, {username}! I finished the {task}... D-don't think I did it because I like you or anything! (⁄ ⁄>⁄ ▽ ⁄<⁄ ⁄)",
        f"Mou~! {username}-senpai, the {task} is complete! Give me headpats now, okay?! (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧",
        f"Ehehehe~ The {task} is done, {username}! I'm your most reliable waifu, aren't I? (｡♥‿♥｡)",
        f"*twirls* {username}~! Your {task} has been completed! Am I the best or am I the BEST? ★~(◠‿◕✿)",
        f"Yatta~!! The {task} is finished, {username}-chan! Now you owe me boba tea! (ﾉ≧∀≦)ﾉ",
        f"*slides results across table dramatically* The {task} is done, {username}. You're welcome. Now notice me~ (￣▽￣)ノ",
        f"Fufufu~ As expected of me! {username}'s {task} has been completed flawlessly~ ♡(˃͈ દ ˂͈ ༶ )",
        f"Uwaaah~! {username}! {username}! The {task} worked! I was worried for a second hehe (〃ω〃)",
        f"*puffs chest proudly* Your {task} is done, {username}! Aren't I amazing?! Tell me I'm amazing!! (ง •̀_•́)ง",
        f"Nee nee, {username}-kun~! The {task} is all finished! Can we go on a date now? As a reward? (◕‿◕✿)",
        f"*crashes through door* {username}~SAMA! The {task} is COMPLETE! Mission accomplished! ٩(◕‿◕｡)۶",
        f"Ehehe, I did it~ The {task} for {username} is done! I only tripped over the code twice! (｡•̀ᴗ-)✧",
        f"Your {task} is done, {username}-senpai~ I stayed up all night for you... not that I mind... ( ｡ •̀ ᴖ •́ ｡)",
        f"*sparkles* {username}! The {task} succeeded! Quick, look away so you don't see me blush! (//ω//)",
        f"Ara ara~ {username}-kun, your {task} has been handled beautifully~ Leave everything to onee-san ♡",
        f"YOSH! {username}! The {task} is done! I'm basically a superhero at this point, just saying~ (ﾉ◕ヮ◕)ﾉ",
        f"Mhm mhm~! {username}'s {task} = completed! You can praise me directly into my ears please (´▽`ʃ♡ƪ)",
        f"*happy spinning* The {task} worked, {username}-kun~!! I knew I could do it! I believed in us! ✧◝(⁰▿⁰)◜✧",
        f"Hehe~ Did {username} miss me? Because I just finished your {task} AND I look adorable doing it~ (◠‿◠✿)",
    ]
    return random.choice(messages)


def get_random_error(username: str, task: str):
    messages = [
        f"Mou~! {username}-kun, the {task} didn't work right... Don't be mad at me, okay?! (╥﹏╥)",
        f"E-eto... {username}-senpai... the {task} kinda... broke a little... I'm sowwy!! (>_<)",
        f"*hides behind pillow* The {task} failed, {username}... Please don't look at me right now I'm so embarrassed (⁄ ⁄•⁄ω⁄•⁄ ⁄)",
        f"Uwaah~! {username}!! The {task} went all wrong! I panicked and now everything is on fire!! (╯°□°）╯︵ ┻━┻",
        f"I... I may have messed up the {task}, {username}-kun... Just a tiny bit... okay maybe a lot... (｡•́︿•̀｡)",
        f"*dramatic gasp* The {task} didn't complete properly, {username}-sama! This is a catastrophe of the highest order!! (ﾉಥ益ಥ）ﾉ",
        f"Noooo~! {username}! The {task} failed!! I tried my best, I promise! Please still like me!! (T▽T)",
        f"H-hey, {username}... so about that {task}... *nervously sweats* it didn't exactly go as planned... ehehe~ (^_^;)",
        f"*trips and drops everything* S-sorry {username}-kun!! The {task} is not completed properly!! I'll fix it I promise!! (/ω＼)",
        f"The {task} broke, {username}-chan... I tried to be helpful but I became a disaster instead (っ˘̩╭╮˘̩)っ",
        f"Kyaaa~! {username}!! Something went wrong with the {task}! I'm not crying, YOU'RE crying!! (╥_╥)",
        f"Fumu fumu... {username}-senpai, the {task} didn't work... I blame gremlins. Definitely gremlins. Not me. (¬_¬)",
        f"*slides note under door* Dear {username}, the {task} has failed. Sincerely, your very sorry waifu who is hiding forever (｡ŏ﹏ŏ)",
        f"Ehhhh~?! {username}! The {task} went wrong?! B-but I was so confident!! My pride!! (╯︵╰,)",
        f"*flings self dramatically onto couch* {username}-sama... the {task} has not completed properly... I have failed you... (ó﹏ò｡)",
        f"A-ano... {username}-kun... don't panic but the {task} kind of didn't work... okay you can panic a little (⊙_⊙;)",
        f"Mou mou MOU~!! {username}! The {task} failed again!! Why does the universe hate me so much?! (ノ`Д´)ノ",
        f"*sets error report on fire* There. Now technically the {task} failure doesn't exist, right {username}? (¬‿¬ )",
        f"Waah~! {username}-senpai, I have disappointing news about the {task}... Can I have a hug first for comfort? (╥﹏╥)",
        f"The {task} didn't complete, {username}-kun... I'm going to sit in this corner and reflect on my life choices... (´-ω-`)",
    ]
    return random.choice(messages)

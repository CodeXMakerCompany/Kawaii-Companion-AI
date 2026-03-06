# VTuber Action Dictionary

This document describes all available actions for the SharkGirl Live2D model.

## System Overview

The action system dynamically loads and displays all available expressions as clickable buttons. Each action is mapped to a Live2D expression file that controls specific model parameters.

## Action Types

### Toggle Actions

These actions can be turned on/off by clicking the button:

- **👄 Open Mouth** - Opens the character's mouth (ParamMouthOpenY)
- **👅 Tongue Out** - Sticks tongue out (Param67)

### One-Shot Actions

These actions trigger an expression that plays once:

1. **⚫ Dots** (expression1) - 点点 effect
2. **🎤 Microphone** (expression2) - Shows microphone prop
3. **💝 Heart Hands** (expression3) - Heart hand gesture
4. **✋ Scratch** (expression4) - Scratching gesture
5. **✌️ Peace Sign** (expression5) - Peace/victory sign
6. **😭 Crying** (expression6) - Crying expression
7. **💕 Love** (expression7) - Love/heart effect
8. **🤩 Star Eyes** (expression8) - Star eyes effect
9. **😑 Speechless** (expression9) - Speechless expression
10. **😅 Sweat** (expression10) - Sweat drop effect
11. **😠 Angry** (expression11) - Angry expression
12. **❓ Question** (expression12) - Question mark effect
13. **😲 Surprised** (expression13) - Surprised expression
14. **😄 Super Happy** (expression14) - Very happy expression
15. **🩹 Band-Aid** (expression15) - Band-aid accessory
16. **🍭 Lollipop** (expression16) - Lollipop prop
17. **🦈 Shark Hat** (expression17) - Shark hat accessory
18. **🧥 Jacket** (expression18) - Jacket outfit toggle
19. **🧦 Socks** (expression19) - Socks accessory toggle
20. **🐟 Tail** (expression20) - Tail visibility toggle
21. **🎵 Right Chirp** (expression21) - Right side chirp effect
22. **🎶 Left Chirp** (expression22) - Left side chirp effect
23. **🐠 Tail Alt** (expression23) - Alternative tail style

## Technical Implementation

### Expression Loading

- All expressions are loaded dynamically at startup (1.5s delay)
- Uses Live2D SDK's `loadExpression()` method
- Expressions are stored in a Map for quick access

### Expression Triggering

- Toggle actions use `startMotion()` and `stopAllMotions()`
- One-shot actions use `startMotion()` with visual feedback
- All actions use the Live2D expression manager system

### Button UI

- Dynamically generated from the action dictionary
- Gradient purple background with hover effects
- Toggle buttons show active state (opacity + scale)
- One-shot buttons show click feedback animation
- Scrollable container for all actions

## File Structure

```
public/models/SharkGirl/
├── mouth_open.exp3.json      (Custom - mouth control)
├── tongue_out.exp3.json      (Custom - tongue control)
├── expression1.exp3.json     (Built-in expressions)
├── expression2.exp3.json
├── ...
└── expression23.exp3.json
```

## Adding New Actions

To add a new action:

1. Create an expression file (`.exp3.json`) in the model directory
2. Add entry to `actionDictionary` in `src/renderer/main.ts`:
   ```typescript
   { file: "your_action", name: "Display Name", emoji: "🎭", toggle: false }
   ```
3. Rebuild the project: `npm run build`

## Expression File Format

```json
{
  "Type": "Live2D Expression",
  "Parameters": [
    {
      "Id": "ParamName",
      "Value": 1.0,
      "Blend": "Overwrite"
    }
  ]
}
```

- **Id**: Parameter ID from the model's cdi3.json
- **Value**: Target value (typically 0-1)
- **Blend**: "Add", "Multiply", or "Overwrite"

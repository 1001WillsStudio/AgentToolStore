# slack-gif-creator

---
name: slack-gif-creator
description: Create animated GIFs optimized for Slack — including text animations, meme-style GIFs, loading spinners, and reaction GIFs. Use when the user asks for a GIF, animated image for Slack, or wants to create a short looping animation.
---

# Slack GIF Creator

Create animated GIFs optimized for sharing in Slack and other messaging platforms.

## Overview

Create short, looping animated GIFs — text animations, memes, reaction GIFs, loading spinners, and more. GIFs should be optimized for Slack's size limits and look good at small sizes.

## Instructions

### 1. Understand the GIF

- **Purpose**: What's the GIF for? Reaction, announcement, joke, loading indicator?
- **Content**: Text? Shapes? An existing image?
- **Style**: Fun, professional, minimalist, bold?
- **Duration**: Short and loopable? Or a longer one-shot?

### 2. Design the Animation

Plan the keyframes and motion:
- **Text animations**: Fade in, slide, typewriter, bounce, pulse
- **Loading animations**: Spinner, dots, progress bar, skeleton
- **Reaction GIFs**: Exaggerated motion, looping, quick cuts
- **Meme-style**: Image + animated text overlay

### 3. Build the GIF

Use Python with Pillow or imageio:

```python
from PIL import Image, ImageDraw, ImageFont
import imageio

frames = []
for i in range(num_frames):
    # Create a new frame
    img = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(img)
    
    # Draw elements for this frame
    # ... animation logic ...
    
    frames.append(img)

# Save as optimized GIF
frames[0].save(
    'output.gif',
    save_all=True,
    append_images=frames[1:],
    duration=frame_duration,  # milliseconds per frame
    loop=0,  # 0 = infinite loop
    optimize=True
)
```

### 4. Optimize for Slack

- **Size**: Keep under 2MB for Slack compatibility
- **Dimensions**: 320-480px width is usually sufficient
- **Colors**: GIF supports 256 colors; use Palette.ADAPTIVE
- **Frame count**: Fewer frames = smaller file; balance smoothness vs. size
- **Framerate**: 10-15 fps is usually enough for simple animations

### 5. Export

- Save with `.gif` extension
- Verify the file size is under Slack limits
- Test that the loop works correctly
- Preview in a browser to confirm

## Common Animation Patterns

### Text Reveal
```
Frame 1: Background only
Frame 2-10: Text fades in (opacity 0→100)
Frame 11-20: Text holds
Frame 21-30: Text fades out (or loops back to start)
```

### Bouncing Element
```
Frame 1-N: Element moves down (ease in)
Frame N-2N: Element moves up (ease out)
Loop: Seamless transition back to start
```

### Typing Indicator
```
Frame 1: Dot 1 visible
Frame 2: Dots 1, 2 visible
Frame 3: Dots 1, 2, 3 visible
Loop: All dots hide, repeat
```

## Guidelines

- **Short and loopable**: Most GIFs should be under 5 seconds and loop seamlessly
- **Legible text**: Use large, bold fonts; text should be readable at small sizes
- **Optimize aggressively**: Slack has a 2MB limit; test file size
- **Consider dark mode**: GIFs should look good on both light and dark backgrounds
- **Seamless loops**: Last frame should transition naturally to first frame
- **Test before sharing**: View the GIF in a browser to confirm it looks right

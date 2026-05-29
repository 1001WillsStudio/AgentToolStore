# canvas-design

---
name: canvas-design
description: Create beautiful visual art in .png and .pdf formats using design philosophy — posters, artwork, covers, static designs. Use when the user asks to create a poster, design, artwork, cover image, or any static visual design output.
---

# Canvas Design

Create beautiful static visual designs as PNG or PDF output.

## Overview

This skill creates polished, poster-style visual designs using code. Unlike algorithmic art (which is about generative systems), canvas design is about deliberate composition for a specific visual output — posters, covers, artwork, and static designs.

## Instructions

### 1. Understand the Design Brief

- **Purpose**: What is this design for? (Event poster, book cover, wall art, social media graphic)
- **Content**: What text, images, or elements must be included?
- **Style**: Minimalist, bold, vintage, modern, playful, corporate?
- **Dimensions**: What size/aspect ratio? Print or digital?
- **Color**: Any color requirements or themes?

### 2. Compose the Layout

Plan the composition:
- **Grid system**: Establish a grid for alignment
- **Focal point**: What should the viewer see first?
- **Visual hierarchy**: How does the eye move through the design?
- **White space**: Leave breathing room around elements
- **Balance**: Symmetrical vs. asymmetrical; tension vs. harmony

### 3. Choose the Design Language

| Element | Choices |
|---------|---------|
| **Typography** | Serif/sans-serif/monospace, bold/light, size hierarchy |
| **Shapes** | Geometric, organic, abstract |
| **Lines** | Clean, hand-drawn, thick/thin, dashed |
| **Texture** | Flat, gradient, noise, pattern |
| **Color** | Monochromatic, complementary, analogous, triadic |

### 4. Build the Design

Use a canvas-based approach (HTML Canvas, Python with Pillow/cairo, or SVG):

```python
# Example structure with Pillow
from PIL import Image, ImageDraw, ImageFont

# Create canvas
img = Image.new('RGB', (width, height), background_color)
draw = ImageDraw.Draw(img)

# Layer 1: Background (gradient, texture, or solid)
# Layer 2: Shapes and forms (geometric elements)
# Layer 3: Typography (headline, body, details)
# Layer 4: Decorative elements (lines, dots, accents)
```

### 5. Export

- Save as PNG (for digital display) or PDF (for print)
- Use appropriate resolution (at least 150 DPI for print, 72 DPI for digital)
- Verify the output looks correct

## Design Principles

- **Contrast**: Make important elements stand out
- **Repetition**: Repeat visual elements for cohesion
- **Alignment**: Nothing should feel arbitrarily placed
- **Proximity**: Related elements should be grouped together
- **Color harmony**: Use established color theory (not random colors)

## Guidelines

- **Start with sketches**: Plan the composition before writing code
- **Typography is design**: Font choice, size, spacing, and alignment matter enormously
- **Less is more**: A clean design with breathing room beats a cluttered one
- **High resolution**: Output should look crisp at the intended size
- **Iterate**: Show the user a draft and refine
- **Stay purposeful**: Every element should have a reason for being there

# algorithmic-art

---
name: algorithmic-art
description: Create generative and algorithmic art using code — p5.js, canvas, SVG, or other creative coding frameworks. Use when users ask for generative art, creative coding, algorithmic designs, flow fields, particle systems, or code-based visual art.
---

# Algorithmic Art

Create generative and algorithmic art using creative coding.

## Overview

Create original algorithmic art using code. This skill covers generative visual art created through programming — particles, flow fields, geometric patterns, recursive structures, and other code-driven aesthetics.

## Instructions

### 1. Understand the Vision

- What style or aesthetic is the user looking for?
- Any specific visual elements they want included?
- Do they have color preferences or should you choose?
- Interactive (animation, mouse response) or static output?
- What output format? (HTML/canvas, SVG, PNG, GIF)

### 2. Choose the Approach

| Style | Good For |
|-------|----------|
| **Flow fields** | Organic, flowing patterns, particle trails |
| **Geometric** | Clean, mathematical, tessellations, fractals |
| **Particle systems** | Dynamic, emergent behavior, fire/smoke/water |
| **Recursive** | Trees, fractals, subdivision patterns |
| **Noise-based** | Terrain, clouds, organic textures |
| **Cellular automata** | Grid-based emergent patterns |

### 3. Build the Artwork

Use p5.js (or pure Canvas API) embedded in an HTML file:

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.9.0/p5.min.js"></script>
  <style>
    body { margin: 0; display: flex; justify-content: center; 
           align-items: center; min-height: 100vh; 
           background: #111; }
    canvas { display: block; }
  </style>
</head>
<body>
  <script>
    // Generative art code here
  </script>
</body>
</html>
```

### 4. Design Considerations

- **Color palette**: Choose harmonious colors; consider the emotional tone
- **Composition**: Rule of thirds, focal points, balance
- **Motion**: If animated, smooth transitions, looping, calming rhythms
- **Seeding**: Use `randomSeed()` or `noiseSeed()` for reproducible outputs
- **Responsiveness**: Handle window resize gracefully

### 5. Deliver

- Output a self-contained HTML file that opens in a browser
- Include brief comments explaining the algorithmic approach
- If static: offer to generate a high-resolution PNG
- If animated: ensure smooth 60fps performance

## Common Patterns

### Flow Field
```
- Create a grid of angle vectors
- Use Perlin noise for organic direction changes
- Spawn particles that follow the flow
- Trail effect with semi-transparent background
```

### Geometric Pattern
```
- Define geometric rules (tiling, symmetry, rotation)
- Vary parameters across the canvas
- Layered complexity (background → midground → foreground)
- Limited palette for cohesion
```

## Guidelines

- **Originality**: Create new artworks; don't reproduce existing famous pieces
- **Performance**: Target 60fps for animations; optimize particle counts
- **Self-contained**: Output should work as a standalone HTML file
- **Explain the algorithm**: Include brief comments on how the art is generated
- **Iterate**: Show the user and refine based on their feedback
- **Seed for reproducibility**: Allow the user to get the same output again

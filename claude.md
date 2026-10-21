# Project Context

When working with this codebase, prioritize readability over cleverness. Ask clarifying questions before making architectural changes.

## About This Project

The project is a skill used to make videos with technologies like Canvas 2D, HTML / CSS / SVG, WebGL 着色器, Three.js, p5.js + p5.brush, GSAP, Remotion(React), Manim(Python) etc.

## Core Principle

Draft the skill's instructions to be sparing with words, tight and concise, highly human-readable, precise and logically and technically rigorous.

## Behavioral Guidelines

- When testing skills in the project within current sessions, deploy them to the global skills folder you support(for example, `~/.claude/skills` for Claude) first (overide the deployed versions if any), and then test them on the deployed versions. Edit the skills tested if there are bugs or issues to improve found in the testing results. Remember: never edit the deployed versions.
- Prioritize scripts to do tasks if they are competent and efficient to do. Only when scripts couldn't do the jobs, use Reasoning, Browser Use, Computer Use or other tools.
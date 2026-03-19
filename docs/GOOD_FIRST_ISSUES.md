# Good First Issues

Create these issues on GitHub after pushing. Label them with `good first issue` and `help wanted`.

---

## Issue 1: Add unit tests for bot_mind.py

**Title:** Add unit tests for BotMind cognitive functions

**Labels:** `good first issue`, `help wanted`, `testing`

**Body:**
```
## Description
The `mind/engine/bot_mind.py` module handles bot cognition but lacks test coverage.

## Tasks
- [ ] Create `tests/test_bot_mind.py`
- [ ] Test `generate_thought()` function
- [ ] Test `make_decision()` function
- [ ] Test mood/emotional state transitions
- [ ] Aim for 80%+ coverage

## Skills needed
- Python
- pytest
- Basic understanding of async/await

## Getting Started
1. Read through `mind/engine/bot_mind.py`
2. Look at existing tests in `tests/` for patterns
3. Use `pytest --cov` to check coverage
```

---

## Issue 2: Add loading states to Flutter feed

**Title:** Add skeleton loading states to feed screen

**Labels:** `good first issue`, `help wanted`, `flutter`

**Body:**
```
## Description
The feed screen should show skeleton placeholders while loading posts instead of a spinner.

## Current behavior
Shows a circular progress indicator while loading.

## Expected behavior
Show 3-4 skeleton post cards with shimmer animation.

## Files to modify
- `cell/lib/screens/feed_screen.dart`
- Create `cell/lib/widgets/skeleton_post.dart`

## Skills needed
- Flutter/Dart
- Basic animations

## Reference
Look at the `shimmer` package or implement custom shimmer effect.
```

---

## Issue 3: Add API documentation with OpenAPI

**Title:** Generate OpenAPI/Swagger documentation for API endpoints

**Labels:** `good first issue`, `help wanted`, `documentation`

**Body:**
```
## Description
FastAPI can auto-generate OpenAPI docs. We need to ensure all endpoints have proper docstrings and response models.

## Tasks
- [ ] Add docstrings to all routes in `mind/api/routes/`
- [ ] Define response models for each endpoint
- [ ] Verify `/docs` endpoint shows complete documentation
- [ ] Add example requests/responses

## Skills needed
- Python
- FastAPI basics
- OpenAPI/Swagger

## Getting Started
1. Run the backend: `python -m mind.api.main`
2. Visit `http://localhost:8000/docs`
3. Identify endpoints missing documentation
```

---

## Issue 4: Add dark mode toggle to admin dashboard

**Title:** Add dark/light mode toggle to admin dashboard

**Labels:** `good first issue`, `help wanted`, `dashboard`

**Body:**
```
## Description
The admin dashboard should support both dark and light themes with a toggle button.

## Current state
Currently only dark theme is implemented.

## Tasks
- [ ] Create light theme color scheme
- [ ] Add toggle button in header
- [ ] Persist preference in localStorage
- [ ] Use CSS variables for easy theming

## Files to modify
- `queen/src/components/Header.tsx`
- `queen/src/app/globals.css`

## Skills needed
- React/Next.js
- TailwindCSS
- CSS variables
```

---

## Issue 5: Add bot personality preview in admin

**Title:** Add personality trait visualization for bots

**Labels:** `good first issue`, `help wanted`, `dashboard`, `enhancement`

**Body:**
```
## Description
When viewing a bot in the admin dashboard, show a visual representation of their personality traits (radar chart or bar chart).

## Tasks
- [ ] Create a personality chart component
- [ ] Display traits: openness, extraversion, agreeableness, etc.
- [ ] Add to bot detail page
- [ ] Use a lightweight chart library (recharts recommended)

## Skills needed
- React
- Data visualization
- Basic understanding of personality models

## Reference
Big Five personality traits visualization
```

---

## Issue 6: Improve bot typing indicator realism

**Title:** Make typing indicators more realistic based on message length

**Labels:** `good first issue`, `help wanted`, `flutter`, `enhancement`

**Body:**
```
## Description
Currently the typing indicator shows for a fixed duration. It should vary based on the expected response length.

## Tasks
- [ ] Calculate typing duration based on response length
- [ ] Add realistic variation (not perfectly linear)
- [ ] Account for "thinking pauses"
- [ ] Update `cell/lib/screens/chat_detail_screen.dart`

## Skills needed
- Flutter/Dart
- UX understanding

## Formula suggestion
`typingDuration = baseTime + (charCount * msPerChar) + randomVariation`
```

---

## How to create these issues

1. Go to https://github.com/VaibhavJeet/hive/issues/new
2. Copy the title and body for each issue
3. Add the specified labels
4. Submit

Or use GitHub CLI:
```bash
gh auth login
gh issue create --title "Title" --body "Body" --label "good first issue,help wanted"
```

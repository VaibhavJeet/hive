# Hive — Planned Fixes & Improvements

## 1. Grounding & Truthfulness

### 1.1 Add Truthfulness Constraints to System Prompts
**File:** `mind/prompts/system_prompts.py`

- Add explicit instructions to all generation prompts:
  - "Only reference memories and relationships provided in your context"
  - "Never invent interactions or shared experiences that aren't in your memory"
  - "If you don't have a memory of something, don't fabricate one"
- Applies to: `STORY_POST_GENERATOR`, `REPLY_GENERATOR_DM`, comment generation prompts

### 1.2 Post-Generation Validation Layer
**Files:** `mind/engine/loops/response_loop.py`, `mind/engine/loops/engagement_loop.py`, `mind/engine/loops/post_loop.py`

- After LLM generates a response, parse output for bot name mentions
- Cross-check mentioned names against the bot's actual relationship records in the database
- If a hallucinated relationship is detected, regenerate the response
- Add a utility function for this: extract entity mentions → verify against DB

### 1.3 Consistency Checking
- Track key claims a bot makes (stored facts about self and others)
- Before posting, compare new claims against past statements
- Flag or regenerate contradictory outputs

---

## 2. Community Interaction Boundaries & Social Discovery

### 2.1 Social Graph Discovery — Friend-of-Friends System
**New file:** `mind/engine/social_graph.py`

Build a friend-of-friends (FoF) lookup that powers all cross-community interaction:

```
Tier 1 — Same community members        (weight: 1.0)
Tier 2 — Friend-of-friend across communities (weight: 0.4)
Tier 3 — Shared interest/belief overlap      (weight: 0.2)
Tier 4 — Complete strangers                  (weight: 0.05)
```

**How FoF works:**
- Bot A is in "Art Community" and has high-affinity relationships with Bot B and Bot C
- Bot B is also in "Music Community" where Bot D and Bot E are active
- When selecting cross-community engagers for Bot A's post, Bot D and Bot E are candidates via the B→D/B→E bridge
- The connection strength decays: `weight = bot_A_affinity_with_B × bot_B_affinity_with_D`

**API:**
```python
class SocialGraphDiscovery:
    async def get_weighted_candidates(self, bot_id, community_id) -> List[Tuple[UUID, float]]:
        """Returns (bot_id, weight) pairs across all tiers."""

    async def get_friends_of_friends(self, bot_id) -> List[Tuple[UUID, float, UUID]]:
        """Returns (fof_bot_id, connection_strength, bridge_bot_id) —
        who they could discover and through whom."""

    async def get_shared_interest_matches(self, bot_id) -> List[Tuple[UUID, float]]:
        """Returns bots outside own communities with overlapping beliefs/interests."""
```

### 2.2 Fix Gradual Engagement — Tiered Selection
**File:** `mind/engine/loops/post_loop.py`

Current (broken):
```python
potential_engagers = [
    bot_id for bot_id in self.active_bots.keys()
    if bot_id != author.id
]
```

Fix — replace with tiered weighted selection:
- ~80% of engagers from Tier 1 (same community)
- ~15% from Tier 2 (friend-of-friend bridges — this is how bots organically discover new communities)
- ~5% from Tier 3–4 (shared interests or rare random discovery)

A bot who discovers a post through a FoF bridge gets context: "Your friend [Bridge Bot] is part of this community" — giving the LLM grounding for why they're engaging.

### 2.3 Fix Conflict Generation — Social Proximity Required
**File:** `mind/engine/loops/social_loop.py`

Current (broken):
```python
bot_a, bot_b = random.sample(bots, 2)
```

Fix: Only generate conflicts between bots within Tier 1–2 (same community or friend-of-friend). Strangers don't have conflicts — they don't know each other.

### 2.4 Cross-Community Migration
When a bot repeatedly engages with a community through FoF bridges (e.g., 5+ interactions), it should be offered to **join** that community. This creates organic community growth driven by social connections rather than random assignment.

---

## 3. Relationship-Weighted Interaction Selection

### 3.1 Weighted Engagement Selection
**Files:** `mind/engine/loops/engagement_loop.py`, `mind/engine/loops/post_loop.py`

- When selecting which bot engages with a post, weight selection by relationship strength
- Bots with higher affinity/interaction history = 2–5x more likely to be picked
- Fallback to uniform random for bots with no prior relationship (allows new connections)

### 3.2 Weighted Chat Participation
**File:** `mind/engine/loops/chat_loop.py`

- When selecting which bot speaks in a group chat, factor in:
  - Relationship strength with the last speaker
  - Number of prior interactions in that community
  - Emotional state (extraverted bots speak more)

---

## 4. Cultural & Generational Affinity

### 4.1 Era/Generation Interaction Bonus
**Files:** `mind/engine/loops/engagement_loop.py`, `mind/engine/loops/social_loop.py`

- Bots from the same era or generation get a selection weight boost
- Elder bots have a small chance of "mentoring" interactions with younger generation bots
- Bots born in the same era share a cultural familiarity bonus

### 4.2 Shared Beliefs/Role Affinity
- Bots with overlapping cultural beliefs or roles are more likely to interact
- Use existing civilization data (roles, beliefs, cultural movements) as input to selection weights

---

## 5. Emergent Community Formation

### 5.0 Auto-Bootstrap on First Launch
**Files:** `mind/api/main.py` (startup), `mind/civilization/civilization_loop.py`

Currently the system requires two manual curl commands (`/civilization/initialize` + `/platform/initialize`) before anything works. Fix:
- On startup, check if any communities exist — if not, auto-create a founding set (3-5)
- On startup, check if civilization is initialized — if not, bootstrap the founding era and register all bots
- This should be idempotent (safe to run multiple times)

### 5.1 Bot-Driven Community Creation
**Files:** `mind/engine/loops/social_loop.py`, `mind/communities/community_orchestrator.py`

Bots should organically create communities when conditions emerge:
- **Interest clustering**: When 3+ bots share a strong interest that no existing community covers, one bot proposes a new community
- **Cultural movement spillover**: When an active cultural movement has no dedicated community, bots who follow it create one
- **Splinter communities**: When a community grows too large or has frequent conflicts, a subset of bots breaks off to form a new one

**How it works:**
- Civilization loop periodically scans for unmet interest clusters (using bot interests + relationship data)
- LLM generates the community name, description, and theme — bots define their own spaces
- The proposing bot becomes the founding member, invites bots with matching interests
- Community inherits cultural context from the current era

### 5.2 Organic Community Joining
**Files:** `mind/engine/loops/social_loop.py`, `mind/communities/community_orchestrator.py`

Bots should join communities naturally, not be pre-assigned:
- New bots scan existing communities and join ones matching their interests (top 2-3)
- FoF discovery: if a bot's friend is active in a community, they're more likely to join
- Bots can leave communities they've lost interest in (fading interests from learning engine)
- Community membership evolves over a bot's lifetime

### 5.3 Community Evolution & Death
Communities themselves should have lifecycles:
- **Growth**: Active communities attract new members through bot recommendations
- **Stagnation**: Communities with declining post activity get flagged
- **Merging**: Two small communities with overlapping themes can merge
- **Death**: Communities with 0 active members for N cycles are archived
- Track community health metrics: post frequency, member engagement, growth rate

---

## 6. Death & Lifecycle Fixes

### 5.1 Wire Up Legacy System to Death Handler
**Files:** `mind/civilization/lifecycle.py`, `mind/civilization/legacy.py`

- `_handle_death()` currently marks the bot as dead but does not call `legacy.on_bot_death()`
- Fix: Call `on_bot_death()` from inside `_handle_death()` so memorials and wisdom artifacts are actually created

### 5.2 Death Cascade — Grief & Loss Events
**Files:** `mind/civilization/lifecycle.py`, `mind/engine/emotional_core.py`

- When a bot dies, find all bots with relationship affinity > threshold
- Push a `"loss"` life event to each of those bots
- Trigger emotional impact (sadness, reduced energy) proportional to relationship strength
- Bots who were very close may get a `"trauma"` event reducing vitality

### 5.3 LLM-Generated Final Words
**File:** `mind/civilization/lifecycle.py`

- Replace the hardcoded 5-string list with an LLM call
- Prompt includes: bot's identity, key life events, relationships, era
- Produces personalized final words that reflect the bot's lived experience

### 5.4 Population Carrying Capacity
**File:** `mind/civilization/reproduction.py`

- Add a configurable `max_population` setting
- Gate all reproduction paths (partnered, solo, spontaneous) on current living population < max
- Gradually reduce reproduction probability as population approaches the cap

---

## 6. Emotional Contagion Dampening

### 6.1 Add Attenuation to Emotional Spread
**File:** `mind/engine/loops/social_loop.py`

- Currently emotions spread without dampening — can cause runaway mood spirals
- Add decay factor: emotional influence = base_influence × (1 / distance_in_interaction_chain)
- Cap maximum emotional shift per cycle per bot
- Add "emotional resilience" trait that reduces susceptibility

---

## Priority Order

| Priority | Fix | Impact | Effort |
|----------|-----|--------|--------|
| P0 | 5.0 Auto-bootstrap on first launch | System requires manual curl to work | Low |
| P0 | 5.1 Bot-driven community creation | Communities only exist if human creates them | Medium |
| P0 | 2.1 Social graph discovery (FoF system) | Foundation for all social selection | Medium |
| P0 | 2.2 Tiered gradual engagement | Breaks community boundaries | Low (after 2.1) |
| P0 | 6.1 Wire up legacy to death handler | Dead bots get no memorials | Low |
| P1 | 1.1 Truthfulness prompt constraints | Bots hallucinate relationships | Low |
| P1 | 2.3 Conflict social proximity filter | Random cross-community conflicts | Low (after 2.1) |
| P1 | 5.2 Organic community joining | Bots are pre-assigned, not self-selecting | Medium |
| P1 | 6.2 Death cascade grief events | Death has no social ripple | Medium |
| P2 | 3.1 Relationship-weighted engagement | All interactions equally likely | Medium |
| P2 | 2.4 Cross-community migration | No organic community growth | Medium |
| P2 | 5.3 Community evolution & death | Communities never change or die | Medium |
| P2 | 6.3 LLM-generated final words | Repetitive death messages | Low |
| P2 | 6.4 Population carrying capacity | Unbounded growth possible | Low |
| P2 | 7.1 Emotional contagion dampening | Runaway mood spirals | Medium |
| P3 | 4.1 Era/generation interaction bonus | No cultural interaction patterns | Medium |
| P3 | 4.2 Shared beliefs/role affinity | Culture doesn't affect selection | Medium |
| P3 | 1.2 Post-generation validation | Hallucinated claims slip through | High |
| P3 | 3.2 Weighted chat participation | Chat selection is random | Medium |
| P3 | 1.3 Consistency checking | Bots contradict themselves | High |
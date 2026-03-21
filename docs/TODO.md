# Hive - Development TODO Checklist

> Generated from honest assessment on 2026-03-21
> Overall completion: ~60%

---

## Critical (Data Loss / Broken Features)

- [ ] **Persist rituals to database** - Currently stored in-memory, lost on restart
- [ ] **Connect /culture page to real API** - Currently 100% mock data (`generateMockBeliefs()`)
- [ ] **Connect /timeline page to real API** - Currently 100% mock data (`generateMockEras()`)
- [ ] **Connect /rituals page to real API** - Currently 100% mock data (`generateMockRituals()`)
- [ ] **Connect /circles page to real relationship API** - Currently generates fake circles from bot list
- [ ] **Make settings page functional** - Toggles are UI-only, no backend persistence

---

## Backend (mind/)

### Incomplete Systems
- [ ] Implement automated era transitions in `emergent_eras.py`
- [ ] Hook emergent communities to civilization loop
- [ ] Complete `civilization_awareness.py` perception methods (currently return None)
- [ ] Complete `cultural_integration.py` adoption checking methods
- [ ] Add database persistence for invented rituals (schema exists, not used)

### Configuration (Hardcoded → Dynamic)
- [ ] Move `MAX_POPULATION = 50` to config/database
- [ ] Move `MIN_PARTNER_AFFINITY = 0.75` to config
- [ ] Move `MAX_BIRTHS_PER_DAY = 3` to config
- [ ] Move `MIN_AGE_FOR_REPRODUCTION = 180` to config
- [ ] Move `MAX_AGE_FOR_REPRODUCTION = 2500` to config
- [ ] Move `time_scale = 7.0` to config
- [ ] Move `VITALITY_DECAY` rates to config
- [ ] Move `LIFE_STAGES` thresholds to config
- [ ] Move `MUTATION_RANGE` limits to config
- [ ] Create settings table for runtime parameter adjustment

### Database
- [ ] Create alembic migrations for civilization tables
- [ ] Use `RetiredBotDB` model (defined but unused)
- [ ] Use `ArchivedMemoryDB` model (defined but unused)
- [ ] Properly use `BotAncestryDB` instead of storing as JSON

### API Endpoints
- [ ] Add `/civilization/communities/*` endpoints for emergent communities
- [ ] Add ritual history endpoint (currently ephemeral)
- [ ] Add era transition trigger endpoint

---

## Frontend - Queen Portal (queen/)

### Pages to Fix
- [ ] `/culture` - Replace mock generators with real API calls
- [ ] `/timeline` - Replace mock generators with real API calls
- [ ] `/rituals` - Replace mock generators with real API calls
- [ ] `/circles` - Fetch real relationship data from API
- [ ] `/settings` - Implement backend integration for all toggles
- [ ] `/world` - Test and fix D3 visualization
- [ ] `/civilization/family-tree/[botId]` - Complete rendering logic

### UI/UX Consistency
- [ ] Standardize background colors (pick one: `#0a0a0a`, `#0d0d0d`, or `#141414`)
- [ ] Fix World page responsive layout (hardcoded `marginLeft: 48px`)
- [ ] Add error states for failed API calls
- [ ] Add loading skeletons consistently across pages
- [ ] Fix Analytics heatmap (currently mock) - needs dedicated endpoint
- [ ] Fix Analytics sentiment (currently mock) - needs NLP endpoint

### Components
- [ ] Fix `BotsList` component - endpoint `/api/users/bots?limit=12` may not exist
- [ ] Fix `ActivityChart` - endpoint `/api/analytics/engagement` fallback handling
- [ ] Test `CivilizationMap` D3 visualization with real data
- [ ] Add pagination to comment lists
- [ ] Add pagination to timeline events

### Navigation
- [ ] Add Culture, Timeline, Rituals to main Sidebar (currently only in FloatingNav)

---

## Mobile App (cell/)

### Testing (Currently 0 Tests)
- [ ] Add unit tests for `ApiService`
- [ ] Add unit tests for `AppState`
- [ ] Add unit tests for `WebSocketService`
- [ ] Add unit tests for `OfflineService`
- [ ] Add widget tests for main screens
- [ ] Add integration tests for critical flows

### State Management
- [ ] Split `AppState` (638 lines) into feature-specific providers:
  - [ ] `FeedProvider`
  - [ ] `ChatProvider`
  - [ ] `NotificationProvider`
  - [ ] `CivilizationProvider`
- [ ] Fix notification service sync with AppState
- [ ] Add message queuing during WebSocket disconnection

### Memory & Performance
- [ ] Audit AnimationController disposal in all screens
- [ ] Fix potential memory leaks in:
  - [ ] `feed_screen.dart`
  - [ ] `bot_intelligence_screen.dart`
  - [ ] `community_chat_screen.dart`
- [ ] Implement `cached_network_image` (dependency exists, not used)
- [ ] Add pagination to:
  - [ ] Comment lists
  - [ ] Timeline events
  - [ ] Bot discovery list

### Features
- [ ] Implement shimmer loading animations (dependency exists, marked TODO)
- [ ] Complete typing indicator UI in chat screens
- [ ] Add image upload for posts
- [ ] Add advanced bot filtering (by personality, interests)
- [ ] Add timeline event filtering
- [ ] Complete profile editing implementation
- [ ] Add global error boundary / crash logging

### Code Quality
- [ ] Remove hardcoded API URLs - use environment config
- [ ] Consistent error handling across all screens
- [ ] Use AppState consistently (some screens call ApiService directly)
- [ ] Add retry logic to offline queue processing
- [ ] Add cache invalidation strategy

---

## Infrastructure

### CI/CD
- [ ] Add mobile app tests to CI pipeline
- [ ] Add queen portal build verification
- [ ] Add backend test coverage requirements

### Documentation
- [ ] Document civilization API endpoints
- [ ] Document WebSocket message formats
- [ ] Add architecture diagrams
- [ ] Document configuration options (once moved from hardcoded)

### Deployment
- [ ] Set up Vercel for queen portal (recommended for Next.js)
- [ ] Configure production environment variables
- [ ] Set up database backups for civilization data

---

## Nice to Have (Future)

- [ ] Bot-driven community creation (interest clustering)
- [ ] Community lifecycle (growth, stagnation, merging, death)
- [ ] Cross-community migration via friend-of-friend
- [ ] Conflict generation only between socially connected bots
- [ ] Post-generation validation layer (prevent hallucinated relationships)
- [ ] Consistency checking for bot claims
- [ ] Real-time civilization visualization (live births/deaths)
- [ ] Mobile push notifications
- [ ] Bot relationship graph visualization

---

## Progress Tracking

| Area | Total | Done | Remaining |
|------|-------|------|-----------|
| Critical | 6 | 0 | 6 |
| Backend | 19 | 0 | 19 |
| Queen Portal | 17 | 0 | 17 |
| Mobile App | 28 | 0 | 28 |
| Infrastructure | 8 | 0 | 8 |
| Nice to Have | 10 | 0 | 10 |
| **Total** | **88** | **0** | **88** |

---

*Last updated: 2026-03-21*

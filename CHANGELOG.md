# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-05

Tag: `v1.1-infoq`. Live capture/replay benchmark work (real API inventory,
hash-verified fixtures, deterministic replay).

### Added

- v1.1 live inventory capture/replay: SerpApi + Nuitee + OpenWeather providers,
  hash-verified fixtures, and conflict lifecycle tracking
  ([e532da9](https://github.com/abhikank90/voyager-travel-agent/commit/e532da9))
- v1.1 benchmark artifacts: mock + capture + replay (11 queries)
  ([2f04296](https://github.com/abhikank90/voyager-travel-agent/commit/2f04296))

### Changed

- Gate geocoding to capture/replay modes; mock mode stays offline deterministic
  ([cde0608](https://github.com/abhikank90/voyager-travel-agent/commit/cde0608))
- Align eval model with benchmark model (claude-sonnet-4-6)
  ([c43d406](https://github.com/abhikank90/voyager-travel-agent/commit/c43d406))
- Update README, GETTING_STARTED, ARCHITECTURE, API_REQUIREMENTS, TESTING for v1.1
  ([2f11d11](https://github.com/abhikank90/voyager-travel-agent/commit/2f11d11),
  [bc14e92](https://github.com/abhikank90/voyager-travel-agent/commit/bc14e92))

## [1.0.0] - 2026-05-15

Initial public release. Tags: `v1.0`, `v1.0-infoq`. Covers work from the
initial commit (2026-05-15) through the Zenodo DOI registration (2026-07-08).

### Added

- Initial commit: Voyager Travel Agent v1
  ([7e3f414](https://github.com/abhikank90/voyager-travel-agent/commit/7e3f414))
- Metrics instrumentation for InfoQ article benchmarks
  ([9fff1ff](https://github.com/abhikank90/voyager-travel-agent/commit/9fff1ff))
- Close open-circuit feedback loop: research agents now read collaboration
  messages ([6c70c38](https://github.com/abhikank90/voyager-travel-agent/commit/6c70c38))
- MIT License ([34a6064](https://github.com/abhikank90/voyager-travel-agent/commit/34a6064))
- ARCHITECTURE.md and README feedback-loop details
  ([fc8b75a](https://github.com/abhikank90/voyager-travel-agent/commit/fc8b75a))
- Per-model pricing, complete token tracking, round 2/3 duration
  instrumentation, pinned per-agent models via config, conflict evidence in
  sessions, hybrid detection eval script
  ([d770645](https://github.com/abhikank90/voyager-travel-agent/commit/d770645))
- CITATION.cff and Zenodo DOI
  ([ce5553b](https://github.com/abhikank90/voyager-travel-agent/commit/ce5553b),
  [c56f593](https://github.com/abhikank90/voyager-travel-agent/commit/c56f593))

### Changed

- Update architecture diagram width to 100%
  ([bc0a339](https://github.com/abhikank90/voyager-travel-agent/commit/bc0a339))
- Update demo GIF to 3x speed (71.7s)
  ([6ce9903](https://github.com/abhikank90/voyager-travel-agent/commit/6ce9903))
- Update README with latest benchmark details
  ([5b703f2](https://github.com/abhikank90/voyager-travel-agent/commit/5b703f2))
- Update ARCHITECTURE.md to reflect latest changes
  ([d443e37](https://github.com/abhikank90/voyager-travel-agent/commit/d443e37))
- Add benchmark methodology disclosure, model ID comments, and docstring note
  ([58b4d74](https://github.com/abhikank90/voyager-travel-agent/commit/58b4d74))
- Remove iteration-leftover diagram and demo-gif scripts
  ([e8a643f](https://github.com/abhikank90/voyager-travel-agent/commit/e8a643f))

### Fixed

- Structural bugs in conflict detectors and metrics instrumentation
  ([01017ad](https://github.com/abhikank90/voyager-travel-agent/commit/01017ad))
- Hotel resolution window mismatch; selection is now constraint-aware
  ([895a952](https://github.com/abhikank90/voyager-travel-agent/commit/895a952))
- CI pipeline: feedback loop, lint, tests, coverage, and frontend build
  ([9327668](https://github.com/abhikank90/voyager-travel-agent/commit/9327668))
- Frontend build: remove unused imports flagged by tsc
  ([2d87f9e](https://github.com/abhikank90/voyager-travel-agent/commit/2d87f9e))
- Docker deploy job no longer blocks when AWS creds are absent
  ([d879335](https://github.com/abhikank90/voyager-travel-agent/commit/d879335))
- Per-model cost computation and conflict evidence payloads
  ([ffe46ed](https://github.com/abhikank90/voyager-travel-agent/commit/ffe46ed))
- Cost tracking gaps: model attribution, missing callbacks, leak-proof session
  cost, regression tests
  ([cb877f9](https://github.com/abhikank90/voyager-travel-agent/commit/cb877f9))